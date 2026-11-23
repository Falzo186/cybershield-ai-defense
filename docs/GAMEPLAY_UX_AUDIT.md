# GAMEPLAY_UX_AUDIT — auditoría de jugabilidad y experiencia de usuario

Auditoría hecha leyendo el código real (`src/lab/nova/motor.py`, `escenario.py`, `ia.py`, `server/nova.py`, `ui/nova/*`) **antes** de tocar nada, y verificada después con pruebas. Estado a fecha de esta entrega.

## 1. Funcionamiento encontrado (antes del rediseño)

| Área | Cómo funcionaba |
|---|---|
| Acciones del Rojo | `scan_directory` (2 por ronda, ≤3 personas, +2 pts c/u), `send_email` (3 por ronda; plantillas aviso_soporte / reporte_urgente maliciosas, consulta_cordial no), `guess_credential` (3/ronda, 12/partida, espera 20 s, 3 fallos bloquean 90 s, parecido ≥4/6 abre «solicitud misteriosa»), `query_resource`, `extract_table`, `request_elevation`, `export_database` (solo con elevación aprobada ≤120 s), `respond_info`, `message_team`. |
| Acciones del Azul | Abrir/ver/pulsar enlace, reportar, neutralizar enlace, clasificar, revocar/suspender, contener incidente, estados de alerta, aprobar/rechazar/pedir info/escalar, votar, tareas, chat. |
| Victoria | W1 = tabla `reportes_financieros` extraída; W2 = las 8 tablas (vía `export_database` tras elevación o una a una). Azul gana por contención con continuidad ≥ 0,6; «rechazar todo» → EMPATE. |
| Presupuestos | Por ronda de 60 s (correos 3, reconocimientos 2, intentos 3) y por partida (12 intentos). |
| Correos | Correos programados (SC-01…06) + correos del Rojo. Un enlace malicioso solo expone la credencial si alguien lo pulsa **y** completa la acción de riesgo. |
| NPC | Empleado sin jugador pulsaba el enlace **siempre** a los 25 s (`click_prob_unconnected = 1.0`). |
| Credenciales | Hash + cifrado; el Rojo solo ve lo descubierto (enmascarado). EMP-04 débil (`12345A`). |
| Autorizaciones | Aprobaciones con recomendación de reglas, votación con decisor, IA Azul puede pedir autorización. |
| Ollama | Proveedor etiquetado, anti-SSRF, modo off/assist/auto; arranque/apagado y tope de tamaño añadidos antes (commit dc8bd8c). |
| Estados | CONFIGURACION → SALA_DE_ESPERA → LISTA → EN_CURSO ⇄ PAUSADA → FINALIZADA/CANCELADA. Nunca inicia solo. |

## 2. Problemas encontrados

### Usabilidad
- U1. Pantalla del Rojo = formularios apilados sin jerarquía; no se sabía el flujo ni la siguiente acción.
- U2. Nombres técnicos (`scan_directory`, `BUDGET_EXCEEDED`) como texto principal.
- U3. La propuesta de la IA (modo asistido) dejaba el botón de confirmar escondido bajo formularios: «el prompt se queda ahí».
- U4. Límites de ronda invisibles; el rechazo solo decía un código.
- U5. El Azul tenía el mismo formulario de prompts que el Rojo; no había panorama de seguridad.
- U6. Sin resumen final ni línea de tiempo; vista de espectador mínima.
- U7. Credenciales siempre desplegadas, ocupando la pantalla.
- U8. Mensaje de Ollama apagado en términos de socket (`WinError 10061`).

### Equilibrio
- B1. **NPC infalibles:** todo correo malicioso a un empleado sin jugador tenía éxito garantizado → la fase de credenciales no tenía estrategia.
- B2. **Atajo de `empleados`:** extraer esa tabla comprometía **todas** las credenciales (cascada), eliminando el resto de fases. Además la tabla extraída contenía `credencial_ficticia` en claro.
- B3. La puntuación de sospecha no existía; el Azul no tenía forma de priorizar.

### Funciona correctamente (se conserva)
Motor autoritativo con pipeline de validación, eventos con visibilidad por rol, presupuestos, bloqueo e inicio manual, votación con decisor, solicitudes misteriosas, presencia, descargas, W1/W2, anti-SSRF, IA que propone y humanos que deciden.

## 3. Cambios propuestos (y estado)
| # | Cambio | Estado |
|---|---|---|
| 1 | Sistema de diseño (`ui/nova/ds.css`) y tablero de 3 zonas | Hecho |
| 2 | Misión guiada, «Hacer siguiente paso» (solo prepara), «¿Qué hago ahora?» | Hecho |
| 3 | Credenciales plegables, 6 estados con nombre de jugador | Hecho |
| 4 | Presupuesto visible y errores explicados | Hecho |
| 5 | Tarjeta de propuesta de IA (Ejecutar / Editar / Descartar) y estado de Ollama | Hecho |
| 6 | Centro de monitoreo Azul con puntuación determinista 0–100 | Hecho |
| 7 | Solicitudes con consecuencia de cada decisión | Hecho |
| 8 | NPC por dificultad, tipo de correo, preparación, señales y defensas | Hecho |
| 9 | `empleados` sin cascada; sin secretos en la tabla extraída | Hecho |
| 10 | Modo práctica de 5 min | Hecho |
| 11 | Resumen final con línea de tiempo por fuente; vista de espectador | Hecho |
| 12 | Modalidad SOC como opción independiente | **No hecho** (fuera de alcance; B5 conserva identidades empresariales) |

## 4. Riesgos de regresión (y cómo se cubrieron)
- Cambiar el clic de NPC afecta pruebas que daban por hecha la exposición: las pruebas de motor fijan `click_prob_unconnected=1.0` salvo las de comportamiento NPC.
- Quitar la cascada de `empleados` cambió dos pruebas (documentado en `GAMEPLAY_BALANCE_REPORT.md`).
- El rediseño movió elementos: se mantuvieron todos los `id` y se adaptaron selectores de e2e (texto «Validada», «Revocada», «Ejecutar»).
- El nuevo e2e `e2e/test_nova_ux.py` (28 comprobaciones) ejerce los controles nuevos contra el backend real.
