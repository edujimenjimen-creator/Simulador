import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==========================================
# 1. PARÁMETROS CONFIGURABLES
# ==========================================
vel_maquina = 5000          # Picks/hora
objetivo_horas = 5.0        # PISO INVIOLABLE MÍNIMO (6 horas de servicio)
adelanto_max_estandar = 10.0 # TECHO MÁXIMO CONFIGURABLE (10 horas)

demanda_servicio_por_dia = {
    "Lunes": 70000,
    "Martes": 50000,
    "Miércoles": 75000,
    "Jueves": 80000,
    "Viernes": 89000,
    "Sábado": 60000
}

demanda_lunes_siguiente = 70000 

tiendas_por_hora = [
    1, 3, 3, 3, 3,   # 00:00 - 04:00
    0, 0, 0, 0,       # 05:00 - 08:00
    8, 19, 9, 9,      # 09:00 - 12:00
    2, 2,             # 13:00 - 14:00
    0,                # 15:00
    3, 7, 12, 4, 1,   # 16:00 - 20:00 (20:00h Última Carga)
    0, 0, 0           # 21:00 - 23:00
]

horas_24 = [f"{h:02d}:00" for h in range(24)]
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

# ==========================================
# 2. CÁLCULO DE OBJETIVO DE SÁBADO (BLINDADO)
# ==========================================
factor_lunes = demanda_lunes_siguiente / sum(tiendas_por_hora)
demanda_lunes_h = [round(t * factor_lunes) for t in tiendas_por_hora]
for i in range(21, 24):
    demanda_lunes_h[i] = 0
demanda_acum_lunes = np.cumsum(demanda_lunes_h)

cargas_madrugada_lunes = sum(demanda_lunes_h[:6])
cargas_6h_lunes = sum(demanda_lunes_h[6:12])
stock_objetivo_sabado = cargas_madrugada_lunes + cargas_6h_lunes

for _ in range(5):
    prod_h_test = [vel_maquina if (6 <= i <= 21) else 0 for i in range(24)]
    prod_acum_test = stock_objetivo_sabado + np.cumsum(prod_h_test)
    buffer_test = prod_acum_test - demanda_acum_lunes
    adelanto_test = buffer_test / vel_maquina
    min_adelanto_lunes = min(adelanto_test[:21])
    
    if min_adelanto_lunes < objetivo_horas:
        deficit = (objetivo_horas - min_adelanto_lunes) * vel_maquina
        stock_objetivo_sabado += int(np.ceil(deficit))
    else:
        break

stock_inicial_lunes = stock_objetivo_sabado

# ==========================================
# 3. MOTOR PROACTIVO
# ==========================================
df_completo_ajustado = []
info_paradas = []
info_arranques = []
stock_actual_00h = stock_inicial_lunes

for dia_idx, dia in enumerate(dias_semana):
    demanda_total = demanda_servicio_por_dia[dia]
    factor_escala = demanda_total / sum(tiendas_por_hora)
    demanda_h = [round(t * factor_escala) for t in tiendas_por_hora]
    for i in range(21, 24):
        demanda_h[i] = 0
    
    demanda_acum = np.cumsum(demanda_h)
    demanda_total_real = demanda_acum[20] 
    
    produccion_h = [0] * 24
    
    if dia == "Sábado":
        for h in range(6, 22):
            produccion_h[h] = vel_maquina
        for _ in range(25):
            p_acum = stock_actual_00h + np.cumsum(produccion_h)
            if p_acum[20] >= demanda_total_real + stock_objetivo_sabado:
                apagado = False
                for h in range(20, 5, -1):
                    if produccion_h[h] == vel_maquina:
                        produccion_h[h] = 0
                        p_acum_test = stock_actual_00h + np.cumsum(produccion_h)
                        if p_acum_test[20] >= demanda_total_real + stock_objetivo_sabado:
                            apagado = True
                            break
                        else:
                            produccion_h[h] = vel_maquina
                if not apagado:
                    break
            else:
                break
    else:
        for h in range(6, 22):
            produccion_h[h] = vel_maquina

        for _ in range(25):
            p_acum = stock_actual_00h + np.cumsum(produccion_h)
            buf = p_acum - demanda_acum
            adel = buf / vel_maquina
            
            min_idx = np.argmin(adel[:21])
            if adel[min_idx] >= objetivo_horas:
                break
            
            encendido = False
            for h in range(min_idx, -1, -1):
                if produccion_h[h] == 0:
                    produccion_h[h] = vel_maquina
                    encendido = True
                    break
            if not encendido:
                for h in range(24):
                    if produccion_h[h] == 0:
                        produccion_h[h] = vel_maquina
                        encendido = True
                        break
            if not encendido:
                break

        for _ in range(25):
            p_acum = stock_actual_00h + np.cumsum(produccion_h)
            buf = p_acum - demanda_acum
            adel = buf / vel_maquina
            
            max_idx = np.argmax(adel[:21])
            if adel[max_idx] <= adelanto_max_estandar:
                break
            
            apagado = False
            for h in range(max_idx, -1, -1):
                if produccion_h[h] == vel_maquina:
                    produccion_h[h] = 0
                    p_acum_test = stock_actual_00h + np.cumsum(produccion_h)
                    buf_test = p_acum_test - demanda_acum
                    adel_test = buf_test / vel_maquina
                    if min(adel_test[:21]) >= objetivo_horas:
                        apagado = True
                        break
                    else:
                        produccion_h[h] = vel_maquina 
            if not apagado:
                break

    produccion_acum = stock_actual_00h + np.cumsum(produccion_h)
    buffer_muelle = produccion_acum - demanda_acum
    horas_adelanto = np.round(buffer_muelle / vel_maquina, 2)

    horas_con_prod = [i for i, p in enumerate(produccion_h) if p > 0]
    ultima_hora_prod = horas_con_prod[-1] if horas_con_prod else 0
    primera_hora_prod = horas_con_prod[0] if horas_con_prod else 0
    
    idx_parada_global = dia_idx * 24 + ultima_hora_prod
    hora_etiqueta_fin = horas_24[(ultima_hora_prod + 1) % 24]
    info_paradas.append({
        "idx_global": idx_parada_global,
        "texto_etiqueta": f"FIN PROD {hora_etiqueta_fin}\nBuffer final: {int(buffer_muelle[23]):,} pks",
        "picks_acum": int(produccion_acum[ultima_hora_prod]),
    })

    idx_inicio_global = dia_idx * 24 + primera_hora_prod
    hora_etiqueta_ini = horas_24[primera_hora_prod]
    info_arranques.append({
        "idx_global": idx_inicio_global,
        "texto_etiqueta": f"INICIO PROD {hora_etiqueta_ini}\nBuffer inicial: {int(buffer_muelle[primera_hora_prod]):,} pks",
        "picks_acum": int(produccion_acum[primera_hora_prod]),
    })

    for h_idx in range(24):
        df_completo_ajustado.append({
            "Eje_X": f"{dia[:3]} {horas_24[h_idx]}",
            "Demanda_Acum": demanda_acum[h_idx],
            "Prod_Acum": produccion_acum[h_idx],
            "Adelanto_Horas": horas_adelanto[h_idx]
        })

    stock_actual_00h = produccion_acum[23] - demanda_total_real

df_plot = pd.DataFrame(df_completo_ajustado)

# ==========================================
# 4. GRÁFICO DE RESULTADOS
# ==========================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})

ax1.plot(df_plot["Eje_X"], df_plot["Demanda_Acum"], label="Demanda Acumulada", color="#ff7f0e", linewidth=2.5)
ax1.plot(df_plot["Eje_X"], df_plot["Prod_Acum"], label="Producción Acumulada + Stock", color="#2ca02c", linewidth=2.5)
ax1.set_title(f"OPM GUADIX - Planificación Semanal Optimizada (Piso {objetivo_horas}h)", fontsize=13, fontweight="bold")
ax1.set_ylabel("Picks Acumulados")
ax1.grid(True, linestyle=":", alpha=0.6)

# Marcadores de FIN DE PRODUCCIÓN (Naranjas)
for p in info_paradas:
    idx = p["idx_global"]
    picks = p["picks_acum"]
    texto = p["texto_etiqueta"]
    ax1.axvline(x=idx, color="#d95f02", linestyle="-.", linewidth=1.5, alpha=0.8)
    ax2.axvline(x=idx, color="#d95f02", linestyle="-.", linewidth=1.5, alpha=0.8)
    ax1.plot(idx, picks, 'o', color="#d95f02", markersize=5)
    ax1.annotate(texto, (idx, picks), textcoords="offset points", xytext=(0, 12),
                 ha='center', fontsize=7.5, fontweight='bold', color="#d95f02",
                 bbox=dict(boxstyle="round,pad=0.3", fc="#ffefe5", ec="#d95f02", lw=1.2))

# Marcadores de INICIO DE PRODUCCIÓN (Gama de Verdes)
for a in info_arranques:
    idx = a["idx_global"]
    picks = a["picks_acum"]
    texto = a["texto_etiqueta"]
    ax1.axvline(x=idx, color="#238b45", linestyle="--", linewidth=1.5, alpha=0.8)
    ax2.axvline(x=idx, color="#238b45", linestyle="--", linewidth=1.5, alpha=0.8)
    ax1.plot(idx, picks, 'o', color="#238b45", markersize=5)
    ax1.annotate(texto, (idx, picks), textcoords="offset points", xytext=(0, -22),
                 ha='center', fontsize=7.5, fontweight='bold', color="#1b5e20",
                 bbox=dict(boxstyle="round,pad=0.3", fc="#e8f5e9", ec="#238b45", lw=1.2))

ax2.plot(df_plot["Eje_X"], df_plot["Adelanto_Horas"], label="Horas de Adelanto en Muelle", color="#1f77b4", linewidth=2)
ax2.axhline(y=objetivo_horas, color="#d62728", linestyle="--", linewidth=1.8, label=f"Límite Inviolable Mínimo ({objetivo_horas}h)")
ax2.axhline(y=adelanto_max_estandar, color="#2ca02c", linestyle=":", linewidth=1.5, label=f"Techo Máximo Configurado ({adelanto_max_estandar}h)")

adelanto = df_plot["Adelanto_Horas"].values
for i in range(1, len(adelanto) - 1):
    if adelanto[i] > adelanto[i-1] and adelanto[i] >= adelanto[i+1]:
        ax2.plot(i, adelanto[i], 'ro', markersize=3.5)
        ax2.annotate(f"{adelanto[i]:.1f}h", (i, adelanto[i]), textcoords="offset points", xytext=(0, 5),
                     ha='center', fontsize=7.5, fontweight='bold', color='#1f77b4',
                     bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7))
    if adelanto[i] < adelanto[i-1] and adelanto[i] <= adelanto[i+1]:
        color_val = '#2ca02c' if adelanto[i] >= objetivo_horas else '#d62728'
        ax2.plot(i, adelanto[i], 'o', color=color_val, markersize=3.5)
        ax2.annotate(f"{adelanto[i]:.1f}h", (i, adelanto[i]), textcoords="offset points", xytext=(0, -12),
                     ha='center', fontsize=7.5, fontweight='bold', color=color_val,
                     bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7))

ax2.set_ylabel("Horas de Colchón")
ax2.set_xlabel("Horas del Día")
ax2.set_ylim(2.5, max(adelanto) + 2)
ax2.grid(True, linestyle=":", alpha=0.6)

ax1.legend(loc="upper left")
ax2.legend(loc="upper left")

# ==========================================
# 5. ETIQUETAS DE DÍAS DENTRO DE LA GRÁFICA SUPERIOR (AX1)
# ==========================================
ticks_horas_indices = []
for i_dia, dia in enumerate(dias_semana):
    base = i_dia * 24
    
    if i_dia > 0:
        ax1.axvline(x=base, color="#333333", linestyle="-", alpha=0.4, linewidth=1.5)
        ax2.axvline(x=base, color="#333333", linestyle="-", alpha=0.4, linewidth=1.5)
    
    ax1.text(base + 12, 3500, dia.upper(), ha='center', va='bottom', fontsize=10, fontweight='bold', color='#1f3b4d',
             bbox=dict(boxstyle="round,pad=0.4", fc="#e1f5fe", ec="#0288d1", lw=1.2, alpha=0.9))
    
    ticks_horas_indices.extend([base + 0, base + 6, base + 14, base + 20])

ticks_horas_indices = sorted(list(set(ticks_horas_indices)))
labels_limpias = [horas_24[i % 24] for i in ticks_horas_indices]

plt.xticks(ticks=ticks_horas_indices, labels=labels_limpias, rotation=0, fontsize=8, fontweight="bold")
plt.tight_layout()

# ==========================================
# 6. RENDERIZADO EN STREAMLIT
# ==========================================
st.pyplot(fig)
