# Modelos / inferencias de Ollama
Config por equipo (`CONFIG_ROL`): modelo + host confirmados contra **su** Ollama (`probar`, `ia/defensor`, `ia/ataque`); host restringido a red local.
Una inferencia: solo ocurre por una acción explícita autorizada (nunca al entrar a una pantalla: regresión 2); timeout por ronda (`TIMEOUT_RONDA`), presupuesto de Harness, 1 reintento solo ante error técnico, cancelación al finalizar. Si Ollama no responde: error claro (409/503) y la partida sigue utilizable; no se inventa ninguna respuesta. Salud: `GET /api/salud`.
