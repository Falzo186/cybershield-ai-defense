# Guion de la demo en vivo (10-15 min)

## Antes de empezar (5 min antes)

1. Arranca el servidor **limpio** (cada arranque = partida nueva):
   `cd llm-redteam` y `py -3 server\app.py` (en Linux/macOS `python3 server/app.py`). Debe decir
   `Centro de Control en: http://<ip>:8000`.
2. Abre **una pestaña (o navegador) por vista**, en este orden: **General** `http://localhost:8000/?rol=general`
   (al proyector) · **Azul** `?rol=azul` · **Rojo** `?rol=rojo` · opcional **Espectador** `?rol=espectador`.
   Azul debe entrar antes de que Rojo envíe (los correos van a su usuario, `ana.perez`).
3. Comprueba que las tres muestran el escritorio con su etiqueta (VISTA GENERAL / EQUIPO AZUL / EQUIPO ROJO) y
   "● Conectado". Si una dice que el equipo "ya está tomado": reinicia el servidor y recarga las pestañas.
4. Plan B si algo falla en vivo: las capturas de una partida real están en `docs/capturas_demo/`.

## Desarrollo (orden sugerido)

| Min | Vista | Acción | Qué contar |
|---|---|---|---|
| 0-2 | General | Presenta el escritorio: ventanas, minimizar/maximizar, marcador arriba. | Laboratorio 100 % local y ficticio; el árbitro ve todo. |
| 2-3 | General | *Simulación* → *Iniciar*: el pipeline se ilumina capa por capa. | Defensa en profundidad: la IA propone, las capas deciden. |
| 3-5 | Rojo | 📬 Correo → envía *Soporte técnico*, *Recursos humanos* (PDF) y *Paquetería* (PDF). | Plantillas fijas, enlaces locales; Rojo nunca ve el enlace. |
| 5-7 | Azul | 📬 Buzón → abre *Paquetería* → pulsa el enlace (el "empleado distraído"). | En General: riesgo 15, Rojo +10. |
| 7-9 | Azul | Abre *Soporte técnico* → **⚑ Reportar**; vuelve a *Paquetería* → **⛔ Contener**. | Riesgo baja y Rojo pierde sus 10 puntos; dos misiones completadas. |
| 9-10 | Azul | *Recursos humanos* → **Abrir PDF** (se descarga) → **⚑ Reportar PDF**; pestaña 🎯 Misiones. | Abrir es solo un evento; reportar quita los +5 a Rojo. |
| 10-12 | General | Maximiza **Auditoría** (□) para enseñar el rastro; enseña `data/eventos.jsonl`. | Cada acción queda en una auditoría append-only y en JSON para Wazuh. |
| 12-13 | General | 🏁 **Finalizar partida** → confirma. | Resultado congelado; tras cerrar, Rojo/Azul reciben 409. |
| 13-15 | — | Preguntas. Opcional: *Batalla IA vs IA* con Ollama. | Con `qwen3:4b` cada llamada tarda 12-27 s en CPU: mejor solo 1-2 rondas. |

Resultado esperado con este guion (medido en la prueba automatizada): **Rojo 0 — Azul 35**, riesgo final 0/100.
Para que Rojo puntúe, deja un enlace clicado **sin contener** o un PDF abierto **sin reportar** antes de finalizar.

## Si algo sale mal

- Un panel "desapareció": búscalo en la barra de tareas (puede estar minimizado) o pulsa **▦ Organizar**.
- El diseño de ventanas estorba: **☰ Vista clásica** en la cabecera (se vuelve con 🖥 Vista escritorio).
- Una pestaña perdió su token (la cerraste): solo se recupera con una partida nueva (reiniciar el servidor).
- Ensayo completo sin manos: `py -3 e2e\demo_partida.py` (13 s, 38 comprobaciones, regenera las capturas).
