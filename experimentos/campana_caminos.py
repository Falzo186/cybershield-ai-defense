"""Campaña del modo CAMINOS (grafo de 16 hojas y modo automático de credenciales). Reanudable, con ids deterministas, candado por PID y
lanzamiento desacoplado. Escribe `data/campanas/<nombre>/observaciones.jsonl` (una línea por partida; el análisis lo hace resumir_caminos.py).

  python experimentos/campana_caminos.py --campana caminos-v1 --fases llm_base,espejo,cruzada --prueba-corta     # 3 partidas
  python experimentos/campana_caminos.py --campana caminos-v1 --fases llm_base,espejo,cruzada --lanzar           # en segundo plano
  python experimentos/campana_caminos.py --campana caminos-v1 --base --lanzar --sufijo base                      # línea base sin GPU (2.º proceso)
  python experimentos/campana_caminos.py --campana caminos-v1 --estado

Fases: base (Rojo y Azul triviales; sin GPU) · llm_base (un 8B contra el otro equipo trivial) · espejo · cruzada. Cada fase juega el GRAFO (3 dificultades)
y el modo AUTOMÁTICO. Los prompts (c1) NO cambian durante la campaña.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from src.lab import cliente_ollama as co  # noqa: E402
from src.lab.caminos import auto as A, grafo as G, proveedores as P  # noqa: E402
from src.lab.caminos.motor import PartidaCaminos  # noqa: E402
from src.lab.combate.modelos import HOST_DEFECTO  # noqa: E402
from src.lab.combate.store import Almacen  # noqa: E402
from src.lab.wazuh_sim import SimProvider  # noqa: E402

HOST = HOST_DEFECTO
QW, LL = "qwen3:8b", "llama3.1:8b"
ROJO_BASE_GRAFO = ["aleatorio", "primera", "guion:cred_gerente,solicitar_base"]
ROJO_BASE_AUTO = ["aleatorio", "primera", "guion:C-01|portal_interno,C-02|portal_interno,C-03|portal_interno"]
AZUL_BASE = ["registro", "aprobar", "rechazar", "aleatorio"]
DIFS = ("sencillo", "intermedio", "complejo")
SUFIJO = ""
VALIDOS = ("VICTORIA_ROJA", "VICTORIA_AZUL", "EMPATE_DEGRADADO")


def celda(fase, modo, dif, rojo, azul, rep):
    cid = hashlib.sha1("|".join([fase, modo, dif or "-", rojo, azul, str(rep)]).encode()).hexdigest()[:12]
    return {"id": cid, "fase": fase, "modo": modo, "dificultad": dif, "rojo": rojo, "azul": azul, "rep": rep, "semilla": rep}


def plan(fases, reps_base=20, reps_llm=5, reps_esp=15, reps_cruz=10):
    out = []
    for f in fases:
        if f == "base":
            for a in AZUL_BASE:
                for r in ROJO_BASE_GRAFO:
                    out += [celda("base", "grafo", d, r, a, k) for d in DIFS for k in range(1, reps_base + 1)]
            for a in AZUL_BASE:
                for r in ROJO_BASE_AUTO:
                    out += [celda("base", "auto", None, r, a, k) for k in range(1, reps_base + 1)]
        elif f == "llm_base":
            for m in (QW, LL):
                for a in AZUL_BASE:
                    out += [celda("llm_base", "grafo", d, m, a, k) for d in DIFS for k in range(1, reps_llm + 1)]
                    out += [celda("llm_base", "auto", None, m, a, k) for k in range(1, reps_llm + 2)]
                for r in ROJO_BASE_GRAFO:
                    out += [celda("llm_base", "grafo", d, r, m, k) for d in DIFS for k in range(1, reps_llm + 1)]
                for r in ROJO_BASE_AUTO:
                    out += [celda("llm_base", "auto", None, r, m, k) for k in range(1, reps_llm + 2)]
        elif f == "espejo":
            for k in range(1, reps_esp + 1):
                for m in (QW, LL):
                    out += [celda("espejo", "grafo", d, m, m, k) for d in DIFS]
            for k in range(1, reps_esp + 6):
                for m in (QW, LL):
                    out.append(celda("espejo", "auto", None, m, m, k))
        elif f == "cruzada":
            for k in range(1, reps_cruz + 1):
                for r, a in ((QW, LL), (LL, QW)):
                    out += [celda("cruzada", "grafo", d, r, a, k) for d in DIFS]
            for k in range(1, reps_cruz + 3):
                for r, a in ((QW, LL), (LL, QW)):
                    out.append(celda("cruzada", "auto", None, r, a, k))
    vistos, unico = set(), []
    for c in out:
        if c["id"] not in vistos:
            vistos.add(c["id"])
            unico.append(c)
    return unico


def carpeta(nombre):
    d = RAIZ / "data" / "campanas" / nombre
    d.mkdir(parents=True, exist_ok=True)
    return d


def leer_obs(d):
    f = d / "observaciones.jsonl"
    out = []
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                continue
    return out


def pid_vivo(pid):
    if not pid:
        return False
    try:
        return str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    except Exception:  # noqa: BLE001
        return False


def candado(d):
    f = d / f"lock{SUFIJO}.pid"
    if f.exists():
        try:
            info = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            info = {}
        if pid_vivo(info.get("pid")) and info.get("pid") != os.getpid():
            return None
    f.write_text(json.dumps({"pid": os.getpid(), "inicio": datetime.now().isoformat(timespec="seconds"), "latido": None}), encoding="utf-8")
    return f


def latido(f, texto):
    try:
        info = json.loads(f.read_text(encoding="utf-8"))
        info.update(latido=datetime.now().isoformat(timespec="seconds"), ultimo=texto)
        f.write_text(json.dumps(info), encoding="utf-8")
    except OSError:
        pass


def esperar_ollama(max_s=600):
    t0 = time.time()
    while time.time() - t0 < max_s:
        if co.ollama_disponible(HOST):
            return True
        time.sleep(15)
    return False


def jugar_celda(c, d):
    alm = Almacen(d / f"partidas{SUFIJO}.db")
    sim = SimProvider(ruta_ndjson=None, ruta_db=":memory:", semilla=c["semilla"])
    rojo = P.construir(c["rojo"], "rojo", c["semilla"], HOST)
    azul = P.construir(c["azul"], "azul", c["semilla"], HOST)
    pid = f"{c['fase']}-{c['id']}"
    t0 = time.time()
    try:
        if c["modo"] == "grafo":
            p = PartidaCaminos(G.cargar(f"caminos-{c['dificultad']}"), rojo, azul, semilla=c["semilla"], almacen=alm, wazuh=sim, partida_id=pid, etiquetas={"celda": c["id"]})
        else:
            p = A.PartidaAuto(rojo, azul, semilla=c["semilla"], almacen=alm, wazuh=sim, partida_id=pid)
        r = p.jugar()
    except Exception as exc:  # noqa: BLE001 - un fallo del motor no tumba la campaña
        return {"resultado": "ERROR_TECNICO", "causa": f"{type(exc).__name__}: {exc}"[:160], "tipo": None, "turnos_jugados": 0, "partida_id": pid}, time.time() - t0, None
    return r, time.time() - t0, p


def observacion(c, r, dur, p, intento):
    valida = r["resultado"] in VALIDOS
    decisiones = Counter()
    if p is not None:
        for e in p.almacen.eventos(p.id):
            if e["tipo"] == "caminos.decision" and e["payload"]["actor"] == "azul":
                decisiones[f"{e['payload']['nodo']}:{e['payload']['opcion']}"] += 1
            elif e["tipo"] == "azul.decision":
                decisiones[e["payload"]["decision"]] += 1
    m = r.get("metricas") or {}
    cons = r.get("consumo") or {}
    return {**c, "intento": intento, "resultado": r["resultado"], "causa": r.get("causa"), "valida": valida, "tipo": r.get("tipo"), "hoja": r.get("hoja"), "reversion": r.get("reversion", False),
            "giro": r.get("giro", False), "turnos": r.get("turnos_jugados"), "camino": r.get("camino"), "tasa_legitimas": r.get("tasa_legitimas"),
            "opciones_invalidas": r.get("opciones_invalidas"), "decisiones_azul": dict(decisiones), "azul_m": (m.get("azul") or {}).get("clasificacion"), "rojo_m": m.get("rojo"),
            "llamadas": cons.get("llamadas_modelo"), "tokens_salida": cons.get("tokens_salida"), "duracion_s": round(dur, 1), "partida_id": r.get("partida_id"),
            "version_prompts": P.VERSION_PROMPTS_CAMINOS, "ts": datetime.now().isoformat(timespec="seconds")}


def ejecutar(nombre, fases, limite=None, max_horas=None, prueba=False, **reps):
    d = carpeta(nombre)
    f = candado(d)
    if f is None:
        print("ya hay una campaña viva con este nombre (lock.pid); no se lanza otra")
        return 3
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pl = plan(fases, **reps)
    if prueba:
        vistos, corto = set(), []
        for c in pl:
            if (c["fase"], c["modo"]) not in vistos:
                vistos.add((c["fase"], c["modo"]))
                corto.append(c)
        pl = corto[:3]
    t_ini, hechos = time.time(), 0
    hechas = {o["id"] for o in leer_obs(d)}
    for c in pl:
        if c["id"] in hechas:
            continue
        if limite is not None and hechos >= limite:
            break
        if max_horas and (time.time() - t_ini) / 3600 >= max_horas:
            print("límite de horas alcanzado; se detiene limpiamente")
            break
        llm = any(not x.startswith(("guion", "aleatorio", "primera", "registro", "aprobar", "rechazar")) for x in (c["rojo"], c["azul"]))
        if llm and not esperar_ollama():
            print("Ollama no responde tras 10 min: la campaña se detiene (reanudable)")
            return 4
        r, dur, p = jugar_celda(c, d)
        obs = observacion(c, r, dur, p, 1)
        with open(d / "observaciones.jsonl", "a", encoding="utf-8") as fo:
            fo.write(json.dumps(obs, ensure_ascii=False) + "\n")
        hechos += 1
        latido(f, f"{c['fase']} {c['modo']} {c['rojo']} vs {c['azul']} -> {r['resultado']}")
        print(f"[{hechos}] {c['fase']:<9} {c['modo']:<5} {str(c['dificultad']):<10} {c['rojo'][:22]:>22} vs {c['azul'][:22]:<22} -> {r['resultado']:<16} {str(r.get('hoja')):<26} {dur:5.0f}s", flush=True)
    print(f"fin: {hechos} partidas nuevas en {(time.time() - t_ini) / 60:.1f} min")
    try:
        f.unlink()
    except OSError:
        pass
    return 0


def estado(nombre, fases, **reps):
    d = carpeta(nombre)
    obs = {o["id"]: o for o in leer_obs(d)}
    pl = plan(fases, **reps)
    f = d / f"lock{SUFIJO}.pid"
    info = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    print(json.dumps({"campana": nombre, "plan": len(pl), "observadas": sum(1 for c in pl if c["id"] in obs), "invalidas": sum(1 for c in pl if c["id"] in obs and not obs[c["id"]]["valida"]),
                      "proceso_vivo": pid_vivo(info.get("pid")), "pid": info.get("pid"), "latido": info.get("latido"), "ultimo": info.get("ultimo")}, ensure_ascii=False, indent=1))


def lanzar(argv_extra, nombre):
    d = carpeta(nombre)
    log = open(d / f"log{SUFIJO}.txt", "a", encoding="utf-8")
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve())] + argv_extra, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True,
                         cwd=str(RAIZ), env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    print(f"campaña lanzada en segundo plano: PID {p.pid}; log en {d / f'log{SUFIJO}.txt'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campana", default="caminos-v1")
    ap.add_argument("--fases", default="llm_base,espejo,cruzada")
    ap.add_argument("--base", action="store_true", help="atajo: solo la fase base (sin GPU)")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--max-horas", type=float, default=None)
    ap.add_argument("--prueba-corta", action="store_true")
    ap.add_argument("--lanzar", action="store_true")
    ap.add_argument("--estado", action="store_true")
    ap.add_argument("--sufijo", default="")
    ap.add_argument("--reps-base", type=int, default=20)
    ap.add_argument("--reps-llm", type=int, default=5)
    ap.add_argument("--reps-esp", type=int, default=15)
    ap.add_argument("--reps-cruz", type=int, default=10)
    a = ap.parse_args()
    global SUFIJO
    SUFIJO = f"-{a.sufijo}" if a.sufijo else ""
    fases = ["base"] if a.base else [x for x in a.fases.split(",") if x]
    reps = {"reps_base": a.reps_base, "reps_llm": a.reps_llm, "reps_esp": a.reps_esp, "reps_cruz": a.reps_cruz}
    if a.estado:
        return estado(a.campana, fases, **reps)
    if a.lanzar:
        return lanzar([x for x in sys.argv[1:] if x != "--lanzar"], a.campana)
    return ejecutar(a.campana, fases, a.limite, a.max_horas, a.prueba_corta, **reps)


if __name__ == "__main__":
    raise SystemExit(main())
