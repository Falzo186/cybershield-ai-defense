"""Solicitudes de autorización (CyberShield Repair §8). Máquina de estados + almacén persistente (SQLite), sin HTTP.

Estados: PENDIENTE -> APROBADA | RECHAZADA | EXPIRADA | CANCELADA. Solo se sale de PENDIENTE, una vez (las demás transiciones son 409).

Transición            Evento             Actor autorizado              Efectos
PENDIENTE->APROBADA   aprobar            jugador/árbitro de Azul       registra quién y cuándo; NO ejecuta nada (el motor sigue validando)
PENDIENTE->RECHAZADA  rechazar           jugador/árbitro de Azul       registra quién y cuándo
PENDIENTE->EXPIRADA   vencer             sistema (tiempo de partida)   registra el vencimiento; nunca queda pendiente indefinidamente
PENDIENTE->CANCELADA  cancelar           quien la creó o el árbitro    registra quién y cuándo

El tiempo es el de la PARTIDA (se congela en pausa): se inyecta `reloj_s()` (p. ej. `partida.transcurrido_s`).
La aceptación humana es solo una DECISIÓN REGISTRADA: no salta ningún permiso ni capa del motor. La recomendación indica su origen
(`reglas` = heurística determinista, `ia` = el defensor IA); nunca se presenta una regla como si fuera IA.
Idempotencia: `clave_origen` única por (partida, clave): reintentar la misma creación devuelve la solicitud existente.
"""
import json
import sqlite3
import threading
from datetime import datetime

ESTADOS = ("PENDIENTE", "APROBADA", "RECHAZADA", "EXPIRADA", "CANCELADA")
TTL_S = 120
RIESGOS = ("BAJO", "MEDIO", "ALTO")
# Recursos «sensibles»: la heurística determinista sube su riesgo. Son ejemplos del laboratorio, no una política real.
RECURSOS_ALTO = ("credenciales", "clientes", "configuracion", "admin")


class ErrorSolicitud(Exception):
    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status, self.mensaje = status, mensaje


def recomendacion_por_reglas(operacion, recurso):
    """Heurística DETERMINISTA y etiquetada como tal (origen «reglas»)."""
    alto = any(k in f"{operacion} {recurso}".lower() for k in RECURSOS_ALTO)
    return {"origen": "reglas", "decision": "RECHAZAR" if alto else "VERIFICAR",
            "motivo": "recurso sensible: no se aprueba sin verificar la identidad por otro canal" if alto
            else "operación de riesgo moderado: verifica la identidad antes de aprobar"}, ("ALTO" if alto else "MEDIO")


class Solicitudes:
    def __init__(self, conn, reloj_s, ttl_s=TTL_S):
        self.conn, self.reloj_s, self.ttl_s = conn, reloj_s, ttl_s
        self._c = threading.RLock()
        with self._c, self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS solicitudes_autorizacion(
                id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT NOT NULL, clave_origen TEXT NOT NULL, identidad TEXT NOT NULL,
                jugador TEXT NOT NULL, operacion TEXT NOT NULL, recurso TEXT NOT NULL, motivo TEXT NOT NULL, riesgo TEXT NOT NULL,
                recomendacion TEXT NOT NULL, estado TEXT NOT NULL, creada TEXT NOT NULL, creada_s REAL NOT NULL, expira_s REAL NOT NULL,
                resuelta_por TEXT, resuelta TEXT, UNIQUE(partida, clave_origen))""")

    # ── creación ────────────────────────────────────────────────────────────────────────────────────
    def crear(self, partida, clave_origen, identidad, jugador, operacion, recurso, motivo, riesgo=None, recomendacion=None):
        """-> (solicitud, creada_ahora). Idempotente por (partida, clave_origen)."""
        operacion, recurso, motivo = (str(x or "").strip()[:200] for x in (operacion, recurso, motivo))
        if not (operacion and recurso and motivo):
            raise ErrorSolicitud(400, "Faltan operación, recurso o motivo.")
        rec, r = (recomendacion, riesgo) if recomendacion else recomendacion_por_reglas(operacion, recurso)
        r = r or riesgo or "MEDIO"
        if r not in RIESGOS:
            raise ErrorSolicitud(400, f"Riesgo no válido: {r}")
        with self._c:
            previa = self._fila("partida=? AND clave_origen=?", (partida, str(clave_origen)))
            if previa:
                return previa, False
            ahora = float(self.reloj_s() or 0)
            with self.conn:
                self.conn.execute(
                    "INSERT INTO solicitudes_autorizacion(partida,clave_origen,identidad,jugador,operacion,recurso,motivo,riesgo,recomendacion,"
                    "estado,creada,creada_s,expira_s) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (partida, str(clave_origen), identidad, jugador, operacion, recurso, motivo, r, json.dumps(rec, ensure_ascii=False),
                     "PENDIENTE", datetime.now().astimezone().isoformat(timespec="seconds"), ahora, ahora + self.ttl_s))
            return self._fila("partida=? AND clave_origen=?", (partida, str(clave_origen))), True

    # ── transiciones ───────────────────────────────────────────────────────────────────────────────
    def _transicion(self, sid, nuevo, quien):
        with self._c:
            self.vencer()
            f = self._fila("id=?", (sid,))
            if f is None:
                raise ErrorSolicitud(404, "Solicitud desconocida.")
            if f["estado"] != "PENDIENTE":
                raise ErrorSolicitud(409, f"La solicitud ya está {f['estado']}: no admite más cambios.")
            with self.conn:
                self.conn.execute("UPDATE solicitudes_autorizacion SET estado=?, resuelta_por=?, resuelta=? WHERE id=? AND estado='PENDIENTE'",
                                  (nuevo, quien, datetime.now().astimezone().isoformat(timespec="seconds"), sid))
            return self._fila("id=?", (sid,))

    def aprobar(self, sid, quien):
        return self._transicion(sid, "APROBADA", quien)

    def rechazar(self, sid, quien):
        return self._transicion(sid, "RECHAZADA", quien)

    def cancelar(self, sid, quien):
        return self._transicion(sid, "CANCELADA", quien)

    def vencer(self):
        """PENDIENTE cuyo plazo (tiempo de partida) pasó -> EXPIRADA. -> ids vencidos."""
        with self._c:
            ahora = float(self.reloj_s() or 0)
            ids = [r[0] for r in self.conn.execute("SELECT id FROM solicitudes_autorizacion WHERE estado='PENDIENTE' AND expira_s<=?", (ahora,))]
            if ids:
                with self.conn:
                    self.conn.execute(f"UPDATE solicitudes_autorizacion SET estado='EXPIRADA', resuelta_por='sistema', resuelta=? "
                                      f"WHERE id IN ({','.join('?' * len(ids))}) AND estado='PENDIENTE'",
                                      (datetime.now().astimezone().isoformat(timespec="seconds"), *ids))
            return ids

    # ── consulta ───────────────────────────────────────────────────────────────────────────────────
    def _q(self, sql, args=()):
        cur = self.conn.cursor()
        cur.row_factory = sqlite3.Row      # sin tocar la fábrica de filas de la conexión compartida
        return cur.execute(sql, args)

    def _fila(self, donde, args):
        f = self._q(f"SELECT * FROM solicitudes_autorizacion WHERE {donde}", args).fetchone()
        return self._publica(dict(f)) if f else None

    def _publica(self, f):
        f["recomendacion"] = json.loads(f["recomendacion"])
        f["tiempo_restante_s"] = max(0, int(round(f["expira_s"] - float(self.reloj_s() or 0)))) if f["estado"] == "PENDIENTE" else 0
        for k in ("clave_origen", "creada_s", "expira_s"):
            f.pop(k, None)
        return f

    def listar(self, partida, estado=None, jugador=None):
        with self._c:
            self.vencer()
            q, a = "partida=?", [partida]
            if estado:
                q += " AND estado=?"
                a.append(estado)
            if jugador:
                q += " AND jugador=?"
                a.append(jugador)
            return [self._publica(dict(f)) for f in self._q(
                f"SELECT * FROM solicitudes_autorizacion WHERE {q} ORDER BY id DESC", a).fetchall()]

    def obtener(self, sid):
        with self._c:
            self.vencer()
            return self._fila("id=?", (sid,))
