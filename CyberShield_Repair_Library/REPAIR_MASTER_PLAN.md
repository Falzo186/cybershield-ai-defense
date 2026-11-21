# Plan maestro de reparación (CyberShield Repair)
Ruta independiente de «CyberShield Rebuilt»; no se tocó ningún archivo de esa ruta. Rama `repair/stabilizacion-proyecto-original`, etiqueta de referencia `pre-repair`; sin push.

Estrategia: **dirigida por pruebas contra el servidor real**. 1) línea base y registro de errores; 2) por cada hallazgo, componente real + prueba unitaria + prueba de regresión; 3) interfaz (`/equipo/`) y E2E con varios navegadores; 4) demo de 17 pasos; 5) batería completa y reportes.

| Fase | Contenido | Estado |
|---|---|---|
| 1 Diagnóstico | inventario, pruebas, regresión de 26 puntos, `ERROR_REGISTRY.md` | hecha |
| 2 Reparación crítica | pausa/reanudación, presencia, permisos (ya correctos), idempotencia | hecha |
| 3 Comunicación | correos del escenario y libre, notificaciones, no leídos, chat, autorizaciones | hecha (ver límites en `REMAINING_ISSUES.md`) |
| 4 IA | controles de Ollama verificados (respuesta tardía, caída, duplicados); sin cambios de fondo | hecha |
| 5 Interfaz | Sala de equipo `/equipo/`; pausa en la UI principal | hecha |
| 6 Validación | regresión 29/29, unitarias, E2E multi-navegador 23/23, demo 17/17, batería completa | ver `TEST_RESULTS.md` |
