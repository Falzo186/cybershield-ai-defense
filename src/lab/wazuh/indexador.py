"""Lectura de alertas del **indexador** de Wazuh (OpenSearch). Solo lectura.

Por qué un cliente aparte de `cliente.py`: son dos servicios distintos. La API del manager
(`https://localhost:55000`) responde estado, agentes y reglas; las alertas viven en el indexador
(`https://localhost:9200`), que es un OpenSearch con los índices `wazuh-alerts-*`. Tienen puerto,
autenticación y formato de respuesta distintos, y mezclar los dos en una clase habría obligado a relajar
las reglas de la primera.

Reglas duras de este módulo:
  - **Solo lectura.** Las únicas rutas permitidas son `_search` y `_count` sobre índices `wazuh-alerts-*`,
    más `/` (el saludo del nodo, para comprobar la conexión). Cualquier otra se rechaza ANTES de salir a la
    red. No hay forma de escribir, borrar un índice ni modificar configuración desde aquí.
  - Una búsqueda es una lectura **aunque el método HTTP sea POST**: la consulta viaja en el cuerpo porque
    OpenSearch lo exige. Esa es la única excepción al «solo GET», es explícita y está acotada a `_search` y
    `_count`.
  - **Nunca inventa alertas.** Sin conexión devuelve `ok=False` con el error; jamás una alerta de relleno.
  - Toda alerta que sale de aquí va marcada `simulado=False` y `origen="wazuh_real"`, y solo puede salir de
    aquí si vino del indexador.
  - Las credenciales se leen del entorno y no se registran en ningún log ni se devuelven en ninguna
    estructura.

**No ha sido probado contra una instalación real**: no hay ninguna en esta máquina. Lo comprobado son los
contratos (rutas, cuerpo de la consulta, cabeceras, normalización y manejo de errores) con un transporte
sustituido, más una prueba de integración que solo se ejecuta cuando hay un indexador configurado
(`integraciones/wazuh/test_indexador_real.py`). Ver `docs/INTEGRACION_WAZUH.md` para los requisitos.
"""
import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.request

from .cliente import ErrorWazuh, _contexto

URL_POR_DEFECTO = "https://localhost:9200"
INDICE = "wazuh-alerts-*"
TIMEOUT = 15
MAX_RESULTADOS = 500          # techo duro: una consulta del panel nunca pide más
# Sufijos de ruta permitidos. Todo lo demás se rechaza antes de abrir el socket.
OPERACIONES = ("_search", "_count")


def _credenciales():
    """Del entorno, con respaldo en las del manager cuando el indexador comparte usuario."""
    return (os.environ.get("WAZUH_INDEXER_USUARIO") or os.environ.get("WAZUH_USUARIO") or "",
            os.environ.get("WAZUH_INDEXER_CLAVE") or os.environ.get("WAZUH_CLAVE") or "")


def configurado():
    """¿Hay credenciales para el indexador? Sin ellas no se intenta ninguna conexión."""
    u, c = _credenciales()
    return bool(u and c)


class ClienteIndexador:
    """Cliente de solo lectura del indexador. `transporte` se sustituye en las pruebas."""

    def __init__(self, url=None, usuario=None, clave=None, verificar_tls=True, timeout=TIMEOUT,
                 indice=None, transporte=None):
        self.url = (url or os.environ.get("WAZUH_INDEXER_URL") or URL_POR_DEFECTO).rstrip("/")
        env_u, env_c = _credenciales()
        self._usuario = usuario or env_u
        self._clave = clave or env_c
        self.verificar_tls = verificar_tls
        self.timeout = timeout
        self.indice = indice or os.environ.get("WAZUH_INDEXER_INDICE") or INDICE
        self._transporte = transporte
        self.ultimo_error = None

    # ── Transporte ─────────────────────────────────────────────────────────────────────────────────────────
    def _ruta_permitida(self, ruta):
        base = ruta.split("?", 1)[0].rstrip("/")
        if base in ("", "/"):
            return True                      # saludo del nodo: comprobar conexión y versión
        return any(base.endswith("/" + op) for op in OPERACIONES)

    def _peticion(self, metodo, ruta, cuerpo=None):
        """Único punto de salida a la red."""
        if metodo not in ("GET", "POST"):
            raise ErrorWazuh(f"este cliente es de solo lectura: {metodo} no está permitido")
        if not self._ruta_permitida(ruta):
            raise ErrorWazuh(f"ruta no permitida por el cliente de solo lectura del indexador: {ruta}")
        if metodo == "POST" and not any(ruta.split("?", 1)[0].rstrip("/").endswith("/" + op)
                                        for op in OPERACIONES):
            raise ErrorWazuh("POST solo está permitido para una búsqueda (_search / _count)")
        if not self._usuario or not self._clave:
            raise ErrorWazuh("faltan credenciales del indexador (WAZUH_INDEXER_USUARIO / "
                             "WAZUH_INDEXER_CLAVE)")
        basico = base64.b64encode(f"{self._usuario}:{self._clave}".encode()).decode()
        cabeceras = {"Authorization": "Basic " + basico, "Content-Type": "application/json"}
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        if self._transporte:
            return self._transporte(metodo, self.url + ruta, cabeceras, datos)
        req = urllib.request.Request(self.url + ruta, data=datos, method=metodo, headers=cabeceras)
        with urllib.request.urlopen(req, timeout=self.timeout,
                                    context=_contexto(self.verificar_tls)) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def _buscar(self, cuerpo):
        estado, datos = self._peticion("POST", f"/{self.indice}/_search", cuerpo)
        if estado != 200:
            raise ErrorWazuh(f"HTTP {estado} al consultar el indexador")
        return datos

    def _intentar(self, fn):
        """Envuelve una consulta: nunca lanza hacia fuera, nunca devuelve datos inventados."""
        t0 = time.perf_counter()
        try:
            datos = fn()
            self.ultimo_error = None
            return {"ok": True, "datos": datos, "error": None,
                    "ms": int((time.perf_counter() - t0) * 1000)}
        except Exception as exc:  # noqa: BLE001
            self.ultimo_error = f"{type(exc).__name__}: {exc}"
            return {"ok": False, "datos": None, "error": self.ultimo_error,
                    "ms": int((time.perf_counter() - t0) * 1000)}

    # ── Consultas ──────────────────────────────────────────────────────────────────────────────────────────
    def consulta(self, nivel_minimo=0, limite=100, desde=None, grupo=None, partida=None):
        """Cuerpo de la búsqueda. Está aparte para poder comprobarlo sin red.

        Se piden solo los campos que el panel usa (`_source`), se ordena por fecha descendente y el tamaño
        está acotado por MAX_RESULTADOS: una consulta del laboratorio no puede vaciar el indexador."""
        filtros = []
        if nivel_minimo:
            filtros.append({"range": {"rule.level": {"gte": int(nivel_minimo)}}})
        if desde:
            filtros.append({"range": {"@timestamp": {"gte": desde}}})
        if grupo:
            filtros.append({"term": {"rule.groups": str(grupo)}})
        if partida:
            filtros.append({"term": {"data.partida": str(partida)}})
        return {
            "size": max(1, min(int(limite), MAX_RESULTADOS)),
            "sort": [{"@timestamp": {"order": "desc"}}],
            "query": {"bool": {"filter": filtros}} if filtros else {"match_all": {}},
            "_source": ["@timestamp", "timestamp", "rule.id", "rule.level", "rule.description",
                        "rule.groups", "rule.mitre.id", "agent.name", "agent.id", "manager.name",
                        "data", "full_log"],
        }

    def alertas(self, nivel_minimo=0, limite=100, desde=None, grupo=None, partida=None):
        """-> {ok, alertas, total, error, ms}. Las alertas vienen ya normalizadas y marcadas como reales."""
        r = self._intentar(lambda: self._buscar(self.consulta(nivel_minimo, limite, desde, grupo, partida)))
        if not r["ok"]:
            return {"ok": False, "alertas": [], "total": None, "error": r["error"], "ms": r["ms"]}
        datos = r["datos"] or {}
        hits = ((datos.get("hits") or {}).get("hits")) or []
        total = (datos.get("hits") or {}).get("total")
        if isinstance(total, dict):
            total = total.get("value")
        return {"ok": True, "alertas": [normalizar(h) for h in hits], "total": total,
                "error": None, "ms": r["ms"]}

    def comprobar(self):
        """Prueba de conexión. -> {conectado, version, indice, error, ms}. Nunca lanza."""
        r = self._intentar(lambda: self._peticion("GET", "/")[1])
        version = (((r.get("datos") or {}).get("version")) or {}).get("number") if r["ok"] else None
        return {"conectado": bool(r["ok"]), "version": version, "indice": self.indice,
                "error": r["error"], "ms": r["ms"]}


def _hondo(d, camino, por_defecto=None):
    """Lee `a.b.c` de un dict anidado sin lanzar. OpenSearch devuelve unos campos planos y otros anidados."""
    actual = d
    for parte in camino.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            return por_defecto
        actual = actual[parte]
    return actual if actual is not None else por_defecto


def normalizar(hit):
    """Un documento del indexador -> la MISMA forma que una alerta del laboratorio.

    Que la forma coincida es lo que permite pintar las dos en la misma tabla. Lo que NUNCA coincide es la
    marca: aquí `simulado` es False y `origen` es "wazuh_real", y ninguna alerta simulada puede entrar por
    esta función porque solo se llama con un documento del indexador.

    Un campo que el documento no traiga queda en None, no en un valor inventado."""
    f = (hit or {}).get("_source") or {}
    datos = f.get("data") if isinstance(f.get("data"), dict) else {}
    mitre = _hondo(f, "rule.mitre.id", [])
    grupos = _hondo(f, "rule.groups", [])
    nivel = _hondo(f, "rule.level")
    regla_id = _hondo(f, "rule.id")
    try:
        nivel = int(nivel) if nivel is not None else None
    except (TypeError, ValueError):
        nivel = None
    try:
        regla_id = int(regla_id) if regla_id is not None else None
    except (TypeError, ValueError):
        pass                                  # un id no numérico se deja tal cual: es dato del indexador
    return {
        "timestamp": f.get("@timestamp") or f.get("timestamp") or datos.get("timestamp"),
        "regla_id": regla_id,
        "nivel": nivel,
        "descripcion": _hondo(f, "rule.description"),
        "grupos": list(grupos) if isinstance(grupos, (list, tuple)) else [grupos] if grupos else [],
        "mitre": list(mitre) if isinstance(mitre, (list, tuple)) else [mitre] if mitre else [],
        "agente": _hondo(f, "agent.name") or datos.get("origen"),
        "agente_id": _hondo(f, "agent.id"),
        "usuario": datos.get("usuario"), "rol": datos.get("rol"), "equipo": datos.get("equipo"),
        "tipo": datos.get("tipo"), "recurso": datos.get("recurso"),
        "resultado": datos.get("resultado"), "riesgo": datos.get("riesgo"),
        "correlacion": datos.get("partida"),
        "indice": (hit or {}).get("_index"),
        "documento": (hit or {}).get("_id"),
        "origen": "wazuh_real",
        "simulado": False,
    }
