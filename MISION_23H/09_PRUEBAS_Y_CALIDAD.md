# 09 — PRUEBAS Y CALIDAD

Separa SIEMPRE: **pruebas con modelos falsos determinísticos** (verifican motor/UI/reglas) y **pruebas con modelos 8B reales** (verifican integración con Ollama y alimentan conclusiones sobre capacidad de IA). Nunca afirmes que "Ollama funciona" basándote solo en modelos falsos.

## Batería mínima
**Unitarias:** motor, permisos, objetivos, condiciones de victoria, misiones (transiciones válidas: pendiente → en_progreso → completada/bloqueada/cancelada/vencida), Harness (presupuesto por ronda, límite de llamadas/tokens/tiempo, cancelación, detección de respuestas vacías y llamadas repetidas), métricas (con casos calculados a mano), Wazuh simulado, parser de decisiones.
**Integración:** Ollama real (corta y controlada), motor↔repositorio, Harness↔combate (el Harness **gobierna partidas reales**, no es un módulo aislado; una acción denegada no provoca reintentos infinitos), misiones↔consecuencias, persistencia, Wazuh↔eventos.
**E2E (Playwright):** crear partida, elegir modelos, ejecutar, observar turnos, completar misiones, ganador, historial, espectador de solo lectura, 4 contextos de navegador.
**Negativas:** modelo desconectado, respuesta vacía, timeout, acción no autorizada, misión inválida, partida interrumpida, evento duplicado, presupuesto agotado, token inválido/rol incorrecto (403), intento de modificar resultado o escenario congelado (409).
**Seguridad:** espectador solo lectura; Rojo no altera permisos del Azul; Azul no altera resultados históricos; ningún modelo toca la BD fuera de los mecanismos autorizados; acciones críticas pasan por el motor; validación de entradas; sin secretos en logs. Documenta limitaciones de TLS/autenticación real sin simular que están resueltas.
**Regresión:** todo lo anterior al 5 de noviembre sigue funcionando (buzón, PDFs, misiones, marcador, cierre de partida, escritorio).
**Casos de combate representativos (deterministas):** gana Rojo; gana Azul; empate; Rojo falla; Azul falso positivo; Azul deja pasar amenaza; partida interrumpida; presupuesto agotado; modelo sin respuesta.

## Criterios
Corre la batería completa al cierre de cada fase y registra resultados en `docs/PRUEBAS.md` (comando, fecha, commit, pasadas/falladas/omitidas). Una prueba omitida lleva motivo. Cobertura aproximada de módulos nuevos ≥ 80 % si hay herramienta disponible; si no, no inventes el número.

## Fórmula de avance (no cambiar pesos históricos)
Estados 0 / 0.5 / 1 por funcionalidad con la fórmula y pesos de la auditoría anterior (`PROGRESO.md`). Informa por separado: avance de implementación, de integración, de pruebas, calidad experimental de los modelos, preparación para demo y dependencias externas. Un 100 % de implementación **no** significa que la IA sea invulnerable ni que los modelos rindan bien.
