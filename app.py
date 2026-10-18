import json
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ==========================================
# 0. PERSISTENCIA DE CONFIGURACIÓN (JSON)
# ==========================================
CONFIG_FILE = "config_opm.json"

def cargar_configuracion():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def guardar_configuracion(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.sidebar.error(f"Error al guardar configuración: {e}")

config_guardada = cargar_configuracion()

# ==========================================
# 0. CONFIGURACIÓN DE PÁGINA STREAMLIT
# ==========================================
st.set_page_config(page_title="OPM - Planificación Semanal", layout="wide")
st.title("🏭 OPM: Planificación semanal")

# ==========================================
# 1. PARÁMETROS CONFIGURABLES (VÍA SIDEBAR)
# ==========================================
st.sidebar.header("⚙ Parámetros del Sistema")

val_capacidad = config_guardada.get("CAPACIDAD_PLAYA", 40000)
CAPACIDAD_PLAYA = st.sidebar.slider(
    "Capacidad Máxima de la Playa (Picks)",
    min_value=10000,
    max_value=100000,
    value=val_capacidad,
    step=5000,
)

val_vel = config_guardada.get("vel_maquina", 5000)
vel_maquina = st.sidebar.number_input(
    "Velocidad de Máquina (Picks/hora)",
    min_value=1000,
    max_value=20000,
    value=val_vel,
    step=500,
)

dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

horas_arranque_guardadas = config_guardada.get("horas_arranque_por_dia", {})
with st.sidebar.expander("⏰ Hora de Arranque por Día"):
    horas_arranque_por_dia = {}
    for dia in dias_semana:
        val_arranque = horas_arranque_guardadas.get(dia, 4)
        horas_arranque_por_dia[dia] = st.slider(
            f"{dia}",
            min_value=0,
            max_value=12,
            value=val_arranque,
            step=1,
            key=f"arranque_{dia}"
        )

demanda_guardada = config_guardada.get("demanda_servicio_por_dia", {
    "Lunes": 70000, "Martes": 50000, "Miércoles": 75000, 
    "Jueves": 80000, "Viernes": 89000, "Sábado": 60000
})

with st.sidebar.expander("📅 Demanda Diaria de Servicio (Picks)"):
    demanda_servicio_por_dia = {}
    for dia in dias_semana:
        demanda_servicio_por_dia[dia] = st.number_input(
            dia, 
            min_value=10000, 
            max_value=200000, 
            value=int(demanda_guardada.get(dia, 70000)), 
            step=5000,
            key=f"demanda_{dia}"
        )

with st.sidebar.expander("🕒 Perfil Horario de Tiendas (24h)"):
    default_tiendas = [1, 3, 3, 3, 3, 0, 0, 0, 0, 8, 19, 9, 9, 2, 2, 0, 3, 7, 12, 4, 1, 0, 0, 0]
    tiendas_guardadas = config_guardada.get("tiendas_por_hora", default_tiendas)
    tiendas_por_hora = []
    for h in range(24):
        val_t = tiendas_guardadas[h] if h < len(tiendas_guardadas) else default_tiendas[h]
        val = st.number_input(f"Hora {h:02d}:00", min_value=0, max_value=100, value=int(val_t), key=f"tienda_h_{h}")
        tiendas_por_hora.append(val)

# Control de incidencias reales para CADA DÍA (Cierre de día)
with st.sidebar.expander("🛠️ Control de Cierres Reales (23:00 por Día)"):
    corregir_cierres_guardado = config_guardada.get("corregir_cierres", {})
    stocks_reales_guardados = config_guardada.get("stocks_reales_cierre", {})
    
    corregir_cierres_por_dia = {}
    stocks_reales_cierre = {}
    
    for dia in dias_semana:
        st.markdown(f"**{dia}**")
        chk_val = corregir_cierres_guardado.get(dia, False)
        stock_val = stocks_reales_guardados.get(dia, 30000)
        
        corregir_cierres_por_dia[dia] = st.checkbox(f"Ajustar cierre {dia}", value=chk_val, key=f"chk_cierre_{dia}")
        stocks_reales_cierre[dia] = st.number_input(
            f"Stock real 23:00 ({dia})",
            min_value=0,
            max_value=200000,
            value=int(stock_val),
            step=1000,
            key=f"num_stock_cierre_{dia}"
        )
        st.markdown("---")

nueva_config = {
    "CAPACIDAD_PLAYA": CAPACIDAD_PLAYA,
    "vel_maquina": vel_maquina,
    "horas_arranque_por_dia": horas_arranque_por_dia,
    "demanda_servicio_por_dia": demanda_servicio_por_dia,
    "tiendas_por_hora": tiendas_por_hora,
    "corregir_cierres": corregir_cierres_por_dia,
    "stocks_reales_cierre": stocks_reales_cierre
}
guardar_configuracion(nueva_config)

horas_24 = [f"{h:02d}:00" for h in range(24)]

# Determinación dinámica de la ÚLTIMA HORA DE CARGA DEL DÍA (donde demanda > 0)
horas_con_carga = [h for h, val in enumerate(tiendas_por_hora) if val > 0]
ultima_hora_carga = max(horas_con_carga) if horas_con_carga else 23

# ==========================================
# 2. PREPARACIÓN DE DEMANDA Y TIENDAS HORA A HORA (144h)
# ==========================================
demanda_h_144 = []
tiendas_h_144 = []
suma_t = sum(tiendas_por_hora)

for dia in dias_semana:
    dem_total = demanda_servicio_por_dia[dia]
    factor = dem_total / suma_t if suma_t > 0 else 0
    
    dem_h = [round(t * factor) for t in tiendas_por_hora]
    demanda_h_144.extend(dem_h)
    tiendas_h_144.extend(tiendas_por_hora)

# ==========================================
# 3. MOTOR DE PRODUCCIÓN AUTÓNOMO
# ==========================================
stock_actual = float(CAPACIDAD_PLAYA)  
demanda_acumulada = 0
produccion_acumulada = float(CAPACIDAD_PLAYA)

demanda_acum_144 = []
prod_acum_144 = []
stock_playa_144 = []
adelanto_horas_144 = []
produccion_efectiva_144 = []
ultima_tienda_preparada_144 = []
tiendas_en_playa_144 = []
cierres_ajustados_144 = [False] * 144

maquina_encendida = False
ultimo_texto_tienda = "Lun 00:00"

for t in range(144):
    dia_idx = t // 24
    hora_del_dia = t % 24
    dia_actual = dias_semana[dia_idx]
    hora_inicio_permitida_dia = horas_arranque_por_dia[dia_actual]

    # Demanda total del DÍA SIGUIENTE
    if dia_idx + 1 < len(dias_semana):
        dia_siguiente = dias_semana[dia_idx + 1]
        demanda_dia_siguiente = demanda_servicio_por_dia[dia_siguiente]
    else:
        demanda_dia_siguiente = demanda_servicio_por_dia[dia_actual]

    dem_h = demanda_h_144[t]
    demanda_acumulada += dem_h
    demanda_acum_144.append(demanda_acumulada)
    
    stock_actual -= dem_h
    if stock_actual < 0:
        stock_actual = 0  

    # A partir de la última hora de carga del día, el stock es íntegramente para el día siguiente
    es_post_ultima_carga = hora_del_dia >= ultima_hora_carga

    if hora_del_dia == hora_inicio_permitida_dia:
        if stock_actual < CAPACIDAD_PLAYA and not (es_post_ultima_carga and stock_actual >= demanda_dia_siguiente):
            maquina_encendida = True
        else:
            maquina_encendida = False
    elif stock_actual >= CAPACIDAD_PLAYA or (es_post_ultima_carga and stock_actual >= demanda_dia_siguiente):
        maquina_encendida = False

    prod_h = 0
    if maquina_encendida and stock_actual < CAPACIDAD_PLAYA and hora_del_dia >= hora_inicio_permitida_dia:
        espacio_libre = CAPACIDAD_PLAYA - stock_actual
        
        if es_post_ultima_carga:
            margen_dia_siguiente = demanda_dia_siguiente - stock_actual
            limite_produccion = max(0.0, min(espacio_libre, margen_dia_siguiente))
        else:
            limite_produccion = espacio_libre
            
        prod_h = min(vel_maquina, limite_produccion)
        stock_actual += prod_h
        
        if stock_actual >= CAPACIDAD_PLAYA or (es_post_ultima_carga and stock_actual >= demanda_dia_siguiente):
            maquina_encendida = False

    produccion_acumulada += prod_h

    # INYECCIÓN DE STOCK REAL A LAS 23:00 PARA CUALQUIER DÍA CONFIGURADO
    if hora_del_dia == 23 and corregir_cierres_por_dia.get(dia_actual, False):
        stock_real_objetivo = float(stocks_reales_cierre.get(dia_actual, stock_actual))
        stock_actual = stock_real_objetivo
        produccion_acumulada = stock_actual + demanda_acumulada
        cierres_ajustados_144[t] = True

    prod_acum_144.append(produccion_acumulada)
    produccion_efectiva_144.append(prod_h)
    stock_playa_144.append(stock_actual)
    
    # Redondeo sin decimales para las horas de adelanto
    horas_adelanto = int(round(stock_actual / vel_maquina)) if vel_maquina > 0 else 0
    adelanto_horas_144.append(horas_adelanto)

    # 1. Cálculo de la última tienda horaria alcanzada (FIFO Proyectado)
    if stock_actual > 0:
        stock_temp = stock_actual
        cursor_sim = t
        while cursor_sim < 143 and stock_temp > 0:
            cursor_sim += 1
            dem_futura = demanda_h_144[cursor_sim]
            if stock_temp >= dem_futura:
                stock_temp -= dem_futura
            else:
                break
        d_fin = dias_semana[cursor_sim // 24][:3]
        h_fin_str = horas_24[cursor_sim % 24]
        ultimo_texto_tienda = f"{d_fin} {h_fin_str}"
    
    ultima_tienda_preparada_144.append(ultimo_texto_tienda)

    # 2. Cálculo directo de tiendas en playa basado en el stock actual de picks
    dem_dia_actual = demanda_servicio_por_dia[dia_actual]
    tiendas_dia_total = sum(tiendas_por_hora)
    picks_por_tienda_dia = dem_dia_actual / tiendas_dia_total if tiendas_dia_total > 0 else 1000
    
    if stock_actual > 0 and picks_por_tienda_dia > 0:
        tiendas_en_playa = round(stock_actual / picks_por_tienda_dia)
        tiendas_en_playa_144.append(int(tiendas_en_playa))
    else:
        tiendas_en_playa_144.append(0)

# ==========================================
# 4. CONSTRUCCIÓN DE DATOS E HITOS
# ==========================================
df_completo_ajustado = []
hitos_produccion = []
hitos_ajustes_reales = []

for dia_idx, dia in enumerate(dias_semana):
    p_h_dia = produccion_efectiva_144[dia_idx * 24 : (dia_idx + 1) * 24]
    dem_h_dia = demanda_h_144[dia_idx * 24 : (dia_idx + 1) * 24]
    
    dem_acum_dia = demanda_acum_144[dia_idx * 24 : (dia_idx + 1) * 24]
    prod_acum_dia = prod_acum_144[dia_idx * 24 : (dia_idx + 1) * 24]
    stock_playa_dia = stock_playa_144[dia_idx * 24 : (dia_idx + 1) * 24]
    adelanto_dia = adelanto_horas_144[dia_idx * 24 : (dia_idx + 1) * 24]
    ult_tienda_dia = ultima_tienda_preparada_144[dia_idx * 24 : (dia_idx + 1) * 24]
    tiendas_playa_dia = tiendas_en_playa_144[dia_idx * 24 : (dia_idx + 1) * 24]
    ajustes_dia = cierres_ajustados_144[dia_idx * 24 : (dia_idx + 1) * 24]

    horas_activas = [i for i, p in enumerate(p_h_dia) if p > 0]
    if horas_activas:
        turnos = []
        inicio_actual = horas_activas[0]
        prev = horas_activas[0]

        for h in horas_activas[1:]:
            if h == prev + 1:
                prev = h
            else:
                turnos.append((inicio_actual, prev))
                inicio_actual = h
                prev = h
        turnos.append((inicio_actual, prev))

        for h_ini, h_fin in turnos:
            stock_ini_val = stock_playa_dia[h_ini]
            hitos_produccion.append({
                "tipo": "INICIO",
                "eje_x": f"{dia[:3]} {horas_24[h_ini]}",
                "y_val": prod_acum_dia[h_ini],
                "texto": f"INICIO {horas_24[h_ini]}<br>({stock_ini_val:,.0f} p.)",
            })
            if h_fin == 23:
                etiqueta_fin = "24:00"
                eje_x_fin = f"{dia[:3]} 23:00"
                y_val_fin = prod_acum_dia[23]
                stock_fin_val = stock_playa_dia[23]
            else:
                etiqueta_fin = horas_24[h_fin + 1]
                eje_x_fin = f"{dia[:3]} {horas_24[h_fin + 1]}"
                y_val_fin = prod_acum_dia[h_fin + 1]
                stock_fin_val = stock_playa_dia[h_fin + 1]

            hitos_produccion.append({
                "tipo": "FIN",
                "eje_x": eje_x_fin,
                "y_val": y_val_fin,
                "texto": f"FIN {etiqueta_fin}<br>({stock_fin_val:,.0f} p.)",
            })

    for h_idx in range(24):
        stock_actual_h = stock_playa_dia[h_idx]
        is_ajustado = ajustes_dia[h_idx]

        if is_ajustado:
            hitos_ajustes
