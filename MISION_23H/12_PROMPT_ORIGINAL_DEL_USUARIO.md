# MISIÓN AUTÓNOMA INTEGRAL — CYBERSHIELD AI DEFENSE
## Auditoría de combates, evaluación de inteligencia artificial, reparación funcional y cierre de pendientes

**ROL:** Actúa como arquitecto de software principal, ingeniero de IA, especialista en simulación adversarial, ingeniero de pruebas, auditor de calidad y responsable técnico de CyberShield AI Defense.

**AUTORIZACIÓN:** Quedas autorizado para ejecutar autónomamente todas las actividades técnicas necesarias dentro del repositorio y entorno local del proyecto. No necesitas solicitar confirmación humana para analizar, planificar, modificar, implementar, corregir, probar, integrar, documentar o realizar commits locales.

No detengas el trabajo para solicitar aprobación de cada fase. Toma decisiones técnicas razonables, documenta tus decisiones y continúa hasta completar todos los objetivos posibles.

La prioridad es conseguir un CyberShield funcional, coherente, reproducible y científicamente evaluable. No se busca aparentar que está terminado: se busca demostrar que funciona.

---

# 1. CONTEXTO Y OBJETIVO ORIGINAL

CyberShield AI Defense es un laboratorio educativo de ciberseguridad que simula enfrentamientos entre dos equipos de inteligencia artificial:

- **Equipo Rojo:** representa al atacante. Debe intentar alcanzar objetivos definidos dentro de escenarios empresariales ficticios.
- **Equipo Azul:** representa al defensor. Debe detectar amenazas, analizar situaciones, tomar decisiones y ejecutar acciones defensivas.
- **Motor de simulación:** valida las acciones, aplica permisos, modifica el estado del escenario y determina las consecuencias.
- **Harness:** controla y registra la ejecución de los modelos, los presupuestos y las condiciones de las inferencias.
- **Wazuh:** aporta observabilidad y detección cuando existe una integración real disponible.
- **Espectadores:** pueden observar las partidas y consultar sus eventos.
- **Administrador:** configura partidas, escenarios, modelos, reglas y condiciones de ejecución.

La arquitectura fundamental debe respetarse:

**La IA propone → el motor valida → los permisos autorizan → el repositorio ejecuta → la auditoría registra.**

Ningún modelo debe poder declararse vencedor por su propia respuesta textual.

La victoria debe determinarse mediante el estado verificable del escenario y los objetivos definidos antes de comenzar la partida.

---

# 2. AUTONOMÍA Y REGLAS DE EJECUCIÓN

Debes trabajar de principio a fin sin esperar instrucciones humanas entre fases.

Puedes:

- Inspeccionar todo el repositorio.
- Revisar código, documentación, historial Git, ramas y commits.
- Ejecutar pruebas unitarias, integración, regresión y extremo a extremo.
- Ejecutar campañas experimentales locales.
- Modificar código y arquitectura cuando sea necesario.
- Crear módulos, servicios, scripts, pruebas y documentación.
- Corregir errores encontrados.
- Integrar módulos que actualmente existan de forma aislada.
- Mejorar interfaces y experiencia de usuario.
- Optimizar rendimiento.
- Crear commits locales independientes y descriptivos.
- Reanudar campañas incompletas.
- Actualizar los informes y el progreso real del proyecto.

No puedes:

1. Eliminar registros históricos, campañas anteriores, experimentos o resultados válidos.
2. Modificar resultados experimentales para mejorar porcentajes.
3. Cambiar retrospectivamente los criterios de evaluación.
4. Presentar simulaciones como integraciones reales.
5. inventar resultados de Ollama o Wazuh.
6. Declarar victorias sin evidencia del motor.
7. Desactivar controles de seguridad para conseguir que una campaña funcione.
8. Ejecutar pruebas ofensivas contra sistemas, redes, cuentas o servicios reales.
9. Descargar modelos o dependencias pesadas sin necesidad; prioriza los recursos locales disponibles.
10. Hacer push, despliegues externos, compras, cambios de permisos externos o acciones irreversibles.
11. Destruir bases de datos o sobrescribir archivos históricos.

Si una actividad necesita una infraestructura externa no disponible, implementa todo lo que pueda probarse localmente, deja una prueba de integración condicional y documenta exactamente qué falta.

No confundas autonomía con ausencia de controles: conserva los límites de seguridad y los mecanismos de autorización.

---

# 3. FASE 0 — INVENTARIO Y RECUPERACIÓN DEL ESTADO

Antes de modificar nada:

1. Identifica la rama activa y el commit actual.
2. Comprueba si el árbol de trabajo está limpio.
3. Identifica las ramas locales y remotas disponibles.
4. Comprueba el estado de `origin/main` sin modificarlo.
5. Localiza los últimos commits relacionados con las fases implementadas.
6. Revisa los informes históricos.
7. Revisa `PROGRESO.md`.
8. Localiza las campañas del defensor y del atacante.
9. Inspecciona los registros y resultados parciales.
10. Identifica procesos de campañas que continúen ejecutándose.
11. Revisa los scripts de reanudación.
12. Comprueba los modelos Ollama realmente instalados.

Documenta:

- Estado inicial del repositorio.
- Funcionalidades existentes.
- Funcionalidades incompletas.
- Funcionalidades desconectadas.
- Pruebas disponibles.
- Problemas reproducibles.
- Deudas técnicas.
- Resultados experimentales existentes.

No reimplementes módulos que ya funcionen correctamente.

Conserva los informes anteriores y añade nuevos resultados como versiones o secciones adicionales.

---

# 4. FASE 1 — AUDITORÍA DEL SISTEMA DE COMBATE

Realiza una revisión integral del ciclo de vida de una partida.

Verifica que una partida pueda:

1. Crearse desde el administrador.
2. Seleccionar modelos diferentes para Rojo y Azul.
3. Configurar un escenario.
4. Definir objetivos de ataque y defensa.
5. Inicializar un estado consistente.
6. Ejecutar turnos.
7. Recibir decisiones de ambos modelos.
8. Validar las decisiones.
9. Ejecutar las acciones autorizadas.
10. Actualizar el escenario.
11. Generar eventos.
12. Registrar los resultados.
13. Finalizar correctamente.
14. Determinar un ganador.
15. Mostrar la cronología.
16. Conservar el historial.

Investiga especialmente:

- Turnos que no se ejecutan.
- Acciones que se ejecutan sin validación.
- Modelos que generan respuestas vacías.
- Respuestas que no se convierten en acciones.
- Acciones duplicadas.
- Eventos perdidos.
- Estados inconsistentes.
- Misiones que nunca terminan.
- Partidas que quedan bloqueadas.
- Errores de sincronización.
- Resultados que no coinciden con las consecuencias.
- Diferencias entre la partida real y la información mostrada en la interfaz.

Comprueba que el estado del escenario sea la fuente de verdad para las consecuencias.

Corrige todos los defectos reproducibles.

---

# 5. FASE 2 — SISTEMA FORMAL DE VICTORIA Y DERROTA

Este apartado es prioritario.

Actualmente no basta con saber si un modelo respondió correctamente. Debe existir una definición formal y verificable de victoria.

Diseña o mejora un sistema de objetivos basado en condiciones observables.

## 5.1 Objetivos del Equipo Rojo

El Equipo Rojo debe disponer de objetivos explícitos, por ejemplo:

- Conseguir acceso no autorizado a un recurso ficticio.
- Conseguir modificar un dato de prueba protegido.
- Provocar una alteración controlada del escenario.
- Conseguir que una acción prohibida supere indebidamente las validaciones.
- Alcanzar un objetivo empresarial ficticio definido por la misión.

Estos objetivos deben implementarse exclusivamente dentro del simulador.

No basta con que el modelo diga que ha conseguido acceder a un recurso.

Debe existir evidencia verificable de que el motor registró el cambio correspondiente.

## 5.2 Objetivos del Equipo Azul

El defensor debe:

- Detectar las amenazas.
- Distinguir acciones legítimas y maliciosas.
- Evitar modificaciones no autorizadas.
- Solicitar autorización cuando corresponda.
- Bloquear las acciones prohibidas.
- Contener incidentes.
- Recuperar el estado del escenario cuando proceda.
- Completar misiones defensivas.
- Mantener la continuidad de operaciones legítimas.

No se debe considerar una buena defensa rechazar absolutamente todas las acciones.

## 5.3 Condiciones de victoria

Implementa condiciones deterministas:

**Victoria Roja:**
- Se alcanza un objetivo ofensivo previamente definido.
- El estado del escenario confirma el efecto.
- El resultado supera las validaciones del motor.
- Existe un registro de auditoría verificable.

**Victoria Azul:**
- Evita los objetivos ofensivos definidos.
- Completa las condiciones defensivas necesarias.
- Conserva la integridad de los recursos protegidos.
- Mantiene la funcionalidad legítima del escenario cuando corresponde.

**Empate:**
- Ningún equipo alcanza su objetivo dentro del límite establecido.
- Ambos cumplen parcialmente sus objetivos sin una condición de victoria definitiva.

**Victoria por objetivos o tiempo:**
- Define claramente cómo se resuelven los casos en los que uno de los equipos cumple sus objetivos antes del límite.

Las condiciones de victoria deben ser configurables por escenario, pero no modificables retrospectivamente durante una partida.

Nunca permitas que una simple respuesta textual de la IA determine el ganador.

---

# 6. FASE 3 — EVALUACIÓN REAL DE LOS COMBATES

Construye un sistema automatizado de evaluación de partidas.

Debe ejecutar múltiples escenarios y medir si los equipos realmente funcionan.

## 6.1 Matriz de enfrentamientos

Evalúa, cuando los modelos estén instalados y sean compatibles:

- Modelo Rojo A contra Azul A.
- Modelo Rojo A contra Azul B.
- Modelo Rojo B contra Azul A.
- Modelo Rojo B contra Azul B.
- Diferentes técnicas de prompting.
- Configuración base.
- Configuración con ejemplos.
- Configuración con recuperación documental.
- Configuración con Harness.
- Escenarios sencillos.
- Escenarios intermedios.
- Escenarios complejos.

No inventes disponibilidad de modelos.

Identifica qué modelos existen realmente en Ollama y adapta la matriz a ellos.

Mantén constantes las condiciones de comparación cuando quieras atribuir diferencias a una sola variable.

## 6.2 Evaluación del Equipo Rojo

Mide:

- Porcentaje de objetivos alcanzados.
- Número de acciones válidas.
- Número de acciones rechazadas.
- Número de acciones bloqueadas.
- Capacidad para adaptar su estrategia.
- Repetición de intentos fallidos.
- Capacidad de aprovechar las reglas del escenario.
- Tiempo medio por turno.
- Tokens utilizados.
- Respuestas vacías.
- Errores de ejecución.

Distingue:

1. Intento de ataque.
2. Acción aceptada por el motor.
3. Efecto producido.
4. Objetivo realmente alcanzado.

No confundas estas cuatro etapas.

## 6.3 Evaluación del Equipo Azul

Mide:

- Detección de amenazas.
- Bloqueos correctos.
- Falsos positivos.
- Falsos negativos.
- Autorizaciones correctas.
- Rechazos incorrectos de solicitudes legítimas.
- Solicitudes de autorización pertinentes.
- Tiempo de respuesta.
- Acciones de contención.
- Misiones completadas.
- Integridad del escenario.
- Recuperación después de un incidente.

Evalúa la capacidad de discriminar, no solamente la capacidad de rechazar.

## 6.4 Métricas de combate

Como mínimo, genera:

- Tasa de éxito del atacante.
- Tasa de prevención del defensor.
- Tasa de detección.
- Precisión.
- Recall.
- F1.
- Falsos positivos.
- Falsos negativos.
- Tasa de acciones legítimas permitidas correctamente.
- Tasa de acciones maliciosas bloqueadas.
- Porcentaje de misiones completadas.
- Duración media de combate.
- Porcentaje de partidas inconclusas.

Define el denominador de cada métrica y no mezcles observaciones inválidas con resultados válidos.

Incorpora intervalos de confianza adecuados y considera la dependencia entre rondas de una misma sesión.

Cuando existan comparaciones múltiples, documenta la corrección estadística aplicada.

Publica siempre una línea base trivial cuando sea pertinente. Una estrategia constante como RECHAZAR debe permitir identificar si una métrica está premiando un comportamiento degenerado.

---

# 7. FASE 4 — CAMPAÑAS DEL ATACANTE PENDIENTES

Revisa el estado de `campana_atacante.py` y las campañas pendientes.

Investiga el error anterior:

`Launch attacker campaigns in background: exit code 4`

No asumas su causa.

Determina si:

- El proceso nunca comenzó.
- El lanzador falló.
- La configuración era inválida.
- Existían dependencias ausentes.
- Había conflictos de procesos.
- Existían resultados parciales.
- La campaña comenzó y terminó de forma inesperada.

Corrige la causa.

Primero realiza una prueba corta y verifica que los registros sean correctos.

Después ejecuta las campañas completas.

Conserva las condiciones originales siempre que sean válidas.

Si detectas un defecto metodológico, documenta el problema y crea una nueva versión del experimento sin alterar los resultados anteriores.

Las campañas deben poder:

- Reanudarse.
- Guardar progreso.
- Evitar duplicaciones.
- Recuperarse de interrupciones.
- Registrar fallos.
- Identificar observaciones válidas.
- Producir resultados reproducibles.

No declares cerrada la evaluación del atacante hasta que exista evidencia suficiente.

---

# 8. FASE 5 — DETECTAR Y CORREGIR COMPORTAMIENTOS DEGENERADOS

Busca sistemáticamente comportamientos como:

- RECHAZAR en todas las situaciones.
- PERMITIR en todas las situaciones.
- SOLICITAR_AUTORIZACION permanentemente.
- Respuestas idénticas sin importar el escenario.
- Ignorar el historial de la partida.
- Ignorar las consecuencias de turnos anteriores.
- Repetir acciones que ya fracasaron.
- Responder sin ejecutar ninguna acción.
- Declarar victorias inexistentes.
- Generar razonamientos que no coinciden con las acciones.
- Utilizar siempre la misma estrategia.
- No reconocer los objetivos de la misión.

Crea pruebas automatizadas para detectar estos comportamientos.

Incluye una evaluación de sensibilidad:

Si cambia la entrada de manera relevante, ¿cambia la decisión del modelo cuando debería hacerlo?

Incluye una evaluación de consistencia:

Si el escenario se mantiene igual, ¿el modelo conserva un comportamiento razonablemente coherente?

No exijas respuestas idénticas cuando exista variabilidad legítima de generación.

La evaluación debe distinguir entre:

- Fallo del modelo.
- Fallo del prompt.
- Fallo del motor.
- Fallo de integración.
- Fallo del escenario.
- Fallo de medición.

Corrige las causas identificadas sin manipular las métricas.

---

# 9. FASE 6 — INTEGRACIÓN REAL DEL HARNESS

Comprueba que el Harness no sea únicamente un módulo independiente.

Debe controlar las partidas reales.

Verifica:

- Presupuesto por ronda.
- Límite de llamadas.
- Límite de tokens.
- Tiempo máximo.
- Cancelación.
- Detección de respuestas vacías.
- Detección de llamadas repetidas.
- Registro de errores.
- Registro de consumo.
- Identificación del modelo.
- Identificación de la técnica utilizada.
- Eventos enviados a la cronología.

El Harness debe ser capaz de detener una ejecución que exceda los límites.

Una acción denegada por permisos no debe provocar reintentos infinitos.

Comprueba que el uso del Harness no altere los resultados de forma inesperada.

Separa claramente la mejora de trazabilidad de la mejora de capacidad del modelo.

---

# 10. FASE 7 — INTEGRACIÓN DE MISIONES Y ESCENARIOS

Verifica que las misiones tengan estados coherentes:

- pendiente
- en_progreso
- bloqueada
- completada
- cancelada
- vencida

Asegura que las transiciones sean válidas.

Cada misión debe incluir:

- Identificador.
- Equipo responsable.
- Objetivo.
- Condiciones de inicio.
- Condiciones de finalización.
- Estado.
- Evidencia de cumplimiento.
- Consecuencias.
- Registro de auditoría.

Comprueba que los escenarios tengan recursos, permisos, vulnerabilidades ficticias y objetivos coherentes.

No debe haber misiones imposibles de completar ni objetivos que dependan de eventos que nunca pueden producirse.

Integra las familias de escenarios disponibles y documenta las que todavía no estén implementadas.

---

# 11. FASE 8 — INTEGRACIÓN DE WAZUH Y OBSERVABILIDAD

Audita la integración existente.

Distingue expresamente:

1. Wazuh real.
2. Wazuh simulado.
3. Wazuh desconectado.
4. Wazuh con errores.

Cuando exista una instancia real disponible:

- Comprueba la conexión.
- Consulta alertas.
- Identifica eventos.
- Correlaciona alertas con las partidas.
- Conserva identificadores y marcas temporales.
- Verifica que las alertas no se dupliquen.

Cuando no exista una instancia real:

- Mantén el modo simulado claramente identificado.
- Prueba los contratos mediante datos ficticios.
- No inventes alertas reales.
- Deja documentada la integración pendiente.

Integra la observabilidad con:

- Harness.
- Motor de combate.
- Cronología.
- Misiones.
- Acciones de ambos equipos.
- Resultados de las partidas.

---

# 12. FASE 9 — SEGURIDAD Y CONTROL DE ACCESO

Audita:

- Roles de administrador.
- Equipo Rojo.
- Equipo Azul.
- Espectadores.
- Autenticación individual.
- Autorización de acciones.
- Gestión de sesiones.
- Protección de secretos.
- Configuración de TLS.
- Validación de entradas.
- Registro de auditoría.

El espectador debe ser exclusivamente de lectura.

El modelo Rojo no debe poder modificar directamente los permisos del Azul.

El modelo Azul no debe poder alterar los resultados históricos.

Ningún modelo debe acceder directamente a la base de datos fuera de los mecanismos autorizados.

Comprueba que las acciones críticas pasen por el motor.

Si la infraestructura no permite verificar TLS o autenticación real, documenta la limitación y no simules que está resuelta.

---

# 13. FASE 10 — INTERFAZ Y EXPERIENCIA DE COMBATE

Audita la interfaz de batalla y su coherencia con el panel administrativo.

El sistema debe permitir visualizar:

- Estado actual de la partida.
- Equipo Rojo y modelo seleccionado.
- Equipo Azul y modelo seleccionado.
- Objetivos de ambos equipos.
- Turno actual.
- Acciones ejecutadas.
- Acciones rechazadas.
- Estado de recursos.
- Misiones.
- Eventos.
- Alertas.
- Consecuencias.
- Cronología.
- Presupuesto consumido.
- Resultado final.

El combate debe ser comprensible visualmente.

Distingue estados:

- Pensando.
- Ejecutando.
- Acción aceptada.
- Acción rechazada.
- Amenaza detectada.
- Misión completada.
- Incidente contenido.
- Victoria.
- Derrota.
- Empate.
- Error técnico.

No muestres una victoria antes de que el motor la confirme.

Aplica el sistema de diseño del panel a la batalla sin destruir las funcionalidades existentes.

Verifica visualmente las pantallas principales y corrige errores de interacción.

---

# 14. FASE 11 — PRUEBAS AUTOMATIZADAS Y REGRESIÓN

Amplía la batería de pruebas.

Incluye:

**Pruebas unitarias**
- Motor.
- Permisos.
- Objetivos.
- Misiones.
- Harness.
- Métricas.
- Condiciones de victoria.

**Pruebas de integración**
- Ollama.
- Motor y repositorio.
- Harness y combate.
- Misiones y consecuencias.
- Wazuh cuando esté disponible.
- Persistencia.

**Pruebas extremo a extremo**
- Crear partida.
- Seleccionar modelos.
- Ejecutar combate.
- Observar turnos.
- Completar misiones.
- Determinar ganador.
- Consultar historial.

**Pruebas negativas**
- Modelo desconectado.
- Respuesta vacía.
- Tiempo agotado.
- Acción no autorizada.
- Misión inválida.
- Partida interrumpida.
- Evento duplicado.
- Presupuesto agotado.

**Pruebas de regresión**
Comprueba que las funcionalidades anteriores sigan funcionando.

No uses exclusivamente modelos falsos para afirmar que Ollama funciona.

Separa los resultados de pruebas simuladas de las pruebas con modelos reales.

Ejecuta las pruebas reales de manera controlada, sin hacer campañas extensas innecesarias.

---

# 15. FASE 12 — CORRECCIÓN AUTÓNOMA DE PENDIENTES

Construye una matriz de pendientes a partir de:

- Código fuente.
- Informes anteriores.
- PROGRESO.md.
- Issues documentados.
- Comentarios TODO/FIXME.
- Resultados experimentales.
- Pruebas fallidas.
- Funcionalidades implementadas pero desconectadas.

Clasifica cada pendiente:

- Crítico.
- Alto.
- Medio.
- Bajo.

Para cada pendiente:

1. Identifica el problema.
2. Determina su causa.
3. Diseña una solución.
4. Implementa la corrección.
5. Añade pruebas.
6. Ejecuta regresión.
7. Documenta el resultado.
8. Actualiza el estado.

No te limites a producir recomendaciones.

Si puedes corregir un problema localmente, corrígelo.

Si un pendiente depende de infraestructura externa, completa el trabajo local posible y documenta el bloqueo.

No dejes tareas pendientes simplemente porque no estaban incluidas en el plan anterior si afectan directamente al objetivo original del proyecto.

---

# 16. FASE 13 — EVALUACIÓN FINAL DEL PRODUCTO

Al completar las correcciones, realiza una evaluación integral.

Ejecuta partidas automatizadas con escenarios representativos y modelos reales disponibles.

El objetivo es demostrar que:

- El Rojo puede intentar alcanzar objetivos.
- El Azul puede detectar y responder.
- Ambos equipos producen decisiones contextualizadas.
- Las acciones pasan por validación.
- Las consecuencias se reflejan en el escenario.
- Las misiones funcionan.
- El Harness controla la ejecución.
- La cronología conserva los eventos.
- Los espectadores observan correctamente.
- El sistema determina victorias y derrotas.
- Los resultados se pueden auditar.

Incluye casos donde:

1. Gana el Equipo Rojo.
2. Gana el Equipo Azul.
3. Se produce un empate.
4. El atacante falla.
5. El defensor comete un falso positivo.
6. El defensor deja pasar una amenaza.
7. Se interrumpe una partida.
8. Se agota el presupuesto.
9. Un modelo no responde.

Estos casos pueden probarse con escenarios deterministas y modelos de prueba para verificar el motor, pero las conclusiones sobre capacidad de IA deben proceder de ejecuciones reales.

No fuerces resultados artificiales en las campañas de evaluación de modelos.

---

# 17. FASE 14 — PROGRESO Y CRITERIOS DE FINALIZACIÓN

Conserva la fórmula de avance y los pesos establecidos en la auditoría anterior.

No cambies los pesos para mejorar el porcentaje.

Utiliza los estados:

- 0: no implementado.
- 0,5: implementado parcialmente, sin integración o sin evidencia suficiente.
- 1: implementado, integrado y probado.

Calcula el porcentaje con la fórmula histórica.

Distingue:

- Avance de implementación.
- Avance de integración.
- Avance de pruebas.
- Calidad experimental de los modelos.
- Preparación para demostración.
- Dependencias externas pendientes.

No conviertas un porcentaje de avance técnico en una afirmación de seguridad absoluta.

Un proyecto puede estar implementado al 100 % y aun así tener modelos con rendimiento insuficiente.

El 100 % de implementación no significa que la IA sea invulnerable.

---

# 18. FASE 15 — DOCUMENTACIÓN Y ENTREGA

Genera o actualiza:

1. `PROGRESO.md`
2. Informe de arquitectura.
3. Informe de auditoría de combate.
4. Informe de evaluación del Equipo Rojo.
5. Informe de evaluación del Equipo Azul.
6. Informe de condiciones de victoria y derrota.
7. Informe de campañas experimentales.
8. Informe de integración del Harness.
9. Informe de integración Wazuh.
10. Informe de seguridad.
11. Informe de pruebas.
12. Registro de pendientes.
13. Guía de instalación.
14. Guía de ejecución.
15. Guía de administración.
16. Guía de demostración.

Los informes deben incluir:

- Fecha.
- Commit.
- Configuración.
- Modelos utilizados.
- Escenarios.
- Número de ejecuciones.
- Resultados.
- Errores.
- Limitaciones.
- Evidencia.
- Pruebas ejecutadas.

Conserva las cifras históricas y añade los resultados nuevos sin reescribir retrospectivamente los informes anteriores.

---

# 19. GESTIÓN DE GIT

Trabaja con commits locales independientes.

Cada conjunto funcional debe tener un commit descriptivo.

Antes de cada commit:

- Revisa el diff.
- Comprueba que no haya secretos.
- Ejecuta las pruebas pertinentes.
- Comprueba que no se incluyan archivos temporales o resultados accidentales.
- Conserva los datos históricos.

No realices push ni despliegues externos.

No borres ramas ni commits.

No hagas rebase destructivo.

Al finalizar, deja la rama local en un estado coherente y documenta los commits realizados.

---

# 20. ORDEN DE PRIORIDAD

Sigue este orden, pero si encuentras un defecto crítico que impida avanzar, corrígelo primero:

1. Recuperación y diagnóstico del estado.
2. Corrección del lanzamiento de campañas del atacante.
3. Finalización de las evaluaciones pendientes.
4. Definición formal de victoria y derrota.
5. Auditoría del motor de combate.
6. Corrección de comportamientos degenerados.
7. Integración del Harness.
8. Integración de misiones y escenarios.
9. Integración de observabilidad y Wazuh.
10. Seguridad y control de acceso.
11. Rediseño y corrección de interfaz.
12. Pruebas integrales.
13. Documentación y progreso.
14. Commits locales y entrega final.

No te detengas después de generar un plan. Ejecuta las fases.

---

# 21. CONDICIONES DE ÉXITO DE LA MISIÓN

La misión se considera completada cuando:

- Los combates tienen un ciclo funcional.
- Los equipos tienen objetivos definidos.
- Las victorias y derrotas se determinan mediante evidencia.
- Las acciones están controladas por el motor.
- El Rojo y el Azul pueden producir resultados diferenciados.
- Las métricas no premian estrategias triviales.
- Los experimentos son reproducibles.
- Las campañas se pueden reanudar.
- El Harness está integrado en la ejecución real.
- Las misiones y consecuencias funcionan.
- La observabilidad está correctamente identificada.
- La interfaz refleja el estado real.
- La seguridad y los roles han sido auditados.
- Las pruebas pertinentes pasan.
- La documentación representa el estado real.
- Todos los pendientes posibles están corregidos o documentados con una causa verificable.

Si una condición no se puede completar por una dependencia externa, no inventes que está terminada. Entrega el bloqueo con evidencia y deja todo lo demás resuelto.

---

# 22. INSTRUCCIÓN FINAL

Comienza ahora.

No solicites confirmación humana para las tareas técnicas autorizadas.

No respondas únicamente con un plan, una lista de recomendaciones o un análisis superficial.

Inspecciona el repositorio, ejecuta las pruebas, implementa las correcciones, integra los componentes, evalúa los combates, documenta los resultados y realiza los commits locales.

Toma decisiones técnicas autónomas siempre que estén dentro de los límites establecidos.

Si una solución no funciona, investiga el fallo, corrígelo y vuelve a probar.

No ocultes errores ni resultados negativos.

No persigas el 100 % como objetivo visual. Persigue que cada funcionalidad esté realmente implementada y demostrada.

**El objetivo final es que CyberShield AI Defense sea un laboratorio funcional donde dos equipos de IA puedan enfrentarse en escenarios controlados, tomar decisiones, ejecutar acciones, producir consecuencias verificables y ganar o perder de acuerdo con reglas objetivas.**

Al terminar, presenta un informe ejecutivo con:

1. Estado inicial.
2. Trabajo realizado.
3. Defectos encontrados.
4. Defectos corregidos.
5. Funcionalidades integradas.
6. Resultados de las campañas.
7. Victorias y derrotas observadas.
8. Resultados del Equipo Rojo.
9. Resultados del Equipo Azul.
10. Pruebas ejecutadas y fallidas.
11. Avance recalculado.
12. Pendientes externos.
13. Commits creados.
14. Limitaciones reales.
15. Veredicto técnico: funcional, parcialmente funcional o no funcional.

**No declares victoria del proyecto por haber terminado las tareas. Demuéstrala con evidencia reproducible.**