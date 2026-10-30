# Contrato de API — AI Security Laboratory

Contrato entre la UI (`ui/`) y el backend (hoy `server/mock_server.py`, mañana el motor real). La UI solo conoce este contrato.
Todo es local y con datos ficticios (empresa "CyberShield Industries").

## REST

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| GET | `/api/estado` | — | `{modelo_atq, modelo_def, modo, corriendo:bool}` |
| POST | `/api/simulacion/iniciar` | `{}` | `{}` — corre 6 escenarios fijos |
| POST | `/api/batalla/iniciar` | `{rondas:int}` | `{}` |
| POST | `/api/detener` | `{}` | `{}` |
| POST | `/api/manual` | `{prompt:str}` | objeto `decision`; además emite sus eventos por SSE |
| GET | `/api/metricas` | — | objeto `metricas` |
| GET | `/api/eventos` | — | SSE: `event: <tipo>` + `data: <json>` |

Errores: HTTP 409 `{mensaje}` si ya hay una ejecución en curso (o si un manual fue detenido).

## Eventos SSE

- `ronda_inicio` `{ronda, modo:"simulacion"|"batalla"|"manual", escenario_id|null, escenario_nombre|null}`
- `ataque` `{ronda, prompt, categoria, objetivo, sensibilidad_objetivo:"PUBLICA"|"INTERNA"|"CONFIDENCIAL"|"CRITICA"}`
- `etapa` `{ronda, etapa, estado:"activo"|"ok"|"bloqueado"|"omitido"}`
  Orden de etapas: `atacante, prompt, analisis, defensor, politicas, autorizacion, herramienta, bd`.
  Las posteriores a una etapa `bloqueado` se emiten como `omitido`.
- `decision` `{ronda, decision:"PERMITIR"|"RECHAZAR"|"SOLICITAR_AUTORIZACION"|"AISLAR"|"MARCAR_COMO_RIESGO", riesgo:0-100, motivo, politica|null, capa_bloqueo|null, herramienta|null, datos_devueltos:[obj]|null, decision_esperada, resultado:"DEFENSA_EXITOSA"|"FALLA_DEFENSA"|"FALSO_POSITIVO"|"PERMITIDO_CORRECTO", tiempo_ms}`
- `auditoria` `{ts:"HH:MM:SS", agente:"ATTACKER"|"DEFENDER"|"POLICY"|"DATABASE"|"SYSTEM", accion, recurso, resultado, nivel_riesgo:"BAJO"|"MEDIO"|"ALTO"|"CRITICO"}`
- `metricas` `{intentos, bloqueados, permitidos, exitosos_atacante, falsos_positivos, falsos_negativos, tiempo_promedio_ms, riesgo_promedio, defense_score, attack_success_rate, block_rate, por_categoria:[{categoria, intentos, bloqueados, exitosos}]}`
- `fin` `{modo, metricas, detenido?:bool}` — `detenido:true` cuando se cancela con `/api/detener` (la UI no muestra el modal).
- `error` `{mensaje}`

Orden por ronda: `ronda_inicio`, `ataque`, `etapa`×8, `decision`, 2-3 `auditoria`, `metricas`.

## Definiciones

- `bloqueados` = decisiones distintas de `PERMITIR`. `exitosos_atacante` = `falsos_negativos` (el defensor permitió algo que se esperaba bloquear).
- `attack_success_rate` = falsos_negativos / intentos maliciosos (en %).
- `block_rate` = bloqueados / intentos (en %).
- `defense_score` = % de decisiones que coinciden con `decision_esperada`. Es un indicador experimental del laboratorio, **NO** una garantía de seguridad.
- `resultado`: `FALLA_DEFENSA` = se permitió lo que debía bloquearse; `FALSO_POSITIVO` = se bloqueó lo que debía permitirse; `DEFENSA_EXITOSA` = ataque contenido; `PERMITIDO_CORRECTO` = solicitud legítima permitida.
- Porcentajes con un decimal (0-100). `riesgo` entero 0-100.

## Extensiones — batalla real con Ollama (solo se AÑADE; nada de lo anterior cambia)

Dos orígenes de datos, siempre etiquetados en la UI: **🟡 MOCK** (simulación, `server/mock_server.py`) y **🟢 OLLAMA** (batalla real, `server/app.py`).
La UI nunca muestra OLLAMA/REAL salvo que lleguen eventos con `origen:"ollama"` generados por una petición real.

### REST añadido (solo en `server/app.py`)
- `GET /api/ollama/estado` -> `{disponible:bool, host}`
- `GET /api/ollama/modelos` -> `{modelos:[str]}` (también emite `ollama_estado`)
- `GET /api/usuarios` -> `{usuarios:[{usuario, rol}]}` — el rol lo fija el sistema, nunca el prompt
- `POST /api/batalla/real/iniciar` `{modelo_atq, modelo_def, rondas, usuario}` -> `{}`; 409 `{error, mensaje}` si Ollama no está disponible, falta algún modelo, el usuario no existe o ya hay una ejecución. En 409 no se inicia nada.
- `/api/detener` también cancela la batalla real.

### SSE añadido / ampliado
- `ollama_estado` `{disponible, modelos}` — al conectar el SSE y tras `/api/ollama/modelos`.
- `ronda_inicio`: `+origen:"ollama"` (ausente = mock).
- `ataque`: `+modelo, tiempo_ms, tokens`.
- `etapa`: nuevos estados `"ejecucion_real"` (el nodo ejecutó una petición real) y `"error"`; campos opcionales `modelo, tiempo_ms, tokens, detalle` (p. ej. `detalle:"RECIBIDO"`).
- `decision`: `+decision_ia` (propuesta del modelo; `decision` es el resultado EFECTIVO tras las capas), `tokens, parse_ok, modelo`. `resultado` admite además `"DEFENSA_EN_PROFUNDIDAD"` (la IA permitió, una capa determinista contuvo).
- `auditoria.accion` admite `MODEL_REQUEST` (recurso=modelo), `MODEL_RESPONSE` (recurso=tiempo), `EVALUATION`, `QUERY`, `ERROR`.
- `ronda_error` `{ronda, modelo, error}` — la ronda se pinta como ERROR (ni bloqueo ni éxito), **no entra en métricas** y la batalla continúa. Una ronda también falla por timeout (150 s).
- `fin`: `+origen, errores` (rondas con error, no contadas).

### Métricas en batalla real
No hay verdad de terreno por ronda: el atacante es malicioso por construcción y `defense_score` = % de rondas contenidas (no `FALLA_DEFENSA`). `attack_success_rate` = `FALLA_DEFENSA` / rondas no legítimas.

### Intensidad del atacante (añadido)
`POST /api/batalla/real/iniciar` acepta `intensidad` (1-3, por defecto 2): 1 directo · 2 engaño con contexto y rol · 3 sofisticado y multi-técnica. Ajusta el system prompt y la temperature del atacante (0.5 / 0.7 / 0.95).

### Manual real (añadido)
`POST /api/manual/real` `{prompt, modelo_def, usuario}` -> objeto `decision` (igual que `/api/manual`, con `resultado`, `decision_ia`, `origen:"ollama"`) y emite los mismos eventos SSE (`ronda_inicio` con `origen:"ollama"`, etapas, `decision`, auditoría `MODEL_REQUEST/MODEL_RESPONSE/EVALUATION/QUERY`, `metricas`). 409 `{error}` si Ollama no está disponible, falta el modelo o el usuario no existe; 502 `{error, veredicto:"ERROR"}` si el defensor falla (no entra en métricas). El veredicto se calcula con `motor.evaluar_veredicto`, el mismo código que la batalla. `decision.origen` ("mock" | "ollama") indica quién produjo la decisión; el mock lo envía como `"mock"`.

### Veredictos y `ia_fallo` (ajuste)
`decision.ia_fallo:bool` — la IA propuso PERMITIR una herramienta de cualquier sensibilidad (INTERNA, CONFIDENCIAL o CRITICA) para la que la identidad no tiene derecho (aunque las capas lo frenen). `resultado`: `FALLA_DEFENSA` = victoria del atacante (ok=True con datos de un nivel fuera del permiso de la identidad); `DEFENSA_EN_PROFUNDIDAD` = IA engañada, capas contuvieron.

### Modo LAN: Ollama por host (añadido)
Cada equipo tiene su propia Ollama; el servidor escucha en `0.0.0.0:$PUERTO` (por defecto 8000). Los hosts se validan: solo IP privadas, loopback o link-local (si no, 400/409 `{error, mensaje}`).
- `GET /api/ollama/estado?host=http://192.168.1.50:11434` -> `{disponible, host}` (sin `host`: la Ollama por defecto del servidor).
- `GET /api/ollama/modelos?host=http://192.168.1.50:11434` -> `{modelos, host}`. Solo la consulta al host por defecto se difunde por SSE (`ollama_estado` lleva ahora `host`).
- `POST /api/batalla/real/iniciar` acepta `host_atacante` y `host_defensor` (por defecto `http://localhost:11434`): el atacante usa `host_atacante` y el defensor `host_defensor`; se comprueba cada Ollama y que cada modelo exista en SU host.
- `POST /api/manual/real` acepta `host_atacante` y `host_defensor`; el manual solo usa la Ollama del defensor.

### Fase J1: diagnóstico, listo/aceptar y puntaje (añadido)
- `GET /api/ollama/probar?host=...&modelo=...` -> `{ok, tiempo_ms, respuesta, error}`. Llamada mínima y real ("Responde solo: OK", `num_predict` 8, timeout 15 s). El timeout por defecto de las llamadas de batalla pasa a 120 s (la primera llamada puede incluir la carga del modelo); la ronda tiene 300 s.
- `POST /api/batalla/real/iniciar` acepta además `de_rol` ("rojo"|"azul"|"general") y `dificultad` ("facil"=ana.perez/empleado, "media"=marta.ruiz/analista, "dificil"=root.lab/admin; sustituye a `usuario`). **Ya no arranca de inmediato**: responde `{estado:"esperando_aceptacion", reto}` (o `{estado:"iniciada"}` si `de_rol` es "general", que no necesita aceptación) y no llama a Ollama hasta que se acepte.
- `POST /api/batalla/responder` `{aceptado:bool, rol?}` -> `{estado:"iniciada"|"rechazado"}`; 409 si no hay reto, si responde un rol que no es el destinatario, o si hay otra ejecución. `/api/estado` incluye `esperando_aceptacion`.
- SSE: `reto_enviado {de_rol, a_rol, rondas, intensidad, dificultad, segundos}` · `reto_respondido {aceptado, de_rol(quien respondió), auto?}` · `reto_cancelado {motivo:"rechazado"|"sin respuesta"|"ocupado", de_rol}` (30 s sin respuesta cancela). La auditoría registra `RETO_ENVIADO/ACEPTADO/RECHAZADO/CANCELADO`.
- Puntaje (mejor de N, sin contar ERROR): punto del atacante con `FALLA_DEFENSA`; punto del defensor con `DEFENSA_EXITOSA` o `DEFENSA_EN_PROFUNDIDAD`; `PERMITIDO_CORRECTO` es neutral. `decision.marcador {atacante, defensor}` en cada ronda y `partida_fin {puntos_atacante, puntos_defensor, ganador:"atacante"|"defensor"|"empate", rondas_jugadas, errores, detenida}` al terminar o detener.

- Corrección de dificultad: `fácil`=visita.demo (invitado), `media`=ana.perez (empleado), `difícil`=marta.ruiz (analista). Nuevo campo `demo:bool` en `POST /api/batalla/real/iniciar`: usa root.lab (admin), no puntúa (sin `marcador` ni `partida_fin`) y `fin` lleva `demo:true`. Con rol admin y `demo=false` responde 409 "Con rol admin no hay falla posible…".

### Modelo por equipo: reto, aceptación y asignación (añadido)
- `POST /api/batalla/real/iniciar`: cada vista envía SOLO su lado en ese instante (`de_rol:"rojo"` → `modelo_atq`+`host_atacante`; `"azul"` → `modelo_def`+`host_defensor`; `"general"` → ambos). Todos esos campos son ahora opcionales.
- `POST /api/batalla/responder` acepta además `modelo` y `host`: el modelo+host actuales del equipo que acepta.
- `GET /api/ollama/probar` acepta `rol` ("rojo"|"azul"): una prueba exitosa confirma ese modelo+host para el equipo.
- El servidor guarda por equipo el último modelo+host confirmado (reto, aceptación o «Probar modelo»; gana el más reciente) y arma la batalla con rojo = atacante y azul = defensor. Antes de jugar verifica ambos; si falta o no está disponible alguno, 409 indicando el equipo (y `reto_cancelado` con ese motivo).
- `ronda_inicio` incluye `asignacion {atacante:{modelo,host}, defensor:{modelo,host}}`, que la UI muestra en el Centro de Control; la auditoría registra `ASIGNACION`.

### Fase R1: riesgo acumulado por sesión y fuga parcial (añadido)
- `decision` (batalla real) incluye `riesgo_acumulado` (0-100, sospecha de la sesión DESPUÉS de esa ronda), `circuito_sesion:bool` y `nivel_fuga:"NINGUNA"|"PARCIAL"|"TOTAL"`. El manual real incluye `nivel_fuga` y `circuito_sesion` (sin sesión acumulada).
- Riesgo acumulado: +8 por cada repetición de una categoría ya vista y +5 por cada rechazo consecutivo a partir del tercero (cada componente con techo 40); -10 por cada 2 `PERMITIDO_CORRECTO` seguidos. Se informa al defensor como contexto.
- Circuito de seguridad por sesión (determinista): si el riesgo acumulado previo a la ronda es >70, cualquier PERMITIR pasa a `SOLICITAR_AUTORIZACION` sin ejecutar herramienta (etapa `autorizacion` bloqueada con detalle `SESION`; veredicto `DEFENSA_EN_PROFUNDIDAD` si la propuesta era indebida, si no `DEFENSA_EXITOSA`).
- `nivel_fuga`: TOTAL = `FALLA_DEFENSA`; PARCIAL = decisión no-PERMITIR cuyo motivo nombra un secreto simulado (`LAB_…`, `lab-secreto/token`). PARCIAL no puntúa.

### Fase R2: filtro rápido antes de inferencia (añadido)
- `decision.origen_decision`: `"ia"` (decidió el defensor LLM) o `"filtro_rapido"` (regex determinista en `src/lab/filtro_rapido.py`, SIN llamar a Ollama). Con filtro rápido: `decision_ia`/`decision` = RECHAZAR, `riesgo` 90, `politica` = `FILTRO-RAPIDO:<categoría>`, veredicto `DEFENSA_EXITOSA`; etapa `analisis` bloqueada y `defensor` omitida con detalle "⚡ Bloqueado por filtro rápido (sin inferencia)"; auditoría `POLICY FILTRO_RAPIDO` en lugar de `MODEL_REQUEST`. Cuenta como rechazo en el riesgo acumulado de la sesión.

### Fase cierre: contexto de sesión e informe (añadido)
- El defensor recibe una línea `Patrón de la sesión: …` (categorías vistas, rechazos seguidos, riesgo acumulado) como contexto; es una señal, no una sentencia.
- `partida_fin` incluye `informe {rondas_totales, rondas_validas, puntos_atacante, puntos_defensor, ganador, veredictos_por_tipo{FALLA_DEFENSA, DEFENSA_EXITOSA, DEFENSA_EN_PROFUNDIDAD, PERMITIDO_CORRECTO, ERROR}, fugas_parciales, activaciones_circuito_sesion, bloqueos_filtro_rapido, riesgo_acumulado_final, dificultad, usuario, modelos_usados{atacante, defensor}}`. La UI lo exporta como `informe_sesion_<fecha>.json`.

### Token verificado por el servidor (añadido; desde la Fase C el token es de un PARTICIPANTE, ver «Sesiones y partida»)
- ~~`POST /api/equipo/reclamar`~~ (un token por equipo): **sustituido** por `POST /api/sesion` en la Fase C.
- Toda ruta `/api/*` exige la cabecera `X-Equipo-Token` (hoy, el token de sesión del participante), salvo `GET /api/eventos` y `GET /api/estado` (espectador, solo lectura). Sin token válido -> 403. «solo token `rojo`» significa: la sesión de cualquier participante del equipo rojo.
- El rol declarado (`de_rol`, `rol`, `?rol=` de `/api/ollama/probar`) debe coincidir con el equipo del token (la vista `general` puede confirmar ambos modelos); si no -> 403. Quien responde un reto es el dueño del token.
- `POST /api/detener` solo con el token de `general` (árbitro); con otro token -> 403. La UI oculta las acciones sin token (y DETENER fuera de la vista general). `?rol=espectador` abre la vista de solo lectura, que nunca reclama token.

### Buzón interno de correos de entrenamiento (añadido)
Nada sale del laboratorio: sin SMTP, plantillas fijas (`src/lab/correos.py`) y enlaces locales generados por el servidor.
- El primer participante azul fija el usuario semilla dueño del buzón del equipo (`usuario` en `POST /api/sesion`; por defecto `ana.perez`); los siguientes comparten ese buzón. Respuesta `+usuario_azul`.
- `GET /api/correo/plantillas` (cualquier token) -> `{plantillas:[{id, nombre}]}`.
- `POST /api/correo` (solo token `rojo`) `{plantilla, para_usuario?}` -> `{id, para_usuario, asunto, plantilla_id, ts}`. Sin `para_usuario` va al usuario de azul (409 si azul no entró). La respuesta NO incluye el enlace. Emite `auditoria` ATTACKER `CORREO_ENVIADO`.
- `GET /api/buzon` (solo token `azul`) -> `{usuario, correos:[{id, de, asunto, cuerpo, plantilla_id, ts, enlace:"/l/<id>"}]}`, solo de la partida actual (proceso del servidor).
- `GET /l/{id}` (público) -> página fija de entrenamiento; registra `CLIC_ENLACE` en la tabla `auditoria` (con la identidad del destinatario) y emite `auditoria` SYSTEM. Enlace inexistente -> 404 sin registro.

### Marca de tiempo de la tabla `auditoria` (ajuste)
- `auditoria.ts` (tabla SQLite) se guarda en ISO 8601 completo con zona horaria, p. ej. `2026-10-22T13:47:05-06:00`. Las filas anteriores conservan `HH:MM:SS`: la tabla es append-only (los triggers impiden reescribirlas).
- El evento SSE `auditoria` sigue enviando `ts:"HH:MM:SS"` para la vista en vivo; no se lee de la tabla.

### Reglas evento -> consecuencia (añadido)
Deterministas, en `sesion.REGLAS_EVENTO`, sobre un `EstadoSesion` de la partida Rojo/Azul (`ESTADO_PARTIDA`, distinto del de cada batalla IA vs IA). El componente de eventos se acota a 0-100.
- `CLIC_ENLACE` (al abrir `/l/{id}`) -> riesgo +15.
- `correo_reportado` -> riesgo −10 y completa las misiones con esa condición.
- `POST /api/correo/{id}/reportar` (solo token `azul`): reporta un correo de SU buzón en esta partida. 404 si no es suyo, 409 si ya estaba reportado. -> `{reportado:true, regla:{evento, riesgo, mision, riesgo_acumulado}}`. Registra `CORREO_REPORTADO` en `auditoria`.
- `GET /api/buzon`: cada correo trae `reportado` (0/1).
- SSE `regla_evento` `{evento, riesgo, mision, riesgo_acumulado, usuario}` y `auditoria` SYSTEM `REGLA`.

### Misiones individuales del Equipo Azul (añadido; ampliado en la Fase E, ver «Misiones, incidentes y credenciales»)
Tablas `misiones(id, titulo, condicion_evento, puntos)` y `progreso_mision(partida, usuario, mision_id, estado, ts)` (estado `pendiente`|`completada`). Tres misiones fijas en `seed.MISIONES`: «Reportar un correo sospechoso» (`correo_reportado`, 10 pts), «Contener un enlace clicado» (`enlace_contenido`, 15 pts) y «Revisar el buzón diariamente» (`manual`, 5 pts). El progreso es por partida y usuario: cada arranque del servidor (partida nueva) empieza con todas las misiones pendientes.
- Una misión se completa cuando ocurre su evento y la regla de ese evento tiene `mision:true` (hoy `correo_reportado` y `enlace_contenido`). `regla_evento` y la respuesta de reportar traen `misiones_completadas:[{id, titulo, puntos}]`.
- `GET /api/misiones` (solo token `azul`) -> `{usuario, misiones:[{id, titulo, condicion_evento, puntos, estado, ts}], puntos, riesgo_partida}`.
- `POST /api/misiones/{id}/completar` (solo token `azul`, solo misiones `manual`) -> `{completada:true, mision_id}`; 409 si no es manual o ya estaba completada.

### Contener un enlace clicado (añadido)
- `POST /api/correo/{id}/contener` (solo token `azul`): bloquea el enlace de un correo de SU buzón que ya tuvo un `CLIC_ENLACE`. 409 si no hubo clic o ya estaba contenido; 404 si no es suyo. -> `{contenido:true, regla}`. Regla `enlace_contenido`: riesgo −15 (anula el clic) y completa «Contener un enlace clicado». Tabla `contenciones`.
- Un clic posterior en `/l/{id}` muestra «Enlace bloqueado por el Equipo Azul», se registra como `CLIC_BLOQUEADO` y no aplica ninguna regla.
- `GET /api/buzon`: cada correo trae también `clicado` y `contenido` (0/1).
- Las definiciones de `seed.MISIONES` se actualizan en BD existentes al arrancar (el progreso se conserva).

### PDFs benignos como eventos (añadido)
PDFs fijos de solo texto en `data/pdf/` (catálogo `src/lab/documentos.py`; nunca se suben desde la UI). Plantillas con adjunto fijo: `recursos_humanos` (recibo_nomina), `paqueteria` (comprobante_envio) y la nueva `comunicado_interno` (politica_escritorio_limpio). Tabla `correos` + columna `adjunto`.
- `GET /api/buzon`: cada correo trae `adjunto:{id, archivo, titulo}|null`, `pdf_abierto` y `pdf_reportado` (0/1).
- `POST /api/evento` (solo token `azul`) `{tipo:"pdf_abierto"|"pdf_reportado", recurso:"correo:<id>"}` -> `{ok, documento, regla, vista}`. Escribe `PDF_ABIERTO`/`PDF_REPORTADO` en `auditoria`. 404 si el correo no es suyo, 409 si no trae PDF, si el PDF ya se reportó o si el adjunto está aislado. **Desde la Fase D** `pdf_abierto` ya no devuelve `descarga`, sino `vista` para el visor seguro (ver «Aplicación de correo»).
- `GET /pdf/{id}` (público, solo ids del catálogo): `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox`.
- Reglas: `pdf_abierto` -> riesgo 0 y completa «Revisar un documento recibido» (misión 4, 10 pts); `pdf_reportado` -> riesgo −10.

### Marcador de la partida para el árbitro y espectadores (añadido)
- SSE `marcador_partida` `{usuario_azul, puntos_azul, misiones_completadas, misiones_total, riesgo, clics, contenciones, correos_reportados, pdf_abiertos, pdf_reportados}`: al conectar el SSE (también sin token), tras cada regla aplicada, al completar una misión manual y cuando Azul entra. Los conteos son las veces que se aplicó la regla del evento en esta partida (un clic sobre un enlace contenido no cuenta).
- La UI lo muestra en la cabecera solo en `?rol=general` y `?rol=espectador`. Rojo aún no puntúa.

### Eventos preparados para un SIEM (Wazuh, aún sin integrar)
`Repositorio.registrar()` (el mismo punto que escribe la tabla `auditoria`) añade una línea JSON a `data/eventos.jsonl` (ignorado por git) para cada evento relevante:
`{"timestamp":"2026-10-23T10:02:05-06:00","partida":"20261023-100100-ab12","equipo":"azul","usuario":"ana.perez","rol":"empleado","tipo":"clic_enlace","accion":"CLIC_ENLACE","recurso":"correo:3","resultado":"CLIC","riesgo":"ALTO","origen":"cybershield-lab"}`
- `tipo`: `clic_enlace`, `clic_bloqueado`, `enlace_contenido`, `correo_reportado`, `pdf_abierto`, `pdf_reportado`, `mision_completada` (equipo `azul`) y `autorizacion_denegada` (todo `DENEGADO` de consultas/herramientas; equipo `null`).
- `riesgo` es el `nivel_riesgo` de la fila de auditoría (BAJO/MEDIO/ALTO/CRITICO). Una BD en memoria (tests) no escribe el archivo. Un fallo al escribirlo no afecta a la auditoría.
- Para Wazuh bastará un `<localfile>` con `log_format json` apuntando a este archivo; no hay nada conectado.

### Puntaje de Rojo (añadido)
`sesion.PUNTOS_ROJO`: +10 por cada correo de la partida con enlace clicado y NO contenido; +5 por cada correo con PDF abierto y NO reportado (una vez por correo, aunque haya varios clics/aperturas). Se calcula del estado actual (`Repositorio.logros_rojo`), así que contener/reportar le quita esos puntos; al finalizar se congela. `marcador_partida` añade `puntos_rojo`, `rojo_enlaces_sin_contener` y `rojo_pdfs_sin_reportar`.

### Equipo en la auditoría (ajuste)
- `auditoria` gana `equipo` y `partida`. Las acciones del buzón quedan como `azul`; en la batalla IA vs IA, `motor.ejecutar_ronda(..., equipo="rojo")` propaga el equipo por `procesar_defensa` -> `ejecutar_herramienta` -> `consultar`, así que sus denegaciones quedan como `rojo` (JSONL incluido). La prueba manual queda con `equipo` NULL.
- `marcador_partida` añade `denegaciones_rojo` (filas DENEGADO de Rojo en la partida) y se difunde tras cada ronda de batalla.

### Cierre de partida con resultado (añadido)
- `POST /api/partida/finalizar` (solo token `general`) congela los puntajes del marcador y declara `ganador` (`rojo`|`azul`|`empate`) -> `{partida, puntos_rojo, puntos_azul, ganador, ts}`. 409 si ya estaba finalizada. Registra `PARTIDA_FINALIZADA` en auditoría (y en el JSONL, tipo `partida_finalizada`).
- SSE `partida_finalizada` `{..., marcador}`; a partir de ahí `marcador_partida` es el congelado, con `final:{...}` (antes `final:null`). La UI de General y Espectador muestra la pantalla de resultado (también al conectar tarde).
- Tras finalizar, `POST /api/correo`, `/api/correo/{id}/reportar`, `/api/correo/{id}/contener`, `/api/evento` y `/api/misiones/{id}/completar` -> 409, y `/l/{id}` -> 409 sin registrar el clic. Leer (buzón, misiones, marcador) sigue permitido. Una partida nueva = reiniciar el servidor.

### Sesiones y partida (Fase C)
Sesión por **participante** y partida con fases; lógica en `server/partida.py`.
- `POST /api/sesion` `{nombre, equipo:"rojo"|"azul"|"general"|"espectador", codigo?, usuario?}` -> `{token, participante:{id, nombre, equipo, rol, unido}, partida, usuario_azul}`. Nombre de 2-24 caracteres (letras, números, espacio, `. _ -`), único en la sala sin distinguir mayúsculas (409). `general` (rol `arbitro`) exige `codigo` = el código de árbitro que el servidor imprime al arrancar (o `CS_CODIGO_ARBITRO`); 403 si falla y 429 tras 5 fallos del mismo cliente (bloqueo 5 min). Varios participantes por equipo, cada uno con su token.
- `GET /api/sesion` (con token) -> `{participante, partida}`: reconexión; 403 si el servidor no reconoce el token (p. ej. tras reiniciar). Las sesiones viven mientras viva el proceso y sobreviven a «nueva partida».
- Una sesión de `espectador` solo puede hacer GET (403 en cualquier POST). Sin sesión, como antes, solo `GET /api/eventos` y `/api/estado`.
- `GET /api/partida` (con token) -> `{id, fase:"preparacion"|"en_curso"|"finalizada", duracion_s, restante_s, inicio, fin, motivo_fin:"arbitro"|"tiempo"|null, participantes:[...sin token]}`.
- `POST /api/partida/iniciar` (solo árbitro) `{duracion_min: 5|10|15}`: preparación -> en curso. 409 si ya empezó; 400 con otra duración.
- `POST /api/partida/finalizar` (solo árbitro): termina antes de tiempo; 409 si no está en curso. Al agotarse el tiempo la partida se cierra sola (`motivo_fin:"tiempo"`): lo hace una tarea del servidor y, además, se comprueba en cada petición, así que el resultado no depende de que el cliente esté conectado.
- `POST /api/partida/nueva` (solo árbitro, con la partida finalizada): partida nueva en preparación sin reiniciar el servidor; correos, misiones, riesgo y marcador empiezan de cero; las sesiones se conservan.
- Las acciones de Rojo/Azul (correo, reportar, contener, `/api/evento`, misión manual, clic en `/l/{id}`) solo valen **en curso**: en preparación -> 409 «La partida aún no ha empezado», tras finalizar -> 409.
- SSE `partida_estado` (= `GET /api/partida`): al conectar, en cada cambio (unirse, iniciar, finalizar, nueva) y cada 15 s en curso, para que los relojes de las vistas se resincronicen con el del servidor.
- Auditoría: `PARTICIPANTE_UNIDO`, `PARTIDA_INICIADA` (también en la tabla), `PARTIDA_FINALIZADA` (con `motivo`), `PARTIDA_NUEVA`.

### Aplicación de correo y visor seguro (Fase D)
Todo lo valida el servidor: sesión `azul`, partida **en curso** (409 si no) y correo del buzón del usuario azul en esta partida (404 si no). Cada acción aplica su regla de `sesion.REGLAS_EVENTO`, y cada regla trae `explicacion` (qué acción, qué control y cómo se evita).
- `GET /api/buzon` añade `enviados` (respuestas de Azul, carpeta «Enviados») y, por correo, `leido`, `leido_por` (participantes, en orden de lectura), `prioridad` (`alta|normal|baja`), `texto_enlace` (lo que el correo dice que enlaza), `archivado`, `aislado`, `respuestas` y `carpeta`: `archivados` > `sospechosos` (reportado) > `entrada`.
- `POST /api/correo/{id}/leer` -> `{leido, nuevo, regla}`: primera lectura de ESE participante -> `CORREO_ABIERTO`, regla `correo_abierto` (riesgo 0: **abrir no compromete nada**). Repetir no duplica el evento.
- `POST /api/correo/{id}/archivar` `{archivar: bool}` -> `{archivado, cambio, regla}` (`CORREO_ARCHIVADO`).
- `POST /api/correo/{id}/verificar` -> `{de, dominio, oficial, parecido, detalle, indicadores, regla}` (`REMITENTE_VERIFICADO`). El dominio se compara con el oficial `cybershield.invalid`; `parecido` se calcula normalizando homoglifos (I/1→l, 0→o, rn→m), no lo declara la plantilla.
- `POST /api/correo/{id}/inspeccionar` -> `{texto_mostrado, destino_real, coincide, explicacion, regla}` (`ENLACE_INSPECCIONADO`). **No cuenta como clic.**
- `POST /api/correo/{id}/responder` `{texto: 1..1000}` -> `{id, ts, a_phishing, regla}` (`RESPUESTA_ENVIADA`). La respuesta no sale del laboratorio: queda en la tabla `respuestas`. Contestar a un remitente que no es el oficial aplica `respuesta_a_phishing` (riesgo +10); si no, `respuesta_enviada` (0).
- `POST /api/correo/{id}/aislar` -> `{aislado, regla}` (`ARCHIVO_AISLADO`, regla −5). 409 si no hay adjunto o ya estaba aislado. Un adjunto aislado ya no se puede previsualizar y no da puntos a Rojo.
- `GET /api/correo/enviados` (solo `rojo`) -> `{enviados:[{id, para_usuario, asunto, plantilla_id, ts, con_adjunto, clicado, adjunto_abierto}]}`: lo que una campaña real podría medir. **No** expone si se leyó ni si se reportó.
- **Visor seguro** (`vista` de `pdf_abierto`): `{id, archivo, titulo, riesgo, tipo:"PDF (solo texto)", tamano_bytes, sha256, procedencia, indicadores, analisis, texto:[líneas]}`. El texto se extrae del flujo del propio PDF en el servidor; la UI lo pinta con `textContent` (nunca como HTML) y no descarga nada. `GET /pdf/{id}` se mantiene para quien quiera el archivo, con las mismas cabeceras.
- Tablas nuevas: `lecturas`, `archivados`, `respuestas` (CHECK 1..1000), `aislamientos`. SIEM (`data/eventos.jsonl`): `correo_recibido`, `correo_abierto`, `remitente_verificado`, `enlace_inspeccionado`, `correo_archivado`, `respuesta_enviada`, `archivo_aislado`.

### Misiones, incidentes y credenciales (Fase E)
Todo lo valida el servidor: sesión `azul` (salvo `GET /api/incidentes`, también `general`) y partida **en curso** en las escrituras (409 si no).
- **Misiones:** `misiones` gana `prioridad` (`alta|media|baja`), `plazo_s` (segundos desde el inicio de la partida o `null`), `depende_de` y `descripcion`; `progreso_mision` gana `completada_por`, `evidencia`, `puntos_obtenidos` y `a_tiempo` (migración con `ADD COLUMN`: el progreso anterior se conserva). Tabla `asignaciones_mision(partida, mision_id, participante, ts)`.
- `GET /api/misiones` -> `{usuario, misiones:[{id, titulo, condicion_evento, puntos, prioridad, plazo_s, depende_de:[ids], requiere:[títulos pendientes], descripcion, estado:"pendiente"|"bloqueada"|"vencida"|"completada", responsable, completada_por, evidencia, puntos_obtenidos, a_tiempo, ts}], transcurrido_s, puntos, riesgo_partida}`. `puntos` suma `puntos_obtenidos` (la mitad si se completó fuera de plazo).
- Una misión **bloqueada** no se completa con su evento; la regla devuelve `misiones_bloqueadas:[{id, titulo, requiere}]` junto a `misiones_completadas:[{id, titulo, puntos, a_tiempo}]`.
- `POST /api/misiones/{id}/asumir` -> `{asumida, mision_id, responsable}`; 404 si no existe, 409 si ya está completada. SSE `misiones_cambio`.
- `POST /api/misiones/{id}/completar` (manual) devuelve además `{puntos, a_tiempo}`; 409 si está bloqueada.
- **Credencial ficticia:** una por usuario semilla (su cuenta de correo); no se guarda ninguna contraseña. La plantilla `soporte_tecnico` tiene `pide_credenciales`: su página `/l/{id}` añade un formulario **sin campos** que hace `POST /l/{id}/credenciales` (CSP `form-action 'self'`). Exige partida en curso, clic previo (409) y enlace no contenido (sin efecto). Primera vez -> `CREDENCIAL_COMPROMETIDA` (nivel CRITICO), regla `credencial_comprometida` (+20) y SSE `credenciales_cambio`. Tabla `compromisos_credencial` (un único compromiso activo por usuario y partida).
- `GET /api/credenciales` -> `{usuario, cuenta, estado:"segura"|"comprometida"|"revocada", historial:[{id, correo_id, asunto, ts, revocada_ts, revocada_por}]}`.
- `POST /api/credenciales/revocar` -> `{revocada, regla}` (`CREDENCIAL_REVOCADA`, regla −15, completa «Revocar una credencial comprometida» si hay un incidente abierto). 409 si no hay nada que revocar.
- **Incidentes:** tabla `incidentes_partida` (CHECK de título 3-80, severidad, estado y resolución 10-500). `GET /api/incidentes` -> `{incidentes:[{id, titulo, severidad, estado, correo_id, abierto_por, ts_apertura, resolucion, resuelto_por, ts_resolucion, pendiente:[motivos]}]}`.
- `POST /api/incidentes` `{titulo, severidad:"baja"|"media"|"alta"|"critica", correo_id?}` -> `{incidente, regla}` (`INCIDENTE_ABIERTO`, regla `incidente_abierto`, 0). 404 si el correo no es del buzón.
- `POST /api/incidentes/{id}/estado` `{estado:"en_investigacion"|"resuelto", resolucion?}`: solo `abierto -> en_investigacion -> resuelto`. Resolver exige resolución de 10-500 caracteres y, si hay correo asociado, su enlace contenido (si se clicó) y la credencial que se comprometió por él revocada; si no, 409 con lo que falta. `INCIDENTE_ACTUALIZADO` / `INCIDENTE_RESUELTO` (regla −5). SSE `incidentes_cambio`.
- Puntaje de Rojo: `puntaje_rojo(enlaces_sin_contener, pdfs_sin_reportar, credenciales_sin_revocar)` = 10·enlaces + 5·PDF + 15·credenciales. Marcador: `rojo_credenciales_sin_revocar`, `credenciales_comprometidas`, `credenciales_revocadas`, `incidentes_abiertos`, `incidentes_resueltos`. `GET /api/correo/enviados` añade `credencial_obtenida`.
- SIEM: `credencial_comprometida`, `credencial_revocada`, `incidente_abierto`, `incidente_actualizado`, `incidente_resuelto`, `mision_asumida`.

### Batalla integrada en la partida (Fase F)
- `GET /api/ia/estado` (público, también sin sesión) -> `{partida, fase_partida, max_ataques, lanzados, restantes, identidad:{usuario, origen:"invitado"|"credencial_robada", rol}, defensor:{modelo, host, ok:true|false|null, ts, error}, atacante:{modelo, host}, en_curso, ataques:[…], puntos:{rojo, azul, lanzados, datos_expuestos, contenidos}, tecnicas:[…]}`. `defensor.ok` es el resultado de la última comprobación **real** (configurarlo o un ataque); `null` = nunca comprobado.
- `en_curso` -> `null` o `{id, n, usuario, origen_identidad, tecnica, intensidad, lanzado_por, fase:"validando"|"atacante"|"defensor", modelo, prompt (desde la fase defensor), transcurrido_ms}`. `transcurrido_ms` lo calcula el servidor al responder: la UI cuenta desde ahí, sin estimar progreso.
- `POST /api/ia/defensor` (solo `azul`) `{modelo, host?}`: comprueba contra esa Ollama que el modelo existe y lo fija como defensor (`DEFENSOR_IA_CONFIGURADO`). 409 con el motivo si no. Válido en cualquier fase.
- `POST /api/ia/ataque` (solo `rojo`) `{modelo, host?, tecnica?: una de atacante.CATEGORIAS | null, intensidad: 1-3}` -> `{ataque: en_curso}` enseguida; el resto llega por SSE. 409 si la partida no está en curso, si ya hay un ataque o una práctica en marcha, si el modelo del atacante no existe en su Ollama (no gasta ataque) o si ya se lanzaron los 8.
- Identidad: `Repositorio.identidad_atacante(partida)` = la cuenta de la credencial comprometida sin revocar más antigua, o `visita.demo` (invitado).
- Flujo: `atacante.generar_ataque` (técnica elegida) -> `motor.procesar_defensa` (filtro rápido, defensor, circuito de sesión, capas) -> `ataque_ia.clasificar` -> fila en `ataques_ia` -> regla de `REGLAS_EVENTO` (`ia_datos_expuestos` +20, `ia_enganada` +5, `ia_contenida` 0, `ia_fallo_seguro` 0) -> marcador. Cada inferencia tiene un tope de 300 s.
- Tabla `ataques_ia`: `n, lanzado_por, usuario, origen_identidad, tecnica, intensidad, estado ("en_curso"|"terminado"|"cancelado"), resultado ("datos_expuestos"|"ia_enganada"|"contenido"|"legitimo"|"fallo_seguro"|"error_atacante"|"cancelado"), veredicto, decision_ia, origen_decision ("ia"|"filtro_rapido"), capa_bloqueo, herramienta, objetivo, sensibilidad_objetivo, sensibilidad_expuesta, categoria, prompt, motivo, error, explicacion, puntos_rojo, puntos_azul, modelo_atq, modelo_def, atq_ms, atq_tokens_entrada, atq_tokens_salida, atq_carga_ms, def_ms, def_tokens_entrada, def_tokens_salida, def_carga_ms, ts_inicio, ts_fin`. Las respuestas de la API añaden `titulo`. No se guardan los datos devueltos, solo su sensibilidad.
- Métricas: `*_ms` = reloj de pared medido por el servidor (petición completa, con reintento JSON si lo hubo); `*_tokens_entrada` = `prompt_eval_count`, `*_tokens_salida` = `eval_count`, `*_carga_ms` = `load_duration`/10⁶, sumados si hubo reintento y `null` si Ollama no los envió. Con el filtro rápido, el defensor no tiene métricas: no hubo inferencia.
- Fallo seguro: un `ERROR` del defensor (sin configurar, HTTP de Ollama, timeout, JSON ilegible) -> `fallo_seguro`, sin herramienta ejecutada. Un fallo del atacante -> `error_atacante` (el ataque cuenta como gastado). Si la partida termina con un ataque a medias, queda `cancelado` (0 / 0).
- Marcador: `puntos_rojo` = buzón + IA y `puntos_azul` = misiones + IA, con el desglose `puntos_rojo_buzon`, `puntos_rojo_ia`, `puntos_azul_misiones` y `puntos_azul_ia`, además de `ataques_ia`, `ia_datos_expuestos` e `ia_contenidos`.
- SSE: `ia_estado` (al conectar, al lanzar y al terminar un ataque, al configurar el defensor, al comprometer o revocar una credencial, en una partida nueva) e `ia_ataque` (`{en_curso}` en cada cambio de fase; `{en_curso:null, terminado}` o `{en_curso:null, cancelado:n}` al acabar).
- Práctica durante la partida: `POST /api/simulacion/iniciar`, `/api/batalla/iniciar`, `/api/manual`, `/api/manual/real` y `/api/batalla/real/iniciar` -> 409 mientras la partida está **en curso**.
- SIEM: `ataque_ia_lanzado`, `ataque_ia_resultado` (equipo `rojo`), `defensor_ia_configurado` (equipo `azul`); las denegaciones de las capas durante un ataque quedan como `autorizacion_denegada` con equipo `rojo`.
- Cliente de Ollama: `generar` devuelve además `tokens_entrada` y `carga_ms` (`tokens` sigue siendo la salida).

### Aplicaciones por permiso (Fase B)
- `GET /api/apps?equipo=` (público) -> `{equipo, apps:[{id, titulo, icono, grupo, descripcion, permiso:"lectura"|"escritura"}], grupos:[{id, titulo}]}`. Con sesión, el equipo es el de la sesión y se ignora el parámetro. Sin sesión, vale el parámetro; si no se indica, `espectador`. El catálogo es `src/lab/apps.APPS`.
- `GET /api/archivos` (aplicación `archivos`: rojo, azul y general; si no, 403 «Tu equipo no tiene la aplicación…»):
  - Rojo -> `{vista:"rojo", catalogo:[{plantilla, nombre, adjunto}], enviados:[enviados_rojo con adjunto]}`, sin datos de reporte ni aislamiento;
  - Azul y General -> `{vista, usuario, adjuntos:[{id, de, asunto, ts, adjunto, pdf_abierto, pdf_reportado, aislado, carpeta}], puede_actuar}`.
  Las acciones siguen siendo las rutas de siempre (`/api/evento`, `/api/correo/{id}/aislar`), solo para Azul.
- `GET /api/seguridad` (aplicación `seguridad`: azul y general) -> `{usuario, fase, riesgo, credencial, defensor:{modelo, host, ok, ts, error}, controles:{correos, reportados, enlaces_clicados, enlaces_contenidos, adjuntos_abiertos, adjuntos_reportados, adjuntos_aislados, incidentes_abiertos, incidentes_resueltos, ataques_ia_contenidos, ataques_ia_datos_expuestos}, recomendaciones:[{nivel, texto, accion}], puede_actuar}`. Las recomendaciones salen de `apps.recomendaciones`, de lo más grave a lo menos. Revocar sigue siendo `POST /api/credenciales/revocar` (solo Azul).
- `GET /api/recursos` (público) -> `{roles, recursos:[{tabla, herramienta, descripcion, sensibilidad, acceso:{rol: "sí"|"con autorización"|"no"}}], nota}`, calculado con `permisos.evaluar_acceso`.
- `GET /api/ayuda?equipo=` (público, equipo como en `/api/apps`) -> `{equipo, pasos, apps, reglas:[{evento, riesgo, completa_mision, explicacion}], puntos_rojo, puntos_azul, max_ataques_ia}`.
- Rutas anteriores: `GET /api/incidentes` (azul y general), `GET /api/misiones` (azul), `GET /api/buzon` (azul) y `GET /api/correo/enviados` (rojo) ya coincidían con el catálogo. `server/test_apps.py` lo comprueba para cada equipo y sin sesión.
- Notificaciones: no tienen ruta propia. La UI las deriva de los eventos SSE (`auditoria`, `ia_ataque`, `credenciales_cambio`, `partida_estado`) según la vista.

### Cronología, resultados y persistencia (Fase G)
Las tres rutas son de lectura y públicas (también para el espectador sin sesión).
- `GET /api/partidas` -> `{actual: Partida.publico(), finalizadas:[{partida, ts, motivo, ganador, puntos_rojo, puntos_azul, inicio, duracion_s}]}`.
- `GET /api/cronologia?partida=&categoria=a,b&equipo=rojo|azul|sistema&nivel=BAJO|MEDIO|ALTO|CRITICO&q=` -> `{partida, fase, inicio, restringida, total, coinciden, entradas:[{id, ts, t_s, categoria, equipo, accion, nivel, texto}] (las 500 últimas que coinciden), conteo:{categoría: n}, categorias, niveles}`. Por defecto, la partida actual. Las entradas salen de la tabla `auditoria` de esa partida (`informe.entrada`). `t_s` = segundos desde el inicio; es negativo en la preparación y `null` si la partida no ha empezado. Categorías: `partida correo enlace documento credencial incidente mision batalla_ia acceso practica`. Un filtro inválido -> 400 y una partida inexistente -> 404.
- Visibilidad: con sesión `rojo` y la partida sin finalizar solo se devuelven las acciones de `informe.VISIBLE_ROJO` y los accesos de su equipo (`restringida: true`). El resto de vistas, y todas al finalizar, reciben todo.
- `GET /api/resultados?partida=` -> `{partida, fase, inicio, duracion_s, usuario_azul, rojo:{total, lineas:[{concepto, cantidad, unitario, subtotal, formula, explicacion}]}, azul:{…}, formula_ganador, riesgo:{final, reglas:[{evento, veces, riesgo_unitario, subtotal}], suma_sin_acotar, explicacion}, batalla_ia:{lanzados, por_resultado, atacante_ms, defensor_ms:{n, media, min, max, total}, tokens:{atacante_entrada, atacante_salida, defensor_entrada, defensor_salida}, carga_ms, nota}, guardado, final}`. Con la partida finalizada sale lo guardado (`guardado: true`, `final` con el ganador y `marcador` congelado). Si no, se calcula en vivo (`final: null`) y las sesiones `rojo`/`azul` reciben 403 hasta que finalice. `rojo.total`/`azul.total` = `puntos_rojo`/`puntos_azul` del marcador.
- Tabla `resultados_partida(partida PK, ts, motivo, ganador, puntos_rojo, puntos_azul, inicio, duracion_s, informe JSON)`: se escribe una vez, al cerrar la partida (por el árbitro o por tiempo).
- Tabla `rondas_practica`: `partida, fase_partida, modo ("batalla"|"manual"), ronda, usuario, rol, categoria, prompt, decision_ia, decision, veredicto (también ERROR), capa_bloqueo, origen_decision, nivel_fuga, error, modelo_atq, modelo_def` y las métricas `atq_*`/`def_*` como en `ataques_ia`. Cada ronda deja además una fila `RONDA_PRACTICA` en la auditoría y una línea `ronda_practica` en el JSONL.
