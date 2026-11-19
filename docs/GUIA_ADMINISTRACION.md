# Guía de administración

- **Árbitro**: el equipo `general` crea, interrumpe y exporta partidas. Entra con el código que el servidor imprime al arrancar (`CS_CODIGO_ARBITRO` para fijarlo). Cámbialo en cada sesión.
- **Una partida a la vez** en el servidor (una GPU). `Interrumpir` pide confirmación y deja la partida como `INCONCLUSA` (se excluye de las tasas).
- **Resultado**: lo escribe solo el motor. Si algo parece inconsistente, exporta el JSON de la partida y ejecuta `Almacen.verificar_cadena(id)`.
- **Datos**: `data/combate.db` (partidas, eventos con cadena de hashes), `data/wazuh_sim.db` y `data/wazuh_sim/alerts.ndjson` (alertas SIMULADAS), `data/campanas/combate-*/`
  (observaciones). Haz copia antes de borrar nada; nunca sobrescribas campañas históricas: crea `combate-v2`.
- **Modelos**: se leen de Ollama en vivo. Si `qwen3:8b`/`llama3.1:8b` no están instalados, usa modelos falsos para probar el motor.
- **Estados raros**: Ollama caído → la campaña espera hasta 10 min y se detiene reanudable (código 4); GPU llena → baja `num_ctx` en `modelos.py` o ejecuta en serie;
  proceso colgado → `--estado` muestra el PID y el último latido; no lances dos campañas con el mismo nombre/sufijo (el candado lo impide).
- **Seguridad**: ver `docs/SEGURIDAD.md`. No expongas el puerto ni Ollama fuera de tu red.
