# Guía de demostración (10–15 min)
**Automática (ensayo):** `python CyberShield_Repair_Library/tests/demo/demo_academica.py` → 17/17 pasos en ≈24 s con Ollama FALSO etiquetado (modo de prueba, sin GPU).
**En vivo con personas:** `python server/app.py` (anota el código de árbitro). Abre `http://localhost:8000/equipo/` en 4–5 navegadores/dispositivos de la misma red.
| Min | Acción | Qué se ve |
|---|---|---|
| 0–2 | Árbitro entra (código); jugadores entran como Rojo/Azul/espectador | participantes con su equipo y punto verde (conectado); PREPARACIÓN: nada ha empezado |
| 2–3 | Cada equipo elige su modelo en la aplicación principal (`/`, ventanas IA Atacante / Defensor) | Ollama real o, sin él, **modo de prueba** (etiquetado) |
| 3–4 | Árbitro: **Iniciar** (duración) | EN CURSO con reloj en todas las pantallas; a los 5 s llega un correo del escenario a Azul (aviso + contador) |
| 4–7 | Rojo: correo libre o plantilla; Azul lo abre, abre un incidente | notificación en vivo, no leídos baja, incidente en el registro |
| 7–9 | Rojo: **Pedir autorización**; Azul: **Aprobar/Rechazar** | la solicitud aparece en todas las pantallas de Azul y se actualiza en Rojo/árbitro; vence sola |
| 9–11 | Rojo lanza un ataque IA; se ve la respuesta defensiva | una sola operación a la vez, con resultado |
| 11–12 | Árbitro: **Pausar** → las acciones dan error claro y el reloj se queda quieto → **Reanudar** | PAUSADA en todas las pantallas |
| 12–13 | Un jugador cierra su pestaña | queda como desconectado, no desaparece |
| 13–15 | **Finalizar**; registro de eventos con filtros | resultado, ganador, cronología |
Plan B sin Ollama: todo lo anterior salvo el ataque IA funciona; el ataque IA se muestra con el Ollama falso etiquetado.
