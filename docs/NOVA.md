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

## Prompts de IA controlados (constructor por partes)
La IA **espera**: ningún modelo recibe un prompt por iniciativa propia. En modo `controlado` (por defecto) un jugador de ese equipo arma la directiva con listas desplegables y pulsa «Lanzar prompt»; solo entonces se llama al modelo.
- **Rojo:** acción, objetivo, estrategia, identidad, tabla, plantilla y credencial. La credencial puede ser `ninguna`, `conocida` (solo aparece desbloqueada en el combo una credencial que el Rojo ya obtuvo; el motor lo comprueba: `CREDENTIAL_NOT_KNOWN`) o `aleatoria` con estructura (hasta 5 dígitos iniciales y una letra). La IA inventa la candidata; si no respeta la estructura el motor la completa y lo anota (`candidata_ajustada_por_motor`).
- **Azul:** foco, sujeto (alerta, solicitud, identidad, correo) y acción preferida.
- Todo viene de catálogos cerrados; no hay texto libre. La directiva manda: si el modelo cambia de acción, la propuesta queda INVALIDA.
- **Oportunidades:** 10 por equipo (el admin las fija entre 1 y 50 al crear la partida). Un prompt lanzado gasta una; las directivas rechazadas no. Agotadas: `PROMPT_BUDGET_EXCEEDED`. Modo `libre` (sin tope) solo para ensayos y experimentos.
- **Acceso sospechoso:** un intento de adivinación casi correcto (≥ `near_miss_min` = 4 de 6 posiciones) abre al Azul una «solicitud misteriosa» con identidad, jugador posible y credencial enmascarada. **Aceptar** lo da por legítimo (−5 puntos Azul, se reinician los fallos); **Denegar** bloquea la identidad (+5). El Rojo no ve la solicitud ni la similitud.
- Pruebas: `src/lab/test_nova_prompts.py` (28), `server/test_nova.py` (50), `e2e/test_nova_ui.py` (37), hito 6b de `demo_nova`.
- Aún no medido con modelos reales: cómo cumplen los 8B las directivas (F20 v2 se midió sin directiva).
