# CyberShield Repair Library
Componentes, máquinas de estado, pruebas y documentación de la reparación del proyecto **original**.
- `components/` implementaciones reales: `game_session/idempotencia.py`, `notifications/notificaciones.py`, `email/correos_escenario.py`, `approvals/solicitudes.py`, `teams/chat.py` (pausa/presencia viven en `server/partida.py` por ser parte del ciclo de la partida).
- `state_machines/` tablas de transición de lo realmente implementado.
- `diagnostics/health_checks/salud.py` y `GET /api/salud`.
- `tests/` unit, regression (servidor real), demo (17 pasos) y `e2e_sala_equipo.py` (3 navegadores).
- Documentos: `REPAIR_MASTER_PLAN.md`, `ERROR_REGISTRY.md`, `REPAIR_STATUS.md`, `REPAIR_FINAL_REPORT.md`, `TEST_RESULTS.md`, `DEMO_GUIDE.md`, `REMAINING_ISSUES.md`, `CHANGELOG.md`, `documentation/`.
Ejecutar todo: `python ejecutar_pruebas.py` (desde la raíz). Solo regresión: `python CyberShield_Repair_Library/tests/regression/test_regresion_presentacion.py`.
