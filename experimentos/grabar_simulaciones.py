"""Graba partidas del modo Caminos como registros reproducibles para la ventana «Simulación».

Las partidas SE EJECUTAN DE VERDAD en el motor (no se escriben a mano): este script solo elige quién juega, ejecuta, y guarda el registro
(fila de la partida + TODOS los eventos con su cadena de hashes + alertas Wazuh SIMULADAS + el grafo) en `data/simulaciones/<id>.json`.
La reproducción no regenera nada: solo reproduce lo registrado. Cada registro declara su procedencia (`tipo`).

  python experimentos/grabar_simulaciones.py                 # catálogo mínimo de CAMINOS_GUION (6 grabaciones)
  python experimentos/grabar_simulaciones.py --desde-campana combate-caminos-v1   # añade victorias Rojas CAMINOS_IA ya registradas
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from src.lab.caminos import grafo as G, proveedores as P  # noqa: E402
from src.lab.caminos.jugar import guion_de_camino  # noqa: E402
from src.lab.caminos.motor import PartidaCaminos  # noqa: E402
from src.lab.combate.store import Almacen  # noqa: E402
from src.lab.wazuh_sim import SimProvider  # noqa: E402

SALIDA = RAIZ / "data" / "simulaciones"
# (id, hoja, titulo corto, dificultad). 3 victorias Rojas por caminos distintos, 2 victorias Azules y 1 reversión.
CATALOGO = [
    ("sim-roja-base-entregada", "H_R_base_entregada", "Victoria Roja: credencial en frío, sesión aprobada y base entregada", "sencillo"),
    ("sim-roja-giro-2f", "H_R_giro_2f", "Victoria Roja: el segundo factor llegó por un correo que nadie reportó", "intermedio"),
    ("sim-roja-inyeccion-documento", "H_R_obedece_doc", "Victoria Roja: inyección indirecta por un documento", "sencillo"),
    ("sim-azul-alerta-rechazo", "H_A_alerta_rechazo", "Victoria Azul: el correo reportado y la alerta bastan", "sencillo"),
    ("sim-azul-honeytoken", "H_A_honeytoken_contenido", "Victoria Azul: la credencial señuelo delata al Rojo", "intermedio"),
    ("sim-reversion-rotacion", "H_A_rev_rotacion", "Reversión: parece ganar el Rojo y al final gana el Azul", "sencillo"),
]


def _grabar_partida(p, extra=None):
    eventos = p.almacen.eventos(p.id)
    ok, msg = p.almacen.verificar_cadena(p.id)
    assert ok, msg
    part = p.almacen.partida(p.id)
    alertas = p.wazuh.consultar_alertas(p.id) if p.wazuh is not None else []
    return {"partida": part, "eventos": eventos, "alertas_wazuh_simuladas": alertas, "cadena_integra": ok, **(extra or {})}


def grabar_guion(id_, hoja, titulo, dificultad):
    g = G.cargar(f"caminos-{dificultad}")
    rec = next(r for r in G.recorridos(g) if r["hoja"] == hoja)
    gr, ga = guion_de_camino(g, rec["camino"])
    p = PartidaCaminos(g, gr, ga, semilla=1, almacen=Almacen(":memory:"), wazuh=SimProvider(ruta_ndjson=None, ruta_db=":memory:", semilla=1))
    p.jugar()
    assert p.resultado["hoja"] == hoja, (p.resultado["hoja"], hoja)
    doc = _grabar_partida(p, {"id_simulacion": id_, "titulo": titulo, "tipo": p.tipo, "procedencia": "CAMINOS_GUION: decisiones prefijadas; es un recorrido posible del grafo demostrado por el motor, NO una partida de un modelo",
                              "modelos": {"rojo": "guion", "azul": "guion"}, "semilla": 1, "dificultad": dificultad, "hash_grafo": p.hash_grafo, "hoja": hoja, "grafo": g})
    (SALIDA / f"{id_}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def grabar_desde_campana(campana, maximo=4):
    """Añade al catálogo las victorias Rojas CAMINOS_IA YA REGISTRADAS por la campaña (no se vuelven a jugar ni se editan): copia la partida,
    sus eventos con hash y el grafo. Las alertas Wazuh simuladas no se persistieron en la campaña: las que ve la reproducción salen de los
    eventos `caminos.alerta` del propio registro."""
    d = RAIZ / "data" / "campanas" / campana
    obs = {}
    for f in sorted(d.glob("observaciones*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(l)
                obs[o["id"]] = o
            except (ValueError, KeyError):
                continue
    elegidas, vistos = [], set()
    for o in sorted(obs.values(), key=lambda x: (x["modo"] != "grafo", x["fase"] != "cruzada", x["id"])):
        clave = (o["modo"], o["rojo"], o["azul"], o.get("hoja"))
        if o["tipo"] == "CAMINOS_IA" and o["resultado"] == "VICTORIA_ROJA" and o["rojo"] in ("qwen3:8b", "llama3.1:8b") and o["azul"] in ("qwen3:8b", "llama3.1:8b") and clave not in vistos:
            vistos.add(clave)
            elegidas.append(o)
    almacenes = [Almacen(f) for f in sorted(d.glob("partidas*.db"))]
    hechas = []
    for o in elegidas[:maximo]:
        pid = o["partida_id"]
        alm = next((a for a in almacenes if a.partida(pid)), None)
        if alm is None:
            continue
        part, ev = alm.partida(pid), alm.eventos(pid)
        ok, msg = alm.verificar_cadena(pid)
        assert ok, msg
        auto = o["modo"] == "auto"
        id_ = f"sim-ia-roja-{o['modo']}-{o['rojo'][:5]}-{o['azul'][:5]}-{o['rep']:02d}".replace(":", "").replace(".", "")
        doc = {"id_simulacion": id_, "titulo": f"Victoria Roja REAL de un 8B ({'modo automático' if auto else 'grafo'}): {o['rojo']} contra {o['azul']}", "tipo": "CAMINOS_IA",
               "procedencia": "CAMINOS_IA: un modelo de lenguaje eligió las opciones; el motor declaró el resultado. Victoria real solo en este modo, no en el combate libre.",
               "modelos": {"rojo": o["rojo"], "azul": o["azul"]}, "semilla": o["semilla"], "dificultad": o.get("dificultad") or "auto", "hash_grafo": part["hash_escenario"], "hoja": o.get("hoja"),
               "grafo": None if auto else G.cargar(f"caminos-{o['dificultad']}"), "modo": "auto" if auto else "grafo", "partida": part, "eventos": ev, "alertas_wazuh_simuladas": [],
               "cadena_integra_al_exportar": ok, "origen": f"campaña {campana}, observación {o['id']}"}
        (SALIDA / f"{id_}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        hechas.append(id_)
        print(id_, o["hoja"], len(ev), "eventos")
    return hechas


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    if "--desde-campana" in sys.argv:
        grabar_desde_campana(sys.argv[sys.argv.index("--desde-campana") + 1])
        return
    for id_, hoja, titulo, dif in CATALOGO:
        d = grabar_guion(id_, hoja, titulo, dif)
        print(id_, d["partida"]["resultado"]["resultado"], hoja, len(d["eventos"]), "eventos", len(d["alertas_wazuh_simuladas"]), "alertas")


if __name__ == "__main__":
    main()
