# Arquitectura (lo que realmente hay)
- **Servidor** FastAPI (`server/app.py` + `mock_server.py` para el SSE y la estática): sesiones y equipos (`server/partida.py`), partida con fases y reloj propio, buzón/misiones/incidentes (`src/lab/repositorio.py`, SQLite), batalla IA (`src/lab/*`, Harness), combate IA vs IA (`src/lab/combate`, `server/combate.py`).
- **Tiempo real:** SSE `/api/eventos` (público, sin datos sensibles en los eventos) + sondeo de respaldo en el cliente. Presencia por latido `POST /api/presencia` + cualquier petición autenticada.
- **Reparación:** componentes puros y probados en `CyberShield_Repair_Library/components/*`, integrados por rutas pequeñas en `server/app.py`; middleware de idempotencia antes del de sesión.
- **Interfaz:** `ui/` (escritorio de ventanas), `ui/equipo/` (Sala de equipo), `ui/combate/`, `ui/panel/`. Todo texto dinámico entra por `textContent`.
- **Persistencia:** base SQLite del laboratorio (`CS_LAB_DB`); solicitudes y chat crean sus tablas al primer uso.
