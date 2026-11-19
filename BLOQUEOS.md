# Bloqueos
- **B-1** (F0): `git checkout -- docs/capturas_demo` fue denegado por el clasificador de permisos del entorno. Síntoma: 31 capturas tracked aparecen borradas. Intentos: 1 (checkout). Hipótesis: la acción se juzga destructiva aunque solo recupere archivos borrados. No afecta a la misión; se excluyen de los commits y se informa al usuario.
