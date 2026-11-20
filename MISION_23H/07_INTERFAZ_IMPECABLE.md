# 07 — INTERFAZ DE USUARIO IMPECABLE

Conserva el sistema tipo escritorio (ventanas, barra de tareas, íconos por rol, "vista clásica" de respaldo). **No reescribas lógica que ya funciona**; eleva calidad, coherencia y claridad. "Impecable" se demuestra con capturas y pruebas, no con afirmaciones.

## Principios
- Estética sobria y profesional de operaciones de seguridad: fondos oscuros neutros, azul marino como color de marca, rojo oscuro para Rojo/alerta, azul para Azul, verde/ámbar contenidos para estados. **Sin neones ni colores chillones ni naranja.** Un único sistema de tokens CSS (colores, espaciado, tipografía, radios, sombras) usado por TODAS las ventanas.
- Jerarquía visual clara: lo importante primero (marcador, turno, estado, resultado), detalle bajo demanda.
- Texto en español, consistente, sin jerga interna cruda; mensajes de error comprensibles y accionables.

## Pantalla de combate ("Teatro de batalla")
Debe mostrar a la vez o en ventanas acopladas: estado de partida y turno N/M; equipo Rojo + modelo; equipo Azul + modelo; objetivos de ambos con progreso (casillas que se marcan solo con confirmación del motor); línea de tiempo de eventos; mensajes Rojo→Azul y decisiones del Azul con justificación; recursos del escenario y su estado (íntegro/comprometido/contenido); panel Wazuh simulado; presupuesto consumido (tokens/llamadas/tiempo); marcador.
Estados visibles y diferenciados: pensando, ejecutando, acción aceptada, acción rechazada, amenaza detectada, misión completada, incidente contenido, **victoria/derrota/empate (solo tras `partida.resultado`)**, error técnico, partida interrumpida.
Pantalla final de resultado con resumen, cronología, métricas de la partida y exportación (JSON/PDF).

## Otras pantallas
Admin (crear partida, elegir escenario/dificultad, modelos Rojo/Azul, límites, semilla), historial de partidas con filtros y reproducción de cronología, vista Espectador (solo lectura real, sin botones de acción), campañas/evaluación (progreso, resultados, métricas con IC), Wazuh simulado, buzón y misiones existentes integrados al mismo diseño.

## Calidad de interacción
Estados de **carga, vacío, error y desconectado** en cada vista; indicadores de progreso reales; confirmaciones en acciones destructivas o irreversibles; toasts con clasificación éxito/error; atajos de teclado básicos; foco visible; navegación por teclado; contraste WCAG AA (≥ 4.5:1); `prefers-reduced-motion`; textos que no se desbordan; scroll interno en paneles; ventanas con tamaños por defecto adecuados y sin solaparse al "Organizar"; sin saltos de layout; rendimiento fluido con 200+ eventos en la cronología (virtualiza o pagina si hace falta).
Responsivo razonable (1366×768 y 1920×1080 obligatorios; no romper en 1280×720).

## Proceso de verificación (obligatorio, bucle ≥ 3 iteraciones)
1. Con Playwright, captura cada pantalla principal en 1366×768 y 1920×1080 → `docs/capturas_final/`.
2. **Mira las capturas** (léelas como imagen), lista defectos concretos (alineación, desbordes, contraste, jerarquía, estados vacíos, inconsistencias), corrige y repite.
3. Consola del navegador **sin errores ni warnings propios**; red sin 4xx/5xx inesperados.
4. Prueba E2E de partida completa con modelos falsos determinísticos (UI) y una con modelos 8B reales.
5. Antes/después en `docs/capturas_antes/` y `docs/capturas_final/` con un `RESUMEN.md` que enumere las mejoras.

## No hacer
No mostrar datos inventados en la UI para "verse bien"; no mostrar victoria anticipada; no esconder errores técnicos tras animaciones; no dejar botones muertos.
