
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

COLUMNAS = [
    "Fecha y hora",
    "Día de servicio",
    "Picks restantes",
    "Estado",
    "Origen"
]

MANUAL = "✏️ Manual"
AUTO = "Automático"


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
                    PRIMARY KEY (
                        fecha_hora,
                        fecha_servicio,
                        estado
                    )
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

            columnas = [
                r[1] for r in conn.execute(
                    "PRAGMA table_info(ajustes_planificacion)"
                ).fetchall()
            ]

            if "estado" not in columnas:
                conn.execute("""
                    ALTER TABLE ajustes_planificacion
                    ADD COLUMN estado TEXT DEFAULT 'En curso'
                """)


def obtener_servicio(fecha_iso):

    with closing(conectar()) as conn:
        fila = conn.execute(
            "SELECT picks FROM servicios WHERE fecha=?",
            (fecha_iso,)
        ).fetchone()

    return int(fila[0]) if fila else 0


@st.cache_data(ttl=30)
def obtener_todos_los_servicios():
    """Carga todos los picks mediante una sola consulta."""

    with closing(conectar()) as conn:
        filas = conn.execute(
            "SELECT fecha, picks FROM servicios"
        ).fetchall()

    return {
        fecha: int(picks or 0)
        for fecha, picks in filas
    }


def guardar_servicio(fecha_iso, picks):

    with closing(conectar()) as conn:
        with conn:

            conn.execute("""
                INSERT INTO servicios (fecha, picks)
                VALUES (?, ?)
                ON CONFLICT(fecha)
                DO UPDATE SET picks=excluded.picks
            """, (fecha_iso, int(picks)))


def guardar_sidebar_servicio(fecha_iso, clave):

    guardar_servicio(
        fecha_iso,
        st.session_state[clave]
    )

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
            SELECT fecha_hora, fecha_servicio, pendientes, estado
            FROM ajustes_planificacion
        """).fetchall()

    resultado = {}

    for fecha_hora, fecha_servicio, pendientes, estado in filas:

        resultado[(fecha_hora, fecha_servicio)] = {
            "pendientes": int(pendientes),
            "estado": estado or "En curso"
        }

    return resultado


def obtener_congelados():

    with closing(conectar()) as conn:
        return conn.execute("""
            SELECT fecha_hora, fecha_servicio,
                   pendientes, estado, origen
            FROM planificacion_congelada
            ORDER BY fecha_hora, fecha_servicio, estado
        """).fetchall()


def guardar_filas_congeladas(filas):
    """
    Guarda literalmente las filas ya calculadas.
    No vuelve a calcular sus valores.
    """

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


# ==========================================================
# CONGELAR CÁLCULOS ANTERIORES
# ==========================================================

def congelar_plan_hasta_ancla():
    """
    Al cambiar la productividad, conserva todo lo visible
    hasta el último ajuste manual.
    """

    plan = st.session_state.get("plan_actual")

    if plan is None or plan.empty:
        return

    ajustes = obtener_ajustes()

    if not ajustes:
        return

    ultimo_txt, ultimo_servicio = max(
        ajustes.keys(),
        key=lambda k: k[0]
    )

    corte = datetime.strptime(
        ultimo_txt,
        "%Y-%m-%d %H:%M:%S"
    )

    prefijo = plan[
        plan["Fecha y hora"] <= corte
    ].copy()

    guardar_filas_congeladas(prefijo)


def guardar_productividad():

    congelar_plan_hasta_ancla()

    guardar_configuracion(
        "productividad",
        st.session_state.productividad
    )

    st.session_state.version_tabla += 1


# ==========================================================
# GUARDAR EDICIONES MANUALES
# ==========================================================

def guardar_ediciones(editor_key):

    estado_editor = st.session_state.get(
        editor_key,
        {}
    )

    cambios = estado_editor.get(
        "edited_rows",
        {}
    )

    if not cambios:
        return

    referencias = st.session_state.get(
        f"{editor_key}_referencias",
        []
    )

    plan_anterior = st.session_state.get(
        "plan_actual"
    )

    # ------------------------------------------------------
    # CAMBIO DEL PRIMER DÍA DE SERVICIO
    # ------------------------------------------------------

    cambio_primera = cambios.get(
        0,
        cambios.get("0", {})
    )

    if "Día de servicio" in cambio_primera:

        try:

            nueva_fecha = datetime.strptime(
                cambio_primera["Día de servicio"],
                "%d/%m/%Y"
            ).date()

            st.session_state.servicio_inicial = (
                nueva_fecha.isoformat()
            )

        except (ValueError, TypeError):
            pass

    # ------------------------------------------------------
    # RECOGER CELDAS MANUALES MODIFICADAS
    # ------------------------------------------------------

    ediciones = []

    for indice_raw, valores in cambios.items():

        if "Picks restantes" not in valores:
            continue

        indice = int(indice_raw)

        if indice < 0 or indice >= len(referencias):
            continue

        ref = referencias[indice]

        if ref["estado"] == "Fin de servicio":
            continue

        ediciones.append((
            ref["fecha_hora"],
            ref["fecha_servicio"],
            max(0, int(valores["Picks restantes"])),
            ref["estado"]
        ))

    if ediciones:

        # La modificación más temprana es la nueva referencia.
        ediciones.sort(
            key=lambda x: (x[0], x[1])
        )

        fecha_hora, fecha_servicio, pendientes, estado_fila = (
            ediciones[0]
        )

        corte = datetime.strptime(
            fecha_hora,
            "%Y-%m-%d %H:%M:%S"
        )

        # --------------------------------------------------
        # CONGELAR TODO LO ANTERIOR A LA CELDA MODIFICADA
        # --------------------------------------------------

        if plan_anterior is not None and not plan_anterior.empty:

            prefijo = plan_anterior[
                plan_anterior["Fecha y hora"] < corte
            ].copy()

            guardar_filas_congeladas(prefijo)

        # --------------------------------------------------
        # ELIMINAR LOS CÁLCULOS POSTERIORES
        # --------------------------------------------------

        with closing(conectar()) as conn:
            with conn:

                conn.execute("""
                    DELETE FROM planificacion_congelada
                    WHERE fecha_hora >= ?
                """, (fecha_hora,))

                conn.execute("""
                    DELETE FROM ajustes_planificacion
                    WHERE fecha_hora >= ?
                """, (fecha_hora,))

                # Guardar el nuevo valor manual en su fecha y hora.
                conn.execute("""
                    INSERT INTO ajustes_planificacion (
                        fecha_hora,
                        fecha_servicio,
                        pendientes,
                        estado
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(fecha_hora, fecha_servicio)
                    DO UPDATE SET
                        pendientes=excluded.pendientes,
                        estado=excluded.estado
                """, (
                    fecha_hora,
                    fecha_servicio,
                    pendientes,
                    estado_fila
                ))

    st.session_state.version_tabla += 1


# ==========================================================
# CÁLCULO DE PLANIFICACIÓN
# ==========================================================

def calcular_planificacion(
    inicio,
    final,
    servicio_inicial,
    productividad
):

    """
    Conserva las filas congeladas y calcula únicamente
    después del último ajuste manual.
    """

    ajustes = obtener_ajustes()
    congelados = obtener_congelados()

    # Todos los picks se cargan una sola vez.
    servicios = obtener_todos_los_servicios()

    registros = {}

    def obtener_picks(fecha):

        return servicios.get(
            fecha.isoformat(),
            0
        )

    def agregar(
        momento,
        servicio,
        saldo,
        estado,
        origen=AUTO
    ):

        if inicio <= momento <= final:

            clave = (
                momento,
                servicio.isoformat(),
                estado
            )

            registros[clave] = {
                "Fecha y hora": momento,
                "Día de servicio": servicio.strftime("%d/%m/%Y"),
                "Picks restantes": max(0, int(round(saldo))),
                "Estado": estado,
                "Origen": origen
            }

    # ------------------------------------------------------
    # 1. RECUPERAR LAS FILAS CONGELADAS
    # ------------------------------------------------------

    for (
        momento_txt,
        servicio_txt,
        pendientes,
        estado,
        origen
    ) in congelados:

        momento = datetime.strptime(
            momento_txt,
            "%Y-%m-%d %H:%M:%S"
        )

        servicio = date.fromisoformat(
            servicio_txt
        )

        agregar(
            momento,
            servicio,
            pendientes,
            estado,
            origen
        )

    # ------------------------------------------------------
    # 2. LOCALIZAR EL ÚLTIMO AJUSTE MANUAL
    # ------------------------------------------------------

    ancla = None

    if ajustes:

        (ancla_txt, servicio_txt), datos = max(
            ajustes.items(),
            key=lambda item: item[0][0]
        )

        ancla = (
            datetime.strptime(
                ancla_txt,
                "%Y-%m-%d %H:%M:%S"
            ),
            date.fromisoformat(servicio_txt),
            datos["pendientes"],
            datos["estado"]
        )

    # ------------------------------------------------------
    # 3. ESTABLECER EL PUNTO DE PARTIDA
    # ------------------------------------------------------

    if ancla:

        cursor, dia_servicio, saldo, estado_ancla = ancla

        # La fila manual permanece en su fecha y hora original.
        agregar(
            cursor,
            dia_servicio,
            saldo,
            estado_ancla,
            MANUAL
        )

        iniciado = True

    else:

        cursor = inicio
        dia_servicio = servicio_inicial

        saldo = float(
            obtener_picks(dia_servicio)
        )

        iniciado = False

    # ------------------------------------------------------
    # 4. CÁLCULO AUTOMÁTICO POSTERIOR
    # ------------------------------------------------------

    eventos = 0
    limite_eventos = 20000

    while cursor <= final and eventos < limite_eventos:

        eventos += 1

        # Si todavía no ha comenzado el servicio.
        if not iniciado:

            # Saltar servicios sin picks.
            # Se consulta el diccionario en memoria, no SQLite.
            saltos = 0

            while saldo <= 0 and saltos < 3660:

                dia_servicio += timedelta(days=1)

                saldo = float(
                    obtener_picks(dia_servicio)
                )

                saltos += 1

            if saldo <= 0:
                break

            agregar(
                cursor,
                dia_servicio,
                saldo,
                "Inicio de servicio",
                AUTO
            )

            iniciado = True

        # Si el ajuste manual deja el servicio a cero,
        # se termina y comienza el siguiente servicio.
        if saldo <= 0.000001:

            agregar(
                cursor,
                dia_servicio,
                0,
                "Fin de servicio",
                AUTO
            )

            dia_servicio += timedelta(days=1)

            saldo = float(
                obtener_picks(dia_servicio)
            )

            iniciado = False
            continue

        if cursor >= final:
            break

        # Siguiente cambio de hora.
        siguiente_hora = (
            cursor.replace(
                minute=0,
                second=0,
                microsecond=0
            ) + timedelta(hours=1)
        )

        # Momento en que terminaría el servicio.
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

        # Consumir picks según productividad.
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

            # El siguiente servicio comienza inmediatamente.
            dia_servicio += timedelta(days=1)

            saldo = float(
                obtener_picks(dia_servicio)
            )

            iniciado = False

        else:

            agregar(
                cursor,
                dia_servicio,
                saldo,
                "En curso",
                AUTO
            )

    # ------------------------------------------------------
    # 5. CREAR TABLA FINAL
    # ------------------------------------------------------

    df = pd.DataFrame(
        list(registros.values()),
        columns=COLUMNAS
    )

    if not df.empty:

        df = df.sort_values(
            by=[
                "Fecha y hora",
                "Estado",
                "Día de servicio"
            ],
            ascending=[True, True, True]
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

# El primer servicio de cada semana comienza el lunes seleccionado.
# Al cambiar de semana, actualizamos el servicio inicial.
if st.session_state.get("semana_servicio_activa") != lunes.isoformat():

    st.session_state.servicio_inicial = lunes.isoformat()

    st.session_state.semana_servicio_activa = (
        lunes.isoformat()
    )


# ==========================================================
# PICKS POR SERVICIO
# ==========================================================

with st.sidebar.expander(
    "📋 PICKS POR SERVICIO",
    expanded=False
):

    st.caption("Picks totales de cada día.")

    for i, dia in enumerate(dias):

        fecha_iso = dia.isoformat()

        clave = f"servicio_{fecha_iso}"

        if clave not in st.session_state:

            st.session_state[clave] = obtener_servicio(
                fecha_iso
            )

        st.number_input(
            f"{NOMBRES[i]} {dia.strftime('%d/%m')}",
            min_value=0,
            max_value=1000000,
            step=1,
            key=clave,
            on_change=guardar_sidebar_servicio,
            args=(fecha_iso, clave)
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
# PANTALLA PRINCIPAL
# ==========================================================

st.title("📦 Gestión de almacén")

st.caption(
    f"Semana de servicio: "
    f"{dias[0].strftime('%d/%m/%Y')} "
    f"al {dias[-1].strftime('%d/%m/%Y')}"
)

st.divider()

st.header("📊 Previsión de picks restantes")

st.markdown(
    "### 🗓️ Seleccionar intervalo de consulta"
)

c1, c2, c3, c4 = st.columns(4)

with c1:

    st.markdown("**Fecha inicio**")

    fecha_inicio = st.date_input(
        "Fecha inicio",
        value=dias[0],
        format="DD/MM/YYYY",
        key="filtro_fecha_inicio",
        label_visibility="collapsed"
    )

with c2:

    st.markdown("**Hora inicio**")

    hora_inicio = st.time_input(
        "Hora inicio",
        value=time(22, 0),
        key="filtro_hora_inicio",
        label_visibility="collapsed"
    )

with c3:

    st.markdown("**Fecha fin**")

    fecha_final = st.date_input(
        "Fecha fin",
        value=dias[-1],
        format="DD/MM/YYYY",
        key="filtro_fecha_final",
        label_visibility="collapsed"
    )

with c4:

    st.markdown("**Hora fin**")

    hora_final = st.time_input(
        "Hora fin",
        value=time(23, 0),
        key="filtro_hora_final",
        label_visibility="collapsed"
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

else:

    # ------------------------------------------------------
    # FECHAS DISPONIBLES PARA EL SELECTOR
    # ------------------------------------------------------

    opciones_fechas = []

    dia_opcion = fecha_inicio

    while dia_opcion <= fecha_final + timedelta(days=30):

        opciones_fechas.append(
            dia_opcion.strftime("%d/%m/%Y")
        )

        dia_opcion += timedelta(days=1)

    try:

        servicio_actual = date.fromisoformat(
            st.session_state.servicio_inicial
        )

    except (ValueError, TypeError):

        servicio_actual = lunes

        st.session_state.servicio_inicial = (
            servicio_actual.isoformat()
        )

    servicio_visible = servicio_actual.strftime(
        "%d/%m/%Y"
    )

    if servicio_visible not in opciones_fechas:

        opciones_fechas.insert(
            0,
            servicio_visible
        )

    # ------------------------------------------------------
    # CALCULAR PLANIFICACIÓN
    # ------------------------------------------------------

    tabla = calcular_planificacion(
        inicio,
        final,
        servicio_actual,
        productividad
    )

    if tabla.empty:

        st.warning(
            "No hay datos para mostrar en ese intervalo."
        )

    else:

        # Guardar la tabla sin formato para los callbacks.
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

        st.markdown(
            "Modifica los picks en la misma fila. "
            "Esa fila será el nuevo punto manual; "
            "solo se recalcularán las filas posteriores."
        )

        # --------------------------------------------------
        # COLORES
        # --------------------------------------------------

        manual_indices = [
            i
            for i, origen in enumerate(tabla_vista["Origen"])
            if origen == MANUAL
        ]

        def estilo_fila(fila):

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

        def estilo_picks(columna):

            return [
                "color:#d00000;font-weight:bold;"
                if i in manual_indices
                else "color:inherit;"
                for i in columna.index
            ]

        tabla_estilizada = (
            tabla_vista.style
            .apply(estilo_fila, axis=1)
            .apply(
                estilo_picks,
                subset=["Picks restantes"]
            )
        )

        # --------------------------------------------------
        # EDITOR
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
        # LEYENDA
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
            ✏️ Manual: valor editado
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

col_a, col_b = st.columns(2)

col_a.metric(
    "Productividad",
    f"{productividad:,} picks/h"
)

col_b.metric(
    "Días consultados",
    (fecha_final - fecha_inicio).days + 1
)

st.caption(
    "Cada ajuste manual se conserva en su fecha y hora. "
    "Las filas anteriores no cambian; las posteriores se "
    "recalculan automáticamente con la productividad seleccionada."
)
