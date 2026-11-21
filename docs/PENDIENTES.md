# Pendientes (matriz viva)

| Id | Descripción | Sev. | Causa | Solución | Estado |
|---|---|---|---|---|---|
| P-01 | No existe victoria/derrota formal para ambos equipos | crítica | Las capas bloquean todo; no hay zonas de política ni verdad de fondo | Módulo `src/lab/combate/` (F2) | **resuelto** (commit b2daa1d; 15 escenarios, 70+33+41 pruebas) |
| P-02 | Combate IA vs IA con 8B gobernado por Harness | crítica | La batalla actual mide fugas, no ganador | F3 | **resuelto** (partidas reales con qwen3:8b y llama3.1:8b; ver campañas) |
| P-03 | Wazuh simulado correlacionado por partida, con ruido | alta | Solo hay lectura/adaptador | `src/lab/wazuh_sim/` (F4) | **resuelto** (19 pruebas; integración con motor y UI) |
| P-04 | `eventos_ejemplo.jsonl` no versionado | media | `.gitignore` `*.jsonl` | reconstruido + excepción | **resuelto** (F0) |
| P-05 | `ejecutar_pruebas.py` cae por cp1252 | baja | consola Windows | reconfigure utf-8 | **resuelto** (F0) |
| P-06 | `docs/capturas_demo/` borrado en el árbol de trabajo | baja | corrida interrumpida del E2E | restaurar desde git | **resuelto 2026-11-19** (fusionado con P-12; restauradas desde git por orden del usuario) |
| P-07 | Campañas con 8B (nunca medidas con 8B) | alta | solo se midió llama3.2:3b y qwen2.5:7b | F7 | **resuelto 2026-11-19** (campaña `combate-v1`: 2 370 partidas, 510 con 8B reales; ver `docs/evaluacion/INFORME_CAMPANAS.md`) |
| P-08 | UI de combate (Teatro de batalla) | alta | no existe | F6 | **resuelto** (`/combate/`, E2E 41/41, capturas 1366/1920/1280) |
| P-09 | RAG sin embeddings | baja | `nomic-embed-text` presente pero no usado | fuera de alcance | aplazado |
| P-10 | Wazuh real | media | no hay instancia | contrato + prueba condicional | aplazado (externo) |
| P-11 | Fila de partida a medias tras cortar una campaña rompía el relanzamiento (`UNIQUE constraint failed`) | alta | `Partida` usaba un id fijo por (escenario, semilla, modelos) | ids únicos `-2`, `-3`; recuperación de partidas terminadas sin observación | **resuelto** (D-10) |
| P-12 | `docs/capturas_demo/` borrado en el árbol de trabajo (31 archivos tracked) | baja | corrida interrumpida del E2E anterior; `git checkout` denegado por el entorno | restaurar con `git checkout -- docs/capturas_demo` | **resuelto 2026-11-19** (duplicado de P-06; `git checkout -- docs/capturas_demo` autorizado por el usuario; árbol limpio) |
| P-13 | Wazuh real (prueba contra instancia) | media | no hay instancia en este laboratorio | contrato + `RealProvider` stub + prueba condicional omitida | externo |
| P-14 | TLS/autenticación de transporte | media | sin certificados ni proxy en esta máquina | configuración documentada en `SEGURIDAD.md`, no verificada | externo |
| P-15 | Variación «con Harness / sin Harness» de las campañas | baja | el Harness ahora siempre gobierna la partida; no hay camino sin él | no se mide su efecto aislado | **medido, exploratorio (2026-11-21)**: estricto vs holgado 15/15 VICTORIA_AZUL en ambas, los topes estrictos nunca cortaron (≈19 llamadas vs tope 24); no se mide efecto real, ver `INFORME_CAMPANAS_V2.md` §Fase D |
| P-16 | Cruzada de `combate-v2` con n=30 por sentido | media | el tope de 4 h se agotó tras el espejo | ampliar a 8 repeticiones (≈ 3 h más) | abierto (2026-11-21) |
| P-17 | Azul llama3.1:8b con prompts v3 sobre-rechaza (87,5 % de legítimas falladas) | alta | el modelo no casa el par «recurso:acción» en la lista de derechos; 3 iteraciones de prompt no lo corrigieron | otro formato del registro, otro modelo o ajuste fino | abierto (2026-11-21) |
| P-18 | Efecto aislado del Rojo v3 | baja | se cambiaron Azul v3 y Rojo v3 a la vez | campaña con Rojo v3 y Azul v2 | abierto (2026-11-21) |
