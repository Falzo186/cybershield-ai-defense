"""Cliente de la API de Wazuh. **Solo lectura.**

Reglas duras de este módulo:
  - Solo emite peticiones **GET** (y el POST de autenticación, que la API exige). No hay ninguna función que
    ejecute una respuesta activa, reinicie un agente ni modifique configuración. El laboratorio observa
    Wazuh; no lo manda.
  - Nunca inventa datos. Si no hay conexión, devuelve `ok=False` con el error; jamás una alerta de relleno.
  - Las credenciales se leen del entorno (`WAZUH_USUARIO`, `WAZUH_CLAVE`) y **no se registran** en ningún
    log ni se devuelven en ninguna estructura.

No ha sido probado contra una instalación real de Wazuh: no hay ninguna en esta máquina. Lo que está
comprobado son los contratos (rutas, cabeceras, manejo de errores y que no se emite nada que no sea GET),
con un transporte sustituido en las pruebas.
"""
import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

RUTA_AUTENTICAR = "/security/user/authenticate"
TIMEOUT = 10
# Rutas de solo lectura que este cliente usa. Cualquier otra se rechaza antes de salir a la red.
PERMITIDAS = ("/agents", "/manager/status", "/manager/info", "/rules", "/security/user/authenticate")


class ErrorWazuh(Exception):
    pass


def _contexto(verificar_tls):
    if verificar_tls:
        return None
    # Una instalación de laboratorio suele traer un certificado autofirmado. Desactivar la verificación es
    # una decisión EXPLÍCITA del operador (verificar_tls=False), nunca el valor por defecto.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class ClienteWazuh:
    """Cliente de solo lectura. `transporte` se sustituye en las pruebas; en producción es urllib."""

    def __init__(self, url="https://localhost:55000", usuario=None, clave=None, verificar_tls=True,
                 timeout=TIMEOUT, transporte=None):
        self.url = url.rstrip("/")
        self._usuario = usuario or os.environ.get("WAZUH_USUARIO") or ""
        self._clave = clave or os.environ.get("WAZUH_CLAVE") or ""
        self.verificar_tls = verificar_tls
        self.timeout = timeout
        self._transporte = transporte
        self._token = None
        self._token_hasta = 0.0
        self.ultimo_error = None

    # ── Transporte ─────────────────────────────────────────────────────────────────────────────────────────
    def _peticion(self, metodo, ruta, cabeceras=None, cuerpo=None):
        """Único punto de salida a la red. Rechaza cualquier método que no sea GET (salvo la autenticación)."""
        if metodo != "GET" and ruta != RUTA_AUTENTICAR:
            raise ErrorWazuh(f"este cliente es de solo lectura: {metodo} no está permitido")
        base = ruta.split("?", 1)[0]
        if not any(base == p or base.startswith(p.rstrip("/") + "/") for p in PERMITIDAS):
            raise ErrorWazuh(f"ruta no permitida por el cliente de solo lectura: {base}")
        if self._transporte:
            return self._transporte(metodo, self.url + ruta, cabeceras or {}, cuerpo)
        req = urllib.request.Request(self.url + ruta, data=cuerpo, method=metodo,
                                     headers=cabeceras or {})
        with urllib.request.urlopen(req, timeout=self.timeout,
                                    context=_contexto(self.verificar_tls)) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    # ── Autenticación ──────────────────────────────────────────────────────────────────────────────────────
    def _autenticar(self):
        if self._token and time.time() < self._token_hasta:
            return self._token
        if not self._usuario or not self._clave:
            raise ErrorWazuh("faltan credenciales (WAZUH_USUARIO / WAZUH_CLAVE)")
        basico = base64.b64encode(f"{self._usuario}:{self._clave}".encode()).decode()
        estado, datos = self._peticion("POST", RUTA_AUTENTICAR, {"Authorization": "Basic " + basico})
        if estado != 200:
            raise ErrorWazuh(f"autenticación rechazada (HTTP {estado})")
        token = ((datos or {}).get("data") or {}).get("token")
        if not token:
            raise ErrorWazuh("la respuesta de autenticación no trae token")
        self._token, self._token_hasta = token, time.time() + 800   # el token de Wazuh dura 900 s
        return token

    def _get(self, ruta):
        cab = {"Authorization": "Bearer " + self._autenticar()}
        estado, datos = self._peticion("GET", ruta, cab)
        if estado != 200:
            raise ErrorWazuh(f"HTTP {estado} en {ruta}")
        return datos

    # ── Consultas (todas de solo lectura) ──────────────────────────────────────────────────────────────────
    def _intentar(self, fn):
        """Envuelve una consulta: nunca lanza hacia fuera, nunca devuelve datos inventados."""
        t0 = time.perf_counter()
        try:
            datos = fn()
            self.ultimo_error = None
            return {"ok": True, "datos": datos, "error": None, "ms": int((time.perf_counter() - t0) * 1000)}
        except Exception as exc:  # noqa: BLE001
            self.ultimo_error = f"{type(exc).__name__}: {exc}"
            return {"ok": False, "datos": None, "error": self.ultimo_error,
                    "ms": int((time.perf_counter() - t0) * 1000)}

    def estado_manager(self):
        return self._intentar(lambda: self._get("/manager/status"))

    def informacion(self):
        return self._intentar(lambda: self._get("/manager/info"))

    def agentes(self, limite=50):
        return self._intentar(lambda: self._get(f"/agents?limit={int(limite)}"))

    def reglas_cybershield(self, limite=100):
        """Las reglas del grupo del laboratorio, para confirmar que el manager las tiene cargadas."""
        return self._intentar(lambda: self._get(f"/rules?group=cybershield&limit={int(limite)}"))

    def comprobar(self):
        """Prueba de conexión completa. -> {conectado, version, error, ms}. Nunca lanza."""
        r = self.informacion()
        version = (((r.get("datos") or {}).get("data") or {}).get("affected_items") or [{}])[0].get("version") \
            if r["ok"] else None
        return {"conectado": bool(r["ok"]), "version": version, "error": r["error"], "ms": r["ms"]}
