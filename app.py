
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

            # Ajustes manuales de la planificación.
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

    with closing(conectar()) as conn:

        with conn:

            for indice, valores in cambios.items():

                if "Picks restantes" not in valores:
                    continue

                indice = int(indice)

                if indice >= len(referencias):
                    continue

                referencia = referencias[indice]

                # Solo permitimos ajustes en filas de trabajo.
                if referencia["tipo"] == "Fin de servicio":
                    continue

                fecha_hora = referencia["fecha_hora"]
                fecha_servicio = referencia["fecha_servicio"]

                pendientes = max(
                    0,
                    int(valores["Picks restantes"])
                )

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
                    fecha_hora,
                    fecha_servicio,
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
# ESTILO
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

    [data-testid="stSidebar"] hr {
        display: none !important;
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

    st.caption("Picks totales de cada servicio.")

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
# GENERADOR DE PLANIFICACIÓN CONSECUTIVA
# ==========================================================

def calcular_planificacion(inicio, final, productividad):

    ajustes = obtener_ajustes()

    registros = []

    cursor = inicio
    dia_servicio = inicio.date()

    # Evita bucles si hay muchos servicios con cero picks.
    limite_servicios = 1000
    servicios_procesados = 0

    while cursor <= final and servicios_procesados < limite_servicios:

        fecha_servicio = dia_servicio.isoformat()

        # Cada servicio comienza con sus picks totales.
        saldo = float(obtener_servicio(fecha_servicio))

        # Ajuste manual en el inicio, si existe.
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
            "Estado": "Inicio de servicio"
        })

        # Si el servicio no tiene picks, termina inmediatamente.
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

        servicio_terminado = False

        while cursor < final and saldo > 0:

            # Próxima hora completa.
            siguiente_hora = (
                cursor.replace(
                    minute=0,
                    second=0,
                    microsecond=0
                ) + timedelta(hours=1)
            )

            # Tiempo necesario para terminar el servicio.
            segundos_necesarios = (
                saldo / productividad
            ) * 3600

            hora_fin_servicio = (
                cursor + timedelta(seconds=segundos_necesarios)
            )

            # El siguiente evento puede ser:
            # - Una hora completa.
            # - El final del servicio.
            # - El final del intervalo consultado.
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

            # El servicio ha terminado.
            if saldo <= 0.000001:

                saldo = 0

                registros.append({
                    "Fecha y hora": cursor,
                    "Día de servicio": dia_servicio.strftime("%d/%m/%Y"),
                    "Picks restantes": 0,
                    "Estado": "Fin de servicio"
                })

                servicio_terminado = True
                break

            # Si hemos llegado al final del intervalo.
            if cursor >= final:

                registros.append({
                    "Fecha y hora": cursor,
                    "Día de servicio": dia_servicio.strftime("%d/%m/%Y"),
                    "Picks restantes": int(round(saldo)),
                    "Estado": "En curso"
                })

                break

            # Aplicar un posible ajuste manual en esta hora.
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

        if servicio_terminado:

            # El siguiente servicio comienza inmediatamente.
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

st.divider()


# ==========================================================
# TABLA
# ==========================================================

inicio = datetime.combine(
    fecha_inicio,
    hora_inicio
)

final = datetime.combine(
    fecha_final,
    hora_final
)

if inicio >= final:

    st.error(
        "La fecha y hora final deben ser posteriores "
        "a la fecha y hora inicial."
    )

else:

    tabla_completa = calcular_planificacion(
        inicio,
        final,
        productividad
    )

    if tabla_completa.empty:

        st.warning("No hay datos para mostrar.")

    else:

        tabla = tabla_completa.copy()

        # Crear referencias internas para las ediciones.
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
                "tipo": fila["Estado"]
            })

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
            "Los servicios se preparan consecutivamente. "
            "El siguiente comienza automáticamente cuando el anterior "
            "llega a cero."
        )

        st.data_editor(
            tabla,
            use_container_width=True,
            hide_index=True,
            height=650,
            key=editor_key,
            on_change=guardar_ediciones,
            args=(editor_key,),
            disabled=[
                "Fecha y hora",
                "Día de servicio",
                "Estado"
            ],
            column_config={

                "Fecha y hora": st.column_config.TextColumn(
                    "Fecha y hora",
                    width="medium"
                ),

                "Día de servicio": st.column_config.TextColumn(
                    "Día de servicio",
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
    "Días de consulta",
    (fecha_final - fecha_inicio).days + 1
)

st.caption(
    "La hora de finalización se calcula según los picks pendientes "
    "y la productividad configurada. Los ajustes manuales se guardan."
)
