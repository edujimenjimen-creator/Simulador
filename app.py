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
    "Jueves": 50694, "Viernes": 64604, "Sábado": 54360,
    "Lunes_Siguiente": 41347
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
    # Entrada para el Lunes de la siguiente semana
    demanda_servicio_por_dia["Lunes_Siguiente"] = st.number_input(
        "Lunes (Siguiente semana)",
        min_value=10000,
        max_value=200000,
        value=int(demanda_guardada.get("Lunes_Siguiente", demanda_servicio_por_dia["Lunes"])),
        step=1000,
        key="demanda_Lunes_Siguiente"
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

    # --- REGLA DE VOLCADO DE PEDIDOS (INCLUYENDO LUNES SIGUIENTE EL SÁBADO) ---
    demanda_volcada_hasta_t = 0
    for d_i in range(dia_idx + 1):
        demanda_volcada_hasta_t += demanda_servicio_por_dia[dias_semana[d_i]]
    
    # Si es >= 04:00h
