# REGRESSION_TEST_RESULTS

Batería completa (`python ejecutar_pruebas.py`) tras el rediseño: **57/57 suites en verde · 2417/2417 comprobaciones**.

| Suite | Resultado | Cubre |
|---|---|---|
| `src.lab.test_nova` | 99/99 | motor: estados, acciones Rojo/Azul, credenciales, correos, NPC por dificultad, monitor de sospecha, resumen, victorias, aprobaciones |
| `src.lab.test_nova_ia` / `_prompts` / `_multijugador` | 27 / 30 / 40 | IA, directivas, 4v4, votación |
| `src.lab.demo_nova` | 10/10 hitos | recorrido de punta a punta |
| `server/test_nova.py` | 67/67 | API: roles, práctica, presupuesto visible, monitor Azul, resumen, explicación sin modelo, Ollama (tope 8B, solo admin/local), dificultad inválida |
| `e2e/test_nova_ui.py` | 40/40 | interfaz con varios navegadores: sala, correo→enlace→exposición, elevación, victoria, pausa, IA asistida, espectador |
| `e2e/test_nova_multijugador_ui.py` | 17/17 | 1 admin + 2 Rojos + 4 Azules en tiempo real |
| `e2e/test_nova_ux.py` (nuevo) | 28/28 | misión guiada, límites, mensajes claros, tarjeta de IA, monitoreo Azul, solicitudes, resumen, práctica, espectador, responsive 390/768 px, consola limpia |

## Mapa con la lista de validación pedida
| # | Área | Dónde se verificó |
|---|---|---|
| 1 | Inicio manual | `test_nova`, `test_nova_ux` (botón de siguiente paso del admin) |
| 2 | Participantes y equipos | `test_nova_multijugador*`, `test_nova_ui` |
| 3–4 | Acciones Rojo / Azul | `test_nova`, `test_nova_ux` |
| 5–6 | Correos y NPC | `test_nova` (dificultad, reportado⇒ignorado, defensas, visibilidad) |
| 7 | Credenciales | `test_nova` (sin cascada, sin secretos en `empleados`), `test_nova_ui` |
| 8–9 | Solicitudes y aprobaciones | `test_nova`, `server/test_nova`, `test_nova_ux` |
| 10–11 | Extracciones y victoria | `test_nova`, `test_nova_ui`, `test_nova_ux` |
| 12 | Modo práctica | `server/test_nova`, `test_nova_ux` |
| 13 | Espectador | `test_nova_ui`, `test_nova_ux` (sin credenciales ni controles) |
| 14 | Ollama conectado | **Verificado a mano**: encender/listar/apagar por la API. No se corrió una partida con `qwen3:4b` en la interfaz nueva |
| 15 | Ollama desconectado | `test_nova_ux` (sin errores de socket) y `server/test_nova` (estado) |
| 16 | Pausa y reanudación | `test_nova_ui` |
| 17 | Logs / eventos | `test_nova`, `test_nova_ui` |
| 18 | Responsive | `test_nova_ux` (390 px y 768 px sin desplazamiento horizontal) |

## Cambios en pruebas existentes (todos intencionales)
- `test_nova`: la extracción de `empleados` ya no expone todas las credenciales (se reescribió la comprobación); el camino alternativo W2 expone cada credencial antes de extraer; `nueva()` fija `click_prob_unconnected=1.0` para pruebas deterministas.
- `server/test_nova`: las partidas de prueba fijan `click_prob_unconnected=1.0`.
- e2e: textos «Validada», «Revocada» y botón «Ejecutar» en lugar de los anteriores; el constructor avanzado se abre antes de usarlo.

## No cubierto / pendiente
- Una partida con IA Ollama real (4B) sobre la interfaz nueva.
- Jugadores en dos PC distintas (criterios 14 y 33 de la auditoría).
- `e2e/test_combate_ui.py` falló por tiempo en la corrida anterior a este rediseño y pasó en esta: es una prueba sensible al tiempo, no se relaciona con Nova.
