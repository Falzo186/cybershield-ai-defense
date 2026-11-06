"""Rutas del panel de operaciones y análisis (`/api/panel/...`).

Va en su propio módulo a propósito: `server/app.py` ya tiene 1 800 líneas y la auditoría lo señaló como
problema. Aquí no se toca nada de la partida; estas rutas son una **vista** sobre los módulos nuevos
(diagnóstico, RAG, harness, evaluación, experimentos, laboratorio adversarial, Wazuh y correlación).

Reglas:
  - Los GET son de solo lectura y no modifican el estado del laboratorio.
  - Lo que exige Ollama no se ejecuta en una petición HTTP: una campaña se lanza en segundo plano y se
    consulta su progreso REAL (rondas hechas / planificadas), nunca una barra estimada.
  - Nada se presenta como conectado o real si no lo está: el estado dice siempre el modo de Wazuh y si
    Ollama respondió.
"""
import threading
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from src.lab import (adversarial, atacante, cliente_ollama, correlacion, diagnostico, experimentos, harness,
                     permisos, rag, repositorio, wazuh)
from src.lab.evaluacion import campana as mod_campana, escenarios, lotes, metricas

# Estado de la campaña en curso (una a la vez: dos campañas simultáneas se pisarían la GPU y las cifras).
_CAMPANA = {"obj": None, "hilo": None, "resultado": None, "error": None, "lanzada": None, "config": None}
# Mediciones de la Fase E, una a la vez cada tipo, por la misma razón: compiten por la misma CPU y las
# latencias dejarían de significar nada. `progreso` lo escribe el propio trabajo con rondas REALES hechas.
_MEDICION = {k: {"hilo": None, "resultado": None, "error": None, "lanzada": None, "config": None,
                 "progreso": None} for k in ("modelo", "atacante", "lote")}
_CANDADO = threading.Lock()


def _ok(datos):
    return JSONResponse(datos)


def _error(mensaje, status=400):
    return JSONResponse({"error": mensaje}, status_code=status)


def _lanzar(clave, config, trabajo):
    """Arranca una medición en segundo plano. Una por clave. El resultado se consulta con su GET.

    No se devuelve ningún número aquí: lo que vuelve es «lanzada». Las cifras llegan cuando existen."""
    with _CANDADO:
        e = _MEDICION[clave]
        if e["hilo"] and e["hilo"].is_alive():
            return _error(f"ya hay una medición de «{clave}» en curso", 409)
        e.update(resultado=None, error=None, config=config, progreso=None,
                 lanzada=time.strftime("%Y-%m-%dT%H:%M:%S%z"))

        def envoltorio():
            try:
                e["resultado"] = trabajo()
            except Exception as exc:  # noqa: BLE001 - el error se publica, no se esconde
                e["error"] = f"{type(exc).__name__}: {exc}"

        hilo = threading.Thread(target=envoltorio, daemon=True)
        e["hilo"] = hilo
        hilo.start()
    return _ok({"lanzada": True, "config": config})


def registrar(app, host_ollama, repo_por_defecto=None):
    """Monta las rutas del panel en la app existente. `host_ollama` es el mismo que usa la partida."""

    def _repo():
        return repo_por_defecto() if callable(repo_por_defecto) else repositorio.por_defecto()

    def _modelo_valido(cuerpo, clave="modelo"):
        """-> (modelo, None) o (None, respuesta de error). Comprueba contra la Ollama REAL: un modelo que no
        está instalado se rechaza antes de lanzar nada, en vez de fallar a mitad de la medición."""
        modelo = (cuerpo.get(clave) or "").strip()
        if not modelo:
            return None, _error(f"falta {clave}")
        if not cliente_ollama.ollama_disponible(host_ollama):
            return None, _error(f"Ollama no responde en {host_ollama}: no se lanza nada", 503)
        if modelo not in cliente_ollama.listar_modelos(host_ollama):
            return None, _error(f"el modelo «{modelo}» no está instalado en Ollama", 400)
        return modelo, None

    # ── Estado general ─────────────────────────────────────────────────────────────────────────────────────
    @app.get("/api/panel/estado")
    async def panel_estado():
        disponible = cliente_ollama.ollama_disponible(host_ollama)
        return _ok({
            "ollama": {"host": host_ollama, "disponible": disponible,
                       "modelos": cliente_ollama.listar_modelos(host_ollama) if disponible else []},
            "base_datos": {"motor": "sqlite", "solo_consultas_fijas": True,
                           "tablas_sensibilidad": permisos.TABLAS},
            "wazuh": wazuh.estado(),
            "rag": rag.estado(),
            "diagnostico": {"clases": len(diagnostico.CLASES),
                            "no_imputables": list(diagnostico.NO_IMPUTABLES)},
            "harness": {"presupuesto_por_defecto": harness.Presupuesto().__dict__,
                        "reintentables": list(harness.REINTENTABLES)},
            "conjunto_evaluacion": experimentos.resumen_conjunto(),
        })

    # ── Resumen para el dashboard ──────────────────────────────────────────────────────────────────────────
    @app.get("/api/panel/resumen")
    async def panel_resumen():
        exps = experimentos.listar()
        oficiales = [e for e in exps if e.get("tipo") == "oficial"]
        with_ex = [e for e in exps if (e.get("metricas") or {}).get("exactitud", {}).get("valor") is not None]
        ultima = with_ex[0] if with_ex else None
        rondas = sum((e.get("metricas") or {}).get("rondas", 0) for e in exps)
        lat = [((e.get("metricas") or {}).get("latencia_modelo_ms") or {}).get("mediana") for e in with_ex]
        return _ok({
            "experimentos": {"total": len(exps), "oficiales": len(oficiales),
                             "por_tipo": {t: sum(1 for e in exps if e.get("tipo") == t)
                                          for t in experimentos.TIPOS}},
            "rondas_evaluadas": rondas,
            "ultima_exactitud": (ultima or {}).get("metricas", {}).get("exactitud"),
            "ultimo_experimento": {k: (ultima or {}).get(k)
                                   for k in ("id", "fecha", "modelo", "tecnica", "pipeline", "tipo")}
            if ultima else None,
            "latencia_mediana_ms": metricas.resumen_numerico(lat),
            "modelos_evaluados": sorted({e.get("modelo") for e in exps if e.get("modelo")}),
            "tecnicas_evaluadas": sorted({e.get("tecnica") for e in exps if e.get("tecnica")}),
            "serie_exactitud": [{"id": e["id"], "fecha": e.get("fecha"), "modelo": e.get("modelo"),
                                 "tecnica": e.get("tecnica"), "pipeline": e.get("pipeline"),
                                 "valor": (e.get("metricas") or {}).get("exactitud", {}).get("valor"),
                                 "bajo": (e.get("metricas") or {}).get("exactitud", {}).get("bajo"),
                                 "alto": (e.get("metricas") or {}).get("exactitud", {}).get("alto"),
                                 "n": (e.get("metricas") or {}).get("exactitud", {}).get("n")}
                                for e in reversed(with_ex)][-40:],
        })

    # ── Conjunto de evaluación ─────────────────────────────────────────────────────────────────────────────
    @app.get("/api/panel/escenarios")
    async def panel_escenarios(familia: str | None = None):
        fams = [familia] if familia else None
        return _ok({"familias": list(escenarios.FAMILIAS),
                    "resumen": escenarios.resumen_conjunto(_repo()),
                    "escenarios": escenarios.conjunto(fams, _repo())})

    # ── Experimentos ───────────────────────────────────────────────────────────────────────────────────────
    @app.get("/api/panel/experimentos")
    async def panel_experimentos(tipo: str | None = None, modelo: str | None = None,
                                 tecnica: str | None = None):
        return _ok({"experimentos": experimentos.listar(tipo, modelo, tecnica), "tipos": list(experimentos.TIPOS)})

    @app.get("/api/panel/experimentos/{id_exp}")
    async def panel_experimento(id_exp: str):
        e = experimentos.cargar(id_exp)
        return _ok(e) if e else _error("no existe ese experimento", 404)

    @app.get("/api/panel/comparar")
    async def panel_comparar(a: str, b: str):
        ea, eb = experimentos.cargar(a), experimentos.cargar(b)
        if not ea or not eb:
            return _error("alguno de los dos experimentos no existe", 404)
        return _ok(experimentos.comparar(ea, eb))

    # ── RAG ────────────────────────────────────────────────────────────────────────────────────────────────
    @app.get("/api/panel/rag")
    async def panel_rag():
        return _ok({"estado": rag.estado(), "tecnicas": list(rag.TECNICAS),
                    "documentos": [{k: d[k] for k in ("id", "titulo", "fuente")}
                                   for d in rag.corpus.documentos()]})

    @app.get("/api/panel/rag/consulta")
    async def panel_rag_consulta(q: str, k: int = 3, umbral: float = 0.12):
        if not q.strip():
            return _error("falta la consulta")
        return _ok(rag.recuperar(q, max(1, min(20, k)), max(0.0, min(1.0, umbral))))

    @app.post("/api/panel/rag/reconstruir")
    async def panel_rag_reconstruir(request: Request):
        return _ok(rag.reconstruir())

    # ── Laboratorio adversarial (detección determinista: no necesita Ollama) ───────────────────────────────
    @app.get("/api/panel/adversarial")
    async def panel_adversarial(vector: str | None = None):
        r = adversarial.campana_deteccion(vector if vector in adversarial.VECTORES else None)
        return _ok({**r, "vectores": list(adversarial.VECTORES)})

    # ── Diagnóstico: catálogo de clases ────────────────────────────────────────────────────────────────────
    @app.get("/api/panel/diagnostico")
    async def panel_diagnostico():
        return _ok({"clases": {k: {"letra": v[0], "severidad": v[1], "componente": v[2],
                                   "cuenta_para_modelo": v[3], "correccion": diagnostico.CORRECCIONES[k]}
                               for k, v in diagnostico.CLASES.items()}})

    # ── Centro de operaciones ──────────────────────────────────────────────────────────────────────────────
    @app.get("/api/panel/soc/alertas")
    async def panel_alertas(nivel: int = 0, limite: int = 100):
        return _ok(wazuh.alertas(nivel_minimo=max(0, nivel), limite=max(1, min(500, limite))))

    @app.get("/api/panel/soc/cronologia")
    async def panel_cronologia(partida: str | None = None, limite: int = 200, fuentes: str | None = None):
        eventos = correlacion.leer_eventos()
        alertas = wazuh.alertas(eventos=eventos, limite=500).get("alertas") or []
        try:
            auditoria = _repo().auditoria(200)
            auditoria = [dict(f) for f in auditoria]
        except Exception:  # noqa: BLE001 - la cronología no debe caerse porque falte la BD
            auditoria = []
        lista = [f.strip() for f in fuentes.split(",")] if fuentes else None
        filas = correlacion.cronologia(eventos, auditoria, alertas, partida, lista,
                                       max(1, min(1000, limite)))
        return _ok({"filas": filas, "fuentes": correlacion.FUENTES, "modo_wazuh": wazuh.modo()})

    @app.get("/api/panel/soc/correlacion")
    async def panel_correlacion(partida: str | None = None):
        incidentes = correlacion.correlacionar(partida=partida)
        return _ok({"incidentes": incidentes, "resumen": correlacion.resumen_correlacion(incidentes),
                    "reglas": [{"nombre": n, "de": o, "a": list(c), "ventana_s": v, "explicacion": e}
                               for n, o, c, v, e in correlacion.REGLAS]})

    # ── Campañas ───────────────────────────────────────────────────────────────────────────────────────────
    @app.get("/api/panel/campana")
    async def panel_campana_estado():
        with _CANDADO:
            obj, hilo = _CAMPANA["obj"], _CAMPANA["hilo"]
            viva = bool(hilo and hilo.is_alive())
            return _ok({
                "en_curso": viva,
                "config": _CAMPANA["config"],
                "lanzada": _CAMPANA["lanzada"],
                "progreso": obj.progreso() if obj else None,
                "error": _CAMPANA["error"],
                "metricas": (_CAMPANA["resultado"] or {}).get("metricas") if not viva else None,
                "modos": {k: {"familias": v[0], "repeticiones": v[1], "descripcion": v[2]}
                          for k, v in mod_campana.MODOS.items()},
                "pipelines": list(mod_campana.PIPELINES),
            })

    @app.post("/api/panel/campana")
    async def panel_campana_lanzar(request: Request):
        cuerpo = await request.json()
        modelo = (cuerpo.get("modelo") or "").strip()
        if not modelo:
            return _error("falta el modelo")
        if not cliente_ollama.ollama_disponible(host_ollama):
            return _error(f"Ollama no responde en {host_ollama}: no se lanza nada", 503)
        if modelo not in cliente_ollama.listar_modelos(host_ollama):
            return _error(f"el modelo «{modelo}» no está instalado en Ollama", 400)
        with _CANDADO:
            if _CAMPANA["hilo"] and _CAMPANA["hilo"].is_alive():
                return _error("ya hay una campaña en curso", 409)
            obj = mod_campana.Campana({})
            cfg = {"modelo": modelo, "modo": cuerpo.get("modo", "rapido"),
                   "tecnica": cuerpo.get("tecnica", "fewshot"),
                   "pipeline": cuerpo.get("pipeline", "directo"),
                   "repeticiones": cuerpo.get("repeticiones"), "semilla": int(cuerpo.get("semilla") or 0),
                   "temperatura": cuerpo.get("temperatura"),
                   "max_segundos": cuerpo.get("max_segundos")}
            _CAMPANA.update(obj=obj, resultado=None, error=None, config=cfg,
                            lanzada=time.strftime("%Y-%m-%dT%H:%M:%S%z"))

            def trabajo():
                try:
                    r = mod_campana.ejecutar(host=host_ollama, repo=repositorio.abrir(":memory:"),
                                             campana=obj, **cfg)
                    _CAMPANA["resultado"] = r
                    experimentos.registrar(r, cuerpo.get("tipo", "exploratorio"), cuerpo.get("notas"),
                                           estado_ollama={"host": host_ollama})
                except Exception as exc:  # noqa: BLE001
                    _CAMPANA["error"] = f"{type(exc).__name__}: {exc}"

            hilo = threading.Thread(target=trabajo, daemon=True)
            _CAMPANA["hilo"] = hilo
            hilo.start()
        return _ok({"lanzada": True, "config": cfg})

    # ── Resistencia del modelo y capacidad del atacante (Fase E; exigen Ollama) ────────────────────────────
    # Las tres medidas se publican por rutas distintas a propósito. Mezclarlas en una sola sería volver al
    # error que el encargo señala: confundir lo que detecta el filtro con lo que resiste el modelo.
    @app.get("/api/panel/adversarial/modelo")
    async def panel_adversarial_modelo():
        with _CANDADO:
            e = _MEDICION["modelo"]
            viva = bool(e["hilo"] and e["hilo"].is_alive())
            return _ok({"en_curso": viva, "config": e["config"], "lanzada": e["lanzada"],
                        "error": e["error"], "progreso": e["progreso"],
                        "resultado": None if viva else e["resultado"],
                        "nota": ("Mide el MODELO defensor sin el filtro rápido delante. No es la resistencia "
                                 "del sistema: esa es /api/panel/adversarial (filtro) junto con las capas.")})

    @app.post("/api/panel/adversarial/modelo")
    async def panel_adversarial_modelo_lanzar(request: Request):
        cuerpo = await request.json()
        modelo, err = _modelo_valido(cuerpo)
        if err:
            return err
        rol = cuerpo.get("rol") or "empleado"
        if rol not in permisos.ROLES:
            return _error(f"rol desconocido: {rol}")
        reps = max(1, min(int(cuerpo.get("repeticiones") or 1), 10))

        def trabajo():
            from src.lab import defensor
            return adversarial.campana_modelo(
                defensor.analizar, host_ollama, modelo, permisos.Identidad(f"eval.{rol}", rol),
                vector=cuerpo.get("vector") if cuerpo.get("vector") in adversarial.VECTORES else None,
                repeticiones=reps, tecnica=cuerpo.get("tecnica", "fewshot"),
                temperatura=cuerpo.get("temperatura"),
                al_avanzar=lambda n, f: _MEDICION["modelo"].__setitem__(
                    "progreso", {"hechas": n, "planificadas": reps * len(adversarial.casos())}))
        return _lanzar("modelo", {"modelo": modelo, "rol": rol, "repeticiones": reps,
                                  "tecnica": cuerpo.get("tecnica", "fewshot"),
                                  "sin_filtro_rapido": True}, trabajo)

    @app.get("/api/panel/adversarial/atacante")
    async def panel_atacante():
        with _CANDADO:
            e = _MEDICION["atacante"]
            viva = bool(e["hilo"] and e["hilo"].is_alive())
            return _ok({"en_curso": viva, "config": e["config"], "lanzada": e["lanzada"],
                        "error": e["error"], "progreso": e["progreso"],
                        "resultado": None if viva else e["resultado"],
                        "nota": ("«Objetivo conseguido» se mide sobre la ejecución (datos que salieron), "
                                 "nunca sobre lo que diga el modelo atacante.")})

    @app.post("/api/panel/adversarial/atacante")
    async def panel_atacante_lanzar(request: Request):
        cuerpo = await request.json()
        modelo_atq, err = _modelo_valido(cuerpo, "modelo_atacante")
        if err:
            return err
        modelo_def, err = _modelo_valido(cuerpo, "modelo_defensor")
        if err:
            return err
        rol = cuerpo.get("rol") or "empleado"
        if rol not in permisos.ROLES:
            return _error(f"rol desconocido: {rol}")
        rondas = max(1, min(int(cuerpo.get("rondas") or 10), 60))
        esc = cuerpo.get("escenario")
        if esc is not None and esc not in atacante.ESCENARIOS:
            return _error(f"escenario desconocido: {esc}")

        def trabajo():
            from src.lab import motor
            return adversarial.campana_atacante(
                motor.ejecutar_ronda, host_ollama, modelo_atq, modelo_def,
                permisos.Identidad(f"eval.{rol}", rol), repositorio.abrir(":memory:"), rondas=rondas,
                escenario=esc, intensidad=max(1, min(int(cuerpo.get("intensidad") or 2), 3)),
                al_avanzar=lambda n, f: _MEDICION["atacante"].__setitem__(
                    "progreso", {"hechas": n, "planificadas": rondas}))
        return _lanzar("atacante", {"modelo_atacante": modelo_atq, "modelo_defensor": modelo_def,
                                    "rol": rol, "rondas": rondas, "escenario": esc}, trabajo)

    @app.post("/api/panel/adversarial/cancelar")
    async def panel_medicion_cancelar(request: Request):
        """Las mediciones no se pueden abortar a mitad de una inferencia sin matar un hilo, y eso no se hace
        aquí. Lo que sí se puede es decir con honestidad que no hay nada que cancelar."""
        with _CANDADO:
            vivas = [k for k, e in _MEDICION.items() if e["hilo"] and e["hilo"].is_alive()]
        if not vivas:
            return _error("no hay ninguna medición en curso", 409)
        return _error("una medición en curso no se interrumpe a mitad de una inferencia: espere a que "
                      f"termine ({', '.join(vivas)}) o reinicie el servidor", 409)

    # ── Campañas por lotes, reanudables ───────────────────────────────────────────────────────────────────
    @app.get("/api/panel/lotes")
    async def panel_lotes():
        with _CANDADO:
            e = _MEDICION["lote"]
            viva = bool(e["hilo"] and e["hilo"].is_alive())
        return _ok({"en_curso": viva, "config": e["config"], "error": e["error"],
                    "progreso": e["progreso"], "resultado": None if viva else e["resultado"],
                    "campanas": lotes.listar(),
                    "nota": ("Una campaña por lotes se reanuda con el mismo id y la misma configuración. "
                             "Reanudar con otro plan u otra condición se rechaza.")})

    @app.get("/api/panel/lotes/{id_campana}")
    async def panel_lote(id_campana: str):
        try:
            return _ok(lotes.resultado(id_campana))
        except lotes.ErrorLote as exc:
            return _error(str(exc), 404)

    @app.post("/api/panel/lotes")
    async def panel_lotes_lanzar(request: Request):
        """Ejecuta UN lote. Si no se pasa `id`, crea la campaña; si se pasa, la reanuda."""
        cuerpo = await request.json()
        modelo, err = _modelo_valido(cuerpo)
        if err:
            return err
        cfg = {"modelo": modelo, "modo": cuerpo.get("modo", "rapido"),
               "tecnica": cuerpo.get("tecnica", "fewshot"), "pipeline": cuerpo.get("pipeline", "directo"),
               "familias": cuerpo.get("familias"), "repeticiones": cuerpo.get("repeticiones"),
               "semilla": int(cuerpo.get("semilla") or 0), "temperatura": cuerpo.get("temperatura"),
               "solo_verificables": bool(cuerpo.get("solo_verificables")), "host": host_ollama}
        id_campana = cuerpo.get("id") or None
        max_rondas = cuerpo.get("max_rondas")
        max_segundos = cuerpo.get("max_segundos")

        def trabajo():
            return lotes.ejecutar_lote(
                id_campana, cfg,
                max_rondas=None if max_rondas is None else max(1, int(max_rondas)),
                max_segundos=None if max_segundos is None else max(1.0, float(max_segundos)),
                repo=repositorio.abrir(":memory:"),
                al_avanzar=lambda prog, ronda: _MEDICION["lote"].__setitem__("progreso", prog))
        return _lanzar("lote", {**cfg, "id": id_campana, "max_rondas": max_rondas,
                                "max_segundos": max_segundos}, trabajo)

    @app.post("/api/panel/campana/cancelar")
    async def panel_campana_cancelar(request: Request):
        with _CANDADO:
            if not (_CAMPANA["obj"] and _CAMPANA["hilo"] and _CAMPANA["hilo"].is_alive()):
                return _error("no hay ninguna campaña en curso", 409)
            _CAMPANA["obj"].cancelar()
        return _ok({"cancelando": True})

    return app
