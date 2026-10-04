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
st.title("🏭 OPM Guadix: Planificación Autónoma con Capacidad y Arranque Diario Configurable")

# ==========================================
# 1. PARÁMETROS CONFIGURABLES (VÍA SIDEBAR)
# ==========================================
st.sidebar.header("⚙ Parámetros del Sistema")

# 1. Capacidad máxima de la playa configurable en picks
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

# 2. Configuración de Hora Mínima de Arranque por Día de la Semana
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

# 3. Demanda Diaria de Servicio (Picks)
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

# 4. Perfil Horario de Tiendas
with st.sidebar.expander("🕒 Perfil Horario de Tiendas (24h)"):
    default_tiendas = [1, 3, 3, 3, 3, 0, 0, 0, 0, 8, 19, 9, 9, 2, 2, 0, 3, 7, 12, 4, 1, 0, 0, 0]
    tiendas_guardadas = config_guardada.get("tiendas_por_hora", default_tiendas)
    tiendas_por_hora = []
    for h in range(24):
        val_t = tiendas_guardadas[h] if h < len(tiendas_guardadas) else default_tiendas[h]
        val = st.number_input(f"Hora {h:02d}:00", min_value=0, max_value=100, value=int(val_t), key=f"tienda_h_{h}")
        tiendas_por_hora.append(val)

# ==========================================
# GUARDAR CONFIGURACIÓN AUTOMÁTICAMENTE
# ==========================================
nueva_config = {
    "CAPACIDAD_PLAYA": CAPACIDAD_PLAYA,
    "vel_maquina": vel_maquina,
    "horas_arranque_por_dia": horas_arranque_por_dia,
    "demanda_servicio_por_dia": demanda_servicio_por_dia,
    "tiendas_por_hora": tiendas_por_hora
}
guardar_configuracion(nueva_config)

horas_24 = [f"{h:02d}:00" for h in range(24)]

if sum(tiendas_por_hora) == 0:
    st.error("⚠️ El perfil horario de tiendas no puede sumar cero.")
    st.stop()

# ==========================================
# 2. PREPARACIÓN DE DEMANDA HORA A HORA (144h)
# ==========================================
demanda_h_144 = []
for dia in dias_semana:
    dem_total = demanda_servicio_por_dia[dia]
    factor = dem_total / sum(tiendas_por_hora)
    dem_h = [round(t * factor) for t in tiendas_por_hora]
    demanda_h_144.extend(dem_h)

# ==========================================
# 3. MOTOR DE PRODUCCIÓN AUTÓNOMO (SIN UMBRAL)
# ==========================================
stock_actual = float(CAPACIDAD_PLAYA)  
demanda_acumulada = 0
produccion_acumulada = float(CAPACIDAD_PLAYA)

demanda_acum_144 = []
prod_acum_144 = []
stock_playa_144 = []
adelanto_horas_144 = []
produccion_efectiva_144 = []

maquina_encendida = False

for t in range(144):
    dia_idx = t // 24
    hora_del_dia = t % 24
    dia_actual = dias_semana[dia_idx]
    hora_inicio_permitida_dia = horas_arranque_por_dia[dia_actual]

    dem_h = demanda_h_144[t]
    demanda_acumulada += dem_h
    demanda_acum_144.append(demanda_acumulada)
    
    stock_actual -= dem_h
    if stock_actual < 0:
        stock_actual = 0  

    if hora_del_dia == hora_inicio_permitida_dia:
        maquina_encendida = True
    elif stock_actual >= CAPACIDAD_PLAYA:
        maquina_encendida = False

    if stock_actual >= CAPACIDAD_PLAYA:
        maquina_encendida = False

    prod_h = 0
    if maquina_encendida and stock_actual < CAPACIDAD_PLAYA and hora_del_dia >= hora_inicio_permitida_dia:
        espacio_libre = CAPACIDAD_PLAYA - stock_actual
        prod_h = min(vel_maquina, espacio_libre)
        stock_actual += prod_h
        
        if stock_actual >= CAPACIDAD_PLAYA:
            maquina_encendida = False

    produccion_acumulada += prod_h
    prod_acum_144.append(produccion_acumulada)
    produccion_efectiva_144.append(prod_h)
    
    stock_playa_144.append(stock_actual)
    horas_adelanto = round(stock_actual / vel_maquina, 2) if vel_maquina > 0 else 0
    adelanto_horas_144.append(horas_adelanto)

# ==========================================
# 4. CONSTRUCCIÓN DE DATOS E HITOS DE PARO/ARRANQUE
# ==========================================
df_completo_ajustado = []
hitos_produccion = []

for dia_idx, dia in enumerate(dias_semana):
    p_h_dia = produccion_efectiva_144[dia_idx * 24 : (dia_idx + 1) * 24]
    dem_h_dia = demanda_h_144[dia_idx * 24 : (dia_idx + 1) * 24]
    
    dem_acum_dia = demanda_acum_144[dia_idx * 24 : (dia_idx + 1) * 24]
    prod_acum_dia = prod_acum_144[dia_idx * 24 : (dia_idx + 1) * 24]
    stock_playa_dia = stock_playa_144[dia_idx * 24 : (dia_idx + 1) * 24]
    adelanto_dia = adelanto_horas_144[dia_idx * 24 : (dia_idx + 1) * 24]

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
                "texto": f"INICIO {horas_24[h_ini]}<br>({stock_ini_val:,.0f} picks)",
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
                "texto": f"FIN {etiqueta_fin}<br>({stock_fin_val:,.0f} picks)",
            })

    for h_idx in range(24):
        df_completo_ajustado.append({
            "Eje_X": f"{dia[:3]} {horas_24[h_idx]}",
            "Dia": dia,
            "Hora": horas_24[h_idx],
            "Demanda_Hora": dem_h_dia[h_idx],
            "Produccion_Hora": p_h_dia[h_idx],
            "Demanda_Acum": dem_acum_dia[h_idx],
            "Prod_Acum": prod_acum_dia[h_idx],
            "Stock_Playa": stock_playa_dia[h_idx],
            "Adelanto_Horas": adelanto_dia[h_idx],
            "Estado": "PRODUCIENDO" if p_h_dia[h_idx] > 0 else "PARADA",
        })

df_plot = pd.DataFrame(df_completo_ajustado)

# ==========================================
# 5. GRÁFICO PLOTLY (3 FILAS: ACUMULADOS, STOCK, ADELANTO)
# ==========================================
fig = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.06,
    row_heights=[0.50, 0.25, 0.25],
    subplot_titles=(
        f"OPM GUADIX - Control por Hora de Arranque (Playa: {CAPACIDAD_PLAYA:,.0f} picks)",
        "Evolución del Stock Exacto en Playa (Picks)",
        "Horas de Adelanto / Autonomía en Playa (Horas)",
    ),
)

# Fila 1: Acumulados
fig.add_trace(go.Scatter(x=df_plot["Eje_X"], y=df_plot["Demanda_Acum"], name="Demanda Acumulada", line=dict(color="#ff7f0e", width=2.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=df_plot["Eje_X"], y=df_plot["Prod_Acum"], name="Producción Acumulada + Stock", line=dict(color="#2ca02c", width=2.5)), row=1, col=1)

# Fila 2: Stock en Playa
fig.add_trace(go.Scatter(x=df_plot["Eje_X"], y=df_plot["Stock_Playa"], name="Stock en Playa (Picks)", line=dict(color="#1f77b4", width=2), hoverinfo="skip"), row=2, col=1)

# Fila 3: Horas de Adelanto (Azul)
fig.add_trace(go.Scatter(x=df_plot["Eje_X"], y=df_plot["Adelanto_Horas"], name="Horas de Adelanto", line=dict(color="#1f77b4", width=2), fill='tozeroy', hoverinfo="skip"), row=3, col=1)

# Etiquetas en los picos de Stock (Fila 2)
x_vals = df_plot["Eje_X"].values
y_picks_vals = df_plot["Stock_Playa"].values
puntos_x, puntos_y, puntos_text = [], [], []
ultimo_y_etiquetado = -9999

for i in range(len(y_picks_vals)):
    val = y_picks_vals[i]
    es_pico = (0 < i < len(y_picks_vals) - 1) and (y_picks_vals[i] > y_picks_vals[i - 1]) and (y_picks_vals[i] > y_picks_vals[i + 1])
    es_valle = (0 < i < len(y_picks_vals) - 1) and (y_picks_vals[i] < y_picks_vals[i - 1]) and (y_picks_vals[i] < y_picks_vals[i + 1])
    es_extremo_global = (i == 0 or i == len(y_picks_vals) - 1)

    if (es_pico or es_valle or es_extremo_global) and abs(val - ultimo_y_etiquetado) >= (CAPACIDAD_PLAYA * 0.1):
        puntos_x.append(x_vals[i])
        puntos_y.append(val)
        puntos_text.append(f"{val:,.0f} p.")
        ultimo_y_etiquetado = val

if puntos_x:
    fig.add_trace(go.Scatter(x=puntos_x, y=puntos_y, mode="markers+text", text=puntos_text, textposition="top center", textfont=dict(size=9, color="#1f77b4"), marker=dict(size=6, color="#1f77b4"), showlegend=False), row=2, col=1)

# ==========================================
# DETECCIÓN ROBUSTA DE PICCOS EN HORAS DE ADELANTO (Fila 3)
# ==========================================
y_adelanto_vals = df_plot["Adelanto_Horas"].values
puntos_adelanto_x, puntos_adelanto_y, puntos_adelanto_text = [], [], []

for i in range(len(y_adelanto_vals)):
    val_ad = y_adelanto_vals[i]
    
    # Condición robusta de pico local (incluyendo mesetas máximas y extremos)
    is_left_lower_or_equal = (i == 0) or (val_ad >= y_adelanto_vals[i - 1])
    is_right_lower = (i == len(y_adelanto_vals) - 1) or (val_ad > y_adelanto_vals[i + 1])
    
    # Asegurar que realmente sea un punto alto respecto a su entorno inmediato general
    es_pico_robusto = False
    if i == 0:
        es_pico_robusto = val_ad > y_adelanto_vals[1]
    elif i == len(y_adelanto_vals) - 1:
        es_pico_robusto = val_ad > y_adelanto_vals[-2]
    else:
        # Es pico si es mayor o igual que el anterior y estrictamente mayor que el siguiente (o viceversa),
        # o si forma un máximo local claro.
        if (y_adelanto_vals[i] >= y_adelanto_vals[i-1]) and (y_adelanto_vals[i] >= y_adelanto_vals[i+1]) and \
           (y_adelanto_vals[i] > y_adelanto_vals[i-1] or y_adelanto_vals[i] > y_adelanto_vals[i+1]):
            es_pico_robusto = True
            
    # Si es el primer o último punto y son máximos relativos locales visibles
    if i == 0 and val_ad >= y_adelanto_vals[1]: es_pico_robusto = True
    if i == len(y_adelanto_vals) - 1 and val_ad >= y_adelanto_vals[-2]: es_pico_robusto = True

    if es_pico_robusto:
        puntos_adelanto_x.append(x_vals[i])
        puntos_adelanto_y.append(val_ad)
        puntos_adelanto_text.append(f"{val_ad:.1f}h")

if puntos_adelanto_x:
    fig.add_trace(go.Scatter(
        x=puntos_adelanto_x, 
        y=puntos_adelanto_y, 
        mode="markers+text", 
        text=puntos_adelanto_text, 
        textposition="top center", 
        textfont=dict(size=9, color="#0b5ed7", family="sans-serif"), 
        marker=dict(size=6, color="#0b5ed7"), 
        showlegend=False
    ), row=3, col=1)

for hito in hitos_produccion:
    is_fin = hito["tipo"] == "FIN"
    fig.add_annotation(
        x=hito["eje_x"], y=hito["y_val"], text=hito["texto"],
        showarrow=True, arrowhead=2, arrowsize=0.8, arrowwidth=1.2,
        arrowcolor="#d62728" if is_fin else "#238b45",
        ax=0, ay=-38 if is_fin else 38,
        bgcolor="white", bordercolor="#d62728" if is_fin else "#238b45",
        borderwidth=1, borderpad=3, font=dict(size=9, color="#d62728" if is_fin else "#1b5e20"),
        row=1, col=1
    )

max_y_picks = max(df_plot["Demanda_Acum"].max(), df_plot["Prod_Acum"].max())
for i_dia, dia in enumerate(dias_semana):
    idx_medio_dia = i_dia * 24 + 12
    fig.add_annotation(
        x=df_plot["Eje_X"].iloc[idx_medio_dia], y=max_y_picks * 0.94, text=f"<b>{dia.upper()}</b>",
        showarrow=False, font=dict(size=11, color="#444444"),
        bgcolor="rgba(255, 255, 255, 0.85)", bordercolor="rgba(150, 150, 150, 0.4)", borderwidth=1, borderpad=4,
        row=1, col=1
    )
    if i_dia > 0:
        fig.add_vline(x=df_plot["Eje_X"].iloc[i_dia * 24], line_dash="solid", line_color="rgba(100, 100, 100, 0.3)", line_width=1.2)

ticks_cada_n_horas = 3
x_ticks_vals = [df_plot["Eje_X"].iloc[i] for i in range(0, len(df_plot), ticks_cada_n_horas)]

fig.update_layout(height=950, template="plotly_white", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=60, r=30, t=80, b=50))
fig.update_xaxes(tickvals=x_ticks_vals, ticktext=x_ticks_vals, tickangle=-45, showgrid=True, row=3, col=1)
fig.update_yaxes(title_text="Picks Acumulados", row=1, col=1, showgrid=True)
fig.update_yaxes(title_text="Stock en Playa (Picks)", range=[0, CAPACIDAD_PLAYA * 1.05], row=2, col=1, showgrid=True)
fig.update_yaxes(title_text="Horas de Adelanto", row=3, col=1, showgrid=True)

# ==========================================
# 6. RENDERIZADO EN STREAMLIT
# ==========================================
st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 7. TABLA DE FRANJAS Y DETALLE DE PREPARACIÓN
# ==========================================
st.subheader("📋 Detalle Horario de Preparación y Estado de Playa")
st.markdown("Visualiza hora a hora la demanda, la producción generada, los **picks exactos** y las **horas de adelanto** disponibles en la playa.")

col_f1, col_f2 = st.columns(2)
with col_f1:
    dia_seleccionado = st.selectbox("Filtrar por Día:", ["Todos"] + dias_semana)
with col_f2:
    solo_activos = st.checkbox("Mostrar solo horas con producción activa", value=False)

df_tabla = df_plot.copy()
if dia_seleccionado != "Todos":
    df_tabla = df_tabla[df_tabla["Dia"] == dia_seleccionado]
if solo_activos:
    df_tabla = df_tabla[df_tabla["Produccion_Hora"] > 0]

st.dataframe(
    df_tabla[["Eje_X", "Demanda_Hora", "Produccion_Hora", "Stock_Playa", "Adelanto_Horas", "Estado"]],
    use_container_width=True,
    hide_index=True
)
