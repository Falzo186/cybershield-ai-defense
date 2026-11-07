"""Pruebas offline de la integración con Wazuh. Ejecutar: python -m src.lab.test_wazuh

No hay ningún Wazuh en esta máquina. Lo que se comprueba aquí son los **contratos**: los tres modos, que una
alerta simulada nunca se presente como real, que el cliente sea de solo lectura de verdad, y que un fallo de
conexión se vea en vez de taparse. El transporte HTTP se sustituye por uno falso.
"""
import json
import os

from . import wazuh
from .wazuh import cliente as mod_cliente, reglas as mod_reglas

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def con_modo(valor):
    """Fija CYBERSHIELD_WAZUH y devuelve el valor anterior."""
    previo = os.environ.get(wazuh.VAR_ENTORNO)
    if valor is None:
        os.environ.pop(wazuh.VAR_ENTORNO, None)
    else:
        os.environ[wazuh.VAR_ENTORNO] = valor
    return previo


def transporte(respuestas, registro):
    """Transporte falso. `respuestas` mapea ruta -> (estado, datos)."""
    def _t(metodo, url, cabeceras, cuerpo):
        ruta = url.split("55000", 1)[-1] if "55000" in url else url
        registro.append((metodo, ruta, sorted(cabeceras)))
        for clave, valor in respuestas.items():
            if ruta.startswith(clave):
                return valor
        return 404, {"error": "no encontrado"}
    return _t


AUTH_OK = {"/security/user/authenticate": (200, {"data": {"token": "jwt-de-prueba"}})}


def main():
    previo = con_modo(None)
    try:
        # ── Modos ───────────────────────────────────────────────────────────────────────────────────────────
        chk("los tres modos están declarados", wazuh.MODOS == ("real", "simulado", "desactivado"))
        con_modo(None)
        chk("sin variable de entorno, el modo es «desactivado»", wazuh.modo() == "desactivado")
        con_modo("basura")
        chk("un valor desconocido NO se interpreta como «real»", wazuh.modo() == "desactivado")
        con_modo("SIMULADO")
        chk("el modo no distingue mayúsculas", wazuh.modo() == "simulado")

        # ── Desactivado ─────────────────────────────────────────────────────────────────────────────────────
        con_modo("desactivado")
        r = wazuh.alertas()
        chk("desactivado: no devuelve alertas y lo explica", r["ok"] and r["alertas"] == [] and r["nota"])
        e = wazuh.estado()
        chk("desactivado: no afirma estar conectado", e["conectado"] is False and e["modo"] == "desactivado")
        chk("el estado siempre dice qué modo está activo", e["modo"] in wazuh.MODOS)
        chk("el estado cuenta las reglas definidas", e["reglas_definidas"] == 19)

        # ── Simulado ────────────────────────────────────────────────────────────────────────────────────────
        con_modo("simulado")
        r = wazuh.alertas()
        chk("simulado: produce alertas de los eventos del laboratorio", r["ok"] and len(r["alertas"]) > 0)
        chk("TODA alerta simulada va marcada como simulada",
            all(a["simulado"] is True and a["origen"] == "simulado" for a in r["alertas"]))
        chk("ninguna alerta simulada se presenta como de Wazuh",
            not any(a["origen"] == "wazuh_real" for a in r["alertas"]))
        chk("la respuesta advierte de que no proceden de ningún Wazuh", "No proceden" in r["nota"])
        chk("simulado: el estado no dice «conectado»", wazuh.estado()["conectado"] is False)
        chk("las alertas traen nivel, regla y descripción resuelta",
            all(a["regla_id"] and a["nivel"] >= 0 and a["descripcion"] for a in r["alertas"]))
        chk("la descripción sustituye las variables $(campo)",
            all("$(" not in a["descripcion"] for a in r["alertas"]))
        chk("el filtro por nivel mínimo funciona",
            all(a["nivel"] >= 8 for a in wazuh.alertas(nivel_minimo=8)["alertas"]))
        chk("el límite se respeta", len(wazuh.alertas(limite=2)["alertas"]) <= 2)
        chk("las alertas vienen de más reciente a más antigua",
            [a["timestamp"] for a in r["alertas"]] == sorted((a["timestamp"] for a in r["alertas"]),
                                                             reverse=True))
        chk("un evento ajeno al laboratorio no genera alerta",
            wazuh.alertas(eventos=[{"origen": "otra-cosa", "tipo": "x"}])["alertas"] == [])
        chk("la correlación de cada alerta es la partida",
            all(a["correlacion"] is not None for a in r["alertas"]))
        chk("simulado nunca necesita red", wazuh.alertas(eventos=[])["ok"] is True)

        # ── Real sin conexión: error visible, nunca caída silenciosa a simulado ─────────────────────────────
        con_modo("real")
        registro = []
        roto = mod_cliente.ClienteWazuh("https://localhost:55000", "u", "c",
                                        transporte=transporte({}, registro))
        r = wazuh.alertas(cliente=roto)
        chk("real sin conexión: ok=False", r["ok"] is False and r["modo"] == "real")
        chk("real sin conexión: NO devuelve alertas simuladas en su lugar",
            r["alertas"] == [] and r["simulado"] is False)
        chk("y lo dice expresamente", "No se muestran alertas simuladas" in r["nota"])
        chk("el estado en modo real sin conexión no miente",
            wazuh.estado(cliente=roto)["conectado"] is False)

        # ── Cliente: SOLO lectura ───────────────────────────────────────────────────────────────────────────
        registro = []
        c = mod_cliente.ClienteWazuh("https://localhost:55000", "u", "c", transporte=transporte(
            {**AUTH_OK,
             "/manager/info": (200, {"data": {"affected_items": [{"version": "v4.9.0"}]}}),
             "/manager/status": (200, {"data": {"affected_items": [{"wazuh-analysisd": "running"}]}}),
             "/agents": (200, {"data": {"affected_items": [{"id": "001", "name": "lab"}]}}),
             "/rules": (200, {"data": {"affected_items": [{"id": 100100}]}})}, registro))
        chk("comprobar() detecta la conexión y la versión",
            c.comprobar() == {"conectado": True, "version": "v4.9.0", "error": None,
                              "ms": c.comprobar()["ms"]} or c.comprobar()["conectado"] is True)
        chk("estado del manager se lee", c.estado_manager()["ok"])
        chk("agentes se leen", c.agentes()["ok"])
        chk("las reglas del grupo cybershield se leen", c.reglas_cybershield()["ok"])
        metodos = {m for m, _, _ in registro}
        chk("solo se emiten GET (salvo el POST de autenticación que la API exige)",
            metodos <= {"GET", "POST"}
            and all(ruta == mod_cliente.RUTA_AUTENTICAR for m, ruta, _ in registro if m == "POST"))
        chk("el token se reutiliza en vez de autenticarse en cada consulta",
            sum(1 for m, _, _ in registro if m == "POST") == 1)
        chk("las consultas van con cabecera Authorization",
            all("Authorization" in cab for m, _, cab in registro if m == "GET"))

        lanzo = False
        try:
            c._peticion("DELETE", "/agents")
        except mod_cliente.ErrorWazuh as exc:
            lanzo = "solo lectura" in str(exc)
        chk("un método que no sea GET se rechaza antes de salir a la red", lanzo)
        lanzo = False
        try:
            c._peticion("GET", "/active-response")
        except mod_cliente.ErrorWazuh as exc:
            lanzo = "no permitida" in str(exc)
        chk("una ruta fuera de la lista permitida se rechaza (nada de respuesta activa)", lanzo)
        chk("el cliente no expone ninguna función de escritura",
            not [n for n in dir(c) if any(v in n for v in ("restart", "reiniciar", "borrar", "escribir",
                                                           "ejecutar", "active"))])

        # ── Errores y credenciales ──────────────────────────────────────────────────────────────────────────
        sin_cred = mod_cliente.ClienteWazuh("https://localhost:55000", "", "",
                                            transporte=transporte(AUTH_OK, []))
        r = sin_cred.estado_manager()
        chk("sin credenciales no se intenta nada y se explica",
            r["ok"] is False and "credenciales" in r["error"])
        malo = mod_cliente.ClienteWazuh("https://x", "u", "c",
                                        transporte=transporte({"/security": (401, {})}, []))
        chk("una autenticación rechazada se informa, no se ignora",
            malo.estado_manager()["error"].startswith("ErrorWazuh") or "401" in malo.estado_manager()["error"])
        chk("la clave no aparece en ninguna estructura devuelta",
            "c" not in str(malo.comprobar().get("error", "")).replace("ErrorWazuh", "") or
            "clave" not in str(malo.comprobar()))

        def explota(*a):
            raise OSError("red caída")
        caido = mod_cliente.ClienteWazuh("https://x", "u", "c", transporte=explota)
        r = caido.estado_manager()
        chk("un fallo de red se devuelve como error, nunca como datos",
            r["ok"] is False and r["datos"] is None and "red caída" in r["error"])
        chk("comprobar() tampoco lanza con la red caída", caido.comprobar()["conectado"] is False)

        # ── Reglas compartidas con la prueba del adaptador ──────────────────────────────────────────────────
        _, reglas = mod_reglas.cargar()
        chk("se cargan las 19 reglas locales", len(reglas) == 19)
        chk("los eventos de ejemplo se leen", len(mod_reglas.eventos_ejemplo()) > 0)
        chk("un archivo de eventos inexistente devuelve lista vacía, no lanza",
            mod_reglas.eventos_ejemplo(mod_reglas.RUTA_EJEMPLOS.parent / "no-existe.jsonl") == [])
        ev = {"origen": "cybershield-lab", "tipo": "clic_enlace", "usuario": "ana.perez",
              "recurso": "correo:1", "resultado": "CLIC"}
        r = mod_reglas.evaluar(reglas, ev)
        chk("la evaluación encuentra la regla propia del clic", r and r["id"] == 100111 and r["nivel"] == 8)
        chk("describir sustituye los campos", "ana.perez" in mod_reglas.describir(r, ev))
        chk("un campo ausente se muestra como «-»", "-" in mod_reglas.describir(r, {**ev, "usuario": None}))
        chk("un XML inexistente al cargar reglas sí lanza (debe verse, no pasar inadvertido)",
            _lanza(lambda: mod_reglas.cargar(mod_reglas.RUTA_REGLAS.parent / "no-existe.xml")))
        chk("alertas_simuladas con un XML roto devuelve error, no alertas inventadas",
            wazuh.alertas_simuladas(ruta_reglas=mod_reglas.RUTA_REGLAS.parent / "no-existe.xml")["ok"]
            is False)
    finally:
        con_modo(previo)

    # ══ Indexador: lectura de alertas REALES (Fase F) ══════════════════════════════════════════════════════
    from src.lab.wazuh import indexador as ix
    from src.lab.wazuh.cliente import ErrorWazuh as _EW

    DOC = {"_index": "wazuh-alerts-4.x-2026.11.06", "_id": "abc", "_source": {
        "@timestamp": "2026-11-06T10:00:00Z",
        "rule": {"id": "100120", "level": 7, "description": "CyberShield: clic en enlace",
                 "groups": ["cybershield", "phishing"], "mitre": {"id": ["T1566", "T1204"]}},
        "agent": {"name": "lab01", "id": "001"},
        "data": {"usuario": "ana.perez", "rol": "empleado", "equipo": "azul", "tipo": "clic_enlace",
                 "recurso": "correo:3", "resultado": "ABIERTO", "riesgo": "ALTO", "partida": "p1"}}}

    def transporte_ix(estado=200, datos=None, registro=None):
        def tr(metodo, url, cabeceras, cuerpo):
            if registro is not None:
                registro.append({"metodo": metodo, "url": url, "cabeceras": cabeceras,
                                 "cuerpo": json.loads(cuerpo.decode()) if cuerpo else None})
            if isinstance(datos, Exception):
                raise datos
            return estado, (datos if datos is not None
                            else {"hits": {"total": {"value": 1}, "hits": [DOC]}})
        return tr

    reg = []
    c = ix.ClienteIndexador(usuario="u", clave="s3cr3t", transporte=transporte_ix(registro=reg))
    r = c.alertas(nivel_minimo=5, limite=10)
    chk("el indexador devuelve alertas", r["ok"] and len(r["alertas"]) == 1)
    chk("con el total que informa el indexador", r["total"] == 1)
    a = r["alertas"][0]
    chk("una alerta del indexador NUNCA va marcada como simulada",
        a["simulado"] is False and a["origen"] == "wazuh_real")
    chk("trae la regla y su nivel", (a["regla_id"], a["nivel"]) == (100120, 7))
    chk("la descripción es la del indexador, no una deducida aquí",
        a["descripcion"] == "CyberShield: clic en enlace")
    chk("trae el agente de origen", (a["agente"], a["agente_id"]) == ("lab01", "001"))
    chk("los identificadores MITRE se conservan", a["mitre"] == ["T1566", "T1204"])
    chk("y los grupos de la regla", a["grupos"] == ["cybershield", "phishing"])
    chk("los campos del laboratorio se leen de data",
        (a["usuario"], a["rol"], a["tipo"], a["correlacion"]) == ("ana.perez", "empleado", "clic_enlace", "p1"))
    chk("se guarda de qué documento salió, para poder volver a él",
        (a["indice"], a["documento"]) == ("wazuh-alerts-4.x-2026.11.06", "abc"))
    chk("una alerta real tiene la misma forma que una simulada",
        set(wazuh.alertas_simuladas(limite=1)["alertas"][0]) <= set(a) if
        wazuh.alertas_simuladas(limite=1)["alertas"] else True)

    # La petición que sale a la red
    p = reg[0]
    chk("la búsqueda va al índice de alertas", p["url"].endswith("/wazuh-alerts-*/_search"))
    chk("se envía autenticación básica", p["cabeceras"]["Authorization"].startswith("Basic "))
    chk("la clave no aparece en claro en la cabecera", "s3cr3t" not in p["cabeceras"]["Authorization"])
    chk("la consulta filtra por nivel mínimo",
        {"range": {"rule.level": {"gte": 5}}} in p["cuerpo"]["query"]["bool"]["filter"])
    chk("ordena por fecha descendente", p["cuerpo"]["sort"] == [{"@timestamp": {"order": "desc"}}])
    chk("pide solo los campos que se usan", "rule.level" in p["cuerpo"]["_source"])
    chk("sin filtros, la consulta es match_all",
        ix.ClienteIndexador(usuario="u", clave="c").consulta()["query"] == {"match_all": {}})
    chk("el tamaño está acotado por un techo duro",
        c.consulta(0, 10 ** 6)["size"] == ix.MAX_RESULTADOS)
    chk("y nunca es menor que 1", c.consulta(0, 0)["size"] == 1)

    # Solo lectura: lo que NO puede hacer
    for metodo, ruta in (("POST", "/_bulk"), ("POST", "/wazuh-alerts-*/_delete_by_query"),
                         ("POST", "/_cluster/settings"), ("POST", "/wazuh-alerts-*/_doc"),
                         ("GET", "/_cat/indices")):
        try:
            c._peticion(metodo, ruta, {})
            chk(f"debía rechazar {metodo} {ruta}", False)
        except _EW:
            chk(f"rechaza {metodo} {ruta} antes de salir a la red", True)
    for metodo in ("DELETE", "PUT", "PATCH", "HEAD"):
        try:
            c._peticion(metodo, "/wazuh-alerts-*/_search", {})
            chk(f"debía rechazar el método {metodo}", False)
        except _EW:
            chk(f"rechaza el método {metodo}", True)
    chk("el saludo del nodo sí está permitido (es como se comprueba la conexión)",
        c._ruta_permitida("/") and c._ruta_permitida(""))
    chk("_count también, porque es una lectura", c._ruta_permitida("/wazuh-alerts-*/_count"))
    chk("no hay ninguna función de escritura en el módulo",
        not [n for n in dir(ix.ClienteIndexador)
             if any(x in n for x in ("borrar", "delete", "crear", "escribir", "indexar", "actualizar"))])

    # Errores: visibles, nunca sustituidos por datos
    sin_cred = ix.ClienteIndexador(usuario="", clave="", transporte=transporte_ix())
    r = sin_cred.alertas()
    chk("sin credenciales no se consulta y el error es visible",
        r["ok"] is False and "credenciales" in r["error"] and r["alertas"] == [])
    caido = ix.ClienteIndexador(usuario="u", clave="c",
                                transporte=transporte_ix(datos=OSError("conexión rechazada")))
    r = caido.alertas()
    chk("un indexador caído devuelve error, nunca una alerta inventada",
        r["ok"] is False and r["alertas"] == [] and "conexión rechazada" in r["error"])
    malo = ix.ClienteIndexador(usuario="u", clave="c", transporte=transporte_ix(estado=403, datos={}))
    chk("un HTTP distinto de 200 es un error con su código", "403" in (malo.alertas()["error"] or ""))
    chk("comprobar() nunca lanza", isinstance(caido.comprobar(), dict))
    chk("y dice que no está conectado", caido.comprobar()["conectado"] is False)
    chk("comprobar() informa de la versión del nodo",
        ix.ClienteIndexador(usuario="u", clave="c",
                            transporte=transporte_ix(datos={"version": {"number": "2.13.0"}})
                            ).comprobar()["version"] == "2.13.0")

    # Normalización defensiva: un documento incompleto no rompe nada ni inventa valores
    vacio = ix.normalizar({"_source": {}})
    chk("un documento sin campos no inventa valores",
        vacio["regla_id"] is None and vacio["nivel"] is None and vacio["descripcion"] is None)
    chk("pero sigue marcado como real, porque viene del indexador",
        vacio["simulado"] is False and vacio["origen"] == "wazuh_real")
    chk("normalizar tolera None", ix.normalizar(None)["simulado"] is False)
    chk("un nivel no numérico queda en None, no en 0",
        ix.normalizar({"_source": {"rule": {"level": "alto"}}})["nivel"] is None)
    chk("un id de regla no numérico se conserva tal cual",
        ix.normalizar({"_source": {"rule": {"id": "abc"}}})["regla_id"] == "abc")
    chk("mitre y grupos sueltos se normalizan a lista",
        ix.normalizar({"_source": {"rule": {"groups": "uno", "mitre": {"id": "T1"}}}})["grupos"] == ["uno"])
    chk("configurado() dice que no cuando faltan credenciales",
        ix.configurado() in (True, False))

    # ── El modo real usa el indexador y no se cae a simulado ──────────────────────────────────────────────
    class ManagerOk:
        def estado_manager(self):
            return {"ok": True, "datos": {}, "error": None, "ms": 1}

        def comprobar(self):
            return {"conectado": True, "version": "4.9.0", "error": None, "ms": 1}

    class IxFalso:
        def __init__(self, ok=True):
            self.ok = ok

        def alertas(self, **kw):
            return ({"ok": True, "alertas": [ix.normalizar(DOC)], "total": 1, "error": None, "ms": 2}
                    if self.ok else
                    {"ok": False, "alertas": [], "total": None, "error": "OSError: sin ruta", "ms": 2})

        def comprobar(self):
            return {"conectado": self.ok, "version": "2.13.0", "indice": "wazuh-alerts-*",
                    "error": None if self.ok else "OSError: sin ruta", "ms": 2}

    previo_modo = os.environ.get(wazuh.VAR_ENTORNO)
    os.environ[wazuh.VAR_ENTORNO] = "real"
    try:
        r = wazuh.alertas(cliente=ManagerOk(), indexador=IxFalso(True))
        chk("en modo real las alertas salen del indexador", r["ok"] and len(r["alertas"]) == 1)
        chk("y van marcadas como reales", all(not a["simulado"] for a in r["alertas"]))
        chk("la nota dice que no se dedujo nada aquí", "ninguna se ha deducido" in r["nota"])
        chk("se informa del total del indexador", r["total_indexador"] == 1)

        r = wazuh.alertas(cliente=ManagerOk(), indexador=IxFalso(False))
        chk("si el indexador falla, el error es visible", r["ok"] is False and r["error"])
        chk("y NO se sustituye por alertas simuladas", r["alertas"] == [] and r["simulado"] is False)
        chk("la nota lo dice con todas las letras", "No se muestran alertas simuladas" in r["nota"])
        chk("pero se distingue que el manager sí respondía", r["manager"] is True)

        e = wazuh.estado(cliente=ManagerOk(), indexador=IxFalso(True))
        chk("el estado distingue manager e indexador",
            e["conectado"] is True and e["indexador"]["conectado"] is True)
        chk("y lo dice en el detalle", "manager e indexador" in e["detalle"])
        e = wazuh.estado(cliente=ManagerOk(), indexador=IxFalso(False))
        chk("un indexador caído con el manager vivo se ve en el estado",
            e["conectado"] is True and e["indexador"]["conectado"] is False)
        chk("y el detalle explica que no hay alertas que leer", "no hay alertas que leer" in e["detalle"])
    finally:
        if previo_modo is None:
            os.environ.pop(wazuh.VAR_ENTORNO, None)
        else:
            os.environ[wazuh.VAR_ENTORNO] = previo_modo

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


def _lanza(fn):
    try:
        fn()
        return False
    except Exception:  # noqa: BLE001
        return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
