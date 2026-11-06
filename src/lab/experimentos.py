"""Registro central de experimentos: lo que hace que dos corridas se puedan comparar de verdad.

Cada experimento guarda, además del resultado, **todo lo que hace falta para repetirlo**: modelo, técnica,
semilla, temperatura, versión del código, huella de la base de datos y huella del conjunto de evaluación. Sin
eso, comparar dos cifras es comparar dos cosas distintas.

Los resultados se separan por tipo (oficial, exploratorio, seguridad, rendimiento, estrés, regresión) y
**nunca se mezclan**: una campaña con un modelo distinto o un conjunto distinto es otro experimento, no una
continuación del anterior.

Almacén: `data/experimentos.jsonl`, una línea por experimento, solo se añade (nunca se reescribe ni se borra
histórico).
"""
import hashlib
import json
import subprocess
import time
from pathlib import Path

from .evaluacion import campana as mod_campana, escenarios, metricas

RUTA = Path(__file__).resolve().parents[2] / "data" / "experimentos.jsonl"
TIPOS = ("oficial", "exploratorio", "seguridad", "rendimiento", "estres", "regresion")
RAIZ = Path(__file__).resolve().parents[2]


def _huella(texto):
    return hashlib.sha256(str(texto).encode("utf-8", "replace")).hexdigest()[:16]


def version_codigo():
    """Commit corto del repositorio, o None si no se puede saber. Nunca inventa un valor."""
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True,
                           text=True, timeout=5)
        if r.returncode:
            return None
        sucio = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True,
                               text=True, timeout=5).stdout.strip()
        return r.stdout.strip() + ("+sucio" if sucio else "")
    except Exception:  # noqa: BLE001
        return None


def huella_bd(ruta=None):
    """Huella del archivo de base de datos usado. None para BD en memoria (y se dice, no se finge)."""
    ruta = Path(ruta) if ruta else (RAIZ / "data" / "lab.db")
    try:
        if not ruta.exists():
            return None
        return _huella(ruta.stat().st_size) + "-" + hashlib.sha256(ruta.read_bytes()).hexdigest()[:12]
    except Exception:  # noqa: BLE001
        return None


def huella_conjunto(familias=None, repo=None):
    """Huella del conjunto de evaluación: si cambian los escenarios, los resultados ya no son comparables."""
    base = mod_campana.escenarios.conjunto(familias, repo)
    return _huella("\u0000".join(f"{e['id']}|{e['rol']}|{e['texto']}|{e.get('esperado')}" for e in base))


def nuevo_id(tipo):
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{tipo}-{_huella(time.time_ns())[:6]}"


def registrar(resultado, tipo="exploratorio", notas=None, ruta=RUTA, ruta_bd=None, estado_ollama=None):
    """Convierte el resultado de `campana.ejecutar` en un experimento y lo guarda. -> el experimento.

    `tipo` desconocido -> «exploratorio»: nada entra en los resultados oficiales por accidente."""
    tipo = tipo if tipo in TIPOS else "exploratorio"
    cfg = (resultado or {}).get("config") or {}
    exp = {
        "id": nuevo_id(tipo),
        "tipo": tipo,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "notas": notas,
        "modelo": cfg.get("modelo"),
        "host": cfg.get("host"),
        "tecnica": cfg.get("tecnica"),
        "pipeline": cfg.get("pipeline"),
        "modo": cfg.get("modo"),
        "familias": cfg.get("familias"),
        "repeticiones": cfg.get("repeticiones"),
        "semilla": cfg.get("semilla"),
        "temperatura": cfg.get("temperatura"),
        "rag_k": cfg.get("rag_k"),
        "rag_umbral": cfg.get("rag_umbral"),
        "version_codigo": version_codigo(),
        "huella_bd": huella_bd(ruta_bd),
        "huella_conjunto": huella_conjunto(cfg.get("familias")),
        "estado_ollama": estado_ollama,
        "estado_campana": (resultado or {}).get("estado"),
        "planificadas": (resultado or {}).get("planificadas"),
        "duracion_s": (resultado or {}).get("duracion_s"),
        "metricas": (resultado or {}).get("metricas"),
        "rondas": (resultado or {}).get("rondas"),
    }
    guardar(exp, ruta)
    return exp


def guardar(exp, ruta=RUTA):
    """Añade una línea al almacén. Nunca reescribe ni borra lo anterior. -> (ok, error)."""
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(exp, ensure_ascii=False, default=str) + "\n")
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def listar(tipo=None, modelo=None, tecnica=None, ruta=RUTA, con_rondas=False):
    """Experimentos guardados, del más reciente al más antiguo. Una línea corrupta se salta, no rompe."""
    out = []
    try:
        if not Path(ruta).exists():
            return []
        for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            try:
                e = json.loads(linea)
            except ValueError:
                continue
            if tipo and e.get("tipo") != tipo:
                continue
            if modelo and e.get("modelo") != modelo:
                continue
            if tecnica and e.get("tecnica") != tecnica:
                continue
            out.append(e if con_rondas else {k: v for k, v in e.items() if k != "rondas"})
    except Exception:  # noqa: BLE001
        return out
    return sorted(out, key=lambda e: e.get("fecha") or "", reverse=True)


def cargar(id_experimento, ruta=RUTA):
    for e in listar(ruta=ruta, con_rondas=True):
        if e.get("id") == id_experimento:
            return e
    return None


# Campos cuya diferencia invalida una comparación directa: no se comparan peras con manzanas en silencio.
CLAVES_COMPARABILIDAD = ("modelo", "huella_conjunto", "version_codigo", "semilla", "repeticiones",
                         "temperatura", "pipeline", "tecnica", "modo", "familias")


def comparar(a, b, semilla=0):
    """Compara dos experimentos. -> {comparable, diferencias, exactitud, por_familia, resumen}.

    `comparable` es False cuando difieren en algo que no sea la variable que se quería comparar; la
    comparación se devuelve igualmente, pero avisando de qué más cambió."""
    if not a or not b:
        return {"comparable": False, "diferencias": {}, "error": "falta uno de los dos experimentos"}
    difs = {k: (a.get(k), b.get(k)) for k in CLAVES_COMPARABILIDAD if a.get(k) != b.get(k)}
    ma, mb = a.get("metricas") or {}, b.get("metricas") or {}
    ea, eb = ma.get("exactitud") or {}, mb.get("exactitud") or {}
    exactitud = metricas.comparar(a.get("id", "A"), ea.get("exitos") or 0, ea.get("n") or 0,
                                  b.get("id", "B"), eb.get("exitos") or 0, eb.get("n") or 0, semilla=semilla)
    por_familia = {}
    fa, fb = ma.get("por_familia") or {}, mb.get("por_familia") or {}
    for fam in sorted(set(fa) | set(fb)):
        va, vb = (fa.get(fam) or {}).get("valor"), (fb.get(fam) or {}).get("valor")
        if va is None or vb is None:
            por_familia[fam] = {"a": va, "b": vb, "cambio": "sin_dato"}
        elif vb > va:
            por_familia[fam] = {"a": va, "b": vb, "cambio": "mejora", "delta": vb - va}
        elif vb < va:
            por_familia[fam] = {"a": va, "b": vb, "cambio": "empeora", "delta": vb - va}
        else:
            por_familia[fam] = {"a": va, "b": vb, "cambio": "igual", "delta": 0.0}
    cambios = [f for f, v in por_familia.items() if v["cambio"] in ("mejora", "empeora")]
    return {
        "comparable": not difs or set(difs) <= {"tecnica"} or set(difs) <= {"pipeline"}
        or set(difs) <= {"temperatura"} or set(difs) <= {"modelo"},
        "diferencias": difs,
        "exactitud": exactitud,
        "por_familia": por_familia,
        "familias_que_cambian": cambios,
        "latencia": {"a": (ma.get("latencia_modelo_ms") or {}).get("mediana"),
                     "b": (mb.get("latencia_modelo_ms") or {}).get("mediana")},
        "infraestructura": {"a": ma.get("infraestructura"), "b": mb.get("infraestructura")},
        "resumen": exactitud.get("explicacion"),
    }


def resumen_conjunto():
    """Qué contiene hoy el conjunto de evaluación (para la documentación y el panel)."""
    # `fijos` son los escritos a mano; `generados` los que produce la recombinación determinista de la
    # familia C. Se publican por separado para que nadie confunda cobertura escrita con cobertura generada.
    gen = escenarios.generados()
    return {"familias": escenarios.resumen_conjunto(), "huella": huella_conjunto(),
            "total": len(escenarios.FIJOS) + len(gen),
            "fijos": len(escenarios.FIJOS), "generados": len(gen),
            "huella_generados": escenarios.huella_generados()}
