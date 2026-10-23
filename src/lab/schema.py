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
    accion TEXT NOT NULL, recurso TEXT, resultado TEXT NOT NULL, nivel_riesgo TEXT NOT NULL,
    equipo TEXT, partida TEXT);
CREATE TABLE IF NOT EXISTS correos(
    id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT NOT NULL, de TEXT NOT NULL,
    para_usuario TEXT NOT NULL REFERENCES usuarios(usuario), asunto TEXT NOT NULL, cuerpo TEXT NOT NULL,
    plantilla_id TEXT NOT NULL, ts TEXT NOT NULL, adjunto TEXT);
CREATE TABLE IF NOT EXISTS enlaces(
    id TEXT PRIMARY KEY, correo_id INTEGER NOT NULL REFERENCES correos(id),
    ruta_local TEXT NOT NULL CHECK(ruta_local = '/l/' || id));
CREATE TABLE IF NOT EXISTS misiones(
    id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, condicion_evento TEXT NOT NULL,
    puntos INTEGER NOT NULL CHECK(puntos >= 0));
CREATE TABLE IF NOT EXISTS progreso_mision(
    partida TEXT NOT NULL, usuario TEXT NOT NULL REFERENCES usuarios(usuario),
    mision_id INTEGER NOT NULL REFERENCES misiones(id),
    estado TEXT NOT NULL CHECK(estado IN ('pendiente','completada')), ts TEXT NOT NULL,
    PRIMARY KEY(partida, usuario, mision_id));
CREATE TABLE IF NOT EXISTS contenciones(
    correo_id INTEGER PRIMARY KEY REFERENCES correos(id), usuario TEXT NOT NULL REFERENCES usuarios(usuario),
    ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reportes(
    correo_id INTEGER PRIMARY KEY REFERENCES correos(id), usuario TEXT NOT NULL REFERENCES usuarios(usuario),
    ts TEXT NOT NULL);
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
    # foreign_keys OFF + legacy_alter_table ON: que el RENAME no reescriba las FK de correos/reportes/... hacia
    # usuarios_v1 (la tabla nueva se llama igual que la vieja, así que las referencias siguen siendo válidas).
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.executescript("""
        PRAGMA foreign_keys = OFF;
        PRAGMA legacy_alter_table = ON;
        BEGIN;
        ALTER TABLE usuarios RENAME TO usuarios_v1;
        CREATE TABLE usuarios(
            usuario TEXT PRIMARY KEY,
            rol TEXT NOT NULL CHECK(rol IN ('invitado','empleado','analista','admin','espectador')));
        INSERT INTO usuarios SELECT usuario, rol FROM usuarios_v1;
        DROP TABLE usuarios_v1;
        COMMIT;
        PRAGMA legacy_alter_table = OFF;""")
    conn.execute(f"PRAGMA foreign_keys = {'ON' if fk else 'OFF'}")


def _migrar_progreso(conn):
    """El progreso de misiones pasó de ser por usuario a ser por partida: la tabla vieja (sin columna partida)
    se descarta. Solo se pierde el progreso; la definición de las misiones vive en la tabla misiones."""
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='progreso_mision'").fetchone()
    if sql is not None and "partida" not in sql[0]:
        conn.execute("DROP TABLE progreso_mision")


def _migrar_auditoria(conn):
    """auditoria ganó equipo (rojo/azul o NULL) y partida. ADD COLUMN no choca con los triggers append-only
    (solo bloquean UPDATE/DELETE); las filas viejas quedan con NULL."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(auditoria)")}
    for col in ("equipo", "partida"):
        if col not in columnas:
            conn.execute(f"ALTER TABLE auditoria ADD COLUMN {col} TEXT")


def _migrar_correos(conn):
    """correos ganó la columna adjunto (id de un PDF fijo del catálogo, o NULL)."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(correos)")}
    if "adjunto" not in columnas:
        conn.execute("ALTER TABLE correos ADD COLUMN adjunto TEXT")


def crear(conn):
    _migrar_roles(conn)
    _migrar_progreso(conn)
    conn.executescript(DDL)
    _migrar_correos(conn)
    _migrar_auditoria(conn)
    conn.commit()
