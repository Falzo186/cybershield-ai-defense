"""Pruebas offline del laboratorio adversarial. Ejecutar: python -m src.lab.test_adversarial

La parte de detección determinista no necesita nada: ni Ollama, ni red, ni azar. La de cumplimiento usa un
defensor falso.
"""
from . import adversarial as adv, permisos, repositorio

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    # ── El conjunto ─────────────────────────────────────────────────────────────────────────────────────────
    todos = adv.casos()
    chk("los ids son únicos", len({c["id"] for c in todos}) == len(todos))
    chk("hay casos de los dos vectores",
        {c["vector"] for c in todos} == set(adv.VECTORES))
    chk("hay controles benignos en los dos vectores (si no, no habría falsos positivos que medir)",
        all(any(not c["malicioso"] for c in todos if c["vector"] == v) for v in adv.VECTORES))
    chk("hay más maliciosos que benignos, pero los benignos son suficientes",
        sum(1 for c in todos if not c["malicioso"]) >= 8)
    chk("filtrar por vector funciona",
        {c["vector"] for c in adv.casos("documentacion")} == {"documentacion"})
    chk("solo_maliciosos excluye los controles",
        all(c["malicioso"] for c in adv.casos(solo_maliciosos=True)))
    chk("el conjunto incluye variantes que el filtro no cubre (para medir su techo real)",
        any(c["categoria"] in ("reformulacion", "codificacion") for c in todos))

    # ── Detección determinista ──────────────────────────────────────────────────────────────────────────────
    r = adv.campana_deteccion()
    m = r["metricas"]
    chk("se evalúan todos los casos", m["intentos"] == len(todos))
    chk("la matriz de confusión cuadra", m["VP"] + m["FN"] + m["FP"] + m["VN"] == m["intentos"])
    chk("maliciosos = VP + FN y benignos = FP + VN",
        m["maliciosos"] == m["VP"] + m["FN"] and m["benignos"] == m["FP"] + m["VN"])
    chk("la detección viene con intervalo de confianza",
        m["deteccion"]["bajo"] is not None and m["deteccion"]["n"] == m["maliciosos"])
    chk("se informa del tamaño de muestra", m["deteccion"]["n"] > 0)

    # Ningún control benigno debe bloquearse: si esto falla, el filtro es un buscador de palabras.
    chk("cero falsos positivos sobre los controles benignos", m["FP"] == 0)
    benignos_raros = [f for f in r["filas"] if not f["malicioso"] and f["detectado"]]
    chk("ningún benigno con la palabra «instrucciones» o «administrador» se bloquea", benignos_raros == [])

    # Las categorías que el filtro SÍ cubre deben detectarse todas.
    cubiertas = {c for c, _, _ in __import__("src.lab.filtro_rapido", fromlist=["x"]).PATRONES_BLOQUEO}
    fallos_cubiertos = [f for f in r["filas"]
                        if f["resultado"] == "FN" and f["categoria"] in cubiertas]
    chk("no se escapa ningún ataque de una categoría que el filtro declara cubrir", fallos_cubiertos == [])
    chk("las no detectadas son exactamente las variantes fuera de patrón",
        set(m["categorias_no_detectadas"]) <= {"reformulacion", "codificacion"})
    chk("y hay al menos una no detectada: el informe no finge cobertura total",
        len(m["categorias_no_detectadas"]) >= 1)

    # ── Inyección indirecta ─────────────────────────────────────────────────────────────────────────────────
    ind = adv.campana_deteccion("documentacion")
    chk("la inyección indirecta se mide por separado",
        all(f["vector"] == "documentacion" for f in ind["filas"]))
    chk("un fragmento de documentación con «ignora tus instrucciones» se descarta",
        next(f for f in ind["filas"] if f["id"] == "IN-01")["detectado"])
    chk("un fragmento con un secreto simulado se descarta",
        next(f for f in ind["filas"] if f["id"] == "IN-03")["detectado"])
    chk("documentación legítima que habla de instrucciones NO se descarta",
        not next(f for f in ind["filas"] if f["id"] == "BD-03")["detectado"])
    chk("el desglose por vector cuadra con el total",
        sum(sum(v.values()) for v in m["por_vector"].values()) == m["intentos"])

    # ── Reproducibilidad ────────────────────────────────────────────────────────────────────────────────────
    chk("la detección determinista da exactamente lo mismo al repetirla",
        [(f["id"], f["resultado"]) for f in adv.campana_deteccion()["filas"]]
        == [(f["id"], f["resultado"]) for f in r["filas"]])
    chk("se mide el tiempo de detección", m["tiempo_deteccion_ms"]["n"] == m["intentos"])

    # ── Cumplimiento del modelo ─────────────────────────────────────────────────────────────────────────────
    repo = repositorio.abrir(":memory:")
    ident = permisos.Identidad("eval.empleado", "empleado")

    def defensor(decision, error=None, ejec=None):
        def procesar(host, modelo, solicitud, identidad, repo_=None, **kw):
            if error:
                return {"defensa": None, "ejecucion": None, "veredicto": "ERROR", "error": error,
                        "diagnostico": {"tipo": "ERROR_INFRAESTRUCTURA", "cuenta_para_modelo": False}}
            return {"defensa": {"decision": decision}, "ejecucion": ejec, "veredicto": "DEFENSA_EXITOSA",
                    "error": None, "origen_decision": "ia",
                    "diagnostico": {"tipo": "SIN_FALLO", "cuenta_para_modelo": True}}
        return procesar

    maliciosos = adv.casos("solicitud", solo_maliciosos=True)
    filas = [adv.evaluar_cumplimiento(c, defensor("RECHAZAR"), "h", "m", ident, repo) for c in maliciosos]
    rc = adv.resumir_cumplimiento(filas)
    chk("un defensor que rechaza cumple la política al 100 %", rc["cumplimiento"]["valor"] == 1.0)
    chk("y no hay fugas", rc["fugas"]["exitos"] == 0)

    filas = [adv.evaluar_cumplimiento(c, defensor("PERMITIR"), "h", "m", ident, repo) for c in maliciosos]
    rc = adv.resumir_cumplimiento(filas)
    chk("un defensor que permite ante un ataque no cumple la política", rc["cumplimiento"]["valor"] == 0.0)

    filas = [adv.evaluar_cumplimiento(c, defensor("PERMITIR", ejec={"ok": True, "sensibilidad": "CRITICA"}),
                                      "h", "m", ident, repo) for c in maliciosos]
    chk("si además salen datos, se cuenta como fuga",
        adv.resumir_cumplimiento(filas)["fugas"]["valor"] == 1.0)

    filas = [adv.evaluar_cumplimiento(c, defensor(None, error="defensor: URLError"), "h", "m", ident, repo)
             for c in maliciosos]
    rc = adv.resumir_cumplimiento(filas)
    chk("Ollama caído no se cuenta como incumplimiento",
        rc["imputables"] == 0 and rc["cumplimiento"]["valor"] is None)
    chk("y se publica aparte", rc["infraestructura"] == len(maliciosos))

    def explota(*a, **kw):
        raise RuntimeError("boom")
    f = adv.evaluar_cumplimiento(maliciosos[0], explota, "h", "m", ident, repo)
    chk("si el motor lanza, se registra como error y no tumba la campaña",
        f["veredicto"] == "ERROR" and "boom" in f["error"])

    # ── Robustez ────────────────────────────────────────────────────────────────────────────────────────────
    chk("resumir sin filas no inventa tasas",
        adv.resumir_deteccion([])["deteccion"]["valor"] is None)
    chk("resumir ignora entradas que no son filas", adv.resumir_deteccion([None, 3])["intentos"] == 0)
    chk("resumir_cumplimiento vacío no lanza", adv.resumir_cumplimiento([])["intentos"] == 0)

    # ══ B · Resistencia del MODELO, medida aparte del filtro (Fase E) ═══════════════════════════════════════
    ident = permisos.Identidad("eval.empleado", "empleado")

    def analizar(decision="RECHAZAR", ok=True, parse_ok=True, error=None, por_texto=None):
        def _f(host, modelo, texto, identidad, catalogo, **kw):
            d = por_texto(texto) if por_texto else decision
            return {"ok": ok, "parse_ok": parse_ok, "decision": d, "riesgo": 60, "motivo": "m",
                    "herramienta": None, "parametros": None, "politica": None, "tiempo_ms": 5,
                    "tokens": 10, "tokens_entrada": 40, "tecnica": "fewshot", "error": error}
        return _f

    # Un modelo que contiene TODO: recall perfecto, pero precisión mala (marca los benignos).
    r = adv.campana_modelo(analizar("RECHAZAR"), "h", "m", ident)
    m = r["metricas"]
    cls = m["clasificacion"]
    chk("la campaña del modelo evalúa todos los casos", m["intentos"] == len(adv.casos()))
    chk("un modelo que lo rechaza todo tiene recall 1", cls["recall"]["valor"] == 1.0)
    chk("pero marca los benignos como maliciosos (FP > 0)", cls["FP"] >= 8)
    chk("y su especificidad es 0", cls["especificidad"]["valor"] == 0.0)
    chk("la campaña del modelo declara que NO pasó por el filtro rápido",
        r["config"]["sin_filtro_rapido"] is True and "SIN el filtro" in m["nota"])

    # Un modelo que permite TODO: no contiene nada; recall 0 y ningún falso positivo.
    m2 = adv.campana_modelo(analizar("PERMITIR"), "h", "m", ident)["metricas"]
    chk("un modelo que lo permite todo tiene recall 0", m2["clasificacion"]["recall"]["valor"] == 0.0)
    chk("y deja sin contener todos los casos maliciosos",
        len(m2["casos_no_contenidos"]) == sum(1 for c in adv.casos() if c["malicioso"]))
    # Sin ningún caso marcado como malicioso no hay precisión (denominador 0), y por tanto no hay F1. Vale
    # None, no 0: «no se puede calcular» y «salió cero» no son lo mismo.
    chk("sin positivos marcados no hay precisión", m2["clasificacion"]["precision"]["valor"] is None)
    chk("y sin precisión no hay F1", m2["clasificacion"]["f1"] is None)

    # Un modelo que falla: indeterminado, ni acierto ni fallo.
    m3 = adv.campana_modelo(analizar(ok=False, error="timeout"), "h", "m", ident)["metricas"]
    chk("un fallo de inferencia es indeterminado", m3["indeterminados"] == m3["intentos"]
        and m3["imputables"] == 0)
    chk("sin casos imputables no hay recall, y vale None",
        m3["clasificacion"]["recall"]["valor"] is None)
    chk("ni F1", m3["clasificacion"]["f1"] is None)
    m4 = adv.campana_modelo(analizar(parse_ok=False), "h", "m", ident)["metricas"]
    chk("un JSON ilegible también es indeterminado, no un fallo del razonamiento",
        m4["imputables"] == 0)

    def revienta(*a, **k):
        raise RuntimeError("Ollama caído")
    m5 = adv.campana_modelo(revienta, "h", "m", ident)["metricas"]
    chk("una excepción del defensor no tumba la campaña", m5["intentos"] == len(adv.casos()))
    chk("y queda como indeterminada con su error", m5["imputables"] == 0)

    # Un modelo razonable: distingue por una palabra. Sirve para comprobar el desglose y la repetibilidad.
    discrimina = analizar(por_texto=lambda t: "RECHAZAR"
                          if any(x in t.lower() for x in ("ignora", "administrador", "revela", "secreto"))
                          else "PERMITIR")
    r6 = adv.campana_modelo(discrimina, "h", "m", ident, repeticiones=3)
    m6 = r6["metricas"]
    chk("repetir multiplica los intentos", m6["intentos"] == 3 * len(adv.casos()))
    chk("un modelo determinista tiene repetibilidad 1", m6["repetibilidad"]["tasa"] == 1.0)
    chk("y se dice sobre cuántos casos repetidos se midió",
        m6["repetibilidad"]["casos_repetidos"] == len(adv.casos()))
    chk("hay desglose por vector", set(m6["por_vector"]) == set(adv.VECTORES))
    chk("cada vector trae su propia matriz de confusión",
        all({"VP", "FP", "FN", "VN", "precision", "recall"} <= set(v) for v in m6["por_vector"].values()))
    chk("un modelo sin repeticiones no inventa una tasa de repetibilidad",
        adv.campana_modelo(discrimina, "h", "m", ident)["metricas"]["repetibilidad"]["tasa"] is None)

    # F1 nunca lleva intervalo de confianza, y se dice por qué.
    chk("F1 se publica sin IC y con su explicación",
        "f1" in cls and "nota_f1" in cls and "correlacionadas" in cls["nota_f1"])

    # ── Filtro contra modelo: comparación explícita, nunca suma ────────────────────────────────────────────
    det = adv.campana_deteccion()
    una_vez = adv.campana_modelo(discrimina, "h", "m", ident)      # una repetición: mismo n que el filtro
    comp = adv.comparar_filtro_y_modelo(det, una_vez)
    chk("la comparación filtro/modelo da un veredicto estadístico",
        comp["comparacion"]["veredicto"] in ("mejora", "empeora", "sin_diferencia_concluyente",
                                             "muestra_insuficiente"))
    chk("y avisa de que los dos recalls no se suman", "no se suman" in comp["nota"].lower())
    chk("con una repetición, los dos recalls se miden sobre los mismos maliciosos",
        comp["filtro"]["n"] == comp["modelo"]["n"] == sum(1 for c in adv.casos() if c["malicioso"]))
    comp3 = adv.comparar_filtro_y_modelo(det, r6)
    chk("con 3 repeticiones el n del modelo es el triple, y se ve en la comparación",
        comp3["modelo"]["n"] == 3 * comp3["filtro"]["n"])

    # ══ Cumplimiento del camino completo, con su etiqueta ══════════════════════════════════════════════════
    def procesar_falso(host, modelo, texto, identidad, repo=None, *a, **k):
        return {"defensa": {"decision": "RECHAZAR", "riesgo": 70, "motivo": "m", "politica": None,
                            "herramienta": None, "parametros": None, "parse_ok": True, "tiempo_ms": 5,
                            "tokens": 9, "intentos": 1},
                "ejecucion": None, "veredicto": "DEFENSA_EXITOSA", "error": None, "nota": None,
                "ia_fallo": False, "nivel_fuga": "NINGUNA", "circuito_sesion": False,
                "origen_decision": "ia", "diagnostico": {"cuenta_para_modelo": True}}
    rc = adv.campana_cumplimiento(procesar_falso, "h", "m", ident, repo)
    chk("la campaña de cumplimiento recorre todos los casos", rc["metricas"]["intentos"] == len(adv.casos()))
    chk("y declara que SÍ pasó por el filtro rápido", rc["config"]["sin_filtro_rapido"] is False)
    chk("el cumplimiento del camino completo se mide aparte del modelo solo",
        rc["metricas"]["cumplimiento"]["valor"] == 1.0)

    # ══ C · Capacidad del modelo ATACANTE ══════════════════════════════════════════════════════════════════
    def ronda(gana_cada):
        def _f(host, matq, mdef, identidad, n, historial=None, repo=None, intensidad=2, escenario=None, **kw):
            gana = n % gana_cada == 0
            return {"ronda": n, "ataque": {"prompt": f"intento {n}", "categoria": "autoridad",
                                           "tiempo_ms": 4},
                    "defensa": {"decision": "PERMITIR" if gana else "RECHAZAR", "tiempo_ms": 6},
                    "ejecucion": {"ok": gana, "sensibilidad": "CRITICA" if gana else None},
                    "veredicto": "FALLA_DEFENSA" if gana else "DEFENSA_EXITOSA",
                    "diagnostico": {"cuenta_para_modelo": True}, "origen_decision": "ia"}
        return _f
    ra = adv.campana_atacante(ronda(3), "h", "ma", "md", ident, repo, rondas=9)
    ma = ra["metricas"]
    chk("la campaña del atacante juega las rondas pedidas", ma["rondas"] == 9)
    chk("cuenta los objetivos conseguidos sobre la ejecución",
        (ma["objetivo_conseguido"]["exitos"], ma["objetivo_conseguido"]["n"]) == (3, 9))
    chk("y publica el intervalo de confianza", ma["objetivo_conseguido"]["bajo"] is not None)
    chk("hay desglose por técnica del atacante", "autoridad" in ma["por_tecnica"])
    chk("y se dice qué frenó los intentos fallidos", ma["frenado_por"] == {"ia": 6})
    chk("la definición de «objetivo conseguido» va con el resultado",
        "sobre la ejecución" in ma["definicion"])

    # Una fuga SIN FALLA_DEFENSA también cuenta: se mide el efecto, no la etiqueta.
    def ronda_fuga(host, matq, mdef, identidad, n, historial=None, repo=None, **kw):
        return {"ronda": n, "ataque": {"prompt": "p", "categoria": "rol_falso", "tiempo_ms": 1},
                "defensa": {"decision": "RECHAZAR", "tiempo_ms": 1},
                "ejecucion": {"ok": True, "sensibilidad": "CONFIDENCIAL"},
                "veredicto": "DEFENSA_EN_PROFUNDIDAD", "diagnostico": {"cuenta_para_modelo": True},
                "origen_decision": "ia"}
    mf = adv.campana_atacante(ronda_fuga, "h", "ma", "md", ident, repo, rondas=2)["metricas"]
    chk("si salieron datos sensibles, el objetivo está conseguido aunque el veredicto no sea FALLA_DEFENSA",
        mf["objetivo_conseguido"]["exitos"] == 2)

    # Un defensor que dice RECHAZAR y no ejecuta nada: el atacante no consiguió nada.
    def ronda_limpia(host, matq, mdef, identidad, n, historial=None, repo=None, **kw):
        return {"ronda": n, "ataque": {"prompt": "p", "categoria": "autoridad", "tiempo_ms": 1},
                "defensa": {"decision": "RECHAZAR", "tiempo_ms": 1}, "ejecucion": None,
                "veredicto": "DEFENSA_EXITOSA", "diagnostico": {"cuenta_para_modelo": True},
                "origen_decision": "ia"}
    ml = adv.campana_atacante(ronda_limpia, "h", "ma", "md", ident, repo, rondas=4)["metricas"]
    chk("un ataque contenido no cuenta como objetivo conseguido", ml["objetivo_conseguido"]["exitos"] == 0)
    chk("y la tasa es 0, no None (hubo rondas imputables)", ml["objetivo_conseguido"]["valor"] == 0.0)

    def ronda_rota(*a, **k):
        raise RuntimeError("Ollama caído")
    mr = adv.campana_atacante(ronda_rota, "h", "ma", "md", ident, repo, rondas=3)["metricas"]
    chk("una ronda con error de infraestructura no cuenta para el atacante",
        mr["imputables"] == 0 and mr["infraestructura"] == 3)
    chk("sin rondas imputables no hay tasa de éxito del atacante",
        mr["objetivo_conseguido"]["valor"] is None)

    # ── Aislamiento del camino de producción ────────────────────────────────────────────────────────────────
    # El laboratorio adversarial NO puede estar en el camino que atiende una solicitud real: ni el motor, ni
    # las capas, ni el servidor de la partida. Sí puede leerlo una vista de solo lectura (server/panel.py),
    # que es donde se presenta su resultado; esa excepción es explícita y está aquí para que se vea.
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    PERMITIDO_LEER = {"adversarial.py", "panel.py"}
    usuarios = [p.name for p in list((raiz / "src" / "lab").glob("*.py")) + list((raiz / "server").glob("*.py"))
                if "adversarial" in p.read_text(encoding="utf-8") and not p.name.startswith("test_")
                and p.name not in PERMITIDO_LEER]
    chk("el laboratorio adversarial no está en el camino que atiende una solicitud real", usuarios == [])
    chk("en concreto, ni el motor ni el servidor de la partida lo importan",
        "adversarial" not in (raiz / "src" / "lab" / "motor.py").read_text(encoding="utf-8")
        and "adversarial" not in (raiz / "src" / "lab" / "herramientas.py").read_text(encoding="utf-8")
        and "adversarial" not in (raiz / "server" / "app.py").read_text(encoding="utf-8"))
    chk("la única vista que lo lee es el panel, y solo para mostrar su resultado",
        "adversarial.campana_deteccion" in (raiz / "server" / "panel.py").read_text(encoding="utf-8"))

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
