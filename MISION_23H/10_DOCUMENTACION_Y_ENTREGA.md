# 10 — DOCUMENTACIÓN Y ENTREGA

Conserva los informes anteriores intactos; los nuevos se agregan con fecha y commit. Cada informe incluye: fecha, commit, configuración, modelos, escenarios, nº de ejecuciones, resultados, errores, limitaciones, evidencia y pruebas ejecutadas.

## Documentos a producir
1. `PROGRESO.md` (actualizado por fase).
2. `docs/ARQUITECTURA.md` (incluye diagrama del flujo propone→valida→autoriza→ejecuta→audita y zonas de política).
3. `docs/auditoria/` (estado inicial y de combate).
4. `docs/VICTORIA_Y_DERROTA.md`.
5. `docs/evaluacion/INFORME_CAMPANAS.md` (Rojo y Azul por separado + cruzado).
6. `docs/HARNESS.md`.
7. `docs/WAZUH_SIMULADO.md` (y qué falta para uno real).
8. `docs/SEGURIDAD.md`.
9. `docs/PRUEBAS.md`.
10. `docs/PENDIENTES.md` y `BLOQUEOS.md`.
11. `docs/DECISIONES.md` (decisiones técnicas y cambios intencionales de pruebas).
12. `docs/GUIA_INSTALACION.md`, `GUIA_EJECUCION.md`, `GUIA_ADMINISTRACION.md`.
13. `docs/GUION_DEMO.md` (guion de 10 minutos: pasos exactos, qué partida mostrar, qué decir, plan B si Ollama falla).
14. `README.md` con datos reales medidos.
15. `docs/INFORME_EJECUTIVO_FINAL.md` (ver abajo).

## Informe ejecutivo final (obligatorio)
Secciones: 1 Estado inicial · 2 Trabajo realizado · 3 Defectos encontrados · 4 Defectos corregidos · 5 Funcionalidades integradas · 6 Resultados de campañas · 7 Victorias/derrotas observadas · 8 Resultados Rojo · 9 Resultados Azul · 10 Pruebas ejecutadas y fallidas · 11 Avance recalculado · 12 Pendientes externos · 13 Commits creados · 14 Limitaciones reales · 15 **Veredicto técnico: funcional / parcialmente funcional / no funcional**, con evidencia.

## Versión PDF para entrega académica
Genera `docs/INFORME_EJECUTIVO_FINAL.pdf` (reportlab o equivalente ya instalado; no descargues nada pesado). Estilo formal: **negro, azul marino y rojo oscuro**; sin colores brillantes ni naranja; portada estilo institucional UAT (Universidad Autónoma de Tamaulipas — Facultad de Ingeniería) con título, autor **Jesús Alejandro Murillo Zavala**, carrera (Ingeniería en Sistemas Computacionales), fecha y proyecto; encabezado/pie con número de página; tablas legibles. Revísalo renderizando páginas a imagen y mirándolas.

## Cierre
Último commit: `docs: cierre de misión 23h`. Deja `git status` limpio, rama `mision-23h` coherente, y `ESTADO_MISION.md` con "MISIÓN FINALIZADA" + hora + resumen de 10 líneas.
