"""CLI de UNA partida del modo Caminos.
  python -m src.lab.caminos.jugar --grafo caminos-sencillo --rojo primera --azul registro
  python -m src.lab.caminos.jugar --grafo caminos-sencillo --rojo qwen3:8b --azul llama3.1:8b --semilla 1
Proveedores: guion:a,b,c · primera · aleatorio · registro · aprobar · rechazar · sin_respuesta · <modelo de Ollama>
"""
import argparse
import json
import sys

from . import grafo as G, proveedores as P
from .motor import PartidaCaminos
from ..combate.modelos import HOST_DEFECTO
from ..combate.store import Almacen
from ..wazuh_sim import SimProvider


def guion_de_camino(g, camino):
    """Camino [(nodo, opcion)] -> (Guion Rojo, Guion Azul) con las decisiones de cada lado en orden."""
    rojo = [o for n, o in camino if g["nodos"][n]["actor"] == "rojo"]
    azul = [o for n, o in camino if g["nodos"][n]["actor"] == "azul"]
    return P.Guion(rojo, "guion_rojo"), P.Guion(azul, "guion_azul")


def jugar(grafo, rojo, azul, semilla=1, host=HOST_DEFECTO, db=None, wazuh=True, etiquetas=None):
    g = G.cargar(grafo) if isinstance(grafo, str) else grafo
    r = P.construir(rojo, "rojo", semilla, host) if isinstance(rojo, str) else rojo
    a = P.construir(azul, "azul", semilla, host) if isinstance(azul, str) else azul
    sim = SimProvider(ruta_ndjson=None, ruta_db=":memory:", semilla=semilla) if wazuh else None
    p = PartidaCaminos(g, r, a, semilla=semilla, almacen=Almacen(db or ":memory:"), wazuh=sim, etiquetas=etiquetas)
    p.jugar()
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grafo", default="caminos-sencillo", choices=G.listar())
    ap.add_argument("--rojo", required=True)
    ap.add_argument("--azul", required=True)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--host", default=HOST_DEFECTO)
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = jugar(a.grafo, a.rojo, a.azul, a.semilla, a.host, a.db)
    r = p.resultado
    print(json.dumps({k: r[k] for k in ("resultado", "motivo", "tipo", "hoja", "camino", "turnos_jugados", "partida_id")}, ensure_ascii=False, indent=1))
    return 0 if r["resultado"] != "ERROR_TECNICO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
