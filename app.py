# Separación de puntos destacados (picos, valles, límites) en Verde y Rojo, evitando textos duplicados consecutivos
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
  cerca_limites = (
      val >= adelanto_max_estandar - 0.2 or val <= objetivo_horas + 0.3
  )

  if es_pico or es_valle or cerca_limites or i == 0 or i == len(y_vals) - 1:
    texto_actual = f"{val:.1f}h"
    cumple_rango = objetivo_horas <= val <= adelanto_max_estandar

    if cumple_rango:
      green_x.append(x_vals[i])
      green_y.append(val)
      # Si el texto es igual al anterior, no lo mostramos para evitar solapamientos
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
