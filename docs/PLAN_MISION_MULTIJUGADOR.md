# Plan de misión: partida multijugador 4 vs 4 y autorizaciones del Azul por votación

Estado revisado en el código el 2026-11-22. Todo es para la prueba y la presentación del proyecto integrador.

## Qué ya está cubierto y qué no
| Punto pedido | Estado | Evidencia / hueco |
|---|---|---|
| Hasta 4 Rojos y 4 Azules | CUBIERTO en reglas | `MAX_ROJO`/`MAX_AZUL` en `src/lab/nova/motor.py` (`TEAM_FULL`). **Nunca probado con 4+4 a la vez** (los e2e usan 1 Rojo y 2 Azules) |
| Panel con la lista de jugadores por equipo, solo nombres | PARCIAL | Existe en la sala de espera (`#lista-part`). No hay panel lateral plegable visible durante la partida, separado Rojo/Azul |
| Cualquier Rojo (no solo el host) dirige ataques | CUBIERTO por diseño, SIN PRUEBA | El actor sale de la sesión (`server/nova.py`, `nova_accion`): cualquier jugador Rojo ejecuta acciones y pide prompts a la IA. Falta una prueba con 2+ Rojos que actúen y no se pisen (presupuestos y contador de prompts son del equipo) |
| La autorización llega a todos los Azules | PARCIAL | `vista_azul` entrega todas las solicitudes a cada Azul. Falta el aviso emergente (diálogo) y que la solicitud de la IA Azul sea una **solicitud** con detalle: hoy `SOLICITAR_AUTORIZACION` crea solo una *tarea* de texto |
| Solo uno decide | CUBIERTO | Máquina de estados `TRANS_APROB`: el segundo recibe `INVALID_TRANSITION`. Pero decide quien llegue primero, sin opiniones |
| Detalle completo: qué pide, quién, credencial, prompt, hora | NO CUBIERTO | La solicitud guarda motivo, riesgo, recurso y hora, pero no el prompt/directiva ni la corrida de IA que la originó |
| Opiniones o votación | NO CUBIERTO | No existe |

## Diseño propuesto (decisión a confirmar)
**Votación con decisor:** todos los Azules ven la solicitud y votan Aceptar/Denegar con un comentario opcional; los votos son visibles. Decide el **primer jugador que votó** (decisor), pero solo puede cerrar la solicitud cuando haya mayoría o el tiempo expire; si hay empate, manda su voto. Alternativa más simple: opiniones sin voto y decide el primero que actúe. Recomiendo la votación con decisor porque cubre "todos opinan" y "solo uno manda".

## Pasos
1. **Prueba 4 vs 4 (primero, para encontrar fallos reales):** test del motor y del servidor con 4 Rojos y 4 Azules; Rojos 2, 3 y 4 ejecutan acciones; contador de prompts compartido; Azul 5 y Rojo 5 reciben `TEAM_FULL`.
2. **Panel de jugadores visible en toda la partida:** botón lateral que abre dos listas (Rojo / Azul), solo nombres y quién está conectado; el Rojo ve los nombres Azules sin su identidad asignada.
3. **Solicitud de autorización de la IA Azul como aprobación real:** cuando el veredicto es `SOLICITAR_AUTORIZACION`, el motor crea una aprobación (no una tarea) con: qué pide, quién lo origina, identidad y credencial enmascarada, directiva usada, id y proveedor de la corrida de IA, y hora de la partida y real.
4. **Votación:** `vote_request` (votar y comentar), cierre por mayoría, desempate por el decisor, expiración por `approval_ttl_s`, votos y comentarios en el registro de eventos. Aplicar también a la solicitud de acceso sospechoso.
5. **Aviso emergente (diálogo)** para todos los Azules cuando llegue una solicitud: detalle completo, botones de voto, contador de votos y cierre automático al resolverse. Debe funcionar con 4 navegadores.
6. **Pruebas:** motor (votos, empate, expiración, voto repetido, voto de un no Azul), servidor (403 para Rojo/espectador), e2e con 4 Azules (todos ven el diálogo; votos mixtos; solo el decisor cierra) y e2e 4 vs 4.
7. **Documentación:** `docs/NOVA.md`, auditoría (criterios 3, 5, 16, 17, 25, 26), guion de demo y D-32 en decisiones.

## Estimación y riesgos
- 6–8 h de trabajo mías con pruebas, sin necesitar la GPU ni Ollama.
- Riesgo: 8 navegadores a la vez en una sola máquina (usar 4 vs 4 en el motor y 2 vs 4 en el navegador).
- No verificado hasta probarlo: 8 personas reales en red local (criterio 33 sigue pendiente).
