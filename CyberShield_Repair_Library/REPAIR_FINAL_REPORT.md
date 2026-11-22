# Informe final · CyberShield Repair (2026-11-21)
Rama `repair/stabilizacion-proyecto-original` (desde `mision-extra`, referencia inalterada `pre-repair`). Sin push; no se tocó ninguna ruta de «CyberShield Rebuilt».

## 1. Errores originales y causa raíz
Ver `ERROR_REGISTRY.md` (14 hallazgos con evidencia). Resumen de la **línea base medida antes de reparar**: de 26 comprobaciones de la presentación, **17 ya pasaban, 3 fallaban y 6 no existían**. Es decir, el proyecto original estaba **menos roto de lo descrito**: el control de partida, equipos, permisos, correos de plantilla, Ollama controlado y registro ya funcionaban; lo que faltaba era pausa, presencia/desconexión, notificaciones, idempotencia, correos del escenario, solicitudes de autorización (y, fuera de las 26, chat, correo libre y salud) y, sobre todo, **una pantalla que hiciera visibles y accionables a los jugadores**.
**No reproducido:** el arranque automático de la batalla y los modelos en bucle (ver `ERROR_REGISTRY.md` § No reproducido). No se afirma causa.

## 2. Archivos modificados / añadidos
`server/partida.py`, `server/app.py`, `src/lab/repositorio.py`, `src/lab/informe.py`, `ui/{index.html,app.js,api.js,render.js,styles.css}`, nuevos `ui/equipo/*`, `CyberShield_Repair_Library/**`, `ejecutar_pruebas.py`, `server/test_partida.py`, `e2e/demo_partida.py` (espera añadida).

## 3. Componentes recuperados / añadidos
Pausa y reanudación · presencia (conectado/desconectado) · notificaciones y no leídos · idempotencia · correos del escenario · correo libre de Rojo · solicitudes de autorización · chat de equipo · diagnóstico de salud · Sala de equipo. Máquinas de estado en `state_machines/`.

## 4. Pruebas
`TEST_RESULTS.md`: batería **44/45 suites · 1 991/1 993**; regresión de la presentación **17/3/6 → 29/0/0**; demo de 17 pasos 17/17 (modo de prueba); E2E de 3 navegadores 23/23. Fallo abierto: rendimiento de `test_combate_ui` (idéntico en la versión anterior, de entorno).

## 5. Estado por área
- **Ollama:** integración ya robusta; verificada con un Ollama falso lento y caído. **No** se probó la demo con Ollama real en esta ruta.
- **Correos:** plantilla + libre + escenario, bandeja, leído, notificación, contador. Límite: buzón de una sola identidad Azul.
- **Multijugador:** participantes en vivo con presencia; verificado con 3 navegadores a la vez (no con dispositivos físicos distintos).
- **Interfaz:** Sala de equipo nueva verificada con capturas (1366×768, 1920×1080); la UI principal solo recibió botones/etiqueta de pausa (cubiertos por `demo_partida` 106/106 en regresión, **no** por una prueba específica de esos botones).

## 6. Pendientes
`REMAINING_ISSUES.md`.

## 7. Comparación Original Repair vs Rebuilt
| | CyberShield Original Repair | CyberShield Rebuilt |
|---|---|---|
| Funcionalidades recuperadas/nuevas | las de §3, medidas | **sin datos en este repositorio** |
| Estabilidad | batería 44/45; regresión 29/29 | sin datos |
| Riesgos restantes | `REMAINING_ISSUES.md` | sin datos |
| Tiempo para llegar aquí | una sesión de trabajo continua (≈ unas horas de reloj), tras la misión extra | sin datos |
| Demo de 17 pasos | **17/17 en ≈24 s, modo de prueba (Ollama falso)**; con Ollama real: pendiente | sin datos |
**No se declara ganador.** Para comparar sin sesgo: ejecutar sobre Rebuilt los mismos 17 pasos (`tests/demo/demo_academica.py` describe cada paso y su evidencia) y la misma regresión de 26 puntos, con el mismo Ollama, y comparar pasos completados y fallos. Hasta entonces no hay base para una recomendación.

## 8. Veredicto honesto
El original se puede **demostrar** hoy de principio a fin en modo de prueba y los defectos reparables quedaron cubiertos por pruebas reproducibles; no está demostrado con Ollama real ni con dispositivos físicos, y quedan límites declarados (buzón compartido, sin estado CANCELADA/ERROR, SSE en vez de WebSocket).
