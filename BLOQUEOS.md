# Bloqueos
- **B-1** (F0): `git checkout -- docs/capturas_demo` fue denegado por el clasificador de permisos del entorno. Síntoma: 31 capturas tracked aparecen borradas. Intentos: 1 (checkout). Hipótesis: la acción se juzga destructiva aunque solo recupere archivos borrados. No afecta a la misión; se excluyen de los commits y se informa al usuario.

## B-1 — cerrado (2026-11-19)
`docs/capturas_demo` restaurada con `git checkout -- docs/capturas_demo` tras autorización explícita del usuario; el árbol queda sin cambios en esa carpeta. Las capturas regeneradas por el E2E se descartaron (no se commitearon).
