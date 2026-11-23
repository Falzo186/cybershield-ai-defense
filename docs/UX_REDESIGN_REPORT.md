# UX_REDESIGN_REPORT

## Qué se modificó
**Visual:** nuevo sistema de diseño (`ui/nova/ds.css`, ver `DESIGN_SYSTEM.md`), tablero de 3 zonas, barra superior con chips de estado (incluye PRÁCTICA), tarjetas con jerarquía (destacada = atención, azul = IA).

**Rojo:** barra de 6 fases con progreso real; «Paso N de 5»; **Hacer siguiente paso** (prepara, no ejecuta); **¿Qué hago ahora?** (usa el estado real y solo ofrece acciones disponibles); elección de ruta (financiera / copia completa); credenciales plegables con contador y 6 estados (Desconocida, Identificada, Candidata, Validada, Comprometida, Revocada); acciones con nombre de jugador y explicación; panel «Tus límites» con ronda y cuenta atrás; mensajes de rechazo explicados; tarjeta de IA con Ejecutar / Editar / Descartar, estado del modelo y última inferencia; el modo automático solo se ve como opción explícita del administrador.

**Azul:** panel «Seguridad de la empresa» (riesgo general 0–100, alertas críticas, incidentes, correos sospechosos, credenciales comprometidas, solicitudes, estado de identidades), «Monitor de eventos» ordenado por sospecha con detalle, «Solicitudes que requieren atención» con análisis, tiempo restante y consecuencia de cada decisión, bandeja con puntuación por correo, IA defensora como monitor (formulario de prompts solo en modo experto).

**Partida:** modo práctica (5 min), botón de siguiente paso del administrador, resumen final con línea de tiempo filtrable, vista de espectador, estados de componente (cargando, vacío, error), Ollama: encender/apagar y tope de modelo.

**Motor/API (apoyo a la UX):** puntuación de sospecha determinista, presupuesto visible, NPC por dificultad, `empleados` sin cascada, `/api/nova/resumen`, `/api/nova/azul/explicar`, `/api/nova/ollama/*`.

## Qué se conservó
Pipeline de validación del motor, visibilidad por rol, inicio manual, W1/W2, condiciones del Azul, votación con decisor, identidades empresariales (los jugadores Azul siguen siendo empleados; los empleados sin jugador son NPC), presencia, descargas, anti-SSRF. Todos los `id` de la interfaz.

## Errores corregidos
Pantalla del Rojo ininteligible; confirmación de la IA escondida; códigos técnicos como mensajes; límites invisibles; NPC infalibles; cascada de credenciales por `empleados`; credenciales en claro en la tabla extraída; error de socket de Ollama sin explicación; columnas del monitor que se solapaban y chip de ronda truncado (detectados en las capturas y corregidos).

## Pendiente
- Modalidad SOC como opción independiente (no se hizo a propósito).
- Partida con IA Ollama real sobre la interfaz nueva y prueba en dos PC (criterios 14 y 33).
- Calibrar la dificultad «normal» con partidas humanas.
- Capturas antiguas de `docs/capturas_*` muestran la interfaz anterior; las nuevas están en `docs/capturas_ux/`.

## Pruebas
Ver `REGRESSION_TEST_RESULTS.md`: 57/57 suites, 2417/2417 comprobaciones, con 28 nuevas de experiencia de usuario contra el backend real.
