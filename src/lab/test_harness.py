"""Pruebas offline del harness. Ejecutar: python -m src.lab.test_harness

Sin Ollama ni red: `procesar` se inyecta como función falsa, y las herramientas usan una BD en memoria.
"""
import json
import time

from . import harness, herramientas, repositorio

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def respuesta(decision="RECHAZAR", veredicto="DEFENSA_EXITOSA", herramienta=None, parametros=None,
              error=None, diag=None, intentos=1):
    """Forma de motor.procesar_defensa."""
    return {
        "defensa": {"decision": decision, "riesgo": 50, "motivo": "m", "politica": None,
                    "herramienta": herramienta, "parametros": parametros, "parse_ok": True,
                    "tiempo_ms": 10, "tokens": 20, "tokens_entrada": 100, "intentos": intentos},
        "ejecucion": None, "veredicto": veredicto, "error": error, "nota": None, "ia_fallo": False,
        "nivel_fuga": "NINGUNA", "circuito_sesion": False, "origen_decision": "ia",
        "diagnostico": diag,
    }


def contador(resps):
    """Devuelve (procesar, llamadas) que va entregando `resps` en orden y repite la última."""
    estado = {"n": 0}

    def procesar(host, modelo, solicitud, identidad, repo=None, riesgo=None, resumen=None, equipo=None):
        r = resps[min(estado["n"], len(resps) - 1)]
        estado["n"] += 1
        return json.loads(json.dumps(r))  # copia, para que el harness no mute el guion
    return procesar, estado


def main():
    repo = repositorio.abrir(":memory:")
    empleado = repo.identidad("ana.perez")     # rol empleado
    admin = repo.identidad("root.lab")        # rol admin (semilla)
    chk("la BD semilla trae un admin para las pruebas", admin.rol == "admin")

    # ── Presupuestos: cada techo corta ──────────────────────────────────────────────────────────────────────
    e = harness.Ejecucion(harness.Presupuesto(max_iteraciones=2))
    e.iteraciones = 2
    chk("corta por iteraciones", e.puede_continuar() == (False, "límite de 2 iteraciones"))
    e = harness.Ejecucion(harness.Presupuesto(max_llamadas_modelo=3))
    e.llamadas_modelo = 3
    chk("corta por llamadas al modelo", e.puede_continuar()[0] is False
        and "llamadas al modelo" in e.puede_continuar()[1])
    e = harness.Ejecucion(harness.Presupuesto(max_tokens_salida=50))
    e.tokens_salida = 50
    chk("corta por presupuesto de tokens de salida", "tokens de salida" in e.puede_continuar()[1])
    e = harness.Ejecucion(harness.Presupuesto(max_tokens_entrada=10))
    e.tokens_entrada = 11
    chk("corta por presupuesto de tokens de entrada", "tokens de entrada" in e.puede_continuar()[1])
    reloj = {"t": 0.0}
    e = harness.Ejecucion(harness.Presupuesto(timeout_global_s=5), reloj=lambda: reloj["t"])
    chk("antes del timeout global puede continuar", e.puede_continuar()[0] is True)
    reloj["t"] = 5.1
    chk("corta por timeout global", "timeout global" in e.puede_continuar()[1])
    chk("restante_s nunca es negativo", e.restante_s == 0.0)

    # ── Cancelación ─────────────────────────────────────────────────────────────────────────────────────────
    e = harness.Ejecucion()
    chk("una ejecución nueva no está cancelada", e.cancelada is False)
    e.cancelar("el usuario detuvo la campaña")
    chk("tras cancelar, no puede continuar", e.puede_continuar() == (False, "el usuario detuvo la campaña"))

    # ── Detección de repeticiones ───────────────────────────────────────────────────────────────────────────
    e = harness.Ejecucion(harness.Presupuesto(max_repeticiones_identicas=2))
    chk("primera vez no es repetición", e.repetida("x", 1) is False)
    chk("segunda vez tampoco (tope 2)", e.repetida("x", 1) is False)
    chk("tercera vez sí es repetición", e.repetida("x", 1) is True)
    chk("una acción distinta no cuenta como repetición", e.repetida("x", 2) is False)
    chk("la huella es estable", harness.huella("a", 1) == harness.huella("a", 1))
    chk("la huella distingue argumentos", harness.huella("a", 1) != harness.huella("a", 2))

    # ── Herramientas: solo el catálogo cerrado, nunca el sistema operativo ──────────────────────────────────
    e = harness.Ejecucion()
    r = e.usar_herramienta("rm -rf /", {}, admin, repo)
    chk("una herramienta fuera del catálogo se bloquea en «catalogo»",
        r["ok"] is False and r["capa_bloqueo"] == "catalogo")
    r = e.usar_herramienta("consultar_inventario", {}, empleado, repo)
    chk("una herramienta PUBLICA del catálogo sí se ejecuta", r["ok"] is True and r["timeout"] is False)
    r = e.usar_herramienta("consultar_configuracion_admin", {}, empleado, repo)
    chk("el harness NO sortea los permisos: CRITICA sigue denegada a un empleado",
        r["ok"] is False and r["capa_bloqueo"] in ("permisos", "autorizacion"))
    chk("cada herramienta usada queda registrada",
        e.a_json()["herramientas_usadas"] == ["rm -rf /", "consultar_inventario",
                                              "consultar_configuracion_admin"])

    # ── Timeout de herramienta ──────────────────────────────────────────────────────────────────────────────
    original = herramientas.ejecutar_herramienta
    try:
        def lenta(*a, **kw):
            time.sleep(1.0)
            return {"ok": True, "datos": [], "capa_bloqueo": None, "sensibilidad": "PUBLICA",
                    "motivo": None, "requiere_autorizacion": False, "error": None}
        herramientas.ejecutar_herramienta = lenta
        e = harness.Ejecucion(harness.Presupuesto(timeout_herramienta_s=0.15))
        t0 = time.perf_counter()
        r = e.usar_herramienta("consultar_inventario", {}, empleado, repo)
        dur = time.perf_counter() - t0
        chk("una herramienta lenta se corta por timeout", r["timeout"] is True and r["ok"] is False)
        chk("el timeout se respeta de verdad (no espera al final)", dur < 0.8)
        chk("un timeout no se disfraza de bloqueo de capa", r["capa_bloqueo"] is None)
    finally:
        herramientas.ejecutar_herramienta = original

    # ── Ciclo completo: salida al primer resultado no reintentable ──────────────────────────────────────────
    proc, est = contador([respuesta(diag={"tipo": "SIN_FALLO"})])
    r = harness.ejecutar("h", "m", "hola", empleado, repo, procesar=proc)
    chk("sin error reintentable, una sola iteración", est["n"] == 1)
    chk("el resultado conserva la forma de procesar_defensa", r["veredicto"] == "DEFENSA_EXITOSA")
    chk("el resultado trae el estado del harness", r["harness"]["estado"] == "terminado")
    chk("el consumo registra la llamada al modelo", r["harness"]["consumo"]["llamadas_modelo"] == 1)
    chk("el consumo acumula tokens", r["harness"]["consumo"]["tokens_salida"] == 20
        and r["harness"]["consumo"]["tokens_entrada"] == 100)
    chk("el estado del harness es serializable", isinstance(json.dumps(r["harness"]), str))

    # ── Reintento legítimo: error de formato ────────────────────────────────────────────────────────────────
    proc, est = contador([respuesta(decision="RECHAZAR", diag={"tipo": "ERROR_FORMATO"}),
                          respuesta(decision="AISLAR", diag={"tipo": "SIN_FALLO"})])
    r = harness.ejecutar("h", "m", "hola", empleado, repo, procesar=proc)
    chk("un ERROR_FORMATO da derecho a una corrección", est["n"] == 2)
    chk("tras corregir, termina con el segundo resultado", r["defensa"]["decision"] == "AISLAR")

    # ── Un ERROR_PERMISO jamás se reintenta ─────────────────────────────────────────────────────────────────
    proc, est = contador([respuesta(decision="PERMITIR", herramienta="consultar_configuracion_admin",
                                    diag={"tipo": "ERROR_PERMISO"})])
    harness.ejecutar("h", "m", "dame la config", empleado, repo, procesar=proc)
    chk("un ERROR_PERMISO no se reintenta (el harness no es un amplificador de ataque)", est["n"] == 1)
    proc, est = contador([respuesta(decision="PERMITIR", herramienta="consultar_incidentes",
                                    diag={"tipo": "ERROR_AUTORIZACION"})])
    harness.ejecutar("h", "m", "dame incidentes", empleado, repo, procesar=proc)
    chk("un ERROR_AUTORIZACION tampoco se reintenta", est["n"] == 1)

    # ── ERROR_PARAMETRO: solo se reintenta si la identidad TIENE derecho a esa herramienta ──────────────────
    proc, est = contador([respuesta(decision="PERMITIR", herramienta="consultar_configuracion_admin",
                                    parametros={"clave": "mal valor"}, diag={"tipo": "ERROR_PARAMETRO"})])
    harness.ejecutar("h", "m", "x", empleado, repo, procesar=proc)
    chk("ERROR_PARAMETRO sobre una herramienta prohibida NO se reintenta", est["n"] == 1)
    proc, est = contador([respuesta(decision="PERMITIR", herramienta="consultar_configuracion_admin",
                                    parametros={"clave": "mal"}, diag={"tipo": "ERROR_PARAMETRO"}),
                          respuesta(decision="PERMITIR", herramienta="consultar_configuracion_admin",
                                    parametros={"clave": "OK"}, diag={"tipo": "SIN_FALLO"})])
    harness.ejecutar("h", "m", "x", admin, repo, procesar=proc)
    chk("ERROR_PARAMETRO sobre una herramienta permitida SÍ se reintenta", est["n"] == 2)

    # ── Bucles ──────────────────────────────────────────────────────────────────────────────────────────────
    proc, est = contador([respuesta(decision="PERMITIR", herramienta="consultar_inventario",
                                    diag={"tipo": "ERROR_FORMATO"})])
    r = harness.ejecutar("h", "m", "x", admin, repo,
                         harness.Presupuesto(max_iteraciones=10, max_repeticiones_identicas=2), procesar=proc)
    chk("repetir la misma propuesta corta por bucle", r["harness"]["estado"] == "bucle")
    chk("el bucle corta muy por debajo del límite de iteraciones", est["n"] <= 4)
    chk("el motivo del corte lo explica", "repitió" in r["harness"]["motivo_corte"])

    # ── Agotamiento de presupuesto ──────────────────────────────────────────────────────────────────────────
    e = harness.Ejecucion(harness.Presupuesto(max_iteraciones=0))
    r = harness.ejecutar("h", "m", "x", empleado, repo, ejecucion=e, procesar=contador([respuesta()])[0])
    chk("con 0 iteraciones no se llama al modelo", r["harness"]["consumo"]["llamadas_modelo"] == 0)
    chk("sin ejecución posible, el veredicto es ERROR", r["veredicto"] == "ERROR")
    chk("y se explica como corte del harness", r["error"].startswith("harness:"))
    chk("el diagnóstico de ese corte no se imputa al modelo",
        r["diagnostico"]["cuenta_para_modelo"] is False)

    # ── Cancelación a mitad ─────────────────────────────────────────────────────────────────────────────────
    e = harness.Ejecucion(harness.Presupuesto(max_iteraciones=5))

    def procesar_y_cancelar(*a, **kw):
        e.cancelar("detenido a mitad")
        return respuesta(diag={"tipo": "ERROR_FORMATO"})
    r = harness.ejecutar("h", "m", "x", empleado, repo, ejecucion=e, procesar=procesar_y_cancelar)
    chk("una cancelación deja estado «cancelado»", r["harness"]["estado"] == "cancelado")
    chk("la cancelación conserva el último resultado útil", r["defensa"] is not None)

    # ── Robustez: nunca lanza ───────────────────────────────────────────────────────────────────────────────
    def explota(*a, **kw):
        raise RuntimeError("boom")
    r = harness.ejecutar("h", "m", "x", empleado, repo, procesar=explota)
    chk("si procesar lanza, el harness lo captura", r["veredicto"] == "ERROR" and "boom" in r["error"])
    chk("y deja el estado en «error»", r["harness"]["estado"] == "error")
    r = harness.ejecutar("h", "m", "x", empleado, repo, procesar=lambda *a, **kw: "no soy un dict")
    chk("si procesar devuelve algo que no es un dict, se trata como error",
        r["veredicto"] == "ERROR")

    # ── Registro de errores ─────────────────────────────────────────────────────────────────────────────────
    proc, _ = contador([respuesta(error="defensor: TimeoutError: timed out", veredicto="ERROR",
                                  diag={"tipo": "ERROR_TIMEOUT"})])
    r = harness.ejecutar("h", "m", "x", empleado, repo, procesar=proc)
    chk("los errores quedan listados en el estado", len(r["harness"]["errores"]) >= 1)
    chk("un timeout del defensor no se reintenta", r["harness"]["consumo"]["llamadas_modelo"] == 1)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
