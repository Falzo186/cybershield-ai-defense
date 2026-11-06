"""Campañas por lotes, reanudables.

Por qué existe: una campaña con n ≥ 200 por condición son horas de CPU en esta máquina (no hay GPU
utilizable). Sin reanudación, cualquier interrupción —cerrar el servidor, un corte, una Ollama que se
reinicia— tira el trabajo hecho. Con reanudación, una campaña grande se come en trozos.

Cómo funciona, y por qué es seguro reanudar:
  - El plan de una campaña es **determinista**: `campana.plan(modo, familias, repeticiones, semilla, …)`
    siempre devuelve la misma lista en el mismo orden. El índice de un trabajo en esa lista es su nombre.
  - Cada ronda terminada se **añade** a un JSONL propio de la campaña, con su índice. Nunca se reescribe
    nada: un archivo de lote es append-only, como el registro de experimentos.
  - Al reanudar se recalcula el plan y se saltan los índices que ya están en el archivo. Si el plan ha
    cambiado (otro conjunto de escenarios, otra semilla, otras familias), **se rechaza la reanudación** en
    vez de mezclar resultados de dos planes distintos y presentarlos como una serie.

Lo que este módulo NO hace: no ejecuta modelos por su cuenta (se lo pide a `campana`), no reinterpreta
resultados y no rellena rondas que no se ejecutaron.
"""
import hashlib
import json
import time
from pathlib import Path

from . import campana, metricas

DIRECTORIO = Path(__file__).resolve().parents[3] / "data" / "campanas"
VERSION_FORMATO = 1
# Claves de la configuración que determinan el PLAN. Si una cambia, el plan es otro y no se puede reanudar.
CLAVES_PLAN = ("modo", "familias", "repeticiones", "semilla", "solo_verificables")
# Claves que determinan la CONDICIÓN medida. Si una cambia, las rondas no son comparables entre sí.
CLAVES_CONDICION = ("modelo", "tecnica", "pipeline", "temperatura", "rag_k", "rag_umbral")


class ErrorLote(Exception):
    """Se lanza solo cuando reanudar produciría un resultado mezclado. Nunca se traga."""


def _huella(*partes):
    crudo = "\u0000".join(repr(p) for p in partes)
    return hashlib.sha256(crudo.encode("utf-8", "replace")).hexdigest()[:16]


def huella_plan(trabajos):
    """Huella del plan: identidad y repetición de cada trabajo, en orden."""
    return _huella([(e["id"], e["rol"], rep) for e, rep in trabajos])


def nuevo_id(modelo="", modo="estandar"):
    limpio = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in f"{modelo}-{modo}")[:40]
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{limpio}-{_huella(time.time_ns())[:6]}"


def ruta(id_campana, directorio=None):
    return Path(directorio or DIRECTORIO) / f"{id_campana}.jsonl"


# ── Escritura (siempre por añadido) ───────────────────────────────────────────────────────────────────────
def _anadir(ruta_archivo, registro):
    ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
    with ruta_archivo.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")


def crear(config, trabajos, id_campana=None, directorio=None):
    """Abre el archivo de una campaña con su cabecera. -> id. No ejecuta nada."""
    id_campana = id_campana or nuevo_id(config.get("modelo", ""), config.get("modo", "estandar"))
    r = ruta(id_campana, directorio)
    if r.exists():
        raise ErrorLote(f"la campaña {id_campana} ya existe: no se sobrescribe")
    _anadir(r, {"tipo": "cabecera", "version": VERSION_FORMATO, "id": id_campana,
                "creada": time.strftime("%Y-%m-%d %H:%M:%S"), "config": dict(config),
                "planificadas": len(trabajos), "huella_plan": huella_plan(trabajos)})
    return id_campana


# ── Lectura ───────────────────────────────────────────────────────────────────────────────────────────────
def leer(id_campana, directorio=None):
    """-> {id, config, planificadas, huella_plan, rondas, hechos, lotes}. Las líneas ilegibles se cuentan
    aparte en `ilegibles` en vez de desaparecer sin más."""
    r = ruta(id_campana, directorio)
    if not r.exists():
        raise ErrorLote(f"no existe la campaña {id_campana}")
    cabecera, rondas, lotes, ilegibles = None, {}, [], 0
    for linea in r.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            reg = json.loads(linea)
        except ValueError:
            ilegibles += 1
            continue
        tipo = reg.get("tipo")
        if tipo == "cabecera" and cabecera is None:
            cabecera = reg
        elif tipo == "ronda":
            rondas[int(reg["i"])] = reg["ronda"]     # una repetición del mismo índice gana la última
        elif tipo == "lote":
            lotes.append(reg)
    if cabecera is None:
        raise ErrorLote(f"la campaña {id_campana} no tiene cabecera legible")
    return {"id": cabecera["id"], "config": cabecera.get("config") or {},
            "planificadas": int(cabecera.get("planificadas") or 0),
            "huella_plan": cabecera.get("huella_plan"),
            "version": cabecera.get("version"), "creada": cabecera.get("creada"),
            "rondas": [rondas[i] for i in sorted(rondas)], "hechos": set(rondas),
            "lotes": lotes, "ilegibles": ilegibles}


def listar(directorio=None):
    """Campañas por lotes conocidas, de la más reciente a la más antigua. Una ilegible se lista con su
    error en vez de omitirse."""
    d = Path(directorio or DIRECTORIO)
    out = []
    for r in sorted(d.glob("*.jsonl"), reverse=True) if d.exists() else []:
        try:
            e = leer(r.stem, directorio)
            out.append({"id": e["id"], "creada": e["creada"], "config": e["config"],
                        "hechas": len(e["hechos"]), "planificadas": e["planificadas"],
                        "completa": len(e["hechos"]) >= e["planificadas"] and e["planificadas"] > 0,
                        "error": None})
        except Exception as exc:  # noqa: BLE001
            out.append({"id": r.stem, "creada": None, "config": {}, "hechas": 0, "planificadas": 0,
                        "completa": False, "error": f"{type(exc).__name__}: {exc}"})
    return out


def progreso(id_campana, directorio=None):
    e = leer(id_campana, directorio)
    hechas, plan_ = len(e["hechos"]), e["planificadas"]
    return {"id": e["id"], "hechas": hechas, "planificadas": plan_,
            "fraccion": (hechas / plan_) if plan_ else 0.0,
            "completa": hechas >= plan_ and plan_ > 0,
            "pendientes": max(0, plan_ - hechas), "lotes": len(e["lotes"]),
            "config": e["config"], "ilegibles": e["ilegibles"]}


# ── Ejecución por lotes ───────────────────────────────────────────────────────────────────────────────────
def _comprobar_compatible(guardada, actual, claves, que):
    distintas = [k for k in claves if guardada.get(k) != actual.get(k)]
    if distintas:
        raise ErrorLote(f"no se puede reanudar: {que} cambió ({', '.join(distintas)}). "
                        f"Cree una campaña nueva en vez de mezclar dos conjuntos de resultados.")


def ejecutar_lote(id_campana=None, config=None, max_rondas=None, max_segundos=None, repo=None,
                  procesar=None, presupuesto=None, al_avanzar=None, directorio=None, campana_obj=None):
    """Ejecuta el siguiente trozo de una campaña. Crea la campaña si `id_campana` es None.

    `max_rondas` / `max_segundos` acotan **este lote**, no la campaña. Devuelve el progreso y el resumen de
    lo acumulado hasta ahora (no solo de este lote), para que un informe parcial sea un informe de verdad.

    Nunca lanza por un fallo de una ronda: una ronda que falla se guarda como ronda con error. Sí lanza
    `ErrorLote` si reanudar mezclaría planes o condiciones distintas, porque eso no es un fallo recuperable.
    """
    from .. import repositorio                      # import local: evita un ciclo al cargar el paquete
    repo = repo or repositorio.abrir(":memory:")
    config = dict(config or {})
    config.setdefault("modo", "estandar")
    trabajos = campana.plan(config.get("modo", "estandar"), config.get("familias"),
                            config.get("repeticiones"), config.get("semilla", 0), repo,
                            bool(config.get("solo_verificables")))

    if id_campana is None:
        id_campana = crear(config, trabajos, directorio=directorio)
        estado = leer(id_campana, directorio)
    else:
        estado = leer(id_campana, directorio)
        _comprobar_compatible(estado["config"], config, CLAVES_PLAN, "el plan")
        _comprobar_compatible(estado["config"], config, CLAVES_CONDICION, "la condición medida")
        if estado["huella_plan"] != huella_plan(trabajos):
            raise ErrorLote("no se puede reanudar: el conjunto de escenarios cambió desde que se creó la "
                            "campaña. Los resultados antiguos siguen en su archivo; cree una campaña nueva.")

    pendientes = [(i, t) for i, t in enumerate(trabajos) if i not in estado["hechos"]]
    hechas_lote, t0, cortado = 0, time.monotonic(), None
    for i, (esc, rep) in pendientes:
        if max_rondas is not None and hechas_lote >= max_rondas:
            cortado = f"tope de {max_rondas} rondas en este lote"
            break
        if max_segundos is not None and (time.monotonic() - t0) >= max_segundos:
            cortado = f"tope de {max_segundos:g} s en este lote"
            break
        if campana_obj is not None and campana_obj.cancelada:
            cortado = "cancelada"
            break
        ronda = campana._una_ronda(esc, rep, config.get("host", "http://localhost:11434"),
                                   config.get("modelo", ""), config.get("tecnica", "fewshot"),
                                   config.get("pipeline", "directo"), config.get("temperatura"),
                                   config.get("rag_k"), config.get("rag_umbral"), repo, presupuesto,
                                   procesar or _procesar_por_defecto())
        _anadir(ruta(id_campana, directorio), {"tipo": "ronda", "i": i, "ronda": ronda})
        hechas_lote += 1
        if al_avanzar:
            try:
                al_avanzar(progreso(id_campana, directorio), ronda)
            except Exception:  # noqa: BLE001 - un observador roto no tumba el lote
                pass

    _anadir(ruta(id_campana, directorio),
            {"tipo": "lote", "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "rondas": hechas_lote,
             "duracion_s": round(time.monotonic() - t0, 3), "cortado": cortado})
    final = leer(id_campana, directorio)
    prog = progreso(id_campana, directorio)
    return {"id": id_campana, "lote": {"rondas": hechas_lote, "cortado": cortado,
                                       "duracion_s": round(time.monotonic() - t0, 3)},
            "progreso": prog, "config": final["config"],
            "metricas": campana.resumir(final["rondas"]),
            "parcial": not prog["completa"]}


def _procesar_por_defecto():
    from .. import motor
    return motor.procesar_defensa


def resultado(id_campana, directorio=None):
    """Resultado acumulado de una campaña por lotes, con la misma forma que `campana.ejecutar`.

    `parcial` dice si faltan rondas. Un resumen parcial se publica como parcial: no se extrapola."""
    e = leer(id_campana, directorio)
    prog = progreso(id_campana, directorio)
    return {"config": e["config"], "estado": "terminada" if prog["completa"] else "parcial",
            "planificadas": e["planificadas"], "duracion_s": sum(l.get("duracion_s") or 0 for l in e["lotes"]),
            "rondas": e["rondas"], "metricas": campana.resumir(e["rondas"]),
            "parcial": not prog["completa"], "hechas": prog["hechas"], "lotes": len(e["lotes"])}


def comparar(id_a, id_b, directorio=None):
    """Compara dos campañas por lotes con el mismo criterio que `campana.comparar_campanas`: exactitud sobre
    rondas verificables e imputables, con intervalo de confianza y tamaño mínimo de muestra."""
    a, b = resultado(id_a, directorio), resultado(id_b, directorio)
    ma, mb = a["metricas"], b["metricas"]
    ea, eb = ma["exactitud"], mb["exactitud"]
    cmp_ = metricas.comparar(id_a, ea["exitos"], ea["n"], id_b, eb["exitos"], eb["n"])
    return {"a": {"id": id_a, "config": a["config"], "metricas": ma, "parcial": a["parcial"]},
            "b": {"id": id_b, "config": b["config"], "metricas": mb, "parcial": b["parcial"]},
            "comparacion": cmp_,
            "aviso": ("Alguna de las dos campañas está incompleta: la comparación es provisional."
                      if a["parcial"] or b["parcial"] else None)}
