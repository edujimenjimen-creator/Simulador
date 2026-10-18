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

# Selección de Hora de Arranque de 00:00 a 24:00 por cada día
opciones_horas = [f"{h:02d}:00" for h in range(25)]

horas_arranque_guardadas = config_guardada.get("horas_arranque_por_dia", {})
with st.sidebar.expander("⏰ Hora de Arranque por Día (00:00 - 24:00)"):
    horas_arranque_por_dia = {}
    for dia in dias_semana:
        val_arranque_int = horas_arranque_guardadas.get(dia, 4)
        val_arranque_str = f"{val_arranque_int:02d}:00"
        if val_arranque_str not in opciones_horas:
            val_arranque_str = "04:00"

        hora_sel_str = st.selectbox(
            f"{dia}",
            options=opciones_horas,
            index=opciones_horas.index(val_arranque_str),
            key=f"arranque_{dia}"
        )
        horas_arranque_por_dia[dia] = int(hora_sel_str.split(":")[0])

demanda_guardada = config_guardada.get("demanda_servicio_por_dia", {
    "Lunes": 70000, "Martes": 50000, "Miércoles": 75000, 
    "Jueves": 80000, "Viernes": 89000, "Sábado": 6
