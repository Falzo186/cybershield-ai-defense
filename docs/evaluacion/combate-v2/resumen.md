# Resumen estadístico de la campaña (generado por `experimentos/resumir_combate.py`)

Observaciones: **300** · válidas **300** · no válidas **0** (inconclusas/errores técnicos, fuera de las tasas) · por resultado: {'VICTORIA_AZUL': 151, 'EMPATE_DEGRADADO': 149} · por fase: {'espejo': 240, 'cruzada': 60}

Cada porcentaje lleva su IC de Wilson al 95 % y su n. Las métricas por solicitud usan bootstrap de partidas. «Exploratoria» = menos de 30 partidas válidas.

## Resultados por celda (fase | Rojo | Azul | configuración)

| Celda | n válidas (inconcl.) | Victoria Roja | Victoria Azul | Empate | Empate degradado | Azul prevención | Azul FP legítimas | Legítimas atendidas |
|---|---|---|---|---|---|---|---|---|
| cruzada | llama3.1:8b@v3 | qwen3:8b@v3 | base | 30 (0) | 0.0 % [0.0–11.4] (n=30) | 100.0 % [88.6–100.0] (n=30) | 0.0 % [0.0–11.4] (n=30) | 0.0 % [0.0–11.4] (n=30) | 100.0 % (n=236; IC no estimable) | 0.0 % (n=90; IC no estimable) | 100 % |
| cruzada | qwen3:8b@v3 | llama3.1:8b@v3 | base | 30 (0) | 0.0 % [0.0–11.4] (n=30) | 3.3 % [0.6–16.7] (n=30) | 0.0 % [0.0–11.4] (n=30) | 96.7 % [83.3–99.4] (n=30) | 100.0 % (n=237; IC no estimable) | 81.1 % [71.7–89.7] (n=90) | 17 % |
| espejo | llama3.1:8b@v3 | llama3.1:8b@v3 | base | 120 (0) | 0.0 % [0.0–3.1] (n=120) | 0.0 % [0.0–3.1] (n=120) | 0.0 % [0.0–3.1] (n=120) | 100.0 % [96.9–100.0] (n=120) | 99.9 % [99.7–100.0] (n=920) | 87.5 % [84.1–90.7] (n=360) | 13 % |
| espejo | qwen3:8b@v3 | qwen3:8b@v3 | base | 120 (0) | 0.0 % [0.0–3.1] (n=120) | 100.0 % [96.9–100.0] (n=120) | 0.0 % [0.0–3.1] (n=120) | 0.0 % [0.0–3.1] (n=120) | 100.0 % (n=955; IC no estimable) | 0.0 % (n=360; IC no estimable) | 100 % |

## Comparaciones (Fisher exacto + Holm)

Fisher exacto bilateral por contraste; corrección de Holm-Bonferroni sobre toda la familia (conservadora; controla el error familiar)

| Contraste | Métrica | A | B | p (Fisher) | p ajustado (Holm) | Significativo (0,05) | Aviso |
|---|---|---|---|---|---|---|---|
| espejo llama3.1:8b@v3 vs espejo qwen3:8b@v3 | victoria_azul | 0/120 | 120/120 | 0.000 | 0.000 | sí |  |
| espejo llama3.1:8b@v3 vs espejo qwen3:8b@v3 | rojo_logra_algun_objetivo | 1/120 | 0/120 | 1.000 | 1.000 | no |  |
