
import streamlit as st
import sqlite3
from datetime import date, timedelta

# ==========================================
# CONFIGURACIÓN
# ==========================================

st.set_page_config(
    page_title="Gestión de Almacén",
    page_icon="📦",
    layout="wide"
)

DB = "almacen.db"
MAX_PICKS_HORA = 500

# ==========================================
# BASE DE DATOS
# ==========================================

def conectar():
    return sqlite3.connect(DB)

def crear_base_datos():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS servicios (
            fecha TEXT PRIMARY KEY,
            picks INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS horas (
            fecha TEXT,
            hora INTEGER,
            tiendas INTEGER DEFAULT 0,
            picks INTEGER DEFAULT 0,
            PRIMARY KEY (fecha, hora)
        )
    """)

    conn.commit()
    conn.close()

def obtener_servicio(fecha):
    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        "SELECT picks FROM servicios WHERE fecha=?",
        (fecha,)
    )

    resultado = cur.fetchone()
    conn.close()

    return resultado[0] if resultado else 0

def obtener_horas(fecha):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT hora, tiendas, picks
        FROM horas
        WHERE fecha=?
        ORDER BY hora
    """, (fecha,))

    resultados = cur.fetchall()
    conn.close()

    datos = {
        hora: {"tiendas": tiendas, "picks": picks}
        for hora, tiendas, picks in resultados
    }

    for hora in range(24):
        if hora not in datos:
            datos[hora] = {"tiendas": 0, "picks": 0}

    return datos

def guardar_servicio(fecha, picks):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO servicios (fecha, picks)
        VALUES (?, ?)
        ON CONFLICT(fecha)
        DO UPDATE SET picks=excluded.picks
    """, (fecha, picks))

    conn.commit()
    conn.close()

def guardar_horas(fecha, tipo, valores):
    conn = conectar()
    cur = conn.cursor()

    # Recuperar los datos existentes
    cur.execute("""
        SELECT hora, tiendas, picks
        FROM horas
        WHERE fecha=?
    """, (fecha,))

    existentes = {
        h: [t, p] for h, t, p in cur.fetchall()
    }

    for hora in range(24):
        if hora not in existentes:
            existentes[hora] = [0, 0]

        if tipo == "tiendas":
            existentes[hora][0] = valores[hora]
        else:
            existentes[hora][1] = valores[hora]

        cur.execute("""
            INSERT INTO horas (fecha, hora, tiendas, picks)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(fecha, hora)
            DO UPDATE SET
                tiendas=excluded.tiendas,
                picks=excluded.picks
        """, (
            fecha,
            hora,
            existentes[hora][0],
            existentes[hora][1]
        ))

    conn.commit()
    conn.close()

crear_base_datos()

# ==========================================
# ESTILO
# ==========================================

st.markdown("""
<style>
    .stApp {
        background-color: #f3f5f9;
    }

    h1, h2, h3 {
        color: #17243a;
    }

    div[data-testid="stMetric"] {
        background: white;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #e5e9f0;
    }

    .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# FECHAS Y NAVEGACIÓN
# ==========================================

st.sidebar.title("📦 ALMACÉN")
st.sidebar.caption("Panel de gestión")

st.sidebar.divider()

st.sidebar.subheader("Semana de servicio")

if "semana" not in st.session_state:
    st.session_state.semana = date(2026, 11, 16)

fecha_elegida = st.sidebar.date_input(
    "Seleccionar semana",
    value=st.session_state.semana,
    format="DD/MM/YYYY"
)

# Ajustar automáticamente al lunes
lunes = fecha_elegida - timedelta(days=fecha_elegida.weekday())
st.session_state.semana = lunes

dias = [
    lunes + timedelta(days=i)
    for i in range(6)
]

nombres = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado"
]

opciones = {
    f"{nombres[i]} {dias[i].strftime('%d/%m')}":
    dias[i].isoformat()
    for i in range(6)
}

st.sidebar.subheader("Días de servicio")

dia_seleccionado = st.sidebar.radio(
    "Selecciona el día",
    list(opciones.keys())
)

fecha_actual = opciones[dia_seleccionado]

st.sidebar.divider()

pantalla = st.sidebar.radio(
    "GESTIÓN DEL ALMACÉN",
    [
        "Servicio diario",
        "Tiendas por hora",
        "Picks por hora",
        "Resumen diario"
    ]
)

# ==========================================
# CABECERA
# ==========================================

st.title("📦 Gestión de almacén")

st.caption(
    f"Servicio seleccionado: {dia_seleccionado} "
    f"| {fecha_actual}"
)

st.divider()

# ==========================================
# SERVICIO DIARIO
# ==========================================

if pantalla == "Servicio diario":

    st.header("Picks del servicio")

    valor_actual = obtener_servicio(fecha_actual)

    with st.form("form_servicio"):

        picks_dia = st.number_input(
            "Número de picks del servicio",
            min_value=0,
            max_value=1000000,
            value=int(valor_actual),
            step=1
        )

        guardar = st.form_submit_button(
            "💾 Guardar servicio",
            use_container_width=True
        )

        if guardar:
            guardar_servicio(
                fecha_actual,
                int(picks_dia)
            )
            st.success("Servicio guardado correctamente.")

    st.info(
        "Introduce aquí el total de picks previstos "
        "para el servicio de este día."
    )

# ==========================================
# TIENDAS POR HORA
# ==========================================

elif pantalla == "Tiendas por hora":

    st.header("🏬 Número de tiendas por hora")

    st.write(
        "Introduce manualmente cuántas tiendas "
        "corresponden a cada hora."
    )

    datos = obtener_horas(fecha_actual)
    valores = []

    with st.form("form_tiendas"):

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
            "💾 Guardar tiendas",
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

# ==========================================
# PICKS POR HORA
# ==========================================

elif pantalla == "Picks por hora":

    st.header("📊 Picks realizados por hora")

    st.write(
        "Utiliza los deslizadores para introducir "
        "los picks realizados en cada hora."
    )

    datos = obtener_horas(fecha_actual)
    valores = []

    with st.form("form_picks"):

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
            "💾 Guardar picks",
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

# ==========================================
# RESUMEN DIARIO
# ==========================================

elif pantalla == "Resumen diario":

    st.header("📈 Resumen del día")

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
        if horas_activas > 0 else 0
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "Picks del servicio",
        f"{servicio:,}"
    )

    c2.metric(
        "Picks realizados",
        f"{total_picks:,}"
    )

    c3, c4 = st.columns(2)

    c3.metric(
        "Total de tiendas",
        f"{total_tiendas:,}"
    )

    c4.metric(
        "Media de picks por hora activa",
        f"{media:.1f}"
    )

    st.divider()

    st.subheader("Detalle horario")

    import pandas as pd

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

    st.subheader("Evolución de picks")

    st.bar_chart(
        tabla.set_index("Hora")["Picks"]
    )

    diferencia = total_picks - servicio

    st.metric(
        "Diferencia respecto al servicio",
        f"{diferencia:+,} picks"
    )
