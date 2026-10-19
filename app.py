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

val_capacidad = config_guardada.get("CAPACIDAD_PLAYA", 45000)
CAPACIDAD_PLAYA = st.sidebar.slider(
    "Capacidad Máxima de la Playa (Picks)",
    min_value=10000,
    max_value=100000,
    value=val_capacidad,
    step=5000,
)

val_vel = config_guardada.get("vel_maquina", 4500)
vel_maquina = st.sidebar.number_input(
    "Velocidad de Máquina (Picks/hora)",
    min_value=1000,
    max_value=20000,
    value=val_vel,
    step=500,
)

dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

horas_arranque_guardadas = config_guardada.get("horas_arranque_por_dia", {})
horas_fin_guardadas = config_guardada.get("horas_fin_por_dia", {})

with st.sidebar.expander("⏰ Horarios de Inicio y Fin por Día"):
    horas_arranque_por_dia = {}
    horas_fin_por_dia = {}
    
    for dia in dias_semana:
        st.markdown(f"**{dia}**")
        val_arranque = horas_arranque_guardadas.get(dia, 18 if dia == "Lunes" else 6)
        val_fin = horas_fin_guardadas.get(dia, 24)

        st.markdown("<span style='color: #2e7d32; font-weight: bold;'>🟢 Hora Inicio</span>", unsafe_allow_html=True)
        horas_arranque_por_dia[dia] = st.slider(
            f"Inicio {dia}",
            min_value=0,
            max_value=24,
            value=int(val_arranque),
            step=1,
            key=f"arranque_{dia}",
            label_visibility="collapsed"
        )

        st.markdown("<span style='color: #c62828; font-weight: bold;'>🔴 Hora Fin</span>", unsafe_allow_html=True)
        horas_fin_por_dia[dia] = st.slider(
            f"Fin {dia}",
            min_value=0,
            max_value=24,
            value=int(val_fin),
            step=1,
            key=f"fin_{dia}",
            label_visibility="collapsed"
        )
        st.markdown("---")

demanda_guardada = config_guardada.get("demanda_servicio_por_dia", {
    "Lunes": 41347, "Martes": 37881, "Miércoles": 37694, 
    "Jueves": 50694, "Viernes": 64604, "Sábado": 54360
})

with st.sidebar.expander("📅 Demanda Diaria de Servicio (Picks)"):
    demanda_servicio_por_dia = {}
    for dia in dias_semana:
        demanda_servicio_por_dia[dia] = st.number_input(
            dia, 
            min_value=10000, 
            max_value=200000, 
            value=int(demanda_guardada.get(dia, 40000)), 
            step=1000,
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

with st.sidebar.expander("🛠️ Control de Stocks Reales (Inicio / Cierres)"):
    stock_inicio_lunes_guardado = config_guardada.get("stock_inicio_lunes", 40552)
    stock_inicio_lunes = st.number_input(
        "Stock inicial real Lunes (00:00)",
        min_value=0,
        max_value=200000,
        value=int(stock_inicio_lunes_guardado),
        step=1000,
        key="num_stock_inicio_lunes"
    )
    st.markdown("---")

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
    "horas_fin_por_dia": horas_fin_por_dia,
    "demanda_servicio_por_dia": demanda_servicio_por_dia,
    "tiendas_por_hora": tiendas_por_hora,
    "stock_inicio_lunes": stock_inicio_lunes,
    "corregir_cierres": corregir_cierres_por_dia,
    "stocks_reales_cierre": stocks_reales_cierre
}
guardar_configuracion(nueva_config)

horas_24 = [f"{h:02d}:00" for h in range(24)]

if sum(tiendas_por_hora) == 0:
    st.error("⚠ El perfil horario de tiendas no puede sumar cero.")
    st.stop()

# ==========================================
# 2. PREPARACIÓN DE DEMANDA Y TIENDAS HORA A HORA (144h)
# ==========================================
demanda_h_144 = []
tiendas_h_144 = []
for dia in dias_semana:
    dem_total = demanda_servicio_por_dia[dia]
    suma_t = sum(tiendas_por_hora)
    factor = dem_total / suma_t if suma_t > 0 else 0
    
    dem_h = [round(t * factor) for t in tiendas_por_hora]
    demanda_h_144.extend(dem_h)
    tiendas_h_144.extend(tiendas_por_hora)

# ==========================================
# 3. MOTOR DE PRODUCCIÓN AUTÓNOMO CON REGLA DE VOLCADO
# ==========================================
stock_actual = float(stock_inicio_lunes)  
demanda_acumulada = 0
produccion_acumulada = float(stock_inicio_lunes)

demanda_acum_144 = []
prod_acum_144 = []
stock_playa_144 = []
adelanto_horas_144 = []
produccion_efectiva_144 = []
ultima_tienda_preparada_144 = []
tiendas_en_playa_144 = []
cierres_ajustados_144 = [False] * 144
motivos_estado_144 = []

ultimo_texto_tienda = "Lun 00:00"

for t in range(144):
    dia_idx = t // 24
    hora_del_dia = t % 24
    dia_actual = dias_semana[dia_idx]
    
    hora_inicio_permitida_dia = horas_arranque_por_dia[dia_actual]
    hora_fin_permitida_dia = horas_fin_por_dia[dia_actual]

    dem_h = demanda_h_144[t]
    demanda_acumulada += dem_h
    demanda_acum_144.append(demanda_acumulada)
    
    stock_actual -= dem_h
    if stock_actual < 0:
        stock_actual = 0  

    # --- REGLA DE VOLCADO DE PEDIDOS ---
    demanda_volcada_hasta_t = 0
    for d_i in range(dia_idx + 1):
        demanda_volcada_hasta_t += demanda_servicio_por_dia[dias_semana[d_i]]
    
    if hora_del_dia >= 4 and (dia_idx + 1) < len(dias_semana):
        demanda_volcada_hasta_t += demanda_servicio_por_dia[dias_semana[dia_idx + 1]]

    esta_en_horario = hora_inicio_permitida_dia <= hora_del_dia < hora_fin_permitida_dia

    prod_h = 0
    motivo = "PARADA"
    
    if esta_en_horario:
        espacio_libre_playa = CAPACIDAD_PLAYA - stock_actual
        
        if espacio_libre_playa <= 0:
            motivo = "PLAYA LLENA"
        elif dia_actual == "Sábado":
            # El sábado no tiene límite de volcado: solo le frena si la playa se llena
            prod_h = min(vel_maquina, espacio_libre_playa)
            stock_actual += prod_h
            motivo = "PRODUCIENDO" if prod_h > 0 else "PLAYA LLENA"
        else:
            pedidos_pendientes_fabricar = demanda_volcada_hasta_t - produccion_acumulada
            if pedidos_pendientes_fabricar <= 0:
                motivo = "PENDIENTE VOLCADO (SIN PEDIDOS)"
            else:
                prod_h = min(vel_maquina, espacio_libre_playa, max(0.0, pedidos_pendientes_fabricar))
                stock_actual += prod_h
                motivo = "PRODUCIENDO" if prod_h > 0 else "SIN TRABAJO"
    else:
        motivo = "FUERA DE HORARIO"

    produccion_acumulada += prod_h

    if hora_del_dia == 23 and corregir_cierres_por_dia.get(dia_actual, False):
        stock_real_objetivo = float(stocks_reales_cierre.get(dia_actual, stock_actual))
        stock_actual = stock_real_objetivo
        produccion_acumulada = stock_actual + demanda_acumulada
        cierres_ajustados_144[t] = True

    prod_acum_144.append(produccion_acumulada)
    produccion_efectiva_144.append(prod_h)
    stock_playa_144.append(stock_actual)
    motivos_estado_144.append(motivo)
    
    horas_adelanto = int(round(stock_actual / vel_maquina)) if vel_maquina > 0 else 0
    adelanto_horas_144.append(horas_adelanto)

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

    dem_dia_actual = demanda_servicio_por_dia[dia_actual]
    tiendas_dia_total = sum(tiendas_por_hora)
    picks_por_tienda_dia = dem_dia_actual / tiendas_dia_total if tiendas_dia_total > 0 else 1000
    
    if stock_actual > 0 and picks_por_tienda_dia > 0:
        tiendas_en_playa = round(stock_actual / picks_por_tienda_dia)
        tiendas_en_playa = min(tiendas_en_playa, tiendas_dia_total)
        tiendas_en_playa_144.append(int(tiendas_en_playa))
    else:
        tiendas_en_playa_144.append(0)

# ==========================================
# 4. CONSTRUCCIÓN DE DATOS E HIT
