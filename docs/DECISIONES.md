# Decisiones técnicas y cambios intencionales (misión 23 h)

| # | Decisión | Por qué | Cómo se ve |
|---|---|---|---|
| D-01 | Módulo nuevo `src/lab/combate/` en vez de ampliar `motor.py` | El `motor.py` anterior mide fugas por ronda; el combate necesita estado, objetivos y resultado. Mezclarlos habría roto pruebas y la tesis. | Nuevo paquete; el anterior intacto |
| D-02 | El Azul decide con el **registro del sistema** (derechos, autorizaciones) y no con el texto | Es el principio «el texto es un dato, no una orden». La verdad de fondo se deriva de ese mismo registro. | `politica_defensor` en los JSON |
| D-03 | Rojo solo texto natural + referencia a un recurso/acción **del catálogo** | Límites éticos del atacante (archivo 02). El catálogo es lo que el escenario expone por diseño; sin descubrimiento autónomo ni memoria entre partidas. | `RojoOllama`; filtro `PROHIBIDO` |
| D-04 | Sin memoria entre partidas | Mismo motivo. Cada `Partida` empieza con historial vacío; las campañas no entrenan. | Pruebas y diseño |
| D-05 | El Rojo no ve las zonas de política | Un atacante real no sabe qué aprueba el sistema por sí mismo. | Contexto del Rojo sin `zona` (probado) |
| D-06 | Objetivos solo sobre recursos `DELEGADO_AL_DEFENSOR` | «Sin objetivos imposibles». Los `DENEGADO` son señuelos que miden defensa en profundidad. | `validar()` |
| D-07 | Marcas de tiempo reales; el hash de cada evento **no** las incluye | Historial legible y a la vez eventos reproducibles con la misma semilla. | Cambio intencional de la primera versión (reloj lógico) |
| D-08 | Variante `sin_autorizaciones` en las campañas | Con el registro completo, rechazar es trivial y el Rojo casi no puede ganar. Esta variante modela que el sistema de tickets no es consultable (verificación imposible), el dilema real de la familia «verificación falsa». Una sola variable por vez. | `config` en cada observación |
| D-09 | Campañas con dos procesos (`base` sin GPU y `llm`) | La línea base trivial no usa la GPU; no hay razón para esperarla. Candado y base de partidas propios por sufijo. | `lock-llm.pid`, `partidas-llm.db` |
| D-10 | `Partida` asigna ids únicos (`-2`, `-3`…) si el id ya existe | Un corte de la campaña dejó una fila a medias y reventó el relanzamiento (`UNIQUE constraint failed`). Defecto propio, encontrado y corregido; la huérfana no cuenta. | `test_combate` |
| D-11 | Muestra de eventos de Wazuh **reconstruida** (`integraciones/wazuh/eventos_ejemplo.jsonl`) | El archivo original nunca se versionó (`.gitignore *.jsonl`); 5 pruebas de la línea base fallaban por eso. Se reconstruyeron 12 eventos con el esquema del contrato. **No es el archivo original.** | `.gitignore`, `00_ESTADO_INICIAL.md` |
| D-12 | `ejecutar_pruebas.py` reconfigura stdout a UTF-8 | Consola Windows cp1252 tumbaba el informe con tildes. | Cambio mínimo |
| D-13 | E2E con el Edge/Chrome instalado si no hay Chromium de Playwright | No descargar ~150 MB; autorizado instalar solo lo necesario. | `lanzar_navegador()` |
| D-14 | `parte` del `Partida`: contextos de los modelos son copias profundas | Un modelo que mutara su contexto alteraría el escenario en memoria (lo detectaría el hash, pero mejor aislarlo). | Prueba «Azul que muta su contexto» |

## Misión extra (2026-11-19)

| Id | Decisión | Por qué | Evidencia |
|---|---|---|---|
| D-15 | Prompts v3 en un módulo aparte (`src/lab/combate/prompts_v3.py`) y se piden con el sufijo `@v3` en el nombre del modelo (`qwen3:8b@v3`) | v2 y `combate-v1` no se pueden tocar y los resultados deben poder compararse lado a lado. El sufijo viaja en el id de celda, en `config.version_prompts` y en la observación. | Prueba: huella de v2 idéntica a la de `pre-mision-extra` |
| D-16 | Azul v3 se **congeló tras tres iteraciones (v3a, v3b, v3c) evaluadas con S1–S3/C1 (16 repeticiones)** y se eligió **v3b**, la de mejor balance | Regla de 3 intentos. v3c (campos que «copian» el par pedido) rompió a qwen: aprobó 16/16 un ticket inventado; v3a/v3b mejoran a qwen (S1 sin derecho 0/16 aprobadas, antes 16/16) pero llama no verifica bien (S1 con derecho 9/16). Los 3 resultados se conservan. **Consecuencia metodológica:** S1–S3 son **en muestra** para v3 (se ajustó mirándolas); la evidencia independiente es la campaña completa. | `docs/evaluacion/combate-v2/sens_*.json` |
| D-17 | El Rojo v3 usa solo el historial de **esta** partida (recursos ya intentados / aún no intentados, 4 últimos turnos) | Es lo que pidió la misión: variar recurso y justificación sin memoria entre partidas ni lectura de resultados previos. No cambia criterios de victoria, umbrales ni tráfico legítimo. | `prompt_rojo_v3`, prueba unitaria |
| D-18 | Partidas «curadas» = **copia verbatim** de 3 partidas reales de `combate-v1` en `data/demo_curadas/*.json` (fila, eventos con hashes y alertas SIMULADAS), servidas en solo lectura | Las bases de las campañas están ignoradas por git y no viajarían con el repositorio; el JSON conserva la cadena de hashes (la API la recomprueba). No se editan eventos. | `experimentos/exportar_curadas.py`, E2E extra |
| D-19 | El «Guion determinista (sin IA)» reutiliza `falso:objetivos` contra `falso:aprobar` / `falso:registro` y muestra una **etiqueta permanente** «GUION DETERMINISTA — NO ES UN MODELO» siempre que el Rojo no es un modelo | Evita que una victoria Roja guionada se confunda con una de IA. La etiqueta se decide por el nombre del jugador persistido, no por el navegador. | E2E extra |
| D-20 | La mitigación «lanzador desacoplado» **no protege de un corte de árbol de procesos** (`taskkill /T`) | Medido en `INCIDENTE_LANZAMIENTO.md`: el hijo desacoplado también muere; solo sobrevive si se mata únicamente al padre. La protección real es la reanudación. | Adenda del incidente |
| D-21 | Fase D (P-15): «Harness estricto» vs «holgado» = **los mismos controles activos**, solo cambian los topes del presupuesto (llamadas, tokens, errores consecutivos, tiempo) | No se desactiva el Harness ni ninguno de sus controles. | `campana_combate.py --fases harness` |

## Cambios de aserción de pruebas previas
Ninguno: no se modificó la aserción de ninguna prueba anterior. Las 5 suites que fallaban en la línea base fallaban por causas de entorno (ver `docs/auditoria/00_ESTADO_INICIAL.md`).

## Misión Caminos (2026-11-21)

| Id | Decisión | Por qué | Evidencia |
|---|---|---|---|
| D-22 | El modo Caminos es un **grafo de decisión fijo** (16 recorridos, 8/8) y no una ampliación del combate libre | El combate libre dejó al Rojo sin «puerta abierta» (0/240, 0/300). Un grafo fijo da al Rojo un camino genuino sin autoaprendizaje ni memoria entre partidas, y al Azul contrajugadas genuinas. | `docs/CAMINOS.md`, `src/lab/caminos/grafo.py` |
| D-23 | Las tres variantes (sencillo/intermedio/complejo) comparten el **mismo grafo y las mismas 16 hojas**; cambia lo que el Azul VE | Conservar el equilibrio exacto 8/8 era más importante que inventar hojas; el validador lo exige. | `validar()` |
| D-24 | Cinco nodos del Rojo tienen una única opción (continuación narrativa) | Añadir una opción de abandono habría añadido hojas Azules y roto el 8/8. La decisión real del Rojo es su primer movimiento y, con sesión, pedir la base o pivotar. Se declara como limitación. | `CAMINOS.md` § Limitación |
| D-25 | El motor de Caminos **reutiliza** `combate.store` (auditoría con hash) y el Wazuh simulado; reglas Wazuh nuevas 100050–100058 | Evita duplicar la cadena de auditoría; todo sigue rotulado SIMULADO. | `reglas.py` |
| D-26 | Toda partida lleva `tipo` (`CAMINOS_GUION`/`CAMINOS_IA`) y una victoria Roja de guion **nunca** se presenta como «la IA venció» | Honestidad de procedencia exigida por el encargo. | UI, API, tests |
| D-27 | Honeytoken en el modo automático = victoria Azul **inmediata**, aunque el Azul apruebe | Es la contramedida de alta confianza del diseño; el resultado lo da el motor al detectar el uso. | `test_caminos_auto` |
| D-28 | Las credenciales del modo automático (3 válidas, 3 inválidas, 2 señuelo) son **fijas y ficticias**; el Rojo no ve la validez | Sin generación ni descubrimiento autónomo de credenciales. | `ESCENARIO`, tests de visibilidad |
| D-29 | Modelos 8B **re-descargados** al iniciar Caminos: `~/.ollama` estaba vacío | Autorizado por `MISION_23H/05` (hasta 3 modelos, ≥ 30 GB libres; había 44 GB). Se descargaron `qwen3:8b` y `llama3.1:8b`. | `BLOQUEOS.md` |
| D-30 | La campaña no cambia prompts a mitad (versión `c1`) y los resultados de los 8B se reportan como salen | Regla 02. | `VERSION_PROMPTS_CAMINOS` |

## D-31 · Prompts de IA controlados por directiva y oportunidades (Nova)
Decidido con el usuario: la IA nunca lanza prompts por sí sola; el jugador elige partes de catálogo (combos) y cada lanzamiento gasta una de 10 oportunidades por equipo (configurable). La credencial obtenida se desbloquea en el combo; la aleatoria se pide con estructura. Un intento casi correcto genera una solicitud sospechosa al Azul (aceptar/denegar). Por equipo, no por jugador. Modo `libre` se conserva solo para experimentos.
