# Problemas pendientes (CyberShield Repair)
1. **Buzón compartido por equipo:** el buzón es el de **una** identidad semilla de Azul (`USUARIO_EQUIPO["azul"]`); todos los jugadores Azul ven los mismos correos (la lectura sí es por participante). Falta una identidad por jugador y destinatario elegible. Alcance medio: toca asignación de identidades, misiones y puntaje.
2. **Estados `CANCELADA` y `ERROR` de partida y la transición explícita «detener sin finalizar»:** hoy una partida se finaliza (con ganador) o vence; no hay cancelación sin resultado ni estado de error persistente.
3. **WebSocket:** se mantiene SSE (`/api/eventos`) + sondeo de respaldo cada 15 s; funciona en tiempo real pero no es WebSocket bidireccional.
4. **Aprobar una solicitud no ejecuta ninguna operación** (por diseño: no salta capas); si se quiere que la aprobación humana habilite una acción concreta, falta el re-validado del motor.
5. **Prueba con Ollama real** de la demo de 17 pasos y con varios dispositivos físicos; prueba de carga.
6. **`test_combate_ui` rendimiento (B-2)** y su espera fija de 800 ms en el filtro Wazuh (intermitente bajo carga).
7. **Causa del «exit code 4»** (misión extra) sigue sin demostrarse.
8. **Comparación con CyberShield Rebuilt:** no hay en este repositorio ningún dato de esa ruta; ver `REPAIR_FINAL_REPORT.md`.
