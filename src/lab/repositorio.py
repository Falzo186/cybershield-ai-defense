"""Repositorio: ÚNICO punto de acceso a la BD. Consultas fijas y parametrizadas, autorizador y auditoría.

Es la última capa de defensa: aunque la IA o la capa de herramientas fallen, aquí se vuelve a
comprobar el acceso. No existe ningún camino para ejecutar SQL arbitrario.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from . import permisos, schema, seed
from .permisos import Identidad

RUTA_DB = Path(__file__).resolve().parents[2] / "data" / "lab.db"
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
    def __init__(self, conn):
        conn.row_factory = sqlite3.Row
        self.conn = conn
        self.autorizador = Autorizador(conn)

    def identidad(self, usuario):
        """La identidad sale de la tabla de usuarios (el sistema), nunca de un prompt."""
        fila = self.conn.execute("SELECT usuario, rol FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
        if fila is None:
            raise KeyError(f"usuario desconocido: {usuario}")
        return Identidad(fila["usuario"], fila["rol"])

    def registrar(self, identidad, accion, recurso, resultado, nivel):
        self.conn.execute(
            "INSERT INTO auditoria(ts,usuario,rol,accion,recurso,resultado,nivel_riesgo) VALUES(?,?,?,?,?,?,?)",
            (datetime.now().strftime("%H:%M:%S"), getattr(identidad, "usuario", None),
             getattr(identidad, "rol", None), accion, recurso, resultado, nivel))
        self.conn.commit()

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

    def auditoria(self, limite=50):
        filas = self.conn.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
        return [dict(f) for f in filas]


def abrir(ruta=None):
    ruta = str(ruta or RUTA_DB)
    if ruta != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta, check_same_thread=False)
    schema.crear(conn)
    seed.sembrar(conn)
    return Repositorio(conn)


_DEFECTO = None


def por_defecto():
    global _DEFECTO
    if _DEFECTO is None:
        _DEFECTO = abrir()
    return _DEFECTO
