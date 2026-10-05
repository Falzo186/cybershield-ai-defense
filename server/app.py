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
from src.lab import cliente_ollama, motor, repositorio  # noqa: E402

app = ms.app
HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TIMEOUT_RONDA = 150  # s: dos llamadas al modelo (60 s c/u) + capas
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
    modelo_atq: str = Field(..., min_length=1, max_length=100)
    modelo_def: str = Field(..., min_length=1, max_length=100)
    rondas: int = Field(6, ge=1, le=50)
    usuario: str = Field("ana.perez", min_length=1, max_length=50)
    intensidad: int = Field(2, ge=1, le=3)  # 1 directo · 2 con contexto y rol · 3 sofisticado
    host_atacante: str = Field("http://localhost:11434", max_length=200)  # Ollama del equipo rojo
    host_defensor: str = Field("http://localhost:11434", max_length=200)  # Ollama del equipo azul


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


@app.get("/api/usuarios")
async def usuarios():
    """Usuarios semilla reales. El rol lo fija el sistema (tabla usuarios), nunca el prompt."""
    filas = repositorio.por_defecto().conn.execute(
        "SELECT usuario, rol FROM usuarios ORDER BY usuario").fetchall()
    return {"usuarios": [{"usuario": f["usuario"], "rol": f["rol"]} for f in filas]}


@app.post("/api/batalla/real/iniciar")
async def iniciar_real(body: BatallaRealIn):
    if ms.ESTADO["corriendo"]:
        return JSONResponse({"error": "Ya hay una ejecución en curso.", "mensaje": "Ya hay una ejecución en curso."},
                            status_code=409)
    ms.ESTADO["corriendo"] = True  # reserva inmediata (evita doble inicio durante las comprobaciones)
    try:
        host_atq = await _hilo(_normalizar_host, body.host_atacante)
        host_def = await _hilo(_normalizar_host, body.host_defensor)
    except ValueError as exc:
        return _rechazo(str(exc))
    for equipo, host, modelo in (("atacante", host_atq, body.modelo_atq), ("defensor", host_def, body.modelo_def)):
        est = await _estado_completo(host)
        if not est["disponible"]:
            return _rechazo(f"La Ollama del {equipo} no está disponible en {host}. Inícielo (y exponga OLLAMA_HOST si es otra PC).")
        if modelo not in est["modelos"]:
            return _rechazo(f"El modelo {modelo} no existe en la Ollama del {equipo} ({host}).")
    try:
        ident = repositorio.por_defecto().identidad(body.usuario)
    except KeyError:
        return _rechazo(f"Usuario desconocido: {body.usuario}")
    ms.TAREA = asyncio.create_task(_correr_real(body.modelo_atq, body.modelo_def, body.rondas, ident,
                                                body.intensidad, host_atq, host_def))
    return {}


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


async def _emitir_ronda(r, matq, mdef, manual=False):
    n, at, df, ej, v = r["ronda"], r["ataque"], r["defensa"], r["ejecucion"], r["veredicto"]
    ms.emitir("ataque", {"ronda": n, "prompt": at["prompt"], "categoria": at["categoria"],
                         "objetivo": OBJETIVO_TXT, "sensibilidad_objetivo": "CRITICA", **_meta(at, matq)})
    if manual:
        ms.emitir("auditoria", ms.aud("ATTACKER", "PROMPT", "usuario (manual)", "ENVIADO", "BAJO"))
    else:
        ms.emitir("auditoria", ms.aud("ATTACKER", "MODEL_RESPONSE", f"{at['tiempo_ms']} ms", "OK", "BAJO"))

    # ¿Dónde se detuvo? IA (defensor) o una capa determinista.
    if df["decision"] != "PERMITIR":
        bloqueo, capa = "defensor", "defensor"
    elif ej and not ej["ok"]:
        capa = ej["capa_bloqueo"]
        bloqueo = CAPA_ETAPA.get(capa, "politicas")
    else:
        bloqueo, capa = None, None

    etapas = [
        _etapa_atacante(at, matq, manual),
        ("prompt", "ok", {"detalle": "RECIBIDO"}),
        ("analisis", "ok", {"detalle": f"RIESGO {df['riesgo']}"}),
        ("defensor", "bloqueado" if bloqueo == "defensor" else "ejecucion_real",
         {**_meta(df, mdef), "detalle": df["decision"]}),
    ]
    ok_detalle = {"politicas": "VALIDADO", "autorizacion": "AUTORIZADO", "herramienta": "QUERY", "bd": "CONSULTA OK"}
    for e in RESTO:
        if bloqueo == "defensor" or ej is None:
            etapas.append((e, "omitido", {}))
        elif bloqueo and RESTO.index(e) > RESTO.index(bloqueo):
            etapas.append((e, "omitido", {}))
        elif e == bloqueo:
            etapas.append((e, "bloqueado", {"detalle": str(capa).upper()}))
        else:
            etapas.append((e, "ok", {"detalle": ok_detalle[e]}))
    await _emitir_etapas(n, etapas)

    if v == "FALLA_DEFENSA":
        efectiva = "PERMITIR"
    elif v == "DEFENSA_EN_PROFUNDIDAD":
        efectiva = "SOLICITAR_AUTORIZACION" if ej["requiere_autorizacion"] else "RECHAZAR"
    else:
        efectiva = df["decision"]
    d = {"ronda": n, "decision": efectiva, "decision_ia": df["decision"], "riesgo": df["riesgo"],
         "motivo": df["motivo"], "politica": df["politica"], "capa_bloqueo": capa,
         "herramienta": df["herramienta"] if ej else None,
         "datos_devueltos": ej["datos"] if ej and ej["ok"] else None,
         "decision_esperada": "PERMITIR" if v == "PERMITIDO_CORRECTO" else "RECHAZAR",
         "resultado": v, "tiempo_ms": df["tiempo_ms"] or 0, "tokens": df["tokens"],
         "parse_ok": df["parse_ok"], "modelo": mdef, "origen": "ollama", "ia_fallo": bool(r.get("ia_fallo"))}
    ms.emitir("decision", d)

    ms.emitir("auditoria", ms.aud("DEFENDER", "MODEL_REQUEST", mdef, "ENVIADO", "BAJO"))
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


async def _correr_real(modelo_atq, modelo_def, rondas, ident, intensidad=2, host_atq=None, host_def=None):
    host_atq, host_def = host_atq or HOST, host_def or HOST
    loop = asyncio.get_running_loop()
    previo = (ms.ESTADO["modelo_atq"], ms.ESTADO["modelo_def"])
    ms.ESTADO.update(modo="batalla", corriendo=True, modelo_atq=modelo_atq, modelo_def=modelo_def)
    ms.M.clear()
    ms.M.update(ms._nuevas_metricas())
    errores, historial = 0, []
    ms.emitir("auditoria", ms.aud("SYSTEM", "INICIO", f"batalla real · {ident.usuario} ({ident.rol}) · intensidad {intensidad}", "OK", "BAJO"))
    try:
        for n in range(1, rondas + 1):
            ms.emitir("ronda_inicio", {"ronda": n, "modo": "batalla", "escenario_id": None,
                                       "escenario_nombre": f"{ident.usuario} ({ident.rol})", "origen": "ollama"})
            ms.emitir("etapa", {"ronda": n, "etapa": "atacante", "estado": "activo", "modelo": modelo_atq})
            ms.emitir("auditoria", ms.aud("ATTACKER", "MODEL_REQUEST", modelo_atq, "ENVIADO", "BAJO"))
            try:
                r = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda n=n, h=list(historial): motor.ejecutar_ronda(
                        host_atq, modelo_atq, modelo_def, ident, n, historial=h, intensidad=intensidad,
                        host_def=host_def)),
                    TIMEOUT_RONDA)
            except asyncio.TimeoutError:
                r = {"ronda": n, "ataque": None, "defensa": None, "ejecucion": None, "veredicto": "ERROR",
                     "error": f"timeout de ronda ({TIMEOUT_RONDA} s)"}
            if r["veredicto"] == "ERROR":
                errores += 1
                await _emitir_error(r, modelo_atq, modelo_def)  # no se registra en métricas; la batalla continúa
            else:
                await _emitir_ronda(r, modelo_atq, modelo_def)
                historial.append({"categoria": r["ataque"]["categoria"], "resultado": r["veredicto"]})
            await asyncio.sleep(0.6)
        ms.emitir("fin", {"modo": "batalla", "origen": "ollama", "metricas": ms.snapshot(), "errores": errores})
    except asyncio.CancelledError:
        ms.emitir("auditoria", ms.aud("SYSTEM", "DETENIDO", "batalla real", "CANCELADO", "BAJO"))
        ms.emitir("fin", {"modo": "batalla", "origen": "ollama", "detenido": True,
                          "metricas": ms.snapshot(), "errores": errores})
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
