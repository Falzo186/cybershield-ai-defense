# Informe final — Evolución técnica de CyberShield AI Defense

06/11/2026 · rama `feature/evolucion-tecnica` · 7 commits sobre `39af796`

---

## 1. Estado inicial comprobado

`main` en `39af796`, árbol limpio. Línea base ejecutada antes de tocar nada:

```
python ejecutar_pruebas.py --rapido  →  21/21 suites · 652/652 comprobaciones
```

### La discrepancia de partida

El encargo describía un «Analizador de ventas con IA» con Python + Streamlit + Ollama + **DuckDB** +
dataset **Instacart**, 31 fases y 649 pruebas. Comprobado contra el repositorio:

| Afirmación | Realidad |
|---|---|
| DuckDB | No existe (`grep -ri duckdb` → 0 resultados) |
| Instacart | No existe; los datos son SQLite ficticio de «CyberShield Industries» |
| Streamlit | No existe; la interfaz es HTML/CSS/JS sin framework, servida por FastAPI |
| SQL generado por un LLM | **No existe y es deliberado**: `repositorio.py` solo tiene consultas fijas |
| 31 fases | `PROGRESO.md` documenta unas 15 entregas (Fase 1 … Fase H) |
| 649 pruebas | **La única cifra que casi encajaba**, y era de este repositorio: 652 |

Existe además un segundo proyecto del usuario en `C:\Users\alexp\IAF` («Bike Stores», Streamlit + SQLite +
Ollama) que sí es un analizador de ventas, pero tampoco usa DuckDB ni Instacart. **El usuario decidió
trabajar sobre `llm-redteam`** y tomar el código como única fuente de verdad.

### El hardware tampoco coincidía

El encargo hablaba de una **NVIDIA RTX 5060 de 8 GB**. La máquina tiene **AMD Radeon integrada** (2 GB
declarados) y 17.8 GB de RAM; `nvidia-smi` no existe. **Ollama corre en CPU**: 2-7 s por inferencia con
`qwen2.5:1.5b`. Todas las latencias de este informe hay que leerlas con eso presente, y por eso no se
publica ningún dato de consumo de GPU: no se puede tomar.

---

## 2. Arquitectura encontrada

Seis capas deterministas (filtro rápido → defensor IA → catálogo cerrado → validación → permisos/
autorización → repositorio + auditoría) sobre SQLite, con la IA en posición de **proponer**, nunca de
ejecutar. Un servidor FastAPI de 1 821 líneas, una interfaz vanilla de ~3 800 líneas con metáfora de
escritorio, y una partida Rojo/Azul completa. Mapa actualizado en
[`ARQUITECTURA_ACTUALIZADA.md`](ARQUITECTURA_ACTUALIZADA.md).

**Problemas detectados** (11, en [`PLAN_EVOLUCION_TECNICA.md`](PLAN_EVOLUCION_TECNICA.md) §2): sin
diagnóstico estructurado, infraestructura y modelo mezclados en un mismo cubo, sin presupuestos de
ejecución, sin RAG, sin evaluación reproducible, sin registro de experimentos, Wazuh sin modos ni cliente,
sin interfaz para nada de esto, y `app.py` demasiado grande.

---

## 3. Funcionalidades nuevas

| Módulo | Qué hace |
|---|---|
| `src/lab/diagnostico.py` | Clasifica **por qué** falló cada ronda en 12 clases, con evidencia, confianza y `DIAGNOSTICO_INDETERMINADO` cuando no hay demostración. Separa infraestructura de modelo |
| `src/lab/harness.py` | Presupuestos (iteraciones, llamadas, tokens, timeouts), detección de bucles, cancelación, estado serializable |
| `src/lab/rag/` | Corpus de 15 documentos, índice BM25 en Python puro, embeddings opcionales, **saneado anti-inyección** de lo recuperado |
| `src/lab/evaluacion/` | 52 escenarios con referencia determinista, 5 modos, semilla, métricas con Wilson y bootstrap, lanzador contra Ollama |
| `src/lab/experimentos.py` | Registro JSONL que solo añade, con hashes de código, BD y conjunto; comparador que avisa cuando dos corridas no son comparables |
| `src/lab/adversarial.py` | 28 casos de prompt injection directa e indirecta, con controles benignos, aislado del camino de producción |
| `src/lab/wazuh/` | Tres modos (real/simulado/desactivado), cliente de API de **solo lectura**, evaluador de reglas compartido |
| `src/lab/correlacion.py` | Cronología unificada (auditoría + eventos + alertas) y correlación con 7 reglas explicables |
| `server/panel.py` | 16 rutas `/api/panel/…`, GET públicos de solo lectura, POST con sesión |
| `ui/panel/` | Sistema de diseño con tokens y **11 pantallas** |

---

## 4. Funcionalidades mejoradas

- **`motor.py`**: toda ronda lleva ahora su diagnóstico; acepta técnica, parámetros de RAG y temperatura.
  Todos con valor por defecto: sin pasarlos, el comportamiento es idéntico al anterior.
- **`defensor.py`**: cuatro técnicas seleccionables (`base`, `fewshot`, `rag`, `fewshot_rag`) y temperatura
  configurable. El valor por defecto (`fewshot`, 0.2) es el comportamiento histórico.
- **`server/app.py`**: emite el diagnóstico por SSE y registra el panel. Tres bloques tocados, ninguna ruta
  existente modificada.
- **`integraciones/wazuh/test_reglas.py`**: deja de tener su propia copia del evaluador de reglas y usa el
  módulo compartido, para que no se desincronicen.
- **`ui/index.html` / `styles.css`**: **una línea**, el enlace al panel.

---

## 5. Problemas corregidos

1. **Infraestructura contaba como fallo del modelo.** `fallo_seguro` agrupaba Ollama caído, timeout, JSON
   ilegible y «defensor no configurado». Ahora cada causa tiene su clase y las no imputables salen del
   denominador de exactitud.
2. **Regresión introducida y corregida en el acto.** Al añadir claves al diccionario de defensa, `motor`
   las exigía con acceso directo y rompía `test_eventos`, que sustituye el defensor en las pruebas. Se pasó
   a `.get` para las opcionales. Detectado por la batería, no por inspección.
3. **El corpus del RAG contenía una carga de ataque literal.** El documento que describe las técnicas decía
   «pide activar un modo administrador» y el propio filtro lo descartaba, con razón. Se reescribió el
   documento; **no** se exceptuó el filtro. Hay una prueba que lo impide en el futuro.
4. **El cliente de Wazuh tenía `/` en la lista de rutas permitidas**, lo que la hacía inútil: cualquier ruta
   pasaba. Detectado por la prueba que intenta llamar a `/active-response`.
5. **Duplicación del evaluador de reglas de Wazuh** entre la prueba y el adaptador.
6. **`app.py` creciendo sin control**: las rutas nuevas fueron a su propio módulo.

---

## 6. Archivos creados (25)

**Código** (10): `src/lab/diagnostico.py`, `harness.py`, `experimentos.py`, `adversarial.py`,
`correlacion.py`, `src/lab/rag/{__init__,corpus,indice}.py`,
`src/lab/evaluacion/{__init__,escenarios,metricas,campana,correr}.py`,
`src/lab/wazuh/{__init__,cliente,reglas}.py`, `server/panel.py`.

**Pruebas** (8): `test_diagnostico.py`, `test_harness.py`, `test_rag.py`, `test_evaluacion.py`,
`test_adversarial.py`, `test_wazuh.py`, `test_correlacion.py`, `server/test_panel.py`.

**Interfaz** (3): `ui/panel/{index.html,panel.css,panel.js}`.

**Documentación** (9): `PLAN_EVOLUCION_TECNICA.md`, `ARQUITECTURA_ACTUALIZADA.md`,
`CLASIFICACION_FALLOS.md`, `HARNESS.md`, `RAG.md`, `EVALUACION_AUTONOMA.md`,
`LABORATORIO_PROMPT_INJECTION.md`, `INTEGRACION_WAZUH.md`, `SEGURIDAD.md`,
`RESULTADOS_EXPERIMENTALES.md`, este informe.

## 7. Archivos modificados (8)

`src/lab/motor.py` · `src/lab/defensor.py` · `server/app.py` · `integraciones/wazuh/test_reglas.py` ·
`ejecutar_pruebas.py` · `ui/index.html` · `ui/styles.css` · `.gitignore` · `README.md` · `PROGRESO.md`.

**Ninguna funcionalidad existente se eliminó.**

---

## 8-10. Pruebas: inicial, final y comparación

| | Inicial | Final | Diferencia |
|---|---|---|---|
| Suites | 21 | **30** | +9 |
| Comprobaciones (sin navegador) | 652 | **1 081** | +429 |
| Comprobaciones (con navegador) | 690* | **1 187** | +497 |
| Suites en rojo | 0 | **0** | — |

\* La línea base no incluyó la suite de navegador; su cifra de entonces era 38 (hoy 106 porque esa suite
creció en la Fase H previa, no en este trabajo).

```
python ejecutar_pruebas.py  →  30/30 suites en verde · 1187/1187 comprobaciones
```

**Qué miden y qué no.** Ninguna de las 1 187 mide la calidad de un modelo: usan el Ollama falso o un doble
inyectado y comprueban el **camino del código**. La calidad del modelo se mide con las campañas de la §12,
que son una herramienta aparte y nunca parte de la batería.

Suites nuevas: `test_diagnostico` 50 · `test_harness` 49 · `test_rag` 64 · `test_evaluacion` 85 ·
`test_adversarial` 37 · `test_wazuh` 48 · `test_correlacion` 39 · `server/test_panel` 57.

---

## 11. Experimentos ejecutados

**10 experimentos reales contra Ollama, 364 rondas de inferencia**, guardados en `data/experimentos.jsonl`
con configuración completa, versión del código y huella del conjunto. Detalle y volcados en
[`RESULTADOS_EXPERIMENTALES.md`](RESULTADOS_EXPERIMENTALES.md) y `eval/`.

---

## 12. Resultados de RAG

Modelo `qwen2.5:1.5b`, 39 rondas por condición, misma semilla:

| Técnica | Exactitud | IC 95 % | Latencia mediana | Repetibilidad | Fugas |
|---|---|---|---|---|---|
| `base` | 71.8 % | [56.2, 83.5] | 3 433 ms | 76.9 % | 0/39 |
| `fewshot` | 87.2 % | [73.3, 94.4] | 2 473 ms | 84.6 % | 0/39 |
| `rag` | 76.9 % | [61.7, 87.4] | **6 600 ms** | 84.6 % | 0/39 |
| `fewshot_rag` | 76.9 % | [61.7, 87.4] | 2 481 ms | **92.3 %** | 0/39 |

**Ninguna diferencia de exactitud es concluyente** con n = 39 (los tres intervalos de la diferencia
incluyen el 0). Lo que **sí** está medido:

- **El RAG cuesta ×2.7 en latencia mediana y ×4.1 en p95.** No es ruido: es el prompt creciendo.
- **Cero fugas en las cuatro condiciones** (0/156 rondas).
- **El RAG no desestabiliza, estabiliza**: `fewshot_rag` dio la repetibilidad más alta.
- La recuperación en sí cuesta **< 1 ms**; el coste está en el prompt, no en el índice.

---

## 13. Resultados de Harness

| Pipeline | Exactitud | IC 95 % | Latencia mediana |
|---|---|---|---|
| directo | 79.5 % | [64.5, 89.2] | 2 032 ms |
| harness | 74.4 % | [58.9, 85.4] | 2 029 ms |

**Sin diferencia concluyente** (−0.231, +0.128). **El harness no mejoró la exactitud, y era previsible**:
solo reintenta errores técnicos, y los fallos de estas rondas fueron de criterio, que por diseño **no** se
reintentan. Un harness que hubiera «mejorado» la cifra reintentando denegaciones de permiso habría sido un
amplificador de ataque. Lo que aporta es **control** —techos, bucles, cancelación, trazabilidad—, no
precisión, y el informe no lo vende de otra manera.

**Temperatura** (0.0 / 0.2 / 0.7): exactitud sin diferencia concluyente, pero la **repetibilidad cae de
92.3 % a 84.6 % y a 46.2 %**. A 0.7, más de la mitad de los escenarios cambian de decisión entre
repeticiones. La temperatura actual del defensor queda justificada por estabilidad, no por exactitud.

---

## 14. Resultados del laboratorio adversarial

Detección determinista (reproducible al 100 %, sin modelo):

| Métrica | Valor | IC 95 % | n |
|---|---|---|---|
| Detección | **78.9 %** | [56.7, 91.5] | 19 maliciosos |
| Falsos positivos | **0.0 %** | [0, 29.9] | 9 benignos |

**VP 15 · FN 4 · FP 0 · VN 9.** Los 4 fallos son tres reformulaciones y una carga en base64, incluidas a
propósito para medir el techo del filtro. Ninguna categoría que el filtro declara cubrir se escapa.

La **inyección indirecta** (vía documentación recuperada) se detectó 5 de 6 veces, y ningún documento
legítimo se descartó por error.

**19 intentos son una muestra pequeña.** El intervalo va del 57 % al 92 %: esto no demuestra que el sistema
sea seguro, y el documento lo dice.

---

## 15. Estado de Wazuh

**Modo simulado: funcionando y medido.** 12 eventos reales de una partida producen 12 alertas, 2 de nivel
12, todas marcadas como simuladas. **Modo desactivado: funcionando.** **Modo real: implementado y probado
en sus contratos, nunca contra un Wazuh.** No hay ninguna instalación a la que conectarse.

Lo que está garantizado por pruebas: en modo real sin conexión se devuelve un **error visible** y **no** se
sustituye por alertas simuladas; el cliente rechaza antes de salir a la red cualquier método que no sea GET
y cualquier ruta fuera de una lista cerrada (no hay forma de llamar a `/active-response`); un valor
desconocido en la variable de entorno **nunca** se interpreta como «real».

**Lo que falta:** la lectura de alertas del indexador en modo real (hoy solo se lee el estado del manager,
y la respuesta lo dice en vez de devolver una lista vacía disfrazada de «no hay alertas»).

---

## 16. Rendimiento de Ollama

En CPU, con `qwen2.5:1.5b`: primera llamada 4.8 s (incluye 4.2 s de carga del modelo), después mediana
2.0-2.5 s y p95 3.4 s. Con RAG, mediana 6.6 s y p95 13.7 s. `llama3.2:3b` tardó 6.7 s en la primera
llamada. **Sin GPU**: `nvidia-smi` no existe en esta máquina.

Una campaña de 39 rondas tarda ~100 s; la matriz de 4 técnicas, ~10 minutos.

---

## 17. Errores que siguen pendientes

Ninguna prueba en rojo y ningún error conocido en el código entregado. Lo pendiente son **ausencias**, no
fallos:

- La lectura de alertas del indexador de Wazuh en modo real.
- La familia de escenarios `generado` está declarada pero no implementada.
- El harness no está conectado a la batalla de la partida.
- El timeout por herramienta no mata el hilo (Python no lo permite); se documenta, no se disimula.

---

## 18. Limitaciones de hardware

Sin GPU NVIDIA: toda la inferencia es CPU. Eso fija el tamaño de muestra alcanzable: **n = 39 por
condición** deja intervalos de ~25 puntos, con los que solo se detectan diferencias grandes. Llegar a
n = 200 por condición —lo que haría concluyentes las comparaciones— son ~7 horas por matriz. **No se
descargó ningún modelo nuevo**; se comprobaron antes VRAM, RAM y disco.

---

## 19. Próximas tareas recomendadas, por valor

1. **Subir el tamaño de muestra a n ≥ 200** en la matriz de técnicas. Es lo único que convierte «parece
   mejor» en «es mejor», y no requiere escribir código.
2. **Comparar modelos** (`llama3.2:3b`, `qwen2.5:7b`) sobre el mismo conjunto. El sistema ya lo soporta
   (`--modelo`); falta tiempo de máquina.
3. **Medir el cumplimiento del modelo** en el laboratorio adversarial, no solo la detección determinista.
4. **Implementar la lectura de alertas** del indexador de Wazuh y probar contra una instalación real.
5. **Ampliar el corpus del RAG** y volver a medir: con 17 fragmentos, su efecto está dominado por el ruido.
6. **Autenticación por persona y TLS** antes de cualquier uso fuera de una red de confianza.
7. Implementar la familia de escenarios generados y correr el modo estrés.

---

## 20. Tabla de módulos

| Módulo | Estado | Evidencia | Pendiente | % |
|---|---|---|---|---|
| Diagnóstico determinista | **Terminado** | 50/50 pruebas · integrado en motor y SSE · `CLASIFICACION_FALLOS.md` | Persistirlo en SQLite | 95 |
| Harness | **Terminado** | 49/49 · medido contra el camino directo · `HARNESS.md` | Conectarlo a la partida | 90 |
| RAG | **Terminado** | 64/64 · matriz de 4 técnicas medida · `RAG.md` | Embeddings sin medir; corpus pequeño | 90 |
| Evaluación autónoma | **Terminado** | 85/85 · 10 campañas reales, 364 rondas · `EVALUACION_AUTONOMA.md` | Familia `generado`; modo estrés sin correr | 85 |
| Registro de experimentos | **Terminado** | 10 experimentos con hashes · comparador con bootstrap | — | 95 |
| Laboratorio adversarial | **Terminado** | 37/37 · detección medida (78.9 %, IC95) · `LABORATORIO_PROMPT_INJECTION.md` | Cumplimiento del modelo sin medir | 80 |
| Wazuh | **Parcial** | 48/48 + 14/14 · simulado medido · `INTEGRACION_WAZUH.md` | Lectura de alertas; nunca probado contra un Wazuh real | 70 |
| Correlación y cronología | **Terminado** | 39/39 · funcionando sobre eventos reales | Correlación de Wazuh (`frequency`) no se simula | 95 |
| Panel e interfaz | **Terminado** | 57/57 · 11 pantallas verificadas sin errores de consola | El sistema de diseño no se aplicó a la interfaz de la partida | 85 |
| Seguridad | **Parcial** | Revisión completa en `SEGURIDAD.md` · pruebas de cada capa | `0.0.0.0` sin TLS; token por equipo | 70 |
| Acceso remoto | **Pendiente** | Arquitectura documentada en `SEGURIDAD.md` §6 | Todo; prioridad baja por decisión del encargo | 25 |
| Bitácora de aprendizaje | **No aplica** | — | El sistema es determinista y sin aprendizaje: no había 17 lecciones que depurar. Decisión documentada en `PLAN_EVOLUCION_TECNICA.md` §4 | — |
| Optimización de N9 | **No aplica** | — | No existe N9 ni ninguna consulta costosa | — |
| Diagnóstico de SQL | **No aplica** | — | Ningún modelo genera SQL; añadirlo habría destruido la capa 6 | — |

### Avance global

Media ponderada de los 11 módulos aplicables, por criterios de aceptación verificados y no por líneas de
código: **~82 %**.

Sin contar «Acceso remoto» (expresamente de prioridad baja en el encargo), el avance de lo que sí era
prioritario es **~87 %**.

---

## 21. Qué garantiza este trabajo, en una línea cada cosa

- Ninguna cifra de este informe está estimada: todas salen de una ejecución real y se pueden reproducir.
- Ninguna diferencia pequeña se presenta como una mejora: cuando la muestra no basta, se dice.
- Un fallo de infraestructura nunca cuenta como fallo del modelo, y se publica por separado.
- Nada simulado se presenta como real: ni una alerta de Wazuh, ni una respuesta de Ollama, ni un progreso.
- Ninguna de las 1 187 pruebas necesita Ollama ni red, y ninguna mide la calidad de un modelo.
- Ninguna funcionalidad existente se eliminó, y la batería completa sigue en verde.
