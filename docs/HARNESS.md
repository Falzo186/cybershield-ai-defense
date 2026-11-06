# Harness — agente controlado, observable y reproducible

Módulo: [`src/lab/harness.py`](../src/lab/harness.py) · Pruebas: `python -m src.lab.test_harness` (49/49).

## Qué resuelve

Antes de esta etapa, `motor.procesar_defensa` ejecutaba **una** pasada sin ningún techo: no había límite de
iteraciones, ni timeout global, ni presupuesto de tokens, ni detección de bucles, ni forma de cancelar. El
único tope eran `MAX_ATAQUES = 8` por partida y el timeout de 120 s por llamada HTTP.

El harness **no da más poder al modelo. Le pone techos y lo observa.**

## Qué puede y qué no puede hacer el modelo

| Puede | No puede |
|---|---|
| Proponer una de las **4** herramientas del catálogo cerrado | Ejecutar nada fuera de ese catálogo |
| Recibir el resultado o el motivo del bloqueo | Tocar el sistema operativo, archivos o la red |
| Pedir una corrección ante un error **técnico** suyo | Reintentar para rodear un permiso |
| Consumir tiempo, tokens y llamadas **hasta el techo** | Concederse permisos, ampliar presupuestos o saltarse una capa |

Las herramientas siguen siendo las funciones de Python de `herramientas.py`. El harness **no añade ninguna**:
`usar_herramienta` comprueba `herramientas.CATALOGO` y, si el nombre no está, bloquea en la capa `catalogo`
exactamente igual que el camino directo.

## Presupuestos

`harness.Presupuesto` (todos configurables):

| Campo | Por defecto | Qué corta |
|---|---|---|
| `max_iteraciones` | 3 | vueltas del ciclo decidir → ejecutar → diagnosticar |
| `max_llamadas_modelo` | 6 | llamadas a Ollama, incluidos los reintentos de JSON de `cliente_ollama` |
| `max_tokens_salida` | 4000 | tokens generados acumulados (`None` = sin techo) |
| `max_tokens_entrada` | `None` | tokens de prompt acumulados |
| `timeout_herramienta_s` | 30 | cada herramienta, por separado |
| `timeout_global_s` | 300 | la ejecución completa |
| `max_repeticiones_identicas` | 2 | la misma acción repetida → corte por bucle |

Los presupuestos se comprueban **antes de cada paso**, nunca después. `puede_continuar()` devuelve
`(bool, motivo)` y el motivo aparece tal cual en el estado final.

### Tokens que Ollama no informa

Si Ollama no envía `eval_count` / `prompt_eval_count`, el contador no suma nada: **no se estima**. El
presupuesto de tokens entonces no corta, y eso se ve en el estado (`tokens_salida` bajo con muchas llamadas).

## Ciclo de trabajo

1. Comprobar presupuesto. Si está agotado o cancelado → corte limpio y clasificado.
2. Comprobar que la solicitud no se está repitiendo.
3. Llamar al camino de defensa (`motor.procesar_defensa`): filtro rápido → defensor IA → circuito de sesión →
   capas deterministas → veredicto → diagnóstico.
4. Contabilizar la llamada, sus tokens y su tiempo.
5. Comprobar si la propuesta del defensor es idéntica a una anterior → corte por bucle.
6. Decidir si procede una corrección (§ siguiente). Si no, terminar.

El resultado tiene **la misma forma** que `motor.procesar_defensa` (veredicto, defensa, ejecucion,
diagnostico…) más una clave `harness`. Por eso los dos caminos son comparables sin tocar nada aguas abajo.

## El reintento nunca sortea un permiso

Esta es la regla de seguridad del módulo. Solo se concede una corrección ante un error **técnico**:

| Diagnóstico | ¿Se reintenta? | Por qué |
|---|---|---|
| `ERROR_FORMATO` | **sí** | El modelo no produjo JSON utilizable: no hubo propuesta que evaluar |
| `ERROR_CATALOGO` | solo si la identidad **real** tiene derecho a esa herramienta | Si no lo tiene, el bloqueo es de política |
| `ERROR_PARAMETRO` | solo si la identidad **real** tiene derecho a esa herramienta | Igual |
| `ERROR_PERMISO` | **nunca** | Reintentar sería amplificar el ataque |
| `ERROR_AUTORIZACION` | **nunca** | Igual |
| Todo lo demás | no | Timeouts, infraestructura, fuga, defensa correcta |

El derecho se comprueba con `permisos.evaluar_acceso` sobre la identidad que fija el sistema, no con lo que
diga el modelo. Hay pruebas para cada una de esas filas.

## Estados finales

`terminado` · `agotado` (algún techo) · `cancelado` · `bucle` · `error` (excepción capturada).

Una ejecución cortada **conserva el último resultado útil**: si ya hubo una decisión, se devuelve esa; si no
hubo ninguna, el veredicto es `ERROR` con `error: "harness: …"`, y su diagnóstico queda **fuera del
denominador de exactitud del modelo** (un corte del harness no es un fallo de razonamiento).

## Cancelación

`Ejecucion.cancelar(motivo)` marca un `threading.Event`. La cancelación se atiende **entre pasos**: no se mata
ningún hilo a medias ni se deja la BD inconsistente.

## Timeout por herramienta: limitación honesta

`usar_herramienta` lanza la herramienta en un hilo *daemon* y espera con `join(timeout)`. Si el tiempo se
agota, **el hilo sigue vivo**: Python no permite matar un hilo. Lo que hace el harness es dejar de esperar,
descartar el resultado y registrar `timeout: true`. Para las herramientas de este laboratorio (lecturas de
SQLite sobre decenas de filas) la situación es teórica, pero el límite está documentado y probado.

Un timeout **nunca** se disfraza de bloqueo de capa: devuelve `capa_bloqueo: None` y un `error` explícito.

## Estado serializable

`Ejecucion.a_json()` devuelve presupuesto, consumo (iteraciones, llamadas, tokens, ms), la lista completa de
`pasos` (modelo / herramienta / decisión / corte, con duración, detalle y error), `herramientas_usadas` y
`errores`. Es JSON puro: se puede guardar, inspeccionar o usar para reanudar.

```json
{"estado": "bucle", "motivo_corte": "el defensor repitió la misma propuesta",
 "consumo": {"iteraciones": 3, "llamadas_modelo": 3, "tokens_salida": 60, "transcurrido_ms": 41},
 "herramientas_usadas": [], "errores": []}
```

## Comparación con el camino directo

Pendiente de medir con Ollama real. El motor de evaluación autónoma (`docs/EVALUACION_AUTONOMA.md`) ejecuta
los dos caminos sobre los mismos escenarios y la misma semilla. **No se da por supuesto que el harness sea
mejor**: cuesta llamadas extra y solo puede ayudar cuando el fallo es de formato. Hasta que haya una campaña
real ejecutada, este documento no publica ninguna cifra de comparación.

## Limitaciones conocidas

- El harness envuelve el camino de defensa completo, no cada herramienta por separado dentro de una
  conversación multi-turno: hoy el defensor decide en una sola pasada y el ciclo sirve para corregir, no para
  que el modelo encadene herramientas. Ampliarlo a multi-turno es un cambio de prompt, no de este módulo.
- Un hilo de herramienta que se pase del timeout no se cancela (arriba).
- Todavía no está conectado a las rutas del servidor: se usa desde el motor de evaluación. Conectarlo a la
  batalla de la partida cambiaría el coste por ronda y debe medirse antes.
