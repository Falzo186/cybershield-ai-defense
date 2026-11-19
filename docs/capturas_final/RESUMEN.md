# Capturas finales del Teatro de batalla (`/combate/`)

Generadas por `python e2e/test_combate_ui.py` (Playwright sobre el Edge/Chrome instalado, modelos FALSOS determinísticos,
bases temporales). Cada captura es una pantalla real, no un mock. Resoluciones obligatorias: 1366×768 y 1920×1080; además
1280×720 para comprobar que no se rompe.

**Antes:** `docs/capturas_antes/combate_antes_batalla_partida.jpg` (la ventana «Batalla de la partida» de la etapa anterior:
solo medía engaño y fugas del defensor; no había ganador para ambos equipos ni objetivos, ni resultado persistido).

## Bucle de revisión visual (3 iteraciones)
| Iteración | Defectos que se vieron en las capturas | Corrección |
|---|---|---|
| 1 | El banner de resultado ocupaba media pantalla y empujaba la cronología fuera de la vista a 1366×768 | Banner compacto de una fila (resultado + motivo + métricas + exportar) |
| 1 | «legítimas —» en una victoria Roja sin tráfico legítimo todavía: parecía un fallo | Texto explícito «sin tráfico legítimo todavía» y medidor «Sin medir» |
| 1 | El formulario de nueva partida seguía abierto con una partida en curso | Se pliega al abrir una partida |
| 1 | Título de escenario con id crudo (`verificacion falsa`) | Nombres de familia con tildes |
| 2 | En «Wazuh (simulado)» el modo SIMULADO pintaba un rectángulo violeta sobre todo el ancho de la tarjeta | Chip compacto |
| 2 | Texto terciario (hints) con contraste ~4,2:1, bajo AA | Token `--p-texto-3` subido a #8a9db8 (≥ 5:1) |
| 2 | Avisos (toasts) tapaban el medidor del Azul | Duran 3,5 s en vez de 5,5 s |
| 3 | Historial con todas las horas iguales (reloj lógico) | Marcas de tiempo reales; el hash del evento no las incluye (sigue reproducible) |
| 3 | Con el servidor caído la cabecera seguía diciendo «Ollama activo» | Cualquier fallo de red refresca el estado y lo dice |

Lo que verifica el E2E (39 comprobaciones): sin «victoria» antes de `partida.resultado` (muestreado durante la partida), coincidencia
de la pantalla con el resultado persistido en victoria Roja, Azul, empate degradado e inconclusa, espectador de solo lectura (403
al intentar crear), Wazuh siempre SIMULADO, estados vacío/error/desconectado, sin desborde horizontal a 1920×1080 y 1280×720,
navegación por teclado, consola sin errores ni warnings propios y sin 4xx/5xx inesperados.

## Archivos
`01_nueva_partida` · `02_victoria_roja` (1366, 1920, 1280) · `03_victoria_azul` · `04_empate_degradado` · `05_historial` ·
`06_wazuh_simulado` · `07_campanas` · `08_espectador` · `09_servidor_desconectado`.

**Pendiente (honesto):** la captura con modelos 8B reales (`10_combate_8b_real_*`) se toma en F8 con una partida real.
