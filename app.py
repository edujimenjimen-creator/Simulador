
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
    guardar_servicio(
        fecha,
        st.session_state[clave]
    )


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
            ORDER BY fecha_hora
        """).fetchall()

    return {
        fecha_hora: int(pendientes)
        for fecha_hora, pendientes in filas
    }


# ==================================================
# GUARDAR EDICIONES MANUALES DE LA TABLA
# ==================================================

def guardar_ediciones_pendientes(editor_key):

    estado = st.session_state.get(editor_key, {})
    cambios = estado.get("edited_rows", {})

    if not cambios:
        return

    filas_cambiadas = []

    for indice, valores in cambios.items():

        if "Picks restantes" not in valores:
            continue

        filas_cambiadas.append((
            int(indice),
            int(valores["Picks restantes"])
        ))

    if not filas_cambiadas:
        return

    # Procesamos las modificaciones por orden cronológico.
    filas_cambiadas.sort(key=lambda x: x[0])

    # Recuperamos las fechas que se mostraban en el editor.
    fechas_filas = st.session_state.get(
        f"{editor_key}_fechas",
        []
    )

    with closing(conectar()) as conn:
        with conn:

            for indice, nuevo_valor in filas_cambiadas:

                if indice >= len(fechas_filas):
                    continue

                fecha_hora = fechas_filas[indice]
                fecha = fecha_hora[:10]

                # Elimina ajustes posteriores de ese mismo día.
                # Los demás días permanecen intactos.
                conn.execute("""
                    DELETE FROM ajustes_pendientes
                    WHERE substr(fecha_hora, 1, 10) = ?
                    AND fecha_hora > ?
                """, (fecha, fecha_hora))

                # Guarda el nuevo saldo manual.
                conn.execute("""
                    INSERT INTO ajustes_pendientes (
                        fecha_hora,
                        pendientes
                    )
                    VALUES (?, ?)
                    ON CONFLICT(fecha_hora)
                    DO UPDATE SET pendientes=excluded.pendientes
                """, (fecha_hora, nuevo_valor))

    st.session_state.version_tabla += 1


# ==================================================
# CREACIÓN DE BASE DE DATOS
# ==================================================

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
# ESTADO DE SESIÓN
# ==================================================

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
# SEMANA DE SERVICIO
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
# HORARIO DE VISUALIZACIÓN
# ==================================================

st.sidebar.subheader("🕒 HORARIO")

hora_inicio = st.sidebar.time_input(
    "Hora inicial",
    value=time(0, 0),
    key="hora_inicio"
)

hora_final = st.sidebar.time_input(
    "Hora final",
    value=time(23, 0),
    key="hora_final"
)


# ==================================================
# CÁLCULO DE PICKS RESTANTES
# ==================================================

def calcular_planificacion(
    dias,
    productividad,
    hora_inicio,
    hora_final
):

    ajustes = obtener_ajustes()
    registros = []

    for i, dia in enumerate(dias):

        fecha = dia.isoformat()
        servicio = obtener_servicio(fecha)

        saldo = servicio

        # Cada día comienza desde su propio total de servicio.
        for hora in range(24):

            fecha_hora_dt = datetime.combine(
                dia,
                time(hour=hora)
            )

            fecha_hora = fecha_hora_dt.strftime(
                "%Y-%m-%d %H:%M"
            )

            # Si existe un ajuste manual, se convierte
            # en el nuevo punto de partida.
            if fecha_hora in ajustes:

                saldo = ajustes[fecha_hora]

            else:

                # Se descuenta productividad en cada hora.
                saldo = max(
                    saldo - productividad,
                    0
                )

            # Aplicamos el horario de visualización.
            if hora_inicio <= hora_final:

                dentro_horario = (
                    hora_inicio.hour <= hora <= hora_final.hour
                )

            else:

                dentro_horario = (
                    hora >= hora_inicio.hour
                    or hora <= hora_final.hour
                )

            if dentro_horario:

                registros.append({
                    "Fecha y hora": fecha_hora,
                    "Picks restantes": int(saldo)
                })

    return pd.DataFrame(registros)


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
# TABLA DE PLANIFICACIÓN
# ==================================================

st.header("📊 Previsión de picks restantes")

st.write(
    "Puedes modificar manualmente cualquier saldo. "
    "Las horas posteriores de ese mismo día se recalcularán."
)

tabla = calcular_planificacion(
    dias,
    productividad,
    hora_inicio,
    hora_final
)

# Guardamos la correspondencia entre filas y fechas.
fechas_editor = tabla["Fecha y hora"].tolist()

editor_key = (
    f"tabla_planificacion_{st.session_state.version_tabla}"
)

st.session_state[f"{editor_key}_fechas"] = fechas_editor

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
# INFORMACIÓN DE PRODUCTIVIDAD
# ==================================================

st.divider()

col1, col2 = st.columns(2)

col1.metric(
    "Productividad configurada",
    f"{productividad:,} picks/h"
)

col2.metric(
    "Días de servicio",
    len(dias)
)

st.caption(
    "Los cambios de productividad recalculan la previsión "
    "de todos los días. Los ajustes manuales guardados "
    "se mantienen como puntos de partida."
)

# ==================================================
# FIN
# ==================================================
