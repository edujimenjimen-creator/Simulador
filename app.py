import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ==========================================
# 0. CONFIGURACIÓN DE PÁGINA STREAMLIT
# ==========================================
st.set_page_config(page_title="OPM Guadix - Planificación Semanal", layout="wide")
st.title("🏭 OPM Guadix: Panel de Planificación Semanal Optimizada (24/7)")

# ==========================================
# 1. PARÁMETROS CONFIGURABLES (VÍA SIDEBAR)
# ==========================================
st.sidebar.header("⚙️ Parámetros del Sistema")

vel_maquina = st.sidebar.number_input(
    "Velocidad de Máquina (Picks/hora)",
    min_value=1000,
    max_value=20000,
    value=5000,
    step=500,
)
objetivo_horas = st.sidebar.number_input(
    "Piso Inviolable Mínimo (Horas)",
    min_value=1.0,
    max_value=12.0,
    value=6.0,
    step=0.5,
)
adelanto_max_estandar = st.sidebar.number_input(
    "Techo Máximo Configurable (Horas)",
    min_value=5.0,
    max_value=24.0,
    value=10.0,
    step=0.5,
)

st.sidebar.subheader("📅 Demanda Diaria de Servicio (Picks)")
demanda_servicio_por_dia = {
    "Lunes": st.sidebar.number_input(
        "Lunes", min_value=10000, max_value=200000, value=70000, step=5000
    ),
    "Martes": st.sidebar.number_input(
        "Martes", min_value=10000, max_value=200000, value=50000, step=5000
    ),
    "Miércoles": st.sidebar.number_input(
        "Miércoles", min_value=10000, max_value=200000, value=75000, step=5000
    ),
    "Jueves": st.sidebar.number_input(
        "Jueves", min_value=10000, max_value=200000, value=80000, step=5000
    ),
    "Viernes": st.sidebar.number_input(
        "Viernes", min_value=10000, max_value=200000, value=89000, step=5000
    ),
    "Sábado": st.sidebar.number_input(
        "Sábado", min_value=10000, max_value=200000, value=60000, step=5000
    ),
}

demanda_lunes_siguiente = st.sidebar.number_input(
    "Demanda Lunes Siguiente (Picks)",
    min_value=10000,
    max_value=200000,
    value=70000,
    step=5000,
)

with st.sidebar.expander("🕒 Perfil Horario de Tiendas (24h)"):
    st.markdown("Ajusta el peso relativo de tiendas por hora:")
    default_tiendas = [
        1,
        3,
        3,
        3,
        3,
        0,
        0,
        0,
        0,
        8,
        19,
        9,
        9,
        2,
        2,
        0,
        3,
        7,
        12,
        4,
        1,
        0,
        0,
        0,
    ]
    tiendas_por_hora = []
    for h in range(24):
        val = st.number_input(
            f"Hora {h:02d}:00",
            min_value=0,
            max_value=100,
            value=default_tiendas[h],
            key=f"tienda_h_{h}",
        )
        tiendas_por_hora.append(val)

horas_24 = [f"{h:02d}:00" for h in range(24)]
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

if sum(tiendas_por_hora) == 0:
    st.error("⚠️ El perfil horario de tiendas no puede sumar cero.")
    st.stop()

# ==========================================
# 2. CÁLCULO DE OBJETIVO DE SÁBADO / STOCK INICIAL
# ==========================================
factor_lunes = demanda_lunes_siguiente / sum(tiendas_por_hora)
demanda_lunes_h = [round(t * factor_lunes) for t in tiendas_por_hora]
demanda_acum_lunes = np.cumsum(demanda_lunes_h)

cargas_madrugada_lunes = sum(demanda_lunes_h[:6])
cargas_6h_lunes = sum(demanda_lunes_h[6:12])
stock_objetivo_sabado = cargas_madrugada_lunes + cargas_6h_lunes

for _ in range(5):
    prod_h_test = [vel_maquina for i in range(24)]
    prod_acum_test = stock_objetivo_sabado + np.cumsum(prod_h_test)
    buffer_test = prod_acum_test - demanda_acum_lunes
    adelanto_test = buffer_test / vel_maquina
    min_adelanto_lunes = min(adelanto_test)

    if min_adelanto_lunes < objetivo_horas:
        deficit = (objetivo_horas - min_adelanto_lunes) * vel_maquina
        stock_objetivo_sabado += int(np.ceil(deficit))
    else:
        break

stock_inicial_lunes = stock_objetivo_sabado

# ==========================================
# 3. MOTOR INTELIGENTE 144H (JERARQUÍA: SUELO ABSOLUTO + EXCEPCIÓN DE TECHO)
# ==========================================
demanda_h_144 = []
for dia in dias_semana:
    dem_total = demanda_servicio_por_dia[dia]
    factor = dem_total / sum(tiendas_por_hora)
    dem_h = [round(t * factor) for t in tiendas_por_hora]
    demanda_h_144.extend(dem_h)

demanda_acum_144 = np.cumsum(demanda_h_144)

target_demanda_144 = np.copy(demanda_acum_144).astype(float)
for t in range(120, 144):
    target_demanda_144[t] += stock_objetivo_sabado * ((t - 119) / 24.0)

produccion_h_144 = [0] * 144

# FASE 1: Prioridad Absoluta -> Garantizar el Suelo Inviolable (6.0h)
# Si es estrictamente necesario para no bajar del suelo, la máquina se encenderá
# aunque eso provoque rebasar temporalmente el techo (excepción justificada).
for _ in range(1500):
    p_acum = stock_inicial_lunes + np.cumsum(produccion_h_144)
    buf = p_acum - target_demanda_144
    adel = buf / vel_maquina

    min_idx = np.argmin(adel)
    if adel[min_idx] >= objetivo_horas:
        break

    encendido = False
    for h in range(min_idx, -1, -1):
        if produccion_h_144[h] == 0:
            produccion_h_144[h] = vel_maquina
            encendido = True
            break
    if not encendido:
        for h in range(min_idx, 144):
            if produccion_h_144[h] == 0:
                produccion_h_144[h] = vel_maquina
                encendido = True
                break
    if not encendido:
        break

# FASE 2: Mantenerse en la Zona Ideal (Entre Suelo y Techo)
# Apagar producción sobrante SÓLO SI el mínimo de la semana se mantiene seguro a salvo del suelo.
for _ in range(2000):
    p_acum = stock_inicial_lunes + np.cumsum(produccion_h_144)
    buf = p_acum - target_demanda_144
    adel = buf / vel_maquina

    max_idx = np.argmax(adel)
    # Si el punto más alto está por debajo del techo, ya estamos en la zona ideal
    if adel[max_idx] <= adelanto_max_estandar + 0.001:
        break

    apagado = False
    # Intentar apagar horas productivas que estén por encima del techo estándar
    horas_por_encima = [
        h for h in range(144) if adel[h] > adelanto_max_estandar and produccion_h_144[h] == vel_maquina
    ]
    
    if horas_por_encima:
        # Apagar desde el pico más alto hacia atrás
        h_a_apagar = max(horas_por_encima, key=lambda x: adel[x])
        produccion_h_144[h_a_apagar] = 0

        # Validar si al apagar esta hora rompemos el suelo en algún sitio
        p_acum_test = stock_inicial_lunes + np.cumsum(produccion_h_144)
        buf_test = p_acum_test - target_demanda_144
        adel_test = buf_test / vel_maquina

        if min(adel_test) >= objetivo_horas - 0.001:
            apagado = True
        else:
            # ¡EXCEPCIÓN CRÍTICA ACTIVADA! Si apagar esto rompe el suelo, revertimos
            # porque la regla de oro es que el suelo jamás se perfora.
            produccion_h_144[h_a_apagar] = vel_maquina
            break
    else:
        break

# ==========================================
# 4. CONSTRUCCIÓN DE DATOS DIARIOS Y HITOS
# ==========================================
df_completo_ajustado = []
hitos_produccion = []
stock_actual_00h = stock_inicial_lunes

for dia_idx, dia in enumerate(dias_semana):
    p_h_dia = produccion_h_144[dia_idx * 24 : (dia_idx + 1) * 24]
    dem_h_dia = demanda_h_144[dia_idx * 24 : (dia_idx + 1) * 24]

    demanda_acum = np.cumsum(dem_h_dia)
    produccion_acum = stock_actual_00h + np.cumsum(p_h_dia)

    buffer_muelle = produccion_acum - demanda_acum
    horas_adelanto = np.round(buffer_muelle / vel_maquina, 2)

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
            hitos_produccion.append({
                "tipo": "INICIO",
                "eje_x": f"{dia[:3]} {horas_24[h_ini]}",
                "y_val": produccion_acum[h_ini],
                "texto": f"INICIO {horas_24[h_ini]}",
            })

            if h_fin == 23:
                etiqueta_fin = "24:00"
                eje_x_fin = f"{dia[:3]} 23:00"
                y_val_fin = produccion_acum[23]
            else:
                etiqueta_fin = horas_24[h_fin + 1]
                eje_x_fin = f"{dia[:3]} {horas_24[h_fin + 1]}"
                y_val_fin = produccion_acum[h_fin + 1]

            hitos_produccion.append({
                "tipo": "FIN",
                "eje_x": eje_x_fin,
                "y_val": y_val_fin,
                "texto": f"FIN {etiqueta_fin}",
            })

    for h_idx in range(24):
        df_completo_ajustado.append({
            "Eje_X": f"{dia[:3]} {horas_24[h_idx]}",
            "Dia": dia,
            "Hora": horas_24[h_idx],
            "Demanda_Acum": demanda_acum[h_idx],
            "Prod_Acum": produccion_acum[h_idx],
            "Adelanto_Horas": horas_adelanto[h_idx],
            "Produciendo": 1 if p_h_dia[h_idx] > 0 else 0,
        })

    stock_actual_00h = produccion_acum[23] - demanda_acum[-1]

df_plot = pd.DataFrame(df_completo_ajustado)

# ==========================================
# 5. GRÁFICO INTERACTIVO CON PLOTLY
# ==========================================
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    row_heights=[0.65, 0.35],
    subplot_titles=(
        f"OPM GUADIX - Planificación Semanal Optimizada 24/7 (Piso {objetivo_horas}h)",
        "Horas de Colchón / Adelanto en Muelle",
    ),
)

fig.add_trace(
    go.Scatter(
        x=df_plot["Eje_X"],
        y=df_plot["Demanda_Acum"],
        name="Demanda Acumulada",
        line=dict(color="#ff7f0e", width=2.5),
        hovertemplate="<b>%{x}</b><br>Demanda: %{y:,.0f} pks<extra></extra>",
    ),
    row=1,
    col=1,
)

fig.add_trace(
    go.Scatter(
        x=df_plot["Eje_X"],
        y=df_plot["Prod_Acum"],
        name="Producción Acumulada + Stock",
        line=dict(color="#2ca02c", width=2.5),
        hovertemplate="<b>%{x}</b><br>Producción + Stock: %{y:,.0f} pks<extra></extra>",
    ),
    row=1,
    col=1,
)

fig.add_trace(
    go.Scatter(
        x=df_plot["Eje_X"],
        y=df_plot["Adelanto_Horas"],
        name="Horas de Adelanto",
        mode="lines",
        line=dict(color="#1f77b4", width=2),
        hoverinfo="skip",
    ),
    row=2,
    col=1,
)

green_x, green_y, green_text = [], [], []
red_x, red_y, red_text = [], [], []

y_vals = df_plot["Adelanto_Horas"].values
x_vals = df_plot["Eje_X"].values

ultimo_texto_verde = None
ultimo_texto_rojo = None

for i in range(len(y_vals)):
    val = y_vals[i]
    es_pico = (
        0 < i < len(y_vals) - 1
        and y_vals[i] >= y_vals[i - 1]
        and y_vals[i] >= y_vals[i + 1]
    )
    es_valle = (
        0 < i < len(y_vals) - 1
        and y_vals[i] <= y_vals[i - 1]
        and y_vals[i] <= y_vals[i + 1]
    )
    cerca_limites = val >= adelanto_max_estandar - 0.2 or val <= objetivo_horas + 0.3

    if es_pico or es_valle or cerca_limites or i == 0 or i == len(y_vals) - 1:
        texto_actual = f"{val:.1f}h"
        cumple_rango = objetivo_horas <= val <= adelanto_max_estandar

        if cumple_rango:
            green_x.append(x_vals[i])
            green_y.append(val)
            if texto_actual != ultimo_texto_verde:
                green_text.append(texto_actual)
                ultimo_texto_verde = texto_actual
            else:
                green_text.append("")
        else:
            red_x.append(x_vals[i])
            red_y.append(val)
            if texto_actual != ultimo_texto_rojo:
                red_text.append(texto_actual)
                ultimo_texto_rojo = texto_actual
            else:
                red_text.append("")

if green_x:
    fig.add_trace(
        go.Scatter(
            x=green_x,
            y=green_y,
            mode="markers+text",
            text=green_text,
            textposition="top center",
            textfont=dict(size=9, color="#2ca02c"),
            marker=dict(size=6, color="#2ca02c"),
            name="En Rango",
            showlegend=False,
            hovertemplate="<b>%{x}</b><br>Colchón: %{y:.2f} h<extra></extra>",
        ),
        row=2,
        col=1,
    )

if red_x:
    fig.add_trace(
        go.Scatter(
            x=red_x,
            y=red_y,
            mode="markers+text",
            text=red_text,
            textposition="top center",
            textfont=dict(size=9, color="#d62728"),
            marker=dict(size=8, color="#d62728"),
            name="Fuera de Rango (Excepción / Alerta)",
            showlegend=False,
            hovertemplate="<b>%{x}</b><br>Colchón: %{y:.2f} h<extra></extra>",
        ),
        row=2,
        col=1,
    )

fig.add_hline(
    y=objetivo_horas,
    line_dash="dash",
    line_color="#d62728",
    line_width=1.8,
    row=2,
    col=1,
    annotation_text=f"Piso Inviolable ({objetivo_horas}h)",
    annotation_position="bottom right",
)

fig.add_hline(
    y=adelanto_max_estandar,
    line_dash="dot",
    line_color="#2ca02c",
    line_width=1.5,
    row=2,
    col=1,
    annotation_text=f"Techo Máximo ({adelanto_max_estandar}h)",
    annotation_position="top right",
)

for hito in hitos_produccion:
    is_fin = hito["tipo"] == "FIN"
    fig.add_annotation(
        x=hito["eje_x"],
        y=hito["y_val"],
        text=hito["texto"],
        showarrow=True,
        arrowhead=2,
        arrowsize=0.8,
        arrowwidth=1.2,
        arrowcolor="#d62728" if is_fin else "#238b45",
        ax=0,
        ay=-28 if is_fin else 28,
        bgcolor="white",
        bordercolor="#d62728" if is_fin else "#238b45",
        borderwidth=1,
        borderpad=3,
        font=dict(size=9, color="#d62728" if is_fin else "#1b5e20"),
        row=1,
        col=1,
    )

max_y_picks = max(df_plot["Demanda_Acum"].max(), df_plot["Prod_Acum"].max())
for i_dia, dia in enumerate(dias_semana):
    idx_medio_dia = i_dia * 24 + 12
    x_dia_val = df_plot["Eje_X"].iloc[idx_medio_dia]
    fig.add_annotation(
        x=x_dia_val,
        y=max_y_picks * 0.94,
        text=f"<b>{dia.upper()}</b>",
        showarrow=False,
        font=dict(size=11, color="#444444"),
        bgcolor="rgba(255, 255, 255, 0.85)",
        bordercolor="rgba(150, 150, 150, 0.4)",
        borderwidth=1,
        borderpad=4,
        row=1,
        col=1,
    )

for i_dia, dia in enumerate(dias_semana):
    if i_dia > 0:
        base_idx = i_dia * 24
        x_val = df_plot["Eje_X"].iloc[base_idx]
        fig.add_vline(
            x=x_val,
            line_dash="solid",
            line_color="rgba(100, 100, 100, 0.3)",
            line_width=1.2,
        )

ticks_cada_n_horas = 3
x_ticks_vals = [
    df_plot["Eje_X"].iloc[i] for i in range(0, len(df_plot), ticks_cada_n_horas)
]

fig.update_layout(
    height=780,
    template="plotly_white",
    hovermode="x unified",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
    ),
    margin=dict(l=60, r=30, t=80, b=50),
)

fig.update_xaxes(
    tickvals=x_ticks_vals,
    ticktext=x_ticks_vals,
    tickangle=-45,
    showgrid=True,
    row=2,
    col=1,
)
fig.update_yaxes(title_text="Picks Acumulados", row=1, col=1, showgrid=True)
fig.update_yaxes(title_text="Horas de Colchón", row=2, col=1, showgrid=True)

# ==========================================
# 6. RENDERIZADO EN STREAMLIT
# ==========================================
st.plotly_chart(fig, use_container_width=True)
