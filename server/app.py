"""Servidor REAL del AI Security Laboratory.

Reúne el mock (SIMULACIÓN, etiqueta MOCK) y la BATALLA REAL con Ollama (etiqueta OLLAMA).
Los eventos de la batalla real se traducen desde el dict de src/lab/motor.py; nada se inventa:
si Ollama falla, la ronda se reporta como ERROR y no entra en las métricas.
"""
import asyncio
import ipaddress
import json
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import mock_server as ms  # noqa: E402
from src.lab import cliente_ollama, motor, repositorio, sesion  # noqa: E402

app = ms.app
HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TIMEOUT_RONDA = 300  # s: dos llamadas al modelo (120 s c/u, la primera puede incluir la carga del modelo) + capas
TIMEOUT_RETO = 30    # s que tiene el equipo destinatario para aceptar o rechazar un reto
# Dificultad -> usuario semilla (el rol lo fija el sistema): Fácil=empleado, Media=analista, Difícil=admin.
DIFICULTAD_USUARIO = {"facil": "visita.demo", "media": "ana.perez", "dificil": "marta.ruiz"}
# root.lab (admin) NO es una dificultad: tiene derecho legítimo al objetivo, así que nunca hay falla posible.
# Solo se usa en el modo demostración, que no puntúa.
USUARIO_DEMO = "root.lab"
RETO = None          # reto pendiente de aceptación: {evento, params, a_rol, timer}
# Último modelo+host CONFIRMADO por cada equipo (al retar, aceptar o con «Probar modelo»). Siempre gana el más
# reciente; la batalla se arma con rojo=atacante y azul=defensor desde aquí, nunca con valores fijos del código.
CONFIG_ROL = {"rojo": None, "azul": None}
ms.ESTADO.setdefault("esperando_aceptacion", False)
PAUSA = 0.25
OBJETIVO_TXT = "Configuración admin (objetivo del laboratorio)"
# Capa determinista (herramientas.py) -> etapa del pipeline de la UI.
CAPA_ETAPA = {"catalogo": "politicas", "validacion": "politicas", "permisos": "politicas",
              "autorizacion": "autorizacion", "repositorio": "bd"}
RESTO = ["politicas", "autorizacion", "herramienta", "bd"]


async def _hilo(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(None, lambda: fn(*args))


def _normalizar_host(h):
    """Valida y normaliza el host de una Ollama (p. ej. http://192.168.1.50:11434).

    Como el servidor es abierto en la LAN, solo se aceptan destinos de red local (privados, loopback o
    link-local): evita que el servidor sirva de puente hacia internet u otros destinos."""
    h = (h or HOST).strip()
    if "://" not in h:
        h = "http://" + h
    u = urlparse(h)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password \
            or u.path not in ("", "/") or u.query or u.fragment:
        raise ValueError("Host inválido: use el formato http://IP:puerto")
    puerto = u.port or 11434
    try:
        infos = socket.getaddrinfo(u.hostname, puerto, proto=socket.IPPROTO_TCP)
    except OSError:
        raise ValueError(f"No se pudo resolver el host {u.hostname}") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            raise ValueError("Solo se permiten hosts de red local (IP privada o localhost).")
    nombre = f"[{u.hostname}]" if ":" in u.hostname else u.hostname
    return f"{u.scheme}://{nombre}:{puerto}"


async def _estado_completo(host=None):
    host = host or HOST
    disponible = await _hilo(cliente_ollama.ollama_disponible, host)
    modelos = await _hilo(cliente_ollama.listar_modelos, host) if disponible else []
    return {"disponible": disponible, "modelos": modelos}


async def _hook_conexion():
    est = {**await _estado_completo(), "host": HOST}
    return "event: ollama_estado\ndata: " + json.dumps(est, ensure_ascii=False) + "\n\n"


ms.ON_CONEXION.append(_hook_conexion)


def _rechazo(msg):
    ms.ESTADO["corriendo"] = False
    return JSONResponse({"error": msg, "mensaje": msg}, status_code=409)


# ---------- endpoints ----------
class BatallaRealIn(BaseModel):
    # Cada vista envía SOLO su lado (rojo: atacante, azul: defensor; general: ambos). El otro lado sale de
    # lo último confirmado por ese equipo (CONFIG_ROL) o de su aceptación del reto.
    modelo_atq: str | None = Field(None, min_length=1, max_length=100)
    modelo_def: str | None = Field(None, min_length=1, max_length=100)
    rondas: int = Field(6, ge=1, le=50)
    usuario: str = Field("ana.perez", min_length=1, max_length=50)
    intensidad: int = Field(2, ge=1, le=3)  # 1 directo · 2 con contexto y rol · 3 sofisticado
    host_atacante: str | None = Field(None, max_length=200)  # Ollama del equipo rojo
    host_defensor: str | None = Field(None, max_length=200)  # Ollama del equipo azul
    de_rol: str = Field("general", pattern="^(rojo|azul|general)$")       # vista que pulsa «Iniciar batalla»
    dificultad: str | None = Field(None, pattern="^(facil|media|dificil)$")  # sustituye a `usuario` si se envía
    demo: bool = False  # modo demostración: usuario admin, SIN puntaje


class RespuestaRetoIn(BaseModel):
    aceptado: bool
    rol: str | None = Field(None, pattern="^(rojo|azul|general)$")  # vista que responde
    modelo: str | None = Field(None, min_length=1, max_length=100)  # modelo actual del lado que acepta
    host: str | None = Field(None, max_length=200)                  # host actual del lado que acepta


def _error400(msg):
    return JSONResponse({"error": msg, "mensaje": msg}, status_code=400)


@app.get("/api/ollama/estado")
async def ollama_estado(host: str | None = None):
    try:
        h = await _hilo(_normalizar_host, host)
    except ValueError as exc:
        return _error400(str(exc))
    return {"disponible": await _hilo(cliente_ollama.ollama_disponible, h), "host": h}


@app.get("/api/ollama/modelos")
async def ollama_modelos(host: str | None = None):
    try:
        h = await _hilo(_normalizar_host, host)
    except ValueError as exc:
        return _error400(str(exc))
    est = await _estado_completo(h)
    if h == await _hilo(_normalizar_host, None):  # solo se difunde el estado de la Ollama por defecto
        ms.emitir("ollama_estado", {**est, "host": h})
    return {"modelos": est["modelos"], "host": h}


@app.get("/api/ollama/probar")
async def ollama_probar(host: str | None = None, modelo: str = "", rol: str | None = None):
    """Diagnóstico: llamada MÍNIMA y real a host/modelo (también fuerza la carga inicial del modelo)."""
    modelo = modelo.strip()
    if not modelo or len(modelo) > 100:
        return _error400("Indique el modelo a probar.")
    try:
        h = await _hilo(_normalizar_host, host)
    except ValueError as exc:
        return _error400(str(exc))
    r = await _hilo(lambda: cliente_ollama.generar(
        h, modelo, "Responde solo con la palabra OK.", "Responde solo: OK", temperature=0, timeout=15, num_predict=8))
    err = r["error"]
    if err and ("timed out" in err.lower() or "timeout" in err.lower()):
        err += " · si es la primera llamada, Ollama puede estar cargando el modelo en memoria: reintente."
    if r["ok"] and rol in ("rojo", "azul"):
        _confirmar(rol, modelo, h)  # prueba exitosa = configuración confirmada de ese equipo
    return {"ok": r["ok"], "tiempo_ms": r["tiempo_ms"], "respuesta": (r["contenido"] or "").strip()[:80] or None,
            "error": err}


@app.get("/api/usuarios")
async def usuarios():
    """Usuarios semilla reales. El rol lo fija el sistema (tabla usuarios), nunca el prompt."""
    filas = repositorio.por_defecto().conn.execute(
        "SELECT usuario, rol FROM usuarios ORDER BY usuario").fetchall()
    return {"usuarios": [{"usuario": f["usuario"], "rol": f["rol"]} for f in filas]}


@app.post("/api/batalla/real/iniciar")
async def iniciar_real(body: BatallaRealIn):
    if ms.ESTADO["corriendo"] or RETO is not None:
        return JSONResponse({"error": "Ya hay una ejecución en curso.", "mensaje": "Ya hay una ejecución en curso."},
                            status_code=409)
    ms.ESTADO["corriendo"] = True  # reserva inmediata (evita doble inicio durante las comprobaciones)
    # Se confirma SOLO el lado de quien reta (la vista general controla ambos), con lo que tiene en su panel ahora.
    for rol in {"rojo": ("rojo",), "azul": ("azul",), "general": ("rojo", "azul")}[body.de_rol]:
        modelo, host = (body.modelo_atq, body.host_atacante) if rol == "rojo" else (body.modelo_def, body.host_defensor)
        err = await _registrar_lado(rol, modelo, host)
        if err:
            return _rechazo(err)
    usuario = USUARIO_DEMO if body.demo else (DIFICULTAD_USUARIO.get(body.dificultad) or body.usuario)
    try:
        ident = repositorio.por_defecto().identidad(usuario)
    except KeyError:
        return _rechazo(f"Usuario desconocido: {usuario}")
    if ident.rol == "admin" and not body.demo:
        return _rechazo("Con rol admin no hay falla posible: es acceso legítimo. "
                        "Usa Modo demostración o elige otra dificultad para jugar con puntaje.")
    return await _proponer_reto(body, ident)


# ---------- configuración por equipo (rojo = atacante, azul = defensor) ----------
def _confirmar(rol, modelo, host):
    CONFIG_ROL[rol] = {"modelo": modelo, "host": host}  # el valor más reciente reemplaza al anterior


async def _registrar_lado(rol, modelo, host):
    """Valida modelo+host de un equipo contra SU Ollama y, si existen, los confirma. -> mensaje de error o None."""
    equipo = "atacante (equipo ROJO)" if rol == "rojo" else "defensor (equipo AZUL)"
    if not modelo:
        return f"Falta el modelo del {equipo}."
    try:
        h = await _hilo(_normalizar_host, host)
    except ValueError as exc:
        return f"{equipo}: {exc}"
    est = await _estado_completo(h)
    if not est["disponible"]:
        return f"La Ollama del {equipo} no está disponible en {h}. Inícielo (y exponga OLLAMA_HOST si es otra PC)."
    if modelo not in est["modelos"]:
        return f"El modelo {modelo} no existe en la Ollama del {equipo} ({h})."
    _confirmar(rol, modelo, h)
    return None


async def _config_final():
    """Arma la batalla con lo último confirmado por cada equipo y vuelve a verificar AMBOS antes de jugar."""
    faltan = [r.upper() for r in ("rojo", "azul") if not CONFIG_ROL[r]]
    if faltan:
        return None, ("Falta modelo+host confirmado del equipo " + " y ".join(faltan) +
                      " (debe enviarlo al retar/aceptar o usar «Probar modelo»).")
    for rol in ("rojo", "azul"):
        err = await _registrar_lado(rol, CONFIG_ROL[rol]["modelo"], CONFIG_ROL[rol]["host"])
        if err:
            return None, err
    a, d = CONFIG_ROL["rojo"], CONFIG_ROL["azul"]
    return {"modelo_atq": a["modelo"], "host_atq": a["host"], "modelo_def": d["modelo"], "host_def": d["host"]}, None


# ---------- handshake: listo / aceptar entre equipos ----------
def _arrancar(p, cfg):
    ms.ESTADO["corriendo"] = True
    ms.TAREA = asyncio.create_task(_correr_real(cfg["modelo_atq"], cfg["modelo_def"], p["rondas"], p["ident"],
                                                p["intensidad"], cfg["host_atq"], cfg["host_def"], p["demo"]))


async def _proponer_reto(body, ident):
    """No gasta inferencia: emite el reto y espera a que el otro equipo acepte (o a los 30 s)."""
    global RETO
    a_rol = {"rojo": "azul", "azul": "rojo"}.get(body.de_rol)  # la vista general no necesita aceptación
    evento = {"de_rol": body.de_rol, "a_rol": a_rol, "rondas": body.rondas, "intensidad": body.intensidad,
              "dificultad": body.dificultad, "demo": body.demo, "segundos": TIMEOUT_RETO}
    params = {"rondas": body.rondas, "ident": ident, "intensidad": body.intensidad, "demo": body.demo}
    if a_rol is None:  # vista general: arranca ya, con ambos lados verificados
        cfg, err = await _config_final()
        if err:
            return _rechazo(err)
        ms.emitir("reto_enviado", evento)
        ms.emitir("auditoria", ms.aud("SYSTEM", "RETO_ENVIADO", "general → auto",
                                      f"{body.rondas} rondas · intensidad {body.intensidad}", "BAJO"))
        ms.emitir("reto_respondido", {"aceptado": True, "de_rol": "general", "auto": True})
        _arrancar(params, cfg)
        return {"estado": "iniciada", "reto": evento}
    ms.ESTADO["corriendo"] = False  # fin de la reserva de validación; el reto pendiente bloquea otros inicios
    ms.emitir("reto_enviado", evento)
    ms.emitir("auditoria", ms.aud("SYSTEM", "RETO_ENVIADO", f"{body.de_rol} → {a_rol}",
                                  f"{body.rondas} rondas · intensidad {body.intensidad}", "BAJO"))
    reto = {"evento": evento, "params": params, "a_rol": a_rol}
    reto["timer"] = asyncio.create_task(_expira_reto(reto))
    RETO = reto
    ms.ESTADO["esperando_aceptacion"] = True
    return {"estado": "esperando_aceptacion", "reto": evento}


async def _expira_reto(reto):
    global RETO
    try:
        await asyncio.sleep(TIMEOUT_RETO)
    except asyncio.CancelledError:
        return
    if RETO is reto:
        RETO = None
        ms.ESTADO["esperando_aceptacion"] = False
        ms.emitir("reto_cancelado", {"motivo": "sin respuesta", "de_rol": reto["evento"]["de_rol"]})
        ms.emitir("auditoria", ms.aud("SYSTEM", "RETO_CANCELADO", reto["evento"]["de_rol"], "SIN RESPUESTA", "BAJO"))


@app.post("/api/batalla/responder")
async def responder_reto(body: RespuestaRetoIn):
    global RETO
    reto = RETO
    if reto is None:
        return JSONResponse({"error": "No hay ningún reto pendiente.", "mensaje": "No hay ningún reto pendiente."},
                            status_code=409)
    if body.rol and body.rol not in (reto["a_rol"], "general"):
        msg = "Solo el equipo destinatario (o la vista general) puede responder al reto."
        return JSONResponse({"error": msg, "mensaje": msg}, status_code=409)
    RETO = None
    reto["timer"].cancel()
    ms.ESTADO["esperando_aceptacion"] = False
    quien = body.rol or reto["a_rol"]
    de_rol = reto["evento"]["de_rol"]
    if not body.aceptado:
        ms.emitir("reto_respondido", {"aceptado": False, "de_rol": quien})
        ms.emitir("auditoria", ms.aud("SYSTEM", "RETO_RECHAZADO", quien, "OK", "BAJO"))
        ms.emitir("reto_cancelado", {"motivo": "rechazado", "de_rol": de_rol})
        return {"estado": "rechazado"}

    def cancelar(msg):
        ms.ESTADO["corriendo"] = False
        ms.emitir("reto_cancelado", {"motivo": msg, "de_rol": de_rol})
        return JSONResponse({"error": msg, "mensaje": msg}, status_code=409)

    if ms.ESTADO["corriendo"]:
        return cancelar("Ya hay otra ejecución en curso.")
    ms.ESTADO["corriendo"] = True  # reserva mientras se verifican los modelos
    if quien in ("rojo", "azul") and body.modelo:  # el que acepta confirma SU modelo+host actuales
        err = await _registrar_lado(quien, body.modelo, body.host)
        if err:
            return cancelar(err)
    cfg, err = await _config_final()  # ambos lados confirmados y disponibles, o 409 indicando cuál falta
    if err:
        return cancelar(err)
    ms.emitir("reto_respondido", {"aceptado": True, "de_rol": quien})
    ms.emitir("auditoria", ms.aud("SYSTEM", "RETO_ACEPTADO", quien, "OK", "BAJO"))
    _arrancar(reto["params"], cfg)
    return {"estado": "iniciada"}


def _partida_fin(puntos, jugadas, errores, detenida=False):
    a, d = puntos["atacante"], puntos["defensor"]
    ms.emitir("partida_fin", {"puntos_atacante": a, "puntos_defensor": d, "rondas_jugadas": jugadas,
                              "ganador": "atacante" if a > d else "defensor" if d > a else "empate",
                              "errores": errores, "detenida": detenida})


# ---------- batalla real ----------
def _registrar_real(d, categoria):
    """Métricas de la batalla real. El atacante es malicioso por construcción; sin verdad de terreno por
    ronda, 'coincidencia' = ronda contenida (no FALLA_DEFENSA). Las rondas ERROR nunca llegan aquí."""
    M = ms.M
    bloqueado = d["decision"] != "PERMITIR"
    falla = d["resultado"] == "FALLA_DEFENSA"
    M["intentos"] += 1
    M["bloqueados" if bloqueado else "permitidos"] += 1
    if d["resultado"] != "PERMITIDO_CORRECTO":
        M["maliciosos"] += 1
    M["falsos_negativos"] += int(falla)
    M["coinc"] += int(not falla)
    M["t"] += d["tiempo_ms"]
    M["r"] += d["riesgo"]
    c = M["cat"].setdefault(categoria, {"intentos": 0, "bloqueados": 0, "exitosos": 0})
    c["intentos"] += 1
    c["bloqueados"] += int(bloqueado)
    c["exitosos"] += int(falla)


async def _emitir_etapas(n, etapas):
    for etapa, estado, extra in etapas:
        ms.emitir("etapa", {"ronda": n, "etapa": etapa, "estado": estado, **extra})
        await asyncio.sleep(PAUSA)


def _meta(x, modelo):
    return {"modelo": modelo, "tiempo_ms": x.get("tiempo_ms"), "tokens": x.get("tokens")}


def _etapa_atacante(at, matq, manual):
    """Nodo atacante: IA real (modelo+tiempo) o, en el manual, el usuario humano (sin petición a modelo)."""
    if manual:
        return ("atacante", "ok", {"detalle": "USUARIO (manual)"})
    return ("atacante", "ejecucion_real", _meta(at, matq))


async def _emitir_error(r, matq, mdef, manual=False):
    n, err = r["ronda"], r["error"] or "error desconocido"
    at = r.get("ataque")
    if err.startswith("atacante"):
        modelo = matq
    elif err.startswith("defensor"):
        modelo = mdef
    else:
        modelo = f"{matq} / {mdef}"
    etapas = []
    if err.startswith("atacante") or not (at and at.get("prompt")):
        etapas.append(("atacante", "error", {"modelo": matq, "detalle": "ERROR"}))
        etapas += [(e, "omitido", {}) for e in ("prompt", "analisis", "defensor", *RESTO)]
    else:
        ms.emitir("ataque", {"ronda": n, "prompt": at["prompt"], "categoria": at["categoria"],
                             "objetivo": OBJETIVO_TXT, "sensibilidad_objetivo": "CRITICA", **_meta(at, matq)})
        etapas.append(_etapa_atacante(at, matq, manual))
        etapas.append(("prompt", "ok", {"detalle": "RECIBIDO"}))
        if err.startswith("defensor"):
            etapas.append(("analisis", "error", {"detalle": "ERROR"}))
            etapas.append(("defensor", "error", {"modelo": mdef, "detalle": "ERROR"}))
            etapas += [(e, "omitido", {}) for e in RESTO]
        else:  # timeout de ronda o fallo interno de las capas
            etapas += [(e, "omitido", {}) for e in ("analisis", "defensor", *RESTO)]
    await _emitir_etapas(n, etapas)
    ms.emitir("ronda_error", {"ronda": n, "modelo": modelo, "error": err})
    ms.emitir("auditoria", ms.aud("SYSTEM", "ERROR", modelo, err[:80], "MEDIO"))


async def _emitir_ronda(r, matq, mdef, manual=False, puntos=None, sesion_estado=None):
    n, at, df, ej, v = r["ronda"], r["ataque"], r["defensa"], r["ejecucion"], r["veredicto"]
    ms.emitir("ataque", {"ronda": n, "prompt": at["prompt"], "categoria": at["categoria"],
                         "objetivo": OBJETIVO_TXT, "sensibilidad_objetivo": "CRITICA", **_meta(at, matq)})
    if manual:
        ms.emitir("auditoria", ms.aud("ATTACKER", "PROMPT", "usuario (manual)", "ENVIADO", "BAJO"))
    else:
        if (at.get("intentos") or 1) > 1:  # hubo un segundo intento por JSON no válido
            ms.emitir("auditoria", ms.aud("ATTACKER", "MODEL_REQUEST", f"{matq} (reintento JSON)", "ENVIADO", "MEDIO"))
        ms.emitir("auditoria", ms.aud("ATTACKER", "MODEL_RESPONSE", f"{at['tiempo_ms']} ms", "OK", "BAJO"))

    # ¿Dónde se detuvo? IA (defensor) o una capa determinista.
    circuito = bool(r.get("circuito_sesion"))  # capa determinista por sesión (no la IA) forzó autorización
    if df["decision"] != "PERMITIR":
        bloqueo, capa = "defensor", "defensor"
    elif circuito:
        bloqueo, capa = "autorizacion", "sesion"
    elif ej and not ej["ok"]:
        capa = ej["capa_bloqueo"]
        bloqueo = CAPA_ETAPA.get(capa, "politicas")
    else:
        bloqueo, capa = None, None

    filtro = df.get("origen_decision") == "filtro_rapido"  # bloqueado por regex, sin llamar al defensor LLM
    etapas = [
        _etapa_atacante(at, matq, manual),
        ("prompt", "ok", {"detalle": "RECIBIDO"}),
        ("analisis", "bloqueado", {"detalle": "⚡ FILTRO RÁPIDO"}) if filtro
        else ("analisis", "ok", {"detalle": f"RIESGO {df['riesgo']}"}),
        ("defensor", "omitido", {"detalle": "⚡ Bloqueado por filtro rápido (sin inferencia)"}) if filtro
        else ("defensor", "bloqueado" if bloqueo == "defensor" else "ejecucion_real",
              {**_meta(df, mdef), "detalle": df["decision"]}),
    ]
    ok_detalle = {"politicas": "VALIDADO", "autorizacion": "AUTORIZADO", "herramienta": "QUERY", "bd": "CONSULTA OK"}
    for e in RESTO:
        if bloqueo == "defensor" or (ej is None and not circuito):
            etapas.append((e, "omitido", {}))
        elif bloqueo and RESTO.index(e) > RESTO.index(bloqueo):
            etapas.append((e, "omitido", {}))
        elif e == bloqueo:
            etapas.append((e, "bloqueado", {"detalle": str(capa).upper()}))
        else:
            etapas.append((e, "ok", {"detalle": ok_detalle[e]}))
    await _emitir_etapas(n, etapas)

    if circuito:
        efectiva = "SOLICITAR_AUTORIZACION"
    elif v == "FALLA_DEFENSA":
        efectiva = "PERMITIR"
    elif v == "DEFENSA_EN_PROFUNDIDAD":
        efectiva = "SOLICITAR_AUTORIZACION" if ej["requiere_autorizacion"] else "RECHAZAR"
    else:
        efectiva = df["decision"]
    if puntos is not None:  # mejor de N: FALLA_DEFENSA = punto del atacante; contención = punto del defensor
        if v == "FALLA_DEFENSA":
            puntos["atacante"] += 1
        elif v in ("DEFENSA_EXITOSA", "DEFENSA_EN_PROFUNDIDAD"):
            puntos["defensor"] += 1  # PERMITIDO_CORRECTO es neutral
    d = {"ronda": n, "decision": efectiva, "decision_ia": df["decision"], "riesgo": df["riesgo"],
         "motivo": df["motivo"], "politica": df["politica"], "capa_bloqueo": capa,
         "herramienta": df["herramienta"] if ej else None,
         "datos_devueltos": ej["datos"] if ej and ej["ok"] else None,
         "decision_esperada": "PERMITIR" if v == "PERMITIDO_CORRECTO" else "RECHAZAR",
         "resultado": v, "tiempo_ms": df["tiempo_ms"] or 0, "tokens": df["tokens"],
         "parse_ok": df["parse_ok"], "modelo": mdef, "origen": "ollama", "ia_fallo": bool(r.get("ia_fallo")),
         "nivel_fuga": r.get("nivel_fuga", "NINGUNA"), "circuito_sesion": circuito,
         "origen_decision": "filtro_rapido" if filtro else "ia"}
    if sesion_estado is not None:  # riesgo acumulado de la sesión DESPUÉS de esta ronda (señal, no veredicto)
        d["riesgo_acumulado"] = sesion_estado.registrar(at["categoria"], v, efectiva)
    if puntos is not None:
        d["marcador"] = dict(puntos)
    ms.emitir("decision", d)

    if filtro:  # no hubo petición al modelo: se audita como política determinista
        ms.emitir("auditoria", ms.aud("POLICY", "FILTRO_RAPIDO", df["politica"], "BLOQUEADO", "ALTO"))
    else:
        ms.emitir("auditoria", ms.aud("DEFENDER", "MODEL_REQUEST", mdef, "ENVIADO", "BAJO"))
        if (df.get("intentos") or 1) > 1:  # hubo un segundo intento por JSON no válido
            ms.emitir("auditoria", ms.aud("DEFENDER", "MODEL_REQUEST", f"{mdef} (reintento JSON)", "ENVIADO", "MEDIO"))
        ms.emitir("auditoria", ms.aud("DEFENDER", "MODEL_RESPONSE", f"{d['tiempo_ms']} ms", "OK", "BAJO"))
    ms.emitir("auditoria", ms.aud("DEFENDER", "EVALUATION", df["herramienta"] or "sin herramienta",
                                  df["decision"], ms.nivel_riesgo(df["riesgo"])))
    if capa and capa != "defensor":
        ms.emitir("auditoria", ms.aud("POLICY", "EVALUATION", capa, "BLOQUEADO", ms.nivel_riesgo(df["riesgo"])))
    if ej and ej["ok"]:
        ms.emitir("auditoria", ms.aud("DATABASE", "QUERY", df["herramienta"], "OK",
                                      ms.NIVEL_POR_SENS.get(ej["sensibilidad"], "BAJO")))
    _registrar_real(d, at["categoria"] or "sin_clasificar")
    ms.emitir("metricas", ms.snapshot())
    return d


async def _correr_real(modelo_atq, modelo_def, rondas, ident, intensidad=2, host_atq=None, host_def=None, demo=False):
    host_atq, host_def = host_atq or HOST, host_def or HOST
    # Modelo y host que REALMENTE se usan en esta batalla (se envían en cada ronda_inicio para inspección).
    asignacion = {"atacante": {"modelo": modelo_atq, "host": host_atq},
                  "defensor": {"modelo": modelo_def, "host": host_def}}
    loop = asyncio.get_running_loop()
    previo = (ms.ESTADO["modelo_atq"], ms.ESTADO["modelo_def"])
    ms.ESTADO.update(modo="batalla", corriendo=True, modelo_atq=modelo_atq, modelo_def=modelo_def)
    ms.M.clear()
    ms.M.update(ms._nuevas_metricas())
    errores, historial, jugadas = 0, [], 0
    puntos = None if demo else {"atacante": 0, "defensor": 0}  # la demostración (admin) no puntúa
    estado_sesion = sesion.EstadoSesion()  # nuevo en cada batalla (revancha incluida); se descarta al terminar
    ms.emitir("auditoria", ms.aud("SYSTEM", "INICIO", f"batalla real · {ident.usuario} ({ident.rol}) · intensidad {intensidad}", "OK", "BAJO"))
    ms.emitir("auditoria", ms.aud("SYSTEM", "ASIGNACION", f"atacante {modelo_atq} @ {host_atq} · defensor {modelo_def} @ {host_def}", "OK", "BAJO"))
    try:
        for n in range(1, rondas + 1):
            ms.emitir("ronda_inicio", {"ronda": n, "modo": "batalla", "escenario_id": None,
                                       "escenario_nombre": f"{ident.usuario} ({ident.rol})", "origen": "ollama",
                                       "asignacion": asignacion})
            ms.emitir("etapa", {"ronda": n, "etapa": "atacante", "estado": "activo", "modelo": modelo_atq})
            ms.emitir("auditoria", ms.aud("ATTACKER", "MODEL_REQUEST", modelo_atq, "ENVIADO", "BAJO"))
            try:
                r = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda n=n, h=list(historial): motor.ejecutar_ronda(
                        host_atq, modelo_atq, modelo_def, ident, n, historial=h, intensidad=intensidad,
                        host_def=host_def, riesgo_sesion=estado_sesion.riesgo_acumulado)),
                    TIMEOUT_RONDA)
            except asyncio.TimeoutError:
                r = {"ronda": n, "ataque": None, "defensa": None, "ejecucion": None, "veredicto": "ERROR",
                     "error": f"timeout de ronda ({TIMEOUT_RONDA} s)"}
            if r["veredicto"] == "ERROR":
                errores += 1
                await _emitir_error(r, modelo_atq, modelo_def)  # no se registra en métricas; la batalla continúa
            else:
                await _emitir_ronda(r, modelo_atq, modelo_def, puntos=puntos, sesion_estado=estado_sesion)
                jugadas += 1
                historial.append({"categoria": r["ataque"]["categoria"], "resultado": r["veredicto"]})
            await asyncio.sleep(0.6)
        ms.emitir("fin", {"modo": "batalla", "origen": "ollama", "metricas": ms.snapshot(), "errores": errores,
                          "demo": demo})
        if puntos is not None:
            _partida_fin(puntos, jugadas, errores)
    except asyncio.CancelledError:
        ms.emitir("auditoria", ms.aud("SYSTEM", "DETENIDO", "batalla real", "CANCELADO", "BAJO"))
        ms.emitir("fin", {"modo": "batalla", "origen": "ollama", "detenido": True,
                          "metricas": ms.snapshot(), "errores": errores})
        if puntos is not None:
            _partida_fin(puntos, jugadas, errores, detenida=True)
    except Exception as exc:  # noqa: BLE001
        ms.emitir("error", {"mensaje": f"Error interno de la batalla real: {exc}"})
    finally:
        ms.ESTADO.update(corriendo=False, modelo_atq=previo[0], modelo_def=previo[1])


# ---------- manual REAL ----------
class ManualRealIn(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    modelo_def: str = Field(..., min_length=1, max_length=100)
    usuario: str = Field("ana.perez", min_length=1, max_length=50)
    host_atacante: str = Field("http://localhost:11434", max_length=200)
    host_defensor: str = Field("http://localhost:11434", max_length=200)  # el manual solo usa la Ollama del defensor


async def _manual_real(body, ident, host_def):
    """Un prompt humano -> defensor IA real -> capas -> veredicto. Devuelve (ok, decision | {error})."""
    ms.RONDA_MANUAL += 1
    n = ms.RONDA_MANUAL
    previo = ms.ESTADO["modelo_def"]
    ms.ESTADO.update(modo="manual", corriendo=True, modelo_def=body.modelo_def)
    try:
        ms.emitir("ronda_inicio", {"ronda": n, "modo": "manual", "escenario_id": None,
                                   "escenario_nombre": f"{ident.usuario} ({ident.rol})", "origen": "ollama"})
        ms.emitir("etapa", {"ronda": n, "etapa": "atacante", "estado": "ok", "detalle": "USUARIO (manual)"})
        ms.emitir("auditoria", ms.aud("DEFENDER", "MODEL_REQUEST", body.modelo_def, "ENVIADO", "BAJO"))
        try:
            p = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(
                None, lambda: motor.procesar_defensa(host_def, body.modelo_def, body.prompt, ident)), TIMEOUT_RONDA)
        except asyncio.TimeoutError:
            p = {"defensa": None, "ejecucion": None, "veredicto": "ERROR", "nota": None,
                 "error": f"timeout de ronda ({TIMEOUT_RONDA} s)"}
        r = {"ronda": n, "ataque": {"prompt": body.prompt, "categoria": "manual", "tiempo_ms": None, "tokens": None}, **p}
        if r["veredicto"] == "ERROR":  # no entra en métricas
            await _emitir_error(r, None, body.modelo_def, manual=True)
            return False, {"error": r["error"], "mensaje": r["error"], "veredicto": "ERROR"}
        return True, await _emitir_ronda(r, None, body.modelo_def, manual=True)
    finally:
        ms.ESTADO.update(corriendo=False, modelo_def=previo)


@app.post("/api/manual/real")
async def manual_real(body: ManualRealIn):
    if ms.ESTADO["corriendo"]:
        return JSONResponse({"error": "Ya hay una ejecución en curso.", "mensaje": "Ya hay una ejecución en curso."},
                            status_code=409)
    ms.ESTADO["corriendo"] = True  # reserva inmediata
    try:
        host_def = await _hilo(_normalizar_host, body.host_defensor)
    except ValueError as exc:
        return _rechazo(str(exc))
    est = await _estado_completo(host_def)
    if not est["disponible"]:
        return _rechazo(f"La Ollama del defensor no está disponible en {host_def}. Inícielo (y exponga OLLAMA_HOST si es otra PC).")
    if body.modelo_def not in est["modelos"]:
        return _rechazo(f"El modelo {body.modelo_def} no existe en la Ollama del defensor ({host_def}).")
    try:
        ident = repositorio.por_defecto().identidad(body.usuario)
    except KeyError:
        return _rechazo(f"Usuario desconocido: {body.usuario}")
    ms.TAREA = asyncio.create_task(_manual_real(body, ident, host_def))
    res = (await asyncio.gather(ms.TAREA, return_exceptions=True))[0]
    if isinstance(res, BaseException):
        return JSONResponse({"error": "Prueba manual detenida.", "mensaje": "Prueba manual detenida."}, status_code=409)
    ok, payload = res
    return payload if ok else JSONResponse(payload, status_code=502)


ms.montar_ui(app)

if __name__ == "__main__":
    ms.anunciar(ms.puerto())
    uvicorn.run(app, host="0.0.0.0", port=ms.puerto())
