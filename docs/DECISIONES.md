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

## Cambios de aserción de pruebas previas
Ninguno: no se modificó la aserción de ninguna prueba anterior. Las 5 suites que fallaban en la línea base fallaban por causas de entorno (ver `docs/auditoria/00_ESTADO_INICIAL.md`).
