# Máquina de estados · Partida (`server/partida.py`, fase `Partida.fase`)
El servidor es la única fuente de verdad; la interfaz solo pinta lo que el servidor difunde (`partida_estado`, SSE) y nunca declara un estado por su cuenta.

Mapa con los estados pedidos por el encargo: CREADA/CONFIGURANDO/ESPERANDO_JUGADORES/LISTA = `preparacion` (la partida nace así y espera al árbitro; no hay inferencias ni reloj). FINALIZANDO es instantáneo (la transición `finalizar` es atómica). CANCELADA y ERROR **no existen como estados**: ver `known_issues.md`.

| Origen | Evento | Destino | Actor | Condiciones / efectos | Errores |
|---|---|---|---|---|---|
| (nace) | crear | `preparacion` | servidor / árbitro (`nueva`) | `nueva` solo desde `finalizada`; correos, misiones y marcador empiezan de cero | 409 si no está finalizada |
| `preparacion` | `iniciar(5\|10\|15)` | `en_curso` | **solo árbitro** | arranca el reloj del servidor, el vigilante de tiempo y la entrega de correos del escenario | 403 otro equipo; 409 si ya empezó; 400 duración |
| `en_curso` | `pausar` | `pausada` | solo árbitro | congela el tiempo restante; cancela el vigilante; las acciones nuevas dan 409; una inferencia ya lanzada puede terminar | 409 si no está en curso |
| `pausada` | `reanudar` | `en_curso` | solo árbitro | continúa desde el tiempo guardado; reinicia vigilante y escenario | 409 si no está pausada |
| `en_curso`/`pausada` | `finalizar` / vence el tiempo | `finalizada` | árbitro / sistema | congela puntajes, declara ganador, cancela la inferencia en curso (su respuesta tardía no cuenta) | 409 si ya finalizó o no empezó |

Garantías verificadas: `server/test_partida.py` (80), regresión 1–4, 19–21, 25 (`tests/regression`).
