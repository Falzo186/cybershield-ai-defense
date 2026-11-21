# Estado de la reparación — 2026-11-21
| Requisito (encargo) | Estado | Evidencia |
|---|---|---|
| La partida no se inicia sola; solo el árbitro | ✅ ya funcionaba | regresión 1, 4 |
| Pausar / reanudar / detener | ✅ corregido | regresión 19–21, `test_partida` |
| Participantes visibles y equipos | ✅ (API ya existía; pantalla nueva) | regresión 5–6, E2E Sala |
| Desconexiones reflejadas | ✅ corregido | regresión 8, E2E |
| Permisos por rol en backend | ✅ ya funcionaba | regresión 4, 7, 26 |
| Correos Rojo→Azul, bandeja, leído | ✅ (plantillas ya existían; libre añadido) | regresión 10, 11, 28 |
| Correos del escenario programados | ✅ añadido | regresión 9, demo 7 |
| Notificaciones y contador | ✅ añadido | regresión 12, E2E |
| Solicitudes de autorización | ✅ añadido (aprobación = decisión registrada, no ejecuta) | regresión 13–14, unit 13 |
| Ollama controlado (sin bucles/duplicados/tardías) | ✅ ya funcionaba; verificado | regresión 2, 16–18, `test_ollama_controles` |
| Chat de equipo | ✅ añadido | regresión 27, E2E |
| Registro/visor de eventos con filtros | ✅ (cronología existía; ampliada) | demo 17, E2E |
| Idempotencia | ✅ añadido (opt-in `Idempotency-Key`) | regresión 23 |
| Estados CANCELADA y ERROR de partida | ❌ no implementados | `REMAINING_ISSUES.md` |
| Buzón propio por cada jugador Azul | ❌ limitado (una identidad por equipo) | `REMAINING_ISSUES.md` |
| WebSockets | ⚠️ se usa SSE + sondeo (la arquitectura existente) | `documentation/architecture.md` |
