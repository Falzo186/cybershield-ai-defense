"""Esquema SQLite del laboratorio (datos ficticios de CyberShield Industries)."""

DDL = """
CREATE TABLE IF NOT EXISTS usuarios(
    usuario TEXT PRIMARY KEY,
    rol TEXT NOT NULL CHECK(rol IN ('invitado','empleado','analista','admin','espectador')));
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
CREATE TABLE IF NOT EXISTS correos(
    id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT NOT NULL, de TEXT NOT NULL,
    para_usuario TEXT NOT NULL REFERENCES usuarios(usuario), asunto TEXT NOT NULL, cuerpo TEXT NOT NULL,
    plantilla_id TEXT NOT NULL, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enlaces(
    id TEXT PRIMARY KEY, correo_id INTEGER NOT NULL REFERENCES correos(id),
    ruta_local TEXT NOT NULL CHECK(ruta_local = '/l/' || id));
CREATE TRIGGER IF NOT EXISTS auditoria_sin_update BEFORE UPDATE ON auditoria
    BEGIN SELECT RAISE(ABORT, 'auditoria es append-only'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_sin_delete BEFORE DELETE ON auditoria
    BEGIN SELECT RAISE(ABORT, 'auditoria es append-only'); END;
"""


def _migrar_roles(conn):
    """Una BD creada antes de 'espectador' conserva el CHECK viejo (CREATE IF NOT EXISTS no lo cambia): se
    reconstruye la tabla usuarios con el CHECK nuevo, copiando las filas."""
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='usuarios'").fetchone()
    if sql is None or "'espectador'" in sql[0]:
        return
    conn.executescript("""
        BEGIN;
        ALTER TABLE usuarios RENAME TO usuarios_v1;
        CREATE TABLE usuarios(
            usuario TEXT PRIMARY KEY,
            rol TEXT NOT NULL CHECK(rol IN ('invitado','empleado','analista','admin','espectador')));
        INSERT INTO usuarios SELECT usuario, rol FROM usuarios_v1;
        DROP TABLE usuarios_v1;
        COMMIT;""")


def crear(conn):
    _migrar_roles(conn)
    conn.executescript(DDL)
    conn.commit()
