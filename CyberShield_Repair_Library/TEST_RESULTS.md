# Resultados de pruebas (CyberShield Repair) — 2026-11-21
Todos medidos en esta máquina, sin números estimados. Comandos reproducibles desde la raíz del repositorio.

## Batería completa (`python ejecutar_pruebas.py`)
**44/45 suites en verde · 1 991/1 993 comprobaciones.** Línea base anterior (misión extra): 37/39 · 1 885/1 887. Suites añadidas: `test_solicitudes` (13), `test_chat` (10), `test_regresion_presentacion` (29), `test_ollama_controles` (7), `demo_academica` (17), `e2e_sala_equipo` (23); `test_partida` 73→80.

**Fallos y su explicación (ninguno es una regresión de la reparación):**
1. `e2e/test_combate_ui.py` · «cronología de 441 mensajes en < 4 s» da ≈6,1 s: **igual en `pre-mision-extra`**; rendimiento de la máquina (B-2 en `BLOQUEOS.md`). Abierto, no se relajó el umbral.
2. En esa misma suite, durante la corrida completa, falló una vez «el filtro por nivel mínimo funciona» (espera fija de 800 ms bajo carga); en 2 repeticiones aisladas pasó (40/41, solo el rendimiento). Intermitente por tiempo.

## Regresión de la presentación (contra el servidor real)
| Momento | PASS | FAIL | NO_IMPLEMENTADO | Total |
|---|---|---|---|---|
| Línea base (antes de reparar) | 17 | 3 | 6 | 26 |
| Final | **29** | 0 | 0 | 29 (26 del encargo + chat, correo libre, salud) |

## Otras
- Controles de Ollama (`test_ollama_controles.py`): 7/7 (respuesta tardía tras finalizar, Ollama caído, sin duplicados).
- Demostración de 17 pasos con 6 clientes simultáneos: 17/17 en ≈24 s, **en modo de prueba con Ollama falso etiquetado** (no mide ningún modelo real).
- E2E de la Sala de equipo con 3 navegadores a la vez: 23/23, consola limpia (salvo el 409 esperado de la acción en pausa), capturas 1366×768 y 1920×1080 en `tests/capturas/`.

## No probado
Ollama real durante la demo de 17 pasos (se probó la integración con el falso; los 8B reales se usaron en las misiones anteriores); varios dispositivos físicos distintos (se usaron varios navegadores/contextos en una máquina); carga con muchos jugadores; TLS.
