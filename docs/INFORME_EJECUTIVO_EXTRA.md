# Informe ejecutivo — misión extra: calibración v3 y preparación de demostración

Fecha: 2026-11-21 · Rama `mision-extra` (desde `mision-23h`, etiqueta `pre-mision-extra`) · Proyecto: CyberShield AI Defense (laboratorio académico, 100 % local y ficticio). No reescribe los informes anteriores.

## 1. Qué se hizo
- **Higiene (fase A):** `PENDIENTES.md` al día (P-06/P-12 fusionados, P-07 resuelto con `combate-v1`); capturas históricas restauradas con autorización; **incidente «exit code 4»**: tres enfoques controlados, **causa no demostrada**. Se descartó la hipótesis del directorio de trabajo y se corrigió una afirmación propia: el lanzador desacoplado **no** sobrevive a un corte de árbol de procesos.
- **Prompts v3 y campaña `combate-v2` (fase B):** v2 y `combate-v1` intactos (prueba con huella). Azul v3 con procedimiento de verificación contra el registro y alertas como contexto; Rojo v3 con el historial de la propia partida. Calibración en tres iteraciones sobre S1–S3/C1 (16 repeticiones), congelada y sin cambios durante la campaña. **300 partidas válidas, 0 inválidas.**
- **Demostración (fase C):** 3 partidas **reales** de `combate-v1` curadas en el Historial con «Reproducir cronología» (eventos verbatim, cadena de hashes recomprobada), modo «Guion determinista (sin IA)» con etiqueta permanente «NO ES UN MODELO», guion de 10 minutos.
- **Harness (fase D, exploratoria):** estricto vs holgado, 15 partidas por celda.

## 2. Resultados v1 (prompts v2) vs v3
| Pareja (espejo) | Versión | Victoria Azul | Empate degradado | Legítimas atendidas | Rojo ≥1 objetivo |
|---|---|---|---|---|---|
| qwen3:8b | v2 (n=60) | 70,0 % | 30,0 % | 84 % | 0 % |
| qwen3:8b | v3 (n=120) | **100 %** [96,9–100] | 0 % | 100 % | 0 % |
| llama3.1:8b | v2 (n=60) | 83,3 % | 6,7 % | 96 % | 10 % |
| llama3.1:8b | v3 (n=120) | **0 %** [0–3,1] | **100 %** | 13 % | 0,8 % |

- **Rojo: 0 victorias en 300 partidas v3.** El Rojo con mejor táctica no abre una puerta que el diseño de texto libre no tiene.
- **qwen3:8b mejora sin ceder:** 0 falsos negativos en 955 solicitudes maliciosas; el sobre-escalamiento baja de 71 % a 15 %.
- **llama3.1:8b empeora:** deja de pedir autorización pero rechaza el 97 % (falla el 87,5 % de las legítimas). Causa: el **modelo** no casa de forma fiable un par «recurso:acción» en la lista de derechos; tres iteraciones de prompt no lo corrigieron.
- Cruzada: solo n=30 por sentido (el tope de 4 h se agotó): exploratoria, mismo patrón. Significancia (Fisher + Holm): los contrastes de victoria Azul y empate degradado son significativos (p < 0,001).
- Harness estricto vs holgado: 15/15 victoria Azul en ambos; los topes estrictos **nunca cortaron** (≈19 llamadas vs tope 24): sin efecto medible.

## 3. Defectos y correcciones
- Afirmación incorrecta propia sobre el lanzador desacoplado (corregida con evidencia).
- Prueba mal diseñada de la misión anterior ya estaba descartada; esta vez, v3c rompió a qwen (aprobaba un ticket inventado 16/16) y se **descartó**, conservando sus datos.
- Carrera preexistente en `e2e/demo_partida.py` (espectador por sondeo): se añadió una espera; la aserción no cambió.

## 4. Pruebas
Batería completa: **37/39 suites · 1 885/1 887** (línea base 38/38 · 1 850/1 850; +37 comprobaciones nuevas). Las 2 fallas están explicadas: `demo_partida` (carrera preexistente, ya arreglada: 106/106 ×3) y `test_combate_ui` (umbral de rendimiento: **6,1 s también en `pre-mision-extra`**, es la máquina; sigue abierta, `BLOQUEOS.md` B-2).

## 5. Limitaciones
Azul v3 y Rojo v3 cambiaron a la vez (el efecto del Rojo no se aísla); S1–S3 son **en muestra** para v3; dos modelos, escenarios sintéticos y un solo atacante de texto; cruzada con n=30; el 100 % de qwen no se extiende a otros atacantes. Wazuh sigue simulado.

## 6. Pendientes
P-16 (cruzada ampliada), P-17 (llama v3), P-18 (Rojo v3 aislado), B-2 (umbral), causa del exit code 4, Wazuh real y TLS.

## 7. Commits
Ver `git log pre-mision-extra..mision-extra`: 17 commits locales, **sin push**.

## 8. Veredicto técnico honesto
La misión cumplió lo medible: qwen3:8b pasa de 70 % a 100 % de victorias Azul sin aprobar nada indebido, la demostración curada funciona y está rotulada con honestidad. **No** cumplió que v3 mejorara a ambos modelos (llama empeora) ni abrió una vía de victoria al Rojo en texto libre; eso queda para el modo con caminos. Veredicto: **funcional con una mejora clara en un modelo y una regresión documentada en el otro.**
