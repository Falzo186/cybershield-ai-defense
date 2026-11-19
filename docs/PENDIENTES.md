# Pendientes (matriz viva)

| Id | Descripción | Sev. | Causa | Solución | Estado |
|---|---|---|---|---|---|
| P-01 | No existe victoria/derrota formal para ambos equipos | crítica | Las capas bloquean todo; no hay zonas de política ni verdad de fondo | Módulo `src/lab/combate/` (F2) | abierto |
| P-02 | Combate IA vs IA con 8B gobernado por Harness | crítica | La batalla actual mide fugas, no ganador | F3 | abierto |
| P-03 | Wazuh simulado correlacionado por partida, con ruido | alta | Solo hay lectura/adaptador | `src/lab/wazuh_sim/` (F4) | abierto |
| P-04 | `eventos_ejemplo.jsonl` no versionado | media | `.gitignore` `*.jsonl` | reconstruido + excepción | **resuelto** (F0) |
| P-05 | `ejecutar_pruebas.py` cae por cp1252 | baja | consola Windows | reconfigure utf-8 | **resuelto** (F0) |
| P-06 | `docs/capturas_demo/` borrado en el árbol de trabajo | baja | corrida interrumpida del E2E | restaurar desde git | abierto (B-1) |
| P-07 | Campañas con 8B (nunca medidas con 8B) | alta | solo se midió llama3.2:3b y qwen2.5:7b | F7 | abierto |
| P-08 | UI de combate (Teatro de batalla) | alta | no existe | F6 | abierto |
| P-09 | RAG sin embeddings | baja | `nomic-embed-text` presente pero no usado | fuera de alcance | aplazado |
| P-10 | Wazuh real | media | no hay instancia | contrato + prueba condicional | aplazado (externo) |
