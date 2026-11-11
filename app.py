
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


def obtener_tiendas_comunes():
    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT hora, tiendas
            FROM carga_tiendas
        """).fetchall()

    datos = {h: t for h, t in filas}

    for h in range(24):
        datos.setdefault(h, 0)

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

# Ocho fechas: lunes hasta el lunes siguiente.
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
        nombre_dia = dia.strftime("%A")
        clave = f"servicio_{fecha}"

        nombres = [
            "Lunes", "Martes", "Miércoles", "Jueves",
            "Viernes", "Sábado", "Domingo"
        ]

        if clave not in st.session_state:
            st.session_state[clave] = int(
                obtener_servicio(fecha)
            )

        st.number_input(
            f"{nombres[dia.weekday()]} {dia.strftime('%d/%m')}",
            min_value=0,
            max_value=1000000,
            step=100,
            key=clave,
            on_change=guardar_sidebar_servicio,
            args=(fecha, clave)
        )

# ==================================================
# CARGA DE TIENDAS COMÚN
# ==================================================

datos_tiendas = obtener_tiendas_comunes()

with st.sidebar.expander(
    "🏬 CARGA DE TIENDAS POR HORA",
    expanded=False
):
    st.caption("Carga común para todos los días.")

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

    st.metric(
        "Total de tiendas por día",
        f"{total_tiendas:,}"
    )

# ==================================================
# PRODUCTIVIDAD
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

guardar_configuracion("productividad", productividad)

st.sidebar.metric(
    "Productividad establecida",
    f"{productividad:,} picks/h"
)

st.sidebar.caption("Gestión de almacén | Versión 2.1")

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
# SELECCIÓN DE FECHAS Y HORAS
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
# CÁLCULO DE LA PREVISIÓN
# ==================================================

tiendas = obtener_tiendas_comunes()
ajustes = obtener_ajustes()

# El cálculo comienza desde el lunes para mantener
# correctamente el saldo acumulado anterior al intervalo.

momento = datetime.combine(
    min(inicio.date(), lunes),
    datetime.min.time()
)

saldo = 0
registros = []

while momento <= fin:

    fecha = momento.date()
    hora = momento.hour
    fecha_texto = fecha.isoformat()

    clave_momento = momento.strftime(
        "%Y-%m-%d %H:%M"
    )

    picks_servicio = obtener_servicio(fecha_texto)

    total_tiendas_dia = sum(tiendas.values())
    tiendas_hora = int(tiendas[hora])

    if total_tiendas_dia > 0:
        picks_por_tienda = (
            picks_servicio / total_tiendas_dia
        )
    else:
        picks_por_tienda = 0

    picks_previstos = round(
        picks_por_tienda * tiendas_hora
    )

    # Se suman los picks de esta hora y se resta
    # la productividad de la máquina.
    saldo_calculado = (
        saldo + picks_previstos - productividad
    )

    # El ajuste manual sustituye el saldo calculado.
    if clave_momento in ajustes:
        saldo = int(ajustes[clave_momento])
    else:
        saldo = saldo_calculado

    registros.append({
        "fecha_hora": clave_momento,
        "Fecha y hora": momento.strftime("%d/%m %H:%M"),
        "Tiendas": tiendas_hora,
        "Picks previstos": int(picks_previstos),
        "Productividad": int(productividad),
        "Picks restantes": int(saldo)
    })

    momento += timedelta(hours=1)

# ==================================================
# MOSTRAR INTERVALO SELECCIONADO
# ==================================================

registros_visibles = [
    r for r in registros
    if inicio <= datetime.strptime(
        r["fecha_hora"], "%Y-%m-%d %H:%M"
    ) <= fin
]

if not registros_visibles:
    st.info("No hay horas que mostrar.")
    st.stop()

st.subheader("📊 PICKS POR HACER")

st.caption(
    "Los picks restantes se actualizan hora a hora. "
    "Si la máquina produce más de lo previsto, "
    "el adelanto se descuenta de las horas siguientes."
)

df = pd.DataFrame(registros_visibles)

valores_originales = df["Picks restantes"].tolist()

df_edicion = df[
    [
        "Fecha y hora",
        "Tiendas",
        "Picks previstos",
        "Productividad",
        "Picks restantes"
    ]
].copy()

df_editado = st.data_editor(
    df_edicion,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    disabled=[
        "Fecha y hora",
        "Tiendas",
        "Picks previstos",
        "Productividad"
    ],
    column_config={
        "Fecha y hora": st.column_config.TextColumn(
            "Fecha y hora",
            width="medium"
        ),
        "Tiendas": st.column_config.NumberColumn(
            "Tiendas",
            format="%d"
        ),
        "Picks previstos": st.column_config.NumberColumn(
            "Picks previstos",
            format="%d"
        ),
        "Productividad": st.column_config.NumberColumn(
            "Productividad",
            format="%d"
        ),
        "Picks restantes": st.column_config.NumberColumn(
            "Picks restantes",
            format="%d",
            help="Puedes modificar manualmente los picks restantes."
        )
    },
    key="tabla_planificacion"
)

# ==================================================
# GUARDAR AJUSTES
# ==================================================

if st.button(
    "💾 GUARDAR CAMBIOS",
    type="primary",
    use_container_width=True
):
    cambios = 0

    for i, fila in df_editado.iterrows():

        nuevo_valor = int(fila["Picks restantes"])
        valor_original = int(valores_originales[i])

        if nuevo_valor != valor_original:

            fecha_hora = df.iloc[i]["fecha_hora"]

            guardar_ajuste(
                fecha_hora,
                nuevo_valor
            )

            cambios += 1

    if cambios > 0:
        st.success(
            f"Se han guardado {cambios} cambios."
        )
        st.rerun()
    else:
        st.info("No has realizado ningún cambio.")

# ==================================================
# RESUMEN
# ==================================================

st.divider()

st.subheader("📌 Resumen del periodo")

total_previsto = int(df["Picks previstos"].sum())
ultimo_saldo = int(df["Picks restantes"].iloc[-1])

c1, c2 = st.columns(2)

c1.metric(
    "Picks previstos en el periodo",
    f"{total_previsto:,}"
)

c2.metric(
    "Picks restantes al finalizar",
    f"{ultimo_saldo:,}"
)
