
import streamlit as st
import sqlite3
import pandas as pd

from datetime import date, datetime, time, timedelta
from contextlib import closing


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

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


# ==========================================================
# BASE DE DATOS
# ==========================================================

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
                CREATE TABLE IF NOT EXISTS configuracion (
                    clave TEXT PRIMARY KEY,
                    valor INTEGER
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ajustes_planificacion (
                    fecha_hora TEXT NOT NULL,
                    fecha_servicio TEXT NOT NULL,
                    pendientes INTEGER NOT NULL,
                    PRIMARY KEY (fecha_hora, fecha_servicio)
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
            SELECT fecha_hora, fecha_servicio, pendientes
            FROM ajustes_planificacion
        """).fetchall()

    return {
        (fecha_hora, fecha_servicio): int(pendientes)
        for fecha_hora, fecha_servicio, pendientes in filas
    }


# ==========================================================
# GUARDAR EDICIONES MANUALES
# ==========================================================

def guardar_ediciones(editor_key):

    estado = st.session_state.get(editor_key, {})
    cambios = estado.get("edited_rows", {})

    if not cambios:
        return

    referencias = st.session_state.get(
        f"{editor_key}_referencias",
        []
    )

    for indice, valores in cambios.items():

        indice = int(indice)

        if indice >= len(referencias):
            continue

        referencia = referencias[indice]

        # El desplegable de la primera fila determina
        # el primer día de servicio.
        if indice == 0 and "Día de servicio" in valores:

            try:
                fecha_elegida = datetime.strptime(
                    valores["Día de servicio"],
                    "%d/%m/%Y"
                ).date()

                st.session_state.servicio_inicial = (
                    fecha_elegida.isoformat()
                )

            except ValueError:
                pass

        # Guardar las modificaciones manuales de picks.
        if "Picks restantes" in valores:

            if referencia["estado"] == "Fin de servicio":
                continue

            pendientes = max(
                0,
                int(valores["Picks restantes"])
            )

            with closing(conectar()) as conn:

                with conn:
                    conn.execute("""
                        INSERT INTO ajustes_planificacion (
                            fecha_hora,
                            fecha_servicio,
                            pendientes
                        )
                        VALUES (?, ?, ?)
                        ON CONFLICT(fecha_hora, fecha_servicio)
                        DO UPDATE SET pendientes=excluded.pendientes
                    """, (
                        referencia["fecha_hora"],
                        referencia["fecha_servicio"],
                        pendientes
                    ))

    st.session_state.version_tabla += 1


# ==========================================================
# INICIALIZACIÓN
# ==========================================================

crear_base_datos()

if "semana" not in st.session_state:

    hoy = date.today()

    st.session_state.semana = (
        hoy - timedelta(days=hoy.weekday())
    )

if "version_tabla" not in st.session_state:
    st.session_state.version_tabla = 0

if "productividad" not in st.session_state:

    st.session_state.productividad = obtener_configuracion(
        "productividad",
        3500
    )


# ==========================================================
# ESTILO GENERAL
# ==========================================================

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
</style>
""", unsafe_allow_html=True)


# ==========================================================
# SIDEBAR
# ==========================================================

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


# ==========================================================
# PICKS POR SERVICIO
# ==========================================================

with st.sidebar.expander(
    "📋 PICKS POR SERVICIO",
    expanded=False
):

    st.caption("Picks totales de cada día.")

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


# ==========================================================
# PRODUCTIVIDAD
# ==========================================================

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
    f"Productividad: {productividad:,} picks/h"
)


# ==========================================================
# CÁLCULO CONSECUTIVO DE SERVICIOS
# ==========================================================

def calcular_planificacion(
    inicio,
    final,
    servicio_inicial,
    productividad
):

    ajustes = obtener_ajustes()

    registros = []

    cursor = inicio
    dia_servicio = servicio_inicial

    servicios_procesados = 0
    limite = 1000

    while cursor <= final and servicios_procesados < limite:

        fecha_servicio = dia_servicio.isoformat()

        # Cargar los picks totales del servicio.
        saldo = float(
            obtener_servicio(fecha_servicio)
        )

        clave_ajuste = (
            cursor.strftime("%Y-%m-%d %H:%M:%S"),
            fecha_servicio
        )

        if clave_ajuste in ajustes:
            saldo = float(ajustes[clave_ajuste])

        # Inicio del servicio.
        registros.append({
            "Fecha y hora": cursor,
            "Día de servicio": dia_servicio.strftime("%d/%m/%Y"),
            "Picks restantes": int(round(saldo)),
            "Estado": "Inicio de servicio"
        })

        # Si no hay picks, termina inmediatamente.
        if saldo <= 0:

            registros.append({
                "Fecha y hora": cursor,
                "Día de servicio": dia_servicio.strftime("%d/%m/%Y"),
                "Picks restantes": 0,
                "Estado": "Fin de servicio"
            })

            dia_servicio += timedelta(days=1)
            servicios_procesados += 1
            continue

        terminado = False

        while cursor < final and saldo > 0:

            siguiente_hora = (
                cursor.replace(
                    minute=0,
                    second=0,
                    microsecond=0
                ) + timedelta(hours=1)
            )

            segundos_necesarios = (
                saldo / productividad
            ) * 3600

            hora_fin_servicio = (
                cursor + timedelta(seconds=segundos_necesarios)
            )

            siguiente_evento = min(
                siguiente_hora,
                hora_fin_servicio,
                final
            )

            segundos = (
                siguiente_evento - cursor
            ).total_seconds()

            picks_procesados = (
                productividad * segundos / 3600
            )

            saldo = max(
                0.0,
                saldo - picks_procesados
            )

            cursor = siguiente_evento

            # Fin exacto del servicio.
            if saldo <= 0.000001:

                saldo = 0

                registros.append({
                    "Fecha y hora": cursor,
                    "Día de servicio": dia_servicio.strftime("%d/%m/%Y"),
                    "Picks restantes": 0,
                    "Estado": "Fin de servicio"
                })

                terminado = True
                break

            # Fin del intervalo consultado.
            if cursor >= final:

                registros.append({
                    "Fecha y hora": cursor,
                    "Día de servicio": dia_servicio.strftime("%d/%m/%Y"),
                    "Picks restantes": int(round(saldo)),
                    "Estado": "En curso"
                })

                break

            # Ajuste manual en ese momento.
            clave_ajuste = (
                cursor.strftime("%Y-%m-%d %H:%M:%S"),
                fecha_servicio
            )

            if clave_ajuste in ajustes:
                saldo = float(ajustes[clave_ajuste])

            registros.append({
                "Fecha y hora": cursor,
                "Día de servicio": dia_servicio.strftime("%d/%m/%Y"),
                "Picks restantes": int(round(saldo)),
                "Estado": "En curso"
            })

        if terminado:

            # El siguiente servicio empieza inmediatamente.
            dia_servicio += timedelta(days=1)
            servicios_procesados += 1

        else:
            break

    return pd.DataFrame(registros)


# ==========================================================
# PANTALLA PRINCIPAL
# ==========================================================

st.title("📦 Gestión de almacén")

st.caption(
    f"Semana de servicio: {dias[0].strftime('%d/%m/%Y')} "
    f"al {dias[-1].strftime('%d/%m/%Y')}"
)

st.divider()

st.header("📊 Previsión de picks restantes")


# ==========================================================
# FILTROS CENTRALES
# ==========================================================

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
        value=time(22, 0),
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
        key="filtro_hora_final",
        label_visibility="collapsed"
    )


# ==========================================================
# TABLA Y COLORES
# ==========================================================

st.divider()

inicio = datetime.combine(fecha_inicio, hora_inicio)
final = datetime.combine(fecha_final, hora_final)

if inicio >= final:

    st.error(
        "La fecha y hora final deben ser posteriores "
        "a la fecha y hora inicial."
    )

else:

    # Fechas disponibles para el desplegable.
    opciones_fechas = []

    dia_opcion = fecha_inicio

    while dia_opcion <= fecha_final + timedelta(days=30):

        opciones_fechas.append(
            dia_opcion.strftime("%d/%m/%Y")
        )

        dia_opcion += timedelta(days=1)

    # Servicio inicial.
    if "servicio_inicial" not in st.session_state:
        st.session_state.servicio_inicial = fecha_inicio.isoformat()

    servicio_actual = datetime.strptime(
        st.session_state.servicio_inicial,
        "%Y-%m-%d"
    ).date()

    servicio_visible = servicio_actual.strftime("%d/%m/%Y")

    if servicio_visible not in opciones_fechas:
        opciones_fechas.insert(0, servicio_visible)

    # Calcular la planificación.
    tabla = calcular_planificacion(
        inicio,
        final,
        servicio_actual,
        productividad
    )

    if tabla.empty:

        st.warning("No hay datos para mostrar.")

    else:

        # Referencias internas para guardar los ajustes.
        referencias = []

        for _, fila in tabla.iterrows():

            referencias.append({
                "fecha_hora": fila["Fecha y hora"].strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "fecha_servicio": datetime.strptime(
                    fila["Día de servicio"],
                    "%d/%m/%Y"
                ).strftime("%Y-%m-%d"),
                "estado": fila["Estado"]
            })

        # Identificar ajustes manuales guardados.
        ajustes = obtener_ajustes()

        indices_rojos = set()

        for indice, referencia in enumerate(referencias):

            clave = (
                referencia["fecha_hora"],
                referencia["fecha_servicio"]
            )

            if clave in ajustes:
                indices_rojos.add(indice)

        tabla["Fecha y hora"] = tabla[
            "Fecha y hora"
        ].dt.strftime("%d/%m/%Y %H:%M:%S")

        editor_key = (
            f"tabla_planificacion_{st.session_state.version_tabla}"
        )

        st.session_state[
            f"{editor_key}_referencias"
        ] = referencias

        st.markdown(
            "Selecciona el servicio inicial en la primera fila. "
            "Los siguientes servicios comenzarán automáticamente."
        )

        # --------------------------------------------------
        # COLOR DE FONDO SEGÚN ESTADO
        # --------------------------------------------------

        def colorear_filas(fila):

            estado = fila["Estado"]

            if estado == "Fin de servicio":

                return [
                    "background-color: #d9f2df;"
                    for _ in fila
                ]

            if estado == "Inicio de servicio":

                return [
                    "background-color: #dceeff;"
                    for _ in fila
                ]

            return [
                "background-color: transparent;"
                for _ in fila
            ]

        # --------------------------------------------------
        # COLOR ROJO PARA MODIFICACIONES MANUALES
        # --------------------------------------------------

        def colorear_picks(columna):

            estilos = []

            for indice in columna.index:

                if indice in indices_rojos:

                    estilos.append(
                        "color: #d00000; font-weight: bold;"
                    )

                else:

                    estilos.append(
                        "color: inherit;"
                    )

            return estilos

        tabla_estilizada = (
            tabla.style
            .apply(colorear_filas, axis=1)
            .apply(
                colorear_picks,
                subset=["Picks restantes"]
            )
        )

        # --------------------------------------------------
        # EDITOR DE TABLA
        # --------------------------------------------------

        st.data_editor(
            tabla_estilizada,
            use_container_width=True,
            hide_index=True,
            height=650,
            key=editor_key,
            on_change=guardar_ediciones,
            args=(editor_key,),
            disabled=[
                "Fecha y hora",
                "Estado"
            ],
            column_config={

                "Fecha y hora": st.column_config.TextColumn(
                    "Fecha y hora",
                    width="medium"
                ),

                "Día de servicio": st.column_config.SelectboxColumn(
                    "Día de servicio",
                    options=opciones_fechas,
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
                ),

                "Estado": st.column_config.TextColumn(
                    "Estado",
                    width="medium"
                )
            }
        )

        # --------------------------------------------------
        # LEYENDA DE COLORES
        # --------------------------------------------------

        st.markdown("""
        <div style="
            display:flex;
            flex-wrap:wrap;
            gap:22px;
            margin-top:14px;
            font-size:14px;
        ">

            <span>
                <span style="
                    display:inline-block;
                    width:13px;
                    height:13px;
                    background:#d9f2df;
                    border:1px solid #a9d5b3;
                    border-radius:3px;
                "></span>
                Fin de servicio
            </span>

            <span>
                <span style="
                    display:inline-block;
                    width:13px;
                    height:13px;
                    background:#dceeff;
                    border:1px solid #aacbed;
                    border-radius:3px;
                "></span>
                Inicio de servicio
            </span>

            <span style="color:#d00000;font-weight:bold;">
                Picks modificados manualmente
            </span>

            <span>
                Picks calculados automáticamente
            </span>

        </div>
        """, unsafe_allow_html=True)


# ==========================================================
# RESUMEN
# ==========================================================

st.divider()

col1, col2 = st.columns(2)

col1.metric(
    "Productividad",
    f"{productividad:,} picks/h"
)

col2.metric(
    "Días consultados",
    (fecha_final - fecha_inicio).days + 1
)

st.caption(
    "Los valores manuales se guardan en rojo. "
    "Las filas de finalización aparecen en verde claro "
    "y las de inicio de servicio en azul claro."
)
