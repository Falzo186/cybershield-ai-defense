# Diagnóstico técnico — CyberShield AI Defense (26/10/2026)

Auditoría sobre `main` en `dcfecdb` (51 commits, árbol limpio, sin stash; ramas locales `main` y `feature/pulido-visual`,
ya fusionada). Todo lo que sigue se ha **ejecutado o inspeccionado** en esta auditoría; lo que no se comprobó se indica.

## 1. Arquitectura real

| Capa | Archivos | Notas |
|---|---|---|
| Interfaz | `ui/index.html`, `app.js` (estado y eventos), `render.js` (solo pinta, sin `innerHTML`), `escritorio.js` (ventanas), `api.js` (REST + SSE) | HTML/CSS/JS sin frameworks ni build. |
| Servidor | `server/app.py` (FastAPI, ~1 000 líneas) sobre `server/mock_server.py` (SSE, estado global, simulación) | Un solo proceso; estado de partida en memoria. Escucha en `0.0.0.0`. |
| Motor IA | `src/lab/motor.py`, `atacante.py`, `defensor.py`, `cliente_ollama.py`, `filtro_rapido.py`, `sesion.py` | Ollama vía `urllib` (`/api/chat`, `think:false`). |
| Capas de acceso | `herramientas.py` (catálogo + validación), `permisos.py` (rol × sensibilidad), `repositorio.py` (único acceso a la BD, SQL fijo y parametrizado) | La IA solo **propone**; las capas deciden. |
| Datos | SQLite `data/lab.db` (`schema.py`, `seed.py`); 13 tablas: `usuarios productos clientes incidentes configuracion_admin autorizaciones auditoria correos enlaces misiones progreso_mision contenciones reportes` | Auditoría *append-only* por triggers. Se mantiene SQLite (decisión previa; el prompt menciona PostgreSQL, pero no hay motivo técnico para migrar). |
| Reglas | `sesion.REGLAS_EVENTO`, `sesion.PUNTOS_ROJO`, `seed.MISIONES` | Deterministas, sin aprendizaje. |
| Eventos SIEM | `data/eventos.jsonl` desde `Repositorio.registrar` | Formato listo para Wazuh; **Wazuh no está integrado**. |
| Pruebas | 9 suites `src/lab/test_*.py`, `server/test_app.py`, `e2e/demo_partida.py` (Playwright), `e2e/capturas_vistas.py` | Ver §3. |

Rutas: `/api/ollama/{estado,modelos,probar}`, `/api/usuarios`, `/api/equipo/reclamar`, `/api/correo{,/plantillas,/{id}/reportar,/{id}/contener}`,
`/api/buzon`, `/api/evento`, `/pdf/{id}`, `/l/{id}`, `/api/misiones{,/{id}/completar}`, `/api/partida/finalizar`,
`/api/batalla/{real/iniciar,responder}`, `/api/manual{,/real}`, `/api/simulacion/iniciar`, `/api/detener`, `/api/estado`, `/api/metricas`, `/api/eventos` (SSE).

## 2. Commits citados

- `41c9d1f` (22/10) «reglas deterministas evento → consecuencia y reporte de correos»: **existe**. Su código sigue vigente y ampliado
  (`REGLAS_EVENTO` tiene hoy 5 reglas: `CLIC_ENLACE +15`, `correo_reportado −10`, `enlace_contenido −15`, `pdf_abierto 0`, `pdf_reportado −10`).
- `37c0d33` (22/10) «misiones individuales del Equipo Azul»: **existe**. Ojo: ahí «Contener un enlace clicado» se completaba con
  `CLIC_ENLACE`; lo corrigió `4f35ca7`, y hoy exige `enlace_contenido`, que `contener_enlace` solo acepta si hubo un clic
  previo (`sin_clic` → 409). El progreso es por partida desde `c5648a0`.

## 3. Pruebas ejecutadas (resultados reales)

| Suite | Resultado |
|---|---|
| `test_lab` · `test_motor` · `test_correos` · `test_reglas` · `test_misiones` | 20/20 · 41/41 · 16/16 · 25/25 · 17/17 |
| `test_documentos` · `test_eventos` · `test_puntaje` · `test_cliente` | 12/12 · 13/13 · 9/9 · 6/6 |
| `server/test_app.py` (servidor completo, BD en memoria) | 88/88 |
| `e2e/demo_partida.py` (4 navegadores, partida Rojo/Azul completa) | 38/38 |
| `test_cliente --real qwen3:4b` (Ollama 0.40.0 local) | 3/3 respuestas válidas del defensor (10,9-28,6 s) |
| Batalla IA vs IA real por el servidor (`llama3.2:3b` ataca, `qwen3:4b` defiende, 2 rondas) | 2/2 rondas sin error, inferencias reales (atacante 10,8-24,5 s; defensor 14,2-16,2 s); gana el defensor 2-0 |

**`qwen3:4b` y las respuestas vacías: resuelto y verificado.** Causa: Ollama 0.40 devuelve el razonamiento en `message.thinking`
(no en `<think>` dentro de `content`); ese razonamiento agotaba `num_predict` (`done_reason=length`) y `content` llegaba vacío.
`cliente_ollama.generar` envía `think: false` (commit `de8133e`); una respuesta vacía sigue siendo un **error explícito**, no un bloqueo.

## 4. Estado por funcionalidad

**Terminadas y verificadas:** capas deterministas de acceso a la BD; batalla IA vs IA real; prueba manual REAL; tokens de equipo
verificados en el servidor; espectador de solo lectura (403 en el servidor); buzón con plantillas fijas y enlaces locales; reportar,
contener (exige clic previo), abrir y reportar PDF; misiones por partida; reglas → riesgo; puntaje de Rojo; cierre de partida con
resultado congelado y 409 posterior; marcador en vivo por SSE; auditoría *append-only* + `eventos.jsonl`; escritorio con ventanas
(arrastrar, redimensionar, minimizar, maximizar, organizar, persistencia por vista).

**Parciales:**
- **Identidad:** un token por **equipo**, no por persona. No hay nombre visible ni varios participantes por equipo, y Azul
  juega con un solo usuario semilla. Una pestaña que pierde su token no lo recupera sin reiniciar la partida. El primero que
  entra como `general` es el árbitro.
- **Partida:** dura lo que el proceso del servidor; no hay preparación, inicio ni duración de 5/10/15 min, ni temporizador.
  La batalla IA vs IA y la partida del buzón son mundos separados, con marcadores distintos.
- **Correo:** solo bandeja de entrada. Faltan enviados, archivados y sospechosos; estado de lectura, prioridad y respuesta;
  y los eventos «correo abierto», «remitente verificado», «enlace inspeccionado» y «respuesta enviada».
- **Documentos:** el PDF se **descarga** al sistema del usuario. No hay visor dentro de la aplicación, ni atributos
  (procedencia, riesgo, indicadores), ni la acción de aislar.
- **Misiones:** 4 misiones fijas de un solo responsable. No tienen prioridad, fecha límite, evidencia, dependencias ni
  objetivos colectivos.
- **Incidentes:** la tabla `incidentes` es solo un dato que la batalla intenta robar. No hay gestión de incidentes
  (abrir, investigar, cerrar).
- **Escenario de compromiso:** no hay credenciales sintéticas que se comprometan ni que se puedan revocar. Tampoco hay
  departamentos ni cuentas con permisos revisables.
- **Metadatos de inferencia:** se guardan modelo, `tiempo_ms`, tokens **de salida** (`eval_count`) e intentos. Faltan los
  tokens de entrada (`prompt_eval_count`). Las rondas de batalla no se guardan: solo viajan por SSE.
- **Resultados de la batalla:** el informe se exporta desde el navegador, pero no se guarda en el servidor.

**Simuladas (MOCK, etiquetadas en la UI 🟡):** modo *Simulación* (6 escenarios fijos de `mock_server.ESCENARIOS`), *Prueba manual MOCK*
(clasificador por palabras clave) y `/api/batalla/iniciar` (batalla mock: **ya no la usa la UI**, código muerto).
Deterministas por diseño (no son IA): filtro rápido por regex, circuito de sesión, reglas de eventos y puntajes.

## 5. Errores reproducibles

1. **Latencia inflada con `localhost` (Windows):** cada llamada a Ollama con `http://localhost:11434` tarda unos **2 s
   más**: `generar` mide 2 350-2 390 ms frente a 336-367 ms con `127.0.0.1`, con el mismo modelo y la misma petición, medido
   alternando los hosts. Esos 2 s se suman al `tiempo_ms` que la UI muestra como latencia del modelo, que **por tanto no es
   honesto**, y hacen que comprobar Ollama tarde unos 4 s. Es el host por defecto. → Fase A.
2. **Batalla sin trazabilidad persistente:** una batalla real dejó 14 líneas de auditoría por SSE y **0** en `eventos.jsonl` y en
   la tabla (las decisiones de la IA y los veredictos no se registran). → Fase G.
3. **Token perdido = equipo inaccesible** hasta reiniciar el servidor (§4). → Fase C.
4. **Ataque vacío enviado como ataque:** `llama3.2:3b` devolvió `{"prompt":""}` en 1 de 6 llamadas reales y el atacante mandaba ese
   JSON literal al defensor como si fuera el texto del ataque. → Fase A.
5. **HTTP 500 intermitente de Ollama** (visto 1 vez en ~20 llamadas, no reproducible en 6 reintentos; el registro de Ollama lo
   muestra a mitad de una generación): el cliente lo informaba solo como «Internal Server Error», sin el mensaje de Ollama. → Fase A.

## 6. Riesgos técnicos y deuda

- **Seguridad:** el servidor escucha en `0.0.0.0` sin autenticación de personas; los tokens de equipo evitan suplantar
  vistas, pero cualquiera en la LAN puede tomar un equipo libre o el árbitro. Mitigado:
  - no hay CORS y la cabecera del token obliga a una petición preflight;
  - todo el texto se pinta con `textContent`;
  - el SQL es fijo;
  - los destinos de Ollama se limitan a IP privadas;
  - los PDF salen de un catálogo fijo y se sirven con `nosniff` y `sandbox`.
  
  Pendiente: límites de frecuencia (*rate limiting*) y caducidad de tokens.
- **Estado en memoria:** la partida, los tokens y `ESTADO_PARTIDA` se pierden al reiniciar, y hay un solo proceso: no hay
  partidas concurrentes.
- **El estado de la batalla vive en el cliente** (contadores e historial) y el SSE no reenvía lo anterior: quien se conecta
  a mitad de una batalla no ve las rondas previas.
- **Deuda:**
  - `server/app.py` es monolítico (~1 000 líneas), mezcla buzón, batalla y partida, y depende del estado global de
    `mock_server`;
  - `/api/batalla/iniciar` (mock) está muerto;
  - conviven dos marcadores (batalla y partida);
  - las capturas de la E2E se reescriben en cada pasada.
- **Modelos pequeños en CPU:** cada llamada tarda 10-30 s, así que una partida de 5 min admite solo unas 5-8 rondas de IA.
  Esto condiciona la Fase F.

## 7. Reutilizable vs. a refactorizar

**Reutilizable tal cual:**
- las capas de acceso (`herramientas`, `permisos`, `repositorio`);
- `motor.py`, `cliente_ollama.py`, el filtro rápido y las reglas;
- el SSE y la auditoría con JSONL;
- el escritorio y su gestor de ventanas;
- las pruebas.

**A refactorizar:**
- la **identidad**: pasar de token por equipo a sesión por participante (nombre, equipo, rol);
- la **partida**: un objeto en el servidor con fases y temporizador autoritativo, que una el buzón y la batalla;
- dividir `server/app.py` en módulos (partida, buzón, batalla);
- **persistir** las rondas de batalla y las inferencias.

## 8. Plan, esfuerzo y orden recomendado

Estimación en días de trabajo efectivo de una IA desarrolladora **con verificación** (pruebas y revisión incluidas):

| Fase | Contenido | Esfuerzo | Depende de |
|---|---|---|---|
| A | Estabilidad: latencia `localhost`, verificación Ollama, este diagnóstico | 0,5 d | — |
| **C** | Sesión por participante (nombre, equipo, rol), lobby, partida con fases y temporizador de 5/10/15 min autoritativo en el servidor | 3 d | A |
| D | Correo completo (carpetas, lectura, prioridad, respuesta, eventos nuevos) y visor de documentos dentro de la app (sin descarga), con atributos y aislar | 3 d | C |
| E | Misiones con responsable, prioridad, plazo, evidencia y dependencias; incidentes; credenciales sintéticas comprometidas/revocables | 3 d | C, D |
| F | Batalla integrada en la partida (Rojo decide cuándo atacar, defensor siempre activo), tokens de entrada/salida reales, estados de inferencia honestos, fallo seguro | 3 d | C, E |
| G | Persistencia de rondas e inferencias, cronología filtrable, panel de resultados con fórmulas documentadas | 2 d | F |
| B | Aplicaciones del escritorio por permiso (Correo, IA, Misiones, Archivos, Seguridad, Incidentes, Recursos, Auditoría, Resultados, Ayuda) y notificaciones | 2-3 d, repartidos | C-G |
| H | Pruebas integrales, regresiones, adaptador Wazuh documentado | 2 d | todo |

**Cambio de orden justificado:** B (escritorio) va **después de C** y se completa a lo largo de D-G. El escritorio ya existe,
con ventanas, minimizar y maximizar; sus nuevas aplicaciones dependen de modelos de datos que aún no existen (sesión,
carpetas de correo, incidentes). Hacerlas antes produciría ventanas vacías: justo «una interfaz convincente que no
funciona». Total: unas **3-4 semanas** de trabajo efectivo.

**Avance global estimado frente a la visión: ~35 %**, ponderado por importancia:
- núcleo IA y capas de acceso (peso 25, ~80 % hecho);
- buzón, reglas y misiones (20, ~45 %);
- identidad y partida (20, ~15 %);
- escritorio y UX (10, ~60 %);
- auditoría y resultados (15, ~35 %);
- Wazuh (5, ~10 %);
- incidentes y escenario de compromiso (5, ~0 %).

## 9. Decisión que necesita aprobación (antes de la Fase C)

La Fase C cambia el **modelo de identidad**, que hoy es un token por equipo y que usan la UI, la E2E y 88 pruebas del
servidor. Propuesta:
- **Sesión por participante:** `POST /api/sesion {nombre, equipo}` devuelve un token propio. El servidor guarda nombre,
  equipo y rol; los nombres son únicos por partida y se reconecta con el mismo token.
- **Un árbitro protegido:** la vista `general` exige un **código de árbitro** que el servidor imprime en la consola al
  arrancar, para que no la tome el primero que llegue.
- **Partida explícita:** fases `preparación → en curso → finalizada`, con duración de 5/10/15 min elegida por el árbitro y
  temporizador en el servidor. La partida termina sola al agotarse el tiempo. Para una partida nueva no hace falta
  reiniciar el proceso.
- **Compatibilidad:** se mantiene `?rol=` como atajo y se adaptan las pruebas existentes, sin borrarlas.

## 10. Informe de la Fase A — estabilidad (rama `feature/fase-a-estabilidad`)

- **Objetivo:** corregir errores reproducibles y verificar Ollama antes de cambiar la arquitectura.
- **Archivos:** `src/lab/cliente_ollama.py`, `src/lab/atacante.py`, `src/lab/test_cliente.py`, `docs/DIAGNOSTICO.md`.
- **Cambios:**
  - `localhost` → `127.0.0.1` al conectar con Ollama, con reintento por el host original si 127.0.0.1 rechaza la conexión
    (instalaciones que solo escuchan en IPv6);
  - un ataque con `prompt` vacío es un error explícito, ya no se envía al defensor;
  - los HTTP 4xx/5xx muestran el mensaje de Ollama.
- **Pruebas (resultados reales):**
  - `test_cliente` 14/14: 8 comprobaciones nuevas para la conexión, el reintento, el 500 y el prompt vacío;
  - el resto de la batería, sin cambios: 20, 41, 16, 25, 17, 12, 13, 9 y 88/88, y la E2E 38/38.
- **Medido tras el arreglo:**
  - `generar` con `localhost`: 318-423 ms, antes 2 350-2 390 ms; `ollama_disponible`: 0,07 s, antes 2,10 s;
  - batalla real de 3 rondas (`llama3.2:3b` contra `qwen3:4b`): 3/3 sin error en 69 s, con el atacante a 6,5-8,4 s
    por llamada; antes, 2 rondas tardaban 87 s.
- **Pendiente** (de otras fases): persistencia de la batalla (G), tokens de entrada (F), identidad y partida (C).
- **Riesgo de regresión:** bajo. Solo cambia cómo se abre la conexión; los demás hosts no se tocan y el reintento cubre IPv6.
- **Criterios de aceptación cumplidos en A:** 3 (los modelos se consultan de verdad), 4 (errores honestos), 13 (las pruebas
  pasan), y 15 parcial (la batalla real no depende de respuestas prefabricadas).

## 11. Informe de la Fase C — participantes y partida (rama `feature/fase-c-identidad`)

- **Objetivo:** identidad por participante, árbitro protegido y partida con fases y temporizador autoritativo, sin
  reescribir lo existente.
- **Estado inicial:** un token por equipo (de 1 persona); la partida era el proceso del servidor; no había duración.
- **Archivos:**
  - `server/partida.py` (nuevo: `Sala`, `Participante`, `Partida`, lógica pura con reloj inyectable);
  - `server/app.py` (middleware de sesión, `/api/sesion`, `/api/partida{,/iniciar,/finalizar,/nueva}`, tarea del temporizador);
  - `server/test_partida.py` (nuevo) y `server/test_app.py`;
  - `ui/index.html`, `app.js`, `render.js`, `api.js`, `escritorio.js`, `styles.css`;
  - `e2e/demo_partida.py`, `e2e/capturas_vistas.py`;
  - `docs/CONTRATO_API.md`, `README.md`, `docs/GUION_DEMO.md`.
- **Cambios:**
  - **Sesiones por participante:** cada participante se une con su nombre visible (único) y su equipo, y recibe su propio
    token; puede haber varios por equipo.
  - **Árbitro protegido:** la vista General exige el código impreso al arrancar, con bloqueo de 5 min tras 5 fallos
    del mismo cliente.
  - **Espectadores:** una sesión de espectador nunca escribe.
  - **Reconexión:** con el token guardado en el navegador, sin volver a unirse.
  - **Partida:** *preparación → en curso → finalizada*, de 5, 10 o 15 min. El tiempo lo cuenta el servidor con un reloj
    monótono y la partida se cierra sola (tarea en segundo plano, más una comprobación en cada petición). Las acciones
    solo valen en curso. Hay **nueva partida** sin reiniciar el servidor.
  - **UI:** diálogo para unirse con errores comprensibles; fase y cuenta atrás en la cabecera, resincronizada por SSE
    cada 15 s; controles del árbitro según la fase.
- **Pruebas (resultados reales):**
  - `test_partida` 29/29 (nuevo);
  - `test_app` 112/112: antes 88; se adaptaron las comprobaciones de `reclamar` al nuevo modelo, sin borrar ninguna, y
    se añadieron sesiones, árbitro, preparación, inicio, fin por tiempo y nueva partida;
  - `e2e/demo_partida.py` 42/42: antes 38; añade la preparación, el 409 previo al inicio y la cuenta atrás igual en las
    4 vistas, que mostraron `05:00` las cuatro;
  - comprobación en navegador real, 18/18: código erróneo, nombre repetido, reconexión al recargar, reloj que no se
    reinicia al recargar, espectador con cuenta atrás y nueva partida en todas las vistas;
  - el resto de la batería, sin cambios.
- **Cambio de contrato:** `POST /api/equipo/reclamar` desaparece, sustituido por `POST /api/sesion`. La sesión se guarda
  en `localStorage` (`cs_sesion_<rol>`) en vez de en `sessionStorage`.
- **Pendiente** (otras fases):
  - la batalla IA vs IA aún no depende de la fase de la partida → F;
  - las misiones siguen siendo del equipo azul, no de cada participante → E;
  - las sesiones viven en memoria y se pierden al reiniciar el servidor;
  - el espectador anónimo no aparece en la lista de participantes.
- **Riesgos de regresión:** medios. Cambió el modelo de identidad, pero lo cubren las 3 suites de servidor y E2E.
  Las posiciones de ventanas guardadas no se ven afectadas.
- **Criterios de aceptación cumplidos en C:**
  - **1 y 2:** cada participante entra en su escritorio, y los permisos se comprueban en el servidor por sesión;
  - **10:** las sesiones de espectador dan 403 en cualquier escritura;
  - **11:** el temporizador y el resultado los da el servidor, y las 4 vistas mostraron el mismo reloj;
  - **13:** todas las pruebas pasan.
- **Avance global estimado: ~43 %.** El bloque identidad y partida (peso 20) pasa de ~15 % a ~55 %.

## 12. Informe de la Fase D — correo y documentos (rama `feature/fase-d-correo`)

- **Objetivo:** que el buzón sea una aplicación de correo creíble y que los PDF se vean en un visor seguro, con
  consecuencias que salgan de acciones concretas y se expliquen.
- **Estado inicial:** lista única de correos con «Reportar» y «Contener»; «Abrir PDF» descargaba el archivo; no había
  lectura, carpetas, verificación de remitente, inspección de enlaces, respuestas ni aislamiento.
- **Archivos:**
  - `src/lab/correos.py` (dominio oficial, prioridad, texto visible del enlace, indicadores, `verificar_remitente`);
  - `src/lab/documentos.py` (extracción de texto del PDF y `vista_previa` con SHA-256 y análisis);
  - `src/lab/schema.py` (tablas `lecturas`, `archivados`, `respuestas`, `aislamientos`);
  - `src/lab/sesion.py` (reglas nuevas, todas con `explicacion`), `src/lab/repositorio.py` (acciones y eventos SIEM);
  - `server/app.py` (`/api/correo/{id}/leer|archivar|verificar|inspeccionar|responder|aislar`, `/api/correo/enviados`);
  - `ui/index.html`, `render.js`, `app.js`, `api.js`, `styles.css`;
  - pruebas: `src/lab/test_correo_app.py` (nuevo), `test_eventos.py`, `server/test_app.py`, `e2e/demo_partida.py`;
  - `docs/CONTRATO_API.md`, `README.md`, `docs/GUION_DEMO.md`.
- **Cambios:**
  - **Carpetas** Entrada / Sospechosos / Archivados / Enviados, calculadas en el servidor; no leídos en negrita y
    prioridad visible; contador del botón = no leídos de la entrada.
  - **Lectura por participante:** abrir un correo lo marca como leído por esa persona (`CORREO_ABIERTO`, riesgo 0).
  - **Verificar remitente:** dominio comparado con `cybershield.invalid`, detectando homoglifos (`cybershieId`).
  - **Inspeccionar enlace:** texto visible frente a destino real; no cuenta como clic.
  - **Responder:** queda en la partida, no sale; responder a un remitente no oficial es `respuesta_a_phishing` (+10).
  - **Aislar adjunto** (−5): impide previsualizarlo y anula los puntos de Rojo por él.
  - **Visor seguro:** texto extraído del propio PDF en el servidor, tamaño, SHA-256, procedencia, indicadores y análisis;
    se pinta con `textContent`, se cierra con Esc y **ya no se descarga nada**.
  - **Rojo:** «Enviados · seguimiento» con clic y adjunto abierto (por SSE), sin saber si se leyó o reportó.
  - Avisos: cuando una acción sube el riesgo, el aviso incluye la explicación de la regla.
- **Pruebas (resultados reales, batería completa en verde):**
  - `test_correo_app` 39/39 (nuevo); `test_eventos` 13/13 (añade `correo_recibido`);
  - `server/test_app.py` 133/133: antes 112; la comprobación del PDF pasa de `descarga` a `vista`;
  - `e2e/demo_partida.py` 52/52 en Chromium real (Playwright): antes 42; añade verificar, inspeccionar sin clic, visor
    con texto y SHA-256 reales, Esc, ninguna descarga, carpeta Sospechosos, aislar y seguimiento de Rojo;
  - `e2e/capturas_vistas.py`: sin scroll interno a 1920×1080. **Corrección (Fase E):** a 1366×768 sí hay scroll
    interno en General (panel de control, +16 px) y Azul (control +33 px, defensor +27 px); al redactar este
    informe solo se leyeron las últimas líneas de la salida. Comprobado que también ocurre en `main`;
  - el resto de suites, sin cambios. No se hizo una prueba manual aparte de las automatizadas en navegador.
- **Cambio de contrato:** `POST /api/evento` con `pdf_abierto` devuelve `vista` en lugar de `descarga`.
- **Decisión para revisar:** previsualizar el PDF sigue dando **+5 a Rojo** mientras no se reporte ni aísle (la regla
  que se pidió antes). Choca con «abrir no equivale a comprometer»: si se prefiere, puede pasar a 0 y dejar los +5
  para una acción explícita (p. ej. «habilitar contenido»).
- **Pendiente:** misiones por participante y de las nuevas acciones (verificar, inspeccionar, aislar) → E; las
  respuestas no tienen límite de cantidad por correo; el servidor ya en marcha (pestaña c2) debe reiniciarse para
  cargar el esquema nuevo.
- **Riesgos de regresión:** bajos-medios. El esquema solo añade tablas; el cambio visible es el visor en vez de la
  descarga.
- **Avance estimado:** ~52 % del plan (A, C y D hechas; B parcial; E, F, G y H pendientes).

## 13. Informe de la Fase E — misiones, incidentes y credenciales (rama `feature/fase-e-misiones`)

- **Objetivo:** misiones con responsable, prioridad, plazo, evidencia y dependencias; incidentes; credenciales
  ficticias que se comprometen y se revocan, con consecuencias explicadas.
- **Estado inicial:** 4 misiones fijas sin prioridad, plazo, dependencias ni autor; no había incidentes de partida
  ni credenciales; el puntaje de Rojo solo contaba enlaces y PDF.
- **Archivos:**
  - `src/lab/seed.py` (8 misiones), `schema.py` (columnas nuevas con migración; tablas `asignaciones_mision`,
    `incidentes_partida`, `compromisos_credencial`), `sesion.py` (reglas nuevas, `puntos_mision`, puntaje con
    credenciales), `repositorio.py`, `correos.py` (`pide_credenciales`);
  - `server/partida.py` (`transcurrido_s`), `server/app.py` (endpoints de misiones, incidentes y credenciales;
    página falsa de inicio de sesión);
  - `ui/index.html`, `render.js`, `app.js`, `api.js`, `styles.css` (pestaña Incidentes, misiones ampliadas);
  - pruebas: `src/lab/test_incidentes.py` (nuevo), `test_misiones.py`, `test_puntaje.py`, `server/test_app.py`,
    `server/test_partida.py`, `e2e/demo_partida.py`;
  - `docs/CONTRATO_API.md`, `README.md`, `docs/GUION_DEMO.md`.
- **Cambios:**
  - **Misiones:** prioridad, plazo desde el inicio (fuera de plazo vale la mitad), dependencias (*bloqueada* hasta
    cumplirlas, y el aviso dice cuál falta), responsable que cualquiera del equipo puede asumir, y autor, hora y
    evidencia al completarse. Hay 4 misiones nuevas: verificar remitente, abrir incidente, revocar credencial y
    resolver incidente.
  - **Credencial ficticia:** la página del enlace de soporte imita un inicio de sesión **sin campos de texto**; el
    botón simula entregar la contraseña. Riesgo +20 y Rojo +15 hasta que Azul revoque; contener el enlace no la
    revoca, y el aviso lo explica.
  - **Incidentes:** abrir (también desde el correo, con el correo ya elegido) → investigar → resolver. Resolver exige
    explicar qué se hizo y que la amenaza del correo esté contenida; si no, el servidor dice qué falta.
  - **Marcador:** credenciales sin revocar en Rojo, credenciales comprometidas e incidentes abiertos.
- **Pruebas (resultados reales, batería completa en verde):**
  - `test_incidentes` 42/42 (nuevo); `test_misiones` 17/17 y `test_puntaje` 9/9 (adaptados a 8 misiones y al
    puntaje con credenciales, sin quitar comprobaciones);
  - `server/test_app.py` 157/157 (antes 133): página sin campos y su CSP, compromiso, permisos, incidente con
    autor y evidencia, bloqueo y desbloqueo, resolución rechazada con motivo, revocación y resolución;
  - `server/test_partida.py` 30/30 (antes 29);
  - `e2e/demo_partida.py` 69/69 en Chromium real (antes 52), 4 pasadas seguidas en verde: pasos 3g-3h de credencial
    robada, incidente, revocar, resolución rechazada, contener y resolver; resultado **Rojo 0 — Azul 85**. El 409 de
    la resolución rechazada se marca como provocado a propósito. Una pasada intermedia falló de forma intermitente y
    destapó un fallo real de la UI: al redibujarse la lista de incidentes se perdía el texto de resolución que se
    estaba escribiendo. Ahora se guarda un borrador por incidente y la E2E lo comprueba;
  - migración probada sobre una **copia** de `data/lab.db`: el progreso anterior se conserva y suma sus puntos.
- **Decisiones tomadas (reversibles; revísalas):**
  - el plazo cuenta desde el inicio de la partida, no desde el evento que lo origina;
  - fuera de plazo una misión vale la mitad, en vez de perderse;
  - si se revoca **antes** de abrir el incidente, la misión de revocar no se completa (la dependencia es estricta).
    Enseña el procedimiento, pero puede parecer dura;
  - sigue pendiente la decisión de la Fase D: previsualizar un PDF da +5 a Rojo.
- **Vistas:** `capturas_vistas.py` da el mismo resultado que `main`: sin scroll interno a 1920×1080; a 1366×768,
  scroll interno en General (+16 px) y Azul (+27/+33 px), que ya existía (ver la corrección del §12). El marcador
  solo añade «cred.» e «Incidentes» cuando hay alguno, para no alargarlo.
- **Pendiente:** el scroll interno a 1366×768 de General y Azul (heredado); incidentes sin correo no comprueban nada al resolverse; las misiones siguen siendo del usuario azul
  compartido (el responsable y el autor son por participante, el progreso es del equipo); General aún no tiene una
  vista propia de incidentes (solo el contador del marcador y la API) → B/G.
- **Riesgos de regresión:** medios. Cambian los puntos de Azul (más misiones) y la forma de `misiones()`; lo cubren
  todas las suites. El servidor en marcha debe reiniciarse para migrar la BD.
- **Avance estimado:** ~60 % del plan (A, C, D y E hechas; B parcial; F, G y H pendientes).

## 14. Informe de la Fase F — batalla integrada en la partida (rama `feature/fase-f-batalla-integrada`)

- **Objetivo:** que la batalla IA forme parte de la partida Rojo/Azul (Rojo decide cuándo atacar, defensor siempre
  activo), con tokens de entrada y salida reales, estados de inferencia honestos y fallo seguro.
- **Estado inicial:** la batalla IA vs IA era un mundo aparte (reto con aceptación, «mejor de N», marcador propio y
  estado en el cliente). Solo se guardaban los tokens de salida; no había fases intermedias reales (el atacante y el
  defensor corrían en una sola llamada) y nada de la batalla llegaba al marcador de la partida.
- **Decisiones aprobadas:** la batalla «mejor de N» se conserva como **práctica**, solo fuera de una partida en curso;
  la IA de Rojo ataca con la identidad **que haya robado** (invitado por defecto; la cuenta de una credencial
  comprometida sin revocar).
- **Archivos:**
  - nuevos: `src/lab/ataque_ia.py` (identidad, clasificación, puntos, explicaciones), `e2e/ollama_falso.py`,
    `src/lab/test_ataque_ia.py`, `server/test_batalla_partida.py`;
  - `src/lab/cliente_ollama.py` (`tokens_entrada`, `carga_ms`), `atacante.py` (técnica elegida por el jugador),
    `defensor.py`, `motor.py`, `sesion.py` (4 reglas), `schema.py` (tabla `ataques_ia`), `repositorio.py`;
  - `server/app.py` (endpoints `/api/ia/*`, fases por SSE, práctica bloqueada durante la partida, marcador);
  - `ui/index.html`, `render.js`, `app.js`, `api.js`, `escritorio.js`, `styles.css` (ventana ⚔ *Batalla de la
    partida*); `e2e/demo_partida.py`; `server/test_app.py` y `src/lab/test_cliente.py` (ampliados);
  - `README.md`, `docs/CONTRATO_API.md`, `docs/GUION_DEMO.md`.
- **Cambios:**
  - **Rojo lanza ataques** de uno en uno, eligiendo técnica e intensidad, con un tope de 8 por partida. El modelo del
    atacante se comprueba contra su Ollama antes de gastar el ataque.
  - **Defensor siempre activo:** Azul lo fija una vez y el servidor lo comprueba de verdad; desde entonces responde
    a cada ataque sin reto ni aceptación. Todas las vistas ven su estado (verificado, error real o sin configurar).
  - **Identidad robada:** con una credencial comprometida sin revocar, la petición es válida para esa cuenta y el
    asistente entrega datos internos: **datos expuestos**, permanentes. Revocar devuelve a Rojo a invitado.
  - **Fases honestas:** el servidor difunde la fase real (validando → atacante → defensor) con el tiempo
    transcurrido calculado por él; la UI cuenta segundos sin porcentajes. Al terminar se ven tokens de entrada y de
    salida y la carga del modelo tal como los informa Ollama, o «—» si no los envía.
  - **Fallo seguro:** si el defensor no da una decisión válida no se ejecuta nada y no puntúa nadie. Un fallo del
    atacante gasta el ataque sin llegar al defensor, y un ataque a medias al finalizar queda cancelado.
  - **Marcador único:** puntos de Rojo = buzón + IA; puntos de Azul = misiones + IA, con desglose. El resultado
    final y la pantalla de General incluyen la batalla.
  - Cada ataque se **persiste** (`ataques_ia`, con métricas por inferencia) y deja auditoría y eventos SIEM. Es lo
    mínimo para puntuar desde el estado; la cronología filtrable y el panel de resultados siguen en la Fase G.
- **Pruebas (resultados reales, batería completa en verde):**
  - `test_ataque_ia` 22/22 (nuevo); `test_cliente` 18/18 (antes 14: métricas de Ollama, suma con reintento JSON,
    `None` si faltan, técnica elegida); el resto de suites unitarias sin cambios en verde;
  - `server/test_batalla_partida.py` 43/43 (nuevo, con un Ollama **falso** por HTTP): permisos (solo Rojo ataca,
    solo Azul fija el defensor, espectador de solo lectura), 409 fuera de la partida, fases reales observadas,
    tokens y carga transmitidos exactamente, contenido, datos expuestos con credencial robada, revocación, IA engañada
    frenada por la capa de permisos, fallo seguro (HTTP 500 y defensor sin configurar), error del atacante, tope de
    8, auditoría, resultado final, práctica bloqueada y desbloqueada, y cancelación al finalizar a mitad de un ataque;
  - `server/test_app.py` 157/157 y `server/test_partida.py` 30/30;
  - `e2e/demo_partida.py` **87/87** en Chromium real (antes 69), con pasos nuevos 3g' (ataque con credencial
    robada: fase visible en las 4 vistas, datos expuestos, tokens) y 3i (tras revocar, ataque como invitado
    contenido). Resultado: **Rojo 10 — Azul 90**. La primera pasada falló en una comprobación y destapó un fallo real:
    al revocar la credencial, la vista de Rojo seguía diciendo «credencial robada» hasta el siguiente ataque. Ahora
    el servidor difunde el estado de la batalla al comprometer o revocar una credencial, y una prueba del servidor
    lo comprueba;
  - **Ollama real** (30/10/2026, CPU local, Ollama 0.40): 2 ataques de `llama3.2:3b` contra `qwen3:4b` por el
    servidor completo. Los dos quedaron **contenidos** (el defensor pidió autorización). Fases observadas:
    atacante → defensor. Atacante 19,1 s y 4,6 s, defensor 27,3 s y 15,6 s. Tokens de entrada/salida:
    atacante 341/59 y 343/38, defensor 446/73 y 504/73. La primera llamada de cada modelo incluyó unos 7 s de carga
    (7 230 y 7 688 ms) y la segunda 14 y 33 ms. No se probó con modelos reales un ataque con credencial robada.
- **Vistas:** `capturas_vistas.py` sin datos: a 1920×1080 sin scroll interno; a 1366×768 solo General (+16 px en
  Centro de control, como antes). Azul ya no lo tiene porque el mosaico cambió con la ventana nueva. Con ataques en
  la lista, la ventana de la batalla tiene scroll propio (es una lista que crece).
- **Decisiones tomadas (reversibles; revísalas):**
  - **puntos:** datos expuestos +10/+20/+30 según sensibilidad (permanentes); IA engañada +5 para Rojo; contenido
    +5 para Azul; fallo seguro 0/0;
  - **tope:** 8 ataques por partida, que cuentan aunque fallen (incluido el error del atacante);
  - **fallo seguro:** no penaliza a Azul. Sin defensor no gana nada, pero tampoco pierde;
  - el Ollama falso solo sirve para pruebas y nunca se usa en el servidor real.
- **Pendiente:**
  - la cabecera sigue mostrando el marcador de la práctica «BATALLA IA vs IA 0 — 0», que puede confundir durante una
    partida;
  - el árbitro no tiene un botón para cancelar un ataque colgado (lo corta el tope de 300 s o finalizar);
  - cronología, filtros y panel de resultados de la batalla → Fase G.
- **Riesgos de regresión:** medios. Cambian los puntos de la partida (la batalla suma) y la práctica queda bloqueada
  durante la partida. Lo cubren todas las suites. El servidor en marcha debe reiniciarse para crear la tabla nueva.
- **Avance estimado:** ~70 % del plan (A, C, D, E y F hechas; B parcial; G y H pendientes).
