# Nova con Ollama REAL en modo controlado (directivas)

Generado por `experimentos/prueba_ollama_directivas.py`: 16 partidas; un «humano» guionizado arma cada directiva y el 8B responde en modo `auto` (el motor valida). Datos crudos: `data/nova_ollama_directivas.json`.

| Modelo | Equipo | Directiva | Lanzadas | EJECUTADA | RECHAZADA (motor) | INVALIDA | FALLIDA | Ajustada por el motor | Latencia media (ms) |
|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b | RED | reconocer | 4 | 4 | 0 | 0 | 0 | - | 3834 |
| qwen3:8b | RED | correo | 4 | 4 | 0 | 0 | 0 | - | 2874 |
| qwen3:8b | RED | aleatoria_12Q | 4 | 4 | 0 | 0 | 0 | 0 | 2705 |
| qwen3:8b | RED | aleatoria_1234 | 4 | 4 | 0 | 0 | 0 | 4 | 2409 |
| qwen3:8b | RED | consulta_conocida | 4 | 4 | 0 | 0 | 0 | - | 2283 |
| qwen3:8b | RED | extraer_conocida | 4 | 4 | 0 | 0 | 0 | - | 2291 |
| qwen3:8b | BLUE | revocar_comprometida | 4 | 0 | 4 | 0 | 0 | - | 2941 |
| qwen3:8b | BLUE | denegar_sospechosa | 4 | 0 | 4 | 0 | 0 | - | 3946 |
| qwen3:8b | BLUE | libre_alerta | 4 | 0 | 4 | 0 | 0 | - | 3237 |
| qwen3:8b | BLUE | libre_general | 4 | 0 | 4 | 0 | 0 | - | 3226 |
| llama3.1:8b | RED | reconocer | 4 | 4 | 0 | 0 | 0 | - | 3061 |
| llama3.1:8b | RED | correo | 4 | 0 | 0 | 4 | 0 | - | 3206 |
| llama3.1:8b | RED | aleatoria_12Q | 4 | 4 | 0 | 0 | 0 | 4 | 1970 |
| llama3.1:8b | RED | aleatoria_1234 | 4 | 4 | 0 | 0 | 0 | 4 | 1386 |
| llama3.1:8b | RED | consulta_conocida | 4 | 0 | 0 | 0 | 4 | - | 0 |
| llama3.1:8b | RED | extraer_conocida | 4 | 0 | 0 | 0 | 4 | - | 0 |
| llama3.1:8b | BLUE | revocar_comprometida | 4 | 0 | 4 | 0 | 0 | - | 1683 |
| llama3.1:8b | BLUE | denegar_sospechosa | 4 | 1 | 3 | 0 | 0 | - | 2081 |
| llama3.1:8b | BLUE | libre_alerta | 4 | 1 | 3 | 0 | 0 | - | 1857 |
| llama3.1:8b | BLUE | libre_general | 4 | 3 | 1 | 0 | 0 | - | 1829 |

## Lectura y límites
- INVALIDA = el modelo no cumplió el esquema o cambió de acción respecto a la directiva (el motor la descarta). RECHAZADA = el motor la rechazó por sus reglas (credencial, permiso, presupuesto).
- «Ajustada por el motor» = la candidata de la credencial aleatoria no respetaba la estructura pedida y el motor la completó; mide cuánto hay que corregir al modelo, no su acierto.
- Muestras pequeñas y exploratorias; el humano es un guion fijo, no un jugador real. No mide calidad táctica.
