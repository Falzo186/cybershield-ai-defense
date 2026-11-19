"""Lanzador de UNA partida de combate (CLI). Ejemplos:

  python -m src.lab.combate.jugar --escenario verificacion_falsa-sencillo --rojo qwen3:8b --azul llama3.1:8b --semilla 1
  python -m src.lab.combate.jugar --escenario verificacion_falsa-sencillo --rojo falso:objetivos --azul falso:registro

Modelos «falso:*» son determinísticos (no usan Ollama). Cualquier otro nombre se pide a Ollama (`--host`).
"""
import argparse
import json
import sys

from . import escenarios as E, modelos as M
from .motor import Partida
from .store import Almacen, RUTA_POR_DEFECTO
from ..wazuh_sim import SimProvider
from ..wazuh_sim.proveedor import RAIZ as _RAIZ


def construir_rojo(spec, esc, semilla, host):
    if spec.startswith("falso:"):
        tipo = spec[6:]
        objs = [r for r in esc["recursos"] if r["objetivo_rojo"]]
        return {"objetivos": lambda: M.RojoObjetivos(objs),
                "fijo": lambda: M.RojoMensajeFijo(objs[0]["id"], objs[0]["accion"]),
                "aleatorio": lambda: M.RojoAleatorio(semilla)}[tipo]()
    return M.RojoOllama(spec, host=host, semilla=semilla)


def construir_azul(spec, semilla, host):
    if spec.startswith("falso:"):
        tipo = spec[6:]
        return {"registro": M.AzulRegistro, "rechazar": lambda: M.AzulFijo("RECHAZAR"), "aprobar": lambda: M.AzulFijo("APROBAR"),
                "solicitar": lambda: M.AzulFijo("SOLICITAR_AUTORIZACION"), "aleatorio": lambda: M.AzulAleatorio(semilla),
                "credulo": M.AzulCaeEnTodo}[tipo]()
    return M.AzulOllama(spec, host=host, semilla=semilla)


def jugar(escenario, rojo, azul, semilla=1, host=M.HOST_DEFECTO, db=None, wazuh=True, etiquetas=None, callback=None):
    esc = E.cargar(escenario)
    r = construir_rojo(rojo, esc, semilla, host) if isinstance(rojo, str) else rojo
    a = construir_azul(azul, semilla, host) if isinstance(azul, str) else azul
    sim = SimProvider(ruta_ndjson=_RAIZ / "data" / "wazuh_sim" / "alerts.ndjson", ruta_db=str((_RAIZ / "data" / "wazuh_sim.db")) if db is None else ":memory:",
                      semilla=semilla) if wazuh else None
    p = Partida(esc, r, a, semilla=semilla, almacen=Almacen(db or RUTA_POR_DEFECTO), wazuh=sim, etiqueta_modelos=etiquetas)
    while not p.terminada():
        p.paso()
        if callback:
            callback(p)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escenario", required=True, choices=E.listar())
    ap.add_argument("--rojo", required=True)
    ap.add_argument("--azul", required=True)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--host", default=M.HOST_DEFECTO)
    ap.add_argument("--db", default=None, help="ruta SQLite de partidas (por defecto data/combate.db)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cb = (lambda p: print(f"  turno {p.turno}/{p._esc['max_turnos']} · objetivos {p.cont['objetivos']} · legítimas {p.cont['legit_servidas']}/{p.cont['legit_n']}")) if a.verbose else None
    p = jugar(a.escenario, a.rojo, a.azul, a.semilla, a.host, a.db, callback=cb)
    r = p.resultado
    print(json.dumps({k: r[k] for k in ("resultado", "motivo", "partida_id", "turnos_jugados", "objetivos_alcanzados", "tasa_legitimas")}, ensure_ascii=False, indent=1))
    return 0 if r["resultado"] not in ("ERROR_TECNICO",) else 2


if __name__ == "__main__":
    raise SystemExit(main())
