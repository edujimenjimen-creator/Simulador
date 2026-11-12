
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
        return int(servicios.get(fecha.isoformat(), 0))

    def agregar(momento, servicio, saldo, estado, origen=AUTO):
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
    # FILTRAR AJUSTES SEGÚN EL SERVICIO SELECCIONADO
    # ------------------------------------------------------

    ajustes_validos = {}

    for (hora_txt, servicio_txt), pendientes in ajustes.items():
        fecha_ajuste = date.fromisoformat(servicio_txt)

        # Ignorar ajustes de servicios anteriores al seleccionado.
        if fecha_ajuste >= servicio_inicial:
            ajustes_validos[(hora_txt, servicio_txt)] = pendientes

    # ------------------------------------------------------
    # FILTRAR HISTÓRICO CONGELADO
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
    # LOCALIZAR EL ÚLTIMO AJUSTE MANUAL VÁLIDO
    # ------------------------------------------------------

    ancla = None

    if ajustes_validos:
        clave_ancla = max(
            ajustes_validos.keys(),
            key=lambda x: x[0]
        )

        hora_txt, servicio_txt = clave_ancla

        ancla = (
            datetime.strptime(hora_txt, "%Y-%m-%d %H:%M:%S"),
            date.fromisoformat(servicio_txt),
            ajustes_validos[clave_ancla]
        )

    # ------------------------------------------------------
    # RECUPERAR FILAS CONGELADAS ANTERIORES AL ANCLA
    # ------------------------------------------------------

    if ancla:
        corte = ancla[0]

        for momento_txt, servicio_txt, pendientes, estado, origen in congelados_validos:
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
    # DETERMINAR EL PUNTO DE PARTIDA
    # ------------------------------------------------------

    if ancla and ancla[0] >= inicio:

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
        # El selector manda: se comienza con los picks
        # del servicio que el usuario acaba de elegir.
        cursor = inicio
        dia_servicio = servicio_inicial
        saldo = float(obtener_picks(dia_servicio))
        iniciado = False

    # ------------------------------------------------------
    # MOTOR DE CÁLCULO
    # ------------------------------------------------------

    eventos = 0
    limite_eventos = 20000

    while cursor <= final and eventos < limite_eventos:

        eventos += 1

        if not iniciado:

            # Si no hay picks, buscar el siguiente servicio
            # introducido en la base de datos.
            if saldo <= 0:

                fechas_siguientes = [
                    date.fromisoformat(fecha)
                    for fecha, picks in servicios.items()
                    if picks > 0 and
                    date.fromisoformat(fecha) > dia_servicio
                ]

                if not fechas_siguientes:
                    break

                dia_servicio = min(fechas_siguientes)
                saldo = float(obtener_picks(dia_servicio))

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

        if siguiente <= cursor:
            break

        horas = (
            siguiente - cursor
        ).total_seconds() / 3600

        saldo = max(
            0,
            saldo - productividad * horas
        )

        cursor = siguiente

        if saldo <= 0.000001:

            saldo = 0

            agregar(
                cursor,
                dia_servicio,
                0,
                "Fin de servicio",
                AUTO
            )

            fechas_siguientes = [
                date.fromisoformat(fecha)
                for fecha, picks in servicios.items()
                if picks > 0 and
                date.fromisoformat(fecha) > dia_servicio
            ]

            if not fechas_siguientes:
                break

            dia_servicio = min(fechas_siguientes)
            saldo = float(obtener_picks(dia_servicio))
            iniciado = False

        else:
            clave = (
                cursor.strftime("%Y-%m-%d %H:%M:%S"),
                dia_servicio.isoformat()
            )

            origen = AUTO

            if clave in ajustes_validos:
                saldo = float(ajustes_validos[clave])
                origen = MANUAL

            agregar(
                cursor,
                dia_servicio,
                saldo,
                "En curso",
                origen
            )

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
