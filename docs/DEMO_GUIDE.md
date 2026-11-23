# DEMO_GUIDE — recorrido de 5 minutos (modo práctica)

Objetivo: comprobar todas las mecánicas rápido, sin partida completa. Es una partida de **práctica**: queda marcada y no cuenta como oficial.

## Preparación
```powershell
python server/app.py
```
Anota el **código de árbitro** de la consola. Administrador: `http://localhost:8000/nova/`. Jugadores en la misma red: `http://<IP del anfitrión>:8000/nova/`.

## 1. Administrador (1 min)
1. Entra como Administrador con el código.
2. Marca **Partida de práctica** y pulsa **Crear partida**. (Dificultad de NPC: «Fácil» recomendada.)
3. Con el botón grande: **1 · Abrir sala de espera**. Cuando entren Rojo y Azul: **2 · Marcar LISTA** y **3 · Iniciar partida**.
4. IA: déjala en **SIMULADO** (no usa GPU). Para IA real: proveedor Ollama → «Encender Ollama» → modelo `qwen3:4b` → Aplicar. Al terminar, «Apagar Ollama».

## 2. Equipo Rojo (2 min)
1. Pulsa **Hacer siguiente paso**: prepara «Reconocer directorio». Revisa y pulsa **Ejecutar operación**.
2. Vuelve a pulsar **Hacer siguiente paso**: prepara un correo de soporte para un empleado. Ejecuta. En «Tus límites» ves cuántos correos te quedan.
3. Espera a que el empleado caiga (en práctica ~8 s). Si no cae, envía otro (puede desconfiar).
4. Elige tu objetivo: **Ruta financiera** (necesitas la credencial de Finanzas) o **Ruta de copia completa**.
5. Copia completa: **Solicitar elevación de permisos** → espera al Azul → **Exportar la base completa**.
6. ¿Perdido? **¿Qué hago ahora?** te dice el estado real y las acciones disponibles.
7. IA Roja (si está en asistido): «Pedir a la IA» → aparece una tarjeta con **Ejecutar / Editar / Descartar**.

## 3. Equipo Azul (2 min)
1. Panel «Seguridad de la empresa»: riesgo general, alertas, incidentes, correos sospechosos, credenciales comprometidas.
2. «Solicitudes que requieren atención»: lee quién, qué, el análisis de sospecha y la **consecuencia de aprobar o rechazar**; decide.
3. «Monitor de eventos»: ordenado por sospecha; abre un evento y usa **Pedir explicación a la IA** (si no hay modelo, responde con las reglas del motor).
4. Tu bandeja muestra la puntuación de cada correo. Puedes **Reportar** o **Neutralizar enlace**: tras reportar, los NPC caen menos.
5. Revoca credenciales comprometidas y contén el incidente para ganar por contención.

## 4. Resultado
Al terminar: victoria, resumen (objetivos, operaciones, credenciales comprometidas, recursos protegidos, errores y decisiones del Azul) y **línea de tiempo** filtrable por Jugadores / NPC / IA / Motor / Administrador. El espectador ve el marcador y la línea de tiempo pública sin secretos.

## Plan B
- Si Ollama no conecta, el panel lo dice en lenguaje simple; usa SIMULADO.
- Si un compañero no carga la página: firewall del puerto 8000 (ver `docs/PRUEBA_RED_LOCAL.md`).
