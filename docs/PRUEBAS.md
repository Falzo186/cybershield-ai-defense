# Pruebas (misión 23 h)

| Fecha | Comando | Commit | Resultado |
|---|---|---|---|
| 2026-11-18 | `python ejecutar_pruebas.py --rapido` (línea base, tras instalar fastapi y reconstruir `eventos_ejemplo.jsonl`) | 4dbdb35 + correcciones | 33/33 suites · 1 581/1 581 |
| 2026-11-19 | `python ejecutar_pruebas.py` (batería completa, con navegador) | aba15af | **38/38 suites · 1 850/1 850** (0 falladas, 0 omitidas por la batería) |
| 2026-11-19 | `python e2e/prueba_real_8b.py` (E2E con `qwen3:8b` vs `llama3.1:8b` reales) | 55fecbc | VICTORIA_AZUL, cadena íntegra, consola sin errores |

Suites nuevas: `src/lab/test_combate.py` (70), `src/lab/test_wazuh_sim.py` (19), `server/test_combate.py` (33), `e2e/test_combate_ui.py` (41).
Cobertura (coverage.py, módulos nuevos `combate/` y `wazuh_sim/`, pruebas unitarias): **91 %** (motor 94 %, modelos 96 %, store 94 %, wazuh_sim 92 %; `jugar.py` 59 %: la ruta CLI `main()` no se prueba).

**Omitidas, con motivo:** prueba de humo contra un Wazuh real (no hay `WAZUH_URL`); `integraciones/wazuh/test_indexador_real.py` (condicional, sin instancia).
**Separación:** las pruebas con modelos falsos (motor, API, UI) NO prueban a Ollama; la integración real se verifica con `e2e/prueba_real_8b.py` y con las campañas (≈ 9 700 llamadas reales). Una prueba con un servidor HTTP de guion cubre el parser, los reintentos y los errores de `RojoOllama`/`AzulOllama`.

## Casos de combate representativos (deterministas)
Victoria Roja · victoria Azul · empate · empate degradado («RECHAZAR siempre» no gana) · Rojo falla (mensaje fijo) · Azul falso positivo · Azul deja pasar amenaza (APROBAR siempre) · partida interrumpida · presupuesto agotado · modelo sin respuesta (Rojo y Azul) · hash de escenario violado · doble resultado (409 y rechazo de la BD) · cadena de hashes alterada · respuesta malformada ≠ aprobación · contexto mutado por un modelo · UI sin victoria prematura.
**Seguridad:** espectador solo lectura (403), Rojo no recibe Wazuh ni zonas, verdad de fondo oculta, escenario congelado (409). **Regresión:** buzón, PDFs, misiones, marcador, cierre y escritorio siguen en verde (`demo_partida` 106/106).

---
## Misión extra (2026-11-21)
| Fecha | Qué | Resultado |
|---|---|---|
| 2026-11-21 | `python ejecutar_pruebas.py` (batería completa) en `mision-extra` | **37/39 suites · 1 885/1 887** (línea base anterior: 38/38 · 1 850/1 850; +2 suites en la batería y +37 comprobaciones: `test_combate` 70→78, `e2e/test_combate_extra.py` 29) |
| 2026-11-21 | Tras el arreglo de la carrera de `demo_partida.py` | `demo_partida` 106/106 (3 de 3 ejecuciones); `test_combate_extra` 29/29 |

**Las 2 comprobaciones que fallaron, explicadas (no son regresiones del código de la misión):**
1. `e2e/demo_partida.py` (105/106): carrera **preexistente** en la prueba. La vista del espectador recibe el «defensor verificado» por sondeo y la prueba no esperaba. Se reprodujo **también en `pre-mision-extra`** (105, 105, 106 en tres ejecuciones). Arreglo: se añadió una espera antes de la aserción (la aserción no cambió). Resultado posterior: 106/106 ×3.
2. `e2e/test_combate_ui.py` (40/41): «cronología de 441 mensajes en < 4 s» da 6,1 s. **También 6,1 s en `pre-mision-extra`**: la máquina está hoy más lenta que el 19/11 (cuando midió <4 s). No se relajó el umbral; **queda como fallo abierto de entorno** (ver `BLOQUEOS.md`).

Suites nuevas: `e2e/test_combate_extra.py` (29: curadas, reproducción, guion determinista con etiqueta permanente, consola limpia) y 8 pruebas en `src/lab/test_combate.py` (huella de v2, sufijo `@v3`, v3 sin verdad de fondo).

---
## Misión Caminos (2026-11-21)
| Fecha | Qué | Resultado |
|---|---|---|
| 2026-11-21 | `python ejecutar_pruebas.py` (batería completa, rama `mision-caminos`) | **42/42 suites · 1 953/1 953** (línea base de la misión extra: 37/39 · 1 885/1 887; +3 suites y +66 comprobaciones: `test_caminos` 25, `test_caminos_auto` 17, `e2e/test_simulacion_ui` 24). `test_combate_ui` pasó 41/41: el umbral de rendimiento que fallaba el 19-21/11 (B-2) pasó esta vez con la máquina descargada, **sin cambiar el umbral**; el resultado depende de la carga. |

Cobertura nueva: un guion por cada una de las 16 hojas (×3 variantes) con cadena íntegra; determinismo por semilla; resultado único e inmutable (409 después); grafo congelado por hash; victoria sin evidencia de estado = ERROR_TECNICO; opciones inválidas e INCONCLUSA; filtro de código en mensajes; visibilidad (el Rojo no ve la validez, el Azul no ve el inventario); lockout, honeytoken, credencial válida sin señales, «rechazar siempre» = empate degradado; lanzar desde la UI (403 sin árbitro); reproducción acelerada completa con resultado oculto hasta su evento; consola limpia. **No prueban la calidad de ningún modelo**: eso lo mide la campaña (`docs/evaluacion/INFORME_CAMINOS.md`).
