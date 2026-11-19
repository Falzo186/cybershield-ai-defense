# Informe ejecutivo final — misión autónoma de 23 horas

Fecha: 2026-11-19 · Rama `mision-23h` · Último commit de código: `aba15af` (los de documentación posteriores no cambian código) · Proyecto: CyberShield AI Defense (laboratorio académico, 100 % local y ficticio).
Modelos: `qwen3:8b` y `llama3.1:8b` (Q4_K_M) en Ollama 0.32.5, RTX 5060 8 GB. Wazuh: **simulado**.

## 1. Estado inicial
El proyecto tenía capas deterministas, equipos, buzón, misiones, Harness, campañas del defensor y del atacante, panel y Wazuh de **solo lectura**. Carecía de lo central: **ninguna victoria o derrota formal** (las capas bloqueaban todo, el Rojo nunca podía «ganar») y de un combate IA vs IA con ganador. Línea base de pruebas: 33 suites, de las que fallaban 5 por causas de entorno (`fastapi` ausente, `eventos_ejemplo.jsonl` nunca versionado, consola cp1252). Detalle: `docs/auditoria/00_ESTADO_INICIAL.md`.

## 2. Trabajo realizado
Motor de combate con zonas de política, verdad de fondo, objetivos con hash y resultado inmutable (15 escenarios) · modelos 8B con parser estricto y Harness gobernando la partida · Wazuh simulado integrado · API y UI «Teatro de batalla» · lanzador de campañas reanudable · análisis estadístico (Wilson, bootstrap por partida, Fisher + Holm) · detección de degenerados y sensibilidad · E2E con capturas · documentación y PDF.

## 3. Defectos encontrados
1. `eventos_ejemplo.jsonl` jamás versionado (`.gitignore *.jsonl`): 5 pruebas fallaban. 2. `fastapi` no instalado. 3. `ejecutar_pruebas.py` caía por cp1252. 4. Un corte de campaña dejaba una partida a medias y el relanzamiento reventaba (`UNIQUE constraint failed`). 5. La UI contaba en vivo las aprobaciones legítimas como «aceptadas del Rojo». 6. Mi primera prueba de sensibilidad estaba mal diseñada (recurso que la política permite a cualquiera). 7. Un commit mío incluyó por error el borrado de capturas históricas (deshecho antes de publicar). 8. `exit code 4` de campañas: ya diagnosticado el 07/11 (el código 4 no sale del programa; el shell fue terminado desde fuera); aquí se evitó con lanzador desacoplado, candado y progreso en archivo (ver también `docs/INCIDENTE_LANZAMIENTO.md`).

## 4. Defectos corregidos
Todos los anteriores (1–7) con prueba o verificación; el 8 se mitiga, no se «demuestra» su causa exacta (sigue siendo la hipótesis ya registrada). El E2E principal ahora arranca con Edge/Chrome si falta el Chromium de Playwright.

## 5. Funcionalidades integradas
Combate Rojo/Azul con 8B desde la **UI y la CLI** · victoria Roja/Azul, empate, empate degradado, inconclusa, error técnico · tráfico legítimo intercalado (30–40 %) · Wazuh simulado visible en UI y consumido por el Azul (el Rojo no lo ve) · Harness (presupuesto, cortes, errores seguidos) · historial con reproducción · exportación JSON · campañas visibles en la UI · enlace desde la interfaz principal y el panel.

## 6. Resultados de campañas (`docs/evaluacion/INFORME_CAMPANAS.md`)
2 370 partidas válidas, 0 inválidas/inconclusas: 1 800 líneas base triviales, 120 espejo, 120 cruzadas, 150 contra línea base, 120 variaciones, 60 con Rojo cortés. ≈ 9 700 inferencias reales.

## 7. Victorias/derrotas observadas
Líneas base: «rechazar siempre» → empate degradado 100 %; Azul por registro → victoria Azul 100 %; Azul «aprobar siempre» → victoria Roja 100 % con Rojo de guion. **8B vs 8B: 0 victorias Rojas en 240; victoria Azul 63–95 %; empate degradado 5–37 %; 6 empates** (Rojo con objetivo parcial, llama→llama).

## 8. Resultados Rojo
0/240 victorias; objetivo parcial en 6/240 (1 920 intentos → 6 aceptadas). Sin repeticiones, sin respuestas vacías ni mensajes filtrados. Contra un Azul que aprueba todo gana 93 %: sabe pedir, no engaña a un defensor que verifica. **No concluyente** para otros modelos o prompts.

## 9. Resultados Azul
Prevención 98,7–100 % (6 aprobaciones indebidas en toda la campaña 8B). Costo: legítimas atendidas 77–97 %; `qwen3:8b` escala ≈ 70 % de sus decisiones y cae en empate degradado en 30 % (espejo). Sensibilidad: detectan tickets inventados y resisten presión, pero **aprueban a quien no tiene el derecho registrado si pide con cortesía** un documento interno (qwen 8/8, llama 5/8). Quitar la verificación de tickets baja la victoria Azul a 27–47 %. No hay evidencia de que el Wazuh simulado ayude (n = 15 por celda).

## 10. Pruebas ejecutadas y fallidas
Batería completa **38/38 suites · 1 850/1 850** (commit aba15af); cobertura de módulos nuevos 91 %. Fallos durante el desarrollo, todos corregidos (lista en el punto 3). Omitidas: prueba contra un Wazuh real (sin instancia). Detalle en `docs/PRUEBAS.md`.

## 11. Avance recalculado
Fórmula histórica sin tocar pesos (`experimentos/avance.py`, 18 criterios del encargo): **100 %**, con evidencia actualizada; este número mide el encargo, **no** que el sistema sea invulnerable ni que los modelos rindan.
Criterios propios de esta misión (0 / 0,5 / 1, sin ponderar): implementación **1** · integración (UI+API+Harness+Wazuh+motor) **1** · pruebas **1** · calidad experimental de los modelos **0,5** (resultado válido pero un solo diseño de prompts y n = 60 por pareja) · preparación para demo **1** (guion, plan B y captura real) · dependencias externas **0,5** (Wazuh real y TLS sin probar).

## 12. Pendientes externos
Instancia real de Wazuh (contrato y stub listos) · TLS/autenticación de transporte (documentado, no desplegado) · RAG con embeddings · más modelos/prompts y más repeticiones para conclusiones estadísticas · medir «con/sin Harness» aislado.

## 13. Commits creados
Rama `mision-23h`, 20 commits desde la etiqueta `pre-mision-23h` (`git log --oneline pre-mision-23h..HEAD`): diagnóstico, sistema formal de victoria + Wazuh simulado, combate con Harness y campañas, API, UI, degenerados, análisis, pruebas, docs, campañas y cierre. **Sin push.**

## 14. Limitaciones reales
60 partidas por pareja (repeticiones del mismo escenario no totalmente independientes); un solo diseño de prompts (v2); el defensor ve un registro del sistema fiable (decisión D-02); Wazuh es simulado, su efecto no extrapola al real; el Rojo cumple los límites éticos (solo texto, sin memoria entre partidas), lo que acota su poder; **31 capturas históricas de `docs/capturas_demo/` aparecían borradas por una corrida anterior y `git checkout` fue denegado**: el E2E principal las regeneró (modificadas respecto a git, sin commit); para volver a las originales: `git checkout -- docs/capturas_demo`.

## 15. Veredicto técnico
**Funcional.** Evidencia: combate completo con 8B reales lanzable desde UI y CLI (E2E real verificado), victoria/derrota decididas solo por el motor y demostradas alcanzables para ambos equipos en los 15 escenarios, Wazuh simulado integrado y rotulado, batería 1 850/1 850, 2 370 partidas medidas sin invalidez. Con la salvedad honesta de que **con estos modelos el Rojo no gana**: el combate es técnicamente completo, pero competitivamente desbalanceado a favor del Azul; eso es un resultado, no un defecto de la medición.
