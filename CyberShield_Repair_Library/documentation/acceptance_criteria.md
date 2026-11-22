# Criterios de aceptación y su verificación
| Criterio del encargo | Verificado por |
|---|---|
| La partida no se inicia automáticamente | regresión 1, 4 |
| Participantes visibles / equipos | regresión 5, 6; E2E Sala |
| Jugadores interactúan | E2E Sala (solicitudes, chat, buzón); demo 17 pasos |
| Correos llegan; bandejas funcionales | regresión 9–11, 28; demo 7–9 |
| Solicitudes de autorización | regresión 13–14; unit 13 |
| Ollama controlado | regresión 2, 16–18; `test_ollama_controles` |
| Operaciones con resultado verificable | demo 13–14 |
| La interfaz refleja el backend | E2E Sala (SSE) |
| Acciones registradas | regresión 22; demo 17 |
| Errores recuperables | regresión 17; `test_ollama_controles` |
| Demo sin intervención manual | `demo_academica.py` 17/17 (modo de prueba); con Ollama real: pendiente |
