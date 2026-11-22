"""Arnés de regresión de CyberShield Repair: levanta el SERVIDOR REAL (subproceso, base temporal, puerto libre) y un Ollama FALSO
con contador de llamadas, y ofrece un cliente HTTP/SSE mínimo. No simula nada del servidor: todo se prueba contra la API real.
El Ollama falso solo sirve para el camino completo; sus respuestas NO dicen nada de la calidad de ningún modelo."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "e2e"))
import ollama_falso as OF  # noqa: E402

CODIGO = "246810"


def puerto_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Respuesta:
    def __init__(self, status, datos):
        self.status, self.datos = status, datos

    def __getitem__(self, k):
        return (self.datos or {})[k]

    def __contains__(self, k):
        return isinstance(self.datos, dict) and k in self.datos

    def get(self, k, d=None):
        return (self.datos or {}).get(k, d) if isinstance(self.datos, dict) else d


class Cliente:
    def __init__(self, base, token=None, nombre=None, equipo=None):
        self.base, self.token, self.nombre, self.equipo = base, token, nombre, equipo

    def _pet(self, metodo, ruta, cuerpo=None, cab=None):
        h = {"Accept": "application/json"}
        if self.token:
            h["X-Equipo-Token"] = self.token
        h.update(cab or {})
        data = None
        if cuerpo is not None:
            data = json.dumps(cuerpo).encode()
            h["Content-Type"] = "application/json"
        rq = urllib.request.Request(self.base + ruta, data=data, headers=h, method=metodo)
        try:
            with urllib.request.urlopen(rq, timeout=20) as r:
                raw = r.read().decode("utf-8")
                try:
                    return Respuesta(r.status, json.loads(raw) if raw else None)
                except ValueError:
                    return Respuesta(r.status, {"raw": raw})      # cuerpos no JSON (descargas CSV/SQL)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return Respuesta(e.code, json.loads(raw))
            except ValueError:
                return Respuesta(e.code, {"raw": raw[:200]})

    def get(self, ruta, cab=None):
        return self._pet("GET", ruta, cab=cab)

    def post(self, ruta, cuerpo=None, cab=None):
        return self._pet("POST", ruta, cuerpo if cuerpo is not None else {}, cab)


class Sse:
    """Suscripción a /api/eventos en un hilo: guarda (evento, datos) en orden de llegada."""

    def __init__(self, base, token=None):
        self.eventos, self._parar = [], False
        h = {"Accept": "text/event-stream"}
        if token:
            h["X-Equipo-Token"] = token
        self._resp = urllib.request.urlopen(urllib.request.Request(base + "/api/eventos", headers=h), timeout=60)
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self):
        ev = None
        try:
            for linea in self._resp:
                t = linea.decode("utf-8").rstrip("\n")
                if t.startswith("event:"):
                    ev = t[6:].strip()
                elif t.startswith("data:") and ev:
                    try:
                        self.eventos.append((ev, json.loads(t[5:].strip())))
                    except ValueError:
                        pass
                    ev = None
        except Exception:  # noqa: BLE001
            pass

    def espera(self, nombre, cond=lambda d: True, hasta=8):
        t0 = time.time()
        while time.time() - t0 < hasta:
            for n, d in list(self.eventos):
                if n == nombre and cond(d):
                    return d
            time.sleep(0.1)
        return None

    def cerrar(self):
        try:
            self._resp.close()
        except Exception:  # noqa: BLE001
            pass


class Entorno:
    """Servidor real + Ollama falso con contador. Uso: `with Entorno() as e: ...`."""

    def __init__(self, retardo_ollama=0.0, env_extra=None):
        self.retardo = retardo_ollama
        self.env_extra = env_extra or {}

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.llamadas_chat = 0
        orig = OF._Manejador.do_POST
        ent = self

        def contado(h):
            if h.path.endswith("/api/chat"):
                ent.llamadas_chat += 1
            return orig(h)
        OF._Manejador.do_POST = contado
        self._orig = orig
        self.srv_ollama, self.url_ollama = OF.iniciar(0, self.retardo)
        self.puerto = puerto_libre()
        self.base = f"http://127.0.0.1:{self.puerto}"
        env = {**os.environ, "PUERTO": str(self.puerto), "CS_LAB_DB": str(self.tmp / "lab.db"), "PYTHONIOENCODING": "utf-8",
               "CS_CODIGO_ARBITRO": CODIGO, "OLLAMA_HOST": self.url_ollama, "CS_NOVA_DB": str(self.tmp / "nova.db"), "CS_NOVA_CLAVES": str(self.tmp / "claves.json"), **self.env_extra}
        self.proc = subprocess.Popen([sys.executable, "server/app.py"], cwd=RAIZ, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            try:
                urllib.request.urlopen(self.base + "/api/ia/estado", timeout=2)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.4)
        else:
            raise RuntimeError("el servidor no arrancó")
        return self

    def unirse(self, nombre, equipo, **extra):
        c = Cliente(self.base)
        cuerpo = {"nombre": nombre, "equipo": equipo, **extra}
        if equipo == "general":
            cuerpo["codigo"] = CODIGO
        r = c.post("/api/sesion", cuerpo)
        if r.status != 200:
            raise RuntimeError(f"no se pudo unir {nombre}: {r.status} {r.datos}")
        return Cliente(self.base, r["token"], nombre, equipo)

    def __exit__(self, *a):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except Exception:  # noqa: BLE001
            self.proc.kill()
        self.srv_ollama.shutdown()
        OF._Manejador.do_POST = self._orig
