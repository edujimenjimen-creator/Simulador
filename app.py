import streamlit as st
import pandas as pd
import numpy as np

# Configuración de la página
st.set_page_config(
    page_title="OPM Guadix - Planificación Proactiva",
    page_icon="🏭",
    layout="wide"
)

st.title("🏭 OPM Guadix: Panel de Planificación y Simulación Proactiva")
st.markdown("Gestión inteligente de producción, buffers de muelle y blindaje de stock logístico.")

# ==========================================
# 🎛️ PANEL DE CONTROL Y PARÁMETROS CONFIGURABLES
# ==========================================
st.sidebar.header("⚙️ Configuración del Sistema")

st.sidebar.subheader("🚚 1. Logística y Muelles")
capacidad_buffer_muelles = st.sidebar.number_init if hasattr(st.sidebar, 'number_init') else st.sidebar.number_input(
    "Capacidad Máxima Buffer Muelles (palets)", 
    min_value=50, max_value=2000, value=500, step=50,
    help="Límite físico de almacenamiento temporal en la zona de expedición/muelles."
)
ratio_carga_camion = st.sidebar.number_input(
    "Capacidad por Camión / Tráiler (palets)",
    min_value=10, max_value=66, value=33, step=1
)

st.sidebar.subheader("⚡ 2. Línea de Producción")
tasa_produccion_hora = st.sidebar.number_input(
    "Velocidad de Producción (palets/hora)",
    min_value=10, max_value=500, value=120, step=10
)
coste_arranque = st.sidebar.number_input(
    "Coste / Inercia de Arranque de Línea (€)",
    min_value=0.0, max_value=5000.0, value=350.0, step=50.0,
    help="Penalización económica o desgaste operativo al encender la línea."
)
coste_parada = st.sidebar.number_input(
    "Coste / Inercia de Parada de Línea (€)",
    min_value=0.0, max_value=2000.0, value=100.0, step=25.0
)
coste_mantenimiento_stock = st.sidebar.number_input(
    "Coste de Almacenamiento (€ / palet·hora)",
    min_value=0.0, max_value=10.0, value=0.5, step=0.1
)

st.sidebar.subheader("🛡️ 3. Blindaje de Stock (Fin de Semana)")
stock_min_lunes = st.sidebar.number_input(
    "Stock Objetivo Mínimo para el Lunes (palets)",
    min_value=0, max_value=3000, value=800, step=50,
    help="Garantiza que el lunes amanezca con este colchón cubierto tras el cierre dominical."
)
factor_demanda_pico = st.sidebar.slider(
    "Multiplicador de Demanda en Horas Punta",
    min_value=1.0, max_value=2.5, value=1.3, step=0.1
)

# ==========================================
# 📊 SIMULACIÓN Y MOTOR PROACTIVO
# ==========================================
# Generación de turnos y horas de simulación (Ejemplo: Ciclo semanal de Lunes a Domingo)
dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
horas_dia = 24

# Creamos una traza horaria de simulación base
np.random.seed(42)
horas_total = len(dias) * horas_dia
df_simulacion = pd.DataFrame({
    'Hora_Global': range(horas_total),
    'Dia': [dias[i // horas_dia] for i in range(horas_total)],
    'Hora_Dia': [i % horas_dia for i in range(horas_total)]
})

# Simulación de demanda horaria por tiendas (patrón logístico real con picos diurnos)
def calcular_demanda(row):
    h = row['Hora_Dia']
    dia = row['Dia']
    # Menos demanda de madrugada, pico en horas centrales de distribución
    base = 20 + 40 * np.sin(np.pi * (h - 6) / 12) if 6 <= h <= 22 else 5
    if dia in ["Sábado", "Domingo"]:
        base *= 0.4 # Menor actividad comercial los fines de semana
    if 8 <= h <= 12:
        base *= factor_demanda_pico
    return max(0, int(base))

df_simulacion['Demanda_Tiendas'] = df_simulacion.apply(calcular_demanda, axis=1)

# Lógica proactiva de producción y buffers
stock_muelles = 200 # Stock inicial en muelles
produccion_activa = []
stock_buffer_historico = []
costes_acumulados = 0

estado_linea = 0 # 0: Apagada, 1: Encendida

for idx, row in df_simulacion.iterrows():
    demanda = row['Demanda_Tiendas']
    dia = row['Dia']
    
    # Regla proactiva: Si estamos a viernes/sábado y el stock baja del objetivo del lunes, forzamos producción
    necesidad_blindaje_lunes = stock_min_lunes if dia in ["Viernes", "Sábado", "Domingo"] else (stock_min_lunes * 0.5)
    
    # Decisión de encendido de línea
    if stock_muelles < necesidad_blindaje_lunes or demanda > (tasa_produccion_hora * 0.5):
        nuevo_estado = 1
    else:
        nuevo_estado = 0
        
    # Costes de transición
    if nuevo_estado == 1 and estado_linea == 0:
        costes_acumulados += coste_arranque
    elif nuevo_estado == 0 and estado_linea == 1:
        costes_acumulados += coste_parada
        
    estado_linea = nuevo_estado
    produccion_hora = tasa_produccion_hora if estado_linea == 1 else 0
    
    # Actualización del buffer de muelles
    stock_muelles = stock_muelles + produccion_hora - demanda
    
    # Control de límites físicos del muelle (saturación o rotura)
    if stock_muelles > capacidad_buffer_muelles:
        # Excedente satura el muelle, frenamos producción teórica o genera alerta
        stock_muelles = capacidad_buffer_muelles
    elif stock_muelles < 0:
        stock_muelles = 0 # Rotura de stock momentánea
        
    costes_acumulados += stock_muelles * coste_mantenimiento_stock
    
    produccion_activa.append(produccion_hora)
    stock_buffer_historico.append(stock_muelles)

df_simulacion['Produccion'] = produccion_activa
df_simulacion['Stock_Muelles'] = stock_buffer_historico

# ==========================================
# 📈 VISUALIZACIÓN EN STREAMLIT
# ==========================================
col1, col2, col3 = st.columns(3)
col1.metric("📦 Stock Final en Muelles", f"{int(df_simulacion['Stock_Muelles'].iloc[-1])} palets")
col2.metric("⚡ Costes Operativos Totales", f"{costes_acumulados:,.2f} €")
col3.metric("🛡️ Objetivo Lunes Configurado", f"{stock_min_lunes} palets")

st.subheader("📈 Evolución Temporal: Producción vs Demanda y Estado del Buffer")
st.line_chart(df_simulacion.set_index('Hora_Global')[['Demanda_Tiendas', 'Produccion', 'Stock_Muelles']])

with st.expander("🔍 Ver datos detallados de la simulación horaria"):
    st.dataframe(df_simulacion)
