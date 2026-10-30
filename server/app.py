"""Servidor REAL del AI Security Laboratory.

Reúne el mock (SIMULACIÓN, etiqueta MOCK) y la BATALLA REAL con Ollama (etiqueta OLLAMA).
Los eventos de la batalla real se traducen desde el dict de src/lab/motor.py; nada se inventa:
si Ollama falla, la ronda se reporta como ERROR y no entra en las métricas.
"""
import asyncio
import ipaddress
import json
import os
import secrets
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402
from fastapi import Request  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import mock_server as ms  # noqa: E402
import partida as pt  # noqa: E402
from src.lab import ataque_ia, atacante, cliente_ollama, correos, documentos, motor, repositorio, sesion  # noqa: E402

app = ms.app
HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TIMEOUT_RONDA = 300  # s: dos llamadas al modelo (120 s c/u, la primera puede incluir la carga del modelo) + capas
TIMEOUT_RETO = 30    # s que tiene el equipo destinatario para aceptar o rechazar un reto
# Dificultad -> usuario semilla (el rol lo fija el sistema): Fácil=invitado, Media=empleado, Difícil=analista.
# El objetivo del atacante por rol está en atacante.OBJETIVO_POR_ROL.
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
# Sesiones por PARTICIPANTE (server/partida.py): cada persona se une con un nombre visible y un equipo y recibe su
# propio token; el equipo y el rol los fija el SERVIDOR con lo que él emitió, nunca lo que declare el cliente. La
# vista «general» (árbitro) exige el código que se imprime en la consola al arrancar. Sin sesión (espectador
# anónimo) solo se puede hacer GET a RUTAS_PUBLICAS; una sesión de espectador tampoco puede modificar nada.
CODIGO_ARBITRO = os.getenv("CS_CODIGO_ARBITRO") or f"{secrets.randbelow(10 ** 6):06d}"
SALA = pt.Sala(CODIGO_ARBITRO)
RUTAS_PUBLICAS = ("/api/eventos", "/api/estado", "/api/ia/estado")
RUTA_SESION = "/api/sesion"
# Rutas reservadas a UN equipo (además de exigir sesión). Detener, iniciar y cerrar la partida es cosa del árbitro;
# Rojo envía correos de entrenamiento y Azul los lee en su buzón.
SOLO_EQUIPO = {"/api/detener": "general", "/api/correo": "rojo", "/api/buzon": "azul", "/api/misiones": "azul",
               "/api/evento": "azul", "/api/partida/finalizar": "general", "/api/partida/iniciar": "general",
               "/api/partida/nueva": "general", "/api/correo/enviados": "rojo", "/api/ia/ataque": "rojo",
               "/api/ia/defensor": "azul"}
# Partida con fases (preparación -> en curso -> finalizada) y temporizador en el servidor. Los correos, misiones y
# eventos se guardan con PARTIDA_ID; «nueva partida» empieza otra sin reiniciar el proceso.
PARTIDA = pt.Partida()
PARTIDA_ID = PARTIDA.id
TAREA_TIEMPO = None  # tarea que cierra la partida al agotarse el tiempo
USUARIO_AZUL_DEFECTO = "ana.perez"
USUARIO_EQUIPO = {}  # equipo -> usuario semilla con el que juega (hoy solo azul: dueño del buzón)
# Riesgo de la partida Rojo/Azul (buzón): cada evento aplica su consecuencia fija de sesion.REGLAS_EVENTO.
# Es independiente del EstadoSesion de cada batalla IA vs IA (ese se crea y descarta por batalla).
ESTADO_PARTIDA = sesion.EstadoSesion()
RESULTADO_FINAL = None  # al finalizar: puntajes congelados, ganador y marcador final (las acciones pasan a 409)
repositorio.PARTIDA = PARTIDA_ID  # cada evento de data/eventos.jsonl lleva la partida


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


def _prohibido(msg, status=403):
    return JSONResponse({"error": msg, "mensaje": msg}, status_code=status)


# ---------- verificación de la sesión del participante ----------
@app.middleware("http")
async def _verificar_sesion(request: Request, call_next):
    """Toda ruta /api exige la sesión de un participante, salvo unirse y el GET de solo lectura del espectador.
    El equipo sale de la sesión emitida por el servidor; una sesión de espectador nunca modifica nada."""
    ruta = request.url.path
    if not ruta.startswith("/api/"):
        return await call_next(request)
    _vencer_si_toca()  # el tiempo lo manda el servidor: se comprueba en cada petición, no solo en la tarea
    if ruta == RUTA_SESION and request.method == "POST":
        return await call_next(request)
    p = SALA.por_token(request.headers.get("X-Equipo-Token"))
    request.state.participante = p
    request.state.equipo = p.equipo if p else None
    if p is None and not (request.method == "GET" and ruta in RUTAS_PUBLICAS):
        return _prohibido("Falta una sesión válida: únete a la partida con tu nombre. "
                          "Sin sesión (espectador) solo se puede leer eventos y estado.")
    if p is not None and p.rol == "espectador" and request.method != "GET":
        return _prohibido("Los espectadores solo observan: no pueden modificar la partida.")
    dueno = SOLO_EQUIPO.get(ruta)
    if dueno and request.state.equipo != dueno:
        return _prohibido(f"Solo el equipo {dueno} puede usar {ruta}.")
    if request.method == "POST" and ruta in RUTAS_PRACTICA and (err := _practica_bloqueada()):
        return err
    return await call_next(request)


def _rol_no_coincide(request, declarado):
    """El rol que declara el cliente debe ser el del token emitido. -> respuesta 403 o None."""
    if declarado != request.state.equipo:
        return _prohibido(f"El token pertenece al equipo {request.state.equipo}, no a «{declarado}».")
    return None


class SesionIn(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=40)
    equipo: str = Field(..., pattern="^(" + "|".join(pt.EQUIPOS) + ")$")
    codigo: str | None = Field(None, max_length=20)    # solo «general»: código de árbitro
    usuario: str | None = Field(None, min_length=1, max_length=50)  # solo azul, el primero: usuario semilla del buzón


def _estado_partida():
    return {**PARTIDA.publico(), "participantes": [p.publico() for p in SALA.participantes()]}


def _emitir_partida():
    ms.emitir("partida_estado", _estado_partida())


@app.post(RUTA_SESION)
async def unirse(body: SesionIn, request: Request):
    """Une a un participante con su nombre visible y equipo -> {token, participante, partida}. El token es solo suyo:
    se guarda en su navegador para reconectar (GET /api/sesion) sin volver a unirse."""
    usuario = None
    if body.equipo == "azul" and "azul" not in USUARIO_EQUIPO:
        # el buzón del equipo azul es de un usuario semilla (la identidad sale de la tabla usuarios, no del cliente)
        usuario = body.usuario or USUARIO_AZUL_DEFECTO
        try:
            repositorio.por_defecto().identidad(usuario)
        except KeyError:
            return _error400(f"Usuario desconocido: {usuario}")
    try:
        p = SALA.unirse(body.nombre, body.equipo, body.codigo, cliente=request.client.host if request.client else "?")
    except pt.ErrorSesion as e:
        return _prohibido(e.mensaje, e.status)
    if usuario:
        USUARIO_EQUIPO["azul"] = usuario
    ms.emitir("auditoria", ms.aud("SYSTEM", "PARTICIPANTE_UNIDO", f"{p.nombre} · {p.equipo}", "OK", "BAJO"))
    _emitir_partida()
    if p.equipo == "azul":
        _emitir_marcador()  # el marcador ya sabe con qué usuario juega Azul
    return {"token": p.token, "participante": p.publico(), "partida": _estado_partida(),
            "usuario_azul": USUARIO_EQUIPO.get("azul")}


@app.get(RUTA_SESION)
async def mi_sesion(request: Request):
    """Reconexión: con un token válido devuelve el participante y la partida (403 si el token no existe)."""
    return {"participante": request.state.participante.publico(), "partida": _estado_partida()}


@app.get("/api/partida")
async def estado_partida():
    return _estado_partida()


class IniciarPartidaIn(BaseModel):
    duracion_min: int


@app.post("/api/partida/iniciar")
async def iniciar_partida(body: IniciarPartidaIn):
    """Solo el árbitro: preparación -> en curso, con 5, 10 o 15 min contados por el servidor."""
    global TAREA_TIEMPO
    try:
        PARTIDA.iniciar(body.duracion_min)
    except pt.ErrorSesion as e:
        return _prohibido(e.mensaje, e.status)
    repositorio.por_defecto().registrar(None, "PARTIDA_INICIADA", PARTIDA_ID, f"{body.duracion_min} min", "BAJO")
    ms.emitir("auditoria", ms.aud("SYSTEM", "PARTIDA_INICIADA", PARTIDA_ID, f"{body.duracion_min} min", "BAJO"))
    TAREA_TIEMPO = asyncio.create_task(_vigilar_tiempo(PARTIDA))
    _emitir_partida()
    return _estado_partida()


async def _vigilar_tiempo(partida):
    """Cierra la partida al agotarse el tiempo y reenvía el estado cada 15 s para que los relojes se resincronicen."""
    while partida is PARTIDA and partida.fase == "en_curso":
        await asyncio.sleep(max(0.2, min(15, partida.restante_s())))
        if partida is not PARTIDA or partida.fase != "en_curso":
            return
        if partida.vencida():
            _cerrar_partida("tiempo")
            return
        _emitir_partida()


def _vencer_si_toca():
    """Si el tiempo ya se agotó (aunque la tarea aún no lo haya visto), la partida se cierra ahora."""
    if PARTIDA.vencida():
        _cerrar_partida("tiempo")


@app.post("/api/partida/nueva")
async def nueva_partida():
    """Solo el árbitro y con la partida finalizada: empieza otra en preparación, sin reiniciar el servidor. Las
    sesiones de los participantes se conservan; correos, misiones, riesgo y marcador empiezan de cero."""
    global PARTIDA, PARTIDA_ID, ESTADO_PARTIDA, RESULTADO_FINAL, ESTADO_IA
    if PARTIDA.fase != "finalizada":
        return _prohibido("Solo se puede empezar una partida nueva cuando la actual ha finalizado.", 409)
    PARTIDA = pt.Partida()
    PARTIDA_ID = PARTIDA.id
    repositorio.PARTIDA = PARTIDA_ID
    ESTADO_PARTIDA = sesion.EstadoSesion()
    ESTADO_IA = sesion.EstadoSesion()
    RESULTADO_FINAL = None
    ms.emitir("auditoria", ms.aud("SYSTEM", "PARTIDA_NUEVA", PARTIDA_ID, "PREPARACIÓN", "BAJO"))
    _emitir_partida()
    _emitir_marcador()
    _emitir_ia()
    return _estado_partida()


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
    # Guion fijo de técnicas por ronda (atacante.ESCENARIOS); None = el atacante elige libremente.
    escenario: str | None = Field(None, pattern="^(" + "|".join(atacante.ESCENARIOS) + ")$")


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
async def ollama_probar(request: Request, host: str | None = None, modelo: str = "", rol: str | None = None):
    """Diagnóstico: llamada MÍNIMA y real a host/modelo (también fuerza la carga inicial del modelo)."""
    if rol in ("rojo", "azul") and request.state.equipo not in (rol, "general"):
        return _prohibido(f"Solo el equipo {rol} (o la vista general) puede confirmar su modelo.")
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


# ---------- buzón interno de correos de entrenamiento (nada sale del laboratorio) ----------
class CorreoIn(BaseModel):
    plantilla: str = Field(..., pattern="^(" + "|".join(correos.PLANTILLAS) + ")$")
    para_usuario: str | None = Field(None, min_length=1, max_length=50)  # por defecto, el usuario del equipo azul


@app.get("/api/correo/plantillas")
async def plantillas_correo():
    return {"plantillas": correos.catalogo()}


@app.post("/api/correo")
async def enviar_correo(body: CorreoIn):
    """Solo Rojo (SOLO_EQUIPO). La respuesta NO incluye el enlace: así Rojo no puede fabricar clics."""
    if cerrada := _partida_cerrada():
        return cerrada
    para = body.para_usuario or USUARIO_EQUIPO.get("azul")
    if not para:
        return _prohibido("Falta destinatario: el equipo AZUL aún no ha entrado en la partida.", 409)
    try:
        c = repositorio.por_defecto().crear_correo(PARTIDA_ID, body.plantilla, para)
    except KeyError:
        return _error400(f"Usuario desconocido: {para}")
    ms.emitir("auditoria", ms.aud("ATTACKER", "CORREO_ENVIADO", f"{body.plantilla} → {para}", "OK", "MEDIO"))
    return c


@app.get("/api/buzon")
async def buzon():
    """Solo Azul (SOLO_EQUIPO): correos de esta partida dirigidos a su usuario."""
    usuario = USUARIO_EQUIPO.get("azul")
    repo = repositorio.por_defecto()
    return {"usuario": usuario, "correos": repo.buzon(PARTIDA_ID, usuario) if usuario else [],
            "enviados": repo.respuestas(PARTIDA_ID, usuario) if usuario else []}  # carpeta «Enviados» de Azul


@app.get("/api/correo/enviados")
async def enviados_rojo():
    """Solo Rojo (SOLO_EQUIPO): sus correos y lo que una campaña real podría medir (clic, apertura del adjunto)."""
    return {"enviados": repositorio.por_defecto().enviados_rojo(PARTIDA_ID)}


def _participante(request):
    p = getattr(request.state, "participante", None) if request is not None else None
    return p.nombre if p else None


def _aplicar_regla(evento, usuario, request=None, evidencia=None):
    """Evento -> consecuencia fija (sesion.REGLAS_EVENTO) sobre el riesgo de la partida. Se difunde por SSE.
    request: el participante que actuó (queda como quien completó la misión); evidencia: el recurso (correo:<id>…)."""
    r = ESTADO_PARTIDA.aplicar_evento(evento)
    if r is None:
        return None
    r["misiones_completadas"], r["misiones_bloqueadas"] = [], []
    if r["mision"] and usuario:
        repo = repositorio.por_defecto()
        r["misiones_completadas"] = [
            {"id": m["id"], "titulo": m["titulo"], "puntos": m["puntos_obtenidos"], "a_tiempo": m["a_tiempo"]}
            for m in repo.completar_misiones_evento(PARTIDA_ID, usuario, evento, _participante(request), evidencia,
                                                    PARTIDA.transcurrido_s())]
        r["misiones_bloqueadas"] = repo.misiones_bloqueadas(PARTIDA_ID, usuario, evento)
        for m in r["misiones_completadas"]:
            ms.emitir("auditoria", ms.aud("DEFENDER", "MISION_COMPLETADA", f"{m['titulo']} · {usuario}",
                                          f"+{m['puntos']} pts" + ("" if m["a_tiempo"] else " (fuera de plazo)"), "BAJO"))
    ms.emitir("regla_evento", {**r, "usuario": usuario})
    ms.emitir("auditoria", ms.aud("SYSTEM", "REGLA", f"{evento} → riesgo {r['riesgo']:+d}",
                                  f"riesgo partida {int(r['riesgo_acumulado'])}/100", "BAJO"))
    _emitir_marcador()
    if evento in ("credencial_comprometida", "credencial_revocada"):
        _emitir_ia()  # cambia la identidad con la que atacaría la IA de Rojo
    return r


# ---------- marcador de la partida (vista general y espectadores; solo lectura, por SSE) ----------
# Conteos de eventos clave = veces que se aplicó su regla en esta partida (sesion.EstadoSesion.eventos_vistos).
CONTEOS_MARCADOR = {"clics": "CLIC_ENLACE", "contenciones": "enlace_contenido", "correos_reportados": "correo_reportado",
                    "pdf_abiertos": "pdf_abierto", "pdf_reportados": "pdf_reportado",
                    "credenciales_comprometidas": "credencial_comprometida", "credenciales_revocadas": "credencial_revocada"}


def _marcador():
    """Marcador en vivo; tras finalizar, el congelado (con el resultado en "final")."""
    if RESULTADO_FINAL:
        return {**RESULTADO_FINAL["marcador"], "final": {k: v for k, v in RESULTADO_FINAL.items() if k != "marcador"}}
    usuario = USUARIO_EQUIPO.get("azul")
    repo = repositorio.por_defecto()
    lista = repo.misiones(PARTIDA_ID, usuario)  # sin usuario azul: todas pendientes
    hechas = [m for m in lista if m["estado"] == "completada"]
    vistos = ESTADO_PARTIDA.eventos_vistos
    rojo = repo.logros_rojo(PARTIDA_ID)
    incidentes = repo.incidentes(PARTIDA_ID)
    ia = repo.puntos_ia(PARTIDA_ID)
    azul_misiones, rojo_buzon = sum(m["puntos_obtenidos"] or 0 for m in hechas), sesion.puntaje_rojo(**rojo)
    return {"usuario_azul": usuario, "puntos_azul": azul_misiones + ia["azul"], "puntos_rojo": rojo_buzon + ia["rojo"],
            "puntos_azul_misiones": azul_misiones, "puntos_azul_ia": ia["azul"],
            "puntos_rojo_buzon": rojo_buzon, "puntos_rojo_ia": ia["rojo"],
            "ataques_ia": ia["lanzados"], "ia_datos_expuestos": ia["datos_expuestos"], "ia_contenidos": ia["contenidos"],
            "rojo_enlaces_sin_contener": rojo["enlaces_sin_contener"], "rojo_pdfs_sin_reportar": rojo["pdfs_sin_reportar"],
            "rojo_credenciales_sin_revocar": rojo["credenciales_sin_revocar"],
            "incidentes_abiertos": sum(i["estado"] != "resuelto" for i in incidentes),
            "incidentes_resueltos": sum(i["estado"] == "resuelto" for i in incidentes),
            "misiones_completadas": len(hechas), "misiones_total": len(lista),
            "riesgo": ESTADO_PARTIDA.riesgo_acumulado,
            "denegaciones_rojo": repositorio.por_defecto().denegaciones(PARTIDA_ID, "rojo"),
            **{clave: vistos.get(evento, 0) for clave, evento in CONTEOS_MARCADOR.items()}, "final": None}


def _partida_cerrada():
    """Las acciones de Rojo/Azul (correo, reportar, contener, PDF, misión manual) solo valen con la partida en curso:
    antes de iniciarla o tras finalizarla -> 409."""
    if PARTIDA.fase == "preparacion":
        return _prohibido("La partida aún no ha empezado: el árbitro debe iniciarla.", 409)
    if PARTIDA.fase == "finalizada":
        return _prohibido("La partida ya finalizó: los puntajes están congelados.", 409)
    return None


@app.post("/api/partida/finalizar")
async def finalizar_partida():
    """Solo General (SOLO_EQUIPO): termina la partida antes de tiempo (congela puntajes y declara ganador)."""
    try:
        return _cerrar_partida("arbitro")
    except pt.ErrorSesion as e:
        return _prohibido(e.mensaje, e.status)


def _cerrar_partida(motivo):
    """Congela los puntajes de Rojo y Azul, declara ganador o empate y lo difunde. motivo: "arbitro" | "tiempo"."""
    global RESULTADO_FINAL
    PARTIDA.finalizar(motivo)  # ErrorSesion si no está en curso
    _cancelar_ataque_ia()  # un ataque IA a medias no cuenta para nadie
    m = _marcador()
    rojo, azul = m["puntos_rojo"], m["puntos_azul"]
    ganador = "rojo" if rojo > azul else "azul" if azul > rojo else "empate"
    RESULTADO_FINAL = {"partida": PARTIDA_ID, "puntos_rojo": rojo, "puntos_azul": azul, "ganador": ganador,
                       "ts": datetime.now().astimezone().isoformat(timespec="seconds"), "motivo": motivo, "marcador": m}
    repositorio.por_defecto().registrar(None, "PARTIDA_FINALIZADA", PARTIDA_ID,
                                        f"ROJO {rojo} - AZUL {azul} · {ganador.upper()}", "BAJO")
    ms.emitir("auditoria", ms.aud("SYSTEM", "PARTIDA_FINALIZADA", PARTIDA_ID,
                                  f"ROJO {rojo} — AZUL {azul} · ganador {ganador}", "BAJO"))
    final = _marcador()
    ms.emitir("marcador_partida", final)
    ms.emitir("partida_finalizada", final["final"] | {"marcador": final})
    _emitir_partida()
    return final["final"]


def _emitir_marcador():
    ms.emitir("marcador_partida", _marcador())


async def _hook_marcador():
    """Al conectar el SSE (también un espectador sin token) llegan el estado de la partida y el marcador actual."""
    _vencer_si_toca()
    return ("event: partida_estado\ndata: " + json.dumps(_estado_partida(), ensure_ascii=False) + "\n\n"
            "event: marcador_partida\ndata: " + json.dumps(_marcador(), ensure_ascii=False) + "\n\n"
            "event: ia_estado\ndata: " + json.dumps(_estado_ia(), ensure_ascii=False) + "\n\n")


ms.ON_CONEXION.insert(0, _hook_marcador)  # primero: el de Ollama puede tardar segundos si Ollama no responde


@app.post("/api/correo/{correo_id}/reportar")
async def reportar_correo(correo_id: int, request: Request):
    """Solo Azul: reporta como sospechoso un correo de SU buzón (una vez por correo) -> regla correo_reportado."""
    if request.state.equipo != "azul":
        return _prohibido("Solo el equipo azul puede reportar correos de su buzón.")
    if cerrada := _partida_cerrada():
        return cerrada
    usuario = USUARIO_EQUIPO.get("azul")
    nuevo = repositorio.por_defecto().reportar_correo(PARTIDA_ID, usuario, correo_id)
    if nuevo is None:
        return _prohibido("Ese correo no está en su buzón de esta partida.", 404)
    if not nuevo:
        return _prohibido("Ese correo ya fue reportado.", 409)
    ms.emitir("auditoria", ms.aud("DEFENDER", "CORREO_REPORTADO", f"correo {correo_id} · {usuario}", "OK", "BAJO"))
    return {"reportado": True, "regla": _aplicar_regla("correo_reportado", usuario, request, f"correo:{correo_id}")}


_CONTENER_ERROR = {"sin_clic": ("Ese enlace no se ha clicado: no hay nada que contener.", 409),
                   "ya_contenido": ("Ese enlace ya estaba contenido.", 409),
                   None: ("Ese correo no está en su buzón de esta partida.", 404)}


@app.post("/api/correo/{correo_id}/contener")
async def contener_enlace(correo_id: int, request: Request):
    """Solo Azul: tras un CLIC_ENLACE, bloquea ese enlace (los clics siguientes ya no cuentan) -> regla
    enlace_contenido, que completa la misión «Contener un enlace clicado»."""
    if request.state.equipo != "azul":
        return _prohibido("Solo el equipo azul puede contener enlaces de su buzón.")
    if cerrada := _partida_cerrada():
        return cerrada
    usuario = USUARIO_EQUIPO.get("azul")
    r = repositorio.por_defecto().contener_enlace(PARTIDA_ID, usuario, correo_id)
    if r != "contenido":
        return _prohibido(*_CONTENER_ERROR[r])
    ms.emitir("auditoria", ms.aud("DEFENDER", "ENLACE_CONTENIDO", f"correo {correo_id} · {usuario}", "OK", "BAJO"))
    return {"contenido": True, "regla": _aplicar_regla("enlace_contenido", usuario, request, f"correo:{correo_id}")}


# ---------- PDFs benignos adjuntos: abrir / reportar son EVENTOS (no se ejecuta nada) ----------
class EventoIn(BaseModel):
    tipo: str = Field(..., pattern="^(pdf_abierto|pdf_reportado)$")
    recurso: str = Field(..., pattern=r"^correo:[0-9]{1,9}$")  # el correo de SU buzón que trae el PDF


_EVENTO_ERROR = {"sin_adjunto": ("Ese correo no trae ningún PDF adjunto.", 409),
                 "ya_reportado": ("Ese PDF ya fue reportado.", 409),
                 "aislado": ("El adjunto está aislado: ya no se puede abrir.", 409),
                 None: ("Ese correo no está en su buzón de esta partida.", 404)}


@app.post("/api/evento")
async def registrar_evento(body: EventoIn, request: Request):
    """Solo Azul (SOLO_EQUIPO). Escribe el evento en auditoría y aplica su regla fija; si es pdf_abierto devuelve la
    VISTA PREVIA para el visor seguro (texto del propio archivo y análisis). Nada se descarga ni se ejecuta."""
    if cerrada := _partida_cerrada():
        return cerrada
    usuario = USUARIO_EQUIPO.get("azul")
    correo_id = int(body.recurso.split(":")[1])
    r = repositorio.por_defecto().evento_pdf(PARTIDA_ID, usuario, correo_id, body.tipo)
    if not isinstance(r, dict):
        return _prohibido(*_EVENTO_ERROR[r])
    doc = r["doc"]
    ms.emitir("auditoria", ms.aud("DEFENDER", body.tipo.upper(), f"{doc['archivo']} · correo {correo_id} · {usuario}",
                                  "OK", "BAJO"))
    return {"ok": True, "documento": doc, "regla": _aplicar_regla(body.tipo, usuario, request, body.recurso), "vista": r.get("vista")}


# ---------- aplicación de correo de Azul (Fase D): todas exigen sesión azul, partida en curso y correo propio ----------
def _accion_azul(request):
    if request.state.equipo != "azul":
        return _prohibido("Solo el equipo azul puede gestionar su buzón.")
    return _partida_cerrada()


_NO_ES_SUYO = ("Ese correo no está en su buzón de esta partida.", 404)


@app.post("/api/correo/{correo_id}/leer")
async def leer_correo(correo_id: int, request: Request):
    """Marca el correo como leído por ESTE participante. Abrir no compromete nada (regla correo_abierto, riesgo 0)."""
    if err := _accion_azul(request):
        return err
    usuario, quien = USUARIO_EQUIPO.get("azul"), request.state.participante.nombre
    r = repositorio.por_defecto().marcar_leido(PARTIDA_ID, usuario, correo_id, quien)
    if r is None:
        return _prohibido(*_NO_ES_SUYO)
    regla = _aplicar_regla("correo_abierto", usuario, request, f"correo:{correo_id}") if r == "nuevo" else None
    return {"leido": True, "nuevo": r == "nuevo", "regla": regla}


class ArchivarIn(BaseModel):
    archivar: bool = True


@app.post("/api/correo/{correo_id}/archivar")
async def archivar_correo(correo_id: int, body: ArchivarIn, request: Request):
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    r = repositorio.por_defecto().archivar(PARTIDA_ID, usuario, correo_id, request.state.participante.nombre, body.archivar)
    if r is None:
        return _prohibido(*_NO_ES_SUYO)
    regla = _aplicar_regla("correo_archivado", usuario, request, f"correo:{correo_id}") if r and body.archivar else None
    return {"archivado": body.archivar, "cambio": r, "regla": regla}


@app.post("/api/correo/{correo_id}/verificar")
async def verificar_remitente(correo_id: int, request: Request):
    """Comprueba el dominio del remitente contra el oficial (calculado, no declarado por la plantilla)."""
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    r = repositorio.por_defecto().verificar_remitente(PARTIDA_ID, usuario, correo_id)
    if r is None:
        return _prohibido(*_NO_ES_SUYO)
    return {**r, "regla": _aplicar_regla("remitente_verificado", usuario, request, f"correo:{correo_id}")}


@app.post("/api/correo/{correo_id}/inspeccionar")
async def inspeccionar_enlace(correo_id: int, request: Request):
    """Muestra a dónde lleva de verdad el enlace, sin abrirlo (no cuenta como clic)."""
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    r = repositorio.por_defecto().inspeccionar_enlace(PARTIDA_ID, usuario, correo_id)
    if r is None:
        return _prohibido(*_NO_ES_SUYO)
    return {**r, "regla": _aplicar_regla("enlace_inspeccionado", usuario, request, f"correo:{correo_id}")}


class RespuestaIn(BaseModel):
    texto: str = Field(..., min_length=1, max_length=1000)


@app.post("/api/correo/{correo_id}/responder")
async def responder_correo(correo_id: int, body: RespuestaIn, request: Request):
    """Respuesta que nunca sale del laboratorio. Contestar a un remitente que no es el oficial es una consecuencia
    explícita (regla respuesta_a_phishing, riesgo +10)."""
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    try:
        r = repositorio.por_defecto().responder(PARTIDA_ID, usuario, correo_id, request.state.participante.nombre,
                                                body.texto)
    except ValueError as e:
        return _error400(str(e))
    if r is None:
        return _prohibido(*_NO_ES_SUYO)
    return {**r, "regla": _aplicar_regla("respuesta_a_phishing" if r["a_phishing"] else "respuesta_enviada", usuario, request,
                                f"correo:{correo_id}")}


_AISLAR_ERROR = {"sin_adjunto": ("Ese correo no trae ningún adjunto que aislar.", 409),
                 "ya_aislado": ("Ese adjunto ya estaba aislado.", 409), None: _NO_ES_SUYO}


@app.post("/api/correo/{correo_id}/aislar")
async def aislar_adjunto(correo_id: int, request: Request):
    """Aísla el adjunto: ya no se puede previsualizar y Rojo pierde sus puntos por él."""
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    r = repositorio.por_defecto().aislar_adjunto(PARTIDA_ID, usuario, correo_id, request.state.participante.nombre)
    if r != "aislado":
        return _prohibido(*_AISLAR_ERROR[r])
    ms.emitir("auditoria", ms.aud("DEFENDER", "ARCHIVO_AISLADO", f"correo {correo_id} · {usuario}", "OK", "BAJO"))
    return {"aislado": True, "regla": _aplicar_regla("archivo_aislado", usuario, request, f"correo:{correo_id}")}


@app.get("/pdf/{doc_id}")
async def descargar_pdf(doc_id: str):
    """PDF benigno del catálogo FIJO, solo como descarga. El id nunca forma una ruta: se busca en el catálogo."""
    d = documentos.info(doc_id)
    if d is None or not documentos.ruta(doc_id).is_file():
        return JSONResponse({"error": "Documento no encontrado."}, status_code=404)
    return FileResponse(documentos.ruta(doc_id), media_type="application/pdf", filename=d["archivo"],
                        content_disposition_type="attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox",
                                 "Cache-Control": "no-store"})


# ---------- misiones individuales del Equipo Azul ----------
@app.get("/api/misiones")
async def misiones():
    """Solo Azul (SOLO_EQUIPO): progreso de su usuario en las misiones fijas y riesgo actual de la partida."""
    usuario = USUARIO_EQUIPO.get("azul")
    lista = repositorio.por_defecto().misiones(PARTIDA_ID, usuario, PARTIDA.transcurrido_s()) if usuario else []
    return {"usuario": usuario, "misiones": lista, "transcurrido_s": PARTIDA.transcurrido_s(),
            "puntos": sum(m["puntos_obtenidos"] or 0 for m in lista if m["estado"] == "completada"),
            "riesgo_partida": ESTADO_PARTIDA.riesgo_acumulado}


@app.post("/api/misiones/{mision_id}/completar")
async def completar_mision(mision_id: int, request: Request):
    """Solo Azul y solo misiones 'manual' (p. ej. revisar el buzón); las demás las completa su evento."""
    if request.state.equipo != "azul":
        return _prohibido("Solo el equipo azul puede completar sus misiones.")
    if cerrada := _partida_cerrada():
        return cerrada
    usuario = USUARIO_EQUIPO.get("azul")
    r = repositorio.por_defecto().completar_mision_manual(PARTIDA_ID, usuario, mision_id, _participante(request),
                                                          PARTIDA.transcurrido_s())
    if r is None:
        return _prohibido("Esa misión no existe o se completa sola con su evento.", 409)
    if r == "bloqueada":
        return _prohibido("Esa misión depende de otra que aún no está completada.", 409)
    if not r:
        return _prohibido("Esa misión ya estaba completada.", 409)
    ms.emitir("auditoria", ms.aud("DEFENDER", "MISION_COMPLETADA", f"misión {mision_id} (manual) · {usuario}",
                                  f"+{r['puntos_obtenidos']} pts", "BAJO"))
    _emitir_marcador()
    return {"completada": True, "mision_id": mision_id, "puntos": r["puntos_obtenidos"], "a_tiempo": r["a_tiempo"]}


@app.post("/api/misiones/{mision_id}/asumir")
async def asumir_mision(mision_id: int, request: Request):
    """Solo Azul: el participante se hace responsable de la misión (visible para todo su equipo)."""
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    r = repositorio.por_defecto().asumir_mision(PARTIDA_ID, usuario, mision_id, _participante(request))
    if r is None:
        return _prohibido("Esa misión no existe.", 404)
    if r == "completada":
        return _prohibido("Esa misión ya está completada.", 409)
    ms.emitir("auditoria", ms.aud("DEFENDER", "MISION_ASUMIDA", f"misión {mision_id} · {_participante(request)}",
                                  "OK", "BAJO"))
    ms.emitir("misiones_cambio", {"mision_id": mision_id})
    return {"asumida": True, "mision_id": mision_id, "responsable": _participante(request)}


# ---------- incidentes de la partida y credenciales ficticias (Fase E) ----------
@app.get("/api/incidentes")
async def listar_incidentes(request: Request):
    """Azul (los gestiona) y General (los supervisa)."""
    if request.state.equipo not in ("azul", "general"):
        return _prohibido("Solo el equipo azul y el árbitro ven los incidentes.")
    repo = repositorio.por_defecto()
    return {"incidentes": [{**i, "pendiente": repo.pendiente_para_resolver(PARTIDA_ID, i) if i["estado"] != "resuelto"
                            else []} for i in repo.incidentes(PARTIDA_ID)]}


class IncidenteIn(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=80)
    severidad: str = Field(..., pattern="^(baja|media|alta|critica)$")
    correo_id: int | None = None


@app.post("/api/incidentes")
async def abrir_incidente(body: IncidenteIn, request: Request):
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    try:
        inc = repositorio.por_defecto().abrir_incidente(PARTIDA_ID, usuario, _participante(request), body.titulo,
                                                        body.severidad, body.correo_id)
    except ValueError as e:
        return _error400(str(e))
    if inc is None:
        return _prohibido(*_NO_ES_SUYO)
    ms.emitir("auditoria", ms.aud("DEFENDER", "INCIDENTE_ABIERTO", f"#{inc['id']} {inc['titulo']} · {inc['severidad']}",
                                  "OK", "MEDIO"))
    ms.emitir("incidentes_cambio", {"id": inc["id"]})
    return {"incidente": inc, "regla": _aplicar_regla("incidente_abierto", usuario, request, f"incidente:{inc['id']}")}


class EstadoIncidenteIn(BaseModel):
    estado: str = Field(..., pattern="^(en_investigacion|resuelto)$")
    resolucion: str | None = Field(None, max_length=500)


@app.post("/api/incidentes/{inc_id}/estado")
async def avanzar_incidente(inc_id: int, body: EstadoIncidenteIn, request: Request):
    """abierto -> en_investigacion -> resuelto. Resolver exige resolución y la amenaza del correo contenida."""
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    try:
        inc = repositorio.por_defecto().avanzar_incidente(PARTIDA_ID, usuario, inc_id, _participante(request),
                                                          body.estado, body.resolucion)
    except ValueError as e:
        return _prohibido(str(e), 409)
    if inc is None:
        return _prohibido("Ese incidente no existe en esta partida.", 404)
    ms.emitir("auditoria", ms.aud("DEFENDER", "INCIDENTE_RESUELTO" if body.estado == "resuelto" else "INCIDENTE_ACTUALIZADO",
                                  f"#{inc_id} → {body.estado}", "OK", "BAJO"))
    ms.emitir("incidentes_cambio", {"id": inc_id})
    regla = _aplicar_regla("incidente_resuelto", usuario, request, f"incidente:{inc_id}") \
        if body.estado == "resuelto" else None
    return {"incidente": inc, "regla": regla}


@app.get("/api/credenciales")
async def ver_credenciales(request: Request):
    """Azul: estado de la credencial ficticia de su usuario (segura · comprometida · revocada) e historial."""
    if request.state.equipo != "azul":
        return _prohibido("Solo el equipo azul gestiona sus credenciales.")
    usuario = USUARIO_EQUIPO.get("azul")
    return repositorio.por_defecto().credenciales(PARTIDA_ID, usuario) if usuario else {"estado": "segura", "historial": []}


@app.post("/api/credenciales/revocar")
async def revocar_credencial(request: Request):
    if err := _accion_azul(request):
        return err
    usuario = USUARIO_EQUIPO.get("azul")
    if repositorio.por_defecto().revocar_credencial(PARTIDA_ID, usuario, _participante(request)) != "revocada":
        return _prohibido("No hay ninguna credencial comprometida que revocar.", 409)
    ms.emitir("auditoria", ms.aud("DEFENDER", "CREDENCIAL_REVOCADA", f"{usuario} · {_participante(request)}",
                                  "OK", "BAJO"))
    ms.emitir("credenciales_cambio", {"usuario": usuario, "estado": "revocada"})
    return {"revocada": True, "regla": _aplicar_regla("credencial_revocada", usuario, request, f"credencial:{usuario}")}


_PAGINA_ENLACE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Laboratorio · enlace de prueba</title>
<style>body{{font-family:system-ui,sans-serif;background:#0f1720;color:#e6edf3;display:grid;place-items:center;
min-height:100vh;margin:0;padding:16px}}main{{max-width:520px;border:1px solid #3b4a5a;border-radius:10px;
padding:28px}}h1{{font-size:22px;margin:0 0 12px}}p{{line-height:1.5;color:#b6c2cf}}</style></head>
<body><main><h1>{titulo}</h1><p>{texto}</p>{extra}</main></body></html>"""
# Formulario de la página «de inicio de sesión» falsa: SIN campos de texto. Nadie escribe una contraseña; el botón
# simula que el empleado la entrega, y eso compromete la credencial ficticia de su cuenta.
_FORM_CREDENCIALES = """<form method="post" action="/l/{enlace}/credenciales" style="margin-top:18px;border-top:1px solid
#3b4a5a;padding-top:16px"><p><b>Portal de verificación de cuenta</b> (imitación)</p><p>Simulación: aquí un atacante
pediría tu usuario y contraseña. No escribas nada: el botón representa enviarlos.</p><button type="submit"
style="padding:8px 14px;border-radius:6px;border:0;background:#c0392b;color:#fff;font-weight:600">Iniciar sesión
(simulado: entregar mi contraseña)</button></form>"""
_CABECERAS_ENLACE = {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
                     "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


@app.get("/l/{enlace_id}")
async def abrir_enlace(enlace_id: str):
    """Enlace de un correo de entrenamiento: registra el clic en auditoría y muestra una página FIJA (no refleja
    nada de la petición). Solo existen los enlaces que generó el servidor."""
    _vencer_si_toca()
    if PARTIDA.fase != "en_curso":  # fuera de la partida el clic no tiene consecuencia ni se registra
        return HTMLResponse(_PAGINA_ENLACE.format(
            titulo="La partida no está en curso",
            texto="Este enlace de entrenamiento solo cuenta mientras la partida está en curso.", extra=""),
            status_code=409, headers=_CABECERAS_ENLACE)
    clic = None
    if 8 <= len(enlace_id) <= 32 and all(ch.isalnum() or ch in "-_" for ch in enlace_id):
        clic = repositorio.por_defecto().registrar_clic(enlace_id)
    if clic is None:
        return HTMLResponse(_PAGINA_ENLACE.format(titulo="Enlace no válido",
                                                  texto="Este enlace no pertenece al laboratorio.", extra=""),
                            status_code=404, headers=_CABECERAS_ENLACE)
    if clic["contenido"]:  # Azul ya lo contuvo: el clic no tiene consecuencia
        ms.emitir("auditoria", ms.aud("SYSTEM", "CLIC_BLOQUEADO",
                                      f"correo {clic['correo_id']} · {clic['para_usuario']}", "BLOQUEADO", "BAJO"))
        return HTMLResponse(_PAGINA_ENLACE.format(
            titulo="Enlace bloqueado por el Equipo Azul",
            texto="Este enlace de entrenamiento fue contenido después de un clic, así que ya no tiene efecto. "
                  "El intento quedó registrado.", extra=""), headers=_CABECERAS_ENLACE)
    ms.emitir("auditoria", ms.aud("SYSTEM", "CLIC_ENLACE", f"correo {clic['correo_id']} · {clic['para_usuario']}",
                                  "CLIC", "ALTO"))
    _aplicar_regla("CLIC_ENLACE", clic["para_usuario"])
    pide = repositorio.por_defecto().pide_credenciales(clic["correo_id"])
    return HTMLResponse(_PAGINA_ENLACE.format(
        titulo="Este fue un enlace de prueba del laboratorio",
        texto="Has abierto un enlace de un correo de entrenamiento. No ha ocurrido nada real, pero el clic quedó "
              "registrado. Antes de abrir un enlace, revisa el remitente, la urgencia del mensaje y a dónde "
              "apunta realmente.", extra=_FORM_CREDENCIALES.format(enlace=enlace_id) if pide else ""),
        headers=_CABECERAS_ENLACE)


_CREDENCIAL_PAGINA = {
    "no_existe": (404, "Enlace no válido", "Este enlace no pertenece a la partida en curso."),
    "no_pide": (404, "Nada que enviar", "Esta página no pide credenciales."),
    "sin_clic": (409, "Abre primero el enlace", "Esta página solo se alcanza desde el enlace del correo."),
    "contenido": (200, "Enlace bloqueado por el Equipo Azul", "El enlace fue contenido: el envío no tuvo efecto."),
}


@app.post("/l/{enlace_id}/credenciales")
async def enviar_credenciales(enlace_id: str):
    """El empleado «entrega» su contraseña en la página falsa (simulado: no hay campos, no se recibe ningún dato).
    Compromete la credencial ficticia de su cuenta hasta que Azul la revoque (regla credencial_comprometida)."""
    _vencer_si_toca()
    if PARTIDA.fase != "en_curso":
        return HTMLResponse(_PAGINA_ENLACE.format(titulo="La partida no está en curso", texto="El envío no cuenta.",
                                                  extra=""), status_code=409, headers=_CABECERAS_ENLACE)
    r = "no_existe"
    if 8 <= len(enlace_id) <= 32 and all(ch.isalnum() or ch in "-_" for ch in enlace_id):
        r = repositorio.por_defecto().comprometer_credencial(PARTIDA_ID, enlace_id)
    if not isinstance(r, dict):
        status, titulo, texto = _CREDENCIAL_PAGINA[r]
        return HTMLResponse(_PAGINA_ENLACE.format(titulo=titulo, texto=texto, extra=""), status_code=status,
                            headers=_CABECERAS_ENLACE)
    if r["nuevo"]:
        ms.emitir("auditoria", ms.aud("SYSTEM", "CREDENCIAL_COMPROMETIDA", f"correo {r['correo_id']} · {r['usuario']}",
                                      "COMPROMETIDA", "CRITICO"))
        ms.emitir("credenciales_cambio", {"usuario": r["usuario"], "estado": "comprometida"})
        _aplicar_regla("credencial_comprometida", r["usuario"])
    return HTMLResponse(_PAGINA_ENLACE.format(
        titulo="Has entregado tu contraseña a una página falsa",
        texto="En un ataque real, el atacante ya podría entrar en tu cuenta. En el laboratorio, la credencial ficticia "
              "de tu cuenta queda COMPROMETIDA hasta que el Equipo Azul la revoque. Contener el enlace no basta.",
        extra=""), headers=_CABECERAS_ENLACE)


@app.post("/api/batalla/real/iniciar")
async def iniciar_real(body: BatallaRealIn, request: Request):
    if err := _rol_no_coincide(request, body.de_rol):
        return err
    if err := _practica_bloqueada():
        return err
    if ms.ESTADO["corriendo"] or RETO is not None or ATAQUE_IA is not None:
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
                                                p["intensidad"], cfg["host_atq"], cfg["host_def"], p["demo"],
                                                p.get("dificultad"), p.get("escenario")))


async def _proponer_reto(body, ident):
    """No gasta inferencia: emite el reto y espera a que el otro equipo acepte (o a los 30 s)."""
    global RETO
    a_rol = {"rojo": "azul", "azul": "rojo"}.get(body.de_rol)  # la vista general no necesita aceptación
    evento = {"de_rol": body.de_rol, "a_rol": a_rol, "rondas": body.rondas, "intensidad": body.intensidad,
              "dificultad": body.dificultad, "demo": body.demo, "escenario": body.escenario,
              "segundos": TIMEOUT_RETO}
    params = {"rondas": body.rondas, "ident": ident, "intensidad": body.intensidad, "demo": body.demo,
              "dificultad": body.dificultad, "escenario": body.escenario}
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
async def responder_reto(body: RespuestaRetoIn, request: Request):
    global RETO
    if body.rol and (err := _rol_no_coincide(request, body.rol)):
        return err
    quien = request.state.equipo  # quien responde es el dueño del token, no el rol que diga el cuerpo
    reto = RETO
    if reto is None:
        return JSONResponse({"error": "No hay ningún reto pendiente.", "mensaje": "No hay ningún reto pendiente."},
                            status_code=409)
    if quien not in (reto["a_rol"], "general"):
        msg = "Solo el equipo destinatario (o la vista general) puede responder al reto."
        return JSONResponse({"error": msg, "mensaje": msg}, status_code=409)
    RETO = None
    reto["timer"].cancel()
    ms.ESTADO["esperando_aceptacion"] = False
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


def _cerrar_informe(informe, puntos, jugadas, errores, estado_sesion, decisiones):
    """Informe agregado de la sesión completa (se adjunta a partida_fin y la UI lo exporta como JSON).
    decisiones = [(decision_ia, veredicto), ...] de las rondas válidas, para el resumen sí/no."""
    a, d = puntos["atacante"], puntos["defensor"]
    return {**informe, **motor.resumen_sino(decisiones), "rondas_totales": jugadas + errores, "rondas_validas": jugadas,
            "puntos_atacante": a, "puntos_defensor": d,
            "ganador": "atacante" if a > d else "defensor" if d > a else "empate",
            "riesgo_acumulado_final": estado_sesion.riesgo_acumulado}


def _partida_fin(puntos, jugadas, errores, detenida=False, informe=None):
    a, d = puntos["atacante"], puntos["defensor"]
    ms.emitir("partida_fin", {"puntos_atacante": a, "puntos_defensor": d, "rondas_jugadas": jugadas,
                              "ganador": "atacante" if a > d else "defensor" if d > a else "empate",
                              "errores": errores, "detenida": detenida, "informe": informe})


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


def _objetivo(at):
    """Objetivo real del atacante (depende de la dificultad); el ataque manual no trae uno y usa el genérico."""
    return {"objetivo": at.get("objetivo") or OBJETIVO_TXT,
            "sensibilidad_objetivo": at.get("sensibilidad_objetivo") or "CRITICA"}


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
        ms.emitir("ataque", {"ronda": n, "prompt": at["prompt"], "categoria": at["categoria"], **_objetivo(at),
                             **_meta(at, matq)})
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
    ms.emitir("ataque", {"ronda": n, "prompt": at["prompt"], "categoria": at["categoria"], **_objetivo(at),
                         **_meta(at, matq)})
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
         "origen_decision": "filtro_rapido" if filtro else "ia", "nota": r.get("nota")}
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


async def _correr_real(modelo_atq, modelo_def, rondas, ident, intensidad=2, host_atq=None, host_def=None, demo=False,
                       dificultad=None, escenario=None):
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
    decisiones = []  # (decision_ia, veredicto) por ronda válida, solo para el resumen sí/no del informe
    puntos = None if demo else {"atacante": 0, "defensor": 0}  # la demostración (admin) no puntúa
    estado_sesion = sesion.EstadoSesion()  # nuevo en cada batalla (revancha incluida); se descarta al terminar
    informe = {"veredictos_por_tipo": {k: 0 for k in ("FALLA_DEFENSA", "DEFENSA_EXITOSA", "DEFENSA_EN_PROFUNDIDAD",
                                                      "PERMITIDO_CORRECTO", "ERROR")},
               "fugas_parciales": 0, "activaciones_circuito_sesion": 0, "bloqueos_filtro_rapido": 0,
               "dificultad": dificultad, "escenario": escenario, "usuario": f"{ident.usuario} ({ident.rol})",
               "modelos_usados": {"atacante": f"{modelo_atq} @ {host_atq}", "defensor": f"{modelo_def} @ {host_def}"}}
    ms.emitir("auditoria", ms.aud("SYSTEM", "INICIO", f"batalla real · {ident.usuario} ({ident.rol}) · intensidad {intensidad} · escenario {escenario or 'libre'}", "OK", "BAJO"))
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
                        host_def=host_def, riesgo_sesion=estado_sesion.riesgo_acumulado,
                        resumen_sesion=estado_sesion.resumen(), escenario=escenario, equipo="rojo")),
                    TIMEOUT_RONDA)
            except asyncio.TimeoutError:
                r = {"ronda": n, "ataque": None, "defensa": None, "ejecucion": None, "veredicto": "ERROR",
                     "error": f"timeout de ronda ({TIMEOUT_RONDA} s)"}
            if r["veredicto"] == "ERROR":
                errores += 1
                informe["veredictos_por_tipo"]["ERROR"] += 1
                await _emitir_error(r, modelo_atq, modelo_def)  # no se registra en métricas; la batalla continúa
            else:
                d = await _emitir_ronda(r, modelo_atq, modelo_def, puntos=puntos, sesion_estado=estado_sesion)
                informe["veredictos_por_tipo"][d["resultado"]] = informe["veredictos_por_tipo"].get(d["resultado"], 0) + 1
                informe["fugas_parciales"] += int(d.get("nivel_fuga") == "PARCIAL")
                informe["activaciones_circuito_sesion"] += int(bool(d.get("circuito_sesion")))
                informe["bloqueos_filtro_rapido"] += int(d.get("origen_decision") == "filtro_rapido")
                decisiones.append((d["decision_ia"], d["resultado"]))
                jugadas += 1
                historial.append({"categoria": r["ataque"]["categoria"], "resultado": r["veredicto"]})
                _emitir_marcador()  # cuenta en vivo los intentos de Rojo frenados (denegaciones)
            await asyncio.sleep(0.6)
        ms.emitir("fin", {"modo": "batalla", "origen": "ollama", "metricas": ms.snapshot(), "errores": errores,
                          "demo": demo})
        if puntos is not None:
            _partida_fin(puntos, jugadas, errores,
                         informe=_cerrar_informe(informe, puntos, jugadas, errores, estado_sesion, decisiones))
    except asyncio.CancelledError:
        ms.emitir("auditoria", ms.aud("SYSTEM", "DETENIDO", "batalla real", "CANCELADO", "BAJO"))
        ms.emitir("fin", {"modo": "batalla", "origen": "ollama", "detenido": True,
                          "metricas": ms.snapshot(), "errores": errores})
        if puntos is not None:
            _partida_fin(puntos, jugadas, errores, detenida=True,
                         informe=_cerrar_informe(informe, puntos, jugadas, errores, estado_sesion, decisiones))
    except Exception as exc:  # noqa: BLE001
        ms.emitir("error", {"mensaje": f"Error interno de la batalla real: {exc}"})
    finally:
        ms.ESTADO.update(corriendo=False, modelo_atq=previo[0], modelo_def=previo[1])


# ---------- batalla integrada en la partida (Fase F) ----------
# Rojo decide CUÁNDO lanza cada ataque IA (uno a la vez, como máximo ataque_ia.MAX_ATAQUES por partida); el defensor
# IA de Azul responde siempre, sin reto ni aceptación. Cada ataque son dos inferencias reales (atacante y defensor)
# seguidas de las capas deterministas; su resultado suma al marcador de la PARTIDA. Las fases que se difunden son
# las reales («esperando a la Ollama del atacante/defensor»): no hay barras de progreso inventadas.
ATAQUE_IA = None          # ataque en curso: {"ataque": fila, "fase": str, "modelo": str, "desde": monotonic, "tarea"}
ESTADO_IA = sesion.EstadoSesion()  # patrón de los ataques IA de esta partida (contexto del defensor y circuito)
DEFENSOR_IA = {"ok": None, "ts": None, "error": None}  # última comprobación REAL del defensor de Azul
# Rutas de práctica (simulación, prueba manual y batalla «mejor de N»): solo fuera de una partida en curso.
RUTAS_PRACTICA = ("/api/simulacion/iniciar", "/api/batalla/iniciar", "/api/manual")


class AtaqueIAIn(BaseModel):
    modelo: str = Field(..., min_length=1, max_length=100)    # modelo del atacante (Ollama del equipo rojo)
    host: str | None = Field(None, max_length=200)
    tecnica: str | None = Field(None, pattern="^(" + "|".join(atacante.CATEGORIAS) + ")$")  # None = libre
    intensidad: int = Field(2, ge=1, le=3)


class DefensorIAIn(BaseModel):
    modelo: str = Field(..., min_length=1, max_length=100)
    host: str | None = Field(None, max_length=200)


def _practica_bloqueada():
    if PARTIDA.fase == "en_curso":
        return _prohibido("Durante la partida la batalla es por ataques IA: Rojo los lanza cuando quiere y el defensor "
                          "de Azul responde siempre. La simulación, la prueba manual y la batalla «mejor de N» son "
                          "práctica: úsalas antes de iniciar o después de finalizar.", 409)
    return None


def _publico_ataque(a):
    return {k: v for k, v in a.items() if k != "partida"} | {"titulo": ataque_ia.TITULO.get(a.get("resultado"))}


def _en_curso_ia():
    if ATAQUE_IA is None:
        return None
    a = ATAQUE_IA["ataque"]
    return {"id": a["id"], "n": a["n"], "usuario": a["usuario"], "origen_identidad": a["origen_identidad"],
            "tecnica": a["tecnica"], "intensidad": a["intensidad"], "lanzado_por": a["lanzado_por"],
            "fase": ATAQUE_IA["fase"], "modelo": ATAQUE_IA["modelo"], "prompt": ATAQUE_IA.get("prompt"),
            "transcurrido_ms": int((time.monotonic() - ATAQUE_IA["desde"]) * 1000)}


def _estado_ia():
    """Todo lo que la UI necesita de la batalla de la partida (sin secretos: los ataques y prompts son ficticios)."""
    repo = repositorio.por_defecto()
    usuario, origen = repo.identidad_atacante(PARTIDA_ID)
    ataques = repo.ataques_ia(PARTIDA_ID)
    d, a = CONFIG_ROL["azul"], CONFIG_ROL["rojo"]
    return {"partida": PARTIDA_ID, "fase_partida": PARTIDA.fase, "max_ataques": ataque_ia.MAX_ATAQUES,
            "lanzados": len(ataques), "restantes": max(0, ataque_ia.MAX_ATAQUES - len(ataques)),
            "identidad": {"usuario": usuario, "origen": origen, "rol": repo.identidad(usuario).rol},
            "defensor": {"modelo": d["modelo"] if d else None, "host": d["host"] if d else None, **DEFENSOR_IA},
            "atacante": {"modelo": a["modelo"] if a else None, "host": a["host"] if a else None},
            "en_curso": _en_curso_ia(), "ataques": [_publico_ataque(x) for x in ataques],
            "puntos": repo.puntos_ia(PARTIDA_ID), "tecnicas": list(atacante.CATEGORIAS)}


def _emitir_ia():
    ms.emitir("ia_estado", _estado_ia())


@app.get("/api/ia/estado")
async def estado_ia():
    return _estado_ia()


@app.post("/api/ia/defensor")
async def configurar_defensor(body: DefensorIAIn, request: Request):
    """Solo Azul (SOLO_EQUIPO): elige el modelo de su defensor IA y comprueba de verdad que su Ollama lo tiene."""
    err = await _registrar_lado("azul", body.modelo.strip(), body.host)
    DEFENSOR_IA.update(ok=err is None, ts=pt.ahora_iso(), error=err)
    if err is None:
        repositorio.por_defecto().registrar(None, "DEFENSOR_IA_CONFIGURADO", f"modelo:{body.modelo}",
                                            _participante(request) or "azul", "BAJO")
        ms.emitir("auditoria", ms.aud("DEFENDER", "CONFIGURADO", f"{CONFIG_ROL['azul']['modelo']} @ "
                                      f"{CONFIG_ROL['azul']['host']}", "OK", "BAJO"))
    _emitir_ia()
    return _prohibido(err, 409) if err else _estado_ia()


@app.post("/api/ia/ataque")
async def lanzar_ataque_ia(body: AtaqueIAIn, request: Request):
    """Solo Rojo (SOLO_EQUIPO) y con la partida en curso: lanza UN ataque IA. Responde enseguida (202 lógico) y el
    progreso llega por SSE (ia_ataque / ia_estado); el resultado suma al marcador de la partida."""
    global ATAQUE_IA
    if err := _partida_cerrada():
        return err
    if ATAQUE_IA is not None:
        return _prohibido("Ya hay un ataque IA en curso: espera a que el defensor responda.", 409)
    if ms.ESTADO["corriendo"] or RETO is not None:
        return _prohibido("Hay una ejecución de práctica en curso: el árbitro debe detenerla antes.", 409)
    repo = repositorio.por_defecto()
    if len(repo.ataques_ia(PARTIDA_ID)) >= ataque_ia.MAX_ATAQUES:
        return _prohibido(f"Ya lanzaste los {ataque_ia.MAX_ATAQUES} ataques IA de esta partida.", 409)
    ATAQUE_IA = {"ataque": None, "fase": "validando", "modelo": body.modelo, "desde": time.monotonic()}  # reserva
    err = await _registrar_lado("rojo", body.modelo.strip(), body.host)
    if err or PARTIDA.fase != "en_curso":
        ATAQUE_IA = None
        return _prohibido(err or "La partida ya no está en curso.", 409)
    usuario, origen = repo.identidad_atacante(PARTIDA_ID)
    dfn = CONFIG_ROL["azul"]
    a = repo.crear_ataque_ia(PARTIDA_ID, _participante(request), usuario, origen, body.tecnica, body.intensidad,
                             CONFIG_ROL["rojo"]["modelo"], dfn["modelo"] if dfn else None)
    if a is None:
        ATAQUE_IA = None
        return _prohibido(f"Ya lanzaste los {ataque_ia.MAX_ATAQUES} ataques IA de esta partida.", 409)
    ATAQUE_IA = {"ataque": a, "fase": "atacante", "modelo": CONFIG_ROL["rojo"]["modelo"], "desde": time.monotonic()}
    ATAQUE_IA["tarea"] = asyncio.create_task(_correr_ataque_ia(PARTIDA, a, dict(CONFIG_ROL["rojo"]),
                                                               dict(dfn) if dfn else None))
    ms.emitir("auditoria", ms.aud("ATTACKER", "ATAQUE_IA", f"#{a['n']} · {usuario} ({origen})",
                                  f"técnica {body.tecnica or 'libre'} · intensidad {body.intensidad}", "MEDIO"))
    _emitir_ia()
    return {"ataque": _en_curso_ia()}


def _emitir_fase_ia():
    ms.emitir("ia_ataque", {"en_curso": _en_curso_ia()})


def _fase_ia(fase, modelo, prompt=None):
    ATAQUE_IA.update(fase=fase, modelo=modelo, desde=time.monotonic())
    if prompt is not None:
        ATAQUE_IA["prompt"] = prompt
    _emitir_fase_ia()


async def _inferencia(fn):
    """Una llamada bloqueante a Ollama en un hilo, con el tope de TIMEOUT_RONDA. -> resultado o None si se agotó."""
    try:
        return await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(None, fn), TIMEOUT_RONDA)
    except asyncio.TimeoutError:
        return None


def _metricas(prefijo, x):
    x = x or {}
    return {f"{prefijo}_ms": x.get("tiempo_ms"), f"{prefijo}_tokens_entrada": x.get("tokens_entrada"),
            f"{prefijo}_tokens_salida": x.get("tokens"), f"{prefijo}_carga_ms": x.get("carga_ms")}


async def _correr_ataque_ia(partida, a, atq, dfn):
    """Atacante IA -> defensor IA -> capas -> clasificación y puntos. Nunca deja el ataque a medias: termina en
    «terminado» (con resultado) o «cancelado» (la partida acabó antes)."""
    global ATAQUE_IA
    repo = repositorio.por_defecto()
    ident = repo.identidad(a["usuario"])
    try:
        historial = [{"categoria": x["categoria"], "resultado": x["veredicto"]}
                     for x in repo.ataques_ia(partida.id) if x["estado"] == "terminado" and x["categoria"]]
        at = await _inferencia(lambda: atacante.generar_ataque(atq["host"], atq["modelo"], ident.rol, historial,
                                                               a["intensidad"], None, a["n"], a["tecnica"]))
        if at is None:
            at = {"ok": False, "error": f"timeout ({TIMEOUT_RONDA} s)"}
        campos = {**_metricas("atq", at), "objetivo": at.get("objetivo"),
                  "sensibilidad_objetivo": at.get("sensibilidad_objetivo"), "categoria": at.get("categoria"),
                  "prompt": at.get("prompt")}
        if not at["ok"]:
            res = {"resultado": "error_atacante", "puntos_rojo": 0, "puntos_azul": 0, "sensibilidad_expuesta": None}
            p, error = None, "atacante: " + str(at["error"])
        else:
            if dfn is None:
                p = {"veredicto": "ERROR", "error": "defensor: el Equipo Azul no ha configurado su defensor IA",
                     "defensa": None, "ejecucion": None}
            else:
                _fase_ia("defensor", dfn["modelo"], at["prompt"])
                p = await _inferencia(lambda: motor.procesar_defensa(
                    dfn["host"], dfn["modelo"], at["prompt"], ident, repo, ESTADO_IA.riesgo_acumulado,
                    ESTADO_IA.resumen(), "rojo"))
                if p is None:
                    p = {"veredicto": "ERROR", "error": f"defensor: timeout ({TIMEOUT_RONDA} s)", "defensa": None,
                         "ejecucion": None}
            res = ataque_ia.clasificar(p, a["origen_identidad"])
            error = p.get("error") if p["veredicto"] == "ERROR" else None
        if partida is not PARTIDA or partida.fase != "en_curso":
            raise asyncio.CancelledError  # la partida terminó mientras se esperaba al modelo: no cuenta
        df, ej = (p or {}).get("defensa") or {}, (p or {}).get("ejecucion") or {}
        filtro = (p or {}).get("origen_decision") == "filtro_rapido"
        if res["resultado"] != "error_atacante":  # la solicitud llegó al defensor: su estado real queda anotado
            falla = res["resultado"] == "fallo_seguro"
            DEFENSOR_IA.update(ok=not falla, ts=pt.ahora_iso(), error=error if falla else None)
        if p and p["veredicto"] != "ERROR":
            efectiva = "SOLICITAR_AUTORIZACION" if p.get("circuito_sesion") else df.get("decision")
            ESTADO_IA.registrar(at.get("categoria"), p["veredicto"], efectiva)
        capa = "circuito de sesión" if (p or {}).get("circuito_sesion") else ej.get("capa_bloqueo")
        fila = repo.cerrar_ataque_ia(
            a["id"], estado="terminado", resultado=res["resultado"], veredicto=(p or {}).get("veredicto"),
            decision_ia=df.get("decision"), origen_decision="filtro_rapido" if filtro else ("ia" if df else None),
            capa_bloqueo=capa, herramienta=ej.get("herramienta"), motivo=df.get("motivo"), error=error,
            sensibilidad_expuesta=res["sensibilidad_expuesta"], puntos_rojo=res["puntos_rojo"],
            puntos_azul=res["puntos_azul"],
            explicacion=ataque_ia.explicar(res["resultado"], a["usuario"], a["origen_identidad"],
                                           res["sensibilidad_expuesta"], capa, error, filtro),
            **campos, **_metricas("def", df if df and not filtro else None))
        ATAQUE_IA = None
        ms.emitir("ia_ataque", {"en_curso": None, "terminado": _publico_ataque(fila)})
        ms.emitir("auditoria", ms.aud("SYSTEM", "ATAQUE_IA_RESULTADO", f"#{fila['n']} · {fila['usuario']}",
                                      ataque_ia.TITULO[fila["resultado"]],
                                      "CRITICO" if fila["resultado"] == "datos_expuestos" else "BAJO"))
        evento = ataque_ia.EVENTO.get(res["resultado"])
        if evento:
            _aplicar_regla(evento, None)  # riesgo + explicación + marcador
        else:
            _emitir_marcador()
    except asyncio.CancelledError:
        repo.cerrar_ataque_ia(a["id"], estado="cancelado", resultado="cancelado",
                              explicacion=ataque_ia.explicar("cancelado", a["usuario"], a["origen_identidad"]))
        ms.emitir("ia_ataque", {"en_curso": None, "cancelado": a["n"]})
    except Exception as exc:  # noqa: BLE001 - un fallo interno nunca deja el ataque «en curso» para siempre
        repo.cerrar_ataque_ia(a["id"], estado="terminado", resultado="fallo_seguro", error=f"interno: {exc}",
                              explicacion=ataque_ia.explicar("fallo_seguro", a["usuario"], a["origen_identidad"],
                                                             error=f"error interno: {exc}"))
        ms.emitir("error", {"mensaje": f"Error interno del ataque IA: {exc}"})
    finally:
        if ATAQUE_IA is not None and ATAQUE_IA.get("ataque") and ATAQUE_IA["ataque"]["id"] == a["id"]:
            ATAQUE_IA = None
        _emitir_ia()


def _cancelar_ataque_ia():
    """Al cerrar la partida, el ataque en curso se cancela (su hilo de Ollama termina solo y se descarta)."""
    if ATAQUE_IA is not None and ATAQUE_IA.get("tarea"):
        ATAQUE_IA["tarea"].cancel()


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
    if err := _practica_bloqueada():
        return err
    if ms.ESTADO["corriendo"] or ATAQUE_IA is not None:
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
    print(f"Código de árbitro (vista General): {CODIGO_ARBITRO}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=ms.puerto())
