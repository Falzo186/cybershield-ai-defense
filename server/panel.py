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

from src.lab import (adversarial, cliente_ollama, correlacion, diagnostico, experimentos, harness,
                     permisos, rag, repositorio, wazuh)
from src.lab.evaluacion import campana as mod_campana, escenarios, metricas

# Estado de la campaña en curso (una a la vez: dos campañas simultáneas se pisarían la GPU y las cifras).
_CAMPANA = {"obj": None, "hilo": None, "resultado": None, "error": None, "lanzada": None, "config": None}
_CANDADO = threading.Lock()


def _ok(datos):
    return JSONResponse(datos)


def _error(mensaje, status=400):
    return JSONResponse({"error": mensaje}, status_code=status)


def registrar(app, host_ollama, repo_por_defecto=None):
    """Monta las rutas del panel en la app existente. `host_ollama` es el mismo que usa la partida."""

    def _repo():
        return repo_por_defecto() if callable(repo_por_defecto) else repositorio.por_defecto()

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

    @app.post("/api/panel/campana/cancelar")
    async def panel_campana_cancelar(request: Request):
        with _CANDADO:
            if not (_CAMPANA["obj"] and _CAMPANA["hilo"] and _CAMPANA["hilo"].is_alive()):
                return _error("no hay ninguna campaña en curso", 409)
            _CAMPANA["obj"].cancelar()
        return _ok({"cancelando": True})

    return app
