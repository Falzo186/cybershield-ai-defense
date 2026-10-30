"""Única conexión real con Ollama (stdlib: urllib). Nunca inventa datos: ante fallo devuelve ok=False."""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

RUTA_DEBUG = Path(__file__).resolve().parents[2] / "data" / "debug_respuestas.log"
MENSAJE_REINTENTO = "Tu respuesta anterior no era JSON válido. Responde SOLO con el JSON, sin explicación."


def _ipv4_si_localhost(url):
    """En Windows, conectar a «localhost» hace que urllib pruebe antes ::1; si Ollama solo escucha en IPv4, cada
    llamada pierde ~2 s (medido: 2 350 ms frente a 350 ms con 127.0.0.1), y esos 2 s se contaban como latencia del
    modelo. -> la misma URL con 127.0.0.1, o None si el host no es localhost."""
    u = urllib.parse.urlsplit(url)
    if u.hostname != "localhost":
        return None
    return urllib.parse.urlunsplit((u.scheme, "127.0.0.1" + (f":{u.port}" if u.port else ""), u.path, u.query, u.fragment))


def _abrir(url, timeout, data=None):
    """urlopen con el atajo IPv4 para localhost; si 127.0.0.1 rechaza la conexión (Ollama solo en IPv6), se reintenta
    con la URL original, así que ninguna instalación que antes funcionara deja de hacerlo."""
    def peticion(u):
        if data is None:
            return u
        return urllib.request.Request(u, data=data, headers={"Content-Type": "application/json"}, method="POST")
    rapida = _ipv4_si_localhost(url)
    if rapida:
        try:
            return urllib.request.urlopen(peticion(rapida), timeout=timeout)
        except urllib.error.URLError as exc:
            if not isinstance(getattr(exc, "reason", None), ConnectionRefusedError):
                raise
    return urllib.request.urlopen(peticion(url), timeout=timeout)


def _get_json(host, ruta, timeout):
    with _abrir(host.rstrip("/") + ruta, timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def ollama_disponible(host):
    try:
        status, _ = _get_json(host, "/api/tags", 2)
        return status == 200
    except Exception:  # noqa: BLE001
        return False


def listar_modelos(host):
    try:
        status, datos = _get_json(host, "/api/tags", 2)
        if status != 200:
            return []
        return [m["name"] for m in datos.get("models", []) if isinstance(m.get("name"), str)]
    except Exception:  # noqa: BLE001
        return []


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def quitar_think(texto):
    """Elimina el razonamiento de modelos 'thinking' (qwen3 y similares): bloques <think>...</think>,
    un </think> sin apertura (se descarta todo lo anterior) o un <think> sin cierre (se descarta lo posterior)."""
    if not isinstance(texto, str):
        return ""
    t = _THINK.sub("", texto)
    bajo = t.lower()
    if "</think>" in bajo:
        t = t[bajo.rfind("</think>") + len("</think>"):]
    elif "<think>" in bajo:
        t = t[:bajo.find("<think>")]
    return t.strip()


def _primer_objeto(texto):
    """Primer bloque {...} con llaves balanceadas (respetando cadenas JSON) que sea un objeto JSON válido."""
    for m in re.finditer(r"\{", texto):
        prof, en_cadena, escape = 0, False, False
        for j in range(m.start(), len(texto)):
            c = texto[j]
            if en_cadena:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    en_cadena = False
            elif c == '"':
                en_cadena = True
            elif c == "{":
                prof += 1
            elif c == "}":
                prof -= 1
                if prof == 0:
                    try:
                        obj = json.loads(texto[m.start():j + 1])
                    except ValueError:
                        break
                    if isinstance(obj, dict):
                        return obj
                    break
    return None


def extraer_json(texto, requeridos=()):
    """Devuelve un dict si el texto es (o contiene) un objeto JSON; si no, None. No reconstruye nada.
    1) quita <think>…</think> y vallas ```json; 2) json.loads directo; 3) primer {...} balanceado; 4) None.
    Si faltan campos `requeridos`, también devuelve None (nunca un objeto a medias)."""
    if not isinstance(texto, str):
        return None
    limpio = re.sub(r"```[A-Za-z]*", "", quitar_think(texto)).strip()
    obj = None
    try:
        obj = json.loads(limpio)
    except ValueError:
        pass
    if not isinstance(obj, dict):
        obj = _primer_objeto(limpio)
    if obj is None or any(k not in obj for k in requeridos):
        return None
    return obj


def registrar_fallo_parseo(origen, modelo, texto):
    """Diagnóstico: guarda la respuesta cruda no parseable en data/debug_respuestas.log (nunca falla)."""
    try:
        RUTA_DEBUG.parent.mkdir(parents=True, exist_ok=True)
        with RUTA_DEBUG.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] origen={origen} modelo={modelo}\n"
                    f"<<<INICIO\n{texto}\nFIN>>>\n\n")
    except Exception:  # noqa: BLE001
        pass


def _sumar(a, b):
    """Suma dos métricas de Ollama; si falta alguna (None), el total es desconocido, no la mitad."""
    return a + b if isinstance(a, int) and isinstance(b, int) else None


def generar_json(host, modelo, system, user, requeridos, origen, **kw):
    """generar + extraer_json con UN solo reintento si la respuesta no es JSON válido con los campos requeridos.
    -> resultado de generar + {obj: dict|None, intentos: 1|2}. Tiempos, tokens y carga suman ambos intentos."""
    r = generar(host, modelo, system, user, formato="json", **kw)
    r.update(obj=None, intentos=1)
    if not r["ok"]:
        return r
    r["obj"] = extraer_json(r["contenido"], requeridos)
    if r["obj"] is not None:
        return r
    registrar_fallo_parseo(f"{origen} (intento 1)", modelo, r["contenido"])
    r2 = generar(host, modelo, system, MENSAJE_REINTENTO + "\n\n" + user, formato="json", **kw)
    r2["tiempo_ms"] += r["tiempo_ms"]
    for k in ("tokens", "tokens_entrada", "carga_ms"):
        r2[k] = _sumar(r.get(k), r2.get(k))
    r2.update(obj=None, intentos=2)
    if not r2["ok"]:
        return r2
    r2["obj"] = extraer_json(r2["contenido"], requeridos)
    if r2["obj"] is None:
        registrar_fallo_parseo(f"{origen} (intento 2, final)", modelo, r2["contenido"])
    return r2


# NOTA sobre el timeout (120 s por defecto): la PRIMERA llamada a un modelo puede tardar mucho porque Ollama
# lo carga en memoria/VRAM (y más aún por LAN); las llamadas siguientes son rápidas. Antes de iniciar una
# batalla conviene usar «Probar modelo» (GET /api/ollama/probar) para forzar esa carga inicial.
def generar(host, modelo, system, user, formato=None, timeout=120, temperature=0.7, num_predict=300):
    """-> {ok, contenido, tiempo_ms, tokens, tokens_entrada, carga_ms, error}

    tiempo_ms: reloj de pared medido aquí (petición completa). tokens = tokens de SALIDA (eval_count),
    tokens_entrada = prompt_eval_count y carga_ms = load_duration, tal como los informa Ollama; si Ollama no los
    envía (o la llamada falla) quedan en None: nunca se estiman."""
    t0 = time.perf_counter()

    def resultado(ok, contenido=None, datos=None, error=None):
        datos = datos or {}
        entero = lambda k: datos.get(k) if isinstance(datos.get(k), int) and not isinstance(datos.get(k), bool) else None  # noqa: E731
        carga = entero("load_duration")
        return {"ok": ok, "contenido": contenido, "tiempo_ms": int((time.perf_counter() - t0) * 1000),
                "tokens": entero("eval_count"), "tokens_entrada": entero("prompt_eval_count"),
                "carga_ms": carga // 1_000_000 if carga is not None else None, "error": error}

    # think: False -> los modelos 'thinking' (qwen3, deepseek-r1…) responden sin razonar. Ollama ya no pone el
    # razonamiento en <think> dentro de content sino en message.thinking, y ese razonamiento agotaba num_predict:
    # la respuesta salía cortada (done_reason=length) con content vacío. Los demás modelos lo ignoran.
    cuerpo = {
        "model": modelo, "stream": False, "think": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    if formato == "json":
        cuerpo["format"] = "json"
    try:
        with _abrir(host.rstrip("/") + "/api/chat", timeout, data=json.dumps(cuerpo).encode("utf-8")) as r:
            if r.status != 200:
                return resultado(False, error=f"HTTP {r.status}")
            datos = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Ollama explica el fallo en el cuerpo ({"error": "..."}): se muestra tal cual en vez de solo el código.
        try:
            detalle = json.loads(exc.read().decode("utf-8", "replace")).get("error")
        except Exception:  # noqa: BLE001 - cuerpo vacío o no JSON
            detalle = None
        return resultado(False, error=f"HTTP {exc.code}: {detalle or exc.reason}")
    except Exception as exc:  # noqa: BLE001 - timeout, conexión rechazada, JSON inválido...
        return resultado(False, error=f"{type(exc).__name__}: {exc}")
    # Se descarta el razonamiento <think> para que defensor y atacante reciban solo la respuesta útil.
    contenido = quitar_think((datos.get("message") or {}).get("content"))
    if not contenido:
        return resultado(False, error="modelo devolvió respuesta vacía (posible modelo 'thinking'); "
                                      "prueba con qwen2.5 o llama3.2")
    return resultado(True, contenido, datos)
