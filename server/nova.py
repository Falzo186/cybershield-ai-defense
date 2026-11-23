"""API de la partida Nova (paquete del profesor): `/api/nova/*`. Delgada: valida el rol DESDE LA SESIÓN (token emitido por el servidor), llama al motor
(`src/lab/nova/motor.py`) y reenvía avisos mínimos por SSE. Un único coordinador (una tarea asyncio) hace `tick()` mientras la partida está EN_CURSO;
no hay otros bucles. Los GET de estado son públicos (el espectador ve su vista); todo POST exige sesión y la validación de equipo se hace en servidor.
"""
import asyncio
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from src.lab.nova import escenario as E
from src.lab import cliente_ollama
from src.lab.nova import ia as IA
from src.lab.nova.motor import ACCIONES_AZUL, ACCIONES_ROJO, ErrorNova, NovaPartida, Reloj, Secretos

ROL = {"general": "ADMIN", "rojo": "RED", "azul": "BLUE", "espectador": "SPECTATOR"}
_E = {"p": None, "tarea": None, "ms": None, "ia": None}
RAIZ = Path(__file__).resolve().parents[1]


MAX_B = float(os.environ.get("CS_NOVA_MAX_B", "8"))   # tope de parámetros (miles de millones) por modelo: la máquina anfitriona tiene ~20 GB de RAM
RECOMENDADO_B = 4.0


def _tam_b(modelo):
    """Tamaño en B según el nombre (`qwen3:4b` → 4.0; `qwen2.5:1.5b` → 1.5). None si el nombre no lo dice."""
    m = re.search(r"(?<![\w.])(\d+(?:\.\d+)?)b(?![a-z])", str(modelo).lower())
    return float(m.group(1)) if m else None


def _es_local(url):
    return (urlparse(url).hostname or "") in ("127.0.0.1", "localhost", "::1")


def _encender_ollama(url, espera_s=25):
    if cliente_ollama.ollama_disponible(url):
        return {"conectado": True, "ya_estaba": True, "mensaje": "Ollama ya estaba encendido"}
    exe = shutil.which("ollama")
    if not exe:
        return {"conectado": False, "mensaje": "No se encontró el programa «ollama» en esta máquina. Instálalo o enciéndelo a mano."}
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    cmd = [exe, "serve"]
    if os.name == "nt":
        kw["creationflags"] = 0x08000000 | 0x00000008          # sin ventana, desprendido
        app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama app.exe"
        if app.exists():                                       # la aplicación de escritorio usa la carpeta de modelos configurada por el usuario
            cmd = [str(app)]
    try:
        subprocess.Popen(cmd, **kw)
    except OSError as e:
        return {"conectado": False, "mensaje": "No se pudo encender Ollama: " + str(e)}
    t0 = time.time()
    while time.time() - t0 < espera_s:
        if cliente_ollama.ollama_disponible(url):
            return {"conectado": True, "ya_estaba": False, "mensaje": "Ollama encendido"}
        time.sleep(0.5)
    return {"conectado": False, "mensaje": "Ollama no respondió a tiempo. Intenta de nuevo o enciéndelo a mano."}


def _apagar_ollama():
    if os.name == "nt":
        for n in ("ollama app.exe", "ollama.exe", "llama-server.exe", "ollama_llama_server.exe"):
            subprocess.run(["taskkill", "/F", "/IM", n], capture_output=True)
    else:
        for n in ("ollama", "llama-server"):
            subprocess.run(["pkill", "-f", n], capture_output=True)
    time.sleep(1)
    return {"conectado": cliente_ollama.ollama_disponible("http://127.0.0.1:11434"), "mensaje": "Ollama apagado (libera RAM y GPU)"}


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
    if p.barrer_presencia():
        _emitir("nova_evento", {"seq": p.seq, "estado": p.estado})
    base = {"id": p.id, "estado": p.estado, "t_s": round(p.t_s(), 1), "duracion_s": p.config["duration_s"], "ronda": p.ronda(), "modalidad": p.config["modalidad"], "ai_mode": p.config["ai_mode"],
            "participantes": [{"nombre": n, "equipo": q["equipo"], "identidad": q["identidad"] if rol in ("ADMIN", "BLUE") or q["equipo"] != "BLUE" else None, "listo": q["listo"], "conectado": q["conectado"]}
                              for n, q in p.participantes.items()],
            "resultado": p.resultado, "puntos": p.puntos if (rol in ("ADMIN", "SPECTATOR") or p.resultado) else None, "continuidad": round(p.continuidad(), 3) if rol in ("ADMIN", "BLUE", "SPECTATOR") else None,
            "rol": rol, "win": p.config["win"] if rol == "ADMIN" else None, "config": {k: v for k, v in p.config.items() if k not in ("win",)} if rol == "ADMIN" else None}
    if rol == "RED" or rol == "ADMIN":
        base["rojo"] = {"credenciales": p.vista_rojo(), "plantillas": list(E.PLANTILLAS_ROJO), "tablas": E.TABLAS, "patron": E.PATRON_CREDENCIAL,
                        "aprobaciones": [{k: v for k, v in a.items() if k not in ("recomendacion", "votos", "decisor", "cierra_s", "detalle", "accion_propuesta")} for a in p.aprobaciones.values() if a["equipo_solicitante"] == "RED"],
                        "extraido": {t: len(f) for t, f in p.extraido.items()}, "misiones": p.misiones("RED"), "mensajes": [x for x in p.mensajes if x["equipo"] == "RED"][-30:]}
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
                      "corridas": len(ctl.runs),
                      "oportunidades": {eq: ctl.oportunidades(eq) for eq in ("RED", "BLUE") if rol in ("ADMIN", "SPECTATOR") or eq == rol},
                      "catalogo_directiva": {"acciones_rojo": sorted(ACCIONES_ROJO), "objetivos": list(IA.OBJETIVOS), "estrategias": list(IA.ESTRATEGIAS), "identidades": [i["id"] for i in E.IDENTIDADES],
                                             "tablas": E.TABLAS, "plantillas": list(E.PLANTILLAS_ROJO), "focos_azul": list(IA.FOCOS_AZUL), "acciones_azul": sorted(ACCIONES_AZUL)}}
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
                  "approval_ttl_s", "elevation_grant_s", "click_delay_s", "seed", "modalidad", "abuse_policy", "ai_prompt_mode", "ai_prompt_budget", "near_miss_min", "approval_mode", "approval_window_s"):
            if k in cuerpo:
                cfg[k] = cuerpo[k]
        if "win" in cuerpo and isinstance(cuerpo["win"], dict):
            cfg["win"] = {**E.WIN_POR_DEFECTO, **{k: v for k, v in cuerpo["win"].items() if k in E.WIN_POR_DEFECTO}}
        cfg.setdefault("approval_mode", "votacion")
        if cfg["approval_mode"] not in ("votacion", "primero"):
            return _err("approval_mode debe ser votacion o primero")
        if "approval_window_s" in cfg and (not isinstance(cfg["approval_window_s"], int) or isinstance(cfg["approval_window_s"], bool) or not 3 <= cfg["approval_window_s"] <= 120):
            return _err("approval_window_s debe ser un entero entre 3 y 120")
        if cfg.get("ai_prompt_mode", "controlado") not in ("controlado", "libre"):
            return _err("ai_prompt_mode debe ser controlado o libre")
        for k_, lo, hi in (("ai_prompt_budget", 1, 50), ("near_miss_min", 2, 6)):
            if k_ in cfg and (not isinstance(cfg[k_], int) or isinstance(cfg[k_], bool) or not lo <= cfg[k_] <= hi):
                return _err(f"{k_} debe ser un entero entre {lo} y {hi}")
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

    @app.post("/api/nova/latido")
    async def nova_latido(request: Request):
        """Presencia automática: cada navegador de jugador avisa que sigue ahí; sin avisos durante 20 s se le marca desconectado."""
        try:
            p = _p()
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        if _rol(request) not in ("RED", "BLUE") or not _nombre(request):
            return JSONResponse({"ok": True, "ignorado": True})
        try:
            p.latido(_nombre(request))
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        return JSONResponse({"ok": True})

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
            modelo = str(spec.get("modelo") or "")[:100] or "qwen3:4b"
            tam = _tam_b(modelo)
            if tam is not None and tam > MAX_B:
                raise ErrorNova(400, f"El modelo {modelo} ({tam:g}B) supera el máximo permitido de {MAX_B:g}B para esta máquina. Usa uno de {RECOMENDADO_B:g}B.", "MODEL_TOO_BIG")
            return IA.OllamaProvider(spec.get("endpoint"), modelo, semilla=int(spec.get("semilla", 0)))
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
        info = [{"nombre": m, "tam_b": _tam_b(m), "permitido": _tam_b(m) is None or _tam_b(m) <= MAX_B, "recomendado": _tam_b(m) is not None and _tam_b(m) <= RECOMENDADO_B} for m in modelos]
        return JSONResponse({"endpoint": url, "conectado": disp, "modelos": modelos, "modelos_info": info, "max_b": MAX_B, "recomendado_b": RECOMENDADO_B, "local": _es_local(url),
                             "error": None if disp else "Ollama está apagado o no responde en ese endpoint"})

    def _admin(request):
        return _rol(request) == "ADMIN"

    @app.post("/api/nova/ollama/iniciar")
    async def nova_ollama_iniciar(request: Request, cuerpo: dict):
        """Solo ADMIN y solo en este equipo (endpoint local): enciende `ollama serve` sin ventana y espera a que responda."""
        if not _admin(request):
            return _err("Solo el administrador enciende Ollama", 403, "FORBIDDEN")
        try:
            url = IA.validar_endpoint(cuerpo.get("endpoint") or "http://127.0.0.1:11434")
        except ErrorNova as e:
            return _err(e.mensaje, e.status, e.motivo)
        if not _es_local(url):
            return _err("Solo se puede encender Ollama en esta misma máquina (127.0.0.1)", 400, "NOT_LOCAL")
        loop = asyncio.get_running_loop()
        r = await loop.run_in_executor(None, _encender_ollama, url)
        return JSONResponse(r, status_code=200 if r["conectado"] else 503)

    @app.post("/api/nova/ollama/detener")
    async def nova_ollama_detener(request: Request, cuerpo: dict):
        """Solo ADMIN: apaga Ollama y sus modelos en esta máquina (libera RAM y GPU)."""
        if not _admin(request):
            return _err("Solo el administrador apaga Ollama", 403, "FORBIDDEN")
        loop = asyncio.get_running_loop()
        r = await loop.run_in_executor(None, _apagar_ollama)
        return JSONResponse(r)

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
            run = await asyncio.get_running_loop().run_in_executor(None, _E["ia"].proponer, eq, cuerpo.get("directiva"))
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

    @app.get("/api/nova/wazuh")
    async def nova_wazuh(request: Request):
        """Capa de observabilidad SEPARADA del juego (nunca influye en el resultado): SIMULADO con las alertas del motor en formato Wazuh; el real solo si
        existe WAZUH_URL (en este laboratorio no hay instancia: NO_CONFIGURADO). Cada alerta lleva `source`."""
        p = _E["p"]
        rol = _rol(request)
        if p is None:
            return JSONResponse({"fuente_activa": "simulated", "estado": "SIMULADO", "alertas": []})
        if rol == "RED":
            return _err("El equipo Rojo no accede al SIEM", 403, "FORBIDDEN")
        nivel = {"BAJA": 3, "MEDIA": 7, "ALTA": 10, "CRITICA": 13}
        al = [{"id": a["id"], "timestamp": a["ts_s"], "rule": {"description": a["titulo"], "level": nivel.get(a["severidad"], 5), "groups": ["cybershield_lab", "nova"]}, "agent": {"name": "nova-" + (a["identidad"] or "base")},
               "source": "simulated", "simulado": True, "etiqueta": "WAZUH SIMULADO"} for a in p.alertas.values()]
        return JSONResponse({"fuente_activa": "simulated", "estado": "SIMULADO", "etiqueta": "WAZUH SIMULADO",
                             "real": {"estado": "NO_CONFIGURADO" if not os.environ.get("WAZUH_URL") else "NO_VERIFICADO", "detalle": "no hay instancia de Wazuh en este laboratorio; no se simula una conexión real"}, "alertas": al})

    @app.get("/api/nova/historial")
    async def nova_historial(request: Request):
        """Historial consultable: resultados persistidos de las partidas Nova (también tras reiniciar el servidor)."""
        import json as _j
        import sqlite3
        try:
            con = sqlite3.connect(_db())
            filas = con.execute("SELECT match_id, resultado, detalle, ts_real FROM nova_results ORDER BY ts_real DESC LIMIT 100").fetchall()
            con.close()
        except sqlite3.Error:
            filas = []
        return JSONResponse({"partidas": [{"match_id": a, "resultado": b, **{k: v for k, v in _j.loads(c).items() if k in ("motivo", "puntos", "continuidad", "tablas_extraidas", "duracion_s")}, "terminada": d} for a, b, c, d in filas]})

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
