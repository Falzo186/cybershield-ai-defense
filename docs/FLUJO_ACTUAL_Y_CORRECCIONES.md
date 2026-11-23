# Flujo actual del juego y propuestas de corrección

Documento para que marques correcciones. Describe **lo que el motor hace hoy** (leído del código, no de memoria) y lo que propongo cambiar. Marca cada propuesta con `[x]` (sí), `[ ]` (no) o escribe tu variante.

## 1. Por qué te perdiste (diagnóstico honesto)

| Lo que te pasó | Causa real |
|---|---|
| «Le doy a pedir ayuda, genera un prompt y se queda ahí» | Con la IA en modo `assist` la IA **solo propone**; hay que pulsar **«Confirmar y ejecutar»** debajo de la propuesta. La interfaz no lo explica y queda entre muchos formularios. En modo `auto` ejecuta sola. |
| «No sé cuál acción manda un correo fácil de obtener» | La acción es «Enviar correo a una identidad» con la plantilla «aviso soporte». Pero el correo **solo da la credencial si alguien pulsa el enlace**: un empleado sin jugador lo pulsa solo a los 25 s de partida; un empleado **con jugador Azul** (como Adela/EMP-01) solo lo pulsa si ese humano decide hacerlo. En tu partida enviaste los correos a EMP-01, que tenía jugador. |
| «Me rechazó por BUDGET_EXCEEDED» | Máximo **3 correos por ronda** (ronda = 60 s de partida). |
| «No conseguí la base» | La base completa (W2) exige que el Azul apruebe una elevación; la tabla financiera (W1) exige la credencial de **Andrea Salas (EMP-05)**. En tu partida terminó en empate: 0 tablas extraídas. |

## 2. Camino del Rojo hoy (ver dibujo en el chat)

1. **Reconocer el directorio** (`scan_directory`): identifica hasta 3 personas por uso; 2 usos por ronda; +2 puntos por persona.
2. **Conseguir una credencial** (elige una):
   - **a. Correo engañoso** (`send_email`, plantilla *aviso soporte* o *reporte urgente*): 3 por ronda, +1 punto. El enlace expone la credencial cuando **alguien lo pulsa y confirma la acción de riesgo** (+15 puntos al Rojo, alerta al Azul).
   - **b. Adivinar** (`guess_credential`): 5 dígitos + 1 letra; 3 intentos por ronda, 12 por partida, espera de 20 s entre intentos; 3 fallos bloquean la identidad 90 s. Un intento muy parecido (≥ 4 de 6) manda una «solicitud misteriosa» al Azul. Acertar da +10.
   - **c. Atajo:** con la credencial de **Sofía Torres (EMP-03)** se extrae la tabla `empleados`, y eso **expone las credenciales de todos**.
3. **Credencial válida descubierta:** aparece en «Credenciales descubiertas».
4. **Dos formas de ganar** (por defecto gana con cualquiera):
   - **W1:** extraer la tabla `reportes_financieros` usando a **Andrea Salas (EMP-05, Finanzas)**. +40 puntos y alerta crítica.
   - **W2:** «Pedir elevación» (con motivo) → **el Azul la aprueba** → «Exportar base completa» **dentro de 120 s** (+80 puntos). Exportar copia las 8 tablas.
5. **El motor declara la victoria Roja** al validar la extracción.

## 3. Camino del Azul hoy

- Cada jugador Azul **es** un empleado (EMP-01 a EMP-06) y además defiende: lee **su** bandeja, abre/ve/pulsa enlaces, reporta correos, neutraliza enlaces, ve alertas del sistema, revoca credenciales, contiene incidentes y responde solicitudes (elevaciones, accesos misteriosos, autorizaciones de su IA).
- Gana por **contención**: credenciales comprometidas revocadas, incidente contenido y **continuidad ≥ 60 %** (no bloquear de más a los empleados legítimos). Si rechaza todo, es EMPATE.
- La IA Azul hoy se maneja como la Roja: un formulario de prompts. **Ese es el problema que señalas.**

## 4. Propuestas — marca las que quieres

### Rojo: más guiado y menos tedioso
- [ ] **R1. Misión guiada:** una barra «Paso 1 de 5» con **un solo botón grande** «Hacer el siguiente paso» (sugiere la acción correcta; los formularios actuales quedan en «modo experto» plegado).
- [ ] **R2. Botón «¿Qué hago ahora?»** que, con el estado real, dice la siguiente acción y por qué.
- [ ] **R3. Credenciales descubiertas como desplegable** (combo) con ver/ocultar; por defecto plegado, con un contador «2 de 6».
- [ ] **R4. IA Roja sin «confirmar» escondido:** la propuesta sale como aviso fijo en la parte alta («La IA propone: … [Ejecutar] [Descartar]»), o modo «ejecutar al instante» configurable.
- [ ] **R5. Distribución:** columna izquierda estrecha con **participantes**; centro dividido en **Preparación | Ejecutar**; derecha **IA**.
- [ ] **R6. Nombres claros** en las acciones (ej.: «Enviar correo de soporte falso» en vez de «Enviar correo a una identidad») y una línea de ayuda bajo cada una.
- [ ] **R7. Atajo visible:** mostrar en el panel qué identidad abre la tabla financiera (Andrea) y cuál abre `empleados` (Sofía).

### Azul: de «IA que arma prompts» a «centro de monitoreo»
- [ ] **B1. IA Azul como monitor pasivo:** sin formulario de prompts. Una IA que **observa eventos y puntúa** cada acción/solicitud con un **nivel de sospecha 0–100** y un motivo corto.
- [ ] **B2. Panel de monitoreo (dashboard):** medidor general de riesgo, lista de eventos ordenada por sospecha (colores), y para cada solicitud su puntuación y por qué.
- [ ] **B3. Solicitudes con puntuación:** el cuadro emergente muestra la sospecha estimada de la IA, **sin decidir por los humanos**.
- [ ] **B4. La IA Azul sigue pudiendo pedir autorización** (esa parte ya existe) pero solo como consecuencia de su monitoreo, no por prompt.
- [ ] **B5. Roles de ciberseguridad con niveles** en lugar de «Ventas/Compras/Finanzas…»: Analista N1 (correos y alertas), Analista N2 (identidades y aprobar solicitudes) y Responsable N3 (contención y elevaciones). Los empleados del escenario pasan a ser cuentas **NPC** que el Rojo ataca.
  - Nota: hoy los jugadores Azul son los propios empleados porque así lo pide el paquete del profesor (correo → enlace → exposición). Con B5 los empleados serían simulados y el Azul vería su bandeja de **reportes** en vez de su correo personal. Es el cambio de fondo; dime si lo quieres o si prefieres solo **renombrar** los departamentos.

### Flujo general
- [ ] **G1. Partida de prueba rápida:** plantilla de 5 minutos con 1 Rojo y 1 Azul, empleados NPC que pican a los 10 s y elevación aprobable, para ensayar sin esperar.
- [ ] **G2. Resumen final** «quién hizo qué» con la línea de tiempo (para demostración).
- [ ] **G3. Vista del espectador/profesor** con marcador y cronología, sin datos sensibles.

### Qué NO quiero perder de la esencia (confirma)
- La IA propone, el motor valida y los humanos deciden.
- Nada empieza solo; el administrador inicia.
- Todo es ficticio y local; los datos simulados van etiquetados.
- El Rojo no ve nada interno del Azul (votos, solicitudes misteriosas).
- [ ] Añade aquí lo que consideres esencial: ______________________

## 5. Lo que haría yo (orden sugerido)
1. R1, R2, R3, R4, R5, R6 (solucionan que no sepas qué hacer; bajo riesgo).
2. B1, B2, B3 (la IA Azul como monitor).
3. B5 solo si confirmas que quieres cambiar los roles; es el cambio más grande y toca el motor y las pruebas.
4. G1–G3 al final.

## 6. Dudas que necesito que respondas
1. ¿La IA Azul debe puntuar **solo con reglas del motor** (siempre disponible, sin Ollama) y usar Ollama solo para explicar, o puntuar con el modelo?
2. ¿Los empleados del escenario deben seguir siendo los jugadores Azul (B5 no) o pasan a NPC (B5 sí)?
3. ¿Quieres que el Rojo pueda ganar solo con W1 (tabla financiera) o que la base completa sea el objetivo principal?
