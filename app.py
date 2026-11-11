
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta
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
MAX_PICKS_HORA = 500

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
                CREATE TABLE IF NOT EXISTS horas (
                    fecha TEXT,
                    hora INTEGER,
                    tiendas INTEGER DEFAULT 0,
                    picks INTEGER DEFAULT 0,
                    PRIMARY KEY (fecha, hora)
                )
            """)

            # Carga de tiendas común a todos los días
            conn.execute("""
                CREATE TABLE IF NOT EXISTS carga_tiendas (
                    hora INTEGER PRIMARY KEY,
                    tiendas INTEGER DEFAULT 0
                )
            """)

def obtener_servicio(fecha):
    with closing(conectar()) as conn:
        resultado = conn.execute(
            "SELECT picks FROM servicios WHERE fecha=?",
            (fecha,)
        ).fetchone()

    return resultado[0] if resultado else 0

def guardar_servicio(fecha, picks):
    with closing(conectar()) as conn:
        with conn:
            conn.execute("""
                INSERT INTO servicios (fecha, picks)
                VALUES (?, ?)
                ON CONFLICT(fecha)
                DO UPDATE SET picks=excluded.picks
            """, (fecha, picks))

def guardar_sidebar_servicio(fecha, clave):
    guardar_servicio(
        fecha,
        int(st.session_state[clave])
    )

def obtener_horas_picks(fecha):
    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT hora, picks
            FROM horas
            WHERE fecha=?
        """, (fecha,)).fetchall()

    datos = {h: p for h, p in filas}

    for h in range(24):
        if h not in datos:
            datos[h] = 0

    return datos

def guardar_picks_horarios(fecha, valores):
    with closing(conectar()) as conn:
        with conn:
            for hora, picks in enumerate(valores):
                conn.execute("""
                    INSERT INTO horas (fecha, hora, tiendas, picks)
                    VALUES (?, ?, 0, ?)
                    ON CONFLICT(fecha, hora)
                    DO UPDATE SET picks=excluded.picks
                """, (fecha, hora, picks))

def obtener_tiendas_comunes():
    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT hora, tiendas
            FROM carga_tiendas
        """).fetchall()

    datos = {h: t for h, t in filas}

    for h in range(24):
        if h not in datos:
            datos[h] = 0

    return datos

def guardar_tienda_sidebar(hora, clave):
    valor = int(st.session_state[clave])

    with closing(conectar()) as conn:
        with conn:
            conn.execute("""
                INSERT INTO carga_tiendas (hora, tiendas)
                VALUES (?, ?)
                ON CONFLICT(hora)
                DO UPDATE SET tiendas=excluded.tiendas
            """, (hora, valor))

crear_base_datos()

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

    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #e5e9f0;
    }

    .block-container {
        padding-top: 2rem;
    }

    [data-testid="stSidebar"] {
        min-width: 280px;
    }
</style>
""", unsafe_allow_html=True)

# ==================================================
# SEMANA DE SERVICIO
# ==================================================

if "semana" not in st.session_state:
    hoy = date.today()
    dias_hasta_lunes = (7 - hoy.weekday()) % 7
    st.session_state.semana = hoy + timedelta(
        days=dias_hasta_lunes
    )

# ==================================================
# BARRA LATERAL
# ==================================================

st.sidebar.title("📦 ALMACÉN")
st.sidebar.caption("Panel de control")
st.sidebar.divider()

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
# PICKS POR SERVICIO: PLEGABLE
# ==================================================

st.sidebar.divider()

with st.sidebar.expander(
    "📋 PICKS POR SERVICIO",
    expanded=False
):

    st.caption("Picks previstos de cada día.")

    for i, dia in enumerate(dias):

        fecha = dia.isoformat()
        clave = f"servicio_{fecha}"

        if clave not in st.session_state:
            st.session_state[clave] = int(
                obtener_servicio(fecha)
            )

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
# CARGA DE TIENDAS: COMÚN A TODOS LOS DÍAS
# ==================================================

st.sidebar.divider()

datos_tiendas = obtener_tiendas_comunes()

with st.sidebar.expander(
    "🏬 CARGA DE TIENDAS POR HORA",
    expanded=False
):

    st.caption(
        "Esta carga es común para los seis días de servicio."
    )

    for hora in range(24):

        clave = f"tienda_comun_{hora}"

        if clave not in st.session_state:
            st.session_state[clave] = int(
                datos_tiendas[hora]
            )

        st.number_input(
            f"{hora:02d}:00 h",
            min_value=0,
            max_value=100000,
            step=1,
            key=clave,
            on_change=guardar_tienda_sidebar,
            args=(hora, clave)
        )

    total_tiendas = sum(
        int(st.session_state.get(
            f"tienda_comun_{h}", datos_tiendas[h]
        ))
        for h in range(24)
    )

    st.divider()

    st.metric(
        "Total de tiendas por día",
        f"{total_tiendas:,}"
    )

# ==================================================
# NAVEGACIÓN
# ==================================================

st.sidebar.divider()
st.sidebar.subheader("⚙️ GESTIÓN")

pantalla = st.sidebar.radio(
    "Selecciona una sección",
    [
        "Picks por hora",
        "Resumen diario",
        "Resumen semanal"
    ]
)

st.sidebar.divider()
st.sidebar.caption("Gestión de almacén | Versión 1.3")

# ==================================================
# FUNCIONES DE PANTALLAS DIARIAS
# ==================================================

def mostrar_picks_hora(dia, indice):

    fecha = dia.isoformat()
    datos = obtener_horas_picks(fecha)

    st.subheader(
        f"{NOMBRES[indice]} - {dia.strftime('%d/%m/%Y')}"
    )

    with st.form(f"form_picks_{fecha}"):

        valores = []

        for inicio in range(0, 24, 2):

            col1, col2 = st.columns(2)

            for columna, hora in zip(
                [col1, col2],
                [inicio, inicio + 1]
            ):

                with columna:

                    valor = st.slider(
                        f"Picks a las {hora:02d}:00",
                        min_value=0,
                        max_value=MAX_PICKS_HORA,
                        value=min(
                            int(datos[hora]),
                            MAX_PICKS_HORA
                        ),
                        step=1,
                        key=f"picks_{fecha}_{hora}"
                    )

                    valores.append((hora, int(valor)))

        guardar = st.form_submit_button(
            "💾 GUARDAR PICKS",
            use_container_width=True
        )

        if guardar:

            lista = [0] * 24

            for hora, valor in valores:
                lista[hora] = valor

            guardar_picks_horarios(
                fecha,
                lista
            )

            st.success(
                f"Picks de {NOMBRES[indice]} guardados."
            )

# ==================================================
# RESUMEN DE UN DÍA
# ==================================================

def mostrar_resumen_diario(dia, indice):

    fecha = dia.isoformat()

    datos_picks = obtener_horas_picks(fecha)
    datos_tiendas = obtener_tiendas_comunes()

    servicio = obtener_servicio(fecha)

    total_tiendas = sum(datos_tiendas.values())
    total_picks = sum(datos_picks.values())

    horas_activas = sum(
        1 for h in range(24)
        if datos_picks[h] > 0
    )

    media = (
        total_picks / horas_activas
        if horas_activas else 0
    )

    cumplimiento = (
        total_picks / servicio * 100
        if servicio > 0 else 0
    )

    st.subheader(
        f"{NOMBRES[indice]} - {dia.strftime('%d/%m/%Y')}"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("Picks del servicio", f"{servicio:,}")
    c2.metric("Picks realizados", f"{total_picks:,}")
    c3.metric("Tiendas previstas", f"{total_tiendas:,}")

    c1, c2, c3 = st.columns(3)

    c1.metric("Productividad media", f"{media:.1f} picks/h")
    c2.metric("Horas activas", horas_activas)
    c3.metric("Cumplimiento", f"{cumplimiento:.1f}%")

    st.progress(min(cumplimiento / 100, 1.0))

    tabla = pd.DataFrame([
        {
            "Hora": f"{h:02d}:00",
            "Tiendas": datos_tiendas[h],
            "Picks realizados": datos_picks[h]
        }
        for h in range(24)
    ])

    st.subheader("Detalle por hora")

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Picks realizados por hora")
    st.bar_chart(
        tabla.set_index("Hora")["Picks realizados"]
    )

    st.subheader("Carga de tiendas por hora")
    st.bar_chart(
        tabla.set_index("Hora")["Tiendas"]
    )

    st.metric(
        "Picks pendientes respecto al servicio",
        f"{max(servicio - total_picks, 0):,}"
    )

# ==================================================
# CABECERA
# ==================================================

st.title("📦 Gestión de almacén")
st.caption(
    f"Semana del {dias[0].strftime('%d/%m/%Y')} "
    f"al {dias[-1].strftime('%d/%m/%Y')}"
)
st.divider()

# ==================================================
# PICKS POR HORA
# ==================================================

if pantalla == "Picks por hora":

    st.header("📊 Picks realizados por hora")

    st.write(
        "Registra los picks realizados de forma independiente "
        "para cada día. Selecciona el día en las pestañas."
    )

    pestañas = st.tabs([
        f"{NOMBRES[i]} {dia.strftime('%d/%m')}"
        for i, dia in enumerate(dias)
    ])

    for i, pestaña in enumerate(pestañas):
        with pestaña:
            mostrar_picks_hora(dias[i], i)

# ==================================================
# RESUMEN DIARIO
# ==================================================

elif pantalla == "Resumen diario":

    st.header("📈 Resumen diario")

    pestañas = st.tabs([
        f"{NOMBRES[i]} {dia.strftime('%d/%m')}"
        for i, dia in enumerate(dias)
    ])

    for i, pestaña in enumerate(pestañas):
        with pestaña:
            mostrar_resumen_diario(dias[i], i)

# ==================================================
# RESUMEN SEMANAL
# ==================================================

elif pantalla == "Resumen semanal":

    st.header("📅 Resumen semanal")

    registros = []

    datos_tiendas = obtener_tiendas_comunes()
    tiendas_diarias = sum(datos_tiendas.values())

    for i, dia in enumerate(dias):

        fecha = dia.isoformat()

        servicio = obtener_servicio(fecha)
        datos_picks = obtener_horas_picks(fecha)

        picks = sum(datos_picks.values())

        cumplimiento = (
            picks / servicio * 100
            if servicio > 0 else 0
        )

        registros.append({
            "Día": NOMBRES[i],
            "Fecha": dia.strftime("%d/%m"),
            "Servicio": servicio,
            "Tiendas": tiendas_diarias,
            "Picks realizados": picks,
            "Cumplimiento (%)": round(cumplimiento, 1)
        })

    tabla = pd.DataFrame(registros)

    total_servicio = tabla["Servicio"].sum()
    total_tiendas_semana = tiendas_diarias * 6
    total_picks = tabla["Picks realizados"].sum()

    cumplimiento_semanal = (
        total_picks / total_servicio * 100
        if total_servicio > 0 else 0
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("Picks previstos", f"{total_servicio:,}")
    c2.metric("Picks realizados", f"{total_picks:,}")
    c3.metric("Tiendas semanales", f"{total_tiendas_semana:,}")

    st.metric(
        "Cumplimiento semanal",
        f"{cumplimiento_semanal:.1f}%"
    )

    st.progress(min(cumplimiento_semanal / 100, 1.0))

    st.divider()

    st.subheader("Detalle de la semana")

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Comparativa de picks por día")

    grafico = tabla.set_index("Día")[
        ["Servicio", "Picks realizados"]
    ]

    st.bar_chart(grafico)

# ==================================================
# FIN
# ==================================================
