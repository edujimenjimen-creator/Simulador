
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
MANUAL = "✏️ Manual"
AUTO = "Automático"

COLUMNAS = [
    "Fecha y hora",
    "Día de servicio",
    "Picks restantes",
    "Servicio completado (%)",
    "Estado",
    "Origen"
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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS planificacion_congelada (
                    fecha_hora TEXT NOT NULL,
                    fecha_servicio TEXT NOT NULL,
                    pendientes INTEGER NOT NULL,
                    estado TEXT NOT NULL,
                    origen TEXT NOT NULL,
                    PRIMARY KEY (fecha_hora, fecha_servicio, estado)
                )
            """)

            columnas = [
                fila[1] for fila in conn.execute(
                    "PRAGMA table_info(ajustes_planificacion)"
                ).fetchall()
            ]

            if "estado" not in columnas:
                conn.execute("""
                    ALTER TABLE ajustes_planificacion
                    ADD COLUMN estado TEXT DEFAULT 'En curso'
                """)


@st.cache_data(ttl=30)
def obtener_todos_los_servicios():

    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT fecha, picks
            FROM servicios
            WHERE picks > 0
            ORDER BY fecha
        """).fetchall()

    return {
        fecha: int(picks)
        for fecha, picks in filas
    }


def obtener_servicio(fecha):

    return obtener_todos_los_servicios().get(
        fecha, 0
    )


def guardar_servicio(fecha, picks):

    with closing(conectar()) as conn:
        with conn:

            conn.execute("""
                INSERT INTO servicios (fecha, picks)
                VALUES (?, ?)
                ON CONFLICT(fecha)
                DO UPDATE SET picks=excluded.picks
            """, (fecha, int(picks)))

    obtener_todos_los_servicios.clear()


def obtener_configuracion(clave, defecto):

    with closing(conectar()) as conn:
        fila = conn.execute(
            "SELECT valor FROM configuracion WHERE clave=?",
            (clave,)
        ).fetchone()

    return int(fila[0]) if fila else defecto


def guardar_configuracion(clave, valor):

    with closing(conectar()) as conn:
        with conn:

            conn.execute("""
                INSERT INTO configuracion (clave, valor)
                VALUES (?, ?)
                ON CONFLICT(clave)
                DO UPDATE SET valor=excluded.valor
            """, (clave, int(valor)))


def obtener_ajustes():

    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT fecha_hora, fecha_servicio, pendientes
            FROM ajustes_planificacion
        """).fetchall()

    return {
        (hora, servicio): int(picks)
        for hora, servicio, picks in filas
    }


def obtener_congelados():

    with closing(conectar()) as conn:
        return conn.execute("""
            SELECT fecha_hora, fecha_servicio,
                   pendientes, estado, origen
            FROM planificacion_congelada
            ORDER BY fecha_hora
        """).fetchall()


# ==========================================================
# GUARDAR HISTÓRICO CONGELADO
# ==========================================================

def guardar_filas_congeladas(filas):

    if filas is None or filas.empty:
        return

    with closing(conectar()) as conn:
        with conn:

            for _, fila in filas.iterrows():

                momento = fila["Fecha y hora"]

                if isinstance(momento, str):
                    momento = datetime.strptime(
                        momento,
                        "%Y-%m-%d %H:%M:%S"
                    )

                servicio = datetime.strptime(
                    fila["Día de servicio"],
                    "%d/%m/%Y"
                ).date()

                conn.execute("""
                    INSERT INTO planificacion_congelada (
                        fecha_hora,
                        fecha_servicio,
                        pendientes,
                        estado,
                        origen
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (
                        fecha_hora,
                        fecha_servicio,
                        estado
                    )
                    DO UPDATE SET
                        pendientes=excluded.pendientes,
                        origen=excluded.origen
                """, (
                    momento.strftime("%Y-%m-%d %H:%M:%S"),
                    servicio.isoformat(),
                    int(fila["Picks restantes"]),
                    fila["Estado"],
                    fila["Origen"]
                ))


def congelar_hasta_ultimo_manual():

    plan = st.session_state.get("plan_actual")
    ajustes = obtener_ajustes()

    if plan is None or plan.empty or not ajustes:
        return

    ultimo_txt = max(
        ajustes.keys(),
        key=lambda x: x[0]
    )[0]

    corte = datetime.strptime(
        ultimo_txt,
        "%Y-%m-%d %H:%M:%S"
    )

    prefijo = plan[
        plan["Fecha y hora"] <= corte
    ].copy()

    guardar_filas_congeladas(prefijo)


def guardar_productividad():

    congelar_hasta_ultimo_manual()

    guardar_configuracion(
        "productividad",
        st.session_state.productividad
    )

    st.session_state.version_tabla += 1


# ==========================================================
# GUARDAR MODIFICACIONES MANUALES
# ==========================================================

def guardar_ediciones(editor_key):

    cambios = st.session_state.get(
        editor_key, {}
    ).get("edited_rows", {})

    if not cambios:
        return

    referencias = st.session_state.get(
        f"{editor_key}_referencias",
        []
    )

    plan_anterior = st.session_state.get("plan_actual")

    ediciones = []

    for indice, valores in cambios.items():

        if "Picks restantes" not in valores:
            continue

        indice = int(indice)

        if indice < 0 or indice >= len(referencias):
            continue

        ref = referencias[indice]

        if ref["estado"] == "Fin de servicio":
            continue

        ediciones.append((
            ref["fecha_hora"],
            ref["fecha_servicio"],
            max(0, int(valores["Picks restantes"]))
        ))

    if ediciones:

        # La edición más temprana se convierte en el nuevo ancla.
        ediciones.sort(key=lambda x: x[0])

        fecha_hora, fecha_servicio, pendientes = ediciones[0]

        corte = datetime.strptime(
            fecha_hora,
            "%Y-%m-%d %H:%M:%S"
        )

        # Conservar todas las filas anteriores a la editada.
        if plan_anterior is not None and not plan_anterior.empty:

            prefijo = plan_anterior[
                plan_anterior["Fecha y hora"] < corte
            ].copy()

            guardar_filas_congeladas(prefijo)

        with closing(conectar()) as conn:
            with conn:

                # Eliminar el tramo posterior.
                conn.execute("""
                    DELETE FROM planificacion_congelada
                    WHERE fecha_hora >= ?
                """, (fecha_hora,))

                conn.execute("""
                    DELETE FROM ajustes_planificacion
                    WHERE fecha_hora >= ?
                """, (fecha_hora,))

                # Guardar el valor en su fecha y hora real.
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
# SIGUIENTE SERVICIO INTRODUCIDO
# ==========================================================

def siguiente_servicio(fecha_actual, servicios):

    fechas = [
        date.fromisoformat(fecha)
        for fecha, picks in servicios.items()
        if picks > 0
        and date.fromisoformat(fecha) > fecha_actual
    ]

    return min(fechas) if fechas else None


# ==========================================================
# MOTOR DE PLANIFICACIÓN
# ==========================================================

def calcular_planificacion(
    inicio,
    final,
    servicio_inicial,
    productividad
):

    servicios = obtener_todos_los_servicios()
    ajustes = obtener_ajustes()
    congelados = obtener_congelados()

    registros = {}

    def obtener_picks(fecha):

        return float(
            servicios.get(fecha.isoformat(), 0)
        )

    def agregar(momento, servicio, saldo, estado, origen=AUTO):

        if inicio <= momento <= final:

            clave = (
                momento,
                servicio.isoformat(),
                estado
            )

            # Picks originales del servicio.
            picks_iniciales = obtener_picks(servicio)

            # Picks restantes en este momento.
            picks_restantes = max(
                0,
                int(round(saldo))
            )

            # Porcentaje completado del servicio.
            if picks_iniciales > 0:

                porcentaje_completado = (
                    (picks_iniciales - picks_restantes)
                    / picks_iniciales
                ) * 100

                porcentaje_completado = max(
                    0.0,
                    min(100.0, porcentaje_completado)
                )

            else:

                porcentaje_completado = 0.0

            registros[clave] = {
                "Fecha y hora": momento,
                "Día de servicio": servicio.strftime("%d/%m/%Y"),
                "Picks restantes": picks_restantes,
                "Servicio completado (%)": round(
                    porcentaje_completado, 1
                ),
                "Estado": estado,
                "Origen": origen
            }

    # ------------------------------------------------------
    # FILTRAR LOS AJUSTES ANTERIORES A LA FECHA SELECCIONADA
    # ------------------------------------------------------

    ajustes_validos = {}

    for (hora_txt, servicio_txt), pendientes in ajustes.items():

        fecha_ajuste = date.fromisoformat(servicio_txt)

        if fecha_ajuste >= servicio_inicial:

            ajustes_validos[(hora_txt, servicio_txt)] = pendientes

    # ------------------------------------------------------
    # RECUPERAR FILAS CONGELADAS DE LA PLANIFICACIÓN
    # ------------------------------------------------------

    congelados_validos = []

    for momento_txt, servicio_txt, pendientes, estado, origen in congelados:

        fecha_congelada = date.fromisoformat(servicio_txt)

        if fecha_congelada >= servicio_inicial:

            congelados_validos.append((
                momento_txt,
                servicio_txt,
                pendientes,
                estado,
                origen
            ))

    # ------------------------------------------------------
    # IDENTIFICAR EL ÚLTIMO MANUAL DE ESTA SECUENCIA
    # ------------------------------------------------------

    ancla = None

    if ajustes_validos:

        clave_ancla = max(
            ajustes_validos.keys(),
            key=lambda x: x[0]
        )

        hora_txt, servicio_txt = clave_ancla

        ancla = (
            datetime.strptime(
                hora_txt,
                "%Y-%m-%d %H:%M:%S"
            ),
            date.fromisoformat(servicio_txt),
            ajustes_validos[clave_ancla]
        )

    # ------------------------------------------------------
    # RECUPERAR LAS FILAS CONGELADAS ANTERIORES AL ANCLA
    # ------------------------------------------------------

    if ancla:

        corte = ancla[0]

        for (
            momento_txt,
            servicio_txt,
            pendientes,
            estado,
            origen
        ) in congelados_validos:

            momento = datetime.strptime(
                momento_txt,
                "%Y-%m-%d %H:%M:%S"
            )

            if momento <= corte:

                agregar(
                    momento,
                    date.fromisoformat(servicio_txt),
                    pendientes,
                    estado,
                    origen
                )

    # ------------------------------------------------------
    # PUNTO DE PARTIDA
    # ------------------------------------------------------

    if ancla and inicio <= ancla[0] <= final:

        cursor, dia_servicio, saldo = ancla

        agregar(
            cursor,
            dia_servicio,
            saldo,
            "En curso",
            MANUAL
        )

        iniciado = True

    else:

        # El selector determina el servicio inicial.
        cursor = inicio
        dia_servicio = servicio_inicial
        saldo = obtener_picks(dia_servicio)

        iniciado = False

    # ------------------------------------------------------
    # MOTOR DE CÁLCULO
    # ------------------------------------------------------

    eventos = 0
    limite_eventos = 20000

    while cursor <= final and eventos < limite_eventos:

        eventos += 1

        if not iniciado:

            # Si no hay picks en esa fecha, buscar el siguiente
            # servicio que sí tenga picks introducidos.

            if saldo <= 0:

                siguiente = siguiente_servicio(
                    dia_servicio,
                    servicios
                )

                if siguiente is None:
                    break

                dia_servicio = siguiente
                saldo = obtener_picks(dia_servicio)

            agregar(
                cursor,
                dia_servicio,
                saldo,
                "Inicio de servicio",
                AUTO
            )

            iniciado = True

        if cursor >= final:
            break

        # Siguiente hora exacta.
        siguiente_hora = (
            cursor.replace(
                minute=0,
                second=0,
                microsecond=0
            ) + timedelta(hours=1)
        )

        # Momento en el que terminarían los picks.
        hora_fin = cursor + timedelta(
            seconds=saldo / productividad * 3600
        )

        siguiente = min(
            siguiente_hora,
            hora_fin,
            final
        )

        if siguiente <= cursor:
            break

        horas = (
            siguiente - cursor
        ).total_seconds() / 3600

        saldo = max(
            0.0,
            saldo - productividad * horas
        )

        cursor = siguiente

        # --------------------------------------------------
        # FIN DEL SERVICIO
        # --------------------------------------------------

        if saldo <= 0.000001:

            saldo = 0.0

            agregar(
                cursor,
                dia_servicio,
                0,
                "Fin de servicio",
                AUTO
            )

            # Buscar el siguiente servicio realmente introducido.
            siguiente = siguiente_servicio(
                dia_servicio,
                servicios
            )

            if siguiente is None:
                break

            dia_servicio = siguiente

            saldo = obtener_picks(dia_servicio)

            iniciado = False

        else:

            # Si existe un ajuste manual en esta hora exacta,
            # aplicarlo al servicio correspondiente.
            clave = (
                cursor.strftime("%Y-%m-%d %H:%M:%S"),
                dia_servicio.isoformat()
            )

            origen = AUTO

            if clave in ajustes_validos:

                saldo = float(
                    ajustes_validos[clave]
                )

                origen = MANUAL

            agregar(
                cursor,
                dia_servicio,
                saldo,
                "En curso",
                origen
            )

    # ------------------------------------------------------
    # TABLA FINAL
    # ------------------------------------------------------

    df = pd.DataFrame(
        list(registros.values()),
        columns=COLUMNAS
    )

    if not df.empty:

        df = df.sort_values(
            ["Fecha y hora", "Estado"],
            ascending=[True, True]
        ).reset_index(drop=True)

    return df


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

if "servicio_inicial" not in st.session_state:

    st.session_state.servicio_inicial = date.today().isoformat()


# ==========================================================
# ESTILO
# ==========================================================

st.markdown("""
<style>
.stApp {
    background-color:#f3f5f9;
}

h1,h2,h3 {
    color:#17243a;
}

.block-container {
    padding-top:2rem;
}

[data-testid="stSidebar"] {
    min-width:280px;
}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap:.35rem;
}

[data-testid="stSidebar"] [data-testid="stExpander"] {
    margin-top:0!important;
    margin-bottom:0!important;
    border:none!important;
}

[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    padding-top:7px!important;
    padding-bottom:7px!important;
}

[data-testid="stSidebar"] .stMarkdown {
    margin-bottom:0!important;
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

    st.caption("Introduce los picks de cada fecha.")

    for dia in dias:

        fecha_iso = dia.isoformat()
        clave = f"servicio_{fecha_iso}"

        if clave not in st.session_state:

            st.session_state[clave] = obtener_servicio(
                fecha_iso
            )

        st.number_input(
            dia.strftime("%A %d/%m"),
            min_value=0,
            max_value=1000000,
            step=1,
            key=clave,
            on_change=lambda f=fecha_iso, k=clave: guardar_servicio(
                f,
                st.session_state[k]
            )
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

productividad = int(
    st.session_state.productividad
)

st.sidebar.caption(
    f"Productividad: {productividad:,} picks/h"
)


# ==========================================================
# FILTROS DE PLANIFICACIÓN
# ==========================================================

st.title("📦 Gestión de almacén")

st.header("📊 Previsión de picks restantes")

st.markdown(
    "### 🗓️ Configuración de la planificación"
)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:

    fecha_inicio = st.date_input(
        "Fecha inicio",
        value=date.today(),
        format="DD/MM/YYYY",
        key="filtro_fecha_inicio"
    )

with col2:

    hora_inicio = st.time_input(
        "Hora inicio",
        value=time(22, 0),
        key="filtro_hora_inicio"
    )

with col3:

    fecha_final = st.date_input(
        "Fecha fin",
        value=date.today() + timedelta(days=7),
        format="DD/MM/YYYY",
        key="filtro_fecha_final"
    )

with col4:

    hora_final = st.time_input(
        "Hora fin",
        value=time(23, 0),
        key="filtro_hora_final"
    )

with col5:

    servicios_disponibles = obtener_todos_los_servicios()

    fechas_servicio = sorted(
        date.fromisoformat(fecha)
        for fecha in servicios_disponibles
    )

    if fechas_servicio:

        if "servicio_inicial" not in st.session_state:

            st.session_state.servicio_inicial = (
                fechas_servicio[0].isoformat()
            )

        actual = date.fromisoformat(
            st.session_state.servicio_inicial
        )

        if actual not in fechas_servicio:
            actual = fechas_servicio[0]

        indice = fechas_servicio.index(actual)

        servicio_inicial = st.selectbox(
            "Fecha de servicio inicial",
            options=fechas_servicio,
            index=indice,
            format_func=lambda d: d.strftime("%d/%m/%Y"),
            key="selector_servicio_inicial"
        )

        st.session_state.servicio_inicial = (
            servicio_inicial.isoformat()
        )

    else:

        servicio_inicial = None

        st.warning(
            "Primero introduce picks en el panel lateral."
        )


# ==========================================================
# TABLA DE PLANIFICACIÓN
# ==========================================================

st.divider()

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

elif servicio_inicial is None:

    st.warning(
        "No hay servicios introducidos."
    )

else:

    tabla = calcular_planificacion(
        inicio,
        final,
        servicio_inicial,
        productividad
    )

    if tabla.empty:

        st.warning(
            "No hay servicios con picks para calcular "
            "en el intervalo seleccionado."
        )

    else:

        st.session_state["plan_actual"] = tabla.copy(
            deep=True
        )

        referencias = []

        for _, fila in tabla.iterrows():

            referencias.append({
                "fecha_hora": fila["Fecha y hora"].strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "fecha_servicio": datetime.strptime(
                    fila["Día de servicio"],
                    "%d/%m/%Y"
                ).date().isoformat(),
                "estado": fila["Estado"]
            })

        tabla_vista = tabla.copy()

        tabla_vista["Fecha y hora"] = tabla_vista[
            "Fecha y hora"
        ].dt.strftime("%d/%m/%Y %H:%M:%S")

        editor_key = (
            f"tabla_planificacion_"
            f"{st.session_state.version_tabla}"
        )

        st.session_state[
            f"{editor_key}_referencias"
        ] = referencias

        manual_indices = {
            i
            for i, origen in enumerate(tabla["Origen"])
            if origen == MANUAL
        }

        def colorear_filas(fila):

            if fila["Estado"] == "Fin de servicio":
                color = "#d9f2df"

            elif fila["Estado"] == "Inicio de servicio":
                color = "#dceeff"

            else:
                color = "transparent"

            return [
                f"background-color:{color};"
                for _ in fila
            ]

        def colorear_picks(columna):

            return [
                "color:#d00000;font-weight:bold;"
                if i in manual_indices
                else "color:inherit;"
                for i in columna.index
            ]

        tabla_estilizada = (
            tabla_vista.style
            .apply(colorear_filas, axis=1)
            .apply(
                colorear_picks,
                subset=["Picks restantes"]
            )
        )

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
                "Servicio completado (%)",
                "Estado",
                "Origen"
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

                "Servicio completado (%)": st.column_config.NumberColumn(
                    "Servicio completado (%)",
                    format="%.1f%%",
                    width="medium",
                    help="Porcentaje completado respecto a los picks iniciales de ese servicio."
                ),

                "Estado": st.column_config.TextColumn(
                    "Estado",
                    width="medium"
                ),

                "Origen": st.column_config.TextColumn(
                    "Origen",
                    width="small"
                )
            }
        )

        st.markdown("""
        <div style="
            display:flex;
            flex-wrap:wrap;
            gap:22px;
            margin-top:14px;
            font-size:14px;
        ">

          <span style="background:#dceeff;padding:4px 8px;">
            Inicio de servicio
          </span>

          <span style="background:#d9f2df;padding:4px 8px;">
            Fin de servicio
          </span>

          <span style="color:#d00000;font-weight:bold;">
            ✏️ Manual
          </span>

          <span>
            Automático
          </span>

        </div>
        """, unsafe_allow_html=True)


# ==========================================================
# RESUMEN
# ==========================================================

st.divider()

col_a, col_b = st.columns(2)

col_a.metric(
    "Productividad",
    f"{productividad:,} picks/h"
)

col_b.metric(
    "Días de planificación",
    (fecha_final - fecha_inicio).days + 1
)

st.caption(
    "La fecha de planificación y la fecha de servicio son "
    "independientes. Cada servicio termina al llegar a cero picks "
    "y entonces comienza el siguiente servicio introducido."
)
