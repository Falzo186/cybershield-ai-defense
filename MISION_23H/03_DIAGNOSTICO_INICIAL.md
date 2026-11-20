# 03 — DIAGNÓSTICO INICIAL (Fase 0, ~1 h)

Antes de cambiar nada, documenta en `docs/auditoria/00_ESTADO_INICIAL.md`:

1. Rama activa, último commit, árbol limpio o sucio, ramas locales/remotas, estado de `origin/main` (solo lectura: `git fetch` permitido, nada más).
2. Lectura de `PROGRESO.md`, `README.md`, informes anteriores, `docs/`, y últimos 40 commits.
3. Inventario real de módulos: ¿existen `campana_atacante.py`, Harness, matrices de evaluación, misiones, Wazuh (real/simulado/desconectado), motor de victoria? Para cada uno: **existe / integrado en partidas reales / probado**. Formato 0, 0.5, 1 (0 no implementado, 0.5 parcial o sin integración/evidencia, 1 implementado+integrado+probado).
4. Modelos Ollama realmente instalados (`ollama list`), versión de Ollama, GPU/VRAM/RAM disponibles, espacio en disco.
5. Procesos en ejecución (campañas colgadas, servidores duplicados) y locks/archivos de progreso.
6. Pruebas existentes: ejecútalas todas y registra el resultado base (pasa/falla/omitidas). Esta es la **línea base de regresión**.
7. Deuda técnica: TODO/FIXME, funcionalidades implementadas pero desconectadas, pruebas fallidas.

## Investigación del error de campañas
Se reportó: `Launch attacker campaigns in background: exit code 4`. **No asumas la causa.** Reprodúcelo y determina cuál de estas fue: el proceso nunca arrancó / falló el lanzador (sintaxis de shell, Windows vs bash, rutas) / configuración inválida / dependencia ausente / conflicto de procesos o puertos / resultados parciales previos / terminó inesperadamente. Corrige la causa raíz, haz una **prueba corta** (2–3 partidas) revisando que los logs sean correctos, y solo después lanza campañas largas. Las campañas deben ser reanudables, sin duplicados, con progreso guardado y observaciones inválidas marcadas aparte.

## Matriz de pendientes
Crea `docs/PENDIENTES.md` con cada pendiente: id, descripción, severidad (crítica/alta/media/baja), causa, solución, estado. Resuelve primero lo crítico. Mantenla viva hasta el cierre.

## Entregable de la fase
`docs/auditoria/00_ESTADO_INICIAL.md`, `docs/PENDIENTES.md`, línea base de pruebas, commit `docs: diagnóstico inicial`. Actualiza `ESTADO_MISION.md`.
