"""Pruebas offline de la integración con Wazuh. Ejecutar: python -m src.lab.test_wazuh

No hay ningún Wazuh en esta máquina. Lo que se comprueba aquí son los **contratos**: los tres modos, que una
alerta simulada nunca se presente como real, que el cliente sea de solo lectura de verdad, y que un fallo de
conexión se vea en vez de taparse. El transporte HTTP se sustituye por uno falso.
"""
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
        chk("el estado cuenta las reglas definidas", e["reglas_definidas"] == 18)

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
        chk("se cargan las 18 reglas locales", len(reglas) == 18)
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
