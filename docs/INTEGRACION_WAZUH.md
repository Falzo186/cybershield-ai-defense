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

Son **dos servicios distintos** y los dos hacen falta. El *manager* (puerto 55000) da estado, agentes y
reglas; el *indexador* (OpenSearch, puerto 9200) es donde están las alertas. Conectar solo el manager deja
el panel sin alertas, y lo dice con esas palabras en vez de mostrar una lista vacía.

### 1 · Agente y reglas (manager)

1. En la máquina del laboratorio, con el agente instalado, añade el contenido de `ossec_localfile.xml` a
   `ossec.conf` corrigiendo la ruta a `data/eventos.jsonl`. Reinicia el agente.
2. En el manager, añade `local_rules.xml` a `/var/ossec/etc/rules/local_rules.xml` y reinicia
   (`systemctl restart wazuh-manager`).
3. Comprueba con `/var/ossec/bin/wazuh-logtest`: pega una línea de `eventos_ejemplo.jsonl` y confirma regla
   y nivel contra lo que imprime `test_reglas.py`.

### 2 · Usuarios de solo lectura

Crea **dos** usuarios, uno por servicio, y dale a cada uno solo lectura:

- API del manager: un usuario con el rol `readonly` (Security → Users en el panel de Wazuh).
- Indexador: un usuario con permiso de lectura sobre `wazuh-alerts-*` y nada más. Basta un rol con
  `indices:data/read/search` sobre ese patrón de índice.

No reutilices el usuario administrador. El laboratorio no necesita escribir nada, y el cliente está
construido para que no pueda: rechaza cualquier ruta que no sea `_search`, `_count` o el saludo del nodo
**antes** de abrir el socket.

### 3 · Variables de entorno

| Variable | Para qué | Ejemplo |
|---|---|---|
| `CYBERSHIELD_WAZUH` | Modo de la integración | `real` |
| `WAZUH_URL` | API del manager | `https://wazuh.interno:55000` |
| `WAZUH_USUARIO` / `WAZUH_CLAVE` | Usuario de solo lectura de la API | — |
| `WAZUH_INDEXER_URL` | Indexador (OpenSearch) | `https://wazuh.interno:9200` |
| `WAZUH_INDEXER_USUARIO` / `WAZUH_INDEXER_CLAVE` | Usuario de solo lectura del indexador | — |
| `WAZUH_INDEXER_INDICE` | Patrón de índice | `wazuh-alerts-*` (por defecto) |
| `WAZUH_TLS` | `0` desactiva la verificación del certificado | solo con certificado autofirmado |

Si no se indican las credenciales del indexador, se reutilizan las del manager; es lo habitual en una
instalación de un solo nodo, pero lo recomendable sigue siendo dos usuarios distintos.

**Ningún secreto se versiona.** Las credenciales se leen del entorno, no se escriben en ningún registro y
no salen en ninguna estructura que devuelva la aplicación.

### 4 · Comprobarlo

```
python integraciones/wazuh/test_indexador_real.py
```

Esta prueba **no está en la batería**, y es deliberado: aquí no hay ningún Wazuh, así que incluirla
«saltada en verde» haría que el informe dijera que la integración real está probada cuando no lo está.
Sin las variables anteriores termina con el código 2 y el mensaje «NO EJECUTADA»: ni éxito ni fallo, **no
comprobado**. Con ellas, comprueba contra la instalación de verdad que los dos servicios responden, que las
reglas del laboratorio están cargadas, que una búsqueda devuelve documentos con la forma esperada, que toda
alerta leída viene marcada como real, y que el cliente sigue negándose a cualquier escritura.

**Requisitos supuestos, sin verificar:** Wazuh 4.x (la regla de correlación usa `same_field`), API en el
puerto 55000 e indexador en el 9200 con índices `wazuh-alerts-*`.

## Qué está comprobado y qué no

**Comprobado sin conexión:** los XML son válidos y los ids únicos y del rango local; los 28 tipos de evento
tienen regla propia (si alguien añade un tipo sin regla, la prueba falla); las descripciones solo usan
campos del contrato; los niveles son válidos; las técnicas MITRE tienen formato correcto; los tres modos se
comportan como se describe; el cliente del manager y el del indexador rechazan todo lo que no sea una
lectura permitida; la normalización de un documento del indexador no inventa ningún valor; un fallo de
conexión se ve y **nunca** se sustituye por alertas simuladas.

**NO comprobado:** nada contra un Wazuh real. No se ha ejecutado `wazuh-logtest`, no se ha visto una alerta
en el panel de Wazuh y no se ha leído un índice `wazuh-alerts-*` de verdad. Lo que hay es el cliente, el
contrato y una prueba de integración lista para ejecutarse el día que exista la instalación.

## Limitaciones

- La correlación de Wazuh (regla 100136: tres autorizaciones denegadas de la misma partida en 120 s) **no
  se simula**: el modo simulado no la producirá nunca, aunque un Wazuh real sí.
- Una búsqueda en el indexador es un `POST` porque la consulta viaja en el cuerpo. Es la única excepción al
  «solo GET», está acotada a `_search` y `_count`, y sigue siendo una lectura.
- Si el agente está en otra máquina, `data/eventos.jsonl` debe ser legible por él; el laboratorio solo
  escribe en local.
- La integración es **de observación**. No ejecuta ninguna acción de respuesta sobre el sistema operativo,
  y los dos clientes están construidos para que no puedan hacerlo.
