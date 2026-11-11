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
                CREATE TABLE IF NOT EXISTS planificacion_congelada (
                    fecha_hora TEXT NOT NULL,
                    fecha_servicio TEXT NOT NULL,
                    pendientes INTEGER NOT NULL,
                    estado TEXT NOT NULL,
                    origen TEXT NOT NULL,
                    PRIMARY KEY (fecha_hora, fecha_servicio, estado)
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


def congelar_hasta_ultimo_manual():
    """Guarda el tramo ya calculado hasta el último ajuste manual."""

    tabla = st.session_state.get("plan_actual")

    if tabla is None or tabla.empty:
        return

    manuales = tabla[tabla["Origen"] == "✏️ Manual"]

    if manuales.empty:
        return

    corte = manuales["Fecha y hora"].max()
    prefijo = tabla[tabla["Fecha y hora"] <= corte]

    with closing(conectar()) as conn:
        with conn:

            for _, fila in prefijo.iterrows():

                conn.execute("""
                    INSERT INTO planificacion_congelada
                    (fecha_hora, fecha_servicio, pendientes, estado, origen)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(fecha_hora, fecha_servicio, estado)
                    DO UPDATE SET pendientes=excluded.pendientes,
                                  origen=excluded.origen
                """, (
                    fila["Fecha y hora"].strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.strptime(
                        fila["Día de servicio"], "%d/%m/%Y"
                    ).date().isoformat(),
                    int(fila["Picks restantes"]),
                    fila["Estado"],
                    fila["Origen"]
                ))


def guardar_productividad():

    congelar_hasta_ultimo_manual()

    guardar_configuracion(
        "productividad",
        st.session_state.productividad
    )

    st.session_state.version_tabla += 1


def obtener_congelados():

    with closing(conectar()) as conn:
        filas = conn.execute("""
            SELECT fecha_hora, fecha_servicio, pendientes, estado, origen
            FROM planificacion_congelada
            ORDER BY fecha_hora,
            CASE estado WHEN 'Fin de servicio' THEN 0 ELSE 1 END
        """).fetchall()

    return filas


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

    # El desplegable de la primera fila determina el primer servicio.
    if "0" in cambios or 0 in cambios:

        valores_primera_fila = cambios.get(
            "0", cambios.get(0, {})
        )

        if "Día de servicio" in valores_primera_fila:

            try:
                fecha_elegida = datetime.strptime(
                    valores_primera_fila["Día de servicio"],
                    "%d/%m/%Y"
                ).date()

                st.session_state.servicio_inicial = (
                    fecha_elegida.isoformat()
                )

            except ValueError:
                pass

    # Recoger las celdas de picks modificadas.
    ediciones_picks = []

    for indice, valores in cambios.items():

        if "Picks restantes" not in valores:
            continue

        indice = int(indice)

        if indice >= len(referencias):
            continue

        referencia = referencias[indice]

        if referencia["estado"] == "Fin de servicio":
            continue

        fecha_hora = referencia["fecha_hora"]
        fecha_servicio = referencia["fecha_servicio"]
        pendientes = max(0, int(valores["Picks restantes"]))

        ediciones_picks.append((
            fecha_hora,
            fecha_servicio,
            pendientes
        ))

    if ediciones_picks:

        # La edición más temprana es el nuevo punto de partida manual.
        ediciones_picks.sort(key=lambda x: x[0])

        fecha_hora, fecha_servicio, pendientes = ediciones_picks[0]

        with closing(conectar()) as conn:
            with conn:

                # Eliminar el tramo posterior al nuevo ajuste.
                conn.execute("""
                    DELETE FROM planificacion_congelada
                    WHERE fecha_hora >= ?
                """, (fecha_hora,))

                conn.execute("""
                    DELETE FROM ajustes_planificacion
                    WHERE fecha_hora >= ?
                """, (fecha_hora,))

                # Guardar el nuevo punto manual.
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
    congelados = obtener_congelados()

    registros = []

    def agregar(
        momento,
        dia,
        saldo,
        estado,
        origen="Automático"
    ):

        if inicio <= momento <= final:

            registros.append({
                "Fecha y hora": momento,
                "Día de servicio": dia.strftime("%d/%m/%Y"),
                "Picks restantes": max(0, int(round(saldo))),
                "Estado": estado,
                "Origen": origen,
            })

    # Buscar el último punto manual.
    anclas = []

    for (momento, servicio), saldo in ajustes.items():

        anclas.append((
            datetime.strptime(
                momento, "%Y-%m-%d %H:%M:%S"
            ),
            date.fromisoformat(servicio),
            saldo
        ))

    ancla = max(anclas, key=lambda x: x[0]) if anclas else None

    if ancla:

        corte, dia_servicio, saldo = ancla

        # Recuperar el tramo congelado anterior al último ajuste.
        for (
            momento_txt,
            servicio_txt,
            pendientes,
            estado,
            origen
        ) in congelados:

            momento = datetime.strptime(
                momento_txt, "%Y-%m-%d %H:%M:%S"
            )

            if momento <= corte:

                agregar(
                    momento,
                    date.fromisoformat(servicio_txt),
                    pendientes,
                    estado,
                    origen
                )

        # Añadir los puntos manuales previos que no estén congelados.
        for (
            (momento_txt, servicio_txt),
            pendientes
        ) in ajustes.items():

            momento = datetime.strptime(
                momento_txt, "%Y-%m-%d %H:%M:%S"
            )

            if momento <= corte and not any(
                r["Fecha y hora"] == momento
                and r["Día de servicio"] ==
                date.fromisoformat(servicio_txt).strftime("%d/%m/%Y")
                for r in registros
            ):

                agregar(
                    momento,
                    date.fromisoformat(servicio_txt),
                    pendientes,
                    "En curso",
                    "✏️ Manual"
                )

        # Asegurar que el último punto manual aparece.
        if not any(
            r["Fecha y hora"] == corte
            and r["Día de servicio"] ==
            dia_servicio.strftime("%d/%m/%Y")
            for r in registros
        ):

            agregar(
                corte,
                dia_servicio,
                saldo,
                "En curso",
                "✏️ Manual"
            )

        cursor = corte
        saldo = float(saldo)
        iniciado = True

    else:

        cursor = inicio
        dia_servicio = servicio_inicial
        saldo = float(
            obtener_servicio(dia_servicio.isoformat())
        )
        iniciado = False

    limite = 1000
    procesados = 0

    while cursor <= final and procesados < limite:

        if not iniciado:

            clave = (
                cursor.strftime("%Y-%m-%d %H:%M:%S"),
                dia_servicio.isoformat()
            )

            if clave in ajustes:
                saldo = float(ajustes[clave])

            agregar(
                cursor,
                dia_servicio,
                saldo,
                "Inicio de servicio",
                "✏️ Manual" if clave in ajustes else "Automático"
            )

        iniciado = True

        if saldo <= 0.000001:

            agregar(
                cursor,
                dia_servicio,
                0,
                "Fin de servicio"
            )

            dia_servicio += timedelta(days=1)
            procesados += 1

            saldo = float(
                obtener_servicio(dia_servicio.isoformat())
            )

            iniciado = False
            continue

        if cursor >= final:
            break

        siguiente_hora = (
            cursor.replace(
                minute=0,
                second=0,
                microsecond=0
            ) + timedelta(hours=1)
        )

        hora_fin = cursor + timedelta(
            seconds=saldo / productividad * 3600
        )

        siguiente = min(
            siguiente_hora,
            hora_fin,
            final
        )

        saldo = max(
            0.,
            saldo - productividad *
            (siguiente - cursor).total_seconds() / 3600
        )

        cursor = siguiente

        if saldo <= 0.000001:

            saldo = 0.

            agregar(
                cursor,
                dia_servicio,
                0,
                "Fin de servicio"
            )

            dia_servicio += timedelta(days=1)
            procesados += 1

            saldo = float(
                obtener_servicio(dia_servicio.isoformat())
            )

            iniciado = False
            continue

        clave = (
            cursor.strftime("%Y-%m-%d %H:%M:%S"),
            dia_servicio.isoformat()
        )

        origen = "Automático"

        if clave in ajustes:

            saldo = float(ajustes[clave])
            origen = "✏️ Manual"

        agregar(
            cursor,
            dia_servicio,
            saldo,
            "En curso",
            origen
        )

    return pd.DataFrame(
        registros,
        columns=[
            "Fecha y hora",
            "Día de servicio",
            "Picks restantes",
            "Estado",
            "Origen"
        ]
    )


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

        indices_rojos = {
            indice
            for indice, origen in enumerate(tabla["Origen"])
            if origen == "✏️ Manual"
        }

        # Guardar la instantánea antes de convertir fechas a texto.
        st.session_state["plan_actual"] = tabla.copy(deep=True)

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
                "Estado",
                "Origen"
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
                ),

                "Origen": st.column_config.TextColumn(
                    "Origen",
                    width="small"
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
                ✏️ Manual: valor editado y guardado
            </span>

            <span>
                Automático: valor calculado por productividad
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
    "Las filas modificadas manualmente se identifican en la columna "
    "«Origen» como ✏️ Manual. Las demás son Automáticas. "
    "Las filas de finalización aparecen en verde claro y las de inicio "
    "de servicio en azul claro."
)
