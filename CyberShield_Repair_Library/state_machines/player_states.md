# Máquina de estados · Jugador / conexión (`Sala`, `Participante`)
| Estado | Cómo se llega | Cómo se sale |
|---|---|---|
| `conectado` | unirse, o cualquier petición/latido en los últimos `PRESENCIA_S` (60 s) | sin actividad > 60 s → `inactivo`; `salir` → `desconectado` |
| `inactivo` (campo `conectado: false`) | sin peticiones ni latido (`POST /api/presencia` cada 20 s) | cualquier petición/latido → `conectado` |
| `desconectado` | `POST /api/sesion/salir` o caducidad de sesión (4 h) | volver a entrar con el mismo nombre (con clave propia si la tenía) |
Un participante desconectado **no desaparece**: se conserva en `listado_publico()` con `conectado:false` y `desconectado` (hora) para no perder su historial. Verificado: regresión 5, 8; E2E de la Sala de equipo.
