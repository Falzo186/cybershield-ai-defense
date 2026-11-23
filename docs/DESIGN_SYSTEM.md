# DESIGN_SYSTEM — CyberShield Nova (v1)

Archivo: `ui/nova/ds.css` (tokens + componentes), con la maquetación de zonas en `ui/nova/nova.css`. Se carga **después** de `panel.css`/`combate.css`, así todas las pantallas de Nova comparten el mismo sistema. Sin dependencias ni build.

## Dirección visual
Centro de operaciones táctico: tema oscuro grafito, superficies diferenciadas por capas, jerarquía por tamaño y color semántico, animaciones discretas (≤200 ms, desactivadas con `prefers-reduced-motion`). Sin neón ni efectos de terminal.

## Tokens (`:root`)
| Grupo | Variables |
|---|---|
| Fondos | `--ds-bg #0d1117` · `--ds-bg-2 #131922` · `--ds-surface #171e29` · `--ds-surface-2 #1d2634` |
| Líneas | `--ds-line #2a3446` · `--ds-line-2 #38455c` |
| Texto | `--ds-text` · `--ds-text-2` · `--ds-text-3` |
| Equipos | `--ds-red #e5575f` · `--ds-blue #4f8ff7` |
| Estado | `--ds-ok` verde · `--ds-warn` amarillo · `--ds-orange` · `--ds-crit` rojo (+ variantes `-bg`) |
| Forma | `--ds-r 10px` · `--ds-r-sm 7px` · espaciado `--ds-e1…e4` |
| Tipografía | 15 px base · 13 px secundaria · 12 px etiquetas · 18 px marca |

## Componentes
| Componente | Clases | Uso |
|---|---|---|
| Botón | `.boton` `.boton-primario` `.boton-peligro` `.boton-grande` | Mínimo 38 px de alto; el primario es la acción principal de la tarjeta. |
| Tarjeta / panel | `.tarjeta` `.tarjeta-cab` `.tarjeta-cuerpo` `.destacada` `.ia` `details.plegable` | `destacada` = requiere atención (solicitudes); `ia` = zona de la IA. |
| Formulario | `.campo` `.form-sol.cols` `.ayuda-accion` `details.avanzado` | Etiquetas en mayúscula pequeña; lo experto va plegado. |
| Indicador | `.chip` `.chip-ok/-aviso/-info` `.nivel.NORMAL/ADVERTENCIA/SOSPECHOSO/CRITICO` `.medidor` | **El nivel siempre lleva texto e icono** (● ▲ ◆ ✖), no solo color. |
| Tablas / listas | `.monitor` `.mon-fila` `.linea` `.id-fila` `.kpi` | Filas clicables con `aria-expanded`. |
| Alertas / avisos | `.guia` `.banner-estado` `.aviso-ayuda` `.prop-card` `.toast` | Toasts con borde de color por tipo. |
| Ventanas | `dialog.dlg-sol` `.panel-jug` | Cuadro modal de solicitudes; panel lateral de jugadores. |
| Estados de componente | `.estado-vacio` `.estado-carga` (spinner) `.estado-error` `.prop-card.pensando/.error` | Cargando, sin información, error, en ejecución. |

## Semáforo (Azul)
Verde = normal (<25) · Amarillo = advertencia (25–49) · Naranja = sospechoso (50–74) · Rojo = crítico (≥75). Cada nivel muestra su nombre y su icono.

## Maquetación
`.tablero`: 3 columnas (situación · operaciones/monitoreo · IA y bandeja). Por debajo de 1100 px pasa a una columna; las columnas vacías se ocultan (`ajustarColumnas`). Probado a 1366×768, 768×1024 y 390×800 sin desplazamiento horizontal.

## Accesibilidad
Foco visible, `aria-current` en la fase actual, `role="meter"` en el riesgo general, `aria-expanded` en filas, `aria-live` en avisos, respeto de `prefers-reduced-motion`, texto en toda señal de color.
