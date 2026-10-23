"""Repositorio: ÚNICO punto de acceso a la BD. Consultas fijas y parametrizadas, autorizador y auditoría.

Es la última capa de defensa: aunque la IA o la capa de herramientas fallen, aquí se vuelve a
comprobar el acceso. No existe ningún camino para ejecutar SQL arbitrario.
"""
import json
import secrets
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import correos, documentos, permisos, schema, seed
from .permisos import Identidad

RUTA_DB = Path(__file__).resolve().parents[2] / "data" / "lab.db"
# Salida para un SIEM (p. ej. Wazuh, aún sin integrar): una línea JSON por evento relevante.
RUTA_EVENTOS = RUTA_DB.parent / "eventos.jsonl"
PARTIDA = None  # id de la partida actual; lo fija server/app.py al arrancar

# Acciones de auditoría que van al JSONL -> (tipo de evento, equipo que actúa). Además, todo DENEGADO de una
# consulta o herramienta sale como "autorizacion_denegada" (equipo null: el actor lo decide la capa superior).
EVENTOS_SIEM = {
    "CLIC_ENLACE": ("clic_enlace", "azul"), "CLIC_BLOQUEADO": ("clic_bloqueado", "azul"),
    "ENLACE_CONTENIDO": ("enlace_contenido", "azul"), "CORREO_REPORTADO": ("correo_reportado", "azul"),
    "PDF_ABIERTO": ("pdf_abierto", "azul"), "PDF_REPORTADO": ("pdf_reportado", "azul"),
    "MISION_COMPLETADA": ("mision_completada", "azul"),
}
_CANDADO_EVENTOS = threading.Lock()
LIMITE_FILAS = 50
NIVEL_RIESGO = {"PUBLICA": "BAJO", "INTERNA": "MEDIO", "CONFIDENCIAL": "ALTO", "CRITICA": "CRITICO"}

# Constantes del código (nunca vienen del usuario ni del modelo): tabla -> columnas y filtros permitidos.
ESPECIFICACION = {
    "productos": {"columnas": ("sku", "nombre", "stock", "precio"), "filtros": ("sku",)},
    "clientes": {"columnas": ("id", "nombre", "industria", "contacto"), "filtros": ("industria",)},
    "incidentes": {"columnas": ("id", "fecha", "sistema", "severidad", "causa_raiz"), "filtros": ("severidad",)},
    "configuracion_admin": {"columnas": ("clave", "valor"), "filtros": ("clave",)},
}


class PermisoDenegado(Exception):
    def __init__(self, capa, motivo, requiere_autorizacion=False):
        super().__init__(motivo)
        self.capa = capa
        self.motivo = motivo
        self.requiere_autorizacion = requiere_autorizacion


class Autorizador:
    """Autorizaciones concedidas por humanos (analista/admin). El modelo no puede otorgarlas."""

    def __init__(self, conn):
        self.conn = conn

    def vigente(self, identidad, tabla):
        fila = self.conn.execute(
            "SELECT 1 FROM autorizaciones WHERE usuario=? AND recurso=? AND vigente=1",
            (identidad.usuario, tabla)).fetchone()
        return fila is not None

    def otorgar(self, otorgante, usuario, tabla):
        if otorgante.rol not in ("analista", "admin"):
            raise PermisoDenegado("autorizador", "solo analista o admin pueden otorgar autorizaciones")
        if permisos.TABLAS.get(tabla) != "CONFIDENCIAL":
            raise PermisoDenegado("autorizador", "solo se delegan recursos CONFIDENCIALES; los CRITICOS nunca")
        self.conn.execute(
            "INSERT INTO autorizaciones(usuario,recurso,vigente,otorgada_por,fecha) VALUES(?,?,1,?,?)",
            (usuario, tabla, otorgante.usuario, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()

    def revocar(self, otorgante, usuario, tabla):
        if otorgante.rol not in ("analista", "admin"):
            raise PermisoDenegado("autorizador", "solo analista o admin pueden revocar autorizaciones")
        self.conn.execute("UPDATE autorizaciones SET vigente=0 WHERE usuario=? AND recurso=?", (usuario, tabla))
        self.conn.commit()


class Repositorio:
    def __init__(self, conn, ruta_eventos=None):
        conn.row_factory = sqlite3.Row
        self.conn = conn
        self.autorizador = Autorizador(conn)
        self.ruta_eventos = ruta_eventos  # None = no se escribe JSONL (p. ej. BD en memoria de los tests)

    def identidad(self, usuario):
        """La identidad sale de la tabla de usuarios (el sistema), nunca de un prompt."""
        fila = self.conn.execute("SELECT usuario, rol FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
        if fila is None:
            raise KeyError(f"usuario desconocido: {usuario}")
        return Identidad(fila["usuario"], fila["rol"])

    def registrar(self, identidad, accion, recurso, resultado, nivel):
        # ISO 8601 completo con zona horaria (p. ej. 2026-10-22T13:47:05-06:00): ordenable y listo para un SIEM.
        ts = datetime.now().astimezone().isoformat(timespec="seconds")
        usuario, rol = getattr(identidad, "usuario", None), getattr(identidad, "rol", None)
        self.conn.execute(
            "INSERT INTO auditoria(ts,usuario,rol,accion,recurso,resultado,nivel_riesgo) VALUES(?,?,?,?,?,?,?)",
            (ts, usuario, rol, accion, recurso, resultado, nivel))
        self.conn.commit()
        self._evento_siem(ts, usuario, rol, accion, recurso, resultado, nivel)

    def _evento_siem(self, ts, usuario, rol, accion, recurso, resultado, nivel):
        """Mismo registro que auditoría, como una línea JSON en eventos.jsonl (solo eventos relevantes). Un fallo
        al escribir el archivo nunca tumba la auditoría (la tabla SQLite sigue siendo la fuente de verdad)."""
        if not self.ruta_eventos:
            return
        tipo, equipo = EVENTOS_SIEM.get(accion, ("autorizacion_denegada", None) if resultado == "DENEGADO"
                                        else (None, None))
        if tipo is None:
            return
        linea = json.dumps({"timestamp": ts, "partida": PARTIDA, "equipo": equipo, "usuario": usuario, "rol": rol,
                            "tipo": tipo, "accion": accion, "recurso": recurso, "resultado": resultado,
                            "riesgo": nivel, "origen": "cybershield-lab"}, ensure_ascii=False)
        try:
            with _CANDADO_EVENTOS, open(self.ruta_eventos, "a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except OSError:
            pass

    def consultar(self, identidad, tabla, filtros=None):
        esp = ESPECIFICACION.get(tabla)
        if esp is None:
            raise ValueError(f"tabla no permitida: {tabla}")
        filtros = filtros or {}
        invalidos = set(filtros) - set(esp["filtros"])
        if invalidos:
            raise ValueError(f"filtros no permitidos: {sorted(invalidos)}")
        if not all(isinstance(v, str) for v in filtros.values()):
            raise ValueError("los valores de filtro deben ser texto")

        sens = permisos.TABLAS[tabla]
        acceso = permisos.evaluar_acceso(identidad, sens, self.autorizador.vigente(identidad, tabla))
        if not acceso.permitido:
            self.registrar(identidad, "CONSULTA", tabla, "DENEGADO", NIVEL_RIESGO[sens])
            raise PermisoDenegado("repositorio", acceso.motivo, acceso.requiere_autorizacion)

        sql = f"SELECT {', '.join(esp['columnas'])} FROM {tabla}"  # solo constantes del código
        if filtros:
            sql += " WHERE " + " AND ".join(f"{k} = ?" for k in filtros)
        sql += f" LIMIT {LIMITE_FILAS}"
        filas = self.conn.execute(sql, tuple(filtros.values())).fetchall()
        self.registrar(identidad, "CONSULTA", tabla, "PERMITIDO", NIVEL_RIESGO[sens])
        return [dict(f) for f in filas]

    # ---------- buzón de entrenamiento (fuera de TABLAS: ninguna herramienta de la IA puede leerlo) ----------
    def crear_correo(self, partida, plantilla_id, para_usuario):
        """Correo desde una plantilla FIJA. El enlace lo genera el servidor (id aleatorio, ruta local /l/<id>).
        KeyError si la plantilla o el usuario no existen. -> {id, para_usuario, asunto, plantilla_id, ts}"""
        self.identidad(para_usuario)
        enlace_id = secrets.token_urlsafe(9)
        ruta = "/l/" + enlace_id
        ahora = datetime.now()
        de, asunto, cuerpo = correos.componer(plantilla_id, para_usuario, ruta, ahora.strftime("%d/%m/%Y"))
        adjunto = correos.adjunto(plantilla_id)
        ts = ahora.isoformat(timespec="seconds")
        with self.conn:  # correo y enlace en una sola transacción
            cur = self.conn.execute(
                "INSERT INTO correos(partida,de,para_usuario,asunto,cuerpo,plantilla_id,ts,adjunto) "
                "VALUES(?,?,?,?,?,?,?,?)", (partida, de, para_usuario, asunto, cuerpo, plantilla_id, ts, adjunto))
            self.conn.execute("INSERT INTO enlaces(id,correo_id,ruta_local) VALUES(?,?,?)",
                              (enlace_id, cur.lastrowid, ruta))
        return {"id": cur.lastrowid, "para_usuario": para_usuario, "asunto": asunto, "plantilla_id": plantilla_id,
                "ts": ts}

    def buzon(self, partida, usuario, limite=LIMITE_FILAS):
        filas = self.conn.execute(
            "SELECT c.id, c.de, c.asunto, c.cuerpo, c.plantilla_id, c.ts, e.ruta_local AS enlace, "
            "r.correo_id IS NOT NULL AS reportado, k.correo_id IS NOT NULL AS contenido, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'CLIC_ENLACE' AND a.recurso = 'correo:' || c.id) "
            "AS clicado, c.adjunto, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'PDF_ABIERTO' AND a.recurso = 'correo:' || c.id) "
            "AS pdf_abierto, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'PDF_REPORTADO' AND a.recurso = 'correo:' || c.id) "
            "AS pdf_reportado "
            "FROM correos c JOIN enlaces e ON e.correo_id = c.id LEFT JOIN reportes r ON r.correo_id = c.id "
            "LEFT JOIN contenciones k ON k.correo_id = c.id "
            "WHERE c.partida = ? AND c.para_usuario = ? ORDER BY c.id DESC LIMIT ?",
            (partida, usuario, limite)).fetchall()
        # adjunto -> {id, archivo, titulo} del catálogo fijo (None si el correo no trae PDF)
        return [{**dict(f), "adjunto": documentos.info(f["adjunto"])} for f in filas]

    def registrar_clic(self, enlace_id):
        """Registra en auditoría el clic en un enlace de entrenamiento. Si Azul ya lo contuvo, el clic queda
        BLOQUEADO (no es un CLIC_ENLACE). -> {correo_id, para_usuario, contenido} o None."""
        fila = self.conn.execute(
            "SELECT c.id AS correo_id, c.para_usuario, k.correo_id IS NOT NULL AS contenido "
            "FROM enlaces e JOIN correos c ON c.id = e.correo_id LEFT JOIN contenciones k ON k.correo_id = c.id "
            "WHERE e.id = ?", (enlace_id,)).fetchone()
        if fila is None:
            return None
        clic = {"correo_id": fila["correo_id"], "para_usuario": fila["para_usuario"], "contenido": bool(fila["contenido"])}
        if clic["contenido"]:
            self.registrar(self.identidad(clic["para_usuario"]), "CLIC_BLOQUEADO", f"correo:{clic['correo_id']}",
                           "BLOQUEADO", "BAJO")
        else:
            self.registrar(self.identidad(clic["para_usuario"]), "CLIC_ENLACE", f"correo:{clic['correo_id']}",
                           "CLIC", "ALTO")
        return clic

    def contener_enlace(self, partida, usuario, correo_id):
        """Azul contiene (bloquea) el enlace de un correo SUYO de esta partida que ya fue clicado.
        -> "contenido" (nuevo) · "ya_contenido" · "sin_clic" (no hay clic que contener) · None (no es suyo)."""
        fila = next((c for c in self.buzon(partida, usuario, limite=-1) if c["id"] == correo_id), None)
        if fila is None:
            return None
        if fila["contenido"]:
            return "ya_contenido"
        if not fila["clicado"]:
            return "sin_clic"
        with self.conn:
            self.conn.execute("INSERT INTO contenciones(correo_id,usuario,ts) VALUES(?,?,?)",
                              (correo_id, usuario, datetime.now().astimezone().isoformat(timespec="seconds")))
        self.registrar(self.identidad(usuario), "ENLACE_CONTENIDO", f"correo:{correo_id}", "CONTENIDO", "BAJO")
        return "contenido"

    def reportar_correo(self, partida, usuario, correo_id):
        """Azul marca un correo SUYO de esta partida como sospechoso. Un correo se reporta una sola vez.
        -> True (reporte nuevo) · False (ya estaba reportado) · None (no existe o no es de ese usuario/partida)."""
        fila = self.conn.execute("SELECT 1 FROM correos WHERE id=? AND partida=? AND para_usuario=?",
                                 (correo_id, partida, usuario)).fetchone()
        if fila is None:
            return None
        with self.conn:
            cur = self.conn.execute("INSERT OR IGNORE INTO reportes(correo_id,usuario,ts) VALUES(?,?,?)",
                                    (correo_id, usuario, datetime.now().astimezone().isoformat(timespec="seconds")))
        if not cur.rowcount:
            return False
        self.registrar(self.identidad(usuario), "CORREO_REPORTADO", f"correo:{correo_id}", "REPORTADO", "BAJO")
        return True

    def evento_pdf(self, partida, usuario, correo_id, tipo):
        """Azul abre o reporta el PDF adjunto de un correo SUYO de esta partida. No se ejecuta nada: es solo un
        evento en auditoría. tipo = "pdf_abierto" | "pdf_reportado" (un PDF se reporta una sola vez).
        -> {"doc": {...}} · "sin_adjunto" · "ya_reportado" · None (no es suyo)."""
        fila = next((c for c in self.buzon(partida, usuario, limite=-1) if c["id"] == correo_id), None)
        if fila is None:
            return None
        if not fila["adjunto"]:
            return "sin_adjunto"
        if tipo == "pdf_reportado" and fila["pdf_reportado"]:
            return "ya_reportado"
        accion, resultado = ("PDF_ABIERTO", "ABIERTO") if tipo == "pdf_abierto" else ("PDF_REPORTADO", "REPORTADO")
        self.registrar(self.identidad(usuario), accion, f"correo:{correo_id}", resultado, "BAJO")
        return {"doc": fila["adjunto"]}

    # ---------- misiones del Equipo Azul ----------
    def misiones(self, partida, usuario):
        """Todas las misiones con el progreso de ese usuario EN ESA PARTIDA ('pendiente' si aún no hay fila):
        una partida nueva (servidor reiniciado) arranca con todas pendientes."""
        filas = self.conn.execute(
            "SELECT m.id, m.titulo, m.condicion_evento, m.puntos, COALESCE(p.estado, 'pendiente') AS estado, p.ts "
            "FROM misiones m LEFT JOIN progreso_mision p "
            "ON p.mision_id = m.id AND p.partida = ? AND p.usuario = ? ORDER BY m.id",
            (partida, usuario)).fetchall()
        return [dict(f) for f in filas]

    def _completar(self, partida, usuario, mision):
        """Marca completada si no lo estaba. -> True si es una completación nueva."""
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO progreso_mision(partida,usuario,mision_id,estado,ts) VALUES(?,?,?,'completada',?) "
                "ON CONFLICT(partida, usuario, mision_id) DO UPDATE SET estado='completada', ts=excluded.ts "
                "WHERE progreso_mision.estado <> 'completada'",
                (partida, usuario, mision["id"], datetime.now().astimezone().isoformat(timespec="seconds")))
        if not cur.rowcount:
            return False
        self.registrar(self.identidad(usuario), "MISION_COMPLETADA", f"mision:{mision['id']}", "COMPLETADA", "BAJO")
        return True

    def completar_misiones_evento(self, partida, usuario, evento):
        """Completa las misiones cuya condición es ese evento. 'manual' nunca se completa por evento.
        -> misiones completadas AHORA (las ya completadas no se repiten)."""
        if evento == "manual":
            return []
        return [m for m in self.misiones(partida, usuario)
                if m["condicion_evento"] == evento and self._completar(partida, usuario, m)]

    def completar_mision_manual(self, partida, usuario, mision_id):
        """Solo misiones con condición 'manual'. -> True (nueva) · False (ya completada) · None (no existe o no es manual)."""
        m = next((m for m in self.misiones(partida, usuario) if m["id"] == mision_id), None)
        if m is None or m["condicion_evento"] != "manual":
            return None
        return self._completar(partida, usuario, m)

    def auditoria(self, limite=50):
        filas = self.conn.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
        return [dict(f) for f in filas]


def abrir(ruta=None, ruta_eventos=None):
    """ruta_eventos: archivo JSONL de eventos. Por defecto data/eventos.jsonl junto a la BD del laboratorio; una BD
    en memoria no escribe eventos salvo que se indique un archivo."""
    ruta = str(ruta or RUTA_DB)
    if ruta_eventos is None and ruta != ":memory:":
        ruta_eventos = Path(ruta).parent / RUTA_EVENTOS.name
    if ruta != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")  # correos/enlaces referencian usuarios/correos
    schema.crear(conn)
    seed.sembrar(conn)
    return Repositorio(conn, ruta_eventos)


_DEFECTO = None


def por_defecto():
    global _DEFECTO
    if _DEFECTO is None:
        _DEFECTO = abrir()
    return _DEFECTO
