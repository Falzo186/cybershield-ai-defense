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

    # ── Aislamiento del camino de producción ────────────────────────────────────────────────────────────────
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    usuarios = [p for p in list((raiz / "src" / "lab").glob("*.py")) + list((raiz / "server").glob("*.py"))
                if "adversarial" in p.read_text(encoding="utf-8") and not p.name.startswith("test_")
                and p.name != "adversarial.py"]
    chk("el laboratorio adversarial no lo importa el código de producción",
        usuarios == [], )

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
