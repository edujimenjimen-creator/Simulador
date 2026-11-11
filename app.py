
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
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
    "Lunes", "Martes", "Miércoles", "Jueves",
    "Viernes", "Sábado", "Domingo"
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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS carga_tiendas (
                    hora INTEGER PRIMARY KEY,
                    tiendas INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ajustes_pendientes (
                    fecha_hora TEXT PRIMARY KEY,
                    pendientes INTEGER DEFAULT 0
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


def obtener_configuracion(clave, defecto):
    with closing(conectar()) as conn:
        resultado = conn.execute(
            "SELECT valor FROM configuracion WHERE clave=?",
            (clave,)
        ).fetchone()

    return resultado[0] if resultado else defecto


def guardar_configuracion(clave, valor):
    with closing(conectar()) as conn:
        with conn:
            conn.execute("""
                INSERT INTO configuracion (clave, valor)
                VALUES (?, ?)
                ON CONFLICT(clave)
                DO UPDATE SET valor=excluded.valor
            """, (clave, valor))


def obtener_ajustes():
    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT fecha_hora, pendientes
            FROM ajustes_pendientes
        """).fetchall()

    return {fecha: pendientes for fecha, pendientes in filas}


def guardar_ajuste(fecha_hora, pendientes):
    with closing(conectar()) as conn:
        with conn:
            conn.execute("""
                INSERT INTO ajustes_pendientes
                    (fecha_hora, pendientes)
                VALUES (?, ?)
                ON CONFLICT(fecha_hora)
                DO UPDATE SET pendientes=excluded.pendientes
            """, (fecha_hora, pendientes))


# ==================================================
# GUARDADO AUTOMÁTICO DE CELDAS
# ==================================================

def guardar_ediciones_pendientes():

    estado = st.session_state.get(
        "tabla_planificacion", {}
    )

    ediciones = estado.get("edited_rows", {})

    mapa_filas = st.session_state.get(
        "mapa_filas_planificacion", {}
    )

    cambios = 0

    for indice, valores in ediciones.items():

        if "Picks restantes" not in valores:
            continue

        indice = int(indice)

        fecha_hora = mapa_filas.get(indice)

        if fecha_hora is None:
            continue

        nuevo_valor = int(
            valores["Picks restantes"]
        )

        guardar_ajuste(
            fecha_hora,
            nuevo_valor
        )

        cambios += 1

    if cambios:
        st.session_state["mensaje_guardado"] = (
            f"Se han guardado automáticamente {cambios} cambios."
        )

    # Limpiamos los cambios temporales del editor.
    # La tabla se reconstruirá con los nuevos saldos.
    st.session_state.pop(
        "tabla_planificacion",
        None
    )


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

    .block-container {
        padding-top: 1.5rem;
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

    [data-testid="stSidebar"] hr {
        display: none !important;
    }

    [data-testid="stSidebar"] .stMarkdown {
        margin-bottom: 0 !important;
    }

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        margin-bottom: 2px !important;
    }
</style>
""", unsafe_allow_html=True)

# ==================================================
# SEMANA DE SERVICIO
# ==================================================

if "semana" not in st.session_state:
    hoy = date.today()
    st.session_state.semana = hoy - timedelta(
        days=hoy.weekday()
    )

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
    for i in range(8)
]

# ==================================================
# PICKS POR SERVICIO
# ==================================================

with st.sidebar.expander(
    "📋 PICKS POR SERVICIO",
    expanded=False
):
    st.caption("Picks totales previstos de cada día.")

    for dia in dias:

        fecha = dia.isoformat()
        clave = f"servicio_{fecha}"

        if clave not in st.session_state:
            st.session_state[clave] = int(
                obtener_servicio(fecha)
            )

        st.number_input(
            f"{NOMBRES[dia.weekday()]} {dia.strftime('%d/%m')}",
            min_value=0,
            max_value=1000000,
            step=100,
            key=clave,
            on_change=guardar_sidebar_servicio,
            args=(fecha, clave)
        )

# ==================================================
# PRODUCTIVIDAD DE LA MÁQUINA
# ==================================================

st.sidebar.subheader("⚙️ PRODUCTIVIDAD")

if "productividad" not in st.session_state:
    st.session_state.productividad = obtener_configuracion(
        "productividad", 3000
    )

productividad = st.sidebar.slider(
    "Picks que hace la máquina por hora",
    min_value=1000,
    max_value=6000,
    step=500,
    key="productividad"
)

guardar_configuracion(
    "productividad",
    productividad
)

st.sidebar.metric(
    "Productividad establecida",
    f"{productividad:,} picks/h"
)

st.sidebar.caption("Gestión de almacén | Versión 2.5")

# ==================================================
# CABECERA
# ==================================================

st.title("📦 Planificación de picks")

st.caption(
    f"Semana de servicio: {lunes.strftime('%d/%m/%Y')} "
    f"al {(lunes + timedelta(days=7)).strftime('%d/%m/%Y')}"
)

st.divider()

# ==================================================
# SELECCIÓN DEL PERIODO
# ==================================================

st.subheader("📅 Selecciona el periodo")

col1, col2, col3, col4 = st.columns(4)

with col1:
    fecha_inicio = st.date_input(
        "Desde el día",
        value=lunes,
        key="fecha_inicio",
        format="DD/MM/YYYY"
    )

with col2:
    hora_inicio = st.selectbox(
        "Desde la hora",
        range(24),
        index=0,
        format_func=lambda h: f"{h:02d}:00",
        key="hora_inicio"
    )

with col3:
    fecha_fin = st.date_input(
        "Hasta el día",
        value=lunes + timedelta(days=7),
        key="fecha_fin",
        format="DD/MM/YYYY"
    )

with col4:
    hora_fin = st.selectbox(
        "Hasta la hora",
        range(24),
        index=23,
        format_func=lambda h: f"{h:02d}:00",
        key="hora_fin"
    )

inicio = datetime.combine(
    fecha_inicio,
    datetime.min.time()
).replace(hour=hora_inicio)

fin = datetime.combine(
    fecha_fin,
    datetime.min.time()
).replace(hour=hora_fin)

if fin < inicio:
    st.error(
        "La fecha y hora final debe ser posterior a la inicial."
    )
    st.stop()

# ==================================================
# CÁLCULO DE PICKS RESTANTES
# ==================================================

ajustes = obtener_ajustes()

# Calculamos desde las 00:00 del primer día seleccionado.
# Así se tienen en cuenta las horas anteriores al intervalo.

momento = datetime.combine(
    inicio.date(),
    datetime.min.time()
)

registros = []

saldo_dia = 0
fecha_anterior = None

while momento <= fin:

    fecha = momento.date()
    fecha_texto = fecha.isoformat()

    clave_momento = momento.strftime(
        "%Y-%m-%d %H:%M"
    )

    # Al comenzar un nuevo día se carga el servicio diario.
    if fecha != fecha_anterior:
        saldo_dia = obtener_servicio(fecha_texto)
        fecha_anterior = fecha

    # Si existe un ajuste manual, prevalece sobre el cálculo.
    if clave_momento in ajustes:
        saldo_dia = int(ajustes[clave_momento])
    else:
        saldo_dia = max(
            saldo_dia - productividad,
            0
        )

    if inicio <= momento <= fin:
        registros.append({
            "fecha_hora": clave_momento,
            "Fecha y hora": momento.strftime(
                "%d/%m %H:%M"
            ),
            "Picks restantes": int(saldo_dia)
        })

    momento += timedelta(hours=1)

# ==================================================
# TABLA PRINCIPAL
# ==================================================

if not registros:
    st.info("No hay horas que mostrar.")
    st.stop()

st.subheader("📊 PICKS RESTANTES")

st.caption(
    "Modifica cualquier cantidad de picks restantes. "
    "El cambio se guardará automáticamente y actualizará "
    "las horas posteriores."
)

# Mapa que relaciona cada fila con su fecha y hora real.
st.session_state["mapa_filas_planificacion"] = {
    i: registro["fecha_hora"]
    for i, registro in enumerate(registros)
}

tabla = pd.DataFrame([
    {
        "Fecha y hora": registro["Fecha y hora"],
        "Picks restantes": registro["Picks restantes"]
    }
    for registro in registros
])

st.data_editor(
    tabla,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    disabled=["Fecha y hora"],
    column_config={
        "Fecha y hora": st.column_config.TextColumn(
            "Fecha y hora",
            width="medium"
        ),
        "Picks restantes": st.column_config.NumberColumn(
            "Picks restantes",
            min_value=0,
            max_value=1000000,
            step=100,
            format="%d",
            help="Modifica esta cantidad para actualizar las horas siguientes."
        )
    },
    key="tabla_planificacion",
    on_change=guardar_ediciones_pendientes
)

# ==================================================
# CONFIRMACIÓN DEL GUARDADO
# ==================================================

if st.session_state.get("mensaje_guardado"):
    st.success(
        st.session_state.pop("mensaje_guardado")
    )

# ==================================================
# RESUMEN
# ==================================================

st.divider()

st.subheader("📌 Resumen del periodo")

ultimo_saldo = int(
    registros[-1]["Picks restantes"]
)

st.metric(
    "Picks restantes al finalizar el periodo",
    f"{ultimo_saldo:,}"
)
