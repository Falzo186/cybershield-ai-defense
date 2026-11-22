# Nova con Ollama REAL (F20) — v2 (prompts con enumeraciones + esquema JSON)

Salida cruda de `experimentos/prueba_ollama_nova.py --partidas 6 --etiqueta _v2` (qwen3:8b y llama3.1:8b en un equipo; el otro equipo usa la heurística **SIMULADA**, etiquetada). Datos: `data/nova_ollama_real_v2.json`.

**Comparación honesta con v1 (sin esquema):** qwen3:8b como Rojo dio 8 corridas, 0 válidas, 8 inválidas (2 partidas, ver `data/nova_ollama_real_v1_parcial.txt`). Con esquema JSON y enumeraciones: 16/16 válidas por partida. El motor sigue validando todo; los resultados no miden calidad estratégica, solo validez estructural.

```
qwen3:8b     RED #1: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 16.5s
qwen3:8b     RED #2: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 16.3s
qwen3:8b     RED #3: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 16.6s
qwen3:8b     RED #4: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 16.3s
qwen3:8b     RED #5: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 15.8s
qwen3:8b     RED #6: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 16.4s
qwen3:8b     BLUE #1: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 11.6s
qwen3:8b     BLUE #2: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 11.3s
qwen3:8b     BLUE #3: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 12.1s
qwen3:8b     BLUE #4: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 11.0s
qwen3:8b     BLUE #5: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 11.2s
qwen3:8b     BLUE #6: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 10.9s
llama3.1:8b  RED #1: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 17.8s
llama3.1:8b  RED #2: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 10.9s
llama3.1:8b  RED #3: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 11.5s
llama3.1:8b  RED #4: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 11.2s
llama3.1:8b  RED #5: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 10.9s
llama3.1:8b  RED #6: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 11.3s
llama3.1:8b  BLUE #1: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 6.6s
llama3.1:8b  BLUE #2: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 6.6s
llama3.1:8b  BLUE #3: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 7.0s
llama3.1:8b  BLUE #4: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 6.2s
llama3.1:8b  BLUE #5: VICTORIA_ROJA    corridas 8 válidas 8 inválidas 0 fallidas 0 6.8s
llama3.1:8b  BLUE #6: EMPATE           corridas 16 válidas 16 inválidas 0 fallidas 0 13.4s
```

NO VERIFICADO: calidad táctica de las propuestas; solo se midió validez y resultado de partida (6 partidas por celda).
