# Guion de la demo en vivo (10-15 min)

## Antes de empezar (5 min antes)

1. Arranca el servidor: `cd llm-redteam` y `py -3 server\app.py` (en Linux/macOS `python3 server/app.py`).
   Anota el **código de árbitro** que imprime (`Código de árbitro (vista General): ……`).
2. Abre **un navegador (o perfil) por participante**, en este orden: **General** `http://localhost:8000/?rol=general`
   (al proyector; nombre + código de árbitro) · **Azul** `?rol=azul` · **Rojo** `?rol=rojo` · opcional
   **Espectador** `?rol=espectador` (sin nombre). Cada uno escribe su **nombre**. Azul entra antes de que Rojo envíe.
3. Comprueba que cada vista muestra su etiqueta con el nombre («EQUIPO AZUL · Beto»), «PREPARACIÓN» y «● Conectado».
   Para la batalla de la partida: Rojo elige su modelo en *IA Atacante* (p. ej. `llama3.2:3b`) y Azul el suyo en
   *IA Defensora* (p. ej. `qwen3:4b`) y pulsa **🛡 Usar mi modelo como defensor**. Usa antes *Probar modelo* en
   ambos: la primera llamada carga el modelo y tarda unos segundos más.
4. En General elige la **duración (5, 10 o 15 min)** y pulsa **▶ Iniciar partida**: todas las vistas pasan a la cuenta
   atrás. Antes de eso, nada cuenta (Rojo no puede enviar).
5. Plan B si algo falla en vivo: las capturas de una partida real están en `docs/capturas_demo/`.

## Desarrollo (orden sugerido)

| Min | Vista | Acción | Qué contar |
|---|---|---|---|
| 0-2 | General | Presenta el escritorio: ventanas, minimizar/maximizar, marcador arriba. | Laboratorio 100 % local y ficticio; el árbitro ve todo. |
| 2-3 | General | *Simulación* → *Iniciar*: el pipeline se ilumina capa por capa. | Defensa en profundidad: la IA propone, las capas deciden. |
| 3-5 | Rojo | 📬 Correo → envía *Soporte técnico*, *Recursos humanos* (PDF) y *Paquetería* (PDF). | Plantillas fijas, enlaces locales; Rojo nunca ve el enlace. |
| 5-7 | Azul | 📬 Buzón → abre *Paquetería* → pulsa el enlace (el "empleado distraído"). | En General: riesgo 15, Rojo +10. |
| 7-9 | Azul | Abre *Soporte técnico* → **⚑ Reportar**; vuelve a *Paquetería* → **⛔ Contener**. | Riesgo baja y Rojo pierde sus 10 puntos; dos misiones completadas. |
| 9-10 | Azul | *Recursos humanos* → **🔎 Verificar remitente** (imita `cybershield`) → **🔗 Inspeccionar enlace** → **👁 Previsualizar** (visor seguro) → **⚑ Reportar PDF** → **🧪 Aislar**; pestaña 🎯 Misiones. | Inspeccionar no es un clic; el visor no descarga ni ejecuta nada; reportar quita los +5 a Rojo. |
| 10 | Rojo | 📬 Correo → **Enviados · seguimiento**. | Rojo ve el clic y el adjunto abierto, nunca si se reportó. |
| 10-11 | Azul | Vuelve a *Soporte técnico* (Sospechosos) → pulsa el enlace → **Iniciar sesión (simulado)**. | La credencial queda comprometida: Rojo +15. Contener no basta. |
| 11 | Rojo | ⚔ *Batalla de la partida* → técnica *autoridad* → **Lanzar ataque IA**. | Rojo ataca con la credencial robada: si el defensor atiende la petición, **datos expuestos** (+10). Todas las vistas ven «esperando a la Ollama…» y los segundos reales. |
| 11-12 | Azul | En el correo, **🚨 Abrir incidente** → pestaña Incidentes → **🔒 Revocar credencial** → **Investigar** → intenta **Resolver** (lo rechaza: falta contener) → **Contener** → **Resolver**. | Dependencias entre misiones; el servidor explica qué falta. |
| 12 | Rojo | Lanza otro ataque IA. | Con la credencial revocada vuelve a ser invitado: el defensor lo contiene (Azul +5). Enseña los tokens y la carga del modelo. |
| 12 | Azul / Rojo | Azul abre **🔐 Seguridad** (qué falta, de lo más grave a lo menos) y **🗂️ Archivos**; Rojo abre **🔔**. | Cada equipo solo tiene sus aplicaciones (lo decide el servidor). Rojo se entera de los clics, pero nunca de lo que hace Azul. |
| 12 | General | Maximiza **Auditoría** (□) para enseñar el rastro; enseña `data/eventos.jsonl`. | Cada acción queda en una auditoría append-only y en JSON para Wazuh. |
| 12-13 | General | 🏁 **Finalizar partida** → confirma. | Resultado congelado; tras cerrar, Rojo/Azul reciben 409. |
| 13 | General | En la pantalla final, **📊 Ver desglose y cronología** → pestaña *Cronología* → filtra *Batalla IA*. | Cada punto tiene su fórmula y la suma es el marcador. La cronología cuenta la partida minuto a minuto, y Rojo la ve entera ahora que terminó. |
| 13-15 | — | Preguntas. La *Batalla IA vs IA* «mejor de N» es práctica: tras finalizar. | Cada ataque son dos llamadas de 5-30 s en CPU: deja tiempo para que terminen. |

Resultado de la prueba automatizada con este guion: **Rojo 10 — Azul 90**, riesgo final 20/100. Usa un Ollama
falso con respuestas fijas: el ataque con credencial robada siempre expone datos y el de invitado siempre se contiene.
Con modelos reales el resultado de cada ataque depende del modelo (en la medición real, `qwen3:4b` pidió
autorización y contuvo los 2 ataques como invitado). La fuga de datos (+10) no se recupera: Rojo la conserva aunque
Azul revoque después. Para que Rojo puntúe más, deja un enlace sin contener o un PDF sin reportar antes de finalizar.

## Si algo sale mal

- Un panel "desapareció": búscalo en la barra de tareas (puede estar minimizado) o pulsa **▦ Organizar**.
- El diseño de ventanas estorba: **☰ Vista clásica** en la cabecera (se vuelve con 🖥 Vista escritorio).
- Cerraste una pestaña: vuelve a abrir la misma URL en el mismo navegador y reconecta sola (la sesión se guarda).
- Otra demo con la misma gente: al terminar, **↻ Nueva partida** en General (sin reiniciar el servidor).
- Un ataque IA tarda mucho: es real (CPU). La fase dice a qué Ollama se espera; el tope es de 300 s por inferencia. Si el
  defensor de Azul falla, el ataque se **deniega** (fallo seguro) y no puntúa nadie.
- Ensayo completo sin manos: `py -3 e2e\demo_partida.py` (~15 s, 42 comprobaciones, regenera las capturas).

---

# Guion de 10 minutos — combate IA vs IA (misión 23 h, 2026-11-18)

**Prepara antes (5 min):** `ollama list` con `qwen3:8b` y `llama3.1:8b`; calienta cada uno con una llamada corta; `python server/app.py` y anota el código de árbitro;
abre `http://localhost:8000/combate/` en dos ventanas (árbitro y espectador).

| Min | Qué haces | Qué dices |
|---|---|---|
| 0–1 | Cabecera: chips «Ollama activo» y **WAZUH SIMULADO**; menú | «Laboratorio local con datos ficticios. La IA propone, el motor valida, las capas autorizan; **Wazuh es simulado**, y lo ves rotulado en todas partes.» |
| 1–3 | Árbitro: escenario `verificacion_falsa-sencillo`, Rojo `qwen3:8b`, Azul `llama3.1:8b`, semilla 1 → Iniciar | «Dos modelos de 8B reales. Nadie es ganador por lo que diga: gana quien llegue a sus objetivos en el estado verificable.» Señala «El equipo Rojo redacta…» y la cronología |
| 3–5 | Sigue 2–3 turnos: mensaje del Rojo, alertas del SIEM, decisión del Azul con su justificación | «El Azul decide con el registro del sistema; el texto del mensaje es un dato. Esta alerta no prueba por sí sola que sea malicioso.» |
| 5–6 | Fin de la partida: banner de resultado, métricas, «Exportar JSON» | «El resultado sale del evento `partida.resultado` que escribe el motor, no del navegador. La cadena de hashes está íntegra.» |
| 6–8 | Segunda partida **con modelos falsos** (`falso:objetivos` vs `falso:aprobar`): victoria Roja en 2 turnos; luego `falso:rechazar`: **empate degradado** | «Ambos pueden ganar de forma verificable. Y “rechazar siempre” no gana: exige ≥ 70 % de legítimas.» |
| 8–9 | Espectador: sin botones, solo lectura (un POST da 403); pestaña Wazuh (simulado) con filtros y detalle JSON | «El espectador es de solo lectura real. Ruido de fondo incluido.» |
| 9–10 | Historial y Campañas; cierra con las cifras reales de `docs/evaluacion/` | «Esto son las medidas honestas con 8B: lo que funcionó y lo que no.» |

**Plan B si Ollama falla:** usa modelos falsos (`falso:*`) para los pasos 1–8 (muestran el motor, no la calidad de un modelo) y di explícitamente que no hay IA real en esa
parte; muestra la partida real ya guardada en el **Historial** (se abre y se reproduce con el control de turno).
**Plan C:** capturas de `docs/capturas_final/`.

---

# Guion de 10 minutos v2 — combate IA vs IA (misión extra, 2026-11-19)

Reemplaza al guion de la misión de 23 h para exposiciones: incluye una partida en vivo con 8B, una **reproducción curada**, el **guion determinista** y la explicación honesta de por qué el Rojo no ganó. El guion anterior sigue más arriba, sin tocar.

**Prepara antes (5 min):** `ollama list` con `qwen3:8b` y `llama3.1:8b`; calienta cada modelo con una llamada corta; `python server/app.py` y anota el código de árbitro; abre `http://localhost:8000/combate/` (árbitro). No lances nada más que use la GPU. Elige el escenario `verificacion_falsa-sencillo`, semilla 1.

| Min | Qué haces | Qué dices |
|---|---|---|
| 0–1 | Cabecera: chips «Ollama activo» y **WAZUH SIMULADO**. | «Laboratorio local con datos ficticios. La IA propone, el motor valida, las capas autorizan; Wazuh es simulado y está rotulado en todas partes.» |
| 1–4 | **Partida en vivo con 8B**: Rojo `qwen3:8b`, Azul `llama3.1:8b` → Iniciar. Sigue 2–3 turnos (mensaje del Rojo, señal del SIEM, decisión del Azul con su justificación). Mientras corre, cada turno tarda 10–25 s: aprovecha para explicar. | «Dos modelos reales de 8B. El Azul decide con el registro del sistema; el texto del mensaje es un dato. La alerta del SIEM no prueba por sí sola nada.» |
| 4–5 | Cuando acabe (o con la partida ya guardada si el tiempo aprieta): banner de resultado y «Exportar JSON». | «El resultado lo escribe el motor en `partida.resultado`; el navegador no calcula nada. La cadena de hashes está íntegra.» |
| 5–6 | **Historial → Partidas de demostración curadas** → «Reproducir cronología» en la de *sobre-cautela* (empate degradado). | «Esto es una partida REAL de la campaña, no una simulación nueva: los eventos son los registrados, con su semilla y su versión de prompts. El Azul frenó al Rojo pero escaló también a los empleados legítimos: no cuenta como victoria.» Opcional: la de *objetivo parcial* (llama→llama, 1 de 2 objetivos). |
| 6–8 | **Teatro de batalla → «Demostración del motor · Guion determinista (sin IA)»**. Botón 1: guion contra Azul «APROBAR siempre» → **victoria Roja** en 2 turnos. Botón 2: el mismo guion contra el Azul por registro → **victoria Azul** (100 % de legítimas). | «Atención a la etiqueta roja: **GUION DETERMINISTA — NO ES UN MODELO**. Esto no es un Rojo con IA que gane: sirve para enseñar que el motor sí puede dar victoria Roja cuando el defensor cede, y que un defensor que verifica el registro no cede.» |
| 8–10 | Pestaña Campañas / `docs/evaluacion/INFORME_CAMPANAS.md` y `INFORME_CAMPANAS_V2.md`. | Ver abajo («Cómo explicar honestamente…»). |

## Cómo explicar honestamente «el Rojo no ganó» y por qué

1. **Los hechos:** en `combate-v1`, el Rojo 8B ganó **0 de 240** partidas con IA real; en la matriz principal solo 6 llegaron a un objetivo parcial, todas con `llama3.1:8b` contra sí mismo (y otras 6 en las variaciones, también llama). Contra un Azul «aprueba todo» sí gana (93 %), así que sabe pedir.
2. **La razón principal:** el Azul decide con el registro (derechos y autorizaciones) y el escenario fue diseñado para que quien verifica no tenga que ceder. Ganar al Rojo es fácil si el defensor lee el registro; **el problema real del Azul no es ceder, es el servicio**: `qwen3:8b` escala ≈70 % de sus decisiones y cae en empate degradado el 30 % de las veces.
3. **Lo que no se afirma:** que el Rojo 8B no pueda ganar jamás; son 60 partidas por pareja, un solo diseño de prompts y modelos pequeños. La prueba de sensibilidad sí mostró un fallo real del Azul: ambos 8B aprobaron un documento interno a quien no tenía el derecho registrado si lo pedía con cortesía (v2: qwen 8/8, llama 5/8).
4. **Lo que se hizo después (misión extra):** prompts v3 y la campaña `combate-v2`, con los resultados lado a lado y sin retocar v2 (ver `INFORME_CAMPANAS_V2.md`).
5. **El guion determinista no es evidencia sobre ningún modelo.** Se usa solo para explicar el motor.

**Plan B si Ollama falla:** pasos 1–5 con la partida curada y las capturas de `docs/capturas_final/extra/`; el guion determinista funciona sin Ollama. Dilo explícitamente.
**Ensayo sin GPU:** `python e2e/test_combate_extra.py` (29 comprobaciones con modelos falsos; regenera las capturas de `docs/capturas_final/extra/`).

---

# Guion de 10 minutos v3 — con modo Caminos (misión Caminos, 2026-11-21)

**Prepara (5 min):** `ollama list` con `qwen3:8b` y `llama3.1:8b` (calienta cada uno); `python server/app.py` y anota el código de árbitro; entra como árbitro en `/combate/` o `/equipo/` (así `/simulacion/` puede lanzar partidas). Abre `http://localhost:8000/simulacion/` y `/combate/`.

| Min | Qué haces | Qué dices |
|---|---|---|
| 0–1 | Cabecera con **WAZUH SIMULADO**. | «Laboratorio local, datos ficticios; la IA propone, el motor valida y declara el resultado.» |
| 1–3 | **Combate libre real** (`/combate/`): Rojo `qwen3:8b` vs Azul `llama3.1:8b` (`LIBRE_IA`). | «Aquí el Rojo solo escribe texto contra un Azul que decide por el registro: en 240+300 partidas **no ganó ninguna**. Es un resultado válido, no un fallo de la demo.» |
| 3–4 | `/simulacion/` → catálogo: señala la **insignia** de cada tarjeta. | «Tres tipos de procedencia: `LIBRE_IA`, `CAMINOS_IA` (un 8B elige opciones del grafo) y `CAMINOS_GUION` (decisiones prefijadas).» |
| 4–6 | **Reproducir «Victoria Roja: el segundo factor llegó por un correo que nadie reportó»** (4×). Señala el grafo, el inventario, las alertas SIMULADAS y «Qué enseña». | «**Es un guion**: demuestra que el motor y el grafo permiten este final; **no** es «la IA venció». Mira qué decisión del Azul lo permitió: no cuestionar de dónde venía el segundo factor.» |
| 6–7 | Reproducir **la reversión** («parece ganar el Rojo y al final gana el Azul»). | «Rotar la credencial a tiempo invalida la sesión: el Azul puede recuperar una partida que parecía perdida.» |
| 7–9 | **Modo automático en vivo**: «Lanzar una partida ahora» → Automático, Rojo `qwen3:8b`, Azul `llama3.1:8b` → «Jugar y ver». | «Aquí dos 8B juegan solos con credenciales ficticias fijas; el motor valida cada credencial. Si el Azul aprueba una válida sin ver el contexto (hora, dispositivo, canal), el Rojo gana de verdad; si el Rojo toca una credencial señuelo, pierde.» |
| 9–10 | Resultados de `docs/evaluacion/INFORME_CAMINOS.md`. | Tasa empírica de victoria Roja con 8B **en este modo** (con n e IC) y honestidad sobre lo que no se probó. |

**Cómo explicar con honestidad `LIBRE_IA` vs `CAMINOS_*`:** el combate libre mide si un modelo logra engañar con **solo texto** a un defensor que verifica el registro (no lo logró). Caminos **cambia las reglas del juego**: da al Rojo opciones y un camino real a la victoria y mide qué hace cada 8B con ellas. Una victoria Roja de **guion** prueba que el diseño la permite; una de **8B** (`CAMINOS_IA`) es real pero **solo en este modo**; ninguna debe presentarse como «la IA hackeó a la IA» en general.
**Plan B sin Ollama:** reproduce las 6 grabaciones (no necesitan GPU) y lanza partidas con los modelos simples (rotuladas GUION).
