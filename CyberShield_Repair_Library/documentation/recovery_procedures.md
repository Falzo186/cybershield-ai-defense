# Procedimientos de recuperación
- **El servidor se reinició:** las sesiones viven en memoria; los participantes vuelven a entrar (la Sala lo pide). La base conserva correos, solicitudes y chat; la partida en memoria vuelve a PREPARACIÓN.
- **Ollama no responde:** `GET /api/salud` lo marca `degradado`; la partida sigue; reintenta `probar` desde la ventana de IA.
- **Una inferencia se queda colgada:** el árbitro finaliza (cancela y no cuenta) y empieza «Nueva partida».
- **Pantalla desactualizada:** el sondeo de respaldo (15 s) la corrige; recargar conserva la sesión (token en el navegador).
- **Correo duplicado por reintento:** enviar con `Idempotency-Key` (la UI nueva no lo necesita porque no reintenta automáticamente).
