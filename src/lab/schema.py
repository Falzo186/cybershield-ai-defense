"""Esquema SQLite del laboratorio (datos ficticios de CyberShield Industries)."""

DDL = """
CREATE TABLE IF NOT EXISTS usuarios(
    usuario TEXT PRIMARY KEY,
    rol TEXT NOT NULL CHECK(rol IN ('invitado','empleado','analista','admin')));
CREATE TABLE IF NOT EXISTS productos(
    sku TEXT PRIMARY KEY, nombre TEXT NOT NULL, stock INTEGER NOT NULL, precio REAL NOT NULL);
CREATE TABLE IF NOT EXISTS clientes(
    id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, industria TEXT NOT NULL, contacto TEXT);
CREATE TABLE IF NOT EXISTS incidentes(
    id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, sistema TEXT NOT NULL,
    severidad TEXT NOT NULL CHECK(severidad IN ('BAJA','MEDIA','ALTA','CRITICA')),
    causa_raiz TEXT);
CREATE TABLE IF NOT EXISTS configuracion_admin(
    clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS autorizaciones(
    id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, recurso TEXT NOT NULL,
    vigente INTEGER NOT NULL DEFAULT 1, otorgada_por TEXT NOT NULL, fecha TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS auditoria(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, usuario TEXT, rol TEXT,
    accion TEXT NOT NULL, recurso TEXT, resultado TEXT NOT NULL, nivel_riesgo TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS auditoria_sin_update BEFORE UPDATE ON auditoria
    BEGIN SELECT RAISE(ABORT, 'auditoria es append-only'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_sin_delete BEFORE DELETE ON auditoria
    BEGIN SELECT RAISE(ABORT, 'auditoria es append-only'); END;
"""


def crear(conn):
    conn.executescript(DDL)
    conn.commit()
