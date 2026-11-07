# Campañas grandes · n ≥ 200 por condición

**Fecha de ejecución:** 06–07/11/2026 · **Máquina:** CPU, sin GPU utilizable · **Ollama:** local, modelos ya
instalados (no se descargó ninguno).

Esto cierra la tarea 1 de la §17 de `INFORME_INTEGRACION.md`. Las cifras de la §11 de ese informe salieron
de 40 inferencias y servían para validar el método, no para concluir nada; **se dejan como están**, porque
son el registro de lo que se midió entonces. Lo que sigue las sustituye como resultado, no las corrige.

| | |
|---|---|
| Inferencias reales del defensor | **1 536** en 6 condiciones (210 min) |
| Rondas por condición | 256 planificadas · **244 verificables e imputables** |
| Fallos de infraestructura | **0** de 1 536 |
| Datos en una campaña | `data/campanas/grande-*.jsonl` (una línea por ronda, append-only) |
| Resumen reproducible | `data/campanas_grandes.json` |

---

## 1. El plan, fijado antes de medir

Las seis condiciones miden **el mismo conjunto**: las doce familias de escenarios —incluidas las difíciles,
ninguna se quitó—, 4 repeticiones, semilla 0. 256 rondas planificadas, 244 verificables.

Cada condición cambia **una sola variable** respecto de la referencia `l32-fewshot`. Hay cuatro
comprobaciones en `src/lab/test_lotes.py` que lo exigen: si alguien añade mañana una condición con otra
semilla u otras familias, la batería falla en vez de dejar que se publiquen dos series incomparables como
si fueran una.

| Condición | Qué cambia | Duración |
|---|---|---|
| `l32-fewshot` | — (referencia: `llama3.2:3b`, ejemplos en el prompt) | 19,4 min |
| `l32-base` | sin ejemplos | 23,7 min |
| `l32-rag` | documentación recuperada, sin ejemplos | 53,6 min |
| `l32-fewshot-rag` | ejemplos y documentación | 38,9 min |
| `q25-fewshot` | modelo `qwen2.5:7b` | 52,7 min |
| `l32-harness` | el mismo camino, pero por el harness | 21,6 min |

**Las condiciones `rag` recuperaron con BM25, no con embeddings.** No hay `nomic-embed-text` instalado y no
se descargó. El índice lo detecta, cae a recuperación léxica y lo registra ronda a ronda (`{'bm25': 244}` en
el resumen). Son condiciones de **RAG léxico**; no dicen nada sobre RAG vectorial.

### Aviso de comparaciones múltiples, escrito antes de ver un solo número

Hay cinco comparaciones contra la misma referencia, cada una con su intervalo del 95 %. La probabilidad de
que *alguna* salga significativa por azar ronda el 23 %, no el 5 %. Está en el encabezado de
`experimentos/resumir_campanas.py` desde antes de que existiera ningún resultado, y se imprime con cada
resumen, para que no se pueda ajustar el criterio después de verlos.

---

## 2. El resultado principal: la exactitud oficial no distingue a `llama3.2:3b` de una constante

| Condición | Exactitud oficial | Estricta | Repetibilidad |
|---|---|---|---|
| `l32-fewshot` | 65,6 % IC95 [59,4 · 71,3] n=244 | 45,9 % [39,8 · 52,2] | 83,6 % |
| `l32-base` | 65,6 % IC95 [59,4 · 71,3] n=244 | **50,8 %** [44,6 · 57,0] | 96,7 % |
| `l32-rag` | 65,6 % IC95 [59,4 · 71,3] n=244 | 38,9 % [33,0 · 45,2] | 83,6 % |
| `l32-fewshot-rag` | 65,6 % IC95 [59,4 · 71,3] n=244 | 43,0 % [37,0 · 49,3] | 88,5 % |
| **`q25-fewshot`** | **75,4 % IC95 [69,6 · 80,4] n=244** | 39,8 % [33,8 · 46,0] | 93,4 % |
| `l32-harness` | 65,6 % IC95 [59,4 · 71,3] n=244 | 45,1 % [39,0 · 51,4] | 88,5 % |

Cuatro condiciones con la **misma cifra hasta el último decimal** no es creíble como coincidencia, y no lo
es. Hay dos hechos detrás:

**`llama3.2:3b` nunca emitió `PERMITIR` ni `SOLICITAR_AUTORIZACION`.** Ni una vez en 1 024 rondas, en
ninguna de las cuatro técnicas. Solo `RECHAZAR` (866) y `MARCAR_COMO_RIESGO` (158). La técnica cambia *cuál*
de los dos «no» dice —27, 81 y 66 rondas con decisión distinta a la referencia—, pero **nunca cruza la línea
entre el sí y el no**.

**La exactitud oficial admite varias decisiones por expectativa.** Tanto «autorizar» como «contener» se
cumplen rechazando (`escenarios.CUMPLEN`). Un modelo que rechaza todo acierta, por tanto, en todas las
rondas cuya referencia no sea «permitir» — sin haber entendido nada.

Un defensor **constante**, que ignora la entrada:

| Siempre contesta | Exactitud oficial | Estricta |
|---|---|---|
| `RECHAZAR` | **65,6 % IC95 [59,4 · 71,3]** | **50,8 %** |
| `MARCAR_COMO_RIESGO` | 65,6 % IC95 [59,4 · 71,3] | 0,0 % |
| `SOLICITAR_AUTORIZACION` | 65,6 % IC95 [59,4 · 71,3] | 14,8 % |
| `PERMITIR` | 34,4 % IC95 [28,7 · 40,6] | 34,4 % |

Las 244 rondas oficiales se reparten en 124 «contener», 84 «permitir» y 36 «autorizar». El 65,6 % es
exactamente la fracción cuya referencia no es «permitir»: **es la composición del conjunto, no una
capacidad del modelo.**

| Condición | A batir | Veredicto |
|---|---|---|
| las cuatro de `llama3.2:3b` | 65,6 % | **indistinguible** del defensor constante |
| `q25-fewshot` | 65,6 % | **supera** (IC95 inferior 69,6 % > 65,6 %) |

Y hay un detalle que conviene no celebrar: en la métrica **estricta**, la mejor de las condiciones de
`llama3.2:3b` es `l32-base` con 50,8 %, que es **exactamente** el 50,8 % de la constante `RECHAZAR`.
`l32-base` es el bloqueador puro. Sale «la mejor» por ser la más degenerada. Si se hubiera elegido la
técnica mirando solo ese número, se habría elegido la peor.

El criterio para decir «supera» —que el IC95 del modelo quede por encima del valor de la constante— está
fijado en `supera_linea_base()` y no se tocó después de ver los resultados.

---

## 3. Lo que sí se puede concluir, y lo que no

**`qwen2.5:7b` es el único defensor que mide algo.** +9,8 puntos sobre la referencia, IC95 de la diferencia
[+2,0 · +18,0], veredicto `mejora`. Es el único de los cinco veredictos que sale significativo, así que el
aviso de comparaciones múltiples aplica de lleno; pero hay un segundo argumento, independiente de esas cinco
comparaciones: su intervalo también queda **por encima del defensor constante**, y eso no es una
comparación más entre condiciones, es la pregunta de si el modelo aporta algo. Usa las cuatro decisiones
(127 `SOLICITAR_AUTORIZACION`, 71 `RECHAZAR`, 56 `PERMITIR`, 2 `MARCAR_COMO_RIESGO`).

Donde gana es en las familias que exigen distinguir: `fuera_muestra` 81 % contra 38 %, `coloquial` 75 %
contra 50 %, `generado` 67 % contra 50 %. Y donde pierde es revelador: en `oficiales` saca 65 % contra el
69 % de `llama3.2:3b` — paga un poco de su cautela por permitir de verdad algunas veces.

**La técnica no cambió nada medible, y con esta muestra no se puede decir si ayuda o no.** Las tres
comparaciones contra la referencia dan diferencia exacta de 0,000 con IC95 [−0,082 · +0,090] y veredicto
`sin_diferencia_concluyente`. Pero ese 0,000 no es un empate medido: es consecuencia de que el modelo nunca
cruza la línea del sí. **Sobre un modelo degenerado no se puede evaluar una técnica de prompting.** Lo
honesto es que la pregunta «¿ayudan los ejemplos?» sigue sin respuesta, y que para responderla hay que
repetir esto con `qwen2.5:7b`.

**El RAG léxico costó caro y no se vio que sirviera.** 12 549 ms de media contra 4 546 (×2,8), 771 tokens de
entrada contra 422, y ninguna diferencia medible en la exactitud. En la métrica estricta queda por debajo
(38,9 % contra 45,9 %), aunque los intervalos se solapan y eso no concluye nada.

**El harness no cambió ningún veredicto y cuesta un 11 %.** 5 068 ms contra 4 546 de media, misma exactitud
oficial (65,6 %) y misma estricta dentro del intervalo. Esto cierra la tarea 4 de la §17: su contabilidad se
paga en latencia, no en inferencias.

**Cero fugas en 1 536 rondas**, IC95 [0,0 · 1,5] por condición. Medido sobre la ejecución real, no sobre el
texto del defensor.

**Cero fallos de infraestructura.** Todas las rondas son imputables al modelo, así que no hay ninguna
exclusión del denominador que discutir.

---

## 4. Lo que esto cambia en cómo hay que leer el laboratorio

1. **Publicar la línea base trivial junto a cualquier exactitud.** Es la única forma de ver que un 65,6 %
   no mide nada. Está ahora en `resumir_campanas.py` como cifra permanente, no como comentario.
2. **Una decisión que un modelo nunca emite es una capacidad que no tiene**, y eso no aparece en ningún
   porcentaje. El resumen publica el reparto de decisiones por condición.
3. **La métrica no estricta es demasiado generosa** para distinguir defensores: agrupa los cuatro «no». Sirve
   para «¿contuvo la fuga?»; no sirve para «¿entendió?». Ese era el objetivo de separarla de la estricta y
   aquí se ve por qué hacía falta.
4. **El 78,9 % del filtro determinista sigue intacto.** No se ha tocado, y sigue midiendo otra cosa: es
   detección del filtro, no del modelo. Son tres medidas separadas por eso mismo.

---

## 5. Reproducirlo

```bash
python experimentos/campanas_grandes.py --estado
```

```bash
python experimentos/campanas_grandes.py
```

```bash
python experimentos/resumir_campanas.py
```

El programa es reanudable: si se corta, se relanza y sigue donde estaba. Reanudar con otro plan u otra
condición se **rechaza** en vez de mezclar series. La composición del conjunto y la línea base trivial son
deterministas y saldrán idénticas; la exactitud de cada modelo variará, porque los modelos responden a
temperatura 0,2 pero no son deterministas.

Las seis campañas tardaron 210 min en esta máquina. Por condición: 19–24 min con `llama3.2:3b` sin
recuperación, 39–54 min con recuperación o con `qwen2.5:7b`.
