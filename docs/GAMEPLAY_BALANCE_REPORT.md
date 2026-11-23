# GAMEPLAY_BALANCE_REPORT — equilibrio de las rutas de victoria

## Rutas de victoria (sin cambios)
- **W1** — extraer `reportes_financieros` con la identidad de Finanzas (EMP-05).
- **W2** — elevación aprobada por el Azul (válida 120 s) + `export_database` (8 tablas).
- Condiciones del Azul y empate intactas. No se tocó `_win_rojo` ni `_evaluar_final`.

## Cambios de mecánica (documentados antes de implementarse)

### 1. NPC ya no son infalibles
`click_prob_unconnected` pasa de `1.0` a `None`: si es `None`, la probabilidad se calcula por regla:

`p = dificultad + tipo de correo + contexto + preparación − señales − defensas`, acotada a [0,05 ; 0,95]

| Factor | Valor |
|---|---|
| Dificultad base | fácil 0,80 · normal 0,55 · difícil 0,25 |
| Tipo de correo | aviso_soporte +0,05 · reporte_urgente +0,10 (+0,15 si el destinatario es de Finanzas/Administración) |
| Preparación del empleado | EMP-04 +0,15 (confiado) · EMP-03 −0,10 · EMP-05 −0,05 · EMP-06 −0,15 |
| Señales sospechosas | −0,05 por cada palabra de presión (urgente, verifica, contraseña…), máx. −0,15 |
| Defensas del Azul | −0,08 por correo del Rojo reportado o enlace neutralizado, máx. −0,32 |

- Un correo **reportado/neutralizado antes** de que el NPC lo lea nunca engaña (`email.ignored`).
- Si el empleado tiene jugador, decide el humano (se comprueba al vencer el retardo, no al enviar).
- Cada decisión queda en `npc.decision` (probabilidad y factores) visible para Azul y admin, **no** para el Rojo; el Rojo solo ve `email.ignored` («el empleado desconfió»).
- El administrador puede fijar la dificultad, o un valor numérico fijo (`click_prob_unconnected`) para pruebas deterministas.

**Medido** (100 partidas sembradas por celda, 1 clic = enlace pulsado):

| Dificultad | EMP-02 | EMP-04 (débil) | EMP-06 (director) | reporte→EMP-05 | EMP-02 tras 3 reportes del Azul |
|---|---|---|---|---|---|
| Fácil | 81 % | 95 % | 62 % | 95 % | 52 % |
| Normal | 50 % | 68 % | 36 % | 72 % | 29 % |
| Difícil | 22 % | 36 % | 9 % | 41 % | 7 % |

Resultado: el Rojo ya necesita varios correos y buena elección de objetivo; el Azul puede reducir la tasa reportando.

### 2. `empleados` sin cascada
- Antes: extraer `empleados` comprometía **las 6** credenciales.
- Ahora: identifica a todos los empleados (datos de personas) y expone **solo la cuenta con credencial débil** (EMP-04, que solo accede a productos/inventario). El resto de credenciales hay que ganarlas con correo o adivinación.
- La tabla extraída guarda `credencial_ficticia = "[protegida]"`: los datos de empleados se distinguen de los secretos de autenticación.
- Se mantiene la alerta CRÍTICA al extraer una tabla protegida.

### 3. Sin cambio
Presupuestos, cooldowns, bloqueos, near-miss, límites de correos y reconocimientos, duración de la elevación.

## Lo que NO se midió
- No se midió el porcentaje real de victorias del Rojo contra un Azul humano que reaccione; solo la tasa de clic de los NPC. Una campaña con jugadores reales en red local (criterio 33) sigue pendiente.
- La dificultad «normal» es un punto de partida razonable, no un valor calibrado con partidas humanas.

## Pruebas asociadas
`src/lab/test_nova.py` (99): dificultad fácil > normal > difícil, el reporte financiero engaña más a Finanzas que a Dirección, decisiones visibles solo para Azul/admin, reportado ⇒ ignorado, defensas reducen la probabilidad, sin cascada y sin secretos en `empleados`.
