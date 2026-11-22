"""API de la partida Nova (paquete del profesor): `/api/nova/*`. Delgada: valida el rol DESDE LA SESIÓN (token emitido por el servidor), llama al motor
(`src/lab/nova/motor.py`) y reenvía avisos mínimos por SSE. Un único coordinador (una tarea asyncio) hace `tick()` mientras la partida está EN_CURSO;
no hay otros bucles. Los GET de estado son públicos (el espectador ve su vista); todo POST exige sesión y la validación de equipo se hace en servidor.
"""
import asyncio
import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from src.lab.nova import escenario as E
from src.lab import cliente_ollama
from src.lab.nova import ia as IA
from src.lab.nova.motor import ErrorNova, NovaPartida, Reloj, Secretos

ROL = {"general": "ADMIN", "rojo": "RED", "azul": "BLUE", "espectador": "SPECTATOR"}
_E = {"p": None, "tarea": None, "ms": None, "ia": None}
RAIZ = Path(__file__).resolve().parents[1]


def _err(msg, status=400, motivo=None):
    return JSONResponse({"error": msg, "mensaje": msg, "motivo": motivo}, status_code=status)


def _rol(request):
    return ROL.get(getattr(request.state, "equipo", None), "SPECTATOR")


def _nombre(request):
    p = getattr(request.state, "participante", None)
    return p.nombre if p else None


def _db():
    return os.environ.get("CS_NOVA_DB") or str(RAIZ / "data" / "nova.db")


def _emitir(tipo, datos):
    if _E["ms"]:
        try:
            _E["ms"].emitir(tipo, datos)
        except Exception:  # noqa: BLE001
            pass


def _estado_publico(p, rol, nombre):
    """Lo que ve cada rol. La visibilidad se filtra AQUÍ: el Rojo no ve el catálogo, el Azul no ve el inventario del Rojo."""
    base = {"id": p.id, "estado": p.estado, "t_s": round(p.t_s(), 1), "duracion_s": p.config["duration_s"], "ronda": p.ronda(), "modalidad": p.config["modalidad"], "ai_mode": p.config["ai_mode"],
            "participantes": [{"nombre": n, "equipo": q["equipo"], "identidad": q["identidad"] if rol in ("ADMIN", "BLUE") or q["equipo"] != "BLUE" else None, "listo": q["listo"], "conectado": q["conectado"]}
                              for n, q in p.participantes.items()],
            "resultado": p.resultado, "puntos": p.puntos if (rol in ("ADMIN", "SPECTATOR") or p.resultado) else None, "continuidad": round(p.continuidad(), 3) if rol in ("ADMIN", "BLUE", "SPECTATOR") else None,
            "rol": rol, "win": p.config["win"] if rol == "ADMIN" else None, "config": {k: v for k, v in p.config.items() if k not in ("win",)} if rol == "ADMIN" else None}
    if rol == "RED" or rol == "ADMIN":
        base["rojo"] = {"credenciales": p.vista_rojo(), "plantillas": list(E.PLANTILLAS_ROJO), "tablas": E.TABLAS, "patron": E.PATRON_CREDENCIAL,
                        "aprobaciones": [{k: v for k, v in a.items() if k != "recomendacion"} for a in p.aprobaciones.values() if a["equipo_solicitante"] == "RED"],
                        "extraido": {t: len(f) for t, f in p.extraido.items()}}
    if rol == "BLUE" and nombre:
        base["azul"] = p.vista_azul(nombre)
    if rol == "ADMIN":
        base["azul_todos"] = {"alertas": list(p.alertas.values()), "incidentes": list(p.incidentes.values()), "aprobaciones": list(p.aprobaciones.values()), "emails": list(p.emails.values())}
        base["catalogo"] = p.catalogo_admin()
        base["metricas"] = p.metricas()
    ctl = _E["ia"]
    if ctl is not None:
        base["ia"] = {"modos": p.config["ai_mode"], "proveedores": {eq: {"kind": pr.kind, "etiqueta": pr.etiqueta, "endpoint": pr.endpoint, "modelo": pr.modelo} for eq, pr in ctl.proveedores.items()
                                                                  if rol in ("ADMIN", "SPECTATOR") or eq == {"RED": "RED", "BLUE": "BLUE"}.get(rol)},
                      "corridas": len(ctl.runs)}
    if rol == "SPECTATOR":
        base["publico"] = {"extraido": {t: len(f) for t, f in p.extraido.items()}, "alertas": len(p.alertas), "incidentes": len(p.incidentes)}
    return base


async def _coordinador():
    """UN solo bucle por partida: tick cada segundo mientras EN_CURSO. Termina al detener/finalizar (no deja tareas vivas)."""
    while True:
        p = _E["p"]
        if p is None or p.estado not in ("EN_CURSO",):
            _E["tarea"] = None
            return
        try:
            antes = p.seq
            p.tick()
            if p.seq != antes:
                _emitir("nova_evento", {"seq": p.seq, "estado": p.estado})
        except Exception:  # noqa: BLE001 - un fallo del tick no debe dejar la partida colgada: pasa a ERROR
            try:
                p.estado = "ERROR"
            except Exception:  # noqa: BLE001
                pass
            _E["tarea"] = None
            return
        await asyncio.sleep(1)


def _arrancar():
    if _E["tarea"] is None or _E["tarea"].done():
        _E["tarea"] = asyncio.create_task(_coordinador())


def registrar(app, ms=None):
    _E["ms"] = ms

    def _p():
        if _E["p"] is None:
            raise ErrorNova(404, "No hay ninguna partida Nova: el administrador debe crearla", "NO_MATCH")
        return _E["p"]

    @app.get("/api/nova/estado")
    async def nova_estado(request: Request):
        p = _E["p"]
        if p is None:
            return JSONResponse({"estado": None, "mensaje": "No hay partida Nova creada"})
        return JSONResponse(_estado_publico(p, _rol(request), _nombre(request)))

    @app.post("/api/nova/partida")
    async def nova_crear(request: Request, cuerpo: dict):
        """Solo el administrador. Crea la partida en CONFIGURACION (nada corre). `time_scale` (≤ 60) acelera el reloj para ensayos."""
        if _rol(request) != "ADMIN":
            return _err("Solo el administrador crea partidas Nova", 403, "FORBIDDEN")
        if _E["p"] is not None and _E["p"].estado not in ("FINALIZADA", "CANCELADA"):
            return _err("Ya hay una partida Nova sin terminar: deténla antes de crear otra", 409, "MATCH_EXISTS")
        cfg = {}
        for k in ("duration_s", "round_s", "guess_attempts_per_round", "guess_attempts_per_match", "guess_cooldown_s", "guess_lockout_after_fails", "lockout_s", "min_continuity", "detect_prob_fail",
                  "approval_ttl_s", "elevation_grant_s", "click_delay_s", "seed", "modalidad", "abuse_policy"):
            if k in cuerpo:
                cfg[k] = cuerpo[k]
        if "win" in cuerpo and isinstance(cuerpo["win"], dict):
            cfg["win"] = {**E.WIN_POR_DEFECTO, **{k: v for k, v in cuerpo["win"].items() if k in E.WIN_POR_DEFECTO}}
        if cfg.get("modalidad", "BALANCED") not in ("RED_ADVANTAGE", "BLUE_ADVANTAGE", "BALANCED"):
            return _err("modalidad no válida")
        try:
            escala = max(0.1, min(60.0, float(cuerpo.get("time_scale", 1.0))))
        except (TypeError, ValueError):
            return _err("time_scale debe ser un número")
        _E["p"] = NovaPartida(config=cfg, reloj=Reloj(virtual=False, escala=escala), secretos=Secretos(), db=_db())
        _E["ia"] = IA.ControlIA(_E["p"])
        return JSONResponse(_estado_publico(_E["p"], "ADMIN", None))

    def _ejecuta(request, fn, *a, **kw):
        try:
            fn(*a, **kw)
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        p = _E["p"]
        _emitir("nova_estado", {"estado": p.estado})
        return JSONResponse(_estado_publico(p, _rol(request), _nombre(request)))

    @app.post("/api/nova/sala")
    async def nova_sala(request: Request):
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        return _ejecuta(request, p.abrir_sala, _rol(request))

    @app.post("/api/nova/unirse")
    async def nova_unirse(request: Request, cuerpo: dict):
        """El jugador entra a la partida con su sesión: equipo desde el token (nunca del cliente). Azul recibe identidad (máx. 4)."""
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        rol = _rol(request)
        if rol == "ADMIN" or not _nombre(request):
            return _err("El administrador no se une como jugador; los jugadores necesitan una sesión", 400)
        return _ejecuta(request, p.unirse, _nombre(request), rol, cuerpo.get("identidad") if rol == "BLUE" else None)

    @app.post("/api/nova/listo")
    async def nova_listo(request: Request, cuerpo: dict):
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        return _ejecuta(request, p.marcar_listo, _nombre(request), bool(cuerpo.get("listo", True)))

    @app.post("/api/nova/reasignar")
    async def nova_reasignar(request: Request, cuerpo: dict):
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        return _ejecuta(request, p.reasignar, _rol(request), cuerpo.get("jugador"), cuerpo.get("identidad"))

    @app.post("/api/nova/lista")
    async def nova_lista(request: Request):
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        return _ejecuta(request, p.marcar_lista, _rol(request))

    @app.post("/api/nova/iniciar")
    async def nova_iniciar(request: Request, cuerpo: dict):
        """ÚNICA vía a EN_CURSO: administrador + confirm=true + idempotency_key. Arranca el coordinador (un solo bucle)."""
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        r = _ejecuta(request, p.iniciar, _rol(request), bool(cuerpo.get("confirm")), cuerpo.get("idempotency_key"))
        if r.status_code == 200:
            _arrancar()
        return r

    @app.post("/api/nova/pausar")
    async def nova_pausar(request: Request):
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        return _ejecuta(request, p.pausar, _rol(request))

    @app.post("/api/nova/reanudar")
    async def nova_reanudar(request: Request):
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        r = _ejecuta(request, p.reanudar, _rol(request))
        if r.status_code == 200:
            _arrancar()
        return r

    @app.post("/api/nova/detener")
    async def nova_detener(request: Request, cuerpo: dict):
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        r = _ejecuta(request, p.detener, _rol(request), bool(cuerpo.get("cancelar")))
        t = _E["tarea"]
        if t is not None and not t.done():
            t.cancel()          # stop no deja tareas vivas
        _E["tarea"] = None
        if _E["ia"] is not None:
            _E["ia"].cancelar_todo()
        return r

    # ── IA: configuración, propuestas, confirmación (assist) y registro de corridas ─────────────────────
    def _proveedor(equipo, spec):
        tipo = (spec or {}).get("tipo", "scripted")
        if tipo == "scripted":
            return IA.ScriptedProvider(equipo, (spec or {}).get("politica", "heuristica"))
        if tipo == "offline":
            return IA.OfflineProvider()
        if tipo == "ollama":
            return IA.OllamaProvider(spec.get("endpoint"), str(spec.get("modelo") or "")[:100] or "qwen3:8b", semilla=int(spec.get("semilla", 0)))
        raise ErrorNova(400, "tipo de proveedor no válido (scripted, ollama u offline)")

    @app.post("/api/nova/ia/config")
    async def nova_ia_config(request: Request, cuerpo: dict):
        """Solo el administrador: modo por equipo (off/assist/auto) y proveedor (scripted etiquetado, Ollama con anti-SSRF, offline)."""
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        if _rol(request) != "ADMIN":
            return _err("Solo el administrador configura la IA", 403, "FORBIDDEN")
        ctl = _E["ia"]
        try:
            for eq in ("RED", "BLUE"):
                c = cuerpo.get(eq)
                if not isinstance(c, dict):
                    continue
                ctl.configurar(eq, c.get("modo"), _proveedor(eq, c["proveedor"]) if c.get("proveedor") else None)
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        _emitir("nova_estado", {"estado": p.estado})
        return JSONResponse(_estado_publico(p, "ADMIN", None))

    @app.get("/api/nova/ollama/estado")
    async def nova_ollama(request: Request, endpoint: str = "http://127.0.0.1:11434"):
        """Estado real del endpoint (nada simulado): conexión, modelos y por qué falla. Endpoint validado contra SSRF."""
        try:
            url = IA.validar_endpoint(endpoint)
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        loop = asyncio.get_running_loop()
        disp = await loop.run_in_executor(None, cliente_ollama.ollama_disponible, url)
        modelos = await loop.run_in_executor(None, cliente_ollama.listar_modelos, url) if disp else []
        return JSONResponse({"endpoint": url, "conectado": disp, "modelos": modelos, "error": None if disp else "Ollama no responde en ese endpoint"})

    @app.post("/api/nova/ia/proponer")
    async def nova_ia_proponer(request: Request, cuerpo: dict):
        """Pide UNA propuesta a la IA de TU equipo (Rojo→RED, Azul→BLUE; el administrador, cualquiera). Corre fuera del bucle de eventos."""
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        rol, eq = _rol(request), cuerpo.get("equipo")
        if rol not in ("ADMIN", "RED", "BLUE") or (rol != "ADMIN" and eq != rol):
            return _err("Solo puedes pedir propuestas a la IA de tu propio equipo", 403, "WRONG_TEAM")
        try:
            run = await asyncio.get_running_loop().run_in_executor(None, _E["ia"].proponer, eq)
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        _emitir("nova_evento", {"seq": p.seq, "estado": p.estado})
        return JSONResponse({k: v for k, v in run.items() if k not in ("entrada", "salida_cruda")})

    @app.post("/api/nova/ia/confirmar")
    async def nova_ia_confirmar(request: Request, cuerpo: dict):
        try:
            p = _p()
            rol = _rol(request)
            run = _E["ia"].propuestas.get(cuerpo.get("run_id"))
            if rol not in ("ADMIN", "RED", "BLUE") or (run and rol != "ADMIN" and run["team"] != rol):
                return _err("Solo un humano del mismo equipo confirma una propuesta de su IA", 403, "WRONG_TEAM")
            res = _E["ia"].descartar(cuerpo.get("run_id")) if cuerpo.get("descartar") else _E["ia"].confirmar(cuerpo.get("run_id"), _nombre(request) or "admin")
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        _emitir("nova_evento", {"seq": p.seq, "estado": p.estado})
        return JSONResponse(res or {"estado": "DESCARTADA"})

    @app.get("/api/nova/ia/runs")
    async def nova_ia_runs(request: Request):
        if _E["ia"] is None:
            return JSONResponse({"corridas": []})
        rol = _rol(request)
        return JSONResponse({"corridas": _E["ia"].publico(None if rol in ("ADMIN", "SPECTATOR") else rol if rol in ("RED", "BLUE") else "-")})

    @app.post("/api/nova/accion")
    async def nova_accion(request: Request, cuerpo: dict):
        """Entrada única de acciones: el actor sale de la SESIÓN (equipo y nombre), no del cuerpo. El motor valida con el pipeline de 10 pasos."""
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        rol = _rol(request)
        if rol == "SPECTATOR":
            return _err("Los espectadores solo observan", 403, "FORBIDDEN")
        accion = {"action_type": cuerpo.get("action_type"), "params": cuerpo.get("params") or {}, "idempotency_key": cuerpo.get("idempotency_key"),
                  "actor": {"kind": "human", "team": rol, "user": _nombre(request) or "admin"}}
        r = p.ejecutar(accion)
        _emitir("nova_evento", {"seq": p.seq, "estado": p.estado})
        if p.estado in ("FINALIZADA",):
            t = _E["tarea"]
            if t is not None and not t.done():
                t.cancel()
            _E["tarea"] = None
            _emitir("nova_estado", {"estado": p.estado})
        return JSONResponse(r, status_code=200 if r["ok"] else (403 if r["reject_reason"] in ("WRONG_TEAM", "PERMISSION_DENIED", "NOT_YOUR_INBOX", "CREDENTIAL_NOT_KNOWN", "CREDENTIAL_UNUSABLE", "IDENTITY_LOCKED", "FORBIDDEN") else 409 if r["reject_reason"] in ("MATCH_NOT_RUNNING", "INVALID_TRANSITION", "INVALID_STATE")
                                                                  else 429 if r["reject_reason"] in ("COOLDOWN", "BUDGET_EXCEEDED") else 400))

    @app.get("/api/nova/eventos")
    async def nova_eventos(request: Request, after_seq: int = 0):
        p = _E["p"]
        if p is None:
            return JSONResponse({"eventos": [], "ultimo": 0})
        ev = p.eventos(_rol(request), after_seq)
        return JSONResponse({"eventos": ev, "ultimo": ev[-1]["seq"] if ev else after_seq, "estado": p.estado})

    @app.get("/api/nova/descarga")
    async def nova_descarga(request: Request, formato: str = "json"):
        """Solo con datos REALMENTE extraídos y a quien corresponde (Rojo, administrador y espectadores tras el resultado)."""
        p = _E["p"]
        if p is None:
            return _err("No hay partida", 404, "NO_MATCH")
        rol = _rol(request)
        if rol == "BLUE" or (rol == "SPECTATOR" and not p.resultado):
            return _err("No disponible para tu rol", 403, "FORBIDDEN")
        try:
            tipo, cuerpo = p.descarga(formato)
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        return Response(content=cuerpo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="nova_{p.id}.{formato}"'})
