"""API de la ventana «Simulación» (/api/simulacion/*): catálogo y registros de partidas del modo Caminos grabadas en data/simulaciones/.

Solo lectura y pública (como las demás vistas de observación). Un registro NO se regenera: se sirve tal como se grabó, con su cadena de
hashes recomprobada en cada lectura y su procedencia (`tipo`) siempre visible.
"""
import hashlib
import json
import os
import threading
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

from src.lab import cliente_ollama
from src.lab.caminos import auto as AUTO, grafo as GRAFO, proveedores as PROV
from src.lab.caminos.motor import PartidaCaminos
from src.lab.combate.store import Almacen
from src.lab.wazuh_sim import SimProvider

RAIZ = Path(__file__).resolve().parents[1]
DIR = RAIZ / "data" / "simulaciones"


def _canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def verificar_cadena(partida_id, eventos):
    """Recalcula la cadena de hashes (misma fórmula que combate.store). -> (ok, mensaje)."""
    prev = "0" * 64
    for e in eventos:
        h = hashlib.sha256((prev + _canon([partida_id, e["seq"], e["turno"], e["tipo"], e["payload"]])).encode("utf-8")).hexdigest()
        if e["hash_prev"] != prev or e["hash"] != h:
            return False, f"cadena rota en seq {e['seq']}"
        prev = e["hash"]
    return True, "cadena íntegra"


def _cargar(id_):
    if id_ and id_.startswith("vivo-") and not any(c in id_ for c in "/\\"):
        return _detalle_vivo(id_[5:])
    if not id_ or any(c in id_ for c in "/\\.") or not id_.startswith("sim-"):
        return None
    f = DIR / f"{id_}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


_ACTUAL = {"id": None, "hilo": None, "error": None}
_CERROJO = threading.Lock()
SIMPLES = ("registro", "aprobar", "rechazar", "aleatorio", "primera", "sin_respuesta")


def _db():
    return Almacen(os.environ.get("CS_CAMINOS_DB") or (RAIZ / "data" / "caminos.db"))


def _detalle_vivo(pid):
    """Detalle de una partida jugada desde la interfaz (mismo formato que una grabación), leída de la base con su cadena de hashes."""
    alm = _db()
    p = alm.partida(pid)
    if not p or not p["resultado"]:
        return None
    ev = alm.eventos(pid)
    cfg = p["config"]
    g = GRAFO.cargar(p["escenario_id"]) if str(p["escenario_id"]).startswith("caminos-") else None
    return {"id_simulacion": "vivo-" + pid, "titulo": "Partida lanzada desde la interfaz", "tipo": cfg.get("tipo"), "procedencia": ("CAMINOS_IA: un modelo eligió opciones; el motor decidió" if cfg.get("tipo") == "CAMINOS_IA"
            else "CAMINOS_GUION: guiones o líneas base deterministas"), "modelos": {"rojo": cfg.get("rojo"), "azul": cfg.get("azul")}, "semilla": cfg.get("semilla"),
            "dificultad": cfg.get("dificultad") or "auto", "hash_grafo": p["hash_escenario"], "hoja": (p["resultado"] or {}).get("hoja"), "grafo": g, "modo": "auto" if cfg.get("modo") == "automatico" else "grafo",
            "partida": {**p, "id": pid}, "eventos": ev, "alertas_wazuh_simuladas": []}


def _resumen(d):
    r = (d["partida"].get("resultado") or {})
    return {"modo": d.get("modo", "grafo"), "id": d["id_simulacion"], "titulo": d["titulo"], "tipo": d["tipo"], "procedencia": d["procedencia"], "modelos": d["modelos"], "semilla": d["semilla"],
            "dificultad": d["dificultad"], "hoja": d.get("hoja") or r.get("hoja"), "resultado": r.get("resultado"), "reversion": r.get("reversion", False),
            "giro": r.get("giro", False), "hash_grafo": d["hash_grafo"], "eventos": len(d["eventos"])}


def _modelo_ok(spec, rol, host):
    if spec in SIMPLES:
        return True, None
    if not cliente_ollama.ollama_disponible(host):
        return False, f"Ollama no responde en {host}: no se inicia la partida con un modelo real"
    if spec.split("@")[0] not in cliente_ollama.listar_modelos(host):
        return False, f"el modelo «{spec}» no está instalado en Ollama"
    return True, None


def _correr(modo, rojo, azul, semilla, dif, host, pid_box):
    try:
        r = PROV.construir(rojo, "rojo", semilla, host)
        a = PROV.construir(azul, "azul", semilla, host)
        w = SimProvider(ruta_ndjson=None, ruta_db=":memory:", semilla=semilla)
        p = (PartidaCaminos(GRAFO.cargar(f"caminos-{dif}"), r, a, semilla=semilla, almacen=_db(), wazuh=w) if modo == "grafo"
             else AUTO.PartidaAuto(r, a, semilla=semilla, almacen=_db(), wazuh=w))
        pid_box.append(p.id)
        p.jugar()
    except Exception as exc:  # noqa: BLE001
        _ACTUAL["error"] = f"{type(exc).__name__}: {exc}"


def registrar(app, host_ollama="http://127.0.0.1:11434"):
    @app.get("/api/simulacion/catalogo")
    async def sim_catalogo():
        out = []
        for f in sorted(DIR.glob("sim-*.json")) if DIR.is_dir() else []:
            d = _cargar(f.stem)
            if d:
                out.append(_resumen(d))
        orden = {"VICTORIA_ROJA": 0, "VICTORIA_AZUL": 1}
        out.sort(key=lambda x: (0 if x["tipo"] == "CAMINOS_IA" and x["resultado"] == "VICTORIA_ROJA" else 1, orden.get(x["resultado"], 2), x["id"]))
        return JSONResponse({"simulaciones": out, "nota": "Registros de partidas ejecutadas por el motor; la reproducción solo reproduce lo registrado."})

    @app.get("/api/caminos/estado")
    async def caminos_estado():
        disp = cliente_ollama.ollama_disponible(host_ollama)
        a = _ACTUAL
        return JSONResponse({"ollama": {"disponible": disp, "modelos": cliente_ollama.listar_modelos(host_ollama) if disp else []}, "simples": list(SIMPLES), "dificultades": ["sencillo", "intermedio", "complejo"],
                             "actual": {"id": a["id"], "viva": bool(a["hilo"] and a["hilo"].is_alive()), "error": a["error"]} if a["hilo"] else None})

    @app.post("/api/caminos/partidas")
    async def caminos_crear(request: Request, cuerpo: dict):
        """Solo el árbitro: lanza UNA partida del modo Caminos (grafo o automático) en segundo plano. Procedencia declarada en el resultado."""
        if request.state.equipo != "general":
            return JSONResponse({"error": "Solo el árbitro (equipo general) puede lanzar partidas de Caminos."}, status_code=403)
        modo, rojo, azul = str(cuerpo.get("modo") or "grafo"), str(cuerpo.get("rojo") or ""), str(cuerpo.get("azul") or "")
        if modo not in ("grafo", "auto"):
            return JSONResponse({"error": "modo debe ser «grafo» o «auto»"}, status_code=400)
        dif = str(cuerpo.get("dificultad") or "sencillo")
        if modo == "grafo" and dif not in ("sencillo", "intermedio", "complejo"):
            return JSONResponse({"error": "dificultad desconocida"}, status_code=400)
        for spec, rol in ((rojo, "rojo"), (azul, "azul")):
            ok, msg = _modelo_ok(spec, rol, host_ollama)
            if not ok:
                return JSONResponse({"error": msg}, status_code=400 if "instalado" in msg else 503)
        try:
            semilla = int(cuerpo.get("semilla", 1))
        except (TypeError, ValueError):
            return JSONResponse({"error": "la semilla debe ser un entero"}, status_code=400)
        with _CERROJO:
            if _ACTUAL["hilo"] and _ACTUAL["hilo"].is_alive():
                return JSONResponse({"error": "ya hay una partida de Caminos en curso: espera a que termine"}, status_code=409)
            caja = []
            _ACTUAL.update(id=None, error=None)
            h = threading.Thread(target=_correr, args=(modo, rojo, azul, semilla, dif, host_ollama, caja), daemon=True)
            _ACTUAL["hilo"] = h
            h.start()
        for _ in range(100):
            if caja:
                break
            import time as _t
            _t.sleep(0.05)
        _ACTUAL["id"] = caja[0] if caja else None
        return JSONResponse({"id": _ACTUAL["id"], "ver": "vivo-" + (_ACTUAL["id"] or "")})

    @app.get("/api/simulacion/{sid}")
    async def sim_detalle(sid: str):
        d = _cargar(sid)
        if d is None:
            if sid.startswith("vivo-") and "/" not in sid and _db().partida(sid[5:]) is not None:
                return JSONResponse({"pendiente": True, "mensaje": "la partida sigue en curso"}, status_code=202)   # aún sin resultado: se reintenta
            return JSONResponse({"error": "simulación desconocida"}, status_code=404)
        ok, msg = verificar_cadena(d["partida"]["id"], d["eventos"])
        return JSONResponse({**_resumen(d), "cadena_integra": ok, "mensaje_cadena": msg, "partida_id": d["partida"]["id"], "eventos_registro": d["eventos"],
                             "alertas_wazuh_simuladas": d["alertas_wazuh_simuladas"], "grafo": d["grafo"], "resultado_detalle": d["partida"]["resultado"],
                             "ensena": (d["partida"]["resultado"] or {}).get("ensena")})
