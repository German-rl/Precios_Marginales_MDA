<!-- Antes de publicar:
     - Las cifras con "≈" las leí de gráficas, no de tablas: verifícalas con tus DataFrames.
     - Los textos entre [corchetes] son para completar con tus resultados o nombres de figuras.
     - La parte del Norte (hallazgo 4) está pendiente: la demanda se tomó con el código de área 'NOR', que probablemente
       es Noroeste. Hay que rehacerla con 'NTE' (Norte) y completar los corchetes. -->

# Precios marginales locales (PML) del MDA: análisis exploratorio

Análisis exploratorio de los precios marginales locales del **Mercado del Día en Adelanto (MDA)** del Mercado Eléctrico Mayorista de México, para seis nodos del Sistema Interconectado Nacional, de enero de 2022 a octubre de 2026 (datos horarios). El objetivo es entender cómo se comportan el precio y sus componentes antes de construir un modelo de pronóstico del PML del día siguiente.

El análisis se centra en la **componente de congestión** y en qué la explica, comparándola con el balance entre demanda y generación de la región de cada nodo.

## Datos

| Dato | Fuente | Cobertura | Script |
|---|---|---|---|
| PML del MDA, por hora y componente (energía, pérdidas, congestión) | CENACE, servicio web SW-PML (JSON, bloques de 7 días) | ene 2022 – oct 2026 | `cenace_pml.py` |
| Demanda real por Balance, por región de control | CENACE | ene 2022 – oct 2026 | `demanda_merge.py` |
| Generación bruta de CFE más PIE por entidad federativa (mensual) | Sistema de Información Energética (SIE) | ene 2022 – ago 2026 | `EDA/generacion_prep.py` |
| Catálogo de nodos P v2026-10-23 (región de control, tensión, entidad) | CENACE | — | — |

**Calidad de los datos:** en el 0.00% de las filas el PML difiere de la suma de sus tres componentes en más de 0.05 MXN/MWh.

**Nodos analizados**

| Nodo | Ubicación | Región de control | Tensión |
|---|---|---|---|
| 01OLI-230 | Olivar, Ciudad de México | Central | 230 kV |
| 02IPO-230 | Ixtepec Potencia, Istmo (Oaxaca) | Oriental | 230 kV |
| 03SMR-230 | San Martín, Guadalajara | Occidental | 230 kV |
| 05CHU-230 | Chuviscar, Chihuahua | Norte | 230 kV |
| 06HUI-230 | Huinalá, Monterrey | Noreste | 230 kV |
| 08IZI-115 | Itzimná, Mérida | Peninsular | 115 kV |

## Cómo reproducirlo

1. `python cenace_pml.py download` y luego `python cenace_pml.py build` → `CENACE_PML/data/pml_mda.csv`.
2. Colocar el ZIP de demanda en `CENACE_PML/data/demanda/` y correr `python demanda_merge.py` → `CENACE_PML/data/demanda_balance.csv`.
3. Colocar el CSV de generación y el catálogo de nodos en `CENACE_PML/data/` y abrir `EDA/EDA.ipynb` (usa `EDA/generacion_prep.py`).

## Definiciones

El PML ($ MXN/MWh) de un nodo y una hora es la suma de tres componentes:

- **Energía (PML_ENE):** costo marginal de la energía en un punto de referencia del sistema; es el mismo para todos los nodos en una hora dada.
- **Pérdidas (PML_PER):** costo marginal de las pérdidas de transmisión del nodo respecto a la referencia; puede ser negativo.
- **Congestión (PML_CNG):** costo asociado a los límites de transmisión. Es positivo en zonas que importan energía con la red al límite y negativo en zonas que no pueden exportar sus excedentes.

Se llama "hora con congestión" a una hora con |PML_CNG| > 100 MXN/MWh (umbral elegido de forma arbitraria). Los porcentajes comparan enero–octubre de cada año para que 2026 sea comparable.

## Hallazgos

**1. El componente de energía domina el nivel del precio.** Explica entre el 93% y el 101% del PML promedio en 2022–2024 y baja a 78% y 81% en 2025 y 2026, porque aumenta la congestión. Su mediana fue la más alta en 2022 (1,137 MXN/MWh, frente a 476–590 en 2023–2026, promedio de los seis nodos), en un año en que el gas natural de referencia (Henry Hub) promedió ≈ 6.4 USD/MMBtu frente a ≈ 2.5 en 2023. En 2024 hay una cola pesada: el p99 llega a 6,738 MXN/MWh, concentrada en mayo y junio, que coincide con la ola de calor y con el Estado Operativo de Alerta declarado por CENACE el 18 de mayo de 2024. 08IZI-115 tiene el PML promedio más alto de los seis nodos (1,404 MXN/MWh) y 05CHU-230 el más bajo (602). [figura: mapa de calor del PML_ENE por año y mes]

**2. La congestión es distinta en cada nodo.** Porcentaje de horas con |CNG| > 100 MXN/MWh (positiva / negativa):

| Nodo | 2022 | 2024 | 2025 | 2026 |
|---|---|---|---|---|
| 08IZI-115 | 12.3 / 1.5 | 24.2 / 0.9 | 47.3 / 0.4 | 41.0 / 0.5 |
| 05CHU-230 | 0.8 / 16.9 | 3.4 / 51.8 | 6.0 / 51.9 | 1.2 / 53.7 |
| 02IPO-230 | 7.0 / 10.1 | 17.6 / 3.0 | 34.2 / 0.7 | 23.7 / 1.7 |
| 01OLI-230 | 6.1 / 1.2 | 13.7 / 0.7 | 27.9 / 0.3 | 18.5 / 0.0 |
| 06HUI-230 | 0.8 / 10.4 | 4.0 / 13.5 | 17.0 / 3.3 | 4.8 / 3.1 |
| 03SMR-230 | 0.9 / 0.9 | 5.2 / 3.9 | 13.7 / 2.4 | 7.5 / 0.3 |

2025 fue el año con más congestión positiva en cinco de los seis nodos y en 2026 baja en todos. 08IZI-115 es el nodo con congestión positiva más frecuente y extrema (p99 entre 4,013 y 7,853 MXN/MWh de 2023 a 2026). 05CHU-230 es el único con congestión predominantemente negativa (p10 entre −303 y −450 MXN/MWh desde 2024). 02IPO-230 cambió de signo: pasó de ser en parte negativa a ser casi toda positiva. [figura: tablas por nodo y año]

**3. La congestión tiene un patrón diario propio de cada nodo.** En 08IZI-115 es máxima entre las 22 y la 1 h (57–64% de las horas en 2025–2026) y mínima a las 7–8 h (12–19%). En 05CHU-230 la congestión negativa alcanza su máximo entre las 10 y las 18 h (63–76% en 2025), consistente con generación solar. La brecha entre día y noche (~30 puntos) ya existía en 2022; lo que cambió es el nivel de todas las horas (≈ +35 puntos), con el mayor aumento de noche (de ≈ 9% a ≈ 45%). [figura: mapas de calor por hora y año de 08IZI-115 y 05CHU-230]

**4. Balance entre demanda y generación de la región.**

- *Península (08IZI-115):* es importadora neta en todo el periodo, con una importación estimada de ≈ 600–850 MW entre 2022 y 2025 que sube a ≈ 850–1,020 MW en 2026. La correlación de Spearman entre la importación mensual y el % de horas congestionadas es 0.49. En el diagrama de dispersión, los meses de 2025 quedan por encima de los de 2022–2023 con la misma importación (por ejemplo, con ≈ 500,000 MWh al mes, ≤ 18% de las horas congestionadas en 2022 y 52–57% en 2025), lo que sugiere un cambio en la capacidad efectiva de importación u otras restricciones, no solo más importación. Mayo de 2025 es un episodio real y prolongado: las 744 horas están en los datos, la mediana de PML_CNG fue 1,569 MXN/MWh y el máximo 12,644, con congestión en casi todos los días salvo del 10 al 13. [figura: balance de la Península]
- *Norte (05CHU-230):* la región está cerca del equilibrio entre demanda y generación de CFE y PIE (balance de ≈ −750 a +900 MW) y pasó de exportar en 2022–2023 a importar en los veranos desde 2024. La congestión negativa sigue el ciclo del balance (≈ 5–10% de las horas en verano y hasta ≈ 97% en meses fríos), pero aumentó entre 2022 y 2024 aunque el balance de CFE y PIE no cambió en esa dirección. Esto es compatible con generación privada (solar) y límites de transmisión que estos datos no incluyen. [figura: balance del Norte]

**5. La demanda por sí sola explica poco el calendario de la congestión.** En la Península la demanda es máxima de mayo a septiembre y mínima de diciembre a febrero, pero la congestión se concentró en marzo–junio en 2023–2024, fue casi nula en el verano de 2022 y desde 2025 se extiende de abril a octubre, incluso en meses de demanda baja. La correlación mensual de Spearman entre la demanda (p90) y el % de horas congestionadas es 0.57 en todo el periodo, pero dentro de cada año va de −0.63 (2022) a 0.81 (2025), con solo 10–12 meses por año. Al comparar contra el promedio del mismo año, mes y hora, la diferencia de demanda entre horas con y sin congestión cae de +100–560 MW a +22–127 MW (≈ 2–6% de la demanda): la mayor parte de la asociación era estacional.

## Conclusiones

1. **La congestión, no la energía, es el componente que diferencia a los nodos.** El nivel del PML lo marca la componente de energía, igual para todos los nodos; lo que separa a un nodo de otro es el signo, la frecuencia y la intensidad de la congestión.
2. **En la Península la congestión se asocia con la dependencia de importaciones, pero eso no explica los cambios entre años.** La región es importadora neta, y la congestión crece con la importación; sin embargo, con la misma importación la congestión fue mucho mayor en 2025 que en 2022–2023, lo que es compatible con un cambio en la capacidad efectiva de importación u otras restricciones que estos datos no permiten identificar.
3. **En Chihuahua la congestión negativa es persistente y sigue el ciclo de la demanda regional, pero el balance de CFE y PIE no explica su aumento.** Es máxima cuando la demanda de la región es baja y mínima en verano, pero creció de 2022 a 2024 mientras el balance se movía hacia más importación. Es una señal de que falta la generación privada y de que los límites de transmisión pueden ser relevantes. Esto último es una hipótesis.
4. **La hipótesis de saturación por demanda industrial no se observa en los nodos analizados.** Atribuida por M2Energy en una nota de Milenio, no se refleja en 06HUI-230 (Monterrey), el nodo de una de las regiones que menciona: su congestión baja en 2025–2026.
5. **El nivel de tensión no se puede evaluar con un solo nodo.** 08IZI-115 es el único nodo de 115 kV y el único de la Península, por lo que tensión y región están confundidas.

## Limitaciones

- La generación es **bruta, mensual y solo de CFE más PIE**: no incluye a los generadores privados (por ejemplo, parques solares y eólicos). Eso sesga el balance: sobreestima la importación de la Península y no permite ver el efecto de la solar privada en Chihuahua.
- La demanda es por **región de control**, no por nodo, y las regiones no coinciden con los estados: Coahuila, por ejemplo, se reparte entre dos zonas del catálogo.
- La demanda por Balance incluye pérdidas y la generación es bruta: el nivel del balance es aproximado; importa más su forma y sus cambios.
- El umbral de congestión (100 MXN/MWh) es arbitrario y son solo seis nodos; los resultados pueden cambiar con otros.
- Se analiza solo el MDA (no el mercado en tiempo real) y no se dispone de temperatura, salidas de líneas ni mantenimientos.
- Las explicaciones con fuentes periodísticas (Milenio, El Financiero) son hipótesis, no resultados de los datos.
- Las correlaciones dentro de cada año usan 10–12 meses, por lo que son poco precisas.

## Próximos pasos


1. Añadir un nodo de 230 kV de la Península y uno de 115 kV de otra región para separar el efecto de la tensión del de la región.
2. Conseguir generación horaria que incluya a los privados y temperatura horaria de Mérida y Chihuahua.
3. Pronóstico del PML del día siguiente: líneas base (valor del día anterior y de la semana anterior), validación con ventana móvil y métricas MAE, RMSE y pinball; usar el **pronóstico** de demanda (no la demanda real) para no filtrar información.
4. Modelos de gradiente (LightGBM) y, después, una red neuronal con representación del nodo y salidas por cuantiles.
