"""Integración con Wazuh en tres modos, y lo que cada uno significa de verdad.

    real         se conecta a una instalación de Wazuh y muestra SUS alertas.
    simulado     deduce alertas de los eventos del laboratorio aplicando las reglas locales, con un modelo
                 aproximado. Sirve para desarrollar y probar el panel sin montar la infraestructura.
    desactivado  el resto de la aplicación funciona igual; el panel dice que Wazuh está apagado.

**Una alerta simulada nunca se presenta como real.** Cada alerta lleva `origen` ("wazuh_real" | "simulado") y
`simulado` (bool), y `estado()` dice siempre qué modo está activo. Si el modo es `real` y la conexión falla,
el resultado es un error visible: *no* se cae al modo simulado por detrás.

El modo se elige con la variable de entorno `CYBERSHIELD_WAZUH` (por defecto `desactivado`).
"""
import os
import time

from . import cliente as mod_cliente, reglas as mod_reglas

MODOS = ("real", "simulado", "desactivado")
VAR_ENTORNO = "CYBERSHIELD_WAZUH"

_ESTADO = {"ultima_sincronizacion": None, "ultimo_error": None, "consultas": 0}


def modo():
    """Modo activo. Un valor desconocido en el entorno se trata como «desactivado», nunca como «real»."""
    v = (os.environ.get(VAR_ENTORNO) or "desactivado").strip().lower()
    return v if v in MODOS else "desactivado"


def _cliente(**kw):
    return mod_cliente.ClienteWazuh(
        url=os.environ.get("WAZUH_URL", "https://localhost:55000"),
        verificar_tls=(os.environ.get("WAZUH_TLS", "1") != "0"), **kw)


def _alerta(evento, regla, simulado):
    return {
        "timestamp": evento.get("timestamp"),
        "regla_id": regla["id"], "nivel": regla["nivel"],
        "descripcion": mod_reglas.describir(regla, evento),
        "grupos": regla["grupos"], "mitre": regla["mitre"],
        "agente": evento.get("origen"), "usuario": evento.get("usuario"), "rol": evento.get("rol"),
        "equipo": evento.get("equipo"), "tipo": evento.get("tipo"), "recurso": evento.get("recurso"),
        "resultado": evento.get("resultado"), "riesgo": evento.get("riesgo"),
        "correlacion": evento.get("partida"),
        "origen": "simulado" if simulado else "wazuh_real",
        "simulado": bool(simulado),
    }


def alertas_simuladas(eventos=None, nivel_minimo=0, limite=100, ruta_reglas=None):
    """Aplica las reglas locales a los eventos del laboratorio. TODA alerta sale marcada como simulada."""
    try:
        _, reglas = mod_reglas.cargar(ruta_reglas or mod_reglas.RUTA_REGLAS)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "alertas": [], "error": f"{type(exc).__name__}: {exc}", "simulado": True}
    evs = eventos if eventos is not None else mod_reglas.eventos_ejemplo()
    out = []
    for ev in evs:
        r = mod_reglas.evaluar(reglas, ev)
        if r is None or r["nivel"] < nivel_minimo:
            continue
        out.append(_alerta(ev, r, True))
    out.sort(key=lambda a: (a["timestamp"] or ""), reverse=True)
    return {"ok": True, "alertas": out[:limite], "error": None, "simulado": True,
            "eventos_leidos": len(evs)}


def alertas(nivel_minimo=0, limite=100, eventos=None, cliente=None):
    """Alertas según el modo activo. Nunca mezcla orígenes y nunca cae de «real» a «simulado» en silencio."""
    m = modo()
    _ESTADO["consultas"] += 1
    if m == "desactivado":
        return {"ok": True, "modo": m, "alertas": [], "error": None, "simulado": False,
                "nota": "Wazuh está desactivado en esta instalación."}
    if m == "simulado":
        r = alertas_simuladas(eventos, nivel_minimo, limite)
        _ESTADO["ultima_sincronizacion"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        _ESTADO["ultimo_error"] = r.get("error")
        return {**r, "modo": m,
                "nota": "Alertas DEDUCIDAS de los eventos del laboratorio con un modelo aproximado de las "
                        "reglas. No proceden de ningún Wazuh."}
    c = cliente or _cliente()
    r = c.estado_manager()
    _ESTADO["ultima_sincronizacion"] = time.strftime("%Y-%m-%dT%H:%M:%S%z") if r["ok"] else \
        _ESTADO["ultima_sincronizacion"]
    _ESTADO["ultimo_error"] = r["error"]
    if not r["ok"]:
        # Modo real sin conexión: error visible. Devolver alertas simuladas aquí sería mentir.
        return {"ok": False, "modo": m, "alertas": [], "error": r["error"], "simulado": False,
                "nota": "Modo real sin conexión con Wazuh. No se muestran alertas simuladas en su lugar."}
    return {"ok": True, "modo": m, "alertas": [], "error": None, "simulado": False,
            "nota": "Conexión con Wazuh establecida. La consulta de alertas del indexador todavía no está "
                    "implementada: esta versión solo lee estado, agentes y reglas."}


def estado(cliente=None):
    """Estado de la integración, para el panel. Nunca afirma que hay conexión sin haberla comprobado."""
    m = modo()
    base = {"modo": m, "modos": list(MODOS), "variable_entorno": VAR_ENTORNO,
            "ultima_sincronizacion": _ESTADO["ultima_sincronizacion"],
            "ultimo_error": _ESTADO["ultimo_error"], "consultas": _ESTADO["consultas"],
            "ruta_eventos": str(mod_reglas.RUTA_EJEMPLOS.parent.parents[0] / "data" / "eventos.jsonl"),
            "ruta_reglas": str(mod_reglas.RUTA_REGLAS)}
    try:
        _, reglas = mod_reglas.cargar()
        base["reglas_definidas"] = len(reglas)
    except Exception as exc:  # noqa: BLE001
        base["reglas_definidas"] = 0
        base["ultimo_error"] = f"{type(exc).__name__}: {exc}"
    if m == "desactivado":
        return {**base, "conectado": False,
                "detalle": "Desactivado: el laboratorio funciona igual y no se consulta ningún Wazuh."}
    if m == "simulado":
        return {**base, "conectado": False, "simulado": True,
                "detalle": "Simulado: las alertas se deducen de los eventos del laboratorio y van marcadas "
                           "como simuladas. No hay ningún Wazuh conectado."}
    c = (cliente or _cliente()).comprobar()
    _ESTADO["ultimo_error"] = c["error"]
    return {**base, "conectado": c["conectado"], "version": c["version"], "ultimo_error": c["error"],
            "ms": c["ms"], "simulado": False,
            "detalle": ("Conectado a Wazuh." if c["conectado"]
                        else "Modo real, pero sin conexión con Wazuh.")}
