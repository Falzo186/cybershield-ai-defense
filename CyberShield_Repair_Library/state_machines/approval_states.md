# Máquina de estados · Solicitud de autorización (`components/approvals/solicitudes.py`)
`PENDIENTE → APROBADA | RECHAZADA | EXPIRADA | CANCELADA`. Solo se sale de PENDIENTE y una vez (`409` después).
| Transición | Evento | Actor | Efectos |
|---|---|---|---|
| →PENDIENTE | crear | Rojo (`POST /api/autorizaciones`) o el defensor IA al responder SOLICITAR_AUTORIZACION | recomendación con origen **etiquetado** (`reglas` o `ia`); vence a los 120 s de **tiempo de partida** (se congela en pausa) |
| →APROBADA / RECHAZADA | aprobar / rechazar | jugador de Azul | registra quién y cuándo; **no ejecuta nada**: el motor y las capas siguen validando |
| →CANCELADA | cancelar | quien la creó o el árbitro | registra quién |
| →EXPIRADA | vencer | sistema | nunca queda pendiente indefinidamente (también se difunde por SSE) |
Pruebas: `tests/unit/test_solicitudes.py` (13), regresión 13–14, E2E de la Sala.
