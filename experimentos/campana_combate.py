"""Campañas de combate IA vs IA (Rojo vs Azul), reanudables y sin duplicados.

  python experimentos/campana_combate.py --campana combate-v1 --fases base,espejo,cruzada --prueba-corta   # 3 partidas
  python experimentos/campana_combate.py --campana combate-v1 --fases base,espejo,cruzada --lanzar         # en segundo plano
  python experimentos/campana_combate.py --campana combate-v1 --estado                                      # PID, progreso

Diseño:
  * Cada celda (fase, escenario, rojo, azul, configuración, repetición) tiene un id determinista. Una celda ya
    observada no se repite; la campaña se puede cortar y reanudar sin duplicados.
  * Cada partida termina en una línea de `observaciones.jsonl` (se escribe al terminar CADA partida).
  * Las observaciones no válidas (INCONCLUSA / ERROR_TECNICO) se guardan con `valida=false` y su motivo; no entran en
    las tasas de éxito y se cuentan aparte. `--reintentar-invalidas` las repite UNA vez más (línea nueva, intento=2).
  * Un candado con PID impide lanzar dos campañas iguales. El lanzador desacopla el proceso del shell (Windows:
    DETACHED_PROCESS) para que no muera con él.
  * Una sola partida a la vez (una GPU). No se cambia ningún criterio de evaluación entre observaciones.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.lab import cliente_ollama as co  # noqa: E402
from src.lab.combate import escenarios as E, jugar as J, modelos as M  # noqa: E402
from src.lab.combate.motor import Partida  # noqa: E402
from src.lab.combate.store import Almacen  # noqa: E402
from src.lab.wazuh_sim import SimProvider  # noqa: E402

MODELO_A, MODELO_B = "qwen3:8b", "llama3.1:8b"
HOST = M.HOST_DEFECTO
BASE_ROJO = ["falso:fijo", "falso:aleatorio", "falso:objetivos"]
BASE_AZUL = ["falso:rechazar", "falso:aprobar", "falso:aleatorio", "falso:registro"]


def celda(fase, esc, rojo, azul, config, rep):
    cid = hashlib.sha1("|".join([fase, esc, rojo, azul, config, str(rep)]).encode()).hexdigest()[:12]
    return {"id": cid, "fase": fase, "escenario": esc, "familia": esc.rsplit("-", 1)[0], "dificultad": esc.rsplit("-", 1)[1],
            "rojo": rojo, "azul": azul, "config": config, "rep": rep, "semilla": rep}


def plan(fases, reps_base=10, reps_llm=3, reps_var=1):
    """Las fases se ejecutan en el ORDEN en que se piden (prioridad: espejo, cruzada, y al final variaciones)."""
    out = []
    for f in fases:
        out += _plan_fase(f, reps_base, reps_llm, reps_var)
    vistos, unico = set(), []
    for c in out:
        if c["id"] not in vistos:
            vistos.add(c["id"])
            unico.append(c)
    return unico


def _plan_fase(fase, reps_base, reps_llm, reps_var):
    fases = [fase]
    esc = E.listar()
    orden = {"sencillo": 0, "intermedio": 1, "complejo": 2}
    esc.sort(key=lambda e: (orden[e.rsplit("-", 1)[1]], e))
    out = []
    if "base" in fases:   # líneas base triviales (sin GPU): Azul trivial × Rojo trivial
        for r in BASE_ROJO:
            for a in BASE_AZUL:
                for e in esc:
                    out += [celda("base", e, r, a, "base", k) for k in range(1, reps_base + 1)]
    if "base_llm" in fases:   # un modelo 8B contra la línea base trivial del otro equipo
        for m in (MODELO_A, MODELO_B):
            for a in ("falso:rechazar", "falso:aprobar", "falso:aleatorio"):
                out += [celda("base_llm", e, m, a, "base", k) for e in esc for k in range(1, 2)]
            for r in ("falso:fijo", "falso:aleatorio"):
                out += [celda("base_llm", e, r, m, "base", k) for e in esc for k in range(1, 2)]
    if "espejo" in fases:
        for k in range(1, reps_llm + 1):
            for e in esc:
                for m in (MODELO_A, MODELO_B):
                    out.append(celda("espejo", e, m, m, "base", k))
    if "cruzada" in fases:
        for k in range(1, reps_llm + 1):
            for e in esc:
                out.append(celda("cruzada", e, MODELO_A, MODELO_B, "base", k))
                out.append(celda("cruzada", e, MODELO_B, MODELO_A, "base", k))
    if "variaciones" in fases:   # una variable por vez, sobre el espejo/cruce que menos hunda: Azul con ejemplos / sin Wazuh
        for k in range(1, reps_var + 1):
            for e in esc:
                for cfg in ("ejemplos", "sin_wazuh", "sin_autorizaciones", "sin_aut_sin_wazuh"):
                    for r, a in ((MODELO_A, MODELO_A), (MODELO_B, MODELO_B)):
                        out.append(celda("variaciones", e, r, a, cfg, k))
    return out


# ── Estado en disco ─────────────────────────────────────────────────────────────────────────────────────────
def carpeta(nombre):
    d = RAIZ / "data" / "campanas" / nombre
    d.mkdir(parents=True, exist_ok=True)
    return d


def leer_obs(d):
    f = d / "observaciones.jsonl"
    if not f.exists():
        return []
    out = []
    for linea in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(linea))
        except ValueError:
            continue
    return out


def estado_por_id(obs):
    """Última observación de cada id. -> {id: obs}."""
    return {o["id"]: o for o in obs}


def pid_vivo(pid):
    if not pid:
        return False
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in r.stdout
    except Exception:  # noqa: BLE001
        return False


SUFIJO = ""   # --sufijo: permite dos procesos sobre la misma campaña (fases distintas): candado y base de partidas propios


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
        info["latido"] = datetime.now().isoformat(timespec="seconds")
        info["ultimo"] = texto
        f.write_text(json.dumps(info), encoding="utf-8")
    except OSError:
        pass


# ── Una partida ─────────────────────────────────────────────────────────────────────────────────────────────
def esperar_ollama(max_s=600):
    t0 = time.time()
    while time.time() - t0 < max_s:
        if co.ollama_disponible(HOST):
            return True
        time.sleep(15)
    return False


def jugar_celda(c, d):
    esc = E.cargar(c["escenario"])
    rojo = J.construir_rojo(c["rojo"], esc, c["semilla"], HOST)
    azul = J.construir_azul(c["azul"], c["semilla"], HOST)
    if c["config"] == "ejemplos" and isinstance(azul, M.AzulOllama):
        azul = M.AzulOllama(c["azul"], host=HOST, semilla=c["semilla"], ejemplos=True)
    wz = SimProvider(ruta_ndjson=d / "wazuh_alerts.ndjson", ruta_db=":memory:", semilla=c["semilla"])
    alm = Almacen(d / f"partidas{SUFIJO}.db")
    previa = alm.partida(f"{c['fase']}-{c['id']}")
    if previa and previa["resultado"]:   # la partida terminó pero la observación no llegó a escribirse (corte entre medias): se recupera, no se repite
        r = dict(previa["resultado"])
        r["recuperada"] = True
        return r, 0.0
    # Si quedó una partida a medias de un corte anterior, el motor le asigna un id nuevo (sufijo -2, -3…): la huérfana no cuenta nada.
    p = Partida(esc, rojo, azul, semilla=c["semilla"], almacen=alm, wazuh=wz,
                partida_id=f"{c['fase']}-{c['id']}", etiqueta_modelos={"celda": c["id"], "config": c["config"]},
                azul_ve_wazuh=c["config"] not in ("sin_wazuh", "sin_aut_sin_wazuh"),
                azul_ve_autorizaciones=c["config"] not in ("sin_autorizaciones", "sin_aut_sin_wazuh"))
    t0 = time.time()
    try:
        r = p.jugar()
    except Exception as exc:  # noqa: BLE001 - un fallo del motor no debe tumbar la campaña
        return {"resultado": "ERROR_TECNICO", "causa": f"excepcion: {type(exc).__name__}: {exc}"[:200], "partida_id": p.id,
                "turnos_jugados": p.turno, "objetivos_alcanzados": [], "umbral_victoria_roja": esc["umbral_victoria_roja"], "tasa_legitimas": None,
                "metricas": p.metricas(), "consumo": {}}, time.time() - t0
    return r, time.time() - t0


def observacion(c, r, dur, intento):
    m = r.get("metricas") or {}
    az = (m.get("azul") or {}).get("clasificacion") or {}
    ro = m.get("rojo") or {}
    valida = r["resultado"] in ("VICTORIA_ROJA", "VICTORIA_AZUL", "EMPATE", "EMPATE_DEGRADADO")
    motivo = None if valida else f"{r['resultado']}: {r.get('causa') or r.get('motivo')}"
    cons = r.get("consumo") or {}
    return {**c, "intento": intento, "resultado": r["resultado"], "causa": r.get("causa"), "valida": valida, "motivo_invalida": motivo,
            "turnos": r.get("turnos_jugados"), "objetivos": len(r.get("objetivos_alcanzados") or []), "umbral": r.get("umbral_victoria_roja"),
            "tasa_legitimas": r.get("tasa_legitimas"), "rojo_m": ro,
            "azul_m": {k: az.get(k) for k in ("VP", "FP", "FN", "VN")}, "decisiones": (m.get("azul") or {}).get("decisiones"),
            "malformadas": (m.get("azul") or {}).get("malformadas"), "errores_tecnicos": m.get("errores_tecnicos"),
            "wazuh": (m.get("azul") or {}).get("wazuh"), "llamadas": cons.get("llamadas_modelo"), "tokens_entrada": cons.get("tokens_entrada"),
            "tokens_salida": cons.get("tokens_salida"), "duracion_s": round(dur, 1), "partida_id": r.get("partida_id"),
            "version_prompts": M.VERSION_PROMPTS, "ts": datetime.now().isoformat(timespec="seconds")}


def ejecutar(nombre, fases, reps_base, reps_llm, reps_var, limite=None, max_horas=None, reintentar=False, prueba=False):
    d = carpeta(nombre)
    f = candado(d)
    if f is None:
        print("ya hay una campaña viva con este nombre (lock.pid); no se lanza otra")
        return 3
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pl = plan(fases, reps_base, reps_llm, reps_var)
    if prueba:   # prueba corta: 1 partida por fase solicitada (2-3 partidas)
        vistos, corto = set(), []
        for c in pl:
            if c["fase"] not in vistos and (c["rojo"].startswith("falso") or True):
                vistos.add(c["fase"])
                corto.append(c)
        pl = corto[:3]
        nombre_obs = d / "observaciones.jsonl"
    t_ini = time.time()
    hechos = 0
    for c in pl:
        previas = estado_por_id(leer_obs(d))
        ant = previas.get(c["id"])
        if ant is not None and (ant["valida"] or not reintentar or ant.get("intento", 1) >= 2):
            continue
        if limite is not None and hechos >= limite:
            break
        if max_horas and (time.time() - t_ini) / 3600 >= max_horas:
            print("límite de horas alcanzado; se detiene limpiamente")
            break
        llm = not (c["rojo"].startswith("falso") and c["azul"].startswith("falso"))
        if llm and not esperar_ollama():
            print("Ollama no responde tras 10 min: la campaña se detiene (reanudable)")
            return 4
        r, dur = jugar_celda(c, d)
        obs = observacion(c, r, dur, (ant or {}).get("intento", 0) + 1)
        with open(d / "observaciones.jsonl", "a", encoding="utf-8") as fo:     # escritura inmediata
            fo.write(json.dumps(obs, ensure_ascii=False) + "\n")
        hechos += 1
        latido(f, f"{c['fase']} {c['escenario']} {c['rojo']} vs {c['azul']} -> {r['resultado']}")
        print(f"[{hechos}] {c['fase']:<11} {c['escenario']:<42} {c['rojo']:>16} vs {c['azul']:<16} {c['config']:<9} -> {r['resultado']:<16} {dur:5.0f}s", flush=True)
    print(f"fin: {hechos} partidas nuevas en {(time.time() - t_ini) / 60:.1f} min")
    try:
        f.unlink()
    except OSError:
        pass
    return 0


def estado(nombre, fases, reps_base, reps_llm, reps_var):
    d = carpeta(nombre)
    obs = estado_por_id(leer_obs(d))
    pl = plan(fases, reps_base, reps_llm, reps_var)
    f = d / f"lock{SUFIJO}.pid"
    info = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    hechas = sum(1 for c in pl if c["id"] in obs)
    inval = sum(1 for c in pl if c["id"] in obs and not obs[c["id"]]["valida"])
    print(json.dumps({"campana": nombre, "plan": len(pl), "observadas": hechas, "pendientes": len(pl) - hechas, "invalidas": inval,
                      "proceso_vivo": pid_vivo(info.get("pid")), "pid": info.get("pid"), "latido": info.get("latido"), "ultimo": info.get("ultimo")},
                     ensure_ascii=False, indent=1))


def lanzar(argv_extra, nombre):
    d = carpeta(nombre)
    log = open(d / f"log{SUFIJO}.txt", "a", encoding="utf-8")
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve())] + argv_extra, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=flags, close_fds=True, cwd=str(RAIZ), env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    print(f"campaña lanzada en segundo plano: PID {p.pid}; log en {d / f'log{SUFIJO}.txt'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campana", default="combate-v1")
    ap.add_argument("--fases", default="base,base_llm,espejo,cruzada,variaciones")
    ap.add_argument("--reps-base", type=int, default=10)
    ap.add_argument("--reps-llm", type=int, default=3)
    ap.add_argument("--reps-var", type=int, default=1)
    ap.add_argument("--limite", type=int, default=None, help="máximo de partidas nuevas en esta ejecución")
    ap.add_argument("--max-horas", type=float, default=None)
    ap.add_argument("--reintentar-invalidas", action="store_true")
    ap.add_argument("--prueba-corta", action="store_true")
    ap.add_argument("--lanzar", action="store_true", help="relanza este mismo comando desacoplado en segundo plano")
    ap.add_argument("--estado", action="store_true")
    ap.add_argument("--sufijo", default="", help="segundo proceso sobre la misma campaña (fases distintas)")
    a = ap.parse_args()
    global SUFIJO
    SUFIJO = f"-{a.sufijo}" if a.sufijo else ""
    fases = [x for x in a.fases.split(",") if x]
    if a.estado:
        return estado(a.campana, fases, a.reps_base, a.reps_llm, a.reps_var)
    if a.lanzar:
        extra = [x for x in sys.argv[1:] if x != "--lanzar"]
        return lanzar(extra, a.campana)
    return ejecutar(a.campana, fases, a.reps_base, a.reps_llm, a.reps_var, a.limite, a.max_horas, a.reintentar_invalidas, a.prueba_corta)


if __name__ == "__main__":
    raise SystemExit(main())
