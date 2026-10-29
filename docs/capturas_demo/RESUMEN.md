# Prueba de extremo a extremo — partida Rojo vs Azul

Generado por `e2e/demo_partida.py` el 2026-10-29T11:02:06-06:00 en 17 s, con un servidor y una BD temporales (Chromium headless, 1366×768, 4 navegadores aislados).

**Resultado: 69/69 comprobaciones correctas.**

## 1. Preparación: cada participante entra con su nombre, entra un espectador y el árbitro inicia la partida

- Cada vista se une con un nombre visible (POST /api/sesion); la General, además, con el código de árbitro.
- Reloj en cada vista: ⏱ 05:00 | ⏱ 05:00 | ⏱ 05:00 | ⏱ 05:00
- ✅ general tiene su sesión y su nombre en la cabecera: esperado `True`, observado `True`
- ✅ rojo tiene su sesión y su nombre en la cabecera: esperado `True`, observado `True`
- ✅ azul tiene su sesión y su nombre en la cabecera: esperado `True`, observado `True`
- ✅ todas las vistas ven la partida en preparación: esperado `['PREPARACIÓN', 'PREPARACIÓN', 'PREPARACIÓN', 'PREPARACIÓN']`, observado `['PREPARACIÓN', 'PREPARACIÓN', 'PREPARACIÓN', 'PREPARACIÓN']`
- ✅ antes de iniciar, Rojo no puede enviar (409): esperado `True`, observado `True`
- ✅ al iniciar, las 4 vistas muestran la cuenta atrás: esperado `True`, observado `True`
- ✅ todas cuentan lo mismo (±2 s, el reloj lo manda el servidor): esperado `True`, observado `True`
- ✅ el espectador no tiene token ni botones de acción: esperado `True`, observado `True`
- ✅ marcador inicial en General: esperado `{'riesgo': 0, 'rojo': 0, 'azul': 0}`, observado `{'riesgo': 0, 'rojo': 0, 'azul': 0}`

![01_general_preparacion.jpg](01_general_preparacion.jpg)
![02_general_inicio.jpg](02_general_inicio.jpg)
![03_rojo_inicio.jpg](03_rojo_inicio.jpg)
![04_azul_inicio.jpg](04_azul_inicio.jpg)

## 2. Rojo envía 3 correos (uno sin adjunto y dos con PDF)

- Avisos: ✓ Correo enviado a ana.perez: «Acción requerida: verificación de la cuenta de ana.perez» | ✓ Correo enviado a ana.perez: «Actualización de tu recibo de nómina (29/10/2026)» | ✓ Correo enviado a ana.perez: «Tu paquete no pudo ser entregado»
- ✅ los 3 envíos se confirman: esperado `3`, observado `3`
- ✅ el buzón de Azul se actualiza solo por SSE: esperado `3`, observado `3`

![05_rojo_envia_correos.jpg](05_rojo_envia_correos.jpg)

## 3a. Azul abre su buzón y lee un correo

- ✅ Azul ve los 3 correos: esperado `3`, observado `3`
- ✅ dos traen PDF adjunto: esperado `2`, observado `2`
- ✅ el detalle muestra el enlace local: esperado `True`, observado `True`

![06_azul_lee_correo.jpg](06_azul_lee_correo.jpg)

## 3b. El «empleado distraído» hace clic en el enlace del correo de paquetería

- Marcador tras el clic: {'riesgo': 15, 'rojo': 10, 'azul': 0, 'clics': 1, 'contenciones': 0, 'reportes': 0, 'pdf': 0}
- ✅ se abre la página de enlace de prueba: esperado `True`, observado `True`
- ✅ General: clic contado: esperado `1`, observado `1`
- ✅ riesgo sube +15: esperado `15`, observado `15`
- ✅ Rojo gana +10 (enlace sin contener): esperado `10`, observado `10`

![07_enlace_de_prueba.jpg](07_enlace_de_prueba.jpg)
![08_general_tras_clic.jpg](08_general_tras_clic.jpg)

## 3c. Azul reporta el correo de soporte técnico

- Aviso: ✓ Correo reportado · regla -10 → riesgo de la partida 5/100 · misión completada: «Reportar un correo sospechoso» +10 pts
- ✅ misión «Reportar un correo sospechoso» completada: esperado `True`, observado `True`
- ✅ riesgo baja −10: esperado `5`, observado `5`
- ✅ Azul suma 10: esperado `10`, observado `10`


## 3d. Azul contiene el enlace clicado

- Aviso: ✓ Enlace contenido · regla -15 → riesgo de la partida 0/100 · misión completada: «Contener un enlace clicado» +15 pts
- ✅ aparece el botón Contener (el enlace tuvo clic): esperado `True`, observado `True`
- ✅ riesgo baja (5 − 15, acotado a 0): esperado `0`, observado `0`
- ✅ Rojo pierde los 10 del enlace: esperado `0`, observado `0`
- ✅ Azul suma 15 (25): esperado `25`, observado `25`

![09_azul_contiene_enlace.jpg](09_azul_contiene_enlace.jpg)

## 3e. Azul verifica el remitente de nómina, inspecciona el enlace y previsualiza el PDF

- Verificación: ⚠ El remitente IMITA al dominio oficial | Dominio que IMITA al oficial: «cybershieId.invalid» se parece a «cybershield.invalid» pero no es el mismo (caracteres cambiados o palabras añadidas). | Indicadores: El dominio usa una «I» mayúscula en lugar de «l» (cybershieId) · Adjunto de nómina no solicitado · Enlace para un «acuse» que no hace falta
- Aviso: ✓ PDF reportado · regla -10 → riesgo de la partida 0/100
- ✅ detecta que el remitente IMITA al dominio oficial: esperado `True`, observado `True`
- ✅ inspeccionar muestra que el enlace no va a donde dice: esperado `True`, observado `True`
- ✅ inspeccionar no cuenta como clic (sin «ENLACE CLICADO»): esperado `0`, observado `0`
- ✅ se abre el visor seguro: esperado `True`, observado `True`
- ✅ el visor muestra el texto del propio PDF: esperado `True`, observado `True`
- ✅ el visor muestra el SHA-256 real del archivo: esperado `True`, observado `True`
- ✅ Esc cierra el visor: esperado `False`, observado `False`
- ✅ no se descargó nada al equipo: esperado `0`, observado `0`
- ✅ Rojo gana +5 (PDF abierto sin reportar): esperado `5`, observado `5`
- ✅ Azul: +5 por verificar el remitente y +10 por el documento = 40: esperado `40`, observado `40`
- ✅ Rojo pierde los 5 del PDF: esperado `0`, observado `0`
- ✅ riesgo sigue en 0 (no baja de 0): esperado `0`, observado `0`
- ✅ el aviso dice el riesgo real de la partida, no solo el −10 de la regla: esperado `True`, observado `True`
- ✅ la lista del buzón marca el PDF como reportado: esperado `1`, observado `1`

![10_azul_visor_pdf.jpg](10_azul_visor_pdf.jpg)
![11_general_pdf_abierto.jpg](11_general_pdf_abierto.jpg)
![12_azul_reporta_pdf.jpg](12_azul_reporta_pdf.jpg)

## 3f. Carpetas y aislamiento del adjunto

- Aviso: ✓ 🧪 Adjunto aislado · regla -5 → riesgo de la partida 0/100
- ✅ el correo reportado está en «Sospechosos»: esperado `1`, observado `1`
- ✅ tras aislarlo, el adjunto ya no se puede previsualizar: esperado `True`, observado `True`
- ✅ aislar no cambia el marcador (Rojo 0, Azul 40): esperado `(0, 40)`, observado `(0, 40)`
- ✅ Rojo ve en su campaña 1 clic y 1 adjunto abierto (sin saber si se leyó o reportó): esperado `True`, observado `True`

![13_rojo_seguimiento_campana.jpg](13_rojo_seguimiento_campana.jpg)

## 3g. Credencial robada: el empleado entrega su contraseña en la página falsa de soporte

- ✅ la página imita un inicio de sesión sin campos para escribir: esperado `(True, 0)`, observado `(True, 0)`
- ✅ la página explica que la credencial queda comprometida: esperado `True`, observado `True`
- ✅ Rojo: +10 por el nuevo clic y +15 por la credencial = 25: esperado `25`, observado `25`
- ✅ riesgo: +15 (clic) +20 (credencial) = 35: esperado `35`, observado `35`
- ✅ Azul recibe el aviso de credencial comprometida: esperado `True`, observado `True`

![14_pagina_falsa_credencial.jpg](14_pagina_falsa_credencial.jpg)

## 3h. Azul abre un incidente desde el correo, revoca la credencial y lo resuelve

- Aviso: 🚨 Incidente #1 abierto · misión completada: «Abrir un incidente de seguridad» +10 pts
- Aviso: ✓ Credencial revocada · regla -15 → riesgo de la partida 20/100 · misión completada: «Revocar una credencial comprometida» +20 pts
- Aviso: Aún no se puede resolver: el enlace del correo se clicó y aún no está contenido.
- Aviso: ✓ Incidente resuelto · regla -5 → riesgo de la partida 0/100 · misión completada: «Resolver el incidente» +15 pts
- ✅ el formulario trae el correo ya elegido: esperado `True`, observado `True`
- ✅ abrir el incidente completa su misión: esperado `True`, observado `True`
- ✅ la credencial aparece COMPROMETIDA con botón para revocarla: esperado `True`, observado `True`
- ✅ revocar completa su misión (desbloqueada por el incidente): esperado `True`, observado `True`
- ✅ Rojo pierde los 15 de la credencial (le quedan los 10 del clic): esperado `10`, observado `10`
- ✅ no deja resolver con el enlace clicado sin contener, y explica por qué: esperado `True`, observado `True`
- ✅ el enlace de soporte queda contenido: esperado `True`, observado `True`
- ✅ la lista ya no muestra nada pendiente para resolver: esperado `True`, observado `True`
- ✅ el texto de resolución escrito antes se conserva al redibujar: esperado `Credencial revocada; enlace de soporte contenido.`, observado `Credencial revocada; enlace de soporte contenido.`
- ✅ resolver el incidente completa su misión: esperado `True`, observado `True`
- ✅ marcador: Rojo 0, Azul 85 (40 + 10 incidente + 20 revocar + 15 resolver), riesgo 0: esperado `(0, 85, 0)`, observado `(0, 85, 0)`

![15_azul_incidente_credencial.jpg](15_azul_incidente_credencial.jpg)
![16_azul_incidente_resuelto.jpg](16_azul_incidente_resuelto.jpg)

## 4. Verificación: misiones, marcador en General y Espectador

- Evidencia de «Revocar»: Completada por Beto Azul · 29/10/2026 11:02 · evidencia: credencial:ana.perez
- Marcador final antes de cerrar: {'riesgo': 0, 'rojo': 0, 'azul': 85, 'clics': 2, 'contenciones': 2, 'reportes': 2, 'pdf': 1}
- Líneas de auditoría en General: 43
- ✅ misiones completadas: todas salvo la manual: esperado `[True, True, False, True, True, True, True, True]`, observado `[True, True, False, True, True, True, True, True]`
- ✅ cada misión dice quién la completó y con qué evidencia: esperado `True`, observado `True`
- ✅ General y Espectador ven el mismo marcador: esperado `{'riesgo': 0, 'rojo': 0, 'azul': 85, 'clics': 2, 'contenciones': 2, 'reportes': 2, 'pdf': 1}`, observado `{'riesgo': 0, 'rojo': 0, 'azul': 85, 'clics': 2, 'contenciones': 2, 'reportes': 2, 'pdf': 1}`
- ✅ la auditoría de General registró la partida: esperado `True`, observado `True`

![17_azul_misiones.jpg](17_azul_misiones.jpg)
![18_espectador_marcador.jpg](18_espectador_marcador.jpg)
![19_general_auditoria_maximizada.jpg](19_general_auditoria_maximizada.jpg)

## 5. General finaliza la partida y se muestra el resultado

- ✅ General ve la pantalla de resultado: esperado `True`, observado `True`
- ✅ ganador: esperado `GANA EL EQUIPO AZUL`, observado `GANA EL EQUIPO AZUL`
- ✅ puntajes finales (Rojo — Azul): esperado `('0', '85')`, observado `('0', '85')`
- ✅ el Espectador también ve el resultado: esperado `True`, observado `True`
- ✅ tras finalizar, Rojo ya no puede enviar (409): esperado `True`, observado `True`
- ✅ sin errores de consola inesperados en ninguna vista: esperado `[]`, observado `[]`

![20_general_resultado.jpg](20_general_resultado.jpg)
![21_espectador_resultado.jpg](21_espectador_resultado.jpg)
![22_rojo_tras_finalizar.jpg](22_rojo_tras_finalizar.jpg)

## Eventos escritos en eventos.jsonl (formato para Wazuh)

- `archivo_aislado`: 1
- `clic_enlace`: 2
- `correo_abierto`: 3
- `correo_recibido`: 3
- `correo_reportado`: 1
- `credencial_comprometida`: 1
- `credencial_revocada`: 1
- `enlace_contenido`: 2
- `enlace_inspeccionado`: 1
- `incidente_abierto`: 1
- `incidente_actualizado`: 1
- `incidente_resuelto`: 1
- `mision_completada`: 7
- `partida_finalizada`: 1
- `pdf_abierto`: 1
- `pdf_reportado`: 1
- `remitente_verificado`: 1

## Comportamientos inesperados

- (esperado) Error de consola (rojo, paso 1): `Failed to load resource: the server responded with a status of 409 (Conflict)` — es una acción rechazada a propósito (enviar antes de iniciar o tras finalizar, resolver un incidente con la amenaza activa)
- (esperado) Error de consola (azul, paso 10): `Failed to load resource: the server responded with a status of 409 (Conflict)` — es una acción rechazada a propósito (enviar antes de iniciar o tras finalizar, resolver un incidente con la amenaza activa)
- (esperado) Error de consola (rojo, paso 12): `Failed to load resource: the server responded with a status of 409 (Conflict)` — es una acción rechazada a propósito (enviar antes de iniciar o tras finalizar, resolver un incidente con la amenaza activa)
- Ninguno: todas las comprobaciones pasaron y no hubo errores de consola inesperados.
