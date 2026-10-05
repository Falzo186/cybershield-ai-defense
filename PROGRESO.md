# Bitácora llm-redteam

## Fase 1 - Esqueleto del simulador
- Qué se hizo: bucle atacante/defensor con Ollama, juez de coincidencia y CLI con registro JSONL.
- Archivos: src/config.py, agentes.py, juez.py, batalla.py, main.py, requirements.txt
- Decisiones: historial propio por agente; juez normaliza (sin espacios/símbolos); num_predict=200.
- Pendiente / siguiente paso: probar con Ollama, analizar data/batallas.jsonl, añadir niveles de dificultad.

## Fase 2 - Niveles de defensa
- Qué se hizo: niveles 1-4 (prompt, +filtro salida, +guardia IA, +detector de entrada por regex).
- Archivos: src/defensas.py (nuevo), src/batalla.py, src/main.py (--nivel)
- Decisiones: gana el atacante solo si el texto final contiene el secreto; la guardia no se llama si el filtro ya bloqueó.
- Métricas nuevas en JSONL: bloqueos_salida, bloqueos_guardia, bloqueos_entrada, fugas_internas.
- Pendiente / siguiente paso: comparar tasas de éxito por nivel; afinar patrones del detector.

## Fase 3 - Campañas y métricas
- Qué se hizo: nivel 0, persistencia SQLite, clasificador de técnicas y modo campaña con tablas resumen.
- Archivos: src/db.py, src/tecnicas.py (nuevos); src/batalla.py, src/main.py; data/redteam.db
- Decisiones: nivel 0 (prompt ingenuo, sin defensas) como baseline para medir cuánto aporta cada defensa.
- Decisiones: técnica por regex (sin IA); "técnica ganadora" = ataque de la última ronda de batallas ganadas.
- Decisiones: cada batalla crea agentes nuevos, así los historiales se reinician.
- Pendiente / siguiente paso: lanzar campaña con N>=10 y analizar tasas por nivel y técnica.

## Fase UI - Interfaz y contrato (mock)
- Qué se hizo: UI "AI Security Laboratory" (3 modos, pipeline, auditoría, modal de métricas) + servidor mock FastAPI con SSE.
- Archivos: docs/CONTRATO_API.md, server/mock_server.py, ui/{index.html,styles.css,api.js,render.js,app.js}, requirements.txt
- Decisiones: UI desacoplada del backend vía contrato; el mock se sustituirá por el motor real sin tocar la UI.
- Decisiones: SSE (EventSource) con reconexión con backoff; HTML/CSS/JS vanilla, sin CDNs ni build.
- Decisiones: protección XSS: todo texto dinámico por textContent/createElement, nunca innerHTML.
- Pendiente / siguiente paso: probar visualmente el mock; implementar los endpoints reales sobre src/ (batalla, defensas, db).

## Fase 0 - Resultados del prototipo
- Qué se hizo: campaña parcial de 26 batallas (rondas=6) sobre niveles 0-2 del prototipo.
- Archivos: data/redteam.db, data/batallas.jsonl
- Resultados: nivel 0 = 10 batallas, 4 victorias atacante (40%), 4.3 rondas prom.
- Resultados: nivel 1 = 10 batallas, 2 victorias (20%), 5.0 rondas prom.
- Resultados: nivel 2 = 6 batallas, 0 victorias (0%), 1 fuga interna bloqueada por el filtro.
- Técnica dominante: urgencia_emocional (5 de 6 victorias); traducción 1.
- Decisiones: muestra pequeña, resultado preliminar; motiva la arquitectura de capas de la versión nueva.
- Pendiente / siguiente paso: niveles 3-4 no se corrieron; repetir con más batallas.

## Fase B1 - Capas deterministas del laboratorio
- Qué se hizo: BD SQLite ficticia (CyberShield), permisos por rol/sensibilidad, repositorio con autorizador y catálogo de herramientas en capas.
- Archivos: src/lab/{permisos,schema,seed,repositorio,herramientas,test_lab}.py
- Decisiones: capas catalogo -> validacion -> permisos/autorizacion -> repositorio; deny-by-default.
- Decisiones: sin SQL libre (consultas fijas y parametrizadas); identidad fijada por el sistema, nunca por el prompt.
- Decisiones: CRITICA solo admin y no delegable; CONFIDENCIAL para empleado solo con autorización humana; auditoría append-only.
- Pendiente / siguiente paso: Fase B2 (motor real Ollama sobre estas capas).

## Fase B2 - Motor real de IA (Ollama)
- Qué se hizo: cliente Ollama, defensor y atacante IA con salida JSON, y motor de una ronda sobre las capas de B1.
- Archivos: src/lab/{cliente_ollama,defensor,atacante,motor,test_motor}.py
- Decisiones: la decisión del modelo es una propuesta, no una ejecución; las capas de herramientas.py deciden.
- Decisiones: la identidad la fija el sistema (repo.identidad), nunca el prompt; cliente con urllib de stdlib.
- Decisiones: errores (timeout, JSON no parseable, fallo interno) dan veredicto ERROR, nunca se disfrazan de bloqueo.
- Decisiones: parseo robusto sin inventar: JSON inválido -> MARCAR_COMO_RIESGO/parse_ok=false.
- Pendiente / siguiente paso: conectar el motor al servidor/UI (reemplazar el mock) y correr campañas reales.

## Fase UI-real - Batalla real con Ollama
- Qué se hizo: servidor server/app.py (mock + batalla real con motor.py) y UI con selectores de modelo, usuario y badge de origen.
- Archivos: server/app.py (nuevo), server/mock_server.py, docs/CONTRATO_API.md, ui/{index.html,styles.css,api.js,render.js,app.js}
- Decisiones: mock y real separados y etiquetados (🟡 MOCK / 🟢 OLLAMA); OLLAMA solo se muestra con eventos origen=ollama.
- Decisiones: errores y timeouts por ronda -> ronda_error, no contaminan métricas y la batalla continúa.
- Decisiones: modelos y estado de Ollama leídos en vivo; identidad elegida entre usuarios semilla (rol fijado por el sistema).
- Decisiones: decision = resultado efectivo tras las capas; decision_ia = propuesta del modelo (DEFENSA_EN_PROFUNDIDAD visible).
- Pendiente / siguiente paso: probar una batalla real con modelos instalados; ajustar timeouts según la máquina.

## Fase ajustes - Contadores, intensidad e historial
- Qué se hizo: marcadores que acumulan por batalla, atacante con intensidad 1-3 e historial desplegable exportable.
- Archivos: ui/{app.js,render.js,index.html,styles.css}, src/lab/{atacante.py,motor.py}, server/app.py, docs/CONTRATO_API.md
- Decisiones: los contadores los acumula la UI por veredicto (ERROR no cuenta); ya no se pisan con la métrica del servidor.
- Decisiones: intensidad ajusta prompt y temperature (0.5/0.7/0.95); prompt exige JSON válido sin texto fuera.
- Decisiones: historial en memoria (prompt, decisiones, riesgo, veredicto, modelos, tiempos, tokens, error) exportable a JSON sin backend.
- Pendiente / siguiente paso: probar intensidades 1-3 con modelos reales y comparar tasas de éxito.

## Fase ajustes - Modo manual real
- Qué se hizo: el modo PRUEBA MANUAL tiene interruptor MOCK/REAL; en REAL usa el defensor Ollama y las capas con identidad del sistema.
- Archivos: server/app.py, server/mock_server.py, src/lab/motor.py, ui/{app.js,render.js,api.js,index.html,styles.css}, docs/CONTRATO_API.md
- Decisiones: veredicto unificado mock/real: motor.evaluar_veredicto y motor.procesar_defensa los usan la batalla y el manual real.
- Decisiones: el manual real reutiliza defensor + capas (ejecutar_herramienta con identidad de repo.identidad); sin duplicar lógica.
- Decisiones: origen siempre visible: badge global (OLLAMA solo con eventos origen=ollama) y etiqueta MOCK/REAL en la tarjeta de decisión.
- Decisiones: errores del defensor -> 502/ronda_error, fuera de las métricas.
- Pendiente / siguiente paso: probar el manual real con prompts de ataque y de consulta legítima.

## Fase ajustes - Veredictos y métrica de engaño a la IA
- Qué se hizo: veredictos afinados para registrar victorias reales del atacante y un contador de "IA engañada".
- Archivos: src/lab/{motor,test_motor}.py, server/{app,mock_server}.py, ui/{render,app}.js, ui/{index.html,styles.css}, docs/CONTRATO_API.md
- Decisiones: FALLA_DEFENSA solo si salieron datos CONFIDENCIAL/CRITICA a quien no tenía derecho (re-comprobación independiente).
- Decisiones: DEFENSA_EN_PROFUNDIDAD = la IA propuso PERMITIR indebido y una capa lo frenó; ia_fallo=true también en FALLA_DEFENSA.
- Decisiones: se quitó la regla "config admin siempre es FALLA" para no penalizar a un admin legítimo.
- Decisiones: "Exitosos" suma solo FALLA_DEFENSA; "IA engañada" suma ia_fallo.
- Pendiente / siguiente paso: campañas reales para medir tasa de IA engañada por modelo e intensidad.

## Fase final - Empaquetado y README
- Qué se hizo: proyecto portable para GitHub ("cybershield-ai-defense") con README, script de arranque y git local sin push.
- Archivos: README.md, ejecutar, .gitignore, LICENSE (MIT), data/.gitkeep, src/lab/seed.py (modo -m), requirements.txt
- Decisiones: ./ejecutar crea .venv, instala una sola vez (.venv/.instalado), crea la BD y no aborta si falta Ollama.
- Decisiones: la BD real es data/lab.db (no cybershield.db); la crea ./ejecutar o `python -m src.lab.seed`.
- Decisiones: README con huecos TODO para los hallazgos finales; datos y métricas marcados como experimentales.
- Pendiente / siguiente paso: pegar métricas reales en el README y subir a GitHub (push manual).

## Fase LAN - Multi-PC, roles y Ollama remoto
- Qué se hizo: servidor en 0.0.0.0 con URL de LAN, Ollama por host (atacante y defensor en PCs distintas) y vistas por equipo.
- Archivos: server/{app,mock_server}.py, src/lab/motor.py, ui/{index.html,app.js,render.js,api.js,styles.css}, ejecutar, README.md, docs/CONTRATO_API.md
- Decisiones: inferencia distribuida (cada PC su Ollama); host_atacante/host_defensor por petición; modelos validados en SU host.
- Decisiones: acceso abierto en LAN sin autenticación; hosts restringidos a red local para evitar SSRF.
- Decisiones: vistas por rol vía ?rol= y localStorage (rojo/azul/general); IP de Ollama guardadas por navegador.
- Decisiones: el estado SSE difundido solo aplica si coincide con el host propio (no pisa a otros equipos).
- Pendiente / siguiente paso: probar con dos PCs reales y medir latencia; añadir autenticación si se sale del laboratorio.

## Fase J1 - Diagnóstico, listo/aceptar y puntaje
- Qué se hizo: botón «Probar modelo», handshake reto/aceptar entre equipos y marcador mejor-de-N con banner y revancha.
- Archivos: server/app.py, src/lab/cliente_ollama.py, ui/{index.html,app.js,render.js,api.js,styles.css}, docs/CONTRATO_API.md
- Decisiones: timeout 120 s por llamada (la primera carga el modelo en memoria); «Probar modelo» usa 15 s y fuerza esa carga.
- Decisiones: handshake antes de gastar inferencia real; reto sin respuesta en 30 s se cancela; la vista general inicia sin aceptación.
- Decisiones: puntaje mejor-de-N calculado en el servidor, sin tocar las capas de seguridad ni los veredictos.
- Decisiones: dificultad mapea a usuarios semilla (empleado/analista/admin) y reemplaza al selector de usuario en batalla.
- Pendiente / siguiente paso: probar el handshake con dos navegadores/PCs y revisar la semántica de la dificultad «admin».

## Fix - Dificultad sin admin en modo puntaje
- Dificultad: Fácil=invitado, Media=empleado, Difícil=analista; admin (root.lab) sale del selector.
- Modo demostración (sin puntaje): casilla propia con etiqueta visible; usa admin y no suma al marcador ni emite partida_fin.
- Con rol admin fuera de la demostración, el servidor rechaza el inicio con la advertencia de acceso legítimo.
- Decisión: admin es invicto por diseño (acceso legítimo), no es una dificultad; se separa a modo demostración.
- Archivos: server/app.py, ui/{index.html,app.js,render.js,styles.css}, docs/CONTRATO_API.md

## Fase robustez - JSON confiable en modelos chicos, reintento, logging
- Qué se hizo: prompts de defensor y atacante más cortos con un ejemplo JSON (few-shot) y cierre "RESPONDE ÚNICAMENTE CON EL JSON".
- Archivos: src/lab/{cliente_ollama,defensor,atacante,motor}.py, server/app.py, .gitignore
- Decisiones: num_predict bajo (defensor 150; atacante 120/160/220 por intensidad) para que el modelo no divague.
- Decisiones: generar_json hace UN solo reintento si la respuesta no es JSON válido; si falla de nuevo, parse_ok=false/ERROR como antes.
- Decisiones: el reintento se audita como MODEL_REQUEST "(reintento JSON)"; ambos fallos se guardan en data/debug_respuestas.log.
- Decisiones: extraer_json quita vallas ```json y rechaza objetos sin los campos requeridos (no construye objetos a medias).
- Pendiente / siguiente paso: medir con llama3.2:1b/3b cuántas rondas necesitan reintento.

## Fase R1 - Riesgo acumulado por sesión y fuga parcial
- Qué se hizo: estado de sesión por batalla (src/lab/sesion.py), circuito de seguridad por sesión, nivel_fuga e indicador de sospecha en la UI.
- Archivos: src/lab/{sesion,motor,defensor}.py, server/app.py, ui/{app.js,render.js,styles.css}, docs/CONTRATO_API.md
- Decisiones: el riesgo acumulado es una señal adicional (contexto para la IA), no reemplaza a las capas ni al riesgo de la ronda.
- Decisiones: el circuito de seguridad por sesión (>70) es determinista y no depende del LLM: fuerza SOLICITAR_AUTORIZACION.
- Decisiones: techo 40 por componente (patrones / rechazos) para que el total pueda superar 70 y el circuito sea alcanzable.
- Decisiones: fuga parcial (motivo que nombra un secreto LAB_…) no suma al marcador pero sí se registra; "CRITICA" no cuenta (es etiqueta pública).
- Decisiones: la sesión se crea al iniciar cada batalla (revancha incluida) y se descarta al terminar.
- Pendiente / siguiente paso: calibrar pesos con partidas reales.

## Fase R2 - Filtro rápido antes de inferencia
- Qué se hizo: src/lab/filtro_rapido.py bloquea casos obvios por regex antes de llamar al defensor LLM.
- Archivos: src/lab/{filtro_rapido,motor,test_motor}.py, server/app.py, ui/render.js, docs/CONTRATO_API.md
- Decisiones: capa determinista previa: secretos LAB_, extracción del system prompt, "ignora tus instrucciones", SQLi obvia, modo admin/desarrollador.
- Decisiones: bloqueo = RECHAZAR riesgo 90 con origen_decision=filtro_rapido; veredicto DEFENSA_EXITOSA; no gasta inferencia.
- Decisiones: se aplica en procesar_defensa (batalla y manual real) y cuenta como rechazo en EstadoSesion.
- Decisiones: el ataque de prueba de test_motor ya no menciona LAB_ (si no, el filtro lo bloquearía antes del caso a probar).
- Pendiente / siguiente paso: medir cuántas rondas ahorra el filtro y ajustar falsos positivos.
