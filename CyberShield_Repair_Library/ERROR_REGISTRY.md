# Registro de errores (CyberShield Repair)

Metodología: antes de tocar código se escribió una **regresión de 26 comprobaciones contra el servidor real** (`tests/regression/test_regresion_presentacion.py`) y se registró la línea base. Cada fila es un hallazgo con evidencia, no una suposición. IDs `E-nn`.

**Línea base (rama `mision-extra`, etiqueta `pre-repair`):** pruebas existentes 100 % verdes salvo el umbral de rendimiento B-2; regresión de la presentación: **17 PASS · 3 FAIL · 6 NO_IMPLEMENTADO de 26**.

| ID | Síntoma (línea base) | Regresión | Causa raíz | Corrección | Estado |
|---|---|---|---|---|---|
| E-01 | No se puede pausar ni reanudar (`405`) | 19, 20 | `Partida` solo tenía preparación→en_curso→finalizada | `Partida.pausar/reanudar` (tiempo congelado), rutas del árbitro, 409 en acciones nuevas, UI | **corregido** |
| E-02 | Quien sale desaparece de la lista; no hay estado de conexión | 8 | `Sala.cerrar_sesion` borraba al participante y no había presencia | `listado_publico()` con `conectado`/`desconectado`, latido `/api/presencia`, vigilante de presencia | **corregido** |
| E-03 | Sin notificaciones ni contador de no leídos | 12 | el backend no emitía eventos de correo ni contaba lecturas | SSE `correo_nuevo`/`buzon_estado` (mínimos), `no_leidos` por participante | **corregido** |
| E-04 | Un reintento duplica el correo | 23 | sin idempotencia | cabecera `Idempotency-Key` (almacén con TTL, por token+ruta) | **corregido** (opt-in por cabecera) |
| E-05 | Sin correos del escenario | 9 | no existía | 6 correos ficticios por tiempo de partida, idempotentes, sin enlaces | **corregido** |
| E-06 | Sin solicitudes de autorización | 13, 14 | no existía | máquina de estados persistente + API + SSE + hook del defensor IA | **corregido** |
| E-07 | Sin chat de equipo | (27) | no existía | `ChatEquipos` aislado por equipo | **corregido** |
| E-08 | Rojo solo podía enviar plantillas | (28) | catálogo cerrado | correo libre de texto plano sin URLs | **corregido** |
| E-09 | Sin diagnóstico de salud | (29) | no existía | `GET /api/salud` | **corregido** |
| E-10 | Acciones de pausa/autorización/escenario no figuraban en la cronología | — | `informe.ACCIONES` no las conocía | nuevas acciones y categoría `autorizacion` | **corregido** |
| E-11 | Chat duplicado en la Sala (dos cargas simultáneas) | E2E | carrera entre SSE y envío | una carga a la vez + ids vistos | **corregido** |
| E-12 | Estilo roto de las solicitudes | E2E | choque de clase `.linea` con `combate.css` | clase renombrada | **corregido** |
| E-13 | Una pausa no debe cancelar un ataque IA ya lanzado | — | la comprobación exigía `en_curso` | acepta `en_curso`/`pausada` al cerrar | **corregido** |
| E-14 | Carrera preexistente en `e2e/demo_partida.py` (espectador por sondeo) | misión extra | la prueba no esperaba la propagación | espera explícita | **corregido** |

## No reproducido (con honestidad)
- **«La batalla comenzaba sola y los modelos generaban en bucle» (presentación):** en el código actual **no se reproduce** el arranque automático: entrar a pantallas no hace ninguna llamada a `/api/chat` (regresión 2) y la partida solo empieza por el árbitro (regresión 4). El límite de «una inferencia a la vez» y el tope de ataques ya existían (regresión 18). No se sabe si el síntoma venía de otra versión o de la práctica «mejor de N»; **no se afirma una causa**.
- **«Los jugadores no se ven / equipos mal asignados»:** ya funcionaba a nivel de API (regresión 5, 6); lo que faltaba era una pantalla de equipo que lo mostrara en vivo (ver Sala de equipo, `/equipo/`).
