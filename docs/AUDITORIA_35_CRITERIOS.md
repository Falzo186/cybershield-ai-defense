# Auditoría de los 35 criterios (01_PROMPT_MAESTRO §30)

Estados: **APROBADO** (operación real + prueba sobre estado + ruta), **PARCIAL**, **NO VERIFICADO**. Es una autoauditoría; no la revisó el profesor. Stack: Python/FastAPI + UI estática (no React/TS/WebSocket; SSE + sondeo).

| # | Criterio | Estado | Evidencia / nota |
|---|---|---|---|
| 1 | Admin crea partida | APROBADO | `server/test_nova.py`, `e2e/test_nova_ui.py` |
| 2 | Jugadores entran | APROBADO | `server/test_nova.py`, e2e 5 navegadores |
| 3 | Aparecen conectados | APROBADO | Latido automático cada 5 s desde el navegador; sin latido 20 s = desconectado (`src/lab/test_nova_multijugador.py`, `server/test_nova.py`, `e2e/test_nova_multijugador_ui.py`: 6 puntos verdes) |
| 4 | Se ve el equipo de cada jugador | APROBADO | `src/lab/test_nova.py`, `e2e/test_nova_ui.py` |
| 5 | Roles respetados en backend | APROBADO | `WRONG_TEAM`/403 en `server/test_nova.py`, `src/lab/test_nova.py` |
| 6 | Sala de espera | APROBADO | estados CONFIGURACION→SALA_DE_ESPERA→LISTA en `test_nova.py` |
| 7 | No inicia automáticamente | APROBADO | `test_nova.py` (solo admin + confirm + idempotency_key) |
| 8 | Admin inicia | APROBADO | `test_nova.py`, e2e |
| 9 | Admin pausa | APROBADO | `test_nova.py` (EN_CURSO↔PAUSADA) |
| 10 | Admin reanuda | APROBADO | `test_nova.py` |
| 11 | Admin detiene | APROBADO | DETENIENDO→FINALIZADA/CANCELADA en `test_nova.py` |
| 12 | Sin ejecuciones ocultas tras detener | APROBADO | `cancelar_todo` de IA + respuestas tardías ignoradas, `test_nova_ia.py` |
| 13 | Red/Blue con Ollama configurables | APROBADO | `ia.py` `configurar`; medido con modelos reales en `docs/evaluacion/NOVA_OLLAMA_REAL_v2.md` |
| 14 | Modelos en computadoras distintas | NO VERIFICADO | Endpoint configurable (anti-SSRF lo restringe); nunca probado con dos PCs reales |
| 15 | UI identifica endpoints y estados reales | PARCIAL | Línea por equipo con modo, proveedor etiquetado, endpoint, modelo y conexión real de Ollama (`e2e/test_nova_ui.py` prueba la rama SIMULADO; la rama Ollama en pantalla no tiene prueba e2e) |
| 16 | Rojo coordina operaciones | APROBADO | mensajería/tareas/misiones, `test_nova.py`, e2e |
| 17 | Azul coordina defensas | APROBADO | idem |
| 18 | Credenciales ficticias funcionales | APROBADO | `^[0-9]{5}[A-Z]$`, adivinación limitada, `test_nova.py` |
| 19 | Bandeja de correos funcional | APROBADO | `test_nova.py`, e2e |
| 20 | Correos a destinatarios correctos | APROBADO | `test_nova.py` (correos programados y del Rojo) |
| 21 | Alertas derivadas de eventos | APROBADO | `TRANS_ALERTA`, `test_nova.py` |
| 22 | IA propone acciones | APROBADO | `test_nova_ia.py`; real con 8B en F20 v2 |
| 23 | Motor valida | APROBADO | `validar_propuesta_*`, pipeline, `test_nova_ia.py` |
| 24 | Consecuencias en el escenario | APROBADO | `test_nova.py` |
| 25 | Azul solicita autorización humana | APROBADO | SOLICITAR_AUTORIZACION → tarea humana, `test_nova_ia.py` |
| 26 | Humanos aprueban/rechazan | APROBADO | `test_nova.py`, e2e |
| 27 | Decisiones modifican estado | APROBADO | `TRANS_APROB`, `test_nova.py` |
| 28 | Espectadores observan | APROBADO | e2e (vista sin acciones) |
| 29 | Victoria justa | APROBADO | W1/W2, contención, empate; `test_nova.py` |
| 30 | Resultados guardados | APROBADO | historial de partidas en `server/test_nova.py` |
| 31 | Historial consultable | APROBADO | idem |
| 32 | E2E pasan | PARCIAL | Batería completa: 51/52 suites, 2248/2249; `e2e/test_nova_ui.py` 33/33. Falla solo un umbral de tiempo de `e2e/test_combate_ui.py` (cronología de 441 mensajes en 6,1 s frente a 4 s), del combate previo, no de Nova |
| 33 | Red local | NO VERIFICADO | Solo localhost; no probado entre equipos |
| 34 | Procedimiento de instalación | APROBADO | `docs/GUIA_INSTALACION.md` (sección Nova); la red local sigue sin verificar (33) |
| 35 | Ensayo de demo reproducible | APROBADO | `src/lab/demo_nova.py` (9 hitos, determinista, en la batería) + `docs/GUION_DEMO.md` |

Resumen: 31 APROBADO, 2 PARCIAL (15, 32), 2 NO VERIFICADO (14, 33). 8 personas reales en red local: NO VERIFICADO.
