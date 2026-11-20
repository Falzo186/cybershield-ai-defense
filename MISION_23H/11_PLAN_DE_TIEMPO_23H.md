# 11 — PLAN DE TIEMPO (23 horas)

T0 = hora real de arranque (registrada con `date`). Las horas son relativas a T0. Al terminar cada fase: pruebas, commit, `ESTADO_MISION.md`, `date`.

| Fase | Horas | Contenido | Entregable / commit |
|---|---|---|---|
| F0 Diagnóstico | 0:00–1:00 | Archivo 03; línea base de pruebas; respaldo; rama | `docs: diagnóstico inicial` |
| F1 Campañas + modelos | 1:00–2:30 | Causa del exit code 4 y fix; instalar/validar 8B; medir tok/s; prueba corta de campaña | `fix: lanzador de campañas`, `docs/MODELOS.md` |
| F2 Victoria/derrota | 2:30–5:30 | Archivo 04: zonas, ground truth, tráfico legítimo, objetivos, resultados, escenarios, pruebas deterministas | `feat: sistema formal de victoria` |
| F3 Combate real con 8B | 5:30–8:00 | Ciclo de partida completo con Harness gobernando; parser de decisiones; detección de degenerados; sensibilidad/consistencia | `feat: combate IA vs IA con Harness` |
| F4 Wazuh simulado | 8:00–10:00 | Archivo 06 completo + integración con Azul y motor | `feat: wazuh simulado` |
| → Lanzar campañas largas en segundo plano (≈ hora 9–10) | 9:30–19:00 | Archivo 08, reanudables; **sin usar la GPU en otras tareas** | resultados en `docs/evaluacion/` |
| F5 Misiones/escenarios/seguridad | 10:00–12:30 | Estados de misión, escenarios 3×3, auditoría de roles/espectador/403/409 | `feat/fix` correspondientes |
| F6 Interfaz impecable | 12:30–17:30 | Archivo 07; capturas, bucle de revisión visual ≥ 3 iteraciones; E2E con modelos falsos | `feat: UI de combate` + `docs/capturas_final/` |
| F7 Análisis de campañas | 17:30–19:30 | Métricas, IC, Holm, líneas base, gráficas | `docs: informe de campañas` |
| F8 Pruebas finales y E2E real | 19:30–21:00 | Batería completa; una E2E con 8B reales; correcciones | `test:` |
| F9 Documentación y entrega | 21:00–22:30 | Archivo 10 completo + PDF | `docs: cierre de misión 23h` |
| Colchón | 22:30–23:00 | Reserva para imprevistos; no iniciar nada nuevo | — |

**T_CIERRE (21:30):** a partir de ahí solo documentación, regresión y limpieza.

## Regla de recorte si vas atrasado
Si una fase excede su ventana en más de 45 min, recorta en este orden (de lo primero a sacrificar a lo último): (1) variaciones de configuración de campañas, (2) escenarios complejos adicionales, (3) pulido de gráficas, (4) pantallas secundarias de la UI. **Nunca se recortan:** victoria/derrota formal, Wazuh simulado básico, combate con 8B reales, pruebas, informe ejecutivo, honestidad de resultados.

## Si el equipo de cómputo falla
Ollama caído → reinícialo (`ollama serve`) y reanuda campañas. GPU/VRAM insuficiente → baja `num_ctx`, usa cuantización menor disponible o ejecuta modelos en serie; documenta. Sin disco → limpia solo artefactos propios regenerables (nunca históricos). Servidor ocupado → identifica el PID propio y reinícialo.

## Latido de progreso
Cada ~2 horas añade una línea con la hora real a `ESTADO_MISION.md` ("latido") y confirma que las campañas en segundo plano siguen vivas (PID, última observación guardada).
