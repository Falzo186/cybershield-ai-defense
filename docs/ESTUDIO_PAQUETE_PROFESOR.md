# Estudio del paquete del profesor (`Desktop\Cyberseguridad\Mision\`) — 2026-11-21

Lectura hecha: `LEEME_PRIMERO`, `INICIAR_AQUI`, `CLAUDE.md`, `04_DECISIONES_CONSOLIDADAS`, `05_CONTRATOS_TECNICOS`, `REGLAS_AUTONOMIA`, `ORDEN_EJECUCION`, `DEFINICION_DE_TERMINADO`, `PROGRESO`, el objetivo y los 35 criterios del `01_PROMPT_MAESTRO` y el índice del `03`. **No** leí completos los prompts de las fases F00–F23 ni el `02`; está marcado donde importa. Durante el estudio **Ollama y la campaña de Caminos quedaron detenidos** (la campaña es reanudable).

## 1. Qué es el paquete
Un plan para que Claude Code **reconstruya CyberShield desde cero** en `CyberShield_Rebuilt` (ruta distinta del proyecto actual, que queda de solo lectura): 24 fases (≈ 40 h), con un runner que lanza una sesión limpia por fase. Fuentes en orden de prioridad: **04 decisiones > 05 contratos > doc 03 > doc 02 > doc 01 > prompt de fase**.

## 2. Qué exige (lo esencial)
- **Problema a no repetir** (01 §0): batalla que arranca sola, prompts que no se detienen, «dos IA intercambiando respuestas», jugadores sin ver quién está conectado, equipos/correos/aprobaciones inexistentes, defensores espectadores, **sistema que premia a la defensa siempre**.
- **Reglas duras:** el motor es la autoridad (la IA propone, el motor valida, los humanos deciden); la partida **nunca** inicia sola (solo admin, con confirmación e idempotencia); sin fachadas; secretos enmascarados; todo ficticio (`.test`, `lab://`); sin `git push` ni `ollama pull`.
- **Diseño concreto (D1–D18):** empresa *Distribuidora Nova*; **6 identidades fijas** (máx. 4 Azul humanos; EMP-04 con credencial débil `12345A`); credenciales **5 dígitos + letra**, guardadas con HMAC + Fernet; **adivinación controlada** (3 intentos/ronda, 12/partida, cooldown 20 s, bloqueo a los 3 fallos); exposición por enlace `lab://` sin campo de contraseña; **victoria Roja** solo por `extraction.completed` del motor (tabla `reportes_financieros` o copia completa vía aprobación humana); victoria Azul por contención con continuidad ≥ 0,6 (**«rechazar todo» no gana**); reloj de partida inyectable; `ScriptedProvider` etiquetado como SIMULADO; `ai_mode` off/assist/auto; tres modalidades (Rojo/Azul/Balanceada); Ollama por equipo y por PC con anti-SSRF.
- **Contratos (05):** máquina de estados de partida (CONFIGURACION → SALA_DE_ESPERA → LISTA → EN_CURSO ↔ PAUSADA → DETENIENDO → FINALIZADA/CANCELADA/ERROR), sobre de eventos con `seq` monótono y visibilidad filtrada en servidor, acción estructurada con pipeline de 10 pasos, propuestas Rojo/veredictos Azul en JSON estricto, 35 tablas mínimas, REST `/api/v1` + WebSocket `/ws/v1`.
- **Stack:** FastAPI + SQLAlchemy + Alembic + WebSockets; React 18 + TypeScript + Vite + Zustand; pruebas pytest/Vitest/Playwright; sin CDN.
- **Cierre:** 35 criterios, cada uno `APROBADO CON EVIDENCIA | PARCIAL | NO IMPLEMENTADO | NO VERIFICADO`; un criterio solo es aprobado con operación real + prueba sobre **estado persistido** + ruta de la prueba.

## 3. Dónde está la reconstrucción (`CyberShield_Rebuilt`)
Hechas **F00–F05** (294 pruebas de backend, motor al 96 % de cobertura): auditoría, 47 tablas + Alembic, auth real, presencia por WebSocket, ciclo de vida con coordinador y reloj, motor con pipeline de 10 pasos y modalidades. **F06–F23 no se ejecutaron**: los logs muestran que el runner chocó con el **límite de uso de 5 horas** («resets 12:20 pm»), no con un fallo de código. Siguiente paso anotado en su `PROGRESO.md`: **F06 (correos y enlaces)**. Falta todo el frontend, las IA, la extracción/victoria y la demo.

## 4. Cómo se compara con lo que ya hicimos en `cybershield-ai-defense`
Mapa **propuesto** de los 35 criterios del 01 §30 frente a la ruta *Original + Repair + Caminos* (evidencia en `CyberShield_Repair_Library/TEST_RESULTS.md` y `docs/`). Es mi lectura, **no** una auditoría formal bajo el estándar del profesor.
| Estado | Criterios |
|---|---|
| Con evidencia (prueba automática sobre el servidor real) | 1–5, 7–10, 12, 13, 18–20, 22–24, 26, 28–31, 32, 34, 35 |
| Parcial | 6 (hay «preparación», no sala de espera con «listo»), 11 (se finaliza; no existe `DETENIENDO`), 14–15 (host por equipo en red local, sin prueba en dos PC), 16–17 (chat y solicitudes, sin tableros de coordinación), 21 (Wazuh **simulado** y cronología; sin alertas/incidentes con la máquina de estados del 05), 25 (el defensor IA genera solicitudes humanas; no es el flujo completo de «Blue solicita»), 27 (la aprobación se registra pero **no** altera un estado del escenario), 33 (LAN no verificada) |
| No cubierto por el diseño actual | extracción de tablas y **pantalla de victoria con descarga** (D7), adivinación con presupuesto/cooldown/bloqueo sobre credenciales `5 dígitos+letra` (D4–D5), 6 identidades Nova fijas y máx. 4 Azul, `ai_runs` completos, modalidades Rojo/Azul/Balanceada, `ai_mode` off/assist/auto, WebSocket/REST bajo `/api/v1`, React/TypeScript |

Lo que el modo **Caminos** y el combate libre aportan (victoria/derrota por motor, «rechazar todo» no gana, honestidad de procedencia, campañas con 8B) **no está pedido** por el paquete, pero encaja con D8 y con el criterio 29.

## 5. Qué hace falta para llegar a lo que pide el profesor
1. **Decidir la ruta**: continuar *Rebuilt* (cumple el stack y los contratos; faltan F06–F23 ≈ 30 h de agente) o **alinear el Original** (más rápido para una demo, pero con otro stack y sin varios criterios).
2. Si se continúa *Rebuilt*: reanudar el runner desde **F06** (sin límite de uso), con Ollama real instalado para F20; preparar un modelo ~4B y uno ~8B (los modelos ya están: `qwen3:8b`, `llama3.1:8b`).
3. Cerrar en `FINAL_DELIVERY_REPORT.md` con los 35 criterios y evidencia, y hacer la **comparación** que ya pidió el usuario entre las dos rutas con el mismo guion de demostración.
4. Reanudar la campaña de Caminos (resumable) y terminar `INFORME_CAMINOS` cuando se libere la GPU.

## 6. Dudas que dejo abiertas
No leí los prompts de las fases F06–F23 ni el doc 02; si se retoma *Rebuilt* hay que leerlos antes de ejecutar. La afirmación del §4 sobre criterios «con evidencia» es una estimación mía a partir de las pruebas existentes.
