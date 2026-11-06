# Integración con Wazuh

Módulos: [`src/lab/wazuh/`](../src/lab/wazuh/) (`__init__.py`, `cliente.py`, `reglas.py`) ·
Configuración y reglas: [`integraciones/wazuh/`](../integraciones/wazuh/) ·
Pruebas: `python -m src.lab.test_wazuh` (48/48) y `python integraciones/wazuh/test_reglas.py` (14/14).

> **No hay ningún Wazuh instalado ni conectado en esta máquina.** Lo que está comprobado son los contratos
> y el modo simulado. Nada en el panel ni en este documento presenta una alerta sintética como real.

## Los tres modos

Se eligen con la variable de entorno **`CYBERSHIELD_WAZUH`**. Un valor desconocido se trata como
`desactivado`; **nunca** como `real`.

| Modo | Qué hace | ¿Alertas? |
|---|---|---|
| `desactivado` (**por defecto**) | El laboratorio funciona igual y no se consulta ningún Wazuh | ninguna |
| `simulado` | Deduce alertas de los eventos del laboratorio aplicando las reglas locales con un modelo aproximado | **marcadas como simuladas** |
| `real` | Se conecta a una instalación de Wazuh y lee su estado | de Wazuh |

```bash
# PowerShell
$env:CYBERSHIELD_WAZUH = "simulado"
# bash
export CYBERSHIELD_WAZUH=real WAZUH_URL=https://192.168.1.50:55000 WAZUH_USUARIO=lector WAZUH_CLAVE=...
```

### La regla que no se rompe

**En modo `real` sin conexión, el resultado es un error visible.** No se devuelven alertas simuladas en su
lugar, ni se cambia de modo por detrás. La respuesta lo dice literalmente: *«Modo real sin conexión con
Wazuh. No se muestran alertas simuladas en su lugar.»* Hay una prueba para eso.

Cada alerta lleva `origen` (`"wazuh_real"` | `"simulado"`) y `simulado` (bool), y `estado()` dice siempre
qué modo está activo. Una prueba comprueba que **ninguna** alerta del modo simulado sale con
`origen: "wazuh_real"`.

## Arquitectura

```
aplicación Python  →  data/eventos.jsonl (JSON por línea, 11 campos)
                            ↓  agente Wazuh (ossec_localfile.xml, log_format json)
                      manager Wazuh  ←  local_rules.xml (18 reglas, ids 100100-100140)
                            ↓  API REST (solo lectura)
                      cliente.ClienteWazuh  →  panel de observabilidad
```

El punto de emisión no ha cambiado: `Repositorio.registrar` escribe la auditoría en SQLite (fuente de
verdad) y la misma línea en `data/eventos.jsonl`. 26 tipos de evento, todos con regla propia.

### Eventos que se monitorizan

Inicio y fin de partida · clic en enlace de phishing y clic bloqueado · contención de enlaces · reporte de
correos y PDF · apertura de PDF · credencial comprometida y revocada · incidentes (abierto, actualizado,
resuelto) · misiones · ataques IA lanzados y su resultado (datos expuestos, IA engañada, contenido, fallo
seguro) · configuración del defensor IA · rondas de práctica · autorizaciones denegadas.

Los eventos **no contienen secretos**: llevan usuario, rol, tipo, acción, recurso, resultado y nivel de
riesgo, nunca el valor de un dato consultado.

## El cliente es de solo lectura, y se comprueba

`cliente.ClienteWazuh` solo emite **GET** (más el POST de autenticación que la API de Wazuh exige) y solo
contra una lista cerrada de rutas: `/manager/status`, `/manager/info`, `/agents`, `/rules`,
`/security/user/authenticate`.

- Un método que no sea GET se rechaza **antes de salir a la red** (`ErrorWazuh: este cliente es de solo
  lectura`).
- Una ruta fuera de la lista se rechaza igual: **no hay forma de llamar a `/active-response`**.
- No existe ninguna función de reinicio, escritura o respuesta activa. Hay una prueba que lo verifica
  recorriendo los métodos del objeto.
- Las credenciales se leen de `WAZUH_USUARIO` / `WAZUH_CLAVE` y **no se registran ni se devuelven**.
- El token JWT se reutiliza (dura 900 s; se renueva a los 800) en vez de autenticarse en cada consulta.
- Un fallo de red devuelve `{ok: False, datos: None, error: "..."}`. **Nunca datos de relleno.**

El TLS se verifica por defecto. Desactivarlo (`WAZUH_TLS=0`, para un certificado autofirmado de laboratorio)
es una decisión explícita del operador.

## Modo simulado: qué es exactamente

`reglas.py` carga `local_rules.xml` y lo aplica con un **modelo simplificado**: decodificador JSON, campos
comparados con expresiones regulares y descenso por `if_sid`. **No simula** correlaciones
(`frequency` / `if_matched_sid`, es decir la regla 100136), ni listas CDB, ni la sintaxis completa de
OS_Regex. Las reglas del laboratorio solo usan `^`, `$` y `|`, que aquí significan lo mismo.

Ese mismo módulo lo usan el modo simulado **y** `integraciones/wazuh/test_reglas.py`, para que no haya dos
modelos de las mismas reglas que se desincronicen.

Resultado real del modo simulado sobre los 12 eventos de ejemplo (una partida jugada con el Ollama falso):
3 alertas de nivel ≥ 6, entre ellas `100132` nivel 12 (datos expuestos por la IA de Rojo), `100114` nivel 12
(credencial comprometida) y `100111` nivel 8 (clic en enlace de phishing).

## Cómo conectar un Wazuh real

1. En la máquina del laboratorio, con el agente instalado, añade el contenido de `ossec_localfile.xml` a
   `ossec.conf` corrigiendo la ruta a `data/eventos.jsonl`. Reinicia el agente.
2. En el manager, añade `local_rules.xml` a `/var/ossec/etc/rules/local_rules.xml` y reinicia
   (`systemctl restart wazuh-manager`).
3. Comprueba con `/var/ossec/bin/wazuh-logtest`: pega una línea de `eventos_ejemplo.jsonl` y confirma regla
   y nivel contra lo que imprime `test_reglas.py`.
4. Crea un usuario de **solo lectura** en Wazuh y exporta `WAZUH_URL`, `WAZUH_USUARIO`, `WAZUH_CLAVE`.
5. `CYBERSHIELD_WAZUH=real` y comprueba el estado en el panel.

**Requisitos supuestos, sin verificar:** Wazuh 4.x (la regla de correlación usa `same_field`) y API en el
puerto 55000.

## Qué está comprobado y qué no

**Comprobado sin conexión (62 comprobaciones entre las dos suites):**
los XML son válidos y los ids únicos y del rango local; los 26 tipos de evento tienen regla propia (si
alguien añade un tipo sin regla, la prueba falla); las descripciones solo usan campos del contrato; los
niveles son válidos; las técnicas MITRE tienen formato correcto; los tres modos se comportan como se
describe; el cliente rechaza todo lo que no sea una lectura permitida; un fallo de conexión se ve.

**NO comprobado:** nada contra un Wazuh real. No se ha ejecutado `wazuh-logtest`, no se ha visto una alerta
en el panel de Wazuh, y la lectura de alertas del indexador **no está implementada** (en modo real el
cliente lee estado, agentes y reglas; la consulta de alertas devuelve una nota diciéndolo, no una lista
vacía disfrazada de «no hay alertas»).

## Limitaciones

- La correlación de Wazuh (regla 100136: tres autorizaciones denegadas de la misma partida en 120 s) **no
  se simula**: el modo simulado no la producirá nunca, aunque un Wazuh real sí.
- El modo real todavía no consulta alertas del indexador de Wazuh, solo el estado del manager.
- Si el agente está en otra máquina, `data/eventos.jsonl` debe ser legible por él; el laboratorio solo
  escribe en local.
- La integración es **de observación**. No ejecuta ninguna acción de respuesta sobre el sistema operativo,
  y el cliente está construido para que no pueda hacerlo.
