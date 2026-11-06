"""Motor de evaluación autónoma: ejecuta campañas reproducibles contra Ollama real.

Qué garantiza:
  - **Reproducible.** Misma semilla = mismo orden de escenarios y mismas repeticiones. La semilla, el modelo,
    la técnica y todos los parámetros quedan en el resultado.
  - **Denominador honesto.** Un fallo de Ollama no cuenta como fallo del modelo. Las métricas separan
    siempre las rondas imputables de las que no lo son, y los escenarios no verificables quedan fuera de la
    exactitud oficial.
  - **Cancelable.** `Campana.cancelar()` para entre rondas; lo ejecutado hasta ese punto se conserva.
  - **Sin inventar progreso.** El progreso es rondas hechas sobre rondas planificadas, nada estimado.

Lo que NO hace: decidir si una respuesta es correcta preguntándoselo a un modelo. La referencia es
determinista (ver `escenarios.esperado`).
"""
import random
import threading
import time

from .. import diagnostico, harness as mod_harness, motor, permisos, repositorio
from . import escenarios, metricas

PIPELINES = ("directo", "harness")

# Presets de modo: (familias, repeticiones, descripción). `None` en familias = todas.
MODOS = {
    "rapido":      (("oficiales",), 1,
                    "Detección de regresiones: el conjunto oficial una vez."),
    "estandar":    (("oficiales", "fuera_muestra", "autorizacion", "parecidos"), 3,
                    "Conjunto principal con 3 repeticiones."),
    "intensivo":   (None, 5,
                    "Todas las familias con 5 repeticiones."),
    "estres":      (None, 20,
                    "Ejecución prolongada para detectar fugas de memoria, conexiones y degradación."),
    "comparativo": (("oficiales", "fuera_muestra", "parecidos"), 5,
                    "Mismo conjunto bajo varias técnicas o modelos."),
}


class Campana:
    """Una campaña en curso. Observable (`progreso()`) y cancelable (`cancelar()`)."""

    def __init__(self, config):
        self.config = dict(config)
        self.rondas = []
        self.planificadas = 0
        self.inicio = None
        self.fin = None
        self.estado = "pendiente"
        self._cancelar = threading.Event()

    def cancelar(self):
        self._cancelar.set()

    @property
    def cancelada(self):
        return self._cancelar.is_set()

    def progreso(self):
        """Progreso REAL: hechas / planificadas. Nunca una barra inventada."""
        hechas = len(self.rondas)
        return {"estado": self.estado, "hechas": hechas, "planificadas": self.planificadas,
                "fraccion": (hechas / self.planificadas) if self.planificadas else 0.0,
                "transcurrido_s": (time.monotonic() - self.inicio) if self.inicio else 0.0,
                "cancelada": self.cancelada}


def plan(modo="estandar", familias=None, repeticiones=None, semilla=0, repo=None, solo_verificables=False):
    """Lista ordenada y reproducible de (escenario, repetición). No ejecuta nada."""
    fam_modo, rep_modo, _ = MODOS.get(modo, MODOS["estandar"])
    fams = familias if familias is not None else fam_modo
    reps = int(repeticiones if repeticiones is not None else rep_modo)
    base = escenarios.conjunto(fams, repo, solo_verificables)
    trabajos = [(e, i + 1) for e in base for i in range(max(1, reps))]
    random.Random(semilla).shuffle(trabajos)   # el orden también es parte de la reproducibilidad
    return trabajos


def _identidad(rol):
    return permisos.Identidad(f"eval.{rol}", rol)


def ejecutar(host="http://localhost:11434", modelo="", modo="estandar", tecnica="fewshot", pipeline="directo",
             familias=None, repeticiones=None, semilla=0, temperatura=None, rag_k=None, rag_umbral=None,
             repo=None, presupuesto=None, al_avanzar=None, campana=None, procesar=None,
             max_segundos=None, solo_verificables=False):
    """Ejecuta una campaña completa. -> dict con config, rondas y métricas. Nunca lanza.

    `procesar` sustituye a motor.procesar_defensa (pruebas). `al_avanzar(progreso, ronda)` se llama tras cada
    ronda. `max_segundos` es un techo de pared para toda la campaña."""
    camp = campana or Campana({})
    repo = repo or repositorio.abrir(":memory:")
    procesar = procesar or motor.procesar_defensa
    pipeline = pipeline if pipeline in PIPELINES else "directo"
    config = {"host": host, "modelo": modelo, "modo": modo, "tecnica": tecnica, "pipeline": pipeline,
              "familias": list(familias) if familias else None, "repeticiones": repeticiones,
              "semilla": semilla, "temperatura": temperatura, "rag_k": rag_k, "rag_umbral": rag_umbral,
              "max_segundos": max_segundos, "solo_verificables": solo_verificables}
    camp.config = config
    trabajos = plan(modo, familias, repeticiones, semilla, repo, solo_verificables)
    camp.planificadas = len(trabajos)
    camp.inicio = time.monotonic()
    camp.estado = "en_curso"

    for esc, rep in trabajos:
        if camp.cancelada:
            camp.estado = "cancelada"
            break
        if max_segundos is not None and (time.monotonic() - camp.inicio) >= max_segundos:
            camp.estado = "tiempo_agotado"
            break
        camp.rondas.append(_una_ronda(esc, rep, host, modelo, tecnica, pipeline, temperatura, rag_k,
                                      rag_umbral, repo, presupuesto, procesar))
        if al_avanzar:
            try:
                al_avanzar(camp.progreso(), camp.rondas[-1])
            except Exception:  # noqa: BLE001 - un observador roto no tumba la campaña
                pass
    else:
        camp.estado = "terminada"
    camp.fin = time.monotonic()
    return {"config": config, "estado": camp.estado, "planificadas": camp.planificadas,
            "duracion_s": camp.fin - camp.inicio, "rondas": camp.rondas,
            "metricas": resumir(camp.rondas)}


def _una_ronda(esc, rep, host, modelo, tecnica, pipeline, temperatura, rag_k, rag_umbral, repo, presupuesto,
               procesar):
    """Una solicitud evaluada. Nunca lanza: un fallo se registra como ronda con error."""
    ident = _identidad(esc["rol"])
    t0 = time.perf_counter()
    try:
        if pipeline == "harness":
            r = mod_harness.ejecutar(host, modelo, esc["texto"], ident, repo, presupuesto,
                                     procesar=lambda *a, **k: procesar(
                                         host, modelo, esc["texto"], ident, repo, None, None, None,
                                         tecnica, host, rag_k, rag_umbral, temperatura))
        else:
            r = procesar(host, modelo, esc["texto"], ident, repo, None, None, None, tecnica, host,
                         rag_k, rag_umbral, temperatura)
        r = r if isinstance(r, dict) else {"veredicto": "ERROR", "error": "respuesta no válida del motor"}
    except Exception as exc:  # noqa: BLE001
        r = {"veredicto": "ERROR", "error": f"campana: {type(exc).__name__}: {exc}",
             "defensa": None, "ejecucion": None}
    ms = int((time.perf_counter() - t0) * 1000)

    defensa = r.get("defensa") or {}
    dg = r.get("diagnostico") or diagnostico.diagnosticar(r)
    decision = defensa.get("decision")
    esperado_ = esc.get("esperado")
    imputable = bool(dg.get("cuenta_para_modelo"))
    return {
        "escenario": esc["id"], "familia": esc["familia"], "rol": esc["rol"], "repeticion": rep,
        "verificable": esc["verificable"], "esperado": esperado_,
        "decision": decision, "veredicto": r.get("veredicto"),
        "acierto": escenarios.acierta(esperado_, decision) if esc["verificable"] else None,
        "acierto_estricto": escenarios.acierta(esperado_, decision, True) if esc["verificable"] else None,
        "fuga": escenarios.hubo_fuga(esperado_, r.get("ejecucion")),
        "diagnostico": dg.get("tipo"), "componente": dg.get("componente"), "imputable": imputable,
        "error": r.get("error"), "ms": ms, "ms_modelo": defensa.get("tiempo_ms"),
        "tokens_entrada": defensa.get("tokens_entrada"), "tokens_salida": defensa.get("tokens"),
        "tecnica": defensa.get("tecnica"), "temperatura": defensa.get("temperatura"),
        "origen_decision": r.get("origen_decision"),
        "rag": defensa.get("rag"),
        "harness": (r.get("harness") or {}).get("consumo"),
        "harness_estado": (r.get("harness") or {}).get("estado"),
    }


def resumir(rondas):
    """Métricas de una campaña, con intervalos de confianza y denominadores explícitos.

    Reglas: la **exactitud oficial** se calcula solo sobre rondas verificables e imputables al modelo. Las
    rondas de infraestructura se publican aparte y nunca se diluyen en el porcentaje."""
    rs = [r for r in (rondas or []) if isinstance(r, dict)]
    verificables = [r for r in rs if r.get("verificable")]
    oficiales = [r for r in verificables if r.get("imputable")]
    infra = [r for r in rs if not r.get("imputable")]

    aciertos = sum(1 for r in oficiales if r.get("acierto"))
    estrictos = sum(1 for r in oficiales if r.get("acierto_estricto"))
    fugas = sum(1 for r in rs if r.get("fuga"))

    por_familia, por_escenario, por_diag = {}, {}, {}
    for r in rs:
        por_diag[r.get("diagnostico")] = por_diag.get(r.get("diagnostico"), 0) + 1
    for r in oficiales:
        for clave, destino in ((r["familia"], por_familia), (r["escenario"], por_escenario)):
            d = destino.setdefault(clave, {"aciertos": 0, "n": 0})
            d["n"] += 1
            d["aciertos"] += int(bool(r.get("acierto")))
    for d in list(por_familia.values()) + list(por_escenario.values()):
        d.update(metricas.wilson(d["aciertos"], d["n"]))

    lat = metricas.resumen_numerico([r.get("ms_modelo") for r in rs])
    rag_ms = metricas.resumen_numerico([(r.get("rag") or {}).get("ms") for r in rs if r.get("rag")])
    return {
        "rondas": len(rs),
        "verificables": len(verificables),
        "exploratorias": len(rs) - len(verificables),
        "imputables": len(oficiales),
        "infraestructura": len(infra),
        "exactitud": metricas.wilson(aciertos, len(oficiales)),
        "exactitud_estricta": metricas.wilson(estrictos, len(oficiales)),
        "fugas": metricas.wilson(fugas, len(rs)),
        "latencia_modelo_ms": lat,
        "latencia_total_ms": metricas.resumen_numerico([r.get("ms") for r in rs]),
        "tokens_entrada": metricas.resumen_numerico([r.get("tokens_entrada") for r in rs]),
        "tokens_salida": metricas.resumen_numerico([r.get("tokens_salida") for r in rs]),
        "recuperacion_ms": rag_ms,
        "por_familia": dict(sorted(por_familia.items())),
        "por_escenario": dict(sorted(por_escenario.items())),
        "por_diagnostico": dict(sorted(por_diag.items(), key=lambda kv: (-kv[1], str(kv[0])))),
        "repetibilidad": _repetibilidad(oficiales),
    }


def _repetibilidad(rondas):
    """¿Da el modelo la misma decisión al repetir el mismo escenario?

    -> {escenarios_con_repeticion, estables, tasa}. `tasa` None si ningún escenario se repitió."""
    por_esc = {}
    for r in rondas:
        por_esc.setdefault(r["escenario"], []).append(r.get("decision"))
    repetidos = {k: v for k, v in por_esc.items() if len(v) > 1}
    estables = sum(1 for v in repetidos.values() if len(set(v)) == 1)
    return {"escenarios_con_repeticion": len(repetidos), "estables": estables,
            "tasa": (estables / len(repetidos)) if repetidos else None}


def comparar_campanas(a, b, semilla=0):
    """Compara la exactitud oficial de dos campañas con bootstrap. -> veredicto de metricas.comparar."""
    ea, eb = a["metricas"]["exactitud"], b["metricas"]["exactitud"]
    nombre = lambda c: f"{c['config'].get('tecnica')}/{c['config'].get('pipeline')}@{c['config'].get('modelo')}"  # noqa: E731
    return metricas.comparar(nombre(a), ea["exitos"], ea["n"], nombre(b), eb["exitos"], eb["n"],
                             semilla=semilla)


def matriz_tecnicas(tecnicas=("base", "fewshot", "rag", "fewshot_rag"), **kw):
    """Ejecuta la MISMA campaña (mismos escenarios, misma semilla, mismas repeticiones) con cada técnica.

    -> {tecnica: campaña} + "comparaciones" contra la técnica de referencia. Es la matriz del encargo."""
    salidas, referencia = {}, kw.pop("referencia", "fewshot")
    for t in tecnicas:
        salidas[t] = ejecutar(tecnica=t, **kw)
    comparaciones = {}
    if referencia in salidas:
        for t, c in salidas.items():
            if t != referencia:
                comparaciones[t] = comparar_campanas(salidas[referencia], c, kw.get("semilla", 0))
    return {"campanas": salidas, "referencia": referencia, "comparaciones": comparaciones}
