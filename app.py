import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ==========================================
# 0. CONFIGURACIÓN DE PÁGINA STREAMLIT
# ==========================================
st.set_page_config(page_title="OPM Guadix - Planificación Semanal", layout="wide")
st.title("🏭 OPM Guadix: Panel de Planificación Semanal Optimizada")

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
    value=5.0,
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
hitos_produccion = []
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

    h_fin_idx = min(h_fin + 1, 23)
    hitos_produccion.append({
        "tipo": "FIN",
        "eje_x": f"{dia[:3]} {horas_24[h_fin_idx]}",
        "y_val": produccion_acum[h_fin_idx],
        "texto": (
            f"<b>FIN PROD {horas_24[h_fin_idx]}</b><br>Buffer:"
            f" {int(buffer_muelle[h_fin_idx]):,}".replace(",", ".")
            + " pks"
        ),
    })

  for h_idx in range(24):
    df_completo_ajustado.append({
        "Eje_X": f"{dia[:3]} {horas_24[h_idx]}",
        "Dia": dia,
        "Hora": horas_24[h_idx],
        "Demanda_Acum": demanda_acum[h_idx],
        "Prod_Acum": produccion_acum[h_idx],
        "Adelanto_Horas": horas_adelanto[h_idx],
        "Produciendo": 1 if produccion_h[h_idx] > 0 else 0,
    })

  stock_actual_00h = produccion_acum[23] - demanda_total_real

df_plot = pd.DataFrame(df_completo_ajustado)

# ==========================================
# 4. GRÁFICO INTERACTIVO CON PLOTLY
# ==========================================
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    row_heights=[0.65, 0.35],
    subplot_titles=(
        f"OPM GUADIX - Planificación Semanal Optimizada (Piso {objetivo_horas}h)",
        "Horas de Colchón / Adelanto en Muelle",
    ),
)

# Panel Superior: Demanda y Producción Acumulada
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
        hovertemplate=(
            "<b>%{x}</b><br>Producción + Stock: %{y:,.0f} pks<extra></extra>"
        ),
    ),
    row=1,
    col=1,
)

# Panel Inferior: Horas de Adelanto
fig.add_trace(
    go.Scatter(
        x=df_plot["Eje_X"],
        y=df_plot["Adelanto_Horas"],
        name="Horas de Adelanto",
        line=dict(color="#1f77b4", width=2),
        hovertemplate="<b>%{x}</b><br>Colchón: %{y:.2f} h<extra></extra>",
    ),
    row=2,
    col=1,
)

# Líneas de referencia (Piso y Techo)
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

# Cuadros de anotación de Inicio y Fin anclados estrictamente al Panel Superior
for hito in hitos_produccion:
  is_fin = hito["tipo"] == "FIN"
  fig.add_annotation(
      x=hito["eje_x"],
      y=hito["y_val"],
      text=hito["texto"],
      showarrow=True,
      arrowhead=2,
      arrowsize=1,
      arrowwidth=1.5,
      arrowcolor="#d62728" if is_fin else "#2ca02c",
      ax=0,
      ay=-45 if is_fin else 45,
      bgcolor="white",
      bordercolor="#d62728" if is_fin else "#2ca02c",
      borderwidth=1.5,
      borderpad=4,
      font=dict(size=10, color="#d62728" if is_fin else "#2ca02c"),
      row=1,
      col=1,
  )

# Divisores verticales por día
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

# Configuración del Layout de Plotly y control de marcas en el Eje X para evitar saturación
ticks_cada_n_horas = 3  # Muestra una etiqueta cada 3 horas para limpieza visual
x_ticks_vals = [df_plot["Eje_X"].iloc[i] for i in range(0, len(df_plot), ticks_cada_n_horas)]

fig.update_layout(
    height=750,
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
# 5. RENDERIZADO EN STREAMLIT
# ==========================================
st.plotly_chart(fig, use_container_width=True)
