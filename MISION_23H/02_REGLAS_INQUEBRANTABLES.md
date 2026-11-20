# 02 — REGLAS INQUEBRANTABLES

## Autorizado (sin pedir confirmación)
Inspeccionar el repo; modificar código; crear módulos, scripts, pruebas, documentación; ejecutar pruebas y campañas locales; hacer commits **locales** en la rama `mision-23h`; instalar dependencias de Python/Node necesarias; reiniciar el servidor local y procesos propios; `ollama pull` de **hasta 3 modelos de ~8B** (ver archivo 05) tras comprobar espacio en disco.

## Prohibido
1. `git push`, cambios en remotos, despliegues, compras, cambios de permisos externos.
2. Borrar ramas, commits, `respaldo_pre_mision/`, campañas anteriores, resultados o informes históricos. Los resultados viejos se conservan; los nuevos se añaden como versiones.
3. Reescribir resultados para mejorar porcentajes; cambiar criterios de evaluación retrospectivamente; cambiar los pesos de la fórmula de avance histórica.
4. Presentar algo simulado como real (Wazuh, Ollama, resultados). Nunca inventar salidas de modelos ni alertas.
5. Desactivar controles de seguridad para que algo "funcione".
6. Tocar sistemas, redes o cuentas reales. Todo dato es ficticio y local.
7. `rm -rf`, `git reset --hard`, `git clean`, rebase destructivo, sobrescribir la BD histórica.
8. Declarar el proyecto "terminado" sin evidencia reproducible.

## Límites de diseño del atacante (decisión ética del proyecto, vigente)
- El Equipo Rojo produce **únicamente texto en lenguaje natural dirigido al defensor simulado** (ingeniería social / prompt injection contra el agente ficticio). Nada de código de explotación, malware, escaneo de red ni instrucciones aplicables al mundo real.
- **Sin memoria persistente del atacante entre partidas**: no se guardan ni reutilizan "lo aprendido" de una partida en la siguiente. Dentro de una partida solo ve su propio historial de turnos y las respuestas visibles del defensor (el contexto normal de una conversación).
- **Sin descubrimiento autónomo** de credenciales/protocolos fuera de lo que el escenario ficticio expone por diseño; las credenciales del escenario son el conjunto fijo de semillas (máx. 10) ya definido.
- Las consecuencias entre turnos las decide el **motor de reglas determinista**, no una IA que acumule estrategia de explotación.
- Las campañas de evaluación comparan modelos/configuraciones con condiciones fijas; no entrenan al atacante con los resultados.
Si un requisito de otro archivo parece chocar con esto, **gana este archivo** y lo documentas en `docs/DECISIONES.md`.

## Disciplina de trabajo
- Rama única de trabajo: `mision-23h`. Commits pequeños y descriptivos al terminar cada conjunto funcional (revisa el diff y que no haya secretos ni archivos temporales).
- Pruebas después de cada tarea relevante; regresión completa al cierre de cada fase.
- **Regla de 3 intentos:** ante un defecto, prueba hasta 3 enfoques distintos con diagnóstico real de causa raíz. Si sigue fallando, regístralo en `BLOQUEOS.md` (síntoma, intentos, hipótesis) y avanza. No te quedes atascado ni repitas lo mismo.
- Distingue siempre: fallo del modelo / del prompt / del motor / de integración / del escenario / de medición.
- No ocultes errores ni resultados negativos. Un resultado malo honesto vale más que uno bonito falso.
- Si una prueba falla porque el comportamiento cambió **intencionalmente**, actualiza la aserción y déjalo anotado en `docs/DECISIONES.md`. Si falla por regresión real, corrígela.

## Entorno
El usuario trabaja en **Windows (PowerShell)**. Escribe scripts en Python (o comandos compatibles con PowerShell: nada de `&&` bash-only), usa rutas portables (`pathlib`) y procesos en segundo plano compatibles con Windows. Antes de lanzar un proceso largo, verifica que no haya otro igual corriendo (puertos, PIDs, locks).

## Ahorro de recursos
No hagas descargas pesadas fuera de lo autorizado. Mantén los logs de campañas en archivos, no en el contexto de la conversación (imprime resúmenes, no volcados).
