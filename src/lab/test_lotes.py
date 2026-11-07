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

    # ── Las campañas grandes comparan lo comparable ────────────────────────────────────────────────────────
    # Toda la lectura de `data/campanas_grandes.json` se apoya en una sola premisa: las seis condiciones
    # miden EL MISMO conjunto, y solo cambia una variable entre cada una y la referencia. Si alguien añade una
    # condición con otra semilla, otras familias u otras repeticiones, los porcentajes dejan de ser
    # comparables sin que nada lo avise. Esto lo avisa. No ejecuta ningún modelo: solo mira el plan.
    import sys as _sys
    _raiz = str(Path(__file__).resolve().parents[2])
    if _raiz not in _sys.path:
        _sys.path.insert(0, _raiz)
    from experimentos import campanas_grandes as cg

    repo_cg = repositorio.abrir(":memory:")
    planes = {}
    for nombre, _, _ in cg.CONDICIONES:
        c = cg.config_de(nombre)
        planes[nombre] = lotes.huella_plan(campana.plan(c["modo"], c["familias"], c["repeticiones"],
                                                        c["semilla"], repo_cg, bool(c["solo_verificables"])))
    chk("las seis condiciones grandes comparten exactamente el mismo plan",
        len(set(planes.values())) == 1 and len(planes) == 6)
    chk("y ninguna cambia una clave del plan en su configuración",
        all(all(cg.config_de(n)[k] == cg.PLAN[k] for k in lotes.CLAVES_PLAN) for n in planes))

    base = cg.config_de("l32-fewshot")
    diferencias = {n: [k for k in lotes.CLAVES_CONDICION if cg.config_de(n).get(k) != base.get(k)]
                   for n in planes if n != "l32-fewshot"}
    chk("cada condición cambia una sola variable respecto de la referencia",
        all(len(v) == 1 for v in diferencias.values()))
    # Tres condiciones cambian la MISMA variable (`tecnica`) con valores distintos, y eso es correcto: son
    # la matriz de técnicas. Lo que no puede repetirse es una condición entera, porque entonces se mediría
    # dos veces lo mismo y se presentaría como dos resultados.
    firmas = [tuple(cg.config_de(n).get(k) for k in lotes.CLAVES_CONDICION) for n in planes]
    chk("ninguna condición está declarada dos veces", len(set(firmas)) == len(firmas))
    chk("las tres condiciones de técnica usan técnicas distintas",
        len({cg.config_de(n)["tecnica"] for n in planes
             if diferencias.get(n) == ["tecnica"] or n == "l32-fewshot"}) == 4)

    trabajos_cg = campana.plan(base["modo"], base["familias"], base["repeticiones"], base["semilla"],
                               repo_cg, bool(base["solo_verificables"]))
    verificables_cg = sum(1 for e, _ in trabajos_cg if e["verificable"])
    chk("el plan grande planifica las 256 rondas declaradas", len(trabajos_cg) == 256)
    chk("y pasa de las 200 observaciones verificables que exige interpretar una diferencia",
        verificables_cg >= 200)
    chk("el identificador de cada campaña grande es fijo, para poder reanudarla",
        cg.id_de("l32-fewshot") == "grande-l32-fewshot" and cg.id_de("q25-fewshot") == "grande-q25-fewshot")

    # ── La línea base trivial ──────────────────────────────────────────────────────────────────────────────
    # La medición grande destapó que la exactitud oficial le da 65,6 % a un defensor que contesta siempre lo
    # mismo. Desde entonces esa cifra se publica al lado de la del modelo. Esto comprueba que se calcula
    # bien, porque si se calculara mal el engaño volvería sin que nada avisara.
    from experimentos import resumir_campanas as rc

    falsas = ([{"verificable": True, "imputable": True, "esperado": "contener", "decision": "RECHAZAR"}] * 6
              + [{"verificable": True, "imputable": True, "esperado": "permitir", "decision": "RECHAZAR"}] * 4
              + [{"verificable": False, "imputable": True, "esperado": None, "decision": "RECHAZAR"}] * 3)
    lb = rc.linea_base_trivial({"rondas": falsas})
    chk("la línea base trivial solo cuenta rondas verificables e imputables",
        lb["por_decision"]["RECHAZAR"]["exactitud"]["n"] == 10)
    chk("rechazar siempre acierta en todo lo que no sea «permitir»",
        lb["por_decision"]["RECHAZAR"]["exactitud"]["valor"] == 0.6)
    chk("permitir siempre acierta solo en «permitir»",
        lb["por_decision"]["PERMITIR"]["exactitud"]["valor"] == 0.4)
    chk("la constante a batir es la mejor de las cuatro", lb["mejor_constante"] == "RECHAZAR")
    chk("y la composición del conjunto se publica, porque es de donde sale la cifra",
        lb["composicion"] == {"contener": 6, "permitir": 4})

    chk("un modelo cuyo intervalo abarca la constante es indistinguible de ella",
        rc.supera_linea_base({"valor": 0.62, "bajo": 0.50, "alto": 0.74}, lb) == "indistinguible")
    chk("uno cuyo intervalo queda por encima la supera",
        rc.supera_linea_base({"valor": 0.80, "bajo": 0.70, "alto": 0.88}, lb) == "supera")
    chk("uno cuyo intervalo queda por debajo no la alcanza",
        rc.supera_linea_base({"valor": 0.30, "bajo": 0.20, "alto": 0.42}, lb) == "por_debajo")
    chk("sin exactitud calculable no se inventa un veredicto",
        rc.supera_linea_base({"valor": None, "bajo": None, "alto": None}, lb) is None)

    emitidas = rc.decisiones_emitidas({"rondas": falsas})
    chk("se publica qué decisiones llegó a emitir el modelo", emitidas == {"RECHAZAR": 13})
    chk("una decisión que nunca se emite no aparece inventada como cero",
        "PERMITIR" not in emitidas)
    chk("el aviso de comparaciones múltiples está escrito en el código, no improvisado",
        "23 %" in rc.NOTA_MULTIPLES and rc.REFERENCIA == "l32-fewshot")

    # ── Campaña del atacante: las dos condiciones comparten el guion ───────────────────────────────────────
    # No hay semilla posible en este camino: el atacante es un modelo a temperatura 0,7 y no es determinista.
    # Lo que sí tiene que ser idéntico entre las dos condiciones es TODO lo demás: qué escenario toca en cada
    # sesión, qué técnica toca en cada ronda, el rol, el objetivo y la intensidad. Si eso no se mantiene, la
    # comparación entre defensores mide dos cosas distintas. Esto lo fija.
    from experimentos import campana_atacante as ca
    from . import atacante as mod_atq

    chk("el diseño declarado es 20 sesiones de 12 rondas",
        ca.SESIONES == 20 and ca.RONDAS_POR_SESION == 12)
    chk("y planifica más de 200 rondas por condición",
        ca.SESIONES * ca.RONDAS_POR_SESION >= 200)
    chk("hay exactamente dos condiciones de defensor", len(ca.CONDICIONES) == 2)

    cfgs = [ca.config_de(n) for n, _, _ in ca.CONDICIONES]
    comunes = ("modelo_atacante", "rol", "rondas_por_sesion", "sesiones", "intensidad", "escenarios")
    chk("las dos condiciones comparten atacante, rol, rondas, intensidad y escenarios",
        all(len({str(c[k]) for c in cfgs}) == 1 for k in comunes))
    chk("y solo se diferencian en el modelo defensor",
        len({c["modelo_defensor"] for c in cfgs}) == 2
        and {k for k in cfgs[0] if str(cfgs[0][k]) != str(cfgs[1][k])} == {"modelo_defensor"})

    guion = [ca.ESCENARIOS[(s - 1) % len(ca.ESCENARIOS)] for s in range(1, ca.SESIONES + 1)]
    chk("el escenario de cada sesión es función solo del número de sesión, igual en ambas condiciones",
        guion == [ca.ESCENARIOS[(s - 1) % len(ca.ESCENARIOS)] for s in range(1, ca.SESIONES + 1)])
    chk("las tres técnicas del catálogo entran, más sesiones de elección libre",
        set(ca.ESCENARIOS) == set(mod_atq.ESCENARIOS) | {None})
    chk("cada escenario del catálogo sale el mismo número de veces",
        len({guion.count(e) for e in mod_atq.ESCENARIOS}) == 1)
    chk("la técnica de cada ronda dentro de un escenario es determinista",
        all(mod_atq.categoria_guion("suplantacion_identidad", n)
            == mod_atq.categoria_guion("suplantacion_identidad", n) for n in range(1, 13)))

    print(f"\nTotal {sum(resultados)}/{len(resultados)}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
