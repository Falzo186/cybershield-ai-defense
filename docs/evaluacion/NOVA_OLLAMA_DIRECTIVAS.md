# Nova con Ollama REAL en modo controlado (directivas)

Generado por `experimentos/prueba_ollama_directivas.py`: 16 partidas; un «humano» guionizado arma cada directiva y el 8B responde en modo `auto` (el motor valida). Datos crudos: `data/nova_ollama_directivas.json`.

| Modelo | Equipo | Directiva | Lanzadas | EJECUTADA | RECHAZADA (motor) | INVALIDA | FALLIDA | Ajustada por el motor | Latencia media (ms) |
|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b | RED | reconocer | 4 | 4 | 0 | 0 | 0 | - | 1806 |
| qwen3:8b | RED | correo | 4 | 4 | 0 | 0 | 0 | - | 2826 |
| qwen3:8b | RED | aleatoria_12Q | 4 | 4 | 0 | 0 | 0 | 0 | 2412 |
| qwen3:8b | RED | aleatoria_1234 | 4 | 4 | 0 | 0 | 0 | 4 | 2190 |
| qwen3:8b | RED | consulta_conocida | 4 | 4 | 0 | 0 | 0 | - | 2196 |
| qwen3:8b | RED | extraer_conocida | 4 | 4 | 0 | 0 | 0 | - | 2199 |
| qwen3:8b | BLUE | revocar_comprometida | 4 | 4 | 0 | 0 | 0 | - | 2878 |
| qwen3:8b | BLUE | denegar_sospechosa | 4 | 4 | 0 | 0 | 0 | - | 3218 |
| qwen3:8b | BLUE | libre_alerta | 4 | 0 | 4 | 0 | 0 | - | 2951 |
| qwen3:8b | BLUE | libre_general | 4 | 0 | 4 | 0 | 0 | - | 2904 |
| llama3.1:8b | RED | reconocer | 4 | 4 | 0 | 0 | 0 | - | 2437 |
| llama3.1:8b | RED | correo | 4 | 4 | 0 | 0 | 0 | - | 3279 |
| llama3.1:8b | RED | aleatoria_12Q | 4 | 4 | 0 | 0 | 0 | 4 | 1585 |
| llama3.1:8b | RED | aleatoria_1234 | 4 | 4 | 0 | 0 | 0 | 4 | 1407 |
| llama3.1:8b | RED | consulta_conocida | 4 | 4 | 0 | 0 | 0 | - | 1565 |
| llama3.1:8b | RED | extraer_conocida | 4 | 4 | 0 | 0 | 0 | - | 1574 |
| llama3.1:8b | BLUE | revocar_comprometida | 4 | 4 | 0 | 0 | 0 | - | 1744 |
| llama3.1:8b | BLUE | denegar_sospechosa | 4 | 4 | 0 | 0 | 0 | - | 1727 |
| llama3.1:8b | BLUE | libre_alerta | 4 | 1 | 3 | 0 | 0 | - | 1797 |
| llama3.1:8b | BLUE | libre_general | 4 | 2 | 2 | 0 | 0 | - | 1870 |

## Lectura y límites
- INVALIDA = el modelo no cumplió el esquema o cambió de acción respecto a la directiva (el motor la descarta). RECHAZADA = el motor la rechazó por sus reglas (credencial, permiso, presupuesto).
- «Ajustada por el motor» = la candidata de la credencial aleatoria no respetaba la estructura pedida y el motor la completó; mide cuánto hay que corregir al modelo, no su acierto.
- Muestras pequeñas y exploratorias; el humano es un guion fijo, no un jugador real. No mide calidad táctica.

## Resultados (4 partidas por modelo y equipo, Ollama real)
- **Con directiva el Rojo ejecuta el 100 %:** qwen3:8b y llama3.1:8b cumplieron las 6 directivas en las 4 partidas (48 de 48 ejecutadas). El resultado VICTORIA_ROJA sale del guion fijo del «humano» (reconocer, correo, adivinar, usar la credencial obtenida, extraer), no de la habilidad del modelo.
- **Credencial aleatoria:** qwen3:8b respetó la estructura `12xxxQ` (0 de 4 ajustadas) pero necesitó corrección del motor en `1234xxL` (4 de 4). llama3.1:8b necesitó corrección en 8 de 8 casos: el motor es necesario, no un detalle.
- **Azul con sujeto y acción elegidos:** 16 de 16 ejecutadas (revocar la credencial comprometida y denegar la solicitud sospechosa).
- **Azul sin acción preferida** (la IA decide): qwen3:8b 0 de 8 aceptadas; llama3.1:8b 3 de 8. El motor las rechazó casi siempre por `UNKNOWN_IDENTITY` (el modelo se inventa el parámetro): sin directiva precisa, estos 8B defienden mal.
- **Comparación con la prueba anterior (v1):** en la primera corrida del experimento, antes de completar el parámetro del sujeto con la directiva, el Azul con directiva fue rechazado 16 de 16 (`UNKNOWN_IDENTITY`/`UNKNOWN_TARGET`) y llama3.1:8b descartó el correo 4 de 4 por cambiar de acción. Se corrigieron dos cosas: el motor completa el parámetro del sujeto elegido y el reintento le dice al modelo qué falló. Datos de aquella corrida: `data/nova_ollama_directivas_v1.json`. Se mejoró el sistema tras ver el fallo, no los datos.
