# ESTADO DE LA MISIÓN 23H

- **T0:** 2026-11-18 21:40:50 (-06:00) · **T_CIERRE (T0+21h30):** 2026-11-19 19:10:50 · **T_FIN (T0+23h):** 2026-11-19 20:40:50
- **Rama:** `mision-23h` (desde `main` @ 4dbdb35) · etiqueta `pre-mision-23h` · respaldo de `data/` en `respaldo_pre_mision/`
- **Fase actual:** campañas con 8B en ejecución (F7 se analiza al terminar); trabajo en paralelo en F3/F5/F6 sin tocar la GPU.

## Hecho (commits)
- F0 diagnóstico + línea base corregida · F2 motor formal de victoria (`src/lab/combate/`, 15 escenarios) · F4 Wazuh simulado (`src/lab/wazuh_sim/`)
- F3 combate con Harness (`ControlPartida`), parser estricto, CLI `python -m src.lab.combate.jugar`, degenerados, lanzador de campañas reanudable
- F6 UI `/combate/` (Teatro de batalla) + API `/api/combate/*` + E2E 39/39 + capturas 1366/1920/1280

## En ejecución en segundo plano
- `experimentos/campana_combate.py --campana combate-v1` (dos procesos: `base` sin GPU, y `espejo,cruzada,base_llm,variaciones` con sufijo `llm`). Estado: `--estado`.

## Pendiente
- Prueba E2E con 8B reales + captura · sensibilidad/consistencia con GPU (al terminar las campañas) · análisis y gráficas (F7) · docs finales (F9) · informe PDF.

## Latidos
- 2026-11-18 21:40 arranque · 22:20 campañas vivas (base 598/1800 · espejo 29/90 al relanzar con la variante `sin_autorizaciones`)
