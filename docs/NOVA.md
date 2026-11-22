# Nova — escenario «Distribuidora Nova» (cobertura del paquete del profesor)

Implementado sobre el stack actual (Python/FastAPI + UI estática), **no** sobre React/TS/WebSocket del paquete (decisión: cubrir lo funcional; ver `docs/DECISIONES.md`). Todo es ficticio, local y de laboratorio.

| Pieza | Ruta |
|---|---|
| Escenario (6 identidades, 8 tablas, correos programados, modalidades) | `src/lab/nova/escenario.py` |
| Motor autoritativo (estados, credenciales, adivinación, exposición `lab://`, extracción, victoria, aprobaciones, tareas, mensajes) | `src/lab/nova/motor.py` |
| IA (proveedores etiquetados, anti-SSRF, esquemas JSON, modos off/assist/auto, `ai_runs`) | `src/lab/nova/ia.py` |
| API | `server/nova.py` (`/api/nova/...`) |
| UI por rol (admin, sala, Rojo, Azul, espectador, victoria) | `ui/nova/` |
| Pruebas | `src/lab/test_nova.py` (89), `src/lab/test_nova_ia.py` (27), `server/test_nova.py` (41), `e2e/test_nova_ui.py` (33) |

## Principios
- La IA **propone**; el motor **valida** (pipeline de 10 pasos); los humanos **deciden**. Nada del cliente ni de la IA fija el resultado.
- La partida **nunca inicia sola**: solo admin, con confirmación e `idempotency_key`.
- Victoria Roja solo por `extraction.completed` del motor; Azul por contención con continuidad ≥ 0,6; «rechazar todo» → EMPATE.
- Proveedor `ScriptedProvider` siempre etiquetado SIMULADO; Wazuh real = NO_CONFIGURADO (la capa simulada está etiquetada).

## Resultados con Ollama real (F20)
- v1 (sin esquema): qwen3:8b Rojo, 8 corridas, 0 válidas (`data/nova_ollama_real_v1_parcial.txt`).
- v2 (enumeraciones + JSON Schema): 100 % de corridas válidas en las partidas medidas (`docs/evaluacion/NOVA_OLLAMA_REAL_v2.md`). Mide validez estructural, no calidad táctica.

## Ejecutar
```
python ejecutar_pruebas.py
```
Arranque del servidor y UI: ver `docs/GUIA_INSTALACION.md`; la UI de Nova está en `/nova/`.
