# Estado inicial (F0) — misión 23 h

Fecha: 2026-11-18 · Commit base: `4dbdb35` (main) · Rama de trabajo: `mision-23h`

## 1. Git
Rama `main`, árbol limpio salvo `MISION_23H/` sin versionar. Remoto `origin` = GitHub (**no se toca**: sin push). Ramas locales: solo `main`; remotas: `origin/main`.

## 2. Entorno medido
| Dato | Valor |
|---|---|
| Ollama | 0.32.5 (Windows), servidor local `127.0.0.1:11434` |
| GPU | NVIDIA GeForce RTX 5060, 8 151 MiB VRAM (≈1,5 GiB ya en uso por el sistema) |
| Disco | 46 GB libres de 465 GB (91 % usado) |
| Modelos 8B ya instalados | `qwen3:8b` (5,2 GB), `llama3.1:8b` (4,9 GB). No hace falta descargar nada. |
| Otros | `qwen3:4b`, `qwen2.5:1.5b`, `qwen2.5-coder:*`, `gemma4:12b` (8 GB, no cabe junto a otro), `nomic-embed-text` |
| Python | 3.12.5; faltaba `fastapi`/`uvicorn` (declarados en `requirements.txt`) → instalados |

Velocidad medida (num_predict=150, temp 0,2): `qwen3:8b` ≈ 20 tok/s en caliente, 25 s de carga en frío; `llama3.1:8b` ≈ 25 tok/s, 8 s de carga en frío. Dos modelos de 8B **no caben a la vez** en 8 GB de VRAM: la partida cruzada implica conmutar (ver `docs/MODELOS.md`).

## 3. Inventario real de módulos (0 / 0,5 / 1)
| Módulo | Existe | Integrado en partidas reales | Probado | Estado |
|---|---|---|---|---|
| Capas deterministas (permisos/herramientas/repositorio) | sí | sí | sí | 1 |
| Equipos con token, sala, partida por tiempo (`server/partida.py`) | sí | sí | sí | 1 |
| Buzón, PDF, misiones, marcador, incidentes | sí | sí | sí | 1 |
| Motor de reglas evento→consecuencia | sí | sí | sí | 1 |
| Harness (`harness.py`, `ControlPartida`) | sí | sí (batalla del defensor) | sí | 1 |
| Campaña del atacante (`experimentos/campana_atacante.py`) | sí | sí | sí | 1 |
| Evaluación (`evaluacion/`: Wilson, bootstrap agrupado) | sí | sí | sí | 1 |
| RAG | sí | parcial (BM25, sin embeddings) | sí | 0,5 |
| Wazuh | adaptador de **solo lectura** + reglas + modo simulado de alertas a partir de eventos | no hay instancia real | sí | 0,5 |
| **Motor formal de victoria/derrota** (zonas de política, verdad de fondo, objetivos, resultado inmutable) | **no** | no | no | **0** |
| **Combate IA vs IA con ganador para ambos equipos** | no (la batalla existente solo mide "engaño"/fuga) | no | no | **0** |
| Wazuh simulado correlacionado por partida con ruido y esquema compatible | no | no | no | 0 |

Conclusión: la batalla existente mide fugas de datos y engaño del defensor, pero **el Rojo nunca puede "ganar" de forma verificable** (las capas bloquean todo) y no hay resultado de partida para ambos equipos. Es el hueco que cubre esta misión.

## 4. Línea base de pruebas (commit 4dbdb35, `python ejecutar_pruebas.py --rapido`)
33 suites. Fallos de línea base y su causa:
| Suite | Causa raíz | Acción |
|---|---|---|
| `server/test_app|batalla_partida|resultados|apps|presupuesto` | `fastapi` no estaba instalado en este Python | `pip install fastapi uvicorn` |
| `test_wazuh` (2), `test_correlacion` (3), `integraciones/wazuh/test_reglas`, `server/test_panel` (1) | `integraciones/wazuh/eventos_ejemplo.jsonl` **nunca se versionó**: `.gitignore` excluye `*.jsonl` | Muestra reconstruida (12 eventos con el esquema del contrato) y excepción en `.gitignore`. **Es una reconstrucción, no el archivo original.** |
| `ejecutar_pruebas.py` | `UnicodeEncodeError` (cp1252) al imprimir el resumen en consola Windows | `sys.stdout.reconfigure(utf-8)` |
| (efecto lateral) | la corrida con navegador interrumpida dejó **borrados** 31 archivos de `docs/capturas_demo/` (el test los mueve y restaura al final) | Sin restaurar todavía (ver `BLOQUEOS.md` B-1); no se incluyen en los commits |

Tras las correcciones: **33/33 suites en verde, 1 581/1 581 comprobaciones** (modo rápido).

## 5. Procesos y locks
Sin campañas colgadas ni servidores duplicados. Ollama corriendo (aplicación de escritorio).

## 6. Error `exit code 4` de las campañas
Ya diagnosticado el 07/11 (`docs/INCIDENTE_LANZAMIENTO.md`): el código 4 **no puede salir del programa** (sus únicas salidas son 0/1/2/130); el envoltorio del shell fue terminado desde fuera. En esta misión las campañas se lanzan con un lanzador propio **desacoplado** (proceso separado, PID y progreso en archivo, reanudable). Se verifica con prueba corta en F1.

## 7. Deuda técnica
Ver `docs/PENDIENTES.md`.
