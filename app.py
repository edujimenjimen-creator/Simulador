
# ==========================================================
# TABLA CON COLORES SEGÚN EL ESTADO
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

    opciones_fechas = []

    dia_opcion = fecha_inicio

    while dia_opcion <= fecha_final + timedelta(days=30):

        opciones_fechas.append(
            dia_opcion.strftime("%d/%m/%Y")
        )

        dia_opcion += timedelta(days=1)

    if "servicio_inicial" not in st.session_state:
        st.session_state.servicio_inicial = fecha_inicio.isoformat()

    servicio_actual = datetime.strptime(
        st.session_state.servicio_inicial,
        "%Y-%m-%d"
    ).date()

    servicio_visible = servicio_actual.strftime("%d/%m/%Y")

    if servicio_visible not in opciones_fechas:
        opciones_fechas.insert(0, servicio_visible)

    tabla = calcular_planificacion(
        inicio,
        final,
        servicio_actual,
        productividad
    )

    if tabla.empty:

        st.warning("No hay datos para mostrar.")

    else:

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

        # Identificar los valores modificados manualmente.
        ajustes = obtener_ajustes()

        indices_rojos = set()

        for indice, referencia in enumerate(referencias):

            clave = (
                referencia["fecha_hora"],
                referencia["fecha_servicio"]
            )

            if clave in ajustes:
                indices_rojos.add(indice)

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
            "Puedes modificar manualmente los picks restantes."
        )

        # --------------------------------------------------
        # COLORES DE LAS FILAS
        # --------------------------------------------------

        def colorear_filas(fila):

            estado = fila["Estado"]

            if estado == "Fin de servicio":
                return [
                    "background-color: #d9f2df;"
                    for _ in fila
                ]

            elif estado == "Inicio de servicio":
                return [
                    "background-color: #dceeff;"
                    for _ in fila
                ]

            return [
                "background-color: transparent;"
                for _ in fila
            ]

        # --------------------------------------------------
        # COLOR ROJO PARA LOS PICKS MANUALES
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
                "Estado"
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
                Picks modificados manualmente
            </span>

            <span>
                Picks calculados automáticamente
            </span>
        </div>
        """, unsafe_allow_html=True)
