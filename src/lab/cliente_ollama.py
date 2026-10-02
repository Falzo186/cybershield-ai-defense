"""Única conexión real con Ollama (stdlib: urllib). Nunca inventa datos: ante fallo devuelve ok=False."""
import json
import time
import urllib.error
import urllib.request


def _get_json(host, ruta, timeout):
    with urllib.request.urlopen(host.rstrip("/") + ruta, timeout=timeout) as r:
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


def extraer_json(texto):
    """Devuelve un dict si el texto es (o contiene) un objeto JSON; si no, None. No reconstruye nada."""
    if not isinstance(texto, str):
        return None
    for candidato in (texto, texto[texto.find("{"): texto.rfind("}") + 1] if "{" in texto else ""):
        try:
            obj = json.loads(candidato)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            return obj
    return None


def generar(host, modelo, system, user, formato=None, timeout=60, temperature=0.7, num_predict=300):
    """-> {ok, contenido, tiempo_ms, tokens, error}"""
    t0 = time.perf_counter()

    def resultado(ok, contenido=None, tokens=None, error=None):
        return {"ok": ok, "contenido": contenido, "tiempo_ms": int((time.perf_counter() - t0) * 1000),
                "tokens": tokens, "error": error}

    cuerpo = {
        "model": modelo, "stream": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    if formato == "json":
        cuerpo["format"] = "json"
    req = urllib.request.Request(
        host.rstrip("/") + "/api/chat", data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return resultado(False, error=f"HTTP {r.status}")
            datos = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return resultado(False, error=f"HTTP {exc.code}: {exc.reason}")
    except Exception as exc:  # noqa: BLE001 - timeout, conexión rechazada, JSON inválido...
        return resultado(False, error=f"{type(exc).__name__}: {exc}")
    contenido = (datos.get("message") or {}).get("content")
    if not isinstance(contenido, str) or not contenido.strip():
        return resultado(False, error="respuesta vacía del modelo")
    tokens = datos.get("eval_count")
    return resultado(True, contenido, tokens if isinstance(tokens, int) else None)
