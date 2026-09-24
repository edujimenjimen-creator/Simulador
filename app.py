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

        # --- CORRECCIÓN AQUÍ ---
        # Si h_fin es 23 (última hora del día), el fin visual debe marcarse a las 24:00 (o el inicio del siguiente tramo)
        if h_fin == 23:
            h_fin_idx = 23
            etiqueta_fin = "24:00"
        else:
            h_fin_idx = h_fin + 1
            etiqueta_fin = horas_24[h_fin_idx]
        # -----------------------

        hitos_produccion.append({
            "tipo": "FIN",
            "eje_x": f"{dia[:3]} {etiqueta_fin if h_fin == 23 else horas_24[h_fin_idx]}",
            "y_val": (
                produccion_acum[h_fin]
                if h_fin == 23
                else produccion_acum[h_fin_idx]
            ),
            "texto": (
                f"<b>FIN PROD {etiqueta_fin}</b><br>Buffer:"
                f" {int(buffer_muelle[h_fin]):,}".replace(",", ".") + " pks"
            ),
        })
