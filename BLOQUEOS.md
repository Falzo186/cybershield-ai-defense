# Bloqueos
- **B-1** (F0): `git checkout -- docs/capturas_demo` fue denegado por el clasificador de permisos del entorno. Síntoma: 31 capturas tracked aparecen borradas. Intentos: 1 (checkout). Hipótesis: la acción se juzga destructiva aunque solo recupere archivos borrados. No afecta a la misión; se excluyen de los commits y se informa al usuario.

## B-1 — cerrado (2026-11-19)
`docs/capturas_demo` restaurada con `git checkout -- docs/capturas_demo` tras autorización explícita del usuario; el árbol queda sin cambios en esa carpeta. Las capturas regeneradas por el E2E se descartaron (no se commitearon).

## Nota 2026-11-19 · C.2 de la misión extra
La versión actual del encargo manda **omitir** C.2 (victoria Roja guionada en la UI) y sustituirla por la misión Caminos. Ya estaba implementada y verificada (modo «Guion determinista (sin IA)», etiqueta permanente «NO ES UN MODELO», 29/29 en el E2E extra) antes de recibir esa instrucción; se conserva rotulada y no se presenta como evidencia sobre ningún modelo. La misión Caminos podrá reemplazarla.

## B-2 · `e2e/test_combate_ui.py`: umbral de rendimiento (2026-11-21)
La comprobación «200+ eventos: la cronología se pinta en < 4 s» da ≈6,1 s en esta máquina, **igual en `pre-mision-extra`** (medido en un worktree aparte): es el rendimiento actual del equipo, no un cambio de código. No se relajó el umbral para «poner en verde». Pendiente: re-medir con la máquina en reposo o decidir un umbral con criterio. Es la única falla abierta de la batería (1 885/1 887).
