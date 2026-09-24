# ==========================================
# 3. MOTOR PROACTIVO 24/7 (CORREGIDO PARA RESPETAR TECHO Y RETRASAR ARRANQUE)
# ==========================================
df_completo_ajustado = []
hitos_produccion = []
stock_actual_00h = stock_inicial_lunes

for dia_idx, dia in enumerate(dias_semana):
    demanda_total = demanda_servicio_por_dia[dia]
    factor_escala = demanda_total / sum(tiendas_por_hora)
    demanda_h = [round(t * factor_escala) for t in tiendas_por_hora]
    
    demanda_acum = np.cumsum(demanda_h)
    demanda_total_real = demanda_acum[-1]

    produccion_h = [0] * 24

    if dia == "Sábado":
        for h in range(24):
            p_test = list(produccion_h)
            p_test[h] = vel_maquina
            p_acum_test = stock_actual_00h + np.cumsum(p_test)
            if p_acum_test[h] < demanda_total_real + stock_objetivo_sabado:
                produccion_h[h] = vel_maquina
    else:
        # ESTRATEGIA 24/7 OPTIMIZADA: 
        # Partimos con la máquina apagada y vamos encendiendo ÚNICAMENTE las horas 
        # donde el buffer baje del objetivo mínimo (Piso), priorizando las horas 
        # más cercanas al problema sin pasarnos del Techo.
        
        # Iteramos para garantizar el piso en todo momento
        for _ in range(30):
            p_acum = stock_actual_00h + np.cumsum(produccion_h)
            buf = p_acum - demanda_acum
            adel = buf / vel_maquina

            min_idx = np.argmin(adel)
            if adel[min_idx] >= objetivo_horas:
                break

            # Si estamos por debajo del piso, encendemos una hora cercana al punto crítico
            # Buscamos encender hacia atrás desde el punto de mínimos para levantar el valle
            encendido = False
            for h in range(min_idx, -1, -1):
                if produccion_h[h] == 0:
                    produccion_h[h] = vel_maquina
                    encendido = True
                    break
            if not encendido:
                for h in range(min_idx, 24):
                    if produccion_h[h] == 0:
                        produccion_h[h] = vel_maquina
                        encendido = True
                        break
            if not encendido:
                break

        # FILTRADO DE TECHO: Apagar horas excedentes empezando por la madrugada (00:00 en adelante)
        # si hacerlo no infringe el piso mínimo. Esto retrasa automáticamente el inicio de producción.
        for _ in range(30):
            p_acum = stock_actual_00h + np.cumsum(produccion_h)
            buf = p_acum - demanda_acum
            adel = buf / vel_maquina

            max_idx = np.argmax(adel)
            if adel[max_idx] <= adelanto_max_estandar:
                break

            apagado = False
            # Intentamos apagar desde la hora 0 (madrugada) hacia adelante para retrasar el arranque
            for h in range(24):
                if produccion_h[h] == vel_maquina:
                    produccion_h[h] = 0
                    p_acum_test = stock_actual_00h + np.cumsum(produccion_h)
                    buf_test = p_acum_test - demanda_acum
                    adel_test = buf_test / vel_maquina
                    
                    # Verificamos que al apagar esta hora NO rompamos el piso mínimo en ninguna otra hora
                    if min(adel_test) >= objetivo_horas:
                        apagado = True
                        break
                    else:
                        # Si rompe el piso, revertimos el apagado y probamos con otra hora
                        produccion_h[h] = vel_maquina
            if not apagado:
                break

    produccion_acum = stock_actual_00h + np.cumsum(produccion_h)
    buffer_muelle = produccion_acum - demanda_acum
    horas_adelanto = np.round(buffer_muelle / vel_maquina, 2)

    horas_activas = [i for i, p in enumerate(produccion_h) if p > 0]
    if horas_activas:
        h_ini = horas_activas[0]
        h_fin = horas_activas[-1]

        hitos_produccion.append({
            "tipo": "INICIO",
            "eje_x": f"{dia[:3]} {horas_24[h_ini]}",
            "y_val": produccion_acum[h_ini],
            "texto": (
                f"<b>INICIO PROD {horas_24[h_ini]}</b><br>Buffer:"
                f" {int(buffer_muelle[h_ini]):,}".replace(",", ".")
                + " pks"
            ),
        })

        h_fin_idx = min(h_fin + 1, 23)
        hitos_produccion.append({
            "tipo": "FIN",
            "eje_x": f"{dia[:3]} {horas_24[h_fin_idx]}",
            "y_val": produccion_acum[h_fin_idx],
            "texto": (
                f"<b>FIN PROD {horas_24[h_fin_idx]}</b><br>Buffer:"
                f" {int(buffer_muelle[h_fin_idx]):,}".replace(",", ".")
                + " pks"
            ),
        })

    for h_idx in range(24):
        df_completo_ajustado.append({
            "Eje_X": f"{dia[:3]} {horas_24[h_idx]}",
            "Dia": dia,
            "Hora": horas_24[h_idx],
            "Demanda_Acum": demanda_acum[h_idx],
            "Prod_Acum": produccion_acum[h_idx],
            "Adelanto_Horas": horas_adelanto[h_idx],
            "Produciendo": 1 if produccion_h[h_idx] > 0 else 0,
        })

    stock_actual_00h = produccion_acum[23] - demanda_total_real

df_plot = pd.DataFrame(df_completo_ajustado)
