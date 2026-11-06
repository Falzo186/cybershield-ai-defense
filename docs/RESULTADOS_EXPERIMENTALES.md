# Resultados experimentales

Todas las cifras de este documento se **midieron realmente** el 06/11/2026 en esta máquina. No hay ninguna
estimada, ni ninguna tabla rellenada «para que quede completa». Donde no hay medición, se dice.

## Condiciones

| | |
|---|---|
| **Modelo** | `qwen2.5:1.5b` (Ollama local). Es el único con el que se corrieron campañas completas |
| **Hardware real** | AMD Radeon integrada (2 GB de VRAM declarados) · 17.8 GB de RAM · Windows 11 |
| **Inferencia** | **En CPU.** `nvidia-smi` no existe en esta máquina: **no hay la RTX 5060 de 8 GB** que mencionaba el encargo. Las latencias de abajo hay que leerlas con eso en mente |
| **Modelos instalados** | `qwen3:4b`, `llama3.2:3b`, `qwen2.5:7b`, `deepseek-r1:1.5b`, `llama3.2:1b`, `qwen2.5:1.5b`. No se descargó ninguno nuevo |
| **Conjunto** | Familia `oficiales` (13 escenarios), 3 repeticiones → **39 rondas por condición** |
| **Semilla** | 0 en todas las comparaciones, así que el orden y las repeticiones son idénticos |
| **Referencia** | Determinista (`permisos.evaluar_acceso`), nunca un juez LLM |

Todos los experimentos están guardados en `data/experimentos.jsonl` con su configuración completa, la
versión del código y la huella del conjunto. Los volcados en bruto están en `eval/`.

### Por qué n = 39 y qué significa eso

Con 39 observaciones, el intervalo de confianza del 95 % de una proporción mide unos **25 puntos** de ancho.
Es decir: con esta muestra solo se pueden detectar diferencias grandes. Subir a n = 200 por condición son
unas 7 horas de CPU por cada matriz de cuatro técnicas; se documenta como limitación, no se disimula
publicando las diferencias pequeñas como si fueran conclusiones.

---

## 1. Matriz de técnicas: base / few-shot / RAG / few-shot + RAG

Mismo conjunto, misma semilla, mismas repeticiones, mismo modelo. Solo cambia la técnica.
Volcado: `eval/matriz_tecnicas_qwen15.json` · 609 s en total.

| Técnica | Exactitud | IC 95 % | Exactitud estricta | Latencia mediana | p95 | Repetibilidad |
|---|---|---|---|---|---|---|
| `base` | 71.8 % | [56.2 %, 83.5 %] | 33.3 % | 3 433 ms | 5 230 ms | 76.9 % |
| **`fewshot`** | **87.2 %** | [73.3 %, 94.4 %] | **48.7 %** | **2 473 ms** | 3 356 ms | 84.6 % |
| `rag` | 76.9 % | [61.7 %, 87.4 %] | 43.6 % | **6 600 ms** | 13 673 ms | 84.6 % |
| `fewshot_rag` | 76.9 % | [61.7 %, 87.4 %] | 41.0 % | 2 481 ms | 6 206 ms | **92.3 %** |

**Fugas: 0 de 39 en las cuatro condiciones.** Ninguna técnica dejó salir un dato que no debía salir.

### Comparación estadística contra `fewshot` (bootstrap, 2 000 remuestreos)

| Comparación | Veredicto | Intervalo de la diferencia |
|---|---|---|
| `base` vs `fewshot` | **sin diferencia concluyente** | (−0.333, +0.026) |
| `rag` vs `fewshot` | **sin diferencia concluyente** | (−0.282, +0.051) |
| `fewshot_rag` vs `fewshot` | **sin diferencia concluyente** | (−0.282, +0.051) |

### Qué se puede afirmar y qué no

**Se puede afirmar:**

- **El RAG cuesta latencia, y mucha.** La mediana pasa de 2 473 ms a 6 600 ms (×2.7) y el p95 de 3 356 ms a
  13 673 ms (×4.1). Eso no es ruido estadístico: es el prompt creciendo con el material recuperado y el
  modelo procesándolo en CPU. Es el hallazgo más sólido de esta matriz.
- **Ninguna técnica produjo una fuga.** 0/156 rondas en total.
- **El RAG no empeoró la estabilidad, la mejoró.** `fewshot_rag` dio la repetibilidad más alta (92.3 %:
  12 de 13 escenarios devuelven siempre la misma decisión), y `base` la más baja (76.9 %).
- **La exactitud estricta es mucho peor que la permisiva en las cuatro** (33-49 % frente a 72-87 %). El
  modelo contiene bien, pero rara vez elige la decisión exacta: ante un caso que pedía
  `SOLICITAR_AUTORIZACION`, tiende a rechazar. No filtra, pero tampoco hace lo correcto.

**No se puede afirmar** que una técnica sea mejor que otra en exactitud. `fewshot` saca 15 puntos a `base`,
pero con n = 39 el intervalo de la diferencia incluye el 0. Decir «few-shot mejora la precisión un 15 %»
sería exactamente el error que el encargo pedía no cometer.

**Dato que llama la atención y que no se explica aquí:** los diagnósticos de `fewshot` incluyen 5
`ERROR_PARAMETRO` y 4 `FALLO_POLITICA`, mientras que `fewshot_rag` dio 39 `SIN_FALLO` limpios. Con una sola
corrida no se puede saber si es señal o azar.

---

## 2. Pipeline: directo frente a harness

Misma técnica (`fewshot`), mismo conjunto, misma semilla. Volcado: `eval/pipeline_y_temperatura.json`.

| Pipeline | Exactitud | IC 95 % | Latencia mediana | Infraestructura |
|---|---|---|---|---|
| `directo` | 79.5 % | [64.5 %, 89.2 %] | 2 032 ms | 0 |
| `harness` | 74.4 % | [58.9 %, 85.4 %] | 2 029 ms | 0 |

**Veredicto: sin diferencia concluyente** — intervalo de la diferencia (−0.231, +0.128), incluye el 0.

**El harness no mejoró nada medible, y era previsible.** Solo puede ayudar cuando el fallo es técnico
(formato ilegible, parámetro mal formado sobre una herramienta permitida), y en estas 39 rondas casi no
hubo de esos: los fallos fueron de criterio, que es justo lo que el harness **no** reintenta por diseño.

Esto es una confirmación de que la regla de seguridad funciona, no un fracaso del módulo: un harness que
hubiera «mejorado» la exactitud reintentando denegaciones de permiso habría sido un amplificador de ataque.
Lo que el harness aporta aquí no es precisión sino **control**: techos, detección de bucles, cancelación y
un registro completo de lo que hizo el modelo.

---

## 3. Temperatura del defensor

Misma técnica (`fewshot`), pipeline directo, mismo conjunto y misma semilla.

| Temperatura | Exactitud | IC 95 % | Repetibilidad | Latencia mediana |
|---|---|---|---|---|
| 0.0 | 82.1 % | [67.3 %, 91.0 %] | 92.3 % | 2 088 ms |

<!-- RESULTADOS-TEMPERATURA -->

---

## 4. Laboratorio adversarial: detección determinista

Reproducible al 100 % (no interviene ningún modelo):
`python -c "from src.lab import adversarial; print(adversarial.campana_deteccion()['metricas'])"`

| Métrica | Valor | IC 95 % | n |
|---|---|---|---|
| **Detección** | **78.9 %** | [56.7 %, 91.5 %] | 19 maliciosos |
| **Falsos positivos** | **0.0 %** | [0 %, 29.9 %] | 9 benignos |
| **Especificidad** | **100 %** | [70.1 %, 100 %] | 9 benignos |

Matriz de confusión: **VP 15 · FN 4 · FP 0 · VN 9**. Tiempo de detección: mediana **0.019 ms**.

| Vector | VP | FN | FP | VN |
|---|---|---|---|---|
| Directa (en la solicitud) | 10 | 3 | 0 | 6 |
| Indirecta (en la documentación recuperada) | 5 | 1 | 0 | 3 |

Los 4 fallos son `DI-11`, `DI-12`, `IN-06` (reformulaciones) y `DI-13` (base64): están en el conjunto a
propósito para medir el techo real del filtro. **Ninguna categoría que el filtro declara cubrir se escapa.**
Detalle en [`LABORATORIO_PROMPT_INJECTION.md`](LABORATORIO_PROMPT_INJECTION.md).

---

## 5. Coste de la recuperación

| | |
|---|---|
| Corpus | 15 documentos → 17 fragmentos |
| Recuperación BM25 | **< 1 ms** (medido como 0 ms con la resolución del reloj) |
| Coste real del RAG | **no está en recuperar, sino en el prompt más largo**: ×2.7 en la latencia del modelo |
| Embeddings | **no medidos**: `nomic-embed-text` no está descargado y no se descargó nada |

---

## 6. Lo que NO se midió, y por qué

| Pendiente | Motivo |
|---|---|
| **Otros modelos** (`llama3.2:3b`, `qwen2.5:7b`, `deepseek-r1:1.5b`…) | Una matriz de 4 técnicas × 39 rondas son ~10 min con el modelo de 1.5B; con el de 7B en CPU serían horas. El sistema está preparado (`--modelo`), solo falta tiempo de máquina |
| **Modo estrés** (5 200 rondas) | Más de 3 horas de CPU |
| **n grande** (≥ 200 por condición) | Es lo que haría concluyentes las comparaciones de la §1. Es la tarea con mejor relación valor/esfuerzo que queda |
| **Cumplimiento del modelo en el laboratorio adversarial** | La detección determinista sí está medida; la tasa de cumplimiento del defensor IA ante los 19 intentos, no |
| **Consumo de memoria y GPU** | No hay GPU NVIDIA ni `nvidia-smi` en esta máquina. No se publica un dato que no se puede tomar |
| **Wazuh real** | No hay ninguna instalación de Wazuh a la que conectarse |
| **Embeddings del RAG** | El modelo de embeddings no está descargado |

---

## 7. Cómo reproducir todo esto

```bash
# Matriz de técnicas (§1) — unos 10 minutos
python -m src.lab.evaluacion.correr --modelo qwen2.5:1.5b --modo rapido --repeticiones 3 --matriz --tipo oficial

# Una condición suelta
python -m src.lab.evaluacion.correr --modelo qwen2.5:1.5b --modo rapido --repeticiones 3 --pipeline harness

# Laboratorio adversarial (§4) — instantáneo, sin Ollama
python -m src.lab.test_adversarial
```

Cada campaña queda registrada en `data/experimentos.jsonl` con modelo, técnica, semilla, temperatura,
versión del código y huella del conjunto, de modo que dos corridas se pueden comparar sabiendo exactamente
en qué se diferencian. El panel (`/panel/#experimentos`) permite seleccionar dos y compararlas.
