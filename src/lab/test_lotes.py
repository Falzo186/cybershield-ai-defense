"""Pruebas de las campañas por lotes reanudables. Ejecutar: python -m src.lab.test_lotes

Sin Ollama ni red: el defensor se inyecta. Cada prueba usa un directorio temporal propio, así que nunca
toca `data/campanas/`.

Lo que se demuestra:
  - una campaña interrumpida se reanuda sin repetir trabajo y sin perder lo hecho;
  - reanudar con otro plan o otra condición se RECHAZA en vez de mezclar resultados;
  - un resumen incompleto se publica como incompleto;
  - el archivo es append-only: nada se reescribe.
"""
import json
import shutil
import tempfile
from pathlib import Path

from .evaluacion import campana, lotes

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def defensor_falso(decision="RECHAZAR", veredicto="DEFENSA_EXITOSA", error=None):
    def procesar(host, modelo, texto, ident, repo=None, riesgo=None, resumen=None, equipo=None, *a, **k):
        return {"defensa": {"decision": decision, "riesgo": 10, "motivo": "m", "politica": None,
                            "herramienta": None, "parametros": None, "parse_ok": True, "tiempo_ms": 1,
                            "tokens": 2, "tokens_entrada": 3, "intentos": 1},
                "ejecucion": None, "veredicto": veredicto, "error": error, "nota": None, "ia_fallo": False,
                "nivel_fuga": "NINGUNA", "circuito_sesion": False, "origen_decision": "ia",
                "diagnostico": None}
    return procesar


def main():
    from . import repositorio
    repo = repositorio.abrir(":memory:")
    d = Path(tempfile.mkdtemp(prefix="lotes_"))
    cfg = {"modo": "rapido", "modelo": "m-prueba", "tecnica": "fewshot", "semilla": 1}
    proc = defensor_falso()

    try:
        # ── Crear y ejecutar un primer lote ────────────────────────────────────────────────────────────────
        r1 = lotes.ejecutar_lote(None, cfg, max_rondas=4, repo=repo, procesar=proc, directorio=d)
        total = r1["progreso"]["planificadas"]
        chk("el plan tiene trabajos", total > 4)
        chk("el primer lote hace exactamente el tope pedido", r1["lote"]["rondas"] == 4)
        chk("y dice por qué se cortó", "tope de 4 rondas" in (r1["lote"]["cortado"] or ""))
        chk("el resultado se declara parcial", r1["parcial"] is True)
        chk("el progreso es real, no una barra inventada",
            r1["progreso"]["hechas"] == 4 and r1["progreso"]["pendientes"] == total - 4)
        chk("las métricas parciales cuentan solo lo ejecutado", r1["metricas"]["rondas"] == 4)

        # ── Reanudar ───────────────────────────────────────────────────────────────────────────────────────
        r2 = lotes.ejecutar_lote(r1["id"], cfg, max_rondas=3, repo=repo, procesar=proc, directorio=d)
        chk("reanudar continúa donde quedó", r2["progreso"]["hechas"] == 7)
        chk("sin repetir trabajo", r2["lote"]["rondas"] == 3)
        chk("sigue siendo parcial", r2["parcial"] is True)
        r3 = lotes.ejecutar_lote(r1["id"], cfg, repo=repo, procesar=proc, directorio=d)
        chk("sin tope, el último lote termina la campaña", r3["progreso"]["completa"] is True)
        chk("y el total coincide con lo planificado", r3["progreso"]["hechas"] == total)
        chk("ya no es parcial", r3["parcial"] is False)
        r4 = lotes.ejecutar_lote(r1["id"], cfg, repo=repo, procesar=proc, directorio=d)
        chk("reanudar una campaña completa no ejecuta nada", r4["lote"]["rondas"] == 0)
        chk("y no duplica rondas", r4["progreso"]["hechas"] == total)

        # ── Cada ronda del plan aparece una sola vez ───────────────────────────────────────────────────────
        e = lotes.leer(r1["id"], d)
        chk("no hay índices repetidos", len(e["hechos"]) == len(e["rondas"]) == total)
        chk("los índices cubren todo el plan", e["hechos"] == set(range(total)))
        chk("el resumen final cuenta todas las rondas", lotes.resultado(r1["id"], d)["metricas"]["rondas"] == total)
        chk("y se declara terminada", lotes.resultado(r1["id"], d)["estado"] == "terminada")

        # ── Append-only: la cabecera sigue siendo la primera línea y nada se reescribió ─────────────────────
        lineas = [json.loads(x) for x in lotes.ruta(r1["id"], d).read_text(encoding="utf-8").splitlines() if x.strip()]
        chk("la cabecera es la primera línea", lineas[0]["tipo"] == "cabecera")
        chk("hay una sola cabecera", sum(1 for x in lineas if x["tipo"] == "cabecera") == 1)
        chk("hay un registro de lote por cada lote ejecutado",
            sum(1 for x in lineas if x["tipo"] == "lote") == 4)
        chk("la cabecera guarda la huella del plan", bool(lineas[0]["huella_plan"]))
        chk("y el número de trabajos planificados", lineas[0]["planificadas"] == total)

        # ── Reanudar con otro plan o otra condición se rechaza ─────────────────────────────────────────────
        for cambio, que in (({"semilla": 99}, "el plan"), ({"modo": "intensivo"}, "el plan"),
                            ({"modelo": "otro"}, "la condición medida"),
                            ({"tecnica": "rag"}, "la condición medida")):
            try:
                lotes.ejecutar_lote(r1["id"], {**cfg, **cambio}, repo=repo, procesar=proc, directorio=d)
                chk(f"debía rechazar el cambio de {list(cambio)[0]}", False)
            except lotes.ErrorLote as exc:
                chk(f"rechaza reanudar con otro {list(cambio)[0]} ({que})", que in str(exc))

        # ── Campaña inexistente y archivo corrupto ─────────────────────────────────────────────────────────
        try:
            lotes.leer("no-existe", d)
            chk("debía lanzar con una campaña inexistente", False)
        except lotes.ErrorLote as exc:
            chk("una campaña inexistente lanza ErrorLote", "no existe" in str(exc))
        try:
            lotes.crear(cfg, [], id_campana=r1["id"], directorio=d)
            chk("debía negarse a sobrescribir", False)
        except lotes.ErrorLote as exc:
            chk("no sobrescribe una campaña existente", "no se sobrescribe" in str(exc))

        malo = lotes.ruta("corrupta", d)
        malo.parent.mkdir(parents=True, exist_ok=True)
        malo.write_text('{"tipo":"cabecera","id":"corrupta","planificadas":2,"config":{}}\n{esto no es json\n',
                        encoding="utf-8")
        e = lotes.leer("corrupta", d)
        chk("una línea ilegible se cuenta, no se esconde", e["ilegibles"] == 1)
        chk("y la campaña sigue siendo legible", e["id"] == "corrupta" and e["rondas"] == [])
        sin_cab = lotes.ruta("sincabecera", d)
        sin_cab.write_text('{"tipo":"ronda","i":0,"ronda":{}}\n', encoding="utf-8")
        try:
            lotes.leer("sincabecera", d)
            chk("debía lanzar sin cabecera", False)
        except lotes.ErrorLote as exc:
            chk("sin cabecera legible, la campaña se rechaza", "cabecera" in str(exc))

        # ── Listado ────────────────────────────────────────────────────────────────────────────────────────
        lista = lotes.listar(d)
        ids = {x["id"] for x in lista}
        chk("el listado incluye la campaña completa", r1["id"] in ids)
        chk("y marca su estado", next(x for x in lista if x["id"] == r1["id"])["completa"] is True)
        chk("una campaña ilegible se lista con su error",
            next(x for x in lista if x["id"] == "sincabecera")["error"] is not None)
        chk("el listado de un directorio que no existe es vacío, no un error",
            lotes.listar(d / "nada") == [])

        # ── Una ronda que falla se guarda como ronda con error ─────────────────────────────────────────────
        def revienta(*a, **k):
            raise RuntimeError("Ollama caído")
        r = lotes.ejecutar_lote(None, {**cfg, "modelo": "roto"}, max_rondas=2, repo=repo,
                                procesar=revienta, directorio=d)
        chk("un fallo del modelo no tumba el lote", r["lote"]["rondas"] == 2)
        rondas = lotes.leer(r["id"], d)["rondas"]
        chk("la ronda queda con su error", all(x["error"] for x in rondas))
        chk("y como no imputable al modelo", all(x["imputable"] is False for x in rondas))
        m = lotes.resultado(r["id"], d)["metricas"]
        chk("la exactitud oficial no se calcula sin rondas imputables",
            m["exactitud"]["valor"] is None and m["exactitud"]["n"] == 0)
        chk("y las rondas se contabilizan como infraestructura", m["infraestructura"] == 2)

        # ── Comparación ────────────────────────────────────────────────────────────────────────────────────
        otra = lotes.ejecutar_lote(None, {**cfg, "modelo": "m-dos"}, repo=repo,
                                   procesar=defensor_falso(decision="PERMITIR"), directorio=d)
        cmp_ = lotes.comparar(r1["id"], otra["id"], d)
        chk("comparar dos campañas da un veredicto estadístico", cmp_["comparacion"]["veredicto"] in
            ("mejora", "empeora", "sin_diferencia_concluyente", "muestra_insuficiente"))
        chk("y nombra las dos campañas", (cmp_["a"]["id"], cmp_["b"]["id"]) == (r1["id"], otra["id"]))
        chk("sin campañas parciales no hay aviso", cmp_["aviso"] is None)
        parcial = lotes.ejecutar_lote(None, {**cfg, "modelo": "m-tres"}, max_rondas=1, repo=repo,
                                      procesar=proc, directorio=d)
        chk("comparar con una campaña incompleta avisa",
            lotes.comparar(r1["id"], parcial["id"], d)["aviso"] is not None)

        # ── Determinismo del plan ──────────────────────────────────────────────────────────────────────────
        t1 = campana.plan("rapido", None, None, 1, repo, False)
        t2 = campana.plan("rapido", None, None, 1, repo, False)
        chk("el plan es determinista con la misma semilla",
            lotes.huella_plan(t1) == lotes.huella_plan(t2))
        chk("y distinto con otra semilla",
            lotes.huella_plan(t1) != lotes.huella_plan(campana.plan("rapido", None, None, 2, repo, False)))
        chk("la huella del plan no depende del orden de lectura del disco",
            lotes.huella_plan(t1) == lotes.leer(r1["id"], d)["huella_plan"])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    chk("DIRECTORIO por defecto apunta a data/campanas",
        lotes.DIRECTORIO.name == "campanas" and lotes.DIRECTORIO.parent.name == "data")

    print(f"\nTotal {sum(resultados)}/{len(resultados)}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
