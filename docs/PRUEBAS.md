# Pruebas (misión 23 h)

| Fecha | Comando | Commit | Resultado |
|---|---|---|---|
| 2026-11-18 | `python ejecutar_pruebas.py --rapido` (línea base, tras instalar fastapi y reconstruir `eventos_ejemplo.jsonl`) | 4dbdb35 + correcciones | 33/33 suites · 1 581/1 581 |
| 2026-11-19 | `python ejecutar_pruebas.py` (batería completa, con navegador) | aba15af | **38/38 suites · 1 850/1 850** (0 falladas, 0 omitidas por la batería) |
| 2026-11-19 | `python e2e/prueba_real_8b.py` (E2E con `qwen3:8b` vs `llama3.1:8b` reales) | 55fecbc | VICTORIA_AZUL, cadena íntegra, consola sin errores |

Suites nuevas: `src/lab/test_combate.py` (70), `src/lab/test_wazuh_sim.py` (19), `server/test_combate.py` (33), `e2e/test_combate_ui.py` (41).
Cobertura (coverage.py, módulos nuevos `combate/` y `wazuh_sim/`, pruebas unitarias): **91 %** (motor 94 %, modelos 96 %, store 94 %, wazuh_sim 92 %; `jugar.py` 59 %: la ruta CLI `main()` no se prueba).

**Omitidas, con motivo:** prueba de humo contra un Wazuh real (no hay `WAZUH_URL`); `integraciones/wazuh/test_indexador_real.py` (condicional, sin instancia).
**Separación:** las pruebas con modelos falsos (motor, API, UI) NO prueban a Ollama; la integración real se verifica con `e2e/prueba_real_8b.py` y con las campañas (≈ 9 700 llamadas reales). Una prueba con un servidor HTTP de guion cubre el parser, los reintentos y los errores de `RojoOllama`/`AzulOllama`.

## Casos de combate representativos (deterministas)
Victoria Roja · victoria Azul · empate · empate degradado («RECHAZAR siempre» no gana) · Rojo falla (mensaje fijo) · Azul falso positivo · Azul deja pasar amenaza (APROBAR siempre) · partida interrumpida · presupuesto agotado · modelo sin respuesta (Rojo y Azul) · hash de escenario violado · doble resultado (409 y rechazo de la BD) · cadena de hashes alterada · respuesta malformada ≠ aprobación · contexto mutado por un modelo · UI sin victoria prematura.
**Seguridad:** espectador solo lectura (403), Rojo no recibe Wazuh ni zonas, verdad de fondo oculta, escenario congelado (409). **Regresión:** buzón, PDFs, misiones, marcador, cierre y escritorio siguen en verde (`demo_partida` 106/106).
