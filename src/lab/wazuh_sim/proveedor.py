"""Proveedores de Wazuh. El simulado persiste en NDJSON append-only + SQLite indexada por partida_id."""
import hashlib
import json
import os
import random
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path

from .reglas import REGLAS, RUIDO

ETIQUETA = "WAZUH SIMULADO"
MODOS = ("real", "simulado", "desconectado", "con_errores")
RAIZ = Path(__file__).resolve().parents[3]

AGENTES = [
    {"id": "001", "name": "srv-correo", "ip": "10.20.0.11", "os": {"name": "Ubuntu", "version": "22.04"}, "group": ["servidores", "correo"]},
    {"id": "002", "name": "srv-rrhh", "ip": "10.20.0.12", "os": {"name": "Ubuntu", "version": "22.04"}, "group": ["servidores", "rrhh"]},
    {"id": "003", "name": "ws-contabilidad-01", "ip": "10.20.1.31", "os": {"name": "Windows", "version": "11"}, "group": ["estaciones", "contabilidad"]},
    {"id": "004", "name": "srv-bd", "ip": "10.20.0.14", "os": {"name": "Debian", "version": "12"}, "group": ["servidores", "base_de_datos"]},
]
_AGENTE = {a["name"]: a for a in AGENTES}


class WazuhProvider(ABC):
    """Contrato común. Un modelo solo debe recibir lo que devuelve `consultar_alertas` (sin verdad de fondo)."""

    modo = "desconectado"

    @abstractmethod
    def listar_agentes(self): ...

    @abstractmethod
    def consultar_alertas(self, partida_id, desde=None, nivel_min=0, grupos=None, agente=None, limite=100): ...

    @abstractmethod
    def estado(self): ...


def _id_det(*partes):
    h = hashlib.sha256("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()
    return f"{int(h[:10], 16)}.{int(h[10:16], 16)}"


class SimProvider(WazuhProvider):
    """Simulación. Alimentada con `alimentar(evento)`; idempotente por id determinista."""

    modo = "simulado"

    def __init__(self, ruta_ndjson=None, ruta_db=":memory:", semilla=0, ruido_por_alerta=(3, 6)):
        self.ruta_ndjson = Path(ruta_ndjson) if ruta_ndjson else None
        self.semilla = semilla
        self.ruido_por_alerta = ruido_por_alerta
        self._cerrojo = threading.RLock()
        self.db = sqlite3.connect(str(ruta_db), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS alertas(id TEXT PRIMARY KEY, partida_id TEXT, turno INT, ts TEXT, "
                        "nivel INT, regla INT, agente TEXT, relevante INT, json TEXT)")
        self.db.execute("CREATE INDEX IF NOT EXISTS ix_alertas_partida ON alertas(partida_id, ts)")
        self.db.commit()
        self.errores = []

    # -- Contrato -------------------------------------------------------------------------------------------
    def listar_agentes(self):
        return [dict(a) for a in AGENTES]

    def estado(self):
        n = self.db.execute("SELECT COUNT(*) FROM alertas").fetchone()[0]
        return {"modo": self.modo, "etiqueta": ETIQUETA, "simulado": True, "alertas_totales": n,
                "agentes": len(AGENTES), "errores": list(self.errores[-3:]),
                "detalle": "Simulación local alimentada por el motor de combate. No es una instalación de Wazuh."}

    def consultar_alertas(self, partida_id, desde=None, nivel_min=0, grupos=None, agente=None, limite=100):
        with self._cerrojo:
            filas = self.db.execute("SELECT json FROM alertas WHERE partida_id=? AND nivel>=? ORDER BY ts, id",
                                    (partida_id, int(nivel_min))).fetchall()
        out = []
        for (j,) in filas:
            a = json.loads(j)
            if desde and a["timestamp"] < desde:
                continue
            if grupos and not (set(grupos) & set(a["rule"]["groups"])):
                continue
            if agente and a["agent"]["name"] != agente:
                continue
            out.append(a)
        return out[-limite:] if limite else out

    # -- Canal oculto (solo el motor y las métricas lo leen) --------------------------------------------------
    def verdad_de_fondo(self, partida_id):
        """-> {id_alerta: relevante(bool)}. Nunca debe llegar a un modelo."""
        return {i: bool(r) for i, r in self.db.execute(
            "SELECT id, relevante FROM alertas WHERE partida_id=?", (partida_id,))}

    def alertas_relevantes(self, partida_id):
        return [json.loads(j) for (j,) in self.db.execute(
            "SELECT json FROM alertas WHERE partida_id=? AND relevante=1 ORDER BY ts, id", (partida_id,))]

    # -- Entrada --------------------------------------------------------------------------------------------
    def alimentar(self, evento):
        """Convierte un evento del motor en alertas (+ ruido). Evento: {partida_id, turno, ts, clave, agente,
        relevante, id_evento, data, full_log}. Reinyectar el mismo evento no duplica nada. -> ids nuevos."""
        clave = evento.get("clave")
        if clave not in REGLAS:
            return []
        nuevos = []
        with self._cerrojo:
            a = self._alerta(evento, clave)
            if self._insertar(a, evento.get("relevante", False)):
                nuevos.append(a["id"])
                # Ruido: reproducible con la semilla y el id del evento (no con el estado global).
                rng = random.Random(f"{self.semilla}|{a['id']}")
                for k in range(rng.randint(*self.ruido_por_alerta)):
                    r = self._ruido(evento, rng, k)
                    if self._insertar(r, False):
                        nuevos.append(r["id"])
        return nuevos

    def _insertar(self, alerta, relevante):
        try:
            cur = self.db.execute("INSERT OR IGNORE INTO alertas VALUES(?,?,?,?,?,?,?,?,?)",
                                  (alerta["id"], alerta["lab"]["partida_id"], alerta["lab"]["turno"], alerta["timestamp"],
                                   alerta["rule"]["level"], int(alerta["rule"]["id"]), alerta["agent"]["name"],
                                   1 if relevante else 0, json.dumps(alerta, ensure_ascii=False)))
            self.db.commit()
            if cur.rowcount == 0:
                return False
            if self.ruta_ndjson:
                self.ruta_ndjson.parent.mkdir(parents=True, exist_ok=True)
                with open(self.ruta_ndjson, "a", encoding="utf-8") as f:   # append-only; sin verdad de fondo
                    f.write(json.dumps(alerta, ensure_ascii=False) + "\n")
            return True
        except Exception as exc:  # noqa: BLE001
            self.errores.append(f"{type(exc).__name__}: {exc}")
            return False

    def _alerta(self, ev, clave):
        rid, nivel, desc, grupos, mitre = REGLAS[clave]
        ag = _AGENTE.get(ev.get("agente")) or AGENTES[0]
        regla = {"id": str(rid), "level": nivel, "description": desc, "groups": list(grupos), "firedtimes": 1}
        if mitre:
            regla["mitre"] = {"id": [mitre["id"]], "tactic": [mitre["tactic"]], "technique": [mitre["technique"]]}
        return {
            "id": _id_det(ev["partida_id"], ev["turno"], rid, ev.get("id_evento")),
            "timestamp": ev["ts"], "rule": regla,
            "agent": {"id": ag["id"], "name": ag["name"], "ip": ag["ip"]},
            "manager": {"name": "wazuh-manager-simulado"},
            "decoder": {"name": "cybershield-lab"}, "location": "/var/log/cybershield/combate.log",
            "full_log": ev.get("full_log") or desc,
            "data": dict(ev.get("data") or {}),
            "lab": {"partida_id": ev["partida_id"], "turno": ev["turno"], "simulado": True, "etiqueta": ETIQUETA},
        }

    def _ruido(self, ev, rng, k):
        rid, nivel, desc, grupos, log = rng.choice(RUIDO)
        ag = rng.choice(AGENTES)
        try:
            t = datetime.fromisoformat(ev["ts"]) + timedelta(milliseconds=rng.randint(-900, 900))
            ts = t.isoformat(timespec="milliseconds")
        except ValueError:
            ts = ev["ts"]
        return {
            "id": _id_det(ev["partida_id"], ev["turno"], rid, ev.get("id_evento"), "ruido", k),
            "timestamp": ts,
            "rule": {"id": str(rid), "level": nivel, "description": desc, "groups": list(grupos), "firedtimes": 1},
            "agent": {"id": ag["id"], "name": ag["name"], "ip": ag["ip"]},
            "manager": {"name": "wazuh-manager-simulado"}, "decoder": {"name": "syslog"},
            "location": "/var/log/syslog", "full_log": log, "data": {},
            "lab": {"partida_id": ev["partida_id"], "turno": ev["turno"], "simulado": True, "etiqueta": ETIQUETA},
        }


class RealProvider(WazuhProvider):
    """Contrato + stub para una instancia real de Wazuh. NO inventa respuestas.

    Lee WAZUH_URL, WAZUH_USUARIO y WAZUH_CLAVE del entorno. Sin ellos, `estado()` dice `desconectado`. Si hay
    URL pero no se implementó la llamada (stub), dice `con_errores`. La integración con la API real (JWT en
    :55000 y el indexador :9200) está en `src/lab/wazuh/` (solo lectura); este proveedor es el punto de
    enganche para el combate."""

    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.url, self.usuario, self.clave = env.get("WAZUH_URL"), env.get("WAZUH_USUARIO"), env.get("WAZUH_CLAVE")

    @property
    def configurado(self):
        return bool(self.url and self.usuario and self.clave)

    @property
    def modo(self):  # noqa: D401
        return "con_errores" if self.configurado else "desconectado"

    def estado(self):
        if not self.configurado:
            return {"modo": "desconectado", "simulado": False,
                    "detalle": "Sin WAZUH_URL/WAZUH_USUARIO/WAZUH_CLAVE: no hay instancia real configurada."}
        return {"modo": "con_errores", "simulado": False,
                "detalle": "Instancia configurada, pero el stub del proveedor real no implementa la consulta."}

    def listar_agentes(self):
        raise NotImplementedError("RealProvider es un stub: requiere una instancia real de Wazuh.")

    def consultar_alertas(self, *a, **k):
        raise NotImplementedError("RealProvider es un stub: requiere una instancia real de Wazuh.")
