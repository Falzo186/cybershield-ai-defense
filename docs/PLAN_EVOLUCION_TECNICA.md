# Plan de evolución técnica — CyberShield AI Defense

Auditoría del 06/11/2026 sobre `main` en `39af796` (árbol limpio). Todo lo que aparece aquí se **ejecutó o
inspeccionó**; lo que no se comprobó se dice expresamente.

---

## 0. Aviso previo: el informe de partida no corresponde a este repositorio

El encargo describe un «Analizador de ventas con IA» con **Python + Streamlit + Ollama + DuckDB + dataset
Instacart + llama3.1:8b + qwen2.5-coder 7B**, 31 fases y 649 pruebas. Comprobado contra el repositorio real:

| Afirmación del informe | Estado real en este repositorio |
|---|---|
| DuckDB en modo solo lectura | **No existe.** No hay ninguna referencia a DuckDB (`grep -ri duckdb` → 0) |
| Dataset Instacart | **No existe.** Los datos son SQLite ficticio de «CyberShield Industries» (`data/lab.db`, 13 tablas) |
| Streamlit | **No existe.** La interfaz es HTML/CSS/JS sin framework ni build, servida por FastAPI |
| Generación de SQL por un LLM | **No existe y es deliberado.** El repositorio prohíbe el SQL libre: `repositorio.py` solo tiene consultas fijas y parametrizadas |
| llama3.1:8b, qwen2.5-coder 7B | No están fijados en el código; el modelo se elige en vivo entre los instalados en Ollama |
| 31 fases | Las fases documentadas en `PROGRESO.md` van de la 1 a la H (unas 15 entregas) |
| 649 pruebas satisfactorias | **La única cifra que casi encaja**, y es de *este* repositorio: la línea base medida hoy da **652/652** |

Existe además un segundo proyecto del usuario en `C:\Users\alexp\IAF` («Bike Stores · Analítica y asistente en
español»: Streamlit + SQLite + Ollama + sqlglot, 10 fases) que sí es un analizador de ventas, pero tampoco usa
DuckDB ni Instacart. **Por decisión expresa del usuario (06/11/2026) se trabaja sobre `llm-redteam`** y el
código real es la única fuente de verdad.

**Consecuencia para el plan.** Los requisitos del encargo que presuponen un motor text2sql no tienen objeto
aquí y no se implementan como estaban escritos; se traducen a su equivalente real o se descartan de forma
explícita (§4). Nada se marca como hecho si no lo está.

---

## 1. Arquitectura actual (verificada)

| Capa | Archivos | Notas |
|---|---|---|
| Interfaz | `ui/index.html` (459 líneas), `app.js` (1 150), `render.js` (1 461, solo pinta, sin `innerHTML`), `escritorio.js` (581, ventanas arrastrables), `api.js` (131, REST + SSE), `styles.css` (737) | Vanilla, sin build ni CDN. Tema oscuro con 13 tokens en `:root`. |
| Servidor | `server/app.py` (1 821 líneas, FastAPI), `server/partida.py`, `server/mock_server.py` | Un proceso; estado de partida en memoria; SSE en `/api/eventos`. |
| Motor IA | `src/lab/motor.py` (172), `atacante.py` (119), `defensor.py` (83), `cliente_ollama.py` (219), `filtro_rapido.py` (35), `sesion.py` (154), `ataque_ia.py` (83) | Ollama por `urllib` de la stdlib (`/api/chat`, `think:false`). |
| Capas de acceso | `herramientas.py` (catálogo de 4 + validación por regex), `permisos.py` (rol × sensibilidad, deny-by-default), `repositorio.py` (782, único acceso a BD) | La IA **propone**; las capas deciden. Sin SQL libre. |
| Datos | SQLite `data/lab.db`; `schema.py`, `seed.py` | Auditoría *append-only* por triggers. |
| Eventos SIEM | `data/eventos.jsonl` escrito por `Repositorio.registrar` | 26 tipos en `EVENTOS_SIEM`, 11 campos por línea. |
| Wazuh | `integraciones/wazuh/`: `local_rules.xml` (18 reglas, ids 100100-100140), `ossec_localfile.xml`, `test_reglas.py` | **Documentado y validado sin conexión. Nunca probado contra un Wazuh real.** |
| Pruebas | 14 suites `src/lab/test_*.py`, 5 de servidor, 2 de integración, 1 de navegador (Playwright) | Lanzador único: `ejecutar_pruebas.py`. |

### Flujo de una ronda real

`atacante.generar_ataque` (Ollama) → `motor.procesar_defensa` → `filtro_rapido.clasificar_rapido` (regex, sin
inferencia) → `defensor.analizar` (Ollama, JSON) → circuito de sesión (`sesion.UMBRAL_CIRCUITO`) →
`herramientas.ejecutar_herramienta` (catálogo → validación → permisos/autorización → repositorio) →
`motor.evaluar_veredicto` → `sesion.registrar` → auditoría + `eventos.jsonl` + SSE.

### Línea base de pruebas (ejecutada hoy)

```
python ejecutar_pruebas.py --rapido
21/21 suites en verde · 652/652 comprobaciones
```

Detalle: `test_lab` 20, `test_motor` 41, `test_correos` 16, `test_reglas` 25, `test_misiones` 17,
`test_documentos` 12, `test_eventos` 13, `test_puntaje` 9, `test_cliente` 18, `test_correo_app` 39,
`test_incidentes` 42, `test_ataque_ia` 22, `test_informe` 31, `test_apps` 23, `server/test_partida` 30,
`server/test_app` 157, `server/test_batalla_partida` 43, `server/test_resultados` 29, `server/test_apps` 27,
`e2e/test_reinicio` 24, `wazuh/test_reglas` 14. La suite de navegador (`e2e/demo_partida.py`, 38
comprobaciones) no se ejecutó en esta línea base.

**Interpretación honesta de esa cifra.** Las pruebas usan el Ollama falso de `e2e/ollama_falso.py`: comprueban
**el camino del código, no la calidad de ningún modelo**. Ninguna de las 652 mide precisión de un LLM.

---

## 2. Problemas detectados

| # | Problema | Evidencia | Gravedad |
|---|---|---|---|
| P1 | **No hay diagnóstico estructurado del fallo.** Una ronda devuelve `veredicto` + un `error` que es una cadena libre (`"defensor: HTTP 500"`, `"capas: …"`). No se puede agregar, contar ni comparar por tipo de causa. | `motor.procesar_defensa`, campo `error` | Alta |
| P2 | **Infraestructura y modelo se mezclan.** `fallo_seguro` agrupa Ollama caído, timeout, JSON ilegible y «defensor no configurado». Son causas distintas y hoy caen en el mismo cubo. | `ataque_ia.clasificar`, rama `v == "ERROR"` | Alta |
| P3 | **Sin presupuestos de ejecución.** `motor.ejecutar_ronda` no tiene límite de iteraciones, ni timeout global, ni presupuesto de tokens, ni detección de bucles o de prompts repetidos. El único tope es `MAX_ATAQUES = 8` por partida y el timeout por llamada (120 s). | `motor.py`, `cliente_ollama.generar` | Alta |
| P4 | **Sin recuperación documental (RAG).** El defensor recibe un *system prompt* fijo; no consulta políticas, precedentes ni casos resueltos. No hay forma de comparar técnicas. | `defensor._system` | Alta |
| P5 | **Sin evaluación autónoma reproducible.** No existe un lanzador de campañas con repeticiones, semilla, métricas e intervalos de confianza. Los hallazgos del README son de muestras de 2-26 rondas. | `README.md` §Hallazgos | Alta |
| P6 | **Sin registro de experimentos.** Los resultados reales viven en `data/*.jsonl` y en la BD de partida, sin id de experimento, versión de código, hash de prompt ni configuración. No se pueden comparar dos corridas. | — | Media |
| P7 | **Wazuh sin modos ni cliente.** Hay reglas y eventos, pero no hay `WAZUH_REAL / SIMULADO / DESACTIVADO`, ni cliente de API, ni panel. La UI no muestra en ningún sitio el estado de Wazuh. | `integraciones/wazuh/` | Media |
| P8 | **Prompt injection indirecta sin cubrir.** El filtro rápido mira el prompt del atacante. No hay ningún camino por el que entre documentación recuperada, así que hoy no hay superficie… pero la habrá en cuanto exista RAG (P4). | `filtro_rapido.py` | Media (alta tras P4) |
| P9 | **Interfaz sin sistema de diseño.** 13 tokens CSS, pero conviven emojis como iconos (📥 ⚠ 🗄 📤), pestañas en mayúsculas y una metáfora de escritorio con ventanas. No hay centro SOC, ni cronología unificada, ni correlación. | `ui/index.html`, `styles.css` | Media |
| P10 | **`server/app.py` tiene 1 821 líneas** y mezcla rutas, reglas de partida, emisión SSE y orquestación de batalla. Cada módulo nuevo que cuelgue de ahí lo empeora. | `server/app.py` | Media |
| P11 | El servidor escucha en `0.0.0.0` y la única autenticación es un token por **equipo**, no por persona. | `docs/DIAGNOSTICO.md` §4 | Media |

---

## 3. Riesgos técnicos y dependencias

- **Sin dependencias nuevas salvo justificación.** Hoy `requirements.txt` son 3 líneas (`ollama`, `fastapi`,
  `uvicorn`) y el motor usa solo la stdlib. Meter ChromaDB o FAISS por el RAG rompería esa propiedad por un
  corpus que son decenas de fragmentos: **se implementa el índice vectorial en la stdlib** (BM25 léxico +
  embeddings opcionales por la API de Ollama, coseno en Python puro). Decisión reversible: la interfaz del
  índice queda aislada en un módulo.
- **Hardware.** RTX 5060 de 8 GB. No se descarga ningún modelo nuevo sin comprobar antes VRAM/RAM/disco. Los
  modelos ya instalados en esta máquina se detectan en vivo por `/api/tags`.
- **Pruebas sin Ollama.** Toda prueba nueva debe pasar sin Ollama encendido y sin red; las que necesiten un
  modelo real van en una suite opcional aparte, nunca en `ejecutar_pruebas.py`.
- **No romper las 652.** Cada etapa se cierra ejecutando la batería completa.

---

## 4. Traducción del encargo a este repositorio

| Requisito del encargo | Decisión |
|---|---|
| §4 Diagnóstico determinista del **SQL** (parser, SQLGlot, JOIN, GROUP BY…) | **No aplica**: aquí no hay SQL generado por un LLM, y añadirlo sería destruir la propiedad de seguridad central. Se implementa el equivalente real: **diagnóstico determinista de la ronda** (por qué falló la defensa), con las 12 clases A-L adaptadas, evidencia, confianza y `DIAGNOSTICO_INDETERMINADO`. |
| §5 RAG | **Aplica tal cual**, sobre políticas de seguridad, catálogo, precedentes y casos resueltos. Matriz base / few-shot / RAG / few-shot+RAG. |
| §6 Harness | **Aplica tal cual.** Hoy las herramientas ya están acotadas (§1); falta la capa de presupuestos y observabilidad. |
| §7 Evaluación autónoma | **Aplica**, con los escenarios A-L traducidos a ataques/solicitudes en vez de preguntas de negocio. |
| §8 Laboratorio adversarial | **Aplica**; es el núcleo del proyecto. Se amplía con inyección indirecta vía RAG. |
| §9 Rojo vs Azul | **Ya existe** (`motor.py`, partida completa). Se añade lo que falta: modelo compartido explícito, semilla reproducible, campañas de 10-1000 rondas e intervalos de confianza. |
| §10 Wazuh | **Aplica**: faltan los 3 modos, el cliente de solo lectura y el panel. |
| §11 Experimentos | **Aplica**: registro central con id, hashes y comparador con bootstrap. |
| §12 Bitácora de aprendizaje | **No existe nada que depurar**: el sistema es determinista y sin aprendizaje (`REGLAS_EVENTO` son reglas fijas, revisadas a mano). No se inventa una bitácora de 17 lecciones que nunca existió. Se documenta la decisión. |
| §13 Contexto y temperatura | **Aplica** como experimento sobre el defensor. |
| §14 Optimización de N9 | **No aplica**: no hay N9 ni consultas costosas (SQL fijo sobre una BD de decenas de filas). |
| §15 Nuevos modelos | **Aplica** en la parte de comparación; sin descargas automáticas. |
| §16 Seguridad | **Aplica**: lo de DuckDB se traduce a comprobar que el repositorio sigue sin SQL libre y que las capas no se pueden eludir. |
| §17 Acceso remoto | Solo documentación de arquitectura; prioridad baja, como pide el encargo. |

---

## 5. Plan de implementación y orden

| Etapa | Entrega | Criterio de aceptación |
|---|---|---|
| **E0** Auditoría | Este documento + línea base 652/652 | Hecho |
| **E1** Diagnóstico determinista | `src/lab/diagnostico.py`: 12 clases, evidencia, confianza, determinista/heurístico, `DIAGNOSTICO_INDETERMINADO`; integrado en `motor` y exportable a JSON | Toda ronda produce un diagnóstico; infraestructura ≠ modelo ≠ lógica; pruebas propias; 652 siguen verdes |
| **E2** Harness | `src/lab/harness.py`: presupuestos (iteraciones, timeouts, tokens, llamadas), registro de herramientas, detección de bucles y de prompt repetido, cancelación, estado recuperable | Una ronda con presupuesto agotado termina de forma limpia y clasificada, nunca colgada |
| **E3** RAG | `src/lab/rag/`: corpus, troceado, índice (BM25 + embeddings opcionales), recuperación con umbral y top-k, registro de fragmentos usados, reconstrucción | Se puede activar y desactivar; se registra qué fragmentos entraron; el corpus no filtra respuestas de referencia |
| **E4** Evaluación autónoma | `src/lab/evaluacion/`: escenarios A-L, modos rápido/estándar/intensivo/estrés/comparativo, semilla, métricas con Wilson y bootstrap | Una campaña de N rondas es reproducible con la misma semilla y publica tamaño de muestra |
| **E5** Registro de experimentos | `src/lab/experimentos.py`: id, fecha, modelo, técnica, hashes, comparador | Comparar dos experimentos dice qué mejoró, qué empeoró y si la muestra basta |
| **E6** Laboratorio adversarial | Escenarios de inyección directa e indirecta (vía RAG), métricas TP/FP/FN | Los escenarios viven aislados del camino de producción |
| **E7** Wazuh | 3 modos, cliente de API de solo lectura, panel | El modo activo se ve siempre; un evento simulado nunca se presenta como real |
| **E8** Modelos, contexto y temperatura | Experimentos controlados | Ninguna conclusión con una sola ejecución |
| **E9** Interfaz | Sistema de diseño + Dashboard, Chat/Consola y Experimentos como pantallas de referencia; después SOC, cronología y correlación | Nada aparenta estar conectado si no lo está |

Cada etapa cierra con `python ejecutar_pruebas.py` y un commit propio.

## 6. Criterios de aceptación globales

Una funcionalidad está terminada cuando está implementada, tiene pruebas que pasan, tiene documentación,
registra evidencia, no rompe lo existente, se puede activar y desactivar, sus errores están clasificados, no
depende de respuestas ficticias y su ejecución se puede repetir.
