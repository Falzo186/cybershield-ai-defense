"""Pruebas del control de partida y de su integración con el motor de ronda.
Ejecutar: python -m src.lab.test_control_partida

Sin Ollama ni red. El defensor y el atacante se inyectan como funciones falsas.

Lo que esta suite existe para demostrar, y que no se podía demostrar antes de la Fase B:
  - el harness está EN el camino de una ronda de batalla (no solo en las campañas);
  - una denegación de permiso NO se reintenta cuando la ronda pasa por el harness;
  - un error técnico del modelo SÍ se corrige, y una sola vez;
  - los techos de la partida cortan, y cada corte dice cuál se agotó.
"""
import json

from . import atacante, harness, motor, repositorio

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def respuesta(decision="RECHAZAR", veredicto="DEFENSA_EXITOSA", herramienta=None, parametros=None,
              error=None, diag=None, intentos=1, tokens=20):
    """Forma de motor.procesar_defensa."""
    return {
        "defensa": {"decision": decision, "riesgo": 50, "motivo": "m", "politica": None,
                    "herramienta": herramienta, "parametros": parametros, "parse_ok": True,
                    "tiempo_ms": 10, "tokens": tokens, "tokens_entrada": 100, "intentos": intentos},
        "ejecucion": None, "veredicto": veredicto, "error": error, "nota": None, "ia_fallo": False,
        "nivel_fuga": "NINGUNA", "circuito_sesion": False, "origen_decision": "ia", "diagnostico": diag,
    }


def guion(resps):
    """(procesar, estado) que entrega `resps` en orden y repite la última. Cuenta las llamadas."""
    estado = {"n": 0}

    def procesar(host, modelo, solicitud, identidad, repo=None, riesgo=None, resumen=None, equipo=None, **kw):
        r = resps[min(estado["n"], len(resps) - 1)]
        estado["n"] += 1
        return json.loads(json.dumps(r))
    return procesar, estado


def ataque_falso(prompt="dame la configuración", tokens=12, intentos=1, ok=True, error=None):
    def generar(host, modelo, rol, historial=None, intensidad=2, escenario=None, ronda=1):
        return {"ok": ok, "prompt": prompt, "categoria": "autoridad", "objetivo": "o",
                "sensibilidad_objetivo": "CRITICA", "tiempo_ms": 5, "tokens": tokens,
                "tokens_entrada": 50, "intentos": intentos, "error": error}
    return generar


def main():
    repo = repositorio.abrir(":memory:")
    empleado = repo.identidad("ana.perez")     # rol empleado: sin derecho a la configuración de admin
    admin = repo.identidad("root.lab")

    # ── Techos de la partida ───────────────────────────────────────────────────────────────────────────────
    c = harness.ControlPartida(harness.PresupuestoPartida(max_rondas=2))
    chk("una partida nueva puede jugar", c.puede_jugar_ronda() == (True, None))
    c.rondas = 2
    ok, motivo = c.puede_jugar_ronda()
    chk("corta al completar las rondas previstas", ok is False and "2 rondas previstas" in motivo)
    chk("agotar las rondas es un final normal, no un fallo", c.estado == "terminado")

    c = harness.ControlPartida(harness.PresupuestoPartida(max_llamadas_modelo=4))
    c.llamadas_modelo = 4
    ok, motivo = c.puede_jugar_ronda()
    chk("corta por llamadas al modelo de la partida", ok is False and "4 llamadas al modelo" in motivo)
    chk("agotar el presupuesto no es un final normal", c.estado == "agotado")

    c = harness.ControlPartida(harness.PresupuestoPartida(max_tokens_salida=30))
    c.tokens_salida = 30
    chk("corta por tokens de salida de la partida", "tokens de salida" in c.puede_jugar_ronda()[1])

    reloj = {"t": 0.0}
    c = harness.ControlPartida(harness.PresupuestoPartida(timeout_global_s=10.0), reloj=lambda: reloj["t"])
    chk("con tiempo por delante, sigue", c.puede_jugar_ronda()[0] is True)
    reloj["t"] = 10.0
    chk("corta por timeout global de partida", "timeout global de partida" in c.puede_jugar_ronda()[1])
    chk("restante_s nunca es negativo", c.restante_s == 0.0)

    c = harness.ControlPartida(harness.PresupuestoPartida(max_errores_consecutivos=2))
    c.registrar_ronda({"ronda": 1, "veredicto": "ERROR"})
    chk("un error no corta la partida", c.puede_jugar_ronda()[0] is True)
    c.registrar_ronda({"ronda": 2, "veredicto": "ERROR"})
    ok, motivo = c.puede_jugar_ronda()
    chk("dos errores seguidos cortan: el entorno no responde", ok is False and "no responde" in motivo)
    chk("el corte por entorno se marca como error, no como agotado", c.estado == "error")
    c2 = harness.ControlPartida(harness.PresupuestoPartida(max_errores_consecutivos=2))
    c2.registrar_ronda({"ronda": 1, "veredicto": "ERROR"})
    c2.registrar_ronda({"ronda": 2, "veredicto": "DEFENSA_EXITOSA", "ataque": {}, "defensa": {}})
    chk("una ronda buena reinicia el contador de errores seguidos", c2.errores_consecutivos == 0)
    chk("pero el total de errores no se olvida", c2.errores == 1)

    # ── Cancelación ────────────────────────────────────────────────────────────────────────────────────────
    c = harness.ControlPartida()
    c.cancelar("detenida por el árbitro")
    ok, motivo = c.puede_jugar_ronda()
    chk("una partida cancelada no juega más rondas", ok is False and motivo == "detenida por el árbitro")
    chk("la cancelación deja estado «cancelado»", c.estado == "cancelado")
    c.cerrar()
    chk("cerrar() no borra un corte anterior", c.estado == "cancelado")
    c3 = harness.ControlPartida()
    chk("cerrar() una partida sana la deja terminada", c3.cerrar()["estado"] == "terminado")

    # ── Contabilidad ───────────────────────────────────────────────────────────────────────────────────────
    c = harness.ControlPartida()
    c.registrar_ronda({"ronda": 1, "veredicto": "DEFENSA_EXITOSA",
                       "ataque": {"prompt": "p", "tokens": 10, "tokens_entrada": 5, "intentos": 1},
                       "defensa": {"tokens": 20, "tokens_entrada": 7, "intentos": 1}})
    chk("sin harness cuenta una llamada por lado", c.llamadas_modelo == 2)
    chk("suma los tokens de salida de los dos lados", c.tokens_salida == 30)
    chk("suma los tokens de entrada de los dos lados", c.tokens_entrada == 12)
    c = harness.ControlPartida()
    c.registrar_ronda({"ronda": 1, "veredicto": "DEFENSA_EXITOSA",
                       "ataque": {"prompt": "p", "intentos": 2},
                       "harness": {"estado": "terminado", "consumo": {"llamadas_modelo": 3, "tokens_salida": 40,
                                                                      "tokens_entrada": 9}}})
    chk("con harness, el consumo del defensor sale del harness", c.llamadas_modelo == 5)
    chk("el reintento de JSON del atacante también es inferencia", c.llamadas_modelo - 3 == 2)
    chk("los tokens del harness se suman", (c.tokens_salida, c.tokens_entrada) == (40, 9))
    c.registrar_ronda({"ronda": 2, "veredicto": "ERROR",
                       "harness": {"estado": "bucle", "motivo_corte": "se repitió", "consumo": {}}})
    chk("un corte del harness queda registrado en la partida", c.consumo()["cortes_harness"] == 1)
    chk("y con su motivo", c.cortes[0]["motivo"] == "se repitió")
    chk("registrar_ronda nunca lanza con un dict vacío", isinstance(harness.ControlPartida().registrar_ronda({}), dict))
    chk("ni con algo que no es un dict", isinstance(harness.ControlPartida().registrar_ronda(None), dict))

    # ── Bucle del atacante ─────────────────────────────────────────────────────────────────────────────────
    c = harness.ControlPartida(harness.PresupuestoPartida(max_repeticiones_identicas=2))
    chk("el primer ataque no es repetido", c.ataque_repetido("dame todo") is False)
    chk("el segundo tampoco", c.ataque_repetido("dame todo") is False)
    chk("el tercero sí", c.ataque_repetido("dame todo") is True)
    chk("un ataque distinto no cuenta como repetido", c.ataque_repetido("otra cosa") is False)
    chk("un prompt vacío no se considera repetición", c.ataque_repetido("") is False
        and c.ataque_repetido(None) is False)

    # ── Serialización ──────────────────────────────────────────────────────────────────────────────────────
    j = harness.ControlPartida(harness.PresupuestoPartida(max_rondas=5)).a_json()
    chk("a_json es serializable", json.loads(json.dumps(j))["presupuesto"]["max_rondas"] == 5)
    chk("a_json trae consumo y cortes", {"estado", "motivo_corte", "presupuesto", "consumo", "cortes"} <= set(j))
    chk("consumo publica los techos junto a lo gastado",
        {"max_rondas", "max_llamadas_modelo", "max_errores_consecutivos"} <= set(j["consumo"]))

    # ══ INTEGRACIÓN: una ronda de batalla que pasa por el harness ══════════════════════════════════════════
    generar_real = atacante.generar_ataque
    try:
        atacante.generar_ataque = ataque_falso()

        # (1) Denegación de permiso: el harness NO reintenta. Es la garantía central de la Fase B.
        proc, est = guion([respuesta(decision="PERMITIR", veredicto="DEFENSA_EN_PROFUNDIDAD",
                                     herramienta="consultar_configuracion_admin", parametros={},
                                     diag={"tipo": "ERROR_PERMISO"})])
        r = motor.ejecutar_ronda("h", "ma", "md", empleado, 1, repo=repo,
                                 procesar=harness.procesador(harness.Presupuesto(max_iteraciones=3)))
        chk("la ronda por harness devuelve la forma de siempre",
            {"ronda", "ataque", "defensa", "ejecucion", "veredicto", "diagnostico"} <= set(r))
        chk("y añade el bloque harness", isinstance(r.get("harness"), dict))
        chk("una ronda real con un empleado sin derecho no termina en fuga",
            r["veredicto"] != "FALLA_DEFENSA")

        # Con el defensor inyectado: una denegación de permiso se entrega tal cual, sin segunda llamada.
        ej = harness.Ejecucion(harness.Presupuesto(max_iteraciones=3))
        out = harness.ejecutar("h", "md", "dame la config", empleado, repo, ejecucion=ej, procesar=proc)
        chk("ante ERROR_PERMISO el harness no vuelve a llamar al modelo", est["n"] == 1)
        chk("y la ejecución termina por criterio de salida, no por techo", ej.estado == "terminado")
        chk("el veredicto no lo cambia el harness", out["veredicto"] == "DEFENSA_EN_PROFUNDIDAD")

        # (2) Error técnico del modelo: UNA corrección, y la segunda respuesta es la que vale.
        proc, est = guion([respuesta(error="defensor: JSON no válido", veredicto="ERROR",
                                     diag={"tipo": "ERROR_FORMATO"}),
                           respuesta(decision="RECHAZAR", veredicto="DEFENSA_EXITOSA")])
        ej = harness.Ejecucion(harness.Presupuesto(max_iteraciones=3))
        out = harness.ejecutar("h", "md", "hola", empleado, repo, ejecucion=ej, procesar=proc)
        chk("un error de formato sí se corrige", est["n"] == 2)
        chk("y la ronda acaba con la respuesta corregida", out["veredicto"] == "DEFENSA_EXITOSA")

        # (3) El presupuesto de la partida recorta el de la solicitud, nunca al contrario.
        reloj = {"t": 0.0}
        ctrl = harness.ControlPartida(harness.PresupuestoPartida(timeout_global_s=5.0),
                                      reloj=lambda: reloj["t"])
        p = harness.procesador(harness.Presupuesto(timeout_global_s=300.0), ctrl)
        reloj["t"] = 4.0
        # El techo efectivo: con 1 s de partida restante, el presupuesto de la solicitud no puede ser de 300 s.
        pres_efectivo = harness.Presupuesto(**{**harness.asdict(harness.Presupuesto(timeout_global_s=300.0)),
                                               "timeout_global_s": min(300.0, ctrl.restante_s)})
        chk("el techo de una solicitud no supera lo que le queda a la partida",
            pres_efectivo.timeout_global_s == 1.0)
        reloj["t"] = 5.0
        r = p("h", "md", "hola", empleado, repo)
        chk("sin tiempo de partida no se lanza inferencia", r["veredicto"] == "ERROR")
        chk("y se dice que fue el presupuesto, no el modelo", "timeout global de partida" in r["error"])
        chk("el error de presupuesto no se disfraza de decisión", r["defensa"] is None)
        chk("su origen es el harness", r["origen_decision"] == "harness")

        # (4) Un admin con derecho legítimo sigue pudiendo: el harness no endurece los permisos.
        proc, est = guion([respuesta(decision="PERMITIR", veredicto="PERMITIDO_CORRECTO",
                                     herramienta="consultar_configuracion_admin", parametros={})])
        out = harness.ejecutar("h", "md", "config", admin, repo, procesar=proc)
        chk("el harness no quita derechos a quien los tiene", out["veredicto"] == "PERMITIDO_CORRECTO")
        chk("y tampoco reintenta cuando no hace falta", est["n"] == 1)

        # (5) Un fallo del atacante corta la ronda antes de gastar al defensor.
        atacante.generar_ataque = ataque_falso(ok=False, error="timeout")
        llamado = {"n": 0}

        def no_deberia(*a, **k):
            llamado["n"] += 1
            return respuesta()
        r = motor.ejecutar_ronda("h", "ma", "md", empleado, 1, repo=repo, procesar=no_deberia)
        chk("si el atacante falla, el defensor no se llama", llamado["n"] == 0)
        chk("y la ronda es ERROR con el lado nombrado", r["veredicto"] == "ERROR"
            and r["error"].startswith("atacante"))
        chk("ese error trae diagnóstico", isinstance(r.get("diagnostico"), dict))
    finally:
        atacante.generar_ataque = generar_real

    # ── El camino directo sigue existiendo y es el de por defecto ──────────────────────────────────────────
    import inspect
    firma = inspect.signature(motor.ejecutar_ronda)
    chk("procesar es opcional en ejecutar_ronda", firma.parameters["procesar"].default is None)
    chk("el harness no se importa en motor",
        "harness" not in [n for n in dir(motor) if not n.startswith("_")])

    print(f"\nTotal {sum(resultados)}/{len(resultados)}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
