# Wazuh simulado

> **Todo lo de este documento es una SIMULACIÓN.** No es Wazuh. La etiqueta «WAZUH SIMULADO» aparece en código, API, logs, UI y capturas.

## Qué hay
`src/lab/wazuh_sim/`:
- `WazuhProvider` (interfaz): `listar_agentes()`, `consultar_alertas(partida_id, desde, nivel_min, grupos, agente, limite)`, `estado()`.
- `SimProvider`: alimentado por los eventos del motor; persistencia en SQLite (indexada por `partida_id`) y NDJSON append-only.
- `RealProvider`: **solo contrato y stub**. Lee `WAZUH_URL`, `WAZUH_USUARIO`, `WAZUH_CLAVE`; sin ellas dice `desconectado`; con ellas pero sin
  implementación dice `con_errores`. No inventa respuestas.

## Modelo de datos
Agentes ficticios `srv-correo`, `srv-rrhh`, `ws-contabilidad-01`, `srv-bd` (IP privada, SO, grupo). Alertas con `id` determinista
(hash de partida+turno+regla+evento), `timestamp` ISO con zona, `rule{id,level,description,groups,mitre{id,tactic,technique}}`,
`agent`, `manager`, `decoder`, `location`, `full_log`, `data` y el campo propio `lab{partida_id,turno,simulado:true,etiqueta}`.

## Reglas (ids 100000+, propias)
Señales **observables** de una solicitud (100010 referencia no registrada · 100011 identidad inconsistente · 100012 fuera de alcance ·
100013 urgencia · 100014 patrón repetido) y consecuencias en el estado (100020 bloqueo por política · 100021 aprobación delegada · 100022
campo protegido · 100023 restablecimiento · 100024 documento liberado · 100025 excepción · 100030 contención · 100031 escalada · 100040
rutina). MITRE ATT&CK (T1566, T1078, T1548, T1565, T1098, T1213, T1562) solo como etiqueta educativa. Las señales se calculan con hechos
que el sistema ve, **nunca** con la verdad de fondo: una alerta no prueba por sí sola que algo sea malicioso (algunas legítimas la disparan).

## Ruido y señal
Por cada alerta relevante se generan 3–6 alertas benignas de nivel 1–4 (reproducibles con la semilla y el id del evento). La verdad de
fondo `relevante` se guarda en un canal oculto (`verdad_de_fondo`, `alertas_relevantes`) que **ningún modelo recibe** y que `consultar_alertas`
no devuelve. Esto hace que detectar no sea trivial: en las partidas con 8B el ruido provoca falsos positivos del Azul (p. ej. escalar una
solicitud legítima por una «actividad inusual» que era ruido).

## Integración
Azul recibe un resumen de las últimas alertas (turno actual y anterior, ≤ 10) en cada decisión; **Rojo no ve Wazuh** (probado). El espectador y el árbitro lo ven
en solo lectura en `/combate/` → «Wazuh (simulado)». Contención: el Azul puede indicar `contener_agente`; el motor la marca correcta si hay una alerta
relevante reciente en ese agente y falso positivo si no.

## Qué falta para uno real
Implementar `RealProvider` sobre la API del manager (JWT, :55000) y el indexador (:9200) — el adaptador de solo lectura ya existe en `src/lab/wazuh/`
(etapa anterior) —, desplegar las reglas de `integraciones/wazuh/local_rules.xml` y escribir una prueba de humo condicional. No hay instancia en este
laboratorio: esa prueba está **omitida** (`OMITIDA … no hay WAZUH_URL`).

## Pruebas
`src/lab/test_wazuh_sim.py` (19): esquema, idempotencia, correlación por partida, ruido reproducible, ocultación de la verdad de fondo, `RealProvider`.
En el motor: el Rojo no recibe alertas; el Azul sí, etiquetadas como simuladas.
