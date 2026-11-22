# Informe de la campaña de Caminos (`caminos-v1`)

Generado por `experimentos/informe_caminos.py` a partir de `data/campanas/caminos-v1/observaciones.jsonl`; análisis completo con IC de Wilson, bootstrap por partida y Fisher + Holm en `docs/evaluacion/caminos-v1/resumen.md`. **Prompts `c1` sin cambios durante la campaña.**

## 1. Qué se midió y con qué honestidad
- **2062 partidas** (960 `CAMINOS_GUION`: guiones y líneas base sin IA; 1102 `CAMINOS_IA`: al menos un lado es un 8B real). **Válidas:** 2052; **inconclusas/errores (excluidas de las tasas):** 10.
- Modos: **grafo** de 16 hojas (3 dificultades) y **automático** de credenciales (8 credenciales fijas, tráfico legítimo 30-40 %).
- Modelos: `qwen3:8b` y `llama3.1:8b` (Ollama local). Fases: línea base sin GPU, 8B contra el otro equipo trivial, **espejo** y **cruzada**.
- Una victoria Roja de `CAMINOS_GUION` demuestra que el diseño la permite; **solo las de `CAMINOS_IA` son victorias de un modelo, y solo en este modo.**

## 2. Líneas base (sin IA)

| Pareja (modo · Rojo vs Azul) | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado |
|---|---|---|---|---|
| grafo · primera vs registro | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 100.0 % [94.0–100.0] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · aleatorio vs registro | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 100.0 % [94.0–100.0] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · guion:cred_gerente,solic vs registro | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 100.0 % [94.0–100.0] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · primera vs aprobar | 60 (0) | 100.0 % [94.0–100.0] (n=60) | 0.0 % [0.0–6.0] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · aleatorio vs aprobar | 60 (0) | 80.0 % [68.2–88.2] (n=60) | 20.0 % [11.8–31.8] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · guion:cred_gerente,solic vs aprobar | 60 (0) | 100.0 % [94.0–100.0] (n=60) | 0.0 % [0.0–6.0] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · primera vs rechazar | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 100.0 % [94.0–100.0] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · aleatorio vs rechazar | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 100.0 % [94.0–100.0] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · guion:cred_gerente,solic vs rechazar | 60 (0) | 0.0 % [0.0–6.0] (n=60) | 100.0 % [94.0–100.0] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · primera vs aleatorio | 60 (0) | 50.0 % [37.7–62.3] (n=60) | 50.0 % [37.7–62.3] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · aleatorio vs aleatorio | 60 (0) | 35.0 % [24.2–47.6] (n=60) | 65.0 % [52.4–75.8] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| grafo · guion:cred_gerente,solic vs aleatorio | 60 (0) | 40.0 % [28.6–52.6] (n=60) | 60.0 % [47.4–71.4] (n=60) | 0.0 % [0.0–6.0] (n=60) |
| auto · primera vs registro | 20 (0) | 0.0 % [0.0–16.1] (n=20) | 100.0 % [83.9–100.0] (n=20) | 0.0 % [0.0–16.1] (n=20) |
| auto · aleatorio vs registro | 20 (0) | 0.0 % [0.0–16.1] (n=20) | 100.0 % [83.9–100.0] (n=20) | 0.0 % [0.0–16.1] (n=20) |
| auto · guion:C-01¦portal_intern vs registro | 20 (0) | 0.0 % [0.0–16.1] (n=20) | 100.0 % [83.9–100.0] (n=20) | 0.0 % [0.0–16.1] (n=20) |
| auto · primera vs aprobar | 20 (0) | 100.0 % [83.9–100.0] (n=20) | 0.0 % [0.0–16.1] (n=20) | 0.0 % [0.0–16.1] (n=20) |
| auto · aleatorio vs aprobar | 20 (0) | 65.0 % [43.3–81.9] (n=20) | 35.0 % [18.1–56.7] (n=20) | 0.0 % [0.0–16.1] (n=20) |
| auto · guion:C-01¦portal_intern vs aprobar | 20 (0) | 100.0 % [83.9–100.0] (n=20) | 0.0 % [0.0–16.1] (n=20) | 0.0 % [0.0–16.1] (n=20) |
| auto · primera vs rechazar | 20 (0) | 0.0 % [0.0–16.1] (n=20) | 0.0 % [0.0–16.1] (n=20) | 100.0 % [83.9–100.0] (n=20) |
| auto · aleatorio vs rechazar | 20 (0) | 0.0 % [0.0–16.1] (n=20) | 95.0 % [76.4–99.1] (n=20) | 5.0 % [0.9–23.6] (n=20) |
| auto · guion:C-01¦portal_intern vs rechazar | 20 (0) | 0.0 % [0.0–16.1] (n=20) | 0.0 % [0.0–16.1] (n=20) | 100.0 % [83.9–100.0] (n=20) |
| auto · primera vs aleatorio | 20 (0) | 55.0 % [34.2–74.2] (n=20) | 10.0 % [2.8–30.1] (n=20) | 35.0 % [18.1–56.7] (n=20) |
| auto · aleatorio vs aleatorio | 20 (0) | 15.0 % [5.2–36.0] (n=20) | 80.0 % [58.4–91.9] (n=20) | 5.0 % [0.9–23.6] (n=20) |
| auto · guion:C-01¦portal_intern vs aleatorio | 20 (0) | 65.0 % [43.3–81.9] (n=20) | 5.0 % [0.9–23.6] (n=20) | 30.0 % [14.5–51.9] (n=20) |

## 3. Un 8B como Rojo contra un Azul trivial

| Pareja | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado |
|---|---|---|---|---|
| grafo · Rojo qwen3:8b vs Azul aprobar | 36 (0) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo qwen3:8b vs Azul registro | 36 (0) | 0.0 % [0.0–9.6] (n=36) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo qwen3:8b vs Azul aleatorio | 36 (0) | 41.7 % [27.1–57.8] (n=36) | 58.3 % [42.2–72.9] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo qwen3:8b vs Azul rechazar | 36 (0) | 0.0 % [0.0–9.6] (n=36) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo llama3.1:8b vs Azul aprobar | 36 (0) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo llama3.1:8b vs Azul registro | 36 (0) | 0.0 % [0.0–9.6] (n=36) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo llama3.1:8b vs Azul aleatorio | 36 (0) | 33.3 % [20.2–49.7] (n=36) | 66.7 % [50.3–79.8] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo llama3.1:8b vs Azul rechazar | 36 (0) | 0.0 % [0.0–9.6] (n=36) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| auto · Rojo qwen3:8b vs Azul aprobar | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 100.0 % [77.2–100.0] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo qwen3:8b vs Azul registro | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 100.0 % [77.2–100.0] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo qwen3:8b vs Azul aleatorio | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 100.0 % [77.2–100.0] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo qwen3:8b vs Azul rechazar | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 100.0 % [77.2–100.0] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo llama3.1:8b vs Azul aprobar | 13 (0) | 100.0 % [77.2–100.0] (n=13) | 0.0 % [0.0–22.8] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo llama3.1:8b vs Azul registro | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 100.0 % [77.2–100.0] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo llama3.1:8b vs Azul aleatorio | 13 (0) | 38.5 % [17.7–64.5] (n=13) | 61.5 % [35.5–82.3] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo llama3.1:8b vs Azul rechazar | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 92.3 % [66.7–98.6] (n=13) | 7.7 % [1.4–33.3] (n=13) |

## 4. Un 8B como Azul contra un Rojo trivial

| Pareja | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado |
|---|---|---|---|---|
| grafo · Rojo aleatorio vs Azul qwen3:8b | 35 (1) | 0.0 % [0.0–9.9] (n=35) | 100.0 % [90.1–100.0] (n=35) | 0.0 % [0.0–9.9] (n=35) |
| grafo · Rojo guion:cred_gerente,solic vs Azul qwen3:8b | 36 (0) | 0.0 % [0.0–9.6] (n=36) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo primera vs Azul qwen3:8b | 36 (0) | 0.0 % [0.0–9.6] (n=36) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo aleatorio vs Azul llama3.1:8b | 33 (3) | 27.3 % [15.1–44.2] (n=33) | 72.7 % [55.8–84.9] (n=33) | 0.0 % [0.0–10.4] (n=33) |
| grafo · Rojo guion:cred_gerente,solic vs Azul llama3.1:8b | 36 (0) | 0.0 % [0.0–9.6] (n=36) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| grafo · Rojo primera vs Azul llama3.1:8b | 36 (0) | 100.0 % [90.4–100.0] (n=36) | 0.0 % [0.0–9.6] (n=36) | 0.0 % [0.0–9.6] (n=36) |
| auto · Rojo aleatorio vs Azul qwen3:8b | 11 (2) | 0.0 % [0.0–25.9] (n=11) | 100.0 % [74.1–100.0] (n=11) | 0.0 % [0.0–25.9] (n=11) |
| auto · Rojo guion:C-01¦portal_intern vs Azul qwen3:8b | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 0.0 % [0.0–22.8] (n=13) | 100.0 % [77.2–100.0] (n=13) |
| auto · Rojo primera vs Azul qwen3:8b | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 0.0 % [0.0–22.8] (n=13) | 100.0 % [77.2–100.0] (n=13) |
| auto · Rojo aleatorio vs Azul llama3.1:8b | 13 (0) | 0.0 % [0.0–22.8] (n=13) | 100.0 % [77.2–100.0] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo guion:C-01¦portal_intern vs Azul llama3.1:8b | 13 (0) | 76.9 % [49.7–91.8] (n=13) | 23.1 % [8.2–50.3] (n=13) | 0.0 % [0.0–22.8] (n=13) |
| auto · Rojo primera vs Azul llama3.1:8b | 13 (0) | 61.5 % [35.5–82.3] (n=13) | 38.5 % [17.7–64.5] (n=13) | 0.0 % [0.0–22.8] (n=13) |

## 5. 8B contra 8B (espejo y cruzada)

| Pareja | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado |
|---|---|---|---|---|
| grafo · espejo · Rojo qwen3:8b vs Azul qwen3:8b | 120 (0) | 0.0 % [0.0–3.1] (n=120) | 100.0 % [96.9–100.0] (n=120) | 0.0 % [0.0–3.1] (n=120) |
| grafo · cruzada · Rojo qwen3:8b vs Azul llama3.1:8b | 44 (0) | 97.7 % [88.2–99.6] (n=44) | 2.3 % [0.4–11.8] (n=44) | 0.0 % [0.0–8.0] (n=44) |
| grafo · cruzada · Rojo llama3.1:8b vs Azul qwen3:8b | 42 (0) | 0.0 % [0.0–8.4] (n=42) | 100.0 % [91.6–100.0] (n=42) | 0.0 % [0.0–8.4] (n=42) |
| grafo · espejo · Rojo llama3.1:8b vs Azul llama3.1:8b | 120 (0) | 0.0 % [0.0–3.1] (n=120) | 100.0 % [96.9–100.0] (n=120) | 0.0 % [0.0–3.1] (n=120) |
| auto · espejo · Rojo qwen3:8b vs Azul qwen3:8b | 41 (4) | 7.3 % [2.5–19.4] (n=41) | 92.7 % [80.6–97.5] (n=41) | 0.0 % [0.0–8.6] (n=41) |
| auto · espejo · Rojo llama3.1:8b vs Azul llama3.1:8b | 45 (0) | 6.7 % [2.3–17.9] (n=45) | 93.3 % [82.1–97.7] (n=45) | 0.0 % [0.0–7.9] (n=45) |

## 6. Victorias Rojas de 8B contra 8B: hojas alcanzadas
`H_R_giro_2f` ×43

## 7. Qué decisiones del Azul inclinaron el resultado (modo grafo, Azul 8B, partidas válidas)
- **Azul qwen3:8b:** N1r2: rechazar×165; N2: pedir_verificacion×90; N2v1: rechazar×90; N3: contener×5; N4: pedir_verificacion×9; N4v1: rechazar×9
- **Azul llama3.1:8b:** N1i2: pedir_verificacion×88; N1i4: aprobar×88; N2: pedir_verificacion×169; N2v1: rechazar×169; N3: contener×4, aprobar×2; N4: pedir_verificacion×6; N4v1: rechazar×6

## 8. Contrastes (Fisher exacto + Holm sobre 32 comparaciones)
Significativos al 0,05 tras Holm: **7**. Los más relevantes:
- [grafo] Rojo qwen3:8b vs Rojo llama3.1:8b · Azul llama3.1:8b — victoria_roja: 43/44 frente a 0/120 (p Holm = 0.0000).
- [grafo] Azul qwen3:8b vs Azul llama3.1:8b · Rojo aleatorio — victoria_azul: 35/35 frente a 24/33 (p Holm = 0.0203).
- [grafo] Azul qwen3:8b vs Azul llama3.1:8b · Rojo primera — victoria_azul: 36/36 frente a 0/36 (p Holm = 0.0000).
- [grafo] Azul qwen3:8b vs Azul llama3.1:8b · Rojo qwen3:8b — victoria_azul: 120/120 frente a 1/44 (p Holm = 0.0000).
- [grafo] Azul llama3.1:8b: Rojo espejo vs Rojo cruzado — victoria_roja: 0/120 frente a 43/44 (p Holm = 0.0000).
- [auto] Rojo qwen3:8b vs Rojo llama3.1:8b · Azul aprobar — victoria_roja: 0/13 frente a 13/13 (p Holm = 0.0000).
- [auto] Rojo qwen3:8b vs Rojo aleatorio · Azul aprobar — victoria_roja: 0/13 frente a 13/20 (p Holm = 0.0044).

## 9. Limitaciones (fijas)
- **La fase cruzada quedó incompleta (86 partidas)**: la GPU se cedió al usuario; los ids son deterministas y la campaña se puede reanudar. Las filas «cruzada» son exploratorias (n < 30).
- Las líneas base son deterministas: sus resultados no varían entre dificultades ni semillas; sirven de referencia, no de muestra.
- Los prompts de los 8B (`c1`) se escribieron una vez y no se calibraron para este modo; otros prompts u otros modelos podrían dar otras tasas.
- En el modo automático el Rojo 8B tiende a probar primero la credencial del administrador de respaldos (un señuelo): es una observación del modelo, no un ajuste del modo.
- El grafo tiene 5 nodos del Rojo con una única opción (D-24): la decisión real del Rojo es su primer movimiento y la elección tras abrir sesión.
- Las partidas lanzadas con `semilla` compartida entre parejas no son pareables partida a partida; los contrastes tratan las muestras como independientes.
- Wazuh es **simulado**; las alertas no provienen de una instalación real.
