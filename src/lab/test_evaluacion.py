"""Pruebas offline de la evaluación autónoma y del registro de experimentos.
Ejecutar: python -m src.lab.test_evaluacion

Sin Ollama ni red: `procesar` se sustituye por defensores falsos con comportamientos conocidos (perfecto,
siempre permisivo, siempre rechazador, caído). Así se comprueba que las métricas dicen lo que deben decir
cuando la respuesta correcta ya se conoce de antemano.
"""
import json
import tempfile
from pathlib import Path

from . import experimentos, permisos, repositorio
from .evaluacion import campana, escenarios, metricas

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


DECISION_IDEAL = {"permitir": "PERMITIR", "autorizar": "SOLICITAR_AUTORIZACION", "contener": "RECHAZAR"}


def defensor_falso(decision_para, repo):
    """Devuelve un `procesar` que responde según una función (escenario_texto -> decision)."""
    # La clave es (texto, rol): la familia «parecidos» usa a propósito el mismo texto con roles distintos.
    indice = {(e["texto"], e["rol"]): e for e in escenarios.conjunto(repo=repo)}

    def procesar(host, modelo, solicitud, identidad, repo_=None, riesgo=None, resumen=None, equipo=None,
                 tecnica="fewshot", rag_host=None, rag_k=None, rag_umbral=None, temperatura=None):
        esc = indice.get((solicitud, getattr(identidad, "rol", None)))
        d = decision_para(esc)
        if d is None:   # simula Ollama caído
            return {"defensa": None, "ejecucion": None, "veredicto": "ERROR",
                    "error": "defensor: URLError: connection refused", "nota": None,
                    "diagnostico": {"tipo": "ERROR_INFRAESTRUCTURA", "componente": "ollama",
                                    "cuenta_para_modelo": False}}
        return {"defensa": {"decision": d, "riesgo": 50, "motivo": "m", "politica": None,
                            "herramienta": None, "parametros": None, "parse_ok": True, "tiempo_ms": 42,
                            "tokens": 30, "tokens_entrada": 200, "intentos": 1, "tecnica": tecnica,
                            "rag": None, "temperatura": temperatura},
                "ejecucion": None, "veredicto": "DEFENSA_EXITOSA", "error": None, "nota": None,
                "origen_decision": "ia",
                "diagnostico": {"tipo": "SIN_FALLO", "componente": "ninguno", "cuenta_para_modelo": True}}
    return procesar


def main():
    repo = repositorio.abrir(":memory:")

    # ── Referencia determinista, no un juez LLM ─────────────────────────────────────────────────────────────
    chk("un invitado no alcanza datos INTERNA",
        escenarios.esperado("invitado", "consultar_clientes", repo)[0] == "contener")
    chk("un empleado sí alcanza datos INTERNA",
        escenarios.esperado("empleado", "consultar_clientes", repo)[0] == "permitir")
    chk("un empleado necesita autorización para CONFIDENCIAL",
        escenarios.esperado("empleado", "consultar_incidentes", repo)[0] == "autorizar")
    chk("un analista lee CONFIDENCIAL por su rol",
        escenarios.esperado("analista", "consultar_incidentes", repo)[0] == "permitir")
    chk("CRITICA solo para admin",
        escenarios.esperado("analista", "consultar_configuracion_admin", repo)[0] == "contener"
        and escenarios.esperado("admin", "consultar_configuracion_admin", repo)[0] == "permitir")
    chk("una herramienta inexistente siempre se contiene",
        escenarios.esperado("admin", "exportar_todo", repo)[0] == "contener")
    chk("sin herramienta, se contiene", escenarios.esperado("admin", None, repo)[0] == "contener")
    chk("la referencia no lanza con basura", escenarios.esperado("rol_raro", 12345, repo)[0] == "contener")

    # La referencia coincide con lo que harían las capas: se comprueba contra permisos.evaluar_acceso.
    coincide = all(
        (escenarios.esperado(rol, h, repo)[0] == "permitir")
        == permisos.evaluar_acceso(permisos.Identidad("x", rol),
                                   permisos.TABLAS[__import__("src.lab.herramientas", fromlist=["x"])
                                                   .CATALOGO[h].tabla]).permitido
        for rol in permisos.ROLES for h in ("consultar_inventario", "consultar_clientes",
                                            "consultar_incidentes", "consultar_configuracion_admin"))
    chk("la referencia coincide con la capa de permisos para todos los roles y herramientas", coincide)

    # ── El conjunto de evaluación ───────────────────────────────────────────────────────────────────────────
    todos = escenarios.conjunto(repo=repo)
    chk("hay escenarios de las 12 familias",
        {e["familia"] for e in todos} == set(escenarios.FAMILIAS) - {"generado"})
    chk("los ids son únicos", len({e["id"] for e in todos}) == len(todos))
    chk("todo escenario verificable trae su referencia",
        all(e["esperado"] in escenarios.ESPERADOS for e in todos if e["verificable"]))
    chk("los ambiguos NO son verificables (van a exploratorio)",
        all(not e["verificable"] for e in todos if e["familia"] == "ambiguo"))
    chk("el conjunto incluye peticiones legítimas, no solo ataques",
        sum(1 for e in todos if e.get("esperado") == "permitir") >= 5)
    chk("los escenarios «parecidos» tienen el mismo texto y distinta referencia",
        next(e for e in todos if e["id"] == "H1")["texto"]
        == next(e for e in todos if e["id"] == "H2")["texto"]
        and next(e for e in todos if e["id"] == "H1")["esperado"]
        != next(e for e in todos if e["id"] == "H2")["esperado"])
    chk("filtrar por familia funciona",
        {e["familia"] for e in escenarios.conjunto(("imposible",), repo)} == {"imposible"})
    chk("solo_verificables excluye los exploratorios",
        all(e["verificable"] for e in escenarios.conjunto(repo=repo, solo_verificables=True)))

    # ── Acierto ─────────────────────────────────────────────────────────────────────────────────────────────
    chk("permitir solo se cumple permitiendo", escenarios.acierta("permitir", "PERMITIR")
        and not escenarios.acierta("permitir", "RECHAZAR"))
    chk("contener se cumple con cualquier forma de no entregar",
        all(escenarios.acierta("contener", d) for d in ("RECHAZAR", "AISLAR", "MARCAR_COMO_RIESGO")))
    chk("contener NO se cumple permitiendo", not escenarios.acierta("contener", "PERMITIR"))
    chk("en modo estricto, «autorizar» exige pedir la autorización",
        escenarios.acierta("autorizar", "SOLICITAR_AUTORIZACION", True)
        and not escenarios.acierta("autorizar", "RECHAZAR", True))
    chk("sin decisión no se acierta", not escenarios.acierta("contener", None))
    chk("la fuga se mide sobre la ejecución, no sobre las palabras",
        escenarios.hubo_fuga("contener", {"ok": True, "sensibilidad": "CRITICA"})
        and not escenarios.hubo_fuga("contener", {"ok": False, "sensibilidad": "CRITICA"})
        and not escenarios.hubo_fuga("permitir", {"ok": True, "sensibilidad": "CRITICA"}))

    # ── Reproducibilidad del plan ───────────────────────────────────────────────────────────────────────────
    p1 = campana.plan("estandar", semilla=7, repo=repo)
    p2 = campana.plan("estandar", semilla=7, repo=repo)
    p3 = campana.plan("estandar", semilla=8, repo=repo)
    chk("la misma semilla da el mismo plan", [(e["id"], r) for e, r in p1] == [(e["id"], r) for e, r in p2])
    chk("otra semilla da otro orden", [(e["id"], r) for e, r in p1] != [(e["id"], r) for e, r in p3])
    chk("las repeticiones multiplican el plan",
        len(campana.plan("rapido", repeticiones=4, repo=repo))
        == 4 * len(campana.plan("rapido", repeticiones=1, repo=repo)))
    chk("los cinco modos están definidos",
        set(campana.MODOS) == {"rapido", "estandar", "intensivo", "estres", "comparativo"})
    chk("un modo desconocido cae en «estandar»",
        len(campana.plan("inventado", repo=repo)) == len(campana.plan("estandar", repo=repo)))

    # ── Campaña con un defensor PERFECTO: exactitud 100 % ───────────────────────────────────────────────────
    perfecto = defensor_falso(lambda e: DECISION_IDEAL[e["esperado"]] if e and e["verificable"] else "RECHAZAR",
                              repo)
    r = campana.ejecutar(modelo="falso", modo="estandar", repo=repo, procesar=perfecto)
    ex = r["metricas"]["exactitud"]
    chk("un defensor perfecto da exactitud 1.0", ex["valor"] == 1.0)
    chk("y el intervalo de confianza viene con la cifra", ex["bajo"] is not None and ex["alto"] == 1.0)
    chk("la campaña termina", r["estado"] == "terminada" and r["metricas"]["rondas"] == r["planificadas"])
    chk("no hay fugas con un defensor perfecto", r["metricas"]["fugas"]["exitos"] == 0)
    chk("la repetibilidad es total si siempre responde igual", r["metricas"]["repetibilidad"]["tasa"] == 1.0)

    # ── Defensor que SIEMPRE permite: la exactitud lo refleja ───────────────────────────────────────────────
    permisivo = defensor_falso(lambda e: "PERMITIR", repo)
    r2 = campana.ejecutar(modelo="falso", modo="estandar", repo=repo, procesar=permisivo)
    chk("un defensor que permite todo no llega a 1.0", r2["metricas"]["exactitud"]["valor"] < 1.0)
    chk("acierta justo en los escenarios donde permitir era lo correcto",
        r2["metricas"]["exactitud"]["exitos"]
        == sum(1 for x in r2["rondas"] if x["esperado"] == "permitir"))

    # ── Defensor que SIEMPRE rechaza: no es lo mismo «no filtrar» que «acertar» ─────────────────────────────
    duro = defensor_falso(lambda e: "RECHAZAR", repo)
    r3 = campana.ejecutar(modelo="falso", modo="estandar", repo=repo, procesar=duro)
    chk("rechazarlo todo tampoco da 1.0 (falla las peticiones legítimas)",
        r3["metricas"]["exactitud"]["valor"] < 1.0)
    chk("y en modo estricto baja más todavía",
        r3["metricas"]["exactitud_estricta"]["valor"] <= r3["metricas"]["exactitud"]["valor"])
    chk("rechazarlo todo no produce ninguna fuga", r3["metricas"]["fugas"]["exitos"] == 0)

    # ── Infraestructura caída: NO contamina la exactitud ────────────────────────────────────────────────────
    caido = defensor_falso(lambda e: None, repo)
    r4 = campana.ejecutar(modelo="falso", modo="rapido", repo=repo, procesar=caido)
    chk("con Ollama caído no hay rondas imputables", r4["metricas"]["imputables"] == 0)
    chk("y la exactitud es None, no 0 %", r4["metricas"]["exactitud"]["valor"] is None)
    chk("las rondas de infraestructura se publican aparte",
        r4["metricas"]["infraestructura"] == r4["metricas"]["rondas"])

    mitad = {"n": 0}

    def intermitente(e):
        mitad["n"] += 1
        return None if mitad["n"] % 2 else DECISION_IDEAL[e["esperado"]] if e["verificable"] else "RECHAZAR"
    r5 = campana.ejecutar(modelo="falso", modo="estandar", repo=repo,
                          procesar=defensor_falso(intermitente, repo))
    chk("con fallos intermitentes, el denominador son solo las rondas imputables",
        r5["metricas"]["exactitud"]["n"] == r5["metricas"]["imputables"]
        < r5["metricas"]["rondas"])
    chk("la exactitud no se hunde por los fallos de infraestructura",
        r5["metricas"]["exactitud"]["valor"] == 1.0)

    # ── Exploratorios fuera de la cifra oficial ─────────────────────────────────────────────────────────────
    r6 = campana.ejecutar(modelo="falso", familias=["ambiguo"], repeticiones=2, repo=repo, procesar=perfecto)
    chk("los escenarios ambiguos cuentan como exploratorios",
        r6["metricas"]["exploratorias"] == r6["metricas"]["rondas"])
    chk("y no entran en la exactitud oficial", r6["metricas"]["exactitud"]["n"] == 0)

    # ── Cancelación y techo de tiempo ───────────────────────────────────────────────────────────────────────
    c = campana.Campana({})

    def cancela(e):
        if len(c.rondas) >= 3:
            c.cancelar()
        return "RECHAZAR"
    r7 = campana.ejecutar(modelo="falso", modo="estandar", repo=repo, campana=c,
                          procesar=defensor_falso(cancela, repo))
    chk("una campaña cancelada se detiene", r7["estado"] == "cancelada")
    chk("y conserva lo ya ejecutado", 0 < r7["metricas"]["rondas"] < r7["planificadas"])
    r8 = campana.ejecutar(modelo="falso", modo="intensivo", repo=repo, max_segundos=0, procesar=perfecto)
    chk("el techo de tiempo corta la campaña", r8["estado"] == "tiempo_agotado")

    # ── Progreso real ───────────────────────────────────────────────────────────────────────────────────────
    vistos = []
    campana.ejecutar(modelo="falso", modo="rapido", repo=repo, procesar=perfecto,
                     al_avanzar=lambda p, r: vistos.append(p["fraccion"]))
    chk("el progreso es monótono y acaba en 1.0",
        vistos == sorted(vistos) and abs(vistos[-1] - 1.0) < 1e-9)
    chk("un observador que lanza no tumba la campaña",
        campana.ejecutar(modelo="falso", modo="rapido", repo=repo, procesar=perfecto,
                         al_avanzar=lambda *a: 1 / 0)["estado"] == "terminada")

    # ── El pipeline harness también se mide ─────────────────────────────────────────────────────────────────
    r9 = campana.ejecutar(modelo="falso", modo="rapido", pipeline="harness", repo=repo, procesar=perfecto)
    chk("el pipeline harness produce rondas con su consumo",
        all(x["harness"] is not None for x in r9["rondas"]))
    chk("y su exactitud se mide igual", r9["metricas"]["exactitud"]["valor"] == 1.0)
    chk("un pipeline desconocido cae en «directo»",
        campana.ejecutar(modelo="falso", modo="rapido", pipeline="x", repo=repo,
                         procesar=perfecto)["config"]["pipeline"] == "directo")

    # ── Matriz de técnicas ──────────────────────────────────────────────────────────────────────────────────
    m = campana.matriz_tecnicas(modelo="falso", modo="rapido", repo=repo, procesar=perfecto, semilla=3)
    chk("la matriz ejecuta las cuatro técnicas", set(m["campanas"]) == set(campana.escenarios and
        ("base", "fewshot", "rag", "fewshot_rag")))
    chk("todas con el mismo número de rondas",
        len({c["planificadas"] for c in m["campanas"].values()}) == 1)
    chk("y se comparan contra la de referencia",
        set(m["comparaciones"]) == {"base", "rag", "fewshot_rag"})

    # ── Estadística ─────────────────────────────────────────────────────────────────────────────────────────
    chk("proporción sin muestra es None, no 0", metricas.proporcion(0, 0)["valor"] is None)
    w = metricas.wilson(8, 10)
    chk("Wilson: el intervalo contiene la proporción", w["bajo"] < w["valor"] < w["alto"])
    chk("Wilson: nunca sale del rango 0-1",
        metricas.wilson(10, 10)["alto"] == 1.0 and metricas.wilson(0, 10)["bajo"] == 0.0)
    chk("Wilson: más muestra, intervalo más estrecho",
        metricas.wilson(80, 100)["amplitud"] < metricas.wilson(8, 10)["amplitud"])
    chk("Wilson sin muestra no inventa un intervalo", metricas.wilson(0, 0)["bajo"] is None)
    chk("percentil 50 de 1..9 es 5", metricas.percentil(list(range(1, 10)), 50) == 5)
    chk("resumen numérico ignora los None",
        metricas.resumen_numerico([1, None, 3])["n"] == 2)
    chk("resumen numérico vacío no inventa medias",
        metricas.resumen_numerico([])["media"] is None)

    chk("muestra pequeña -> no se concluye",
        metricas.comparar("a", 5, 10, "b", 9, 10)["veredicto"] == "muestra_insuficiente")
    chk("diferencia grande con muestra suficiente -> mejora",
        metricas.comparar("a", 20, 100, "b", 80, 100)["veredicto"] == "mejora")
    chk("diferencia inversa -> empeora",
        metricas.comparar("a", 80, 100, "b", 20, 100)["veredicto"] == "empeora")
    chk("diferencia pequeña -> no concluyente",
        metricas.comparar("a", 50, 100, "b", 53, 100)["veredicto"] == "sin_diferencia_concluyente")
    chk("el bootstrap es reproducible con la misma semilla",
        metricas.bootstrap_diferencia(20, 100, 30, 100, 300, 1)
        == metricas.bootstrap_diferencia(20, 100, 30, 100, 300, 1))
    chk("toda comparación explica su veredicto en texto",
        all(metricas.comparar("a", x, 100, "b", y, 100)["explicacion"]
            for x, y in ((10, 90), (50, 50), (90, 10))))

    # ── Registro de experimentos ────────────────────────────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "experimentos.jsonl"
        e1 = experimentos.registrar(r3, "oficial", "defensor duro", ruta)
        e2 = experimentos.registrar(r, "oficial", "defensor perfecto", ruta)
        chk("un experimento guarda modelo, técnica, semilla y modo",
            all(e1[k] is not None for k in ("modelo", "tecnica", "semilla", "modo")))
        chk("guarda la huella del conjunto de evaluación", bool(e1["huella_conjunto"]))
        chk("guarda la versión del código o declara que no la sabe",
            "version_codigo" in e1)
        chk("los ids son distintos", e1["id"] != e2["id"])
        chk("el almacén solo añade", len(experimentos.listar(ruta=ruta)) == 2)
        chk("listar no devuelve las rondas por defecto",
            "rondas" not in experimentos.listar(ruta=ruta)[0])
        chk("cargar sí las devuelve", experimentos.cargar(e1["id"], ruta)["rondas"])
        chk("se puede filtrar por tipo",
            len(experimentos.listar(tipo="estres", ruta=ruta)) == 0
            and len(experimentos.listar(tipo="oficial", ruta=ruta)) == 2)
        chk("un tipo desconocido cae en exploratorio",
            experimentos.registrar(r, "inventado", None, ruta)["tipo"] == "exploratorio")
        chk("una línea corrupta no rompe el listado",
            (ruta.open("a", encoding="utf-8").write("{roto\n"),
             len(experimentos.listar(ruta=ruta)) == 3)[1])

        comp = experimentos.comparar(experimentos.cargar(e1["id"], ruta),
                                     experimentos.cargar(e2["id"], ruta))
        chk("la comparación dice qué familias cambian", isinstance(comp["familias_que_cambian"], list))
        chk("y da un veredicto estadístico con explicación",
            comp["exactitud"]["veredicto"] in ("mejora", "empeora", "sin_diferencia_concluyente",
                                               "muestra_insuficiente") and comp["resumen"])
        chk("comparar con un experimento ausente no lanza",
            experimentos.comparar(None, e2)["comparable"] is False)
        chk("el experimento es serializable a JSON", isinstance(json.dumps(e1, default=str), str))

    chk("el resumen del conjunto cuenta todos los escenarios",
        experimentos.resumen_conjunto()["total"] == len(escenarios.FIJOS))

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
