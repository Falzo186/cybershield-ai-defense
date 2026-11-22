"""Motor de la partida Nova (paquete del profesor: contratos 05 y decisiones 04). Lógica pura, sin HTTP.

El MOTOR es la autoridad: las personas y las IA proponen acciones; el motor las valida con un pipeline fijo, aplica la consecuencia y registra eventos
con `seq` monótono y visibilidad por rol. La partida NUNCA inicia sola: solo `iniciar` (del administrador, con confirmación e idempotencia) pasa de
LISTA a EN_CURSO. El reloj de partida avanza solo en EN_CURSO (virtual en pruebas, sin `sleep`).

Pipeline (05 §4): 1 estructura · 2 partida EN_CURSO · 3 actor/rol · 4 recurso o identidad existe · 5 credencial conocida y utilizable · 6 permisos ·
7 estado (bloqueo/suspensión/lockout) · 8 reglas y presupuestos · 9 consecuencia · 10 registro. Rechazo = DENIED/INVALID + motivo tipificado.
"""
import hashlib
import hmac
import json
import os
import random
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import escenario as E

RAIZ = Path(__file__).resolve().parents[3]

# ── Máquina de estados de la partida (05 §2) ───────────────────────────────────────────────────────────────
TRANSICIONES = {
    "CONFIGURACION": {"SALA_DE_ESPERA", "CANCELADA"},
    "SALA_DE_ESPERA": {"LISTA", "CONFIGURACION", "CANCELADA"},
    "LISTA": {"EN_CURSO", "SALA_DE_ESPERA", "CANCELADA"},
    "EN_CURSO": {"PAUSADA", "DETENIENDO", "FINALIZADA", "ERROR"},
    "PAUSADA": {"EN_CURSO", "DETENIENDO", "CANCELADA"},
    "DETENIENDO": {"FINALIZADA", "CANCELADA", "ERROR"},
    "ERROR": {"DETENIENDO", "CANCELADA"},
    "FINALIZADA": set(), "CANCELADA": set(),
}
ESTADOS_CRED = ("PROTEGIDA", "EXPUESTA", "COMPROMETIDA", "SUSPENDIDA", "REVOCADA")
TRANS_ALERTA = {"NUEVA": {"EN_ANALISIS"}, "EN_ANALISIS": {"ASIGNADA", "FALSO_POSITIVO", "RESUELTA"}, "ASIGNADA": {"CONTENIDA", "FALSO_POSITIVO", "RESUELTA"},
                "CONTENIDA": {"RESUELTA"}, "RESUELTA": {"CERRADA"}, "FALSO_POSITIVO": {"CERRADA"}, "CERRADA": set()}
TRANS_APROB = {"PENDIENTE": {"APROBADA", "RECHAZADA", "INFO_SOLICITADA", "ESCALADA", "EXPIRADA"}, "INFO_SOLICITADA": {"APROBADA", "RECHAZADA", "ESCALADA", "EXPIRADA"},
               "ESCALADA": {"APROBADA", "RECHAZADA", "EXPIRADA"}}
TRANS_TAREA = {"PENDIENTE": {"EN_PROGRESO", "CANCELADA"}, "EN_PROGRESO": {"ESPERANDO_APROBACION", "COMPLETADA", "CANCELADA"}, "ESPERANDO_APROBACION": {"COMPLETADA", "RECHAZADA", "CANCELADA"}}
EQUIPOS = ("RED", "BLUE", "ADMIN", "SPECTATOR")
ACCIONES_ROJO = {"send_email", "scan_directory", "guess_credential", "use_credential", "query_resource", "extract_table", "export_database", "request_elevation", "respond_info", "message_team"}
ACCIONES_AZUL = {"assign_task", "set_task_status", "classify_email", "report_email", "open_email", "view_link", "click_link", "risk_action", "revoke_credential", "suspend_identity", "block_link", "contain_incident",
                 "approve_request", "reject_request", "request_more_info", "escalate", "set_alert_status", "message_team", "allow"}
CONFIG_DEFECTO = {"duration_s": 720, "round_s": 60, "guess_attempts_per_round": 3, "guess_attempts_per_match": 12, "guess_cooldown_s": 20, "guess_lockout_after_fails": 3, "lockout_s": 90,
                  "detect_prob_fail": 0.6, "min_continuity": 0.6, "abuse_policy": "empate", "approval_ttl_s": 90, "elevation_grant_s": 120, "emails_per_round": 3, "scans_per_round": 2,
                  "click_prob_unconnected": 1.0, "click_delay_s": 25, "modalidad": "BALANCED", "ai_mode": {"RED": "off", "BLUE": "off"}, "win": E.WIN_POR_DEFECTO, "seed": 1,
                  "model_down_policy": "pause", "ai_prompt_budget": 10, "ai_prompt_mode": "controlado", "near_miss_min": 4}


class ErrorNova(Exception):
    def __init__(self, status, mensaje, motivo="INVALID"):
        super().__init__(mensaje)
        self.status, self.mensaje, self.motivo = status, mensaje, motivo


# ── Reloj de partida (D10) ────────────────────────────────────────────────────────────────────────────────
class Reloj:
    """Avanza SOLO en EN_CURSO. `virtual=True` (pruebas): se mueve únicamente con `avanzar`. Real: tiempo monótono × `escala`."""

    def __init__(self, virtual=True, escala=1.0):
        self.virtual, self.escala, self._ms, self._corriendo, self._t0 = virtual, escala, 0, False, None

    def iniciar(self):
        if not self._corriendo:
            self._corriendo, self._t0 = True, time.monotonic()

    def detener(self):
        self._ms = self.ahora_ms()
        self._corriendo = False

    def ahora_ms(self):
        if self.virtual or not self._corriendo:
            return int(self._ms)
        return int(self._ms + (time.monotonic() - self._t0) * 1000 * self.escala)

    def avanzar(self, ms):
        if not self.virtual:
            raise ErrorNova(400, "El reloj real no se adelanta a mano")
        if self._corriendo:
            self._ms += ms


# ── Secretos (D4): HMAC para verificar, Fernet para que solo el motor/admin vea el valor ───────────────────────
class Secretos:
    def __init__(self, pepper=None, clave_fernet=None):
        from cryptography.fernet import Fernet
        if pepper is None or clave_fernet is None:
            ruta = Path(os.environ.get("CS_NOVA_CLAVES") or (RAIZ / "data" / "nova_claves.json"))
            if ruta.exists():
                d = json.loads(ruta.read_text(encoding="utf-8"))
            else:
                ruta.parent.mkdir(parents=True, exist_ok=True)
                d = {"pepper": uuid.uuid4().hex + uuid.uuid4().hex, "fernet": Fernet.generate_key().decode()}
                ruta.write_text(json.dumps(d), encoding="utf-8")
            pepper, clave_fernet = pepper or d["pepper"], clave_fernet or d["fernet"]
        self._pepper, self._f = pepper.encode(), Fernet(clave_fernet.encode() if isinstance(clave_fernet, str) else clave_fernet)

    def hash(self, v):
        return hmac.new(self._pepper, v.encode("utf-8"), hashlib.sha256).hexdigest()

    def cifrar(self, v):
        return self._f.encrypt(v.encode("utf-8")).decode()

    def descifrar(self, t):
        return self._f.decrypt(t.encode()).decode()

    def verificar(self, v, h):
        return hmac.compare_digest(self.hash(v), h)

    @staticmethod
    def enmascarar(v):
        return v[:2] + "***" + v[-1] if v and len(v) >= 4 else "***"


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class NovaPartida:
    def __init__(self, id=None, config=None, reloj=None, secretos=None, db=":memory:"):
        self.id = id or "nova-" + uuid.uuid4().hex[:8]
        explicito = dict(config or {})
        self.config = {**CONFIG_DEFECTO, **E.MODALIDADES.get(explicito.get("modalidad", "BALANCED"), {}), **explicito}   # lo explícito del administrador gana sobre la modalidad
        self.config["modalidad_params"] = dict(E.MODALIDADES.get(self.config["modalidad"], {}))
        self.reloj = reloj or Reloj(virtual=True)
        self.secretos = secretos or Secretos()
        self.rng = random.Random(f"nova|{self.config['seed']}")
        self.estado = "CONFIGURACION"
        self._lock = threading.RLock()
        self.participantes, self.eventos_lista, self.acciones, self._idem = {}, [], [], {}
        self.base = E.generar_base(E.generar_credenciales())
        self.identidades = {i["id"]: dict(i) for i in E.IDENTIDADES}
        self.creds = {}
        for iid, valor in E.generar_credenciales().items():       # estable entre partidas: misma semilla
            self.creds[iid] = {"hash": self.secretos.hash(valor), "enc": self.secretos.cifrar(valor), "estado": "PROTEGIDA", "debil": self.identidades[iid]["weak"]}
        self.rojo_estado = {iid: "DESCONOCIDA" for iid in self.identidades}
        self.rojo_conoce = {}                                      # iid -> valor (solo lo descubierto, expuesto o adivinado)
        self.rojo_origen = {}
        self.emails, self.links, self.alertas, self.incidentes, self.aprobaciones, self.extraido = {}, {}, {}, {}, {}, {}
        self.fallos_identidad, self.bloqueo_hasta, self.guess_cooldown_hasta = {}, {}, 0
        self.guess_ronda, self.guess_total, self.emails_ronda, self.scans_ronda = {}, 0, {}, {}
        self.programados = [{**c, "estado": "PENDIENTE"} for c in E.CORREOS_PROGRAMADOS]
        self.clics_pendientes = []
        self.grants_db_export_hasta = 0
        self.puntos = {"RED": 0, "BLUE": 0}
        self.resultado = None
        self.legitimas = {"entregadas": 0, "servidas": 0, "resueltas": 0}
        self.tareas, self.mensajes = {}, []
        self.seq = 0
        self.db = sqlite3.connect(str(db), check_same_thread=False)
        self.db.executescript("""CREATE TABLE IF NOT EXISTS nova_events(match_id TEXT, seq INT, ts_match_ms INT, ts_real TEXT, type TEXT, actor TEXT, target TEXT, result TEXT,
            visibility TEXT, data TEXT, PRIMARY KEY(match_id, seq));
            CREATE TABLE IF NOT EXISTS nova_results(match_id TEXT PRIMARY KEY, resultado TEXT, detalle TEXT, ts_real TEXT);
            CREATE TABLE IF NOT EXISTS nova_extracted(match_id TEXT, tabla TEXT, filas INT, PRIMARY KEY(match_id, tabla));""")
        self._ev("match.created", {"kind": "system", "team": "SYSTEM"}, {"kind": "match", "id": self.id}, vis=["ADMIN"], data={"config": {k: v for k, v in self.config.items() if k != "win"}})

    # ── eventos ───────────────────────────────────────────────────────────────────────────────────────
    def _ev(self, tipo, actor=None, target=None, result="OK", vis=None, data=None):
        self.seq += 1
        e = {"v": 1, "id": uuid.uuid4().hex[:12], "seq": self.seq, "match_id": self.id, "round": self.ronda(), "ts_real": _utc(), "ts_match_ms": self.reloj.ahora_ms(), "type": tipo,
             "actor": actor or {"kind": "system", "team": "SYSTEM"}, "target": target or {"kind": "match", "id": self.id}, "result": result,
             "visibility": vis or ["ADMIN", "RED", "BLUE", "SPECTATOR"], "data": data or {}}
        self.eventos_lista.append(e)
        self.db.execute("INSERT INTO nova_events VALUES(?,?,?,?,?,?,?,?,?,?)", (self.id, e["seq"], e["ts_match_ms"], e["ts_real"], tipo, json.dumps(e["actor"]), json.dumps(e["target"]), result,
                                                                               json.dumps(e["visibility"]), json.dumps(e["data"], ensure_ascii=False)))
        self.db.commit()
        return e

    def eventos(self, para="ADMIN", after_seq=0):
        """Eventos visibles para un rol (el filtrado ocurre aquí, en el servidor): un Azul nunca ve eventos solo-Rojo ni secretos."""
        return [e for e in self.eventos_lista if e["seq"] > after_seq and (para == "ADMIN" or para in e["visibility"])]

    def ronda(self):
        return self.reloj.ahora_ms() // (self.config["round_s"] * 1000)

    def t_s(self):
        return self.reloj.ahora_ms() / 1000

    # ── ciclo de vida (la partida NUNCA inicia sola) ─────────────────────────────────────────────────
    def _a(self, nuevo, actor="ADMIN"):
        if nuevo not in TRANSICIONES[self.estado]:
            raise ErrorNova(409, f"Transición no válida: {self.estado} → {nuevo}", "INVALID_TRANSITION")
        antes, self.estado = self.estado, nuevo
        self._ev("match." + {"SALA_DE_ESPERA": "lobby_opened", "LISTA": "ready", "EN_CURSO": "started", "PAUSADA": "paused", "DETENIENDO": "stopping", "FINALIZADA": "finished",
                             "CANCELADA": "cancelled", "ERROR": "error", "CONFIGURACION": "config_changed"}[nuevo], {"kind": "human", "team": actor}, data={"de": antes, "a": nuevo})

    def _solo_admin(self, rol):
        if rol != "ADMIN":
            raise ErrorNova(403, "Solo el administrador puede controlar la partida", "FORBIDDEN")

    def abrir_sala(self, rol="ADMIN"):
        self._solo_admin(rol)
        self._a("SALA_DE_ESPERA")

    def unirse(self, nombre, equipo, identidad=None):
        with self._lock:
            if equipo not in EQUIPOS:
                raise ErrorNova(400, "Equipo desconocido")
            if self.estado not in ("SALA_DE_ESPERA", "LISTA", "EN_CURSO", "PAUSADA") and equipo in ("RED", "BLUE"):
                raise ErrorNova(409, "La partida aún no abrió su sala de espera" if self.estado == "CONFIGURACION" else "La partida ya terminó")
            if nombre in self.participantes:
                self.participantes[nombre]["conectado"] = True
                return self.participantes[nombre]
            if equipo == "BLUE":
                ocupadas = {p["identidad"] for p in self.participantes.values() if p["equipo"] == "BLUE"}
                if len(ocupadas) >= E.MAX_AZUL:
                    raise ErrorNova(409, f"El equipo Azul está completo (máximo {E.MAX_AZUL} jugadores)", "TEAM_FULL")
                iid = identidad or next(i for i in E.ORDEN_AZUL if i not in ocupadas)
                if iid in ocupadas or iid not in self.identidades:
                    raise ErrorNova(409, "Esa identidad ya está asignada", "IDENTITY_TAKEN")
                identidad = iid
            if equipo == "RED" and sum(p["equipo"] == "RED" for p in self.participantes.values()) >= E.MAX_ROJO:
                raise ErrorNova(409, f"El equipo Rojo está completo (máximo {E.MAX_ROJO})", "TEAM_FULL")
            p = {"nombre": nombre, "equipo": equipo, "identidad": identidad if equipo == "BLUE" else None, "listo": False, "conectado": True, "unido": _utc()}
            self.participantes[nombre] = p
            self._ev("presence.connected", {"kind": "human", "team": equipo, "label": nombre}, data={"equipo": equipo})
            if identidad:
                self._ev("identity.assigned", {"kind": "system", "team": "SYSTEM"}, {"kind": "identity", "id": identidad}, data={"jugador": nombre, "identidad": identidad})
            return p

    def desconectar(self, nombre):
        if nombre in self.participantes:
            self.participantes[nombre]["conectado"] = False
            self._ev("presence.disconnected", {"kind": "human", "team": self.participantes[nombre]["equipo"], "label": nombre})

    def reasignar(self, rol, nombre, identidad):
        self._solo_admin(rol)
        if self.estado not in ("SALA_DE_ESPERA", "LISTA"):
            raise ErrorNova(409, "Solo se puede reasignar en la sala de espera")
        p = self.participantes.get(nombre)
        if not p or p["equipo"] != "BLUE" or identidad not in self.identidades:
            raise ErrorNova(400, "Jugador o identidad no válidos")
        if any(o["identidad"] == identidad and o["nombre"] != nombre for o in self.participantes.values()):
            raise ErrorNova(409, "Esa identidad ya está asignada", "IDENTITY_TAKEN")
        p["identidad"] = identidad
        self._ev("team.member_moved", {"kind": "human", "team": "ADMIN"}, {"kind": "identity", "id": identidad}, data={"jugador": nombre})

    def marcar_listo(self, nombre, listo=True):
        if nombre not in self.participantes:
            raise ErrorNova(404, "Jugador desconocido")
        self.participantes[nombre]["listo"] = bool(listo)

    def marcar_lista(self, rol="ADMIN"):
        self._solo_admin(rol)
        if self.estado == "SALA_DE_ESPERA" and not (any(p["equipo"] == "RED" for p in self.participantes.values()) and any(p["equipo"] == "BLUE" for p in self.participantes.values())):
            raise ErrorNova(409, "Hace falta al menos un jugador Rojo y uno Azul", "NOT_READY")
        self._a("LISTA")

    def iniciar(self, rol, confirm=False, idempotency_key=None):
        """ÚNICO camino a EN_CURSO: administrador + confirmación + clave de idempotencia. Repetir la misma clave no inicia dos veces."""
        with self._lock:
            self._solo_admin(rol)
            if not confirm or not idempotency_key:
                raise ErrorNova(400, "Iniciar exige confirmación explícita y una clave de idempotencia", "CONFIRM_REQUIRED")
            if idempotency_key in self._idem:
                return self._idem[idempotency_key]
            self._a("EN_CURSO")
            self.reloj.iniciar()
            self.config_congelada = json.dumps(self.config, sort_keys=True, default=str)       # modalidad y parámetros quedan CONGELADOS desde el inicio
            self._ev("match.clock_started", data={"duration_s": self.config["duration_s"], "modalidad": self.config["modalidad"], "parametros": self.config["modalidad_params"]})
            r = {"estado": self.estado}
            self._idem[idempotency_key] = r
            return r

    def pausar(self, rol="ADMIN"):
        self._solo_admin(rol)
        self._a("PAUSADA")
        self.reloj.detener()

    def reanudar(self, rol="ADMIN"):
        self._solo_admin(rol)
        self._a("EN_CURSO")
        self.reloj.iniciar()
        self._ev("match.resumed")

    def detener(self, rol="ADMIN", cancelar=False):
        """`stop` no deja tareas vivas: pasa por DETENIENDO y termina FINALIZADA (con resultado) o CANCELADA (SIN_RESULTADO_CANCELADA)."""
        self._solo_admin(rol)
        self._a("DETENIENDO")
        self.reloj.detener()
        if cancelar:
            self._a("CANCELADA")
            self._cerrar("SIN_RESULTADO_CANCELADA", "cancelada por el administrador")
        else:
            self._a("FINALIZADA")
            self._evaluar_final(forzado=True)

    # ── tick: scheduler, caducidades, victoria por tiempo ───────────────────────────────────────────
    def tick(self):
        """Lo llama el coordinador (un único bucle por partida). Dispara correos programados UNA sola vez, caduca aprobaciones y evalúa el fin."""
        with self._lock:
            if self.estado != "EN_CURSO":
                return
            t = self.t_s()
            for c in self.programados:
                if c["estado"] == "PENDIENTE" and c["at_s"] <= t:
                    c["estado"] = "GENERADO"
                    self._ev("scheduler.event_fired", data={"scenario_event_id": c["id"]})
                    self._entregar_programado(c)
            for a in self.aprobaciones.values():
                if a["estado"] in ("PENDIENTE", "INFO_SOLICITADA", "ESCALADA") and t >= a["expira_s"]:
                    self._aprob_estado(a, "EXPIRADA", {"kind": "system", "team": "SYSTEM"})
                    if a["legitima"]:
                        self.legitimas["resueltas"] += 1
            for cp in [c for c in self.clics_pendientes if c["at_s"] <= t]:
                self.clics_pendientes.remove(cp)
                self._clic_guionizado(cp)
            if self.estado == "EN_CURSO" and self.resultado is None:
                self._evaluar_final()

    def avanzar(self, segundos, paso_s=1):
        """Pruebas: avanza el reloj virtual con ticks intermedios (el scheduler no se salta eventos)."""
        restante = segundos
        while restante > 0 and self.estado == "EN_CURSO":
            d = min(paso_s, restante)
            self.reloj.avanzar(int(d * 1000))
            restante -= d
            self.tick()

    # ── correos ───────────────────────────────────────────────────────────────────────────────────────
    def _jugador_de(self, iid):
        return next((n for n, p in self.participantes.items() if p["equipo"] == "BLUE" and p["identidad"] == iid and p["conectado"]), None)

    def _crear_email(self, origen, de, iid, asunto, cuerpo, malicioso=False, scenario_id=None, link=False):
        eid = "EM-" + uuid.uuid4().hex[:6]
        lid = "LK-" + uuid.uuid4().hex[:6] if link else None
        em = {"id": eid, "origen": origen, "de": de, "para": iid, "asunto": asunto, "cuerpo": cuerpo, "link_id": lid, "estado": "ENTREGADO", "leido": False, "reportado": False,
              "clasificado": None, "respondido": False, "ts_s": self.t_s(), "scenario_id": scenario_id}
        self.emails[eid] = em
        if lid:
            self.links[lid] = {"id": lid, "email_id": eid, "malicioso": malicioso, "neutralizado": False, "visto": False, "clic": False, "riesgo": False, "para": iid, "url": f"lab://enlace/{lid}"}
        self._ev("email.received", {"kind": "system" if origen == "ESCENARIO" else "human", "team": "RED" if origen == "RED" else "SYSTEM"}, {"kind": "email", "id": eid},
                 vis=["ADMIN", "BLUE"] if origen == "ESCENARIO" else ["ADMIN", "RED", "BLUE"], data={"para": iid, "asunto": asunto, "origen": origen, "jugador": self._jugador_de(iid)})
        if malicioso and link and self._jugador_de(iid) is None:     # empleado NO conectado: comportamiento guionizado, sin intervención de nadie
            if self.rng.random() < self.config["click_prob_unconnected"]:
                self.clics_pendientes.append({"link_id": lid, "at_s": self.t_s() + self.config["click_delay_s"]})
        return em

    def _entregar_programado(self, c):
        iid = "EMP-01"
        for n, p in self.participantes.items():       # al primer Azul conectado; si no hay, a EMP-01 (existe igualmente)
            if p["equipo"] == "BLUE":
                iid = p["identidad"]
                break
        em = self._crear_email("ESCENARIO", c["de"], iid, c["asunto"], c["cuerpo"], scenario_id=c["id"])
        if c.get("requiere_aprobacion"):
            self.legitimas["entregadas"] += 1
            self._crear_aprobacion({"kind": "system", "team": "SYSTEM"}, f"Solicitud legítima de un compañero ({c['asunto']})", "consulta_autorizada", "R-VENTAS" if "ventas" in c["asunto"].lower() else "R-INVENTARIO",
                                   legitima=True, email_id=em["id"])
        return em

    # ── pipeline ──────────────────────────────────────────────────────────────────────────────────────
    def ejecutar(self, accion):
        """Entrada única de acciones (05 §4). -> {ok, result, reject_reason, mensaje, data}. Nunca lanza por un rechazo de negocio."""
        with self._lock:
            tipo = (accion or {}).get("action_type")
            actor = (accion or {}).get("actor") or {}
            aid = (accion or {}).get("action_id") or uuid.uuid4().hex[:10]
            idem = (accion or {}).get("idempotency_key")
            if idem and ("a", idem) in self._idem:
                return self._idem[("a", idem)]
            try:
                self._paso1_estructura(accion)
                if self.estado != "EN_CURSO":
                    raise ErrorNova(409, "La partida no está en curso" + (" (en pausa)" if self.estado == "PAUSADA" else ""), "MATCH_NOT_RUNNING")
                equipo = actor.get("team")
                permitido = (tipo in ACCIONES_ROJO and equipo in ("RED", "ADMIN")) or (tipo in ACCIONES_AZUL and equipo in ("BLUE", "ADMIN"))
                if not permitido:
                    raise ErrorNova(403, "Ese equipo no puede ejecutar esa acción", "WRONG_TEAM")
                data = getattr(self, "_h_" + tipo)(accion)
                r = {"ok": True, "result": "OK", "reject_reason": None, "mensaje": "", "data": data or {}, "action_id": aid}
                self._ev("action.executed", {"kind": actor.get("kind", "human"), "team": equipo, "label": actor.get("user")}, {"kind": "action", "id": aid}, vis=["ADMIN"], data={"action_type": tipo, "meta": {k: str(v)[:120] for k, v in ((accion.get("params") or {}).get("meta") or {}).items()} if isinstance((accion.get("params") or {}).get("meta"), dict) else None})
            except ErrorNova as ex:
                r = {"ok": False, "result": "DENIED" if ex.motivo != "INVALID_SCHEMA" else "INVALID", "reject_reason": ex.motivo, "mensaje": ex.mensaje, "data": {}, "action_id": aid}
                self._ev("action.rejected", {"kind": actor.get("kind", "human"), "team": actor.get("team"), "label": actor.get("user")}, {"kind": "action", "id": aid}, result=r["result"],
                         vis=["ADMIN", actor.get("team", "ADMIN")] if actor.get("team") in ("RED", "BLUE") else ["ADMIN"], data={"action_type": tipo, "reject_reason": ex.motivo, "mensaje": ex.mensaje})
            self.acciones.append({"action_id": aid, "action_type": tipo, "actor": actor, "ok": r["ok"], "reject_reason": r["reject_reason"], "ts_match_ms": self.reloj.ahora_ms()})
            if idem:
                self._idem[("a", idem)] = r
            if self.estado == "EN_CURSO" and self.resultado is None:
                self._evaluar_final()
            return r

    @staticmethod
    def _paso1_estructura(a):
        if not isinstance(a, dict) or not isinstance(a.get("actor"), dict) or not a.get("action_type") or not isinstance(a.get("params", {}), dict):
            raise ErrorNova(400, "Acción mal formada", "INVALID_SCHEMA")

    def _identidad(self, iid):
        if iid not in self.identidades:
            raise ErrorNova(404, f"Identidad desconocida: {iid}", "UNKNOWN_IDENTITY")
        return self.identidades[iid]

    def _tabla_permitida(self, iid, tabla):
        return tabla in E.RECURSOS[self.identidades[iid]["recurso"]]["tablas"]

    def _usable(self, iid):
        c = self.creds[iid]
        if c["estado"] in ("SUSPENDIDA", "REVOCADA"):
            raise ErrorNova(403, "La credencial está suspendida o revocada", "CREDENTIAL_UNUSABLE")
        if self.bloqueo_hasta.get(iid, 0) > self.t_s():
            raise ErrorNova(403, "La identidad está bloqueada temporalmente", "IDENTITY_LOCKED")

    def _conoce(self, iid):
        if iid not in self.rojo_conoce:
            raise ErrorNova(403, "El equipo Rojo no conoce una credencial de esa identidad (no se puede usar lo no descubierto)", "CREDENTIAL_NOT_KNOWN")

    # ── acciones del Rojo ─────────────────────────────────────────────────────────────────────────────
    def _h_scan_directory(self, a):
        r = self.ronda()
        if self.scans_ronda.get(r, 0) >= self.config["scans_per_round"]:
            raise ErrorNova(429, "Presupuesto de reconocimiento de esta ronda agotado", "BUDGET_EXCEEDED")
        self.scans_ronda[r] = self.scans_ronda.get(r, 0) + 1
        nuevos = [i for i in self.identidades if self.rojo_estado[i] == "DESCONOCIDA"][:3]
        for i in nuevos:
            self.rojo_estado[i] = "IDENTIFICADA"
            self.rojo_origen[i] = "reconocimiento del directorio"
            if self.config.get("revela_permisos_al_identificar"):
                self.rojo_permisos = getattr(self, "rojo_permisos", {})
                self.rojo_permisos[i] = self.identidades[i]["permiso"]
        self.puntos["RED"] += 2 * len(nuevos)
        self._ev("resource.queried", {"kind": "human", "team": "RED"}, {"kind": "resource", "id": "directorio"}, vis=["ADMIN", "RED"], data={"identificadas": nuevos})
        return {"identificadas": nuevos}

    def _h_send_email(self, a):
        p = a.get("params", {})
        iid = p.get("identidad_id")
        self._identidad(iid)
        plantilla = p.get("plantilla", "consulta_cordial")
        if plantilla not in E.PLANTILLAS_ROJO:
            raise ErrorNova(400, "Plantilla desconocida", "INVALID_SCHEMA")
        asunto = " ".join(str(p.get("asunto") or E.PLANTILLAS_ROJO[plantilla]["asunto"]).split())[:120]
        cuerpo = str(p.get("cuerpo") or "").strip()[:600]
        if re.search(r"(?i)(https?://|ftp://|www\.)", asunto + cuerpo):
            raise ErrorNova(400, "El correo no puede contener direcciones web externas: los enlaces los fija el servidor (lab://)", "INVALID_SCHEMA")
        r = self.ronda()
        if self.emails_ronda.get(r, 0) >= self.config["emails_per_round"]:
            raise ErrorNova(429, "Límite de correos de esta ronda", "BUDGET_EXCEEDED")
        self.emails_ronda[r] = self.emails_ronda.get(r, 0) + 1
        mal = E.PLANTILLAS_ROJO[plantilla]["malicioso"]
        em = self._crear_email("RED", f"{(a['actor'].get('user') or 'rojo')} <rojo@laboratorio.invalid>", iid, asunto, cuerpo or "Mensaje de laboratorio.", malicioso=mal, link=mal)
        self.puntos["RED"] += 1
        self._ev("email.sent_by_red", {"kind": a["actor"].get("kind", "human"), "team": "RED", "label": a["actor"].get("user")}, {"kind": "email", "id": em["id"]}, vis=["ADMIN", "RED"], data={"para": iid})
        return {"email_id": em["id"]}

    def _h_guess_credential(self, a):
        p = a.get("params", {})
        iid, cand = p.get("identidad_id"), str(p.get("candidate_value") or "")
        self._identidad(iid)
        if not re.match(E.PATRON_CREDENCIAL, cand):
            raise ErrorNova(400, "La candidata no cumple el patrón (5 dígitos y una letra mayúscula)", "INVALID_SCHEMA")
        self._usable(iid)
        t, r, c = self.t_s(), self.ronda(), self.config
        if t < self.guess_cooldown_hasta:
            raise ErrorNova(429, f"Espera {self.guess_cooldown_hasta - t:.0f} s antes del siguiente intento", "COOLDOWN")
        if self.guess_ronda.get(r, 0) >= c["guess_attempts_per_round"]:
            raise ErrorNova(429, "Intentos de esta ronda agotados", "BUDGET_EXCEEDED")
        if self.guess_total >= c["guess_attempts_per_match"]:
            raise ErrorNova(429, "Intentos de la partida agotados", "BUDGET_EXCEEDED")
        self.guess_ronda[r] = self.guess_ronda.get(r, 0) + 1
        self.guess_total += 1
        ok = self.secretos.verificar(cand, self.creds[iid]["hash"])
        actor = {"kind": a["actor"].get("kind", "human"), "team": "RED", "label": a["actor"].get("user")}
        self._ev("credential.guess_attempt", actor, {"kind": "credential", "id": iid}, vis=["ADMIN", "RED"], data={"candidato": self.secretos.enmascarar(cand), "acierto": ok})
        if ok:
            self.guess_cooldown_hasta = t + c["guess_cooldown_s"]
            self.fallos_identidad[iid] = 0
            self._comprometer(iid, "adivinación", actor)
            self._ev("credential.guess_success", actor, {"kind": "credential", "id": iid}, vis=["ADMIN", "RED"])
            self.puntos["RED"] += 10
            return {"acierto": True, "identidad": iid}
        self.guess_cooldown_hasta = t + c["guess_cooldown_s"]
        self.fallos_identidad[iid] = self.fallos_identidad.get(iid, 0) + 1
        self._ev("credential.guess_fail", actor, {"kind": "credential", "id": iid}, vis=["ADMIN", "RED"])
        bloqueo = self.fallos_identidad[iid] >= c["guess_lockout_after_fails"]
        if not bloqueo:
            self._sospecha_acceso(iid, cand, actor)
        if bloqueo:
            self.bloqueo_hasta[iid] = t + c["lockout_s"]
            self.fallos_identidad[iid] = 0
            self._ev("credential.lockout", {"kind": "system", "team": "SYSTEM"}, {"kind": "identity", "id": iid}, data={"hasta_s": self.bloqueo_hasta[iid]})
            self._alerta("Identidad bloqueada por intentos fallidos", iid, "ALTA", "credential.lockout")
        elif self.rng.random() < c["detect_prob_fail"]:     # detección probabilística con RNG sembrado
            self._alerta("Intento de acceso denegado", iid, "MEDIA", "credential.guess_fail")
        return {"acierto": False, "identidad": iid, "bloqueada": bloqueo}

    def _sospecha_acceso(self, iid, cand, actor):
        """Un intento fallido muy parecido a la credencial real (>= `near_miss_min` de 6 posiciones) abre una solicitud misteriosa para el AZUL:
        el motor NO decide; los humanos aceptan (lo dan por legítimo) o deniegan (bloquea la identidad). El Rojo no se entera ni recibe la similitud."""
        real = self.secretos.descifrar(self.creds[iid]["enc"])
        coinc = sum(1 for x, y in zip(cand, real) if x == y)
        if coinc < self.config["near_miss_min"] or any(a["estado"] == "PENDIENTE" and a["operacion"] == "acceso_sospechoso" and a["identidad"] == iid for a in self.aprobaciones.values()):
            return None
        ap = self._crear_aprobacion({"kind": "system", "team": "SYSTEM", "label": "Detección de accesos"}, f"Intento de acceso con una credencial muy parecida a la de {self.identidades[iid]['nombre']}", "acceso_sospechoso",
                                    self.identidades[iid]["recurso"], False, solicitante_identidad=iid)
        ap["riesgo"] = "ALTO"
        ap["recomendacion"] = {"origen": "reglas", "decision": "RECHAZAR", "motivo": "la credencial presentada se parece a la real pero no coincide"}
        ap["detalle"] = {"identidad": iid, "nombre": self.identidades[iid]["nombre"], "jugador_posible": self._jugador_de(iid), "candidato": self.secretos.enmascarar(cand), "coincidencias": coinc, "de": 6}
        return ap

    def _h_use_credential(self, a):
        return self._h_query_resource(a)

    def _h_query_resource(self, a):
        p = a.get("params", {})
        iid = p.get("identidad_id")
        self._identidad(iid)
        self._conoce(iid)
        self._usable(iid)
        rec = E.RECURSOS[self.identidades[iid]["recurso"]]
        self._ev("resource.queried", {"kind": "human", "team": "RED", "label": a["actor"].get("user")}, {"kind": "resource", "id": self.identidades[iid]["recurso"]}, vis=["ADMIN", "RED"], data={"identidad": iid})
        self._ev("credential.used", {"kind": "human", "team": "RED"}, {"kind": "credential", "id": iid}, vis=["ADMIN", "RED", "BLUE"], data={"enmascarada": self.secretos.enmascarar(self.rojo_conoce[iid])})
        if rec["protegido"]:
            self._alerta("Consulta a un recurso protegido con credencial comprometida", iid, "ALTA", "resource.queried")
        out = {"recurso": self.identidades[iid]["recurso"], "tablas": rec["tablas"]}
        if not rec["tablas"]:
            out["kpis"] = E.kpis(self.base)
        else:
            out["filas"] = {t: len(self.base[t]) for t in rec["tablas"]}
        return out

    def _h_extract_table(self, a):
        p = a.get("params", {})
        iid, tabla = p.get("identidad_id"), p.get("tabla")
        self._identidad(iid)
        if tabla not in E.TABLAS:
            raise ErrorNova(400, "Tabla desconocida", "INVALID_SCHEMA")
        self._conoce(iid)
        self._usable(iid)
        if not self._tabla_permitida(iid, tabla):
            self._ev("extraction.blocked", {"kind": "human", "team": "RED", "label": a["actor"].get("user")}, {"kind": "resource", "id": tabla}, result="DENIED", vis=["ADMIN", "RED", "BLUE"], data={"identidad": iid})
            raise ErrorNova(403, f"La identidad {iid} no tiene permiso sobre la tabla {tabla}", "PERMISSION_DENIED")
        self._ev("extraction.started", {"kind": "human", "team": "RED"}, {"kind": "resource", "id": tabla}, vis=["ADMIN", "RED", "BLUE"], data={"identidad": iid})
        self._guardar_extraccion(tabla)
        self.puntos["RED"] += 40 if tabla in E.PROTEGIDAS else 8
        if tabla in E.PROTEGIDAS:
            self._alerta(f"Extracción de la tabla protegida {tabla}", iid, "CRITICA", "extraction.completed")
        if tabla == "empleados":       # el directorio contiene las credenciales de laboratorio: quedan EXPUESTAS (cascada realista del escenario)
            for i in self.identidades:
                if i not in self.rojo_conoce:
                    self._comprometer(i, "tabla empleados extraída", {"kind": "human", "team": "RED"}, silencioso=True)
        return {"tabla": tabla, "filas": len(self.base[tabla])}

    def _guardar_extraccion(self, tabla):
        self.extraido[tabla] = [dict(f) for f in self.base[tabla]]
        self.db.execute("INSERT OR REPLACE INTO nova_extracted VALUES(?,?,?)", (self.id, tabla, len(self.base[tabla])))
        self.db.commit()
        self._ev("extraction.completed", {"kind": "human", "team": "RED"}, {"kind": "resource", "id": tabla}, vis=["ADMIN", "RED", "BLUE", "SPECTATOR"], data={"tabla": tabla, "filas": len(self.base[tabla]), "protegida": tabla in E.PROTEGIDAS})

    def _h_export_database(self, a):
        if self.t_s() >= self.grants_db_export_hasta:
            raise ErrorNova(403, "Nadie tiene permiso db_export: hace falta una elevación aprobada por el equipo Azul", "PERMISSION_DENIED")
        for t in E.TABLAS:
            self._guardar_extraccion(t)
        self.puntos["RED"] += 80
        self._alerta("Copia completa de la base de datos", None, "CRITICA", "extraction.completed")
        return {"tablas": len(E.TABLAS)}

    def _h_request_elevation(self, a):
        p = a.get("params", {})
        motivo = str(p.get("motivo") or "").strip()[:300]
        if not motivo:
            raise ErrorNova(400, "La solicitud necesita un motivo", "INVALID_SCHEMA")
        ap = self._crear_aprobacion({"kind": "human", "team": "RED", "label": a["actor"].get("user")}, motivo, "db_export", "NovaStore_Lab", legitima=False, solicitante_identidad=p.get("identidad_id"))
        return {"approval_id": ap["id"]}

    def _h_respond_info(self, a):
        ap = self.aprobaciones.get(a.get("params", {}).get("approval_id"))
        if not ap or ap["estado"] != "INFO_SOLICITADA":
            raise ErrorNova(409, "No hay una solicitud esperando información", "INVALID_STATE")
        ap["respuesta_info"] = str(a["params"].get("texto") or "")[:300]
        self._ev("approval.info_provided", {"kind": "human", "team": "RED"}, {"kind": "approval", "id": ap["id"]}, vis=["ADMIN", "RED", "BLUE"], data={"texto": ap["respuesta_info"]})
        return {}

    def _h_message_team(self, a):
        txt = str(a.get("params", {}).get("texto", "")).strip()[:300]
        if not txt:
            raise ErrorNova(400, "El mensaje está vacío", "INVALID_SCHEMA")
        self.mensajes.append({"id": len(self.mensajes) + 1, "equipo": a["actor"].get("team"), "autor": a["actor"].get("user"), "texto": txt, "ts_s": self.t_s()})
        self._ev("message.sent", {"kind": a["actor"].get("kind", "human"), "team": a["actor"].get("team"), "label": a["actor"].get("user")}, vis=["ADMIN", a["actor"].get("team", "ADMIN")], data={"texto": str(a.get("params", {}).get("texto", ""))[:300]})
        return {}

    # ── comprometer / exposición (D6) ────────────────────────────────────────────────────────────────
    def _comprometer(self, iid, origen, actor, silencioso=False):
        c = self.creds[iid]
        if c["estado"] in ("SUSPENDIDA", "REVOCADA"):
            return False
        if c["estado"] == "PROTEGIDA":
            self._ev("credential.exposed", {"kind": "system", "team": "SYSTEM"}, {"kind": "credential", "id": iid}, vis=["ADMIN", "BLUE"], data={"origen": origen})
        c["estado"] = "COMPROMETIDA"
        self.rojo_conoce[iid] = self.secretos.descifrar(c["enc"])
        self.rojo_estado[iid] = "VALIDA_DESCUBIERTA"
        self.rojo_origen[iid] = origen
        self._ev("credential.validated_by_engine", {"kind": "system", "team": "SYSTEM"}, {"kind": "credential", "id": iid}, vis=["ADMIN", "RED", "BLUE"], data={"enmascarada": self.secretos.enmascarar(self.rojo_conoce[iid]), "origen": origen})
        if not silencioso:
            self._abrir_incidente(iid)
        return True

    def _abrir_incidente(self, iid):
        if not any(i["estado"] != "CERRADO" for i in self.incidentes.values()):
            inc = {"id": "INC-001", "estado": "ABIERTO", "titulo": "Posible compromiso de credencial de laboratorio", "identidades": [iid], "ts_s": self.t_s()}
            self.incidentes[inc["id"]] = inc
            self._ev("incident.created", {"kind": "system", "team": "SYSTEM"}, {"kind": "incident", "id": inc["id"]}, vis=["ADMIN", "BLUE"], data={"identidad": iid})
        else:
            for i in self.incidentes.values():
                if iid not in i["identidades"]:
                    i["identidades"].append(iid)

    def _alerta(self, titulo, iid, severidad, origen_evento):
        aid = "AL-" + str(len(self.alertas) + 1).zfill(3)
        self.alertas[aid] = {"id": aid, "titulo": titulo, "identidad": iid, "severidad": severidad, "estado": "NUEVA", "ts_s": self.t_s(), "origen": origen_evento}
        if self.config.get("alertas_con_detalle"):
            self.alertas[aid]["detalle"] = f"origen {origen_evento} · identidad {iid or '—'} · t={self.t_s():.0f}s · ronda {self.ronda()}"
        self._ev("alert.created", {"kind": "system", "team": "SYSTEM"}, {"kind": "alert", "id": aid}, vis=["ADMIN", "BLUE"], data={"titulo": titulo, "severidad": severidad, "identidad": iid})
        return aid

    # ── cadena de correo → enlace → exposición ────────────────────────────────────────────────────────
    def _h_open_email(self, a):
        em = self._email_de(a)
        if not em["leido"]:
            em["leido"] = True
            self._ev("email.opened", {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "email", "id": em["id"]}, vis=["ADMIN", "BLUE"])
        return {"asunto": em["asunto"], "de": em["de"], "tiene_enlace": bool(em["link_id"])}     # abrir NO compromete nada

    def _email_de(self, a):
        em = self.emails.get(a.get("params", {}).get("email_id"))
        if not em:
            raise ErrorNova(404, "Correo desconocido", "UNKNOWN_TARGET")
        if a["actor"].get("team") == "BLUE" and not self._es_de_su_identidad(a["actor"].get("user"), em["para"]):
            raise ErrorNova(403, "Ese correo no está en tu bandeja", "NOT_YOUR_INBOX")
        return em

    def _es_de_su_identidad(self, user, iid):
        p = self.participantes.get(user)
        return bool(p and p["equipo"] == "BLUE" and p["identidad"] == iid)

    def _link_de(self, a):
        lk = self.links.get(a.get("params", {}).get("link_id"))
        if not lk:
            raise ErrorNova(404, "Enlace desconocido", "UNKNOWN_TARGET")
        if a["actor"].get("team") == "BLUE" and not self._es_de_su_identidad(a["actor"].get("user"), lk["para"]):
            raise ErrorNova(403, "Ese enlace no está en tu bandeja", "NOT_YOUR_INBOX")
        return lk

    def _h_view_link(self, a):
        lk = self._link_de(a)
        lk["visto"] = True
        self._ev("link.viewed", {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "link", "id": lk["id"]}, vis=["ADMIN", "BLUE"])
        return {"url": lk["url"]}

    def _h_click_link(self, a):
        lk = self._link_de(a)
        lk["clic"] = True
        self._ev("link.clicked", {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "link", "id": lk["id"]}, vis=["ADMIN", "BLUE"], data={"neutralizado": lk["neutralizado"]})
        return {"pagina": "portal_interno_de_laboratorio", "boton": "Iniciar sesión con mi identidad de laboratorio",
                "aviso": "Es una página interna del laboratorio: no existe ningún campo para escribir contraseñas."}

    def _h_risk_action(self, a):
        lk = self._link_de(a)
        return self._riesgo(lk, {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")})

    def _riesgo(self, lk, actor):
        lk["riesgo"] = True
        self._ev("risk_action.completed", actor, {"kind": "link", "id": lk["id"]}, vis=["ADMIN", "BLUE"], data={"identidad": lk["para"]})
        expone = lk["malicioso"] and not lk["neutralizado"] and self.creds[lk["para"]]["estado"] not in ("SUSPENDIDA", "REVOCADA")
        if expone:
            self._comprometer(lk["para"], "enlace malicioso pulsado", actor)
            self.puntos["RED"] += 15
            self._alerta("Credencial expuesta tras una acción de riesgo", lk["para"], "ALTA", "risk_action.completed")
        return {"credencial_expuesta": expone}

    def _clic_guionizado(self, cp):
        lk = self.links.get(cp["link_id"])
        if lk:
            self._ev("link.clicked", {"kind": "system", "team": "SYSTEM", "label": "empleado guionizado"}, {"kind": "link", "id": lk["id"]}, vis=["ADMIN", "BLUE"])
            self._riesgo(lk, {"kind": "system", "team": "SYSTEM", "label": "empleado guionizado"})

    # ── acciones del Azul ─────────────────────────────────────────────────────────────────────────────
    def _h_classify_email(self, a):
        em = self._email_de(a)
        em["clasificado"] = a["params"].get("clasificacion")
        self._ev("email.classified", {"kind": a["actor"].get("kind", "human"), "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "email", "id": em["id"]}, vis=["ADMIN", "BLUE"], data={"clasificacion": em["clasificado"]})
        return {}

    def _h_report_email(self, a):
        em = self._email_de(a)
        em["reportado"] = True
        self._ev("email.reported", {"kind": a["actor"].get("kind", "human"), "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "email", "id": em["id"]}, vis=["ADMIN", "BLUE"])
        if em["origen"] == "RED":
            self.puntos["BLUE"] += 5
        return {}

    def _h_block_link(self, a):
        lk = self._link_de(a)
        lk["neutralizado"] = True
        self._ev("link.neutralized", {"kind": a["actor"].get("kind", "human"), "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "link", "id": lk["id"]}, vis=["ADMIN", "BLUE"])
        if lk["malicioso"]:
            self.puntos["BLUE"] += 5
        return {}

    def _h_revoke_credential(self, a):
        return self._cambiar_cred(a, "REVOCADA")

    def _h_suspend_identity(self, a):
        return self._cambiar_cred(a, "SUSPENDIDA")

    def _cambiar_cred(self, a, nuevo):
        iid = a.get("params", {}).get("identidad_id")
        self._identidad(iid)
        c = self.creds[iid]
        previo = c["estado"]
        c["estado"] = nuevo
        if previo in ("EXPUESTA", "COMPROMETIDA"):
            self.puntos["BLUE"] += 10
        elif previo == "PROTEGIDA":
            self.puntos["BLUE"] -= 5       # falso positivo: revocar/suspender sin motivo penaliza (anti «rechazar todo»)
        self.rojo_estado[iid] = "BLOQUEADA" if iid in self.rojo_conoce or self.rojo_estado[iid] != "DESCONOCIDA" else self.rojo_estado[iid]
        self._ev("credential." + ("revoked" if nuevo == "REVOCADA" else "suspended"), {"kind": a["actor"].get("kind", "human"), "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "credential", "id": iid},
                 vis=["ADMIN", "BLUE", "RED"], data={"previo": previo})
        return {"previo": previo}

    def _h_contain_incident(self, a):
        inc = self.incidentes.get(a.get("params", {}).get("incident_id"))
        if not inc:
            raise ErrorNova(404, "Incidente desconocido", "UNKNOWN_TARGET")
        pendientes = [i for i in inc["identidades"] if self.creds[i]["estado"] in ("EXPUESTA", "COMPROMETIDA")]
        if pendientes:
            raise ErrorNova(409, "Aún hay credenciales comprometidas sin revocar o suspender", "INVALID_STATE")
        inc["estado"] = "CONTENIDO"
        self.puntos["BLUE"] += 10
        self._ev("incident.contained", {"kind": a["actor"].get("kind", "human"), "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "incident", "id": inc["id"]}, vis=["ADMIN", "BLUE"])
        return {}

    def _h_set_alert_status(self, a):
        al = self.alertas.get(a.get("params", {}).get("alert_id"))
        nuevo = a.get("params", {}).get("estado")
        if not al:
            raise ErrorNova(404, "Alerta desconocida", "UNKNOWN_TARGET")
        if nuevo not in TRANS_ALERTA.get(al["estado"], set()):
            raise ErrorNova(409, f"Transición de alerta no válida: {al['estado']} → {nuevo}", "INVALID_TRANSITION")
        al["estado"] = nuevo
        self._ev("alert.status_changed", {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "alert", "id": al["id"]}, vis=["ADMIN", "BLUE"], data={"estado": nuevo})
        if nuevo == "FALSO_POSITIVO" and al["origen"] in ("credential.guess_fail", "credential.lockout"):
            self.puntos["BLUE"] -= 3       # descartar un ataque real como falso positivo penaliza
        return {}

    def _h_assign_task(self, a):
        p = a.get("params", {})
        titulo = str(p.get("titulo") or "").strip()[:120]
        if not titulo:
            raise ErrorNova(400, "La tarea necesita un título", "INVALID_SCHEMA")
        tid = "TK-" + str(len(self.tareas) + 1).zfill(3)
        self.tareas[tid] = {"id": tid, "titulo": titulo, "asignado": p.get("asignado") or a["actor"].get("user"), "estado": "PENDIENTE", "ts_s": self.t_s()}
        self._ev("task.created", {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "task", "id": tid}, vis=["ADMIN", "BLUE"], data={"titulo": titulo})
        return {"task_id": tid}

    def _h_set_task_status(self, a):
        t = self.tareas.get(a.get("params", {}).get("task_id"))
        nuevo = a.get("params", {}).get("estado")
        if not t:
            raise ErrorNova(404, "Tarea desconocida", "UNKNOWN_TARGET")
        if nuevo not in TRANS_TAREA.get(t["estado"], set()):
            raise ErrorNova(409, f"Transición de tarea no válida: {t['estado']} → {nuevo}", "INVALID_TRANSITION")
        t["estado"] = nuevo
        self._ev("task.status_changed", {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")}, {"kind": "task", "id": t["id"]}, vis=["ADMIN", "BLUE"], data={"estado": nuevo})
        return {}

    def _h_allow(self, a):
        return {}

    # ── aprobaciones (flujo solicitud → decisión → consecuencia) ─────────────────────────────────────
    def _crear_aprobacion(self, actor, motivo, operacion, recurso, legitima, email_id=None, solicitante_identidad=None):
        aid = "AP-" + str(len(self.aprobaciones) + 1).zfill(3)
        riesgo = "ALTO" if operacion == "db_export" else "BAJO"
        ap = {"id": aid, "estado": "PENDIENTE", "solicitante": actor.get("label") or actor.get("team"), "equipo_solicitante": actor.get("team"), "operacion": operacion, "recurso": recurso, "motivo": motivo,
              "riesgo": riesgo, "legitima": legitima, "email_id": email_id, "identidad": solicitante_identidad, "ts_s": self.t_s(), "expira_s": self.t_s() + self.config["approval_ttl_s"],
              "recomendacion": {"origen": "reglas", "decision": "RECHAZAR" if operacion == "db_export" else "APROBAR", "motivo": "copia completa de la base: exige verificación fuerte" if operacion == "db_export" else "operación rutinaria dentro de los permisos"}}
        self.aprobaciones[aid] = ap
        self._ev("approval.requested", actor, {"kind": "approval", "id": aid}, vis=["ADMIN", "BLUE"] + (["RED"] if actor.get("team") == "RED" else []), data={"operacion": operacion, "recurso": recurso, "riesgo": riesgo})
        return ap

    def _aprob_estado(self, ap, nuevo, actor):
        if nuevo not in TRANS_APROB.get(ap["estado"], set()):
            raise ErrorNova(409, f"La solicitud ya está {ap['estado']}", "INVALID_TRANSITION")
        ap["estado"] = nuevo
        ap["resuelta_por"] = actor.get("label") or actor.get("team")
        self._ev({"APROBADA": "approval.approved", "RECHAZADA": "approval.rejected", "INFO_SOLICITADA": "approval.info_requested", "ESCALADA": "approval.escalated", "EXPIRADA": "approval.rejected"}[nuevo],
                 actor, {"kind": "approval", "id": ap["id"]}, result="EXPIRED" if nuevo == "EXPIRADA" else "OK", vis=["ADMIN", "BLUE", "RED"] if ap["equipo_solicitante"] == "RED" else ["ADMIN", "BLUE"], data={"estado": nuevo})

    def _ap(self, a):
        ap = self.aprobaciones.get(a.get("params", {}).get("approval_id"))
        if not ap:
            raise ErrorNova(404, "Solicitud desconocida", "UNKNOWN_TARGET")
        return ap

    def _h_approve_request(self, a):
        ap = self._ap(a)
        actor = {"kind": a["actor"].get("kind", "human"), "team": "BLUE", "label": a["actor"].get("user")}
        self._aprob_estado(ap, "APROBADA", actor)
        if ap["legitima"]:
            self.legitimas["resueltas"] += 1
            self.legitimas["servidas"] += 1
            self.puntos["BLUE"] += 3
        elif ap["operacion"] == "acceso_sospechoso":       # Azul lo acepta como acceso legítimo: era un ataque, la defensa pierde puntos y el contador de fallos se reinicia
            self.fallos_identidad[ap["identidad"]] = 0
            self.puntos["BLUE"] -= 5
            self._ev("access.suspicious_accepted", actor, {"kind": "identity", "id": ap["identidad"]}, vis=["ADMIN", "BLUE"])
        elif ap["operacion"] == "db_export":       # la consecuencia SÍ cambia el estado del escenario: concede el permiso db_export por un tiempo
            self.grants_db_export_hasta = self.t_s() + self.config["elevation_grant_s"]
            self.puntos["BLUE"] -= 10
            self._ev("credential.permissions_changed", {"kind": "system", "team": "SYSTEM"}, {"kind": "credential", "id": "db_export"}, vis=["ADMIN", "BLUE", "RED"], data={"concedido_hasta_s": self.grants_db_export_hasta})
        return {"estado": ap["estado"]}

    def _h_reject_request(self, a):
        ap = self._ap(a)
        self._aprob_estado(ap, "RECHAZADA", {"kind": a["actor"].get("kind", "human"), "team": "BLUE", "label": a["actor"].get("user")})
        if ap["operacion"] == "acceso_sospechoso":       # denegar bloquea la identidad atacada: la consecuencia cambia el estado
            self.bloqueo_hasta[ap["identidad"]] = self.t_s() + self.config["lockout_s"]
            self.puntos["BLUE"] += 5
            self._ev("credential.lockout", {"kind": "system", "team": "SYSTEM"}, {"kind": "identity", "id": ap["identidad"]}, data={"hasta_s": self.bloqueo_hasta[ap["identidad"]], "motivo": "acceso sospechoso denegado"})
        elif ap["legitima"]:
            self.legitimas["resueltas"] += 1
            self.puntos["BLUE"] -= 3       # rechazar una solicitud legítima penaliza
        else:
            self.puntos["BLUE"] += 5
        return {"estado": ap["estado"]}

    def _h_request_more_info(self, a):
        ap = self._ap(a)
        self._aprob_estado(ap, "INFO_SOLICITADA", {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")})
        return {}

    def _h_escalate(self, a):
        ap = self._ap(a)
        self._aprob_estado(ap, "ESCALADA", {"kind": "human", "team": "BLUE", "label": a["actor"].get("user")})
        return {}

    # ── puntuación, victoria y resultado (D7, D8) ─────────────────────────────────────────────────────
    def continuidad(self):
        e = self.legitimas["entregadas"]
        return 1.0 if e == 0 else self.legitimas["servidas"] / e

    def _win_rojo(self):
        w = self.config["win"]
        reglas = set(w["reglas"])
        w1 = "W1" in reglas and w["w1_tabla"] in self.extraido
        w2 = "W2" in reglas and all(t in self.extraido for t in E.TABLAS)
        w3 = "W3" in reglas and sum(len(self.extraido.get(t, [])) for t in E.PROTEGIDAS) >= w["w3_umbral_registros"]
        res = {"W1": w1, "W2": w2, "W3": w3}
        sel = [k for k in reglas if res.get(k)]
        return (bool(sel) if w["modo"] == "any_of" else len(sel) == len(reglas)), sel

    def _evaluar_final(self, forzado=False):
        if self.resultado is not None:
            return
        ok, sel = self._win_rojo()
        if ok:      # la victoria Roja la da SOLO `extraction.completed` del motor (nunca texto de un modelo)
            self._ev("win.condition_met", vis=["ADMIN", "RED", "BLUE", "SPECTATOR"], data={"reglas": sel})
            return self._cerrar("VICTORIA_ROJA", f"extracción validada por el motor ({', '.join(sel)})")
        comprometidas = [i for i, c in self.creds.items() if c["estado"] in ("EXPUESTA", "COMPROMETIDA")]
        hubo = any(e["type"] == "credential.validated_by_engine" for e in self.eventos_lista)
        inc_ok = all(i["estado"] in ("CONTENIDO", "CERRADO") for i in self.incidentes.values())
        if hubo and not comprometidas and inc_ok and self.continuidad() >= self.config["min_continuity"] and not forzado:
            return self._cerrar("VICTORIA_AZUL", "contención completa: credenciales revocadas, incidente contenido y continuidad suficiente")
        if forzado or self.t_s() >= self.config["duration_s"]:
            if self.continuidad() < self.config["min_continuity"]:
                return self._cerrar("EMPATE" if self.config["abuse_policy"] == "empate" else "VICTORIA_ROJA", "defensa abusiva: la continuidad legítima cayó bajo el umbral")
            if self.puntos["BLUE"] >= self.puntos["RED"]:
                return self._cerrar("VICTORIA_AZUL", "tiempo agotado sin extracción protegida y con continuidad suficiente")
            return self._cerrar("EMPATE", "tiempo agotado: la ventaja de puntos es del Rojo pero sin extracción protegida")

    def _cerrar(self, resultado, motivo):
        if self.resultado is not None:
            return self.resultado
        if self.estado == "EN_CURSO":
            self.reloj.detener()
            self.estado = "FINALIZADA"
            self._ev("match.finished", data={"motivo": motivo})
        r = {"resultado": resultado, "motivo": motivo, "match_id": self.id, "puntos": dict(self.puntos), "continuidad": round(self.continuidad(), 3), "tablas_extraidas": sorted(self.extraido),
             "duracion_s": round(self.t_s(), 1)}
        self.resultado = r
        self.db.execute("INSERT OR IGNORE INTO nova_results VALUES(?,?,?,?)", (self.id, resultado, json.dumps(r, ensure_ascii=False), _utc()))
        self.db.commit()
        self._ev("match.result", vis=["ADMIN", "RED", "BLUE", "SPECTATOR"], data=r)
        return r

    # ── descarga (solo con datos realmente extraídos) ────────────────────────────────────────────────
    def descarga(self, formato):
        if not self.extraido:
            raise ErrorNova(409, "No hay datos extraídos: no hay nada que descargar", "NO_DATA")
        if formato == "json":
            return "application/json", json.dumps(self.extraido, ensure_ascii=False, indent=1)
        if formato == "csv":
            import csv
            import io
            buf = io.StringIO()
            for t, filas in self.extraido.items():
                buf.write(f"# tabla: {t}\n")
                w = csv.DictWriter(buf, fieldnames=list(filas[0].keys()) if filas else [])
                w.writeheader()
                w.writerows(filas)
                buf.write("\n")
            return "text/csv", buf.getvalue()
        if formato == "sql":
            out = []
            for t, filas in self.extraido.items():
                for f in filas:
                    cols = ", ".join(f)
                    vals = ", ".join("'" + str(v).replace("'", "''") + "'" if isinstance(v, str) else str(v) for v in f.values())
                    out.append(f"INSERT INTO {t} ({cols}) VALUES ({vals});")
            return "application/sql", "\n".join(out) + "\n"
        raise ErrorNova(400, "Formato no válido (csv, json o sql)", "INVALID_SCHEMA")

    # ── vistas por rol (la visibilidad se filtra en el servidor) ────────────────────────────────────
    def vista_rojo(self):
        """Panel «Credenciales y accesos descubiertos»: el Rojo ve estados y SOLO los valores que descubrió (enmascarados)."""
        out = []
        for iid, i in self.identidades.items():
            est = self.rojo_estado[iid]
            if self.creds[iid]["estado"] in ("SUSPENDIDA", "REVOCADA") and est != "DESCONOCIDA":
                est = "BLOQUEADA"
            d = {"id": iid, "estado": est}
            if est != "DESCONOCIDA":
                d.update(nombre=i["nombre"], depto=i["depto"], origen=self.rojo_origen.get(iid))
                if iid in getattr(self, "rojo_permisos", {}):
                    d["permiso"] = self.rojo_permisos[iid]
            if iid in self.rojo_conoce:
                d["credencial"] = self.secretos.enmascarar(self.rojo_conoce[iid])
            out.append(d)
        return out

    def vista_azul(self, nombre):
        p = self.participantes.get(nombre) or {}
        iid = p.get("identidad")
        return {"identidad": {**self.identidades[iid], "estado_credencial": self.creds[iid]["estado"]} if iid else None,
                "correos": [e for e in self.emails.values() if e["para"] == iid], "alertas": list(self.alertas.values()), "incidentes": list(self.incidentes.values()),
                "aprobaciones": list(self.aprobaciones.values()), "tareas": list(self.tareas.values()), "mensajes": [x for x in self.mensajes if x["equipo"] == "BLUE"][-30:], "misiones": self.misiones("BLUE")}

    def misiones(self, equipo):
        """Misiones del equipo, con estado DERIVADO del estado real del motor (nada se marca a mano): PENDIENTE → DISPONIBLE → EN_PROGRESO → COMPLETADA."""
        tipos = {e["type"] for e in self.eventos_lista}
        creds_c = [i for i, c in self.creds.items() if c["estado"] in ("EXPUESTA", "COMPROMETIDA")]
        rev = [i for i, c in self.creds.items() if c["estado"] in ("SUSPENDIDA", "REVOCADA")]
        if equipo == "RED":
            m = [("M-R1", "Identificar identidades del directorio", any(v != "DESCONOCIDA" for v in self.rojo_estado.values()), "resource.queried" in tipos),
                 ("M-R2", "Obtener una credencial válida", bool(self.rojo_conoce), "email.sent_by_red" in tipos or "credential.guess_attempt" in tipos),
                 ("M-R3", "Extraer la tabla protegida reportes_financieros", "reportes_financieros" in self.extraido, bool(self.rojo_conoce)),
                 ("M-R4", "Conseguir la copia completa de la base", len(self.extraido) == len(E.TABLAS), any(a["estado"] == "PENDIENTE" and a["operacion"] == "db_export" for a in self.aprobaciones.values()))]
        else:
            m = [("M-B1", "Reportar un correo del Rojo", any(e["reportado"] and e["origen"] == "RED" for e in self.emails.values()), any(e["origen"] == "RED" for e in self.emails.values())),
                 ("M-B2", "Revocar o suspender toda credencial comprometida", bool(rev) and not creds_c, bool(creds_c)),
                 ("M-B3", "Contener el incidente", bool(self.incidentes) and all(i["estado"] in ("CONTENIDO", "CERRADO") for i in self.incidentes.values()), bool(self.incidentes)),
                 ("M-B4", "Atender las solicitudes legítimas (continuidad ≥ umbral)", self.legitimas["entregadas"] > 0 and self.continuidad() >= self.config["min_continuity"] and self.legitimas["resueltas"] == self.legitimas["entregadas"], self.legitimas["entregadas"] > 0)]
        return [{"id": i, "titulo": t, "estado": "COMPLETADA" if hecho else "EN_PROGRESO" if prog else "DISPONIBLE"} for i, t, hecho, prog in m]

    def catalogo_admin(self):
        """El administrador ve TODO el catálogo, con el valor descifrado solo aquí (nunca en logs ni eventos)."""
        return [{**self.identidades[i], "estado": c["estado"], "credencial": self.secretos.descifrar(c["enc"]), "debil": c["debil"]} for i, c in self.creds.items()]

    def metricas(self):
        return {"puntos": dict(self.puntos), "continuidad": round(self.continuidad(), 3), "acciones": len(self.acciones), "rechazadas": sum(1 for x in self.acciones if not x["ok"]),
                "eventos": self.seq, "tablas_extraidas": sorted(self.extraido), "estado": self.estado, "resultado": self.resultado}
