"""Rutas del combate IA vs IA (`/api/combate/...`).

Reglas (misión 23 h):
  - Los GET son de solo lectura y públicos (también para el espectador). Los POST (crear, interrumpir) exigen la
    sesión del equipo «general» (árbitro): la comprobación está aquí, además del middleware de la partida.
  - La interfaz muestra «victoria/derrota/empate» SOLO a partir del evento `partida.resultado` persistido: el
    campo `resultado` de estas rutas sale de la base de datos, nunca de un cálculo del cliente.
  - Durante una partida en curso se oculta la verdad de fondo (`legitima`).
  - Todo lo de Wazuh va marcado como SIMULADO.
"""
import os
import threading
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

from src.lab import cliente_ollama
from src.lab.combate import escenarios as E, jugar as J, modelos as M, motor as X
from src.lab.combate.store import Almacen, RUTA_POR_DEFECTO
from src.lab.wazuh_sim import ETIQUETA, SimProvider

RAIZ = Path(__file__).resolve().parents[1]
PAUSA_FALSOS_S = 0.6        # ritmo de turnos con modelos falsos, para que la interfaz pueda mostrar el avance
MODELOS_FALSOS_ROJO = {"falso:objetivos": "Rojo de guion (va a por los objetivos)", "falso:fijo": "Rojo de mensaje fijo",
                       "falso:aleatorio": "Rojo aleatorio"}
MODELOS_FALSOS_AZUL = {"falso:registro": "Azul de referencia (decide por registro)", "falso:rechazar": "Azul «rechazar siempre»",
                       "falso:aprobar": "Azul «aprobar siempre»", "falso:aleatorio": "Azul aleatorio", "falso:credulo": "Azul crédulo"}
_ACTUAL = {"partida": None, "hilo": None, "error": None, "cancelar": False}
_CERROJO = threading.Lock()


def _ok(d):
    return JSONResponse(d)


def _err(msg, status=400):
    return JSONResponse({"error": msg}, status_code=status)


def _almacen():
    return Almacen(os.environ.get("CS_COMBATE_DB") or RUTA_POR_DEFECTO)


def _wazuh():
    ruta = os.environ.get("CS_WAZUH_SIM_DB") or (RAIZ / "data" / "wazuh_sim.db")
    return SimProvider(ruta_ndjson=RAIZ / "data" / "wazuh_sim" / "alerts.ndjson" if not os.environ.get("CS_WAZUH_SIM_DB") else None,
                       ruta_db=str(ruta), semilla=0)


def _resumen(p):
    r = p["resultado"]
    return {"id": p["id"], "escenario": p["escenario_id"], "estado": p["estado"], "creada": p["creada"], "fin": p["fin"],
            "rojo": p["config"].get("rojo"), "azul": p["config"].get("azul"), "semilla": p["config"].get("semilla"),
            "resultado": r["resultado"] if r else None, "motivo": r["motivo"] if r else None,
            "turnos": r["turnos_jugados"] if r else None, "hash_escenario": p["hash_escenario"]}


def _estado_actual():
    p = _ACTUAL["partida"]
    if p is None:
        return None
    return {"id": p.id, "escenario": p._esc["id"], "turno": p.turno, "max_turnos": p._esc["max_turnos"], "terminada": p.terminada(),
            "interrumpible": not p.terminada(), "error": _ACTUAL["error"],
            "viva": bool(_ACTUAL["hilo"] and _ACTUAL["hilo"].is_alive())}


def _correr(p, pausa):
    try:
        while not p.terminada() and not _ACTUAL["cancelar"]:
            p.paso()
            if pausa:
                time.sleep(pausa)
        if _ACTUAL["cancelar"] and not p.terminada():
            p.interrumpir("interrumpida por el árbitro")
    except X.ErrorMotor as exc:
        if exc.status != 409 or not p.terminada():
            _ACTUAL["error"] = f"{exc.status}: {exc.mensaje}"
    except Exception as exc:  # noqa: BLE001 - se publica, no se esconde
        _ACTUAL["error"] = f"{type(exc).__name__}: {exc}"
        if not p.terminada():
            try:
                p._cerrar("ERROR_TECNICO", f"fallo de integración: {type(exc).__name__}: {exc}", causa="excepcion")
            except X.ErrorMotor:
                pass


def registrar(app, host_ollama):
    def _modelo_ok(spec, rol):
        if spec.startswith("falso:"):
            ok = MODELOS_FALSOS_ROJO if rol == "rojo" else MODELOS_FALSOS_AZUL
            return spec in ok, f"modelo falso desconocido: {spec}"
        if not cliente_ollama.ollama_disponible(host_ollama):
            return False, f"Ollama no responde en {host_ollama}: no se inicia la partida"
        if spec not in cliente_ollama.listar_modelos(host_ollama):
            return False, f"el modelo «{spec}» no está instalado en Ollama"
        return True, None

    @app.get("/api/combate/estado")
    async def combate_estado():
        disp = cliente_ollama.ollama_disponible(host_ollama)
        return _ok({"ollama": {"host": host_ollama, "disponible": disp, "modelos": cliente_ollama.listar_modelos(host_ollama) if disp else []},
                    "wazuh": {**_wazuh().estado(), "etiqueta": ETIQUETA},
                    "actual": _estado_actual(), "version_prompts": M.VERSION_PROMPTS})

    @app.get("/api/combate/modelos")
    async def combate_modelos():
        disp = cliente_ollama.ollama_disponible(host_ollama)
        reales = cliente_ollama.listar_modelos(host_ollama) if disp else []
        return _ok({"ollama_disponible": disp, "reales": reales, "falsos_rojo": MODELOS_FALSOS_ROJO, "falsos_azul": MODELOS_FALSOS_AZUL,
                    "recomendados_8b": [m for m in reales if m in ("qwen3:8b", "llama3.1:8b")]})

    @app.get("/api/combate/escenarios")
    async def combate_escenarios():
        out = []
        for i in E.listar():
            e = E.cargar(i)
            out.append({"id": e["id"], "familia": e["familia"], "dificultad": e["dificultad"], "titulo": e["titulo"], "descripcion": e["descripcion"],
                        "max_turnos": e["max_turnos"], "umbral_victoria_roja": e["umbral_victoria_roja"],
                        "objetivos_rojo": [{"id": o["id"], "descripcion": o["descripcion"]} for o in e["objetivos_rojo"]],
                        "objetivos_azul": e["objetivos_azul"], "hash": E.hash_escenario(e)[:16],
                        "recursos": [{"id": r["id"], "nombre": r["nombre"], "agente": r["agente"]} for r in e["recursos"]
                                     if r["objetivo_rojo"] or r["zona"] == "DENEGADO_POR_POLITICA"]})
        return _ok({"escenarios": out})

    @app.post("/api/combate/partidas")
    async def combate_crear(request: Request, cuerpo: dict):
        if request.state.equipo != "general":
            return _err("Solo el árbitro (equipo general) puede crear partidas de combate.", 403)
        esc, rojo, azul = cuerpo.get("escenario"), str(cuerpo.get("rojo") or ""), str(cuerpo.get("azul") or "")
        if esc not in E.listar():
            return _err(f"escenario desconocido: {esc}")
        for spec, rol in ((rojo, "rojo"), (azul, "azul")):
            ok, msg = _modelo_ok(spec, rol)
            if not ok:
                return _err(msg, 400 if "falso" in str(msg) or "instalado" in str(msg) else 503)
        try:
            semilla = int(cuerpo.get("semilla", 1))
        except (TypeError, ValueError):
            return _err("la semilla debe ser un entero")
        with _CERROJO:
            if _ACTUAL["hilo"] and _ACTUAL["hilo"].is_alive() and not (_ACTUAL["partida"] and _ACTUAL["partida"].terminada()):
                return _err("ya hay una partida de combate en curso; interrúmpela o espera a que termine", 409)
            e = E.cargar(esc)
            try:
                r = J.construir_rojo(rojo, e, semilla, host_ollama)
                a = M.AzulOllama(azul, host=host_ollama, semilla=semilla, ejemplos=bool(cuerpo.get("ejemplos"))) if not azul.startswith("falso:") \
                    else J.construir_azul(azul, semilla, host_ollama)
                p = X.Partida(e, r, a, semilla=semilla, almacen=_almacen(), wazuh=_wazuh(), azul_ve_wazuh=cuerpo.get("azul_ve_wazuh", True) is not False,
                              etiqueta_modelos={"origen": "interfaz"})
            except X.ErrorMotor as exc:
                return _err(exc.mensaje, exc.status)
            pausa = PAUSA_FALSOS_S if rojo.startswith("falso:") and azul.startswith("falso:") else 0
            _ACTUAL.update(partida=p, error=None, cancelar=False)
            h = threading.Thread(target=_correr, args=(p, pausa), daemon=True)
            _ACTUAL["hilo"] = h
            h.start()
        return _ok({"id": p.id, "escenario": esc, "hash_escenario": p.hash_escenario, "max_turnos": e["max_turnos"]})

    @app.post("/api/combate/partidas/{pid}/interrumpir")
    async def combate_interrumpir(pid: str, request: Request):
        if request.state.equipo != "general":
            return _err("Solo el árbitro puede interrumpir una partida.", 403)
        p = _ACTUAL["partida"]
        if p is None or p.id != pid:
            return _err("esa partida no está en curso en este servidor", 404)
        if p.terminada():
            return _err("la partida ya tiene resultado: no admite más acciones", 409)
        _ACTUAL["cancelar"] = True
        return _ok({"id": pid, "interrumpiendo": True})

    @app.get("/api/combate/partidas")
    async def combate_listar(resultado: str | None = None, escenario: str | None = None, limite: int = 100):
        ps = [_resumen(p) for p in _almacen().listar(max(1, min(limite, 500)))]
        if resultado:
            ps = [p for p in ps if p["resultado"] == resultado]
        if escenario:
            ps = [p for p in ps if p["escenario"] == escenario or p["escenario"].startswith(escenario)]
        return _ok({"partidas": ps})

    @app.get("/api/combate/partidas/{pid}")
    async def combate_detalle(pid: str):
        alm = _almacen()
        p = alm.partida(pid)
        if not p:
            return _err("partida desconocida", 404)
        esc = E.cargar(p["escenario_id"])
        vivo = _ACTUAL["partida"] is not None and _ACTUAL["partida"].id == pid and not _ACTUAL["partida"].terminada()
        res = p["resultado"]            # SOLO lo persistido por el motor
        det = {**_resumen(p), "config": p["config"], "max_turnos": esc["max_turnos"], "umbral_victoria_roja": esc["umbral_victoria_roja"],
               "objetivos_rojo": esc["objetivos_rojo"], "objetivos_azul": esc["objetivos_azul"],
               "recursos": [{"id": r["id"], "nombre": r["nombre"], "agente": r["agente"], "tipo": r["tipo"], "zona": r["zona"] if res else None,
                             "protegido": r["zona"] == "DENEGADO_POR_POLITICA"} for r in esc["recursos"]
                            if r["objetivo_rojo"] or r["zona"] == "DENEGADO_POR_POLITICA"],
               "en_curso": vivo, "cadena": alm.verificar_cadena(pid)[0]}
        if res:
            det["resultado_detalle"] = res
        return _ok(det)

    @app.get("/api/combate/partidas/{pid}/eventos")
    async def combate_eventos(pid: str, desde: int = 0):
        alm = _almacen()
        p = alm.partida(pid)
        if not p:
            return _err("partida desconocida", 404)
        ev = alm.eventos(pid, desde)
        if p["resultado"] is None:   # en curso: sin verdad de fondo
            for e in ev:
                e["payload"] = {k: v for k, v in e["payload"].items() if k not in ("legitima", "crudo")}
        return _ok({"eventos": ev, "terminada": p["resultado"] is not None, "ultimo": ev[-1]["seq"] if ev else desde})

    @app.get("/api/combate/partidas/{pid}/wazuh")
    async def combate_wazuh(pid: str, nivel_min: int = 0, grupo: str | None = None, agente: str | None = None, limite: int = 200):
        w = _wazuh()
        al = w.consultar_alertas(pid, nivel_min=max(0, nivel_min), grupos=[grupo] if grupo else None, agente=agente, limite=max(1, min(limite, 500)))
        return _ok({"etiqueta": ETIQUETA, "modo": w.modo, "simulado": True, "agentes": w.listar_agentes(), "alertas": al,
                    "total": len(al)})

    @app.get("/api/combate/partidas/{pid}/exportar")
    async def combate_exportar(pid: str):
        alm = _almacen()
        p = alm.partida(pid)
        if not p:
            return _err("partida desconocida", 404)
        if p["resultado"] is None:
            return _err("la partida aún no tiene resultado: no se puede exportar", 409)
        return _ok({"partida": p, "eventos": alm.eventos(pid), "cadena_integra": alm.verificar_cadena(pid)[0],
                    "alertas_wazuh_simuladas": _wazuh().consultar_alertas(pid), "etiqueta_wazuh": ETIQUETA})

    @app.get("/api/combate/campanas")
    async def combate_campanas():
        import json
        out = []
        base = RAIZ / "data" / "campanas"
        for d in sorted(base.glob("combate-*")) if base.exists() else []:
            f = d / "observaciones.jsonl"
            obs = {}
            if f.exists():
                for linea in f.read_text(encoding="utf-8").splitlines():
                    try:
                        o = json.loads(linea)
                        obs[o["id"]] = o
                    except (ValueError, KeyError):
                        continue
            res = {}
            for o in obs.values():
                res[o["resultado"]] = res.get(o["resultado"], 0) + 1
            lock = d / "lock.pid"
            info = json.loads(lock.read_text(encoding="utf-8")) if lock.exists() else {}
            out.append({"nombre": d.name, "observaciones": len(obs), "por_resultado": res, "invalidas": sum(1 for o in obs.values() if not o["valida"]),
                        "en_ejecucion": bool(info.get("pid")), "latido": info.get("latido"), "ultimo": info.get("ultimo")})
        return _ok({"campanas": out})
