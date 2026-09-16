import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Configuración de la página
st.set_page_config(page_title="Simulador de Producción", page_icon="⚙️", layout="wide")

st.title("⚙️ Simulador de Línea de Producción")
st.write("Bienvenido al entorno de simulación industrial. Utiliza los controles laterales para ajustar los parámetros de la planta.")

# Panel lateral de controles
st.sidebar.header("Parámetros de Simulación")
num_lineas = st.sidebar.slider("Número de líneas activas", 1, 10, 4)
velocidad_base = st.sidebar.slider("Velocidad objetivo (uds/min)", 50, 500, 120)
tasa_fallos = st.sidebar.slider("Tasa de defectos estimada (%)", 0.0, 10.0, 1.5)

# Generación de datos simulados
np.random.seed(42)
horas = [f"{h:02d}:00" for h in range(8, 17)]
datos_produccion = []

for hora in horas:
    for linea in range(1, num_lineas + 1):
        produccion_real = int(np.random.normal(velocidad_base * 60, 150))
        defectos = int(produccion_real * (np.random.normal(tasa_fallos, 0.5) / 100))
        defectos = max(0, defectos)
        eficiencia = max(0, min(100, ((produccion_real - defectos) / (velocidad_base * 60)) * 100))
        
        datos_produccion.append({
            "Hora": hora,
            "Línea": f"Línea {linea}",
            "Producidas": max(0, produccion_real),
            "Defectuosas": defectos,
            "Eficiencia (%)": round(eficiencia, 2)
        })

df = pd.DataFrame(datos_produccion)

# Métricas principales arriba
col1, col2, col3 = st.columns(3)
col1.metric("Producción Total", f"{df['Producidas'].sum():,} uds")
col2.metric("Total Defectuosas", f"{df['Defectuosas'].sum():,} uds")
col3.metric("Eficiencia Media", f"{df['Eficiencia (%)'].mean():.1f}%")

st.divider()

# Gráfico de evolución con Matplotlib
st.subheader("📊 Evolución de la Producción por Hora")
fig, ax = plt.subplots(figsize=(10, 4))

for linea in df["Línea"].unique():
    subset = df[df["Línea"] == linea]
    ax.plot(subset["Hora"], subset["Producidas"], marker='o', label=linea)

ax.set_xlabel("Hora del Turno")
ax.set_ylabel("Unidades Producidas")
ax.legend()
ax.grid(True, linestyle="--", alpha=0.6)

st.pyplot(fig)

# Tabla de datos detallados
st.subheader("📋 Registro Detallado")
st.dataframe(df, use_container_width=True)
