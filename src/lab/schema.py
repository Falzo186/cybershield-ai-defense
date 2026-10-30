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
    puntos INTEGER NOT NULL CHECK(puntos >= 0), prioridad TEXT NOT NULL DEFAULT 'media', plazo_s INTEGER,
    depende_de TEXT NOT NULL DEFAULT '', descripcion TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS progreso_mision(
    partida TEXT NOT NULL, usuario TEXT NOT NULL REFERENCES usuarios(usuario),
    mision_id INTEGER NOT NULL REFERENCES misiones(id),
    estado TEXT NOT NULL CHECK(estado IN ('pendiente','completada')), ts TEXT NOT NULL,
    completada_por TEXT, evidencia TEXT, puntos_obtenidos INTEGER, a_tiempo INTEGER,
    PRIMARY KEY(partida, usuario, mision_id));
CREATE TABLE IF NOT EXISTS asignaciones_mision(
    partida TEXT NOT NULL, mision_id INTEGER NOT NULL REFERENCES misiones(id), participante TEXT NOT NULL,
    ts TEXT NOT NULL, PRIMARY KEY(partida, mision_id));
CREATE TABLE IF NOT EXISTS incidentes_partida(
    id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT NOT NULL,
    titulo TEXT NOT NULL CHECK(length(titulo) BETWEEN 3 AND 80),
    severidad TEXT NOT NULL CHECK(severidad IN ('baja','media','alta','critica')),
    estado TEXT NOT NULL CHECK(estado IN ('abierto','en_investigacion','resuelto')),
    correo_id INTEGER REFERENCES correos(id), abierto_por TEXT NOT NULL, ts_apertura TEXT NOT NULL,
    resolucion TEXT CHECK(resolucion IS NULL OR length(resolucion) BETWEEN 10 AND 500),
    resuelto_por TEXT, ts_resolucion TEXT);
CREATE TABLE IF NOT EXISTS compromisos_credencial(
    id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT NOT NULL, usuario TEXT NOT NULL REFERENCES usuarios(usuario),
    correo_id INTEGER NOT NULL REFERENCES correos(id), ts TEXT NOT NULL, revocada_ts TEXT, revocada_por TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS compromiso_activo ON compromisos_credencial(partida, usuario)
    WHERE revocada_ts IS NULL;
CREATE TABLE IF NOT EXISTS ataques_ia(
    id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT NOT NULL, n INTEGER NOT NULL, lanzado_por TEXT,
    usuario TEXT NOT NULL REFERENCES usuarios(usuario),
    origen_identidad TEXT NOT NULL CHECK(origen_identidad IN ('invitado','credencial_robada')),
    tecnica TEXT, intensidad INTEGER NOT NULL CHECK(intensidad BETWEEN 1 AND 3),
    estado TEXT NOT NULL CHECK(estado IN ('en_curso','terminado','cancelado')), resultado TEXT,
    veredicto TEXT, decision_ia TEXT, origen_decision TEXT, capa_bloqueo TEXT, herramienta TEXT,
    objetivo TEXT, sensibilidad_objetivo TEXT, sensibilidad_expuesta TEXT, categoria TEXT, prompt TEXT, motivo TEXT,
    error TEXT, explicacion TEXT, puntos_rojo INTEGER NOT NULL DEFAULT 0, puntos_azul INTEGER NOT NULL DEFAULT 0,
    modelo_atq TEXT, modelo_def TEXT,
    atq_ms INTEGER, atq_tokens_entrada INTEGER, atq_tokens_salida INTEGER, atq_carga_ms INTEGER,
    def_ms INTEGER, def_tokens_entrada INTEGER, def_tokens_salida INTEGER, def_carga_ms INTEGER,
    ts_inicio TEXT NOT NULL, ts_fin TEXT, UNIQUE(partida, n));
CREATE TABLE IF NOT EXISTS contenciones(
    correo_id INTEGER PRIMARY KEY REFERENCES correos(id), usuario TEXT NOT NULL REFERENCES usuarios(usuario),
    ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lecturas(
    correo_id INTEGER NOT NULL REFERENCES correos(id), participante TEXT NOT NULL, ts TEXT NOT NULL,
    PRIMARY KEY(correo_id, participante));
CREATE TABLE IF NOT EXISTS archivados(
    correo_id INTEGER PRIMARY KEY REFERENCES correos(id), participante TEXT NOT NULL, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS respuestas(
    id INTEGER PRIMARY KEY AUTOINCREMENT, correo_id INTEGER NOT NULL REFERENCES correos(id),
    participante TEXT NOT NULL, texto TEXT NOT NULL CHECK(length(texto) BETWEEN 1 AND 1000), ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS aislamientos(
    correo_id INTEGER PRIMARY KEY REFERENCES correos(id), participante TEXT NOT NULL, ts TEXT NOT NULL);
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


def _migrar_misiones(conn):
    """Fase E: misiones ganó prioridad, plazo, dependencias y descripción; progreso_mision, quién la completó, la
    evidencia y los puntos obtenidos. ADD COLUMN conserva el progreso existente (las columnas nuevas quedan NULL)."""
    nuevas = {"misiones": (("prioridad", "TEXT NOT NULL DEFAULT 'media'"), ("plazo_s", "INTEGER"),
                           ("depende_de", "TEXT NOT NULL DEFAULT ''"), ("descripcion", "TEXT NOT NULL DEFAULT ''")),
              "progreso_mision": (("completada_por", "TEXT"), ("evidencia", "TEXT"), ("puntos_obtenidos", "INTEGER"),
                                  ("a_tiempo", "INTEGER"))}
    for tabla, cols in nuevas.items():
        existentes = {f[1] for f in conn.execute(f"PRAGMA table_info({tabla})")}
        for col, tipo in cols:
            if col not in existentes:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")


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
    _migrar_misiones(conn)
    conn.commit()
