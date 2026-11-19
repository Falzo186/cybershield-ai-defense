# Arquitectura del combate IA vs IA (misión 23 h)

Fecha: 2026-11-18 · Rama `mision-23h`. Complementa a `docs/ARQUITECTURA_ACTUALIZADA.md` (etapa anterior), que sigue vigente para el
resto del laboratorio (buzón, PDFs, misiones, marcador, capas deterministas de datos).

## Principio rector
> **La IA propone → el motor valida → los permisos autorizan → el repositorio ejecuta → la auditoría registra.**

Ningún modelo se declara ganador por lo que dice. Gana quien alcanza sus objetivos en el **estado verificable** del escenario.

```
 Rojo (LLM 8B)            Motor de combate (src/lab/combate/motor.py)             Azul (LLM 8B)
 texto natural   ──────►  1. valida la petición (recurso/acción del catálogo)
 + {recurso,acción}       2. calcula señales observables  ──► Wazuh SIMULADO ──────► alertas (resumen)
                          3. ───────────── contexto sin verdad de fondo ──────────►  decide:
                                                                                     APROBAR / RECHAZAR /
                          4. aplica la ZONA DE POLÍTICA ◄───── decisión ───────────  SOLICITAR_AUTORIZACION / ESCALAR
                             DENEGADO_POR_POLITICA → bloquea siempre (defensa en profundidad)
                             DELEGADO_AL_DEFENSOR  → ejecuta, cambia estado, compara con la verdad de fondo
                             LIBRE                 → sin fricción
                          5. escribe el evento (cadena de hashes) en data/combate.db
                          6. evalúa el resultado en orden fijo  ──► partida.resultado (único, inmutable)
        Harness (ControlPartida) acota llamadas, tokens, tiempo y errores seguidos de TODA la partida
```

## Módulos
| Módulo | Responsabilidad |
|---|---|
| `src/lab/combate/escenarios.py` | 15 escenarios JSON (5 familias × 3 dificultades), `hash_escenario`, `validar` (objetivos alcanzables) |
| `src/lab/combate/motor.py` | `Partida`: turnos, zonas, verdad de fondo, objetivos, resultado, métricas, aislamiento de contextos |
| `src/lab/combate/modelos.py` | `RojoOllama`/`AzulOllama` (8B), parser estricto con reintentos acotados (≤ 2), modelos falsos y líneas base |
| `src/lab/combate/store.py` | SQLite con cadena de hashes; índice único que impide dos `partida.resultado` |
| `src/lab/combate/degenerados.py` | Detección de comportamientos degenerados (solo mide) |
| `src/lab/combate/jugar.py` | CLI de una partida |
| `src/lab/wazuh_sim/` | `WazuhProvider`, `SimProvider` (ruido + verdad de fondo oculta), `RealProvider` (stub) |
| `server/combate.py` | API `/api/combate/*` (GET públicos de solo lectura, POST del árbitro) |
| `ui/combate/` | Teatro de batalla, historial, Wazuh simulado, campañas |
| `experimentos/campana_combate.py` | Campañas reanudables en segundo plano |
| `experimentos/resumir_combate.py` | Estadística: Wilson, bootstrap por partida, Fisher + Holm, gráficas |

## Zonas de política
| Zona | Quién decide | Efecto |
|---|---|---|
| `DENEGADO_POR_POLITICA` | Las capas deterministas, siempre | Si el defensor aprueba, el motor bloquea: **DEFENSA_EN_PROFUNDIDAD** (punto de tesis del Azul; el Rojo anota *engaño parcial*, no objetivo) |
| `DELEGADO_AL_DEFENSOR` | El defensor (autoritativo) | El motor ejecuta, persiste el cambio y lo compara con la verdad de fondo |
| `LIBRE` | Nadie | Solicitudes legítimas sin fricción |

La zona **no** se muestra al Rojo ni al Azul durante la partida. El Azul decide con el *registro del sistema* (rol, derechos,
autorizaciones vigentes) y las alertas de Wazuh simulado.

## Verdad de fondo
Cada solicitud tiene una etiqueta `legitima` que solo conoce el motor. Las del Rojo son maliciosas por construcción. El **tráfico
legítimo** (plantillas fijas, semilla fija) se intercala en el 30–40 % de los turnos: sin él, «RECHAZAR siempre» ganaría.
La etiqueta se guarda en el evento (auditoría) y se oculta en la API mientras la partida está en curso.

## Persistencia y auditoría
`data/combate.db` (tablas `partidas`, `eventos`). Cada evento enlaza el hash del anterior; `verificar_cadena(pid)` detecta cualquier
alteración. El resultado es el evento `partida.resultado`. Los escenarios se congelan por hash al iniciar.

## Qué NO cambió
Las capas deterministas de datos (`permisos`, `herramientas`, `repositorio`), el buzón, las misiones y la UI de escritorio siguen
como estaban; el combate es un módulo nuevo que respeta el mismo principio y se publica en `/combate/`.
