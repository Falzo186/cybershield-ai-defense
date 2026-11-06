# Auditoría de integración — CyberShield AI Defense

Fecha: 06/11/2026 · Rama auditada: `main` en `29434f2` · Línea base de referencia: `39af796`

Este documento es la **Fase A** del encargo de integración. No propone nada que no se haya comprobado
antes contra el repositorio: cada fila de las tablas lleva el archivo y la línea donde se verificó, o la
orden que se ejecutó. Donde el encargo parte de una cifra que no coincide con el repositorio, se dice.

---

## 0. Discrepancias del encargo frente al repositorio

El encargo describe el estado de partida con cinco cifras. Tres coinciden, dos no.

| Afirmación del encargo | Estado real comprobado | Cómo se comprobó |
|---|---|---|
| Rama `feature/evolucion-tecnica` | **Ya fusionada** en `main` (`0f62862`, merge `--no-ff`) y subida a `origin/main`. La rama local sigue existiendo pero no es el frente de trabajo. | `git log --oneline 39af796..HEAD` |
| «Siete commits sobre `39af796`» | **Once**: 9 de etapa (`fde7dbb`…`657fa8f`), 1 de fusión (`0f62862`) y 1 de corrección documental (`29434f2`). | `git log --oneline 39af796..HEAD \| wc -l` |
| «30 suites y 1 187 comprobaciones» | **Correcto.** Reproducido hoy: `30/30 suites · 1187/1187`. | `python ejecutar_pruebas.py` |
| «Panel técnico con 11 pantallas» | **Correcto.** 11 bloques `class="vista"`. | `grep -c 'class="vista"' ui/panel/index.html` |
| «Avance aproximado del 82 %» | Es la cifra del informe anterior, calculada con pesos declarados en `INFORME_FINAL.md` §17. Se **recalcula** en este documento §5 con los criterios del nuevo encargo, que son más exigentes (piden integración, no solo implementación), y por eso baja. | lectura de `docs/INFORME_FINAL.md` |

### Auditoría documental pedida en §2

| Punto | Valor comprobado |
|---|---|
| Archivos creados | **43** (`git diff --name-status 39af796 29434f2 \| grep -c ^A`) |
| Archivos modificados | **10**: `.gitignore`, `PROGRESO.md`, `README.md`, `ejecutar_pruebas.py`, `integraciones/wazuh/test_reglas.py`, `server/app.py`, `src/lab/defensor.py`, `src/lab/motor.py`, `ui/index.html`, `ui/styles.css` |
| Volumen | 53 archivos, +15 980 / −49 líneas |
| Pruebas antes | 21 suites · 652 comprobaciones (`39af796`) |
| Pruebas después | 30 suites · 1 187 comprobaciones (`29434f2`) |
| Comparabilidad | Comparables: mismo ejecutor (`ejecutar_pruebas.py`), misma máquina, mismo intérprete. **No** son dos medidas del mismo conjunto: 9 suites son nuevas. El delta honesto es «+9 suites y +535 comprobaciones», no «las pruebas mejoraron». |
| Pruebas de código vs evaluación de IA | Separadas y así se mantienen. Las 1 187 usan el Ollama falso (`e2e/ollama_falso.py`) o dobles inyectados: miden el **camino del código**. La calidad de los modelos se mide con las campañas de `src/lab/evaluacion/`, que no forman parte de la batería. |

---

## 1. Matriz de funcionalidades

«Integrada» significa que la funcionalidad está en el camino que recorre una partida real o una ruta que
la interfaz usa, no que exista una clase o un endpoint que la llame.

| Funcionalidad | Implementada | Integrada | Probada | Evidencia | Pendiente |
|---|---|---|---|---|---|
| Motor de ronda Rojo/Azul | Sí | Sí | Sí | `src/lab/motor.py:166` · `server/app.py:1272` (`_correr_real`) | — |
| Seis capas deterministas | Sí | Sí | Sí | `filtro_rapido.py`, `defensor.py`, `herramientas.py`, `permisos.py`, `repositorio.py` · `test_motor` | — |
| Selección real de modelos (Rojo y Azul por separado) | Sí | Sí | Sí | `server/app.py:322` `/api/ollama/modelos`; `_registrar_lado` valida modelo **y** host contra la Ollama de cada equipo (`app.py:959`) | — |
| Estado de conexión, tiempo de inferencia, tokens | Sí | Sí | Sí | `_meta()` en `app.py:1132`; eventos `ataque`/`decision` llevan `tiempo_ms` y `tokens` | Tokens de **entrada** no se muestran en la UI de batalla |
| Distinción real / simulado / error | Sí | Sí | Sí | `origen: "ollama"`, `origen_decision`, evento `ronda_error`; `--p-simulado` reservado en el panel | — |
| Diagnóstico determinista por ronda | Sí | Sí | Sí | `src/lab/diagnostico.py` · se adjunta en `motor.procesar_defensa` y viaja en `decision` y `ronda_error` | — |
| **Harness de ejecución** | Sí | **No** | Sí (aislado) | `src/lab/harness.py` (288 líneas, 49 comprobaciones). Único consumidor real: `evaluacion/campana.py:133`. `grep harness server/app.py` → **0 coincidencias** | **Conectarlo a la partida: es el hueco principal** |
| RAG (BM25 + embeddings opcionales) | Sí | Parcial | Sí | `src/lab/rag/` · `defensor.analizar(tecnica=…)` lo acepta | La batalla siempre usa `tecnica="fewshot"`; no hay forma de elegir RAG en una partida |
| Evaluación autónoma (campañas) | Sí | Sí | Sí | `evaluacion/campana.py` · `/api/panel/campana` | Familia `generado` **vacía**; modo `estres` nunca ejecutado; campañas **no reanudables** |
| Registro de experimentos | Sí | Sí | Sí | `src/lab/experimentos.py` · `data/experimentos.jsonl` append-only | — |
| Laboratorio adversarial | Sí | Parcial | Sí | `src/lab/adversarial.py` (28 casos) · `/api/panel/adversarial` | Solo se mide la **detección determinista**. `evaluar_cumplimiento` existe (`adversarial.py:178`) pero **ninguna campaña lo ejecuta**; la capacidad del atacante no se mide |
| Wazuh tres modos | Sí | Sí | Sí | `src/lab/wazuh/` · `/api/panel/soc/alertas` | Lectura de alertas del **indexador** no implementada (lo dice el propio código: `wazuh/__init__.py:94`) |
| Correlación de incidentes | Sí | Sí | Sí | `src/lab/correlacion.py` · `/api/panel/soc/correlacion` | No incluye eventos del harness (no existen todavía) |
| Misiones del equipo Azul | Sí | Sí | Sí | `repositorio.py:662-740`; estados `pendiente/bloqueada/vencida/completada`, dependencias, plazo, evidencia, puntos · `test_misiones` | Falta `en_progreso` y `cancelada` como estados explícitos |
| Consecuencias y estado del escenario | Sí | Sí | Sí | `completar_misiones_evento`, `incidentes`, `credenciales/revocar`, enlaces `/l/{id}` · `test_incidentes` | — |
| Persistencia e historial de partidas | Sí | Sí | Sí | `/api/partidas`, `/api/cronologia?partida=`, `/api/resultados?partida=` | Repetición explícita de una partida como nueva ejecución |
| Roles (árbitro, rojo, azul, espectador) | Sí | Sí | Sí | `server/partida.py` · middleware `app.py:143-171`: espectador solo GET | Autenticación **por persona** (hoy el token identifica, no autentica con secreto propio) |
| Cronología consultable | Sí | Sí | Sí | `/api/cronologia` con filtros y visibilidad por fase (`informe.visible_para`) | Eventos del harness |
| Panel técnico (11 pantallas) | Sí | Sí | Sí | `ui/panel/` · `server/panel.py` (16 rutas) · `test_panel` 57/57 | — |
| **Sistema de diseño en la UI de batalla** | Sí (en el panel) | **No** | — | `ui/panel/panel.css` tiene el sistema de tokens; `ui/styles.css` (745 líneas) es anterior y no lo usa | **Aplicar el lenguaje visual a la partida** |
| TLS y gestión de secretos | Parcial | — | — | Credenciales de Wazuh solo por entorno (`wazuh/cliente.py:8`); no hay secretos versionados (comprobado con `git grep`) | TLS para despliegue en red |

### Lo que no encontré y conviene saber

- **Sin dependencias circulares** entre los módulos nuevos: `harness` importa `motor`, y `motor` no importa
  `harness`. Por eso la integración de la Fase B tiene que hacerse desde `motor` hacia `harness` con
  cuidado, o desde el servidor.
- **Sin lógica duplicada relevante** salvo una: `_tiene_derecho` está en `motor.py:14` y en `harness.py`
  (importado desde `motor`). Correcto, no duplicado.
- `server/app.py` tiene **1 830 líneas** y 50 rutas. Es el archivo con más responsabilidades del proyecto y
  el que más riesgo de regresión concentra. No lo voy a partir en esta fase: partirlo es un cambio de alto
  impacto sin beneficio funcional, y la batería que lo protege (`test_app` 157 comprobaciones) está
  escrita contra sus rutas, no contra su estructura interna.

---

## 2. Diagnóstico breve

El proyecto **no** tiene un problema de funcionalidad ausente: tiene un problema de **acoplamiento
insuficiente** entre módulos que funcionan. Tres huecos son reales y verificables:

1. **El harness no controla ninguna partida.** Existe, está probado y se usa en las campañas, pero la
   batalla real llama a `motor.ejecutar_ronda` directamente. Consecuencia concreta: una partida no tiene
   techo de llamadas al modelo, no detecta que el atacante repite el mismo prompt, y su cancelación
   depende de `asyncio.CancelledError` en vez de un presupuesto observable.
2. **El laboratorio adversarial mide el filtro, no el modelo.** El 78,9 % publicado es la detección
   determinista. La resistencia del defensor IA y la capacidad del atacante no se han medido nunca, y el
   encargo pide separarlas explícitamente (§8 A/B/C).
3. **El sistema de diseño se quedó en el panel.** La pantalla que un usuario ve primero —la partida— sigue
   con la hoja de estilos anterior.

Y dos limitaciones que no son defectos sino falta de infraestructura, declaradas como tales:

4. **Wazuh real no se puede probar**: no hay instalación en esta máquina. El cliente está escrito y sus
   contratos están probados con transporte sustituido; lo que falta es la lectura del indexador y una
   prueba que solo pueda ejecutarse cuando exista un Wazuh.
5. **Las campañas grandes (n ≥ 200) no caben en una sesión**: la inferencia es por CPU (no hay GPU
   utilizable; `nvidia-smi` no existe en esta máquina y la gráfica es una Radeon integrada de 2 GB). Una
   campaña de 200 × 4 condiciones son horas. Sin reanudación, cualquier interrupción tira el trabajo.

---

## 3. Plan priorizado

El orden sigue las fases del encargo, salvo que adelanto la reanudación de campañas (Fase E) porque de
ella depende que se pueda medir cualquier cosa con muestras serias.

| # | Fase | Qué se hace | Criterio de aceptación |
|---|---|---|---|
| 1 | **B** | Presupuesto de partida y harness en el camino de la batalla. `motor.ejecutar_ronda` acepta presupuesto; `_correr_real` crea un control por partida; el consumo se emite por SSE. | Una partida con techo de llamadas se corta sola y lo dice; una denegación de permiso **no** se reintenta; prueba que lo demuestra en el camino de la batalla, no en el harness aislado. |
| 2 | **E1** | Campañas reanudables por lotes: estado en disco, reanudación por id, sin repetir trabajo hecho. | Una campaña interrumpida se reanuda y produce el mismo plan; el conteo no se duplica. |
| 3 | **E2** | Familia `generado` con escenarios derivados de forma determinista; medición de **cumplimiento del defensor** y de **objetivo del atacante** por separado. | `generado` produce escenarios verificables y reproducibles por semilla; el informe distingue detección del filtro / resistencia del modelo / éxito del atacante, con precisión, recall, F1 e IC. |
| 4 | **D** | Catálogo explícito de escenarios de empresa con objetivos, reglas y condiciones de victoria; estados `en_progreso` y `cancelada` en misiones. | Un escenario declara sus objetivos y criterios; el motor los evalúa; transiciones probadas. |
| 5 | **G** | Lenguaje visual del panel aplicado a la pantalla de batalla, sin tocar su comportamiento. | La E2E de navegador (106 comprobaciones) sigue en verde después del rediseño. |
| 6 | **F** | Lectura de alertas del indexador en modo real + prueba de integración ejecutable solo con Wazuh disponible + requisitos de instalación documentados. | Con Wazuh ausente: error visible, nunca datos simulados. Con Wazuh presente: la prueba se ejecuta. |
| 7 | **H** | Autenticación por persona y TLS documentado. | Un participante no puede usar el token de otro; el despliegue en red documenta su TLS. |

Las fases 6 y 7 quedan **parcialmente bloqueadas por infraestructura** (no hay Wazuh ni certificados en
esta máquina). Se entregan preparadas y documentadas, no fingidas como validadas.

---

## 4. Riesgos de esta fase

| Riesgo | Mitigación |
|---|---|
| Meter el harness en la batalla cambia el consumo de inferencia y puede volver lentas las partidas | El presupuesto por defecto permite **un** paso por ronda: el comportamiento por defecto es idéntico al actual. El reintento solo ocurre si se pide. |
| Tocar `server/app.py` rompe la partida | La batería incluye 157 + 43 + 106 comprobaciones sobre ese camino. Se ejecuta completa después de cada bloque. |
| Rediseñar `ui/styles.css` rompe la E2E de navegador | La E2E selecciona por `id` y por texto, no por clase de estilo. Se ejecuta antes y después. |
| Medir cumplimiento del modelo consume horas de CPU | Se mide con muestras pequeñas y se publica el intervalo de confianza; un resultado no concluyente se declara no concluyente. |

---

## 5. Fórmula de avance

El encargo (§19) prohíbe estimar el avance «por impresión». La fórmula es:

```
avance = Σ(peso_i × cumplimiento_i) / Σ(peso_i)
```

donde `cumplimiento_i ∈ {0, 0.5, 1}` según los criterios de aceptación de §18 del encargo:
**1** = implementado, integrado y probado · **0.5** = implementado pero no integrado, o integrado sin
prueba · **0** = ausente. Los pesos están fijados *antes* de medir, para que no se puedan ajustar al
resultado.

| Criterio de §18 | Peso | Cumplimiento al inicio de esta fase | Razón |
|---|---|---|---|
| Partida completa entre dos modelos reales | 10 | 1 | `_correr_real` + E2E |
| Selección independiente de modelos Rojo/Azul | 6 | 1 | `_registrar_lado` valida ambos |
| Acciones dentro de un escenario ficticio | 6 | 1 | buzón, apps, documentos, enlaces |
| Validación de acciones por el motor | 10 | 1 | seis capas |
| Misiones defensivas funcionales | 8 | 1 | `repositorio.misiones` + pruebas |
| Consecuencias verificables | 8 | 1 | `completar_misiones_evento`, incidentes |
| Diagnóstico de cada ronda | 6 | 1 | `diagnostico.diagnosticar` en todas las rondas |
| **Harness integrado** | 8 | **0** | no está en el camino de la partida |
| Persistencia de partidas | 6 | 1 | `partidas_finalizadas` |
| Cronología consultable | 6 | 1 | `/api/cronologia` |
| **Evaluación adversarial del defensor** | 8 | **0** | solo se mide el filtro |
| **Evaluación del objetivo del atacante** | 6 | **0** | no se mide |
| Panel coherente con la partida | 6 | 0.5 | el panel existe; la batalla no comparte su lenguaje |
| Vista de espectador de solo lectura | 4 | 1 | middleware probado |
| Separación real / simulado | 6 | 1 | etiquetado en ambos sentidos |
| **Wazuh real probado o limitación documentada** | 6 | 0.5 | documentada; falta el indexador y la prueba condicional |
| Batería completa en verde | 8 | 1 | 1 187/1 187 |
| Documentación actualizada | 4 | 1 | 11 documentos |

**Σ pesos = 122 · Σ(peso × cumplimiento) = 93 → avance al inicio de esta fase = 76,2 %.**

Es menor que el 82 % del informe anterior y no porque el proyecto haya empeorado: los criterios de §18
son más exigentes que los que usé entonces, porque exigen integración y medición del modelo, no solo
implementación. La cifra del informe anterior sigue siendo correcta *bajo sus propios pesos*, que están
publicados en `INFORME_FINAL.md` §17. No se reescribe.
