# Guion de la demo en vivo (10-15 min)

## Antes de empezar (5 min antes)

1. Arranca el servidor: `cd llm-redteam` y `py -3 server\app.py` (en Linux/macOS `python3 server/app.py`).
   Anota el **código de árbitro** que imprime (`Código de árbitro (vista General): ……`).
2. Abre **un navegador (o perfil) por participante**, en este orden: **General** `http://localhost:8000/?rol=general`
   (al proyector; nombre + código de árbitro) · **Azul** `?rol=azul` · **Rojo** `?rol=rojo` · opcional
   **Espectador** `?rol=espectador` (sin nombre). Cada uno escribe su **nombre**. Azul entra antes de que Rojo envíe.
3. Comprueba que cada vista muestra su etiqueta con el nombre («EQUIPO AZUL · Beto»), «PREPARACIÓN» y «● Conectado».
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
| 11-12 | Azul | En el correo, **🚨 Abrir incidente** → pestaña Incidentes → **🔒 Revocar credencial** → **Investigar** → intenta **Resolver** (lo rechaza: falta contener) → **Contener** → **Resolver**. | Dependencias entre misiones; el servidor explica qué falta. |
| 12 | General | Maximiza **Auditoría** (□) para enseñar el rastro; enseña `data/eventos.jsonl`. | Cada acción queda en una auditoría append-only y en JSON para Wazuh. |
| 12-13 | General | 🏁 **Finalizar partida** → confirma. | Resultado congelado; tras cerrar, Rojo/Azul reciben 409. |
| 13-15 | — | Preguntas. Opcional: *Batalla IA vs IA* con Ollama. | Con `qwen3:4b` cada llamada tarda 12-27 s en CPU: mejor solo 1-2 rondas. |

Resultado esperado con este guion (medido en la prueba automatizada): **Rojo 0 — Azul 85**, riesgo final 0/100.
Para que Rojo puntúe, deja un enlace clicado **sin contener** o un PDF abierto **sin reportar** antes de finalizar.

## Si algo sale mal

- Un panel "desapareció": búscalo en la barra de tareas (puede estar minimizado) o pulsa **▦ Organizar**.
- El diseño de ventanas estorba: **☰ Vista clásica** en la cabecera (se vuelve con 🖥 Vista escritorio).
- Cerraste una pestaña: vuelve a abrir la misma URL en el mismo navegador y reconecta sola (la sesión se guarda).
- Otra demo con la misma gente: al terminar, **↻ Nueva partida** en General (sin reiniciar el servidor).
- Ensayo completo sin manos: `py -3 e2e\demo_partida.py` (~15 s, 42 comprobaciones, regenera las capturas).
