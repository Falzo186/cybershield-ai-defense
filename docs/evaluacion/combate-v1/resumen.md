# Resumen estadístico de la campaña (generado por `experimentos/resumir_combate.py`)

Observaciones: **2370** · válidas **2370** · no válidas **0** (inconclusas/errores técnicos, fuera de las tasas) · por resultado: {'EMPATE_DEGRADADO': 850, 'VICTORIA_AZUL': 829, 'VICTORIA_ROJA': 559, 'EMPATE': 132} · por fase: {'base': 1800, 'espejo': 120, 'cruzada': 120, 'base_llm': 150, 'variaciones': 120, 'cortes': 60}

Cada porcentaje lleva su IC de Wilson al 95 % y su n. Las métricas por solicitud usan bootstrap de partidas. «Exploratoria» = menos de 30 partidas válidas.

## Resultados por celda (fase | Rojo | Azul | configuración)

| Celda | n válidas (inconcl.) | Victoria Roja | Victoria Azul | Empate | Empate degradado | Azul prevención | Azul FP legítimas | Legítimas atendidas |
|---|---|---|---|---|---|---|---|---|
| base | falso:aleatorio | falso:aleatorio | base | 150 (0) | 34.7 % [27.5–42.6] (n=150) | 1.3 % [0.4–4.7] (n=150) | 2.0 % [0.7–5.7] (n=150) | 62.0 % [54.0–69.4] (n=150) | 70.1 % [67.7–72.1] (n=1072) | 69.5 % [65.3–73.7] (n=387) | 27 % |
| base | falso:aleatorio | falso:aprobar | base | 150 (0) | 96.7 % [92.4–98.6] (n=150) | 0.0 % [0.0–2.5] (n=150) | 3.3 % [1.4–7.6] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % (n=525; IC no estimable) | 0.0 % (n=138; IC no estimable) | 100 % |
| base | falso:aleatorio | falso:rechazar | base | 150 (0) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 100.0 % [97.5–100.0] (n=150) | 100.0 % (n=1200; IC no estimable) | 100.0 % (n=450; IC no estimable) | 0 % |
| base | falso:aleatorio | falso:registro | base | 150 (0) | 0.0 % [0.0–2.5] (n=150) | 100.0 % [97.5–100.0] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 100.0 % (n=1200; IC no estimable) | 0.0 % (n=450; IC no estimable) | 100 % |
| base | falso:fijo | falso:aleatorio | base | 150 (0) | 32.0 % [25.1–39.8] (n=150) | 0.0 % [0.0–2.5] (n=150) | 3.3 % [1.4–7.6] (n=150) | 64.7 % [56.7–71.9] (n=150) | 70.6 % [68.3–72.8] (n=1038) | 69.1 % [64.7–73.4] (n=379) | 28 % |
| base | falso:fijo | falso:aprobar | base | 150 (0) | 33.3 % [26.3–41.2] (n=150) | 0.0 % [0.0–2.5] (n=150) | 66.7 % [58.8–73.7] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % (n=950; IC no estimable) | 0.0 % (n=350; IC no estimable) | 100 % |
| base | falso:fijo | falso:rechazar | base | 150 (0) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 100.0 % [97.5–100.0] (n=150) | 100.0 % (n=1200; IC no estimable) | 100.0 % (n=450; IC no estimable) | 0 % |
| base | falso:fijo | falso:registro | base | 150 (0) | 0.0 % [0.0–2.5] (n=150) | 100.0 % [97.5–100.0] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 100.0 % (n=1200; IC no estimable) | 0.0 % (n=450; IC no estimable) | 100 % |
| base | falso:objetivos | falso:aleatorio | base | 150 (0) | 49.3 % [41.4–57.3] (n=150) | 0.0 % [0.0–2.5] (n=150) | 3.3 % [1.4–7.6] (n=150) | 47.3 % [39.5–55.3] (n=150) | 68.9 % [65.8–71.5] (n=919) | 66.6 % [61.9–71.3] (n=323) | 29 % |
| base | falso:objetivos | falso:aprobar | base | 150 (0) | 100.0 % [97.5–100.0] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % (n=300; IC no estimable) | 0.0 % (n=50; IC no estimable) | 100 % |
| base | falso:objetivos | falso:rechazar | base | 150 (0) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 100.0 % [97.5–100.0] (n=150) | 100.0 % (n=1200; IC no estimable) | 100.0 % (n=450; IC no estimable) | 0 % |
| base | falso:objetivos | falso:registro | base | 150 (0) | 0.0 % [0.0–2.5] (n=150) | 100.0 % [97.5–100.0] (n=150) | 0.0 % [0.0–2.5] (n=150) | 0.0 % [0.0–2.5] (n=150) | 100.0 % (n=1200; IC no estimable) | 0.0 % (n=450; IC no estimable) | 100 % |
| base_llm | falso:aleatorio | llama3.1:8b | base | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 100.0 % [79.6–100.0] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 100.0 % (n=120; IC no estimable) | 4.4 % [0.0–10.4] (n=45) | 97 % |
| base_llm | falso:aleatorio | qwen3:8b | base | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 93.3 % [70.2–98.8] (n=15) | 0.0 % [0.0–20.4] (n=15) | 6.7 % [1.2–29.8] (n=15) | 100.0 % (n=120; IC no estimable) | 6.7 % [0.0–13.3] (n=45) | 94 % |
| base_llm | falso:fijo | llama3.1:8b | base | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 100.0 % [79.6–100.0] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 100.0 % (n=120; IC no estimable) | 0.0 % (n=45; IC no estimable) | 100 % |
| base_llm | falso:fijo | qwen3:8b | base | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 80.0 % [54.8–93.0] (n=15) | 0.0 % [0.0–20.4] (n=15) | 20.0 % [7.0–45.2] (n=15) | 100.0 % (n=120; IC no estimable) | 11.1 % [2.2–22.7] (n=45) | 88 % |
| base_llm | llama3.1:8b | falso:aleatorio | base | 15 (0) | 46.7 % [24.8–69.9] (n=15) | 0.0 % [0.0–20.4] (n=15) | 13.3 % [3.7–37.9] (n=15) | 40.0 % [19.8–64.3] (n=15) | 73.2 % [66.2–79.0] (n=97) | 58.3 % [41.5–75.7] (n=36) | 42 % |
| base_llm | llama3.1:8b | falso:aprobar | base | 15 (0) | 93.3 % [70.2–98.8] (n=15) | 6.7 % [1.2–29.8] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % (n=58; IC no estimable) | 0.0 % (n=14; IC no estimable) | 100 % |
| base_llm | llama3.1:8b | falso:rechazar | base | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 100.0 % [79.6–100.0] (n=15) | 100.0 % (n=116; IC no estimable) | 100.0 % (n=45; IC no estimable) | 0 % |
| base_llm | qwen3:8b | falso:aleatorio | base | 15 (0) | 33.3 % [15.2–58.3] (n=15) | 13.3 % [3.7–37.9] (n=15) | 0.0 % [0.0–20.4] (n=15) | 53.3 % [30.1–75.2] (n=15) | 73.1 % [65.9–79.2] (n=108) | 59.5 % [43.6–76.7] (n=37) | 39 % |
| base_llm | qwen3:8b | falso:aprobar | base | 15 (0) | 93.3 % [70.2–98.8] (n=15) | 0.0 % [0.0–20.4] (n=15) | 6.7 % [1.2–29.8] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % (n=49; IC no estimable) | 0.0 % (n=13; IC no estimable) | 100 % |
| base_llm | qwen3:8b | falso:rechazar | base | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 100.0 % [79.6–100.0] (n=15) | 100.0 % (n=120; IC no estimable) | 100.0 % (n=45; IC no estimable) | 0 % |
| cortes | falso:cortes | llama3.1:8b | base | 30 (0) | 0.0 % [0.0–11.4] (n=30) | 96.7 % [83.3–99.4] (n=30) | 3.3 % [0.6–16.7] (n=30) | 0.0 % [0.0–11.4] (n=30) | 99.6 % [98.7–100.0] (n=240) | 2.2 % [0.0–5.3] (n=90) | 98 % |
| cortes | falso:cortes | qwen3:8b | base | 30 (0) | 0.0 % [0.0–11.4] (n=30) | 80.0 % [62.7–90.5] (n=30) | 0.0 % [0.0–11.4] (n=30) | 20.0 % [9.5–37.3] (n=30) | 100.0 % (n=240; IC no estimable) | 10.0 % [4.3–16.9] (n=90) | 89 % |
| cruzada | llama3.1:8b | qwen3:8b | base | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 63.3 % [50.7–74.4] (n=60) | 0.0 % [0.0–6.0] (n=60) | 36.7 % [25.6–49.3] (n=60) | 100.0 % (n=463; IC no estimable) | 21.7 % [15.3–28.3] (n=180) | 77 % |
| cruzada | qwen3:8b | llama3.1:8b | base | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 95.0 % [86.3–98.3] (n=60) | 0.0 % [0.0–6.0] (n=60) | 5.0 % [1.7–13.7] (n=60) | 100.0 % (n=480; IC no estimable) | 3.9 % [1.6–6.7] (n=180) | 97 % |
| espejo | llama3.1:8b | llama3.1:8b | base | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 83.3 % [72.0–90.7] (n=60) | 10.0 % [4.7–20.1] (n=60) | 6.7 % [2.6–15.9] (n=60) | 98.7 % [97.5–99.6] (n=452) | 3.9 % [1.1–6.9] (n=180) | 96 % |
| espejo | qwen3:8b | qwen3:8b | base | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 70.0 % [57.5–80.1] (n=60) | 0.0 % [0.0–6.0] (n=60) | 30.0 % [19.9–42.5] (n=60) | 100.0 % (n=478; IC no estimable) | 13.9 % [8.9–19.3] (n=180) | 84 % |
| variaciones | llama3.1:8b | llama3.1:8b | ejemplos | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 100.0 % [79.6–100.0] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 100.0 % (n=118; IC no estimable) | 4.4 % [0.0–10.4] (n=45) | 97 % |
| variaciones | llama3.1:8b | llama3.1:8b | sin_aut_sin_wazuh | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 33.3 % [15.2–58.3] (n=15) | 13.3 % [3.7–37.9] (n=15) | 53.3 % [30.1–75.2] (n=15) | 97.5 % [94.8–100.0] (n=118) | 28.9 % [15.6–40.8] (n=45) | 72 % |
| variaciones | llama3.1:8b | llama3.1:8b | sin_autorizaciones | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 46.7 % [24.8–69.9] (n=15) | 0.0 % [0.0–20.4] (n=15) | 53.3 % [30.1–75.2] (n=15) | 98.2 % [94.7–100.0] (n=114) | 31.1 % [18.7–41.5] (n=45) | 70 % |
| variaciones | llama3.1:8b | llama3.1:8b | sin_wazuh | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 86.7 % [62.1–96.3] (n=15) | 13.3 % [3.7–37.9] (n=15) | 0.0 % [0.0–20.4] (n=15) | 98.3 % [95.7–100.0] (n=119) | 2.2 % [0.0–6.7] (n=45) | 98 % |
| variaciones | qwen3:8b | qwen3:8b | ejemplos | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 93.3 % [70.2–98.8] (n=15) | 0.0 % [0.0–20.4] (n=15) | 6.7 % [1.2–29.8] (n=15) | 100.0 % (n=120; IC no estimable) | 4.4 % [0.0–10.6] (n=45) | 95 % |
| variaciones | qwen3:8b | qwen3:8b | sin_aut_sin_wazuh | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 33.3 % [15.2–58.3] (n=15) | 0.0 % [0.0–20.4] (n=15) | 66.7 % [41.7–84.8] (n=15) | 100.0 % (n=120; IC no estimable) | 42.2 % [27.9–54.0] (n=45) | 60 % |
| variaciones | qwen3:8b | qwen3:8b | sin_autorizaciones | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 26.7 % [10.9–52.0] (n=15) | 0.0 % [0.0–20.4] (n=15) | 73.3 % [48.0–89.1] (n=15) | 100.0 % (n=120; IC no estimable) | 44.4 % [31.1–56.1] (n=45) | 57 % |
| variaciones | qwen3:8b | qwen3:8b | sin_wazuh | 15 (0) | 0.0 % [0.0–20.4] (n=15) | 100.0 % [79.6–100.0] (n=15) | 0.0 % [0.0–20.4] (n=15) | 0.0 % [0.0–20.4] (n=15) | 100.0 % (n=120; IC no estimable) | 0.0 % (n=45; IC no estimable) | 100 % |

## Comparaciones (Fisher exacto + Holm)

Fisher exacto bilateral por contraste; corrección de Holm-Bonferroni sobre toda la familia (conservadora; controla el error familiar)

| Contraste | Métrica | A | B | p (Fisher) | p ajustado (Holm) | Significativo (0,05) | Aviso |
|---|---|---|---|---|---|---|---|
| espejo llama3.1:8b vs espejo qwen3:8b | victoria_azul | 50/60 | 42/60 | 0.130 | 1.000 | no |  |
| espejo llama3.1:8b vs espejo qwen3:8b | rojo_logra_algun_objetivo | 6/60 | 0/60 | 0.027 | 0.356 | no |  |
| qwen3:8b: variación «ejemplos» vs base | victoria_azul | 42/60 | 14/15 | 0.096 | 1.000 | no | muestra pequeña: exploratorio |
| qwen3:8b: variación «ejemplos» vs base | rojo_logra_algun_objetivo | 0/60 | 0/15 | 1.000 | 1.000 | no | muestra pequeña: exploratorio |
| llama3.1:8b: variación «ejemplos» vs base | victoria_azul | 50/60 | 15/15 | 0.196 | 1.000 | no | muestra pequeña: exploratorio |
| llama3.1:8b: variación «ejemplos» vs base | rojo_logra_algun_objetivo | 6/60 | 0/15 | 0.339 | 1.000 | no | muestra pequeña: exploratorio |
| qwen3:8b: variación «sin_wazuh» vs base | victoria_azul | 42/60 | 15/15 | 0.016 | 0.229 | no | muestra pequeña: exploratorio |
| qwen3:8b: variación «sin_wazuh» vs base | rojo_logra_algun_objetivo | 0/60 | 0/15 | 1.000 | 1.000 | no | muestra pequeña: exploratorio |
| llama3.1:8b: variación «sin_wazuh» vs base | victoria_azul | 50/60 | 13/15 | 1.000 | 1.000 | no | muestra pequeña: exploratorio |
| llama3.1:8b: variación «sin_wazuh» vs base | rojo_logra_algun_objetivo | 6/60 | 2/15 | 0.657 | 1.000 | no | muestra pequeña: exploratorio |
| qwen3:8b: variación «sin_autorizaciones» vs base | victoria_azul | 42/60 | 4/15 | 0.003 | 0.052 | no | muestra pequeña: exploratorio |
| qwen3:8b: variación «sin_autorizaciones» vs base | rojo_logra_algun_objetivo | 0/60 | 0/15 | 1.000 | 1.000 | no | muestra pequeña: exploratorio |
| llama3.1:8b: variación «sin_autorizaciones» vs base | victoria_azul | 50/60 | 7/15 | 0.006 | 0.095 | no | muestra pequeña: exploratorio |
| llama3.1:8b: variación «sin_autorizaciones» vs base | rojo_logra_algun_objetivo | 6/60 | 1/15 | 1.000 | 1.000 | no | muestra pequeña: exploratorio |
| qwen3:8b: variación «sin_aut_sin_wazuh» vs base | victoria_azul | 42/60 | 5/15 | 0.015 | 0.229 | no | muestra pequeña: exploratorio |
| qwen3:8b: variación «sin_aut_sin_wazuh» vs base | rojo_logra_algun_objetivo | 0/60 | 0/15 | 1.000 | 1.000 | no | muestra pequeña: exploratorio |
| llama3.1:8b: variación «sin_aut_sin_wazuh» vs base | victoria_azul | 50/60 | 5/15 | 0.000 | 0.006 | sí | muestra pequeña: exploratorio |
| llama3.1:8b: variación «sin_aut_sin_wazuh» vs base | rojo_logra_algun_objetivo | 6/60 | 3/15 | 0.372 | 1.000 | no | muestra pequeña: exploratorio |
