
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, time, timedelta
from contextlib import closing

# ==================================================
# CONFIGURACIÓN
# ==================================================

st.set_page_config(
    page_title="Gestión de Almacén",
    page_icon="📦",
    layout="wide"
)

DB = "almacen.db"

NOMBRES = [
    "Lunes", "Martes", "Miércoles",
    "Jueves", "Viernes", "Sábado"
]


# ==================================================
# BASE DE DATOS
# ==================================================

def conectar():
    return sqlite3.connect(DB)


def crear_base_datos():

    with closing(conectar()) as conn:
        with conn:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS servicios (
                    fecha TEXT PRIMARY KEY,
                    picks INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ajustes_pendientes (
                    fecha_hora TEXT PRIMARY KEY,
                    pendientes INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS asignaciones_servicio (
                    fecha_hora TEXT PRIMARY KEY,
                    fecha_servicio TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS configuracion (
                    clave TEXT PRIMARY KEY,
                    valor INTEGER
                )
            """)


def obtener_servicio(fecha):

    with closing(conectar()) as conn:
        resultado = conn.execute(
            "SELECT picks FROM servicios WHERE fecha=?",
            (fecha,)
        ).fetchone()

    return int(resultado[0]) if resultado else 0


def guardar_servicio(fecha, picks):

    with closing(conectar()) as conn:
        with conn:
            conn.execute("""
                INSERT INTO servicios (fecha, picks)
                VALUES (?, ?)
                ON CONFLICT(fecha)
                DO UPDATE SET picks=excluded.picks
            """, (fecha, int(picks)))


def guardar_sidebar_servicio(fecha, clave):
    guardar_servicio(fecha, st.session_state[clave])


def obtener_configuracion(clave, defecto):

    with closing(conectar()) as conn:
        resultado = conn.execute(
            "SELECT valor FROM configuracion WHERE clave=?",
            (clave,)
        ).fetchone()

    return int(resultado[0]) if resultado else defecto


def guardar_configuracion(clave, valor):

    with closing(conectar()) as conn:
        with conn:
            conn.execute("""
                INSERT INTO configuracion (clave, valor)
                VALUES (?, ?)
                ON CONFLICT(clave)
                DO UPDATE SET valor=excluded.valor
            """, (clave, int(valor)))


def guardar_productividad():

    guardar_configuracion(
        "productividad",
        st.session_state.productividad
    )


def obtener_ajustes():

    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT fecha_hora, pendientes
            FROM ajustes_pendientes
        """).fetchall()

    return {
        fecha_hora: int(pendientes)
        for fecha_hora, pendientes in filas
    }


def obtener_asignaciones():

    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT fecha_hora, fecha_servicio
            FROM asignaciones_servicio
        """).fetchall()

    return {
        fecha_hora: fecha_servicio
        for fecha_hora, fecha_servicio in filas
    }


# ==================================================
# GUARDAR CAMBIOS DE LA TABLA
# ==================================================

def guardar_ediciones_pendientes(editor_key):

    estado = st.session_state.get(editor_key, {})
    cambios = estado.get("edited_rows", {})

    if not cambios:
        return

    fechas_filas = st.session_state.get(
        f"{editor_key}_fechas",
        []
    )

    filas_cambiadas = []

    for indice, valores in cambios.items():

        filas_cambiadas.append((
            int(indice),
            valores
        ))

    filas_cambiadas.sort(key=lambda x: x[0])

    with closing(conectar()) as conn:

        with conn:

            for indice, valores in filas_cambiadas:

                if indice >= len(fechas_filas):
                    continue

                fecha_hora = fechas_filas[indice]
                fecha = fecha_hora[:10]

                # Cambio del día de servicio.
                if "Día de servicio" in valores:

                    nuevo_servicio = valores["Día de servicio"]

                    conn.execute("""
                        INSERT INTO asignaciones_servicio (
                            fecha_hora,
                            fecha_servicio
                        )
                        VALUES (?, ?)
                        ON CONFLICT(fecha_hora)
                        DO UPDATE SET
                        fecha_servicio=excluded.fecha_servicio
                    """, (fecha_hora, nuevo_servicio))

                    # Eliminar ajustes posteriores de ese mismo
                    # servicio para permitir su recálculo.
                    conn.execute("""
                        DELETE FROM ajustes_pendientes
                        WHERE fecha_hora > ?
                        AND fecha_hora IN (
                            SELECT fecha_hora
                            FROM asignaciones_servicio
                            WHERE fecha_servicio = ?
                        )
                    """, (fecha_hora, nuevo_servicio))

                # Cambio manual de picks restantes.
                if "Picks restantes" in valores:

                    nuevo_valor = int(
                        valores["Picks restantes"]
                    )

                    conn.execute("""
                        INSERT INTO ajustes_pendientes (
                            fecha_hora,
                            pendientes
                        )
                        VALUES (?, ?)
                        ON CONFLICT(fecha_hora)
                        DO UPDATE SET
                        pendientes=excluded.pendientes
                    """, (fecha_hora, nuevo_valor))

    st.session_state.version_tabla += 1


# ==================================================
# INICIALIZACIÓN
# ==================================================

crear_base_datos()

if "semana" not in st.session_state:

    hoy = date.today()

    st.session_state.semana = hoy - timedelta(
        days=hoy.weekday()
    )

if "version_tabla" not in st.session_state:
    st.session_state.version_tabla = 0

if "productividad" not in st.session_state:

    st.session_state.productividad = obtener_configuracion(
        "productividad",
        3000
    )


# ==================================================
# ESTILO
# ==================================================

st.markdown("""
<style>
    .stApp {
        background-color: #f3f5f9;
    }

    h1, h2, h3 {
        color: #17243a;
    }

    .block-container {
        padding-top: 2rem;
    }

    [data-testid="stSidebar"] {
        min-width: 280px;
    }

    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.35rem;
    }

    [data-testid="stSidebar"] [data-testid="stExpander"] {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        border: none !important;
    }

    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        padding-top: 7px !important;
        padding-bottom: 7px !important;
    }

    [data-testid="stSidebar"] .stMarkdown {
        margin-bottom: 0 !important;
    }

    [data-testid="stSidebar"] hr {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)


# ==================================================
# SIDEBAR: SEMANA DE SERVICIO
# ==================================================

st.sidebar.title("📦 ALMACÉN")
st.sidebar.caption("Panel de control")

st.sidebar.subheader("📅 SEMANA DE SERVICIO")

fecha_elegida = st.sidebar.date_input(
    "Seleccionar semana",
    value=st.session_state.semana,
    format="DD/MM/YYYY"
)

lunes = fecha_elegida - timedelta(
    days=fecha_elegida.weekday()
)

st.session_state.semana = lunes

dias = [
    lunes + timedelta(days=i)
    for i in range(6)
]


# ==================================================
# PICKS POR SERVICIO
# ==================================================

with st.sidebar.expander(
    "📋 PICKS POR SERVICIO",
    expanded=False
):

    st.caption("Picks previstos de cada día.")

    for i, dia in enumerate(dias):

        fecha = dia.isoformat()
        clave = f"servicio_{fecha}"

        if clave not in st.session_state:
            st.session_state[clave] = obtener_servicio(fecha)

        st.number_input(
            f"{NOMBRES[i]} {dia.strftime('%d/%m')}",
            min_value=0,
            max_value=1000000,
            step=1,
            key=clave,
            on_change=guardar_sidebar_servicio,
            args=(fecha, clave)
        )


# ==================================================
# PRODUCTIVIDAD
# ==================================================

st.sidebar.subheader("⚙️ PRODUCTIVIDAD")

st.sidebar.slider(
    "Picks por hora",
    min_value=1000,
    max_value=6000,
    step=500,
    key="productividad",
    on_change=guardar_productividad
)

productividad = int(st.session_state.productividad)

st.sidebar.caption(
    f"Productividad actual: {productividad:,} picks/h"
)


# ==================================================
# CABECERA CENTRAL
# ==================================================

st.title("📦 Gestión de almacén")

st.caption(
    f"Semana de servicio: {dias[0].strftime('%d/%m/%Y')} "
    f"al {dias[-1].strftime('%d/%m/%Y')}"
)

st.divider()

st.header("📊 Previsión de picks restantes")


# ==================================================
# FILTROS CENTRALES
# ==================================================

st.markdown("### 🗓️ Seleccionar intervalo de consulta")

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.markdown("**Fecha inicio**")

    fecha_inicio = st.date_input(
        "Fecha inicio",
        value=dias[0],
        format="DD/MM/YYYY",
        key="filtro_fecha_inicio",
        label_visibility="collapsed"
    )

with col2:

    st.markdown("**Hora inicio**")

    hora_inicio = st.time_input(
        "Hora inicio",
        value=time(0, 0),
        step=timedelta(hours=1),
        key="filtro_hora_inicio",
        label_visibility="collapsed"
    )

with col3:

    st.markdown("**Fecha fin**")

    fecha_final = st.date_input(
        "Fecha fin",
        value=dias[-1],
        format="DD/MM/YYYY",
        key="filtro_fecha_final",
        label_visibility="collapsed"
    )

with col4:

    st.markdown("**Hora fin**")

    hora_final = st.time_input(
        "Hora fin",
        value=time(23, 0),
        step=timedelta(hours=1),
        key="filtro_hora_final",
        label_visibility="collapsed"
    )

st.divider()


# ==================================================
# CÁLCULO DE PLANIFICACIÓN
# ==================================================

def calcular_planificacion(
    fecha_inicio,
    fecha_final,
    productividad
):

    ajustes = obtener_ajustes()
    asignaciones = obtener_asignaciones()

    registros = []

    # Saldo independiente para cada día de servicio.
    saldos = {}

    dia = fecha_inicio

    while dia <= fecha_final:

        for hora in range(24):

            fecha_hora_dt = datetime.combine(
                dia,
                time(hour=hora)
            )

            fecha_hora = fecha_hora_dt.strftime(
                "%Y-%m-%d %H:%M"
            )

            # Si no existe asignación manual,
            # se utiliza el día natural de la fecha y hora.
            dia_servicio = asignaciones.get(
                fecha_hora,
                dia.isoformat()
            )

            # Obtener los picks totales de ese servicio.
            if dia_servicio not in saldos:

                saldos[dia_servicio] = obtener_servicio(
                    dia_servicio
                )

            # Si hay un ajuste manual, prevalece.
            if fecha_hora in ajustes:

                saldos[dia_servicio] = ajustes[fecha_hora]

            else:

                # La primera hora asignada a un servicio
                # muestra el total inicial.
                # Las siguientes descuentan productividad.
                ya_iniciado = any(
                    registro["Día de servicio"] == dia_servicio
                    for registro in registros
                )

                if ya_iniciado:

                    saldos[dia_servicio] = max(
                        saldos[dia_servicio] - productividad,
                        0
                    )

            registros.append({
                "Fecha y hora": fecha_hora_dt,
                "Día de servicio": dia_servicio,
                "Picks restantes": int(
                    saldos[dia_servicio]
                )
            })

        dia += timedelta(days=1)

    return pd.DataFrame(registros)


# ==================================================
# GENERAR TABLA
# ==================================================

inicio = datetime.combine(
    fecha_inicio,
    hora_inicio
)

final = datetime.combine(
    fecha_final,
    hora_final
)

if inicio > final:

    st.error(
        "La fecha y hora de inicio no pueden ser posteriores "
        "a la fecha y hora de fin."
    )

else:

    tabla_completa = calcular_planificacion(
        fecha_inicio,
        fecha_final,
        productividad
    )

    # Filtrar el intervalo exacto.
    tabla = tabla_completa[
        (tabla_completa["Fecha y hora"] >= inicio) &
        (tabla_completa["Fecha y hora"] <= final)
    ].copy().reset_index(drop=True)

    if tabla.empty:

        st.warning(
            "No hay registros dentro del intervalo seleccionado."
        )

    else:

        # Fechas reales para guardar los cambios.
        fechas_editor = [
            valor.strftime("%Y-%m-%d %H:%M")
            for valor in tabla["Fecha y hora"]
        ]

        # Opciones de días de servicio disponibles.
        opciones_servicio = []

        dia_opcion = fecha_inicio

        while dia_opcion <= fecha_final:

            opciones_servicio.append(
                dia_opcion.isoformat()
            )

            dia_opcion += timedelta(days=1)

        # Mostrar fechas en formato español.
        tabla["Fecha y hora"] = tabla[
            "Fecha y hora"
        ].dt.strftime("%d/%m/%Y %H:%M")

        tabla["Día de servicio"] = tabla[
            "Día de servicio"
        ].apply(
            lambda x: datetime.strptime(
                x, "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
        )

        # Las opciones del desplegable también en formato español.
        opciones_visibles = [
            datetime.strptime(
                x, "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
            for x in opciones_servicio
        ]

        editor_key = (
            f"tabla_planificacion_{st.session_state.version_tabla}"
        )

        st.session_state[f"{editor_key}_fechas"] = fechas_editor

        st.markdown(
            "Puedes cambiar el **Día de servicio** de cada hora "
            "y los picks se descontarán de ese servicio."
        )

        st.data_editor(
            tabla,
            use_container_width=True,
            hide_index=True,
            height=650,
            key=editor_key,
            on_change=guardar_ediciones_pendientes,
            args=(editor_key,),
            disabled=["Fecha y hora"],
            column_config={

                "Fecha y hora": st.column_config.TextColumn(
                    "Fecha y hora",
                    width="medium"
                ),

                "Día de servicio": st.column_config.SelectboxColumn(
                    "Día de servicio",
                    options=opciones_visibles,
                    required=True,
                    width="medium"
                ),

                "Picks restantes": st.column_config.NumberColumn(
                    "Picks restantes",
                    min_value=0,
                    max_value=1000000,
                    step=1,
                    format="%d",
                    width="medium"
                )
            }
        )


# ==================================================
# RESUMEN
# ==================================================

st.divider()

col1, col2 = st.columns(2)

col1.metric(
    "Productividad configurada",
    f"{productividad:,} picks/h"
)

col2.metric(
    "Días consultados",
    (fecha_final - fecha_inicio).days + 1
)

st.caption(
    "Las asignaciones de días de servicio y los ajustes manuales "
    "se guardan en la base de datos."
)
