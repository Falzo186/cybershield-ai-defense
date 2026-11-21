"""API de la ventana «Simulación» (/api/simulacion/*): catálogo y registros de partidas del modo Caminos grabadas en data/simulaciones/.

Solo lectura y pública (como las demás vistas de observación). Un registro NO se regenera: se sirve tal como se grabó, con su cadena de
hashes recomprobada en cada lectura y su procedencia (`tipo`) siempre visible.
"""
import hashlib
import json
from pathlib import Path

from fastapi.responses import JSONResponse

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
    if not id_ or any(c in id_ for c in "/\.") or not id_.startswith("sim-"):
        return None
    f = DIR / f"{id_}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def _resumen(d):
    r = (d["partida"].get("resultado") or {})
    return {"id": d["id_simulacion"], "titulo": d["titulo"], "tipo": d["tipo"], "procedencia": d["procedencia"], "modelos": d["modelos"], "semilla": d["semilla"],
            "dificultad": d["dificultad"], "hoja": d.get("hoja") or r.get("hoja"), "resultado": r.get("resultado"), "reversion": r.get("reversion", False),
            "giro": r.get("giro", False), "hash_grafo": d["hash_grafo"], "eventos": len(d["eventos"])}


def registrar(app):
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

    @app.get("/api/simulacion/{sid}")
    async def sim_detalle(sid: str):
        d = _cargar(sid)
        if d is None:
            return JSONResponse({"error": "simulación desconocida"}, status_code=404)
        ok, msg = verificar_cadena(d["partida"]["id"], d["eventos"])
        return JSONResponse({**_resumen(d), "cadena_integra": ok, "mensaje_cadena": msg, "partida_id": d["partida"]["id"], "eventos_registro": d["eventos"],
                             "alertas_wazuh_simuladas": d["alertas_wazuh_simuladas"], "grafo": d["grafo"], "resultado_detalle": d["partida"]["resultado"],
                             "ensena": (d["partida"]["resultado"] or {}).get("ensena")})
