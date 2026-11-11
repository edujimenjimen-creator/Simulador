
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

def guardar_sidebar(fecha, clave):
    valor = int(st.session_state[clave])
    guardar_servicio(fecha, valor)

def obtener_horas(fecha):
    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT hora, tiendas, picks
            FROM horas
            WHERE fecha=?
        """, (fecha,)).fetchall()

    datos = {
        h: {"tiendas": t, "picks": p}
        for h, t, p in filas
    }

    for h in range(24):
        if h not in datos:
            datos[h] = {
                "tiendas": 0,
                "picks": 0
            }

    return datos

def guardar_horas(fecha, tipo, valores):
    with closing(conectar()) as conn:
        with conn:

            for hora, valor in enumerate(valores):

                fila = conn.execute("""
                    SELECT tiendas, picks
                    FROM horas
                    WHERE fecha=? AND hora=?
                """, (fecha, hora)).fetchone()

                tiendas = fila[0] if fila else 0
                picks = fila[1] if fila else 0

                if tipo == "tiendas":
                    tiendas = valor
                else:
                    picks = valor

                conn.execute("""
                    INSERT INTO horas
                    (fecha, hora, tiendas, picks)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(fecha, hora)
                    DO UPDATE SET
                        tiendas=excluded.tiendas,
                        picks=excluded.picks
                """, (fecha, hora, tiendas, picks))

crear_base_datos()

# ==================================================
# ESTILO VISUAL
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
</style>
""", unsafe_allow_html=True)

# ==================================================
# FECHAS DE SERVICIO
# ==================================================

nombres = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado"
]

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
st.sidebar.caption("Panel de control del almacén")

st.sidebar.divider()

st.sidebar.subheader("📅 SEMANA DE SERVICIO")

fecha_elegida = st.sidebar.date_input(
    "Seleccionar semana",
    value=st.session_state.semana,
    format="DD/MM/YYYY"
)

# Ajustar fecha al lunes de esa semana
lunes = fecha_elegida - timedelta(
    days=fecha_elegida.weekday()
)

st.session_state.semana = lunes

dias = [
    lunes + timedelta(days=i)
    for i in range(6)
]

st.sidebar.divider()

# ==================================================
# PICKS POR SERVICIO PLEGABLES
# ==================================================

with st.sidebar.expander(
    "📋 PICKS POR SERVICIO",
    expanded=False
):

    st.caption(
        "Introduce los picks previstos de cada día. "
        "Se guardan automáticamente."
    )

    for i, dia in enumerate(dias):

        fecha = dia.isoformat()
        nombre = nombres[i]
        clave = f"sidebar_picks_{fecha}"

        valor_guardado = obtener_servicio(fecha)

        if clave not in st.session_state:
            st.session_state[clave] = int(valor_guardado)

        st.number_input(
            f"{nombre} {dia.strftime('%d/%m')}",
            min_value=0,
            max_value=1000000,
            step=1,
            key=clave,
            on_change=guardar_sidebar,
            args=(fecha, clave)
        )

st.sidebar.divider()

# ==================================================
# NAVEGACIÓN
# ==================================================

st.sidebar.subheader("⚙️ GESTIÓN")

pantalla = st.sidebar.radio(
    "Selecciona una sección",
    [
        "Tiendas por hora",
        "Picks por hora",
        "Resumen diario",
        "Resumen semanal"
    ]
)

dia_seleccionado = st.sidebar.selectbox(
    "Día que quieres consultar",
    nombres
)

indice_dia = nombres.index(dia_seleccionado)
fecha_actual = dias[indice_dia].isoformat()

st.sidebar.divider()

st.sidebar.caption(
    "Gestión de almacén | Versión 1.1"
)

# ==================================================
# CABECERA PRINCIPAL
# ==================================================

st.title("📦 Gestión de almacén")

st.caption(
    f"{dia_seleccionado} "
    f"{dias[indice_dia].strftime('%d/%m/%Y')}"
)

st.divider()

# ==================================================
# TIENDAS POR HORA
# ==================================================

if pantalla == "Tiendas por hora":

    st.header("🏬 Tiendas por hora")

    st.write(
        "Introduce manualmente el número de tiendas "
        "correspondiente a cada hora."
    )

    datos = obtener_horas(fecha_actual)

    with st.form("form_tiendas"):

        valores = []

        for inicio in range(0, 24, 2):

            col1, col2 = st.columns(2)

            for columna, hora in zip(
                [col1, col2],
                [inicio, inicio + 1]
            ):

                with columna:

                    valor = st.number_input(
                        f"Tiendas a las {hora:02d}:00",
                        min_value=0,
                        max_value=100000,
                        value=int(datos[hora]["tiendas"]),
                        step=1,
                        key=f"tiendas_{fecha_actual}_{hora}"
                    )

                    valores.append((hora, int(valor)))

        guardar = st.form_submit_button(
            "💾 GUARDAR TIENDAS",
            use_container_width=True
        )

        if guardar:

            lista = [0] * 24

            for hora, valor in valores:
                lista[hora] = valor

            guardar_horas(
                fecha_actual,
                "tiendas",
                lista
            )

            st.success("Tiendas guardadas correctamente.")

# ==================================================
# PICKS POR HORA
# ==================================================

elif pantalla == "Picks por hora":

    st.header("📊 Picks realizados por hora")

    st.write(
        "Utiliza los deslizadores para indicar "
        "cuántos picks has realizado en cada hora."
    )

    datos = obtener_horas(fecha_actual)

    with st.form("form_picks"):

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
                            int(datos[hora]["picks"]),
                            MAX_PICKS_HORA
                        ),
                        step=1,
                        key=f"picks_{fecha_actual}_{hora}"
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

            guardar_horas(
                fecha_actual,
                "picks",
                lista
            )

            st.success("Picks guardados correctamente.")

# ==================================================
# RESUMEN DIARIO
# ==================================================

elif pantalla == "Resumen diario":

    st.header("📈 Resumen diario")

    datos = obtener_horas(fecha_actual)
    servicio = obtener_servicio(fecha_actual)

    total_tiendas = sum(
        datos[h]["tiendas"] for h in range(24)
    )

    total_picks = sum(
        datos[h]["picks"] for h in range(24)
    )

    horas_activas = sum(
        1 for h in range(24)
        if datos[h]["picks"] > 0
    )

    media = (
        total_picks / horas_activas
        if horas_activas else 0
    )

    cumplimiento = (
        total_picks / servicio * 100
        if servicio > 0 else 0
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Picks del servicio",
        f"{servicio:,}"
    )

    c2.metric(
        "Picks realizados",
        f"{total_picks:,}"
    )

    c3.metric(
        "Tiendas",
        f"{total_tiendas:,}"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Productividad media",
        f"{media:.1f} picks/h"
    )

    c2.metric(
        "Horas activas",
        horas_activas
    )

    c3.metric(
        "Cumplimiento",
        f"{cumplimiento:.1f}%"
    )

    st.progress(
        min(cumplimiento / 100, 1.0)
    )

    st.divider()

    st.subheader("Detalle por hora")

    tabla = pd.DataFrame([
        {
            "Hora": f"{h:02d}:00",
            "Tiendas": datos[h]["tiendas"],
            "Picks": datos[h]["picks"]
        }
        for h in range(24)
    ])

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Picks realizados por hora")

    st.bar_chart(
        tabla.set_index("Hora")["Picks"]
    )

    st.subheader("Tiendas por hora")

    st.bar_chart(
        tabla.set_index("Hora")["Tiendas"]
    )

    st.metric(
        "Diferencia respecto al servicio",
        f"{total_picks - servicio:+,} picks"
    )

# ==================================================
# RESUMEN SEMANAL
# ==================================================

elif pantalla == "Resumen semanal":

    st.header("📅 Resumen semanal")

    registros = []

    for i, dia in enumerate(dias):

        fecha = dia.isoformat()

        servicio = obtener_servicio(fecha)
        datos = obtener_horas(fecha)

        tiendas = sum(
            datos[h]["tiendas"] for h in range(24)
        )

        picks = sum(
            datos[h]["picks"] for h in range(24)
        )

        cumplimiento = (
            picks / servicio * 100
            if servicio > 0 else 0
        )

        registros.append({
            "Día": nombres[i],
            "Fecha": dia.strftime("%d/%m"),
            "Servicio": servicio,
            "Tiendas": tiendas,
            "Picks realizados": picks,
            "Cumplimiento (%)": round(cumplimiento, 1)
        })

    tabla = pd.DataFrame(registros)

    total_servicio = tabla["Servicio"].sum()
    total_tiendas = tabla["Tiendas"].sum()
    total_picks = tabla["Picks realizados"].sum()

    cumplimiento_semanal = (
        total_picks / total_servicio * 100
        if total_servicio > 0 else 0
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Picks previstos",
        f"{total_servicio:,}"
    )

    c2.metric(
        "Picks realizados",
        f"{total_picks:,}"
    )

    c3.metric(
        "Tiendas",
        f"{total_tiendas:,}"
    )

    st.metric(
        "Cumplimiento semanal",
        f"{cumplimiento_semanal:.1f}%"
    )

    st.progress(
        min(cumplimiento_semanal / 100, 1.0)
    )

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
# FIN DE LA APLICACIÓN
# ==================================================
