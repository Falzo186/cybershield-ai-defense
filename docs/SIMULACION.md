# Ventana «Simulación» (`/simulacion/`)

Reproduce **partidas grabadas del modo Caminos** a ritmo narrativo (≈ 10 min) con paneles sincronizados. No genera nada: reproduce un **registro** (eventos con cadena de hashes) escrito por el motor.

## Qué muestra
- **Catálogo** (`GET /api/simulacion/catalogo`): ≥ 6 grabaciones (3 victorias Rojas por caminos distintos, 2 Azules y 1 reversión) más, si existen, las victorias Rojas **CAMINOS_IA** de la campaña. Cada tarjeta lleva la **insignia de procedencia**, los modelos, la semilla, la hoja y el hash del grafo.
- **Reproductor**: reproducir/pausar, velocidad 0,5×–4×, «siguiente hito», barra de progreso con hitos clicables; **nota fija** «Reproducción a ritmo narrativo: no es la duración real de la ejecución, que fue de milisegundos».
- **Paneles sincronizados** (derivados SOLO de lo ya reproducido): línea de tiempo en español con marca de tiempo simulada; mensajes Rojo/Azul; inventario de credenciales (sin probar/presentada/fallida/bloqueada/válida confirmada por el motor/rotada/señuelo, **revelado según avanza el registro**); alertas Wazuh rotuladas **SIMULADO**; estado de la base sintética (íntegra/comprometida/contenida); marcador; **grafo** con el camino recorrido resaltado y las hojas posibles atenuadas.
- **Resultado y «Qué enseña esta partida»** solo al llegar al evento `partida.resultado` del registro; arrastrar la barra hacia atrás los oculta de nuevo.

## Procedencia (obligatoria, siempre visible)
| `tipo` | Qué es | Cómo se presenta |
|---|---|---|
| `CAMINOS_GUION` | decisiones prefijadas o líneas base deterministas | «**Recorrido posible del grafo, demostrado por el motor. NO es una victoria de un modelo de IA**» |
| `CAMINOS_IA` | un 8B eligió las opciones | «un modelo eligió opciones; el motor decidió». Una victoria Roja aquí es real **en este modo** |
| `LIBRE_IA` | combate libre de texto | (combate libre, `/combate/`) |

## Grabar y lanzar
- `python experimentos/grabar_simulaciones.py` ejecuta de verdad en el motor las 6 partidas del catálogo y guarda `data/simulaciones/*.json` (partida, eventos, alertas, grafo). `--desde-campana <nombre>` añade las victorias Rojas CAMINOS_IA registradas.
- **Lanzar desde la UI** (árbitro): `POST /api/caminos/partidas` con modo `auto`|`grafo`, rojo, azul, semilla; solo la sesión «general» (otros → 403); una a la vez (409). Se abre la reproducción de lo que acaba de pasar.
- CLI: `python -m src.lab.caminos.jugar …` (grafo) y `python -m src.lab.caminos.auto --rojo qwen3:8b --azul llama3.1:8b --n 20 --semilla 1` (automático).

## Seguridad y verificación
Solo lectura y pública (GET). La cadena de hashes se **recomprueba en cada lectura**; ids con rutas maliciosas → 404; texto dinámico solo por `textContent`. Pruebas: `e2e/test_simulacion_ui.py` (24 comprobaciones: catálogo, procedencia, reproducción completa acelerada, resultado oculto hasta su evento, lanzar desde la UI, consola limpia) con capturas en `docs/capturas_caminos/` (1366×768 y 1920×1080, tres iteraciones visuales).
