"""Pruebas offline del buzón de entrenamiento (BD en memoria). Ejecutar: python -m src.lab.test_correos"""
import sqlite3

from . import correos, repositorio, schema

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def lanza(fn, exc):
    try:
        fn()
    except exc:
        return True
    return False


def main():
    repo = repositorio.abrir(":memory:")

    de, asunto, cuerpo = correos.componer("soporte_tecnico", "ana.perez", "/l/abcdefgh", "22/10/2026")
    chk("plantilla rellena usuario y enlace local", "ana.perez" in asunto and "/l/abcdefgh" in cuerpo)
    chk("remitente ficticio (.invalid)", de.endswith(".invalid"))
    chk("todas las plantillas componen sin variables sueltas",
        all("{" not in "".join(correos.componer(p, "u", "/l/x", "f")) for p in correos.PLANTILLAS))
    chk("plantilla desconocida -> KeyError", lanza(lambda: correos.componer("libre", "u", "/l/x", "f"), KeyError))

    c = repo.crear_correo("p1", "recursos_humanos", "ana.perez")
    chk("crear_correo devuelve id sin enlace", c["id"] and "enlace" not in c)
    chk("usuario inexistente -> KeyError", lanza(lambda: repo.crear_correo("p1", "paqueteria", "nadie"), KeyError))
    chk("plantilla inexistente -> KeyError", lanza(lambda: repo.crear_correo("p1", "libre", "ana.perez"), KeyError))
    repo.crear_correo("p1", "paqueteria", "luis.gomez")
    repo.crear_correo("p2", "soporte_tecnico", "ana.perez")

    b = repo.buzon("p1", "ana.perez")
    chk("buzón filtra por usuario y partida", len(b) == 1 and b[0]["id"] == c["id"])
    chk("el enlace es una ruta local /l/<id>", b[0]["enlace"].startswith("/l/") and b[0]["enlace"] in b[0]["cuerpo"])
    chk("buzón vacío para otro usuario en otra partida", repo.buzon("p2", "luis.gomez") == [])

    enlace_id = b[0]["enlace"][3:]
    antes = len(repo.auditoria(500))
    clic = repo.registrar_clic(enlace_id)
    aud = repo.auditoria(1)[0]
    chk("clic registrado en auditoría con la identidad del destinatario",
        clic == {"correo_id": c["id"], "para_usuario": "ana.perez", "contenido": False}
        and len(repo.auditoria(500)) == antes + 1
        and aud["accion"] == "CLIC_ENLACE" and aud["usuario"] == "ana.perez")
    chk("enlace inexistente -> None y sin auditoría",
        repo.registrar_clic("noexiste123") is None and len(repo.auditoria(500)) == antes + 1)

    chk("la BD rechaza una URL externa como enlace", lanza(lambda: repo.conn.execute(
        "INSERT INTO enlaces(id,correo_id,ruta_local) VALUES('x1',?,'https://evil.invalid/x')", (c["id"],)),
        sqlite3.IntegrityError))
    chk("la BD rechaza enlaces a correos inexistentes", lanza(lambda: repo.conn.execute(
        "INSERT INTO enlaces(id,correo_id,ruta_local) VALUES('x2',999,'/l/x2')"), sqlite3.IntegrityError))
    chk("las herramientas de la IA no pueden leer correos", "correos" not in repositorio.ESPECIFICACION)

    # BD vieja (CHECK de roles sin 'espectador') que ya tiene correos: la migración no rompe sus FK
    vieja = sqlite3.connect(":memory:")
    vieja.execute("PRAGMA foreign_keys = ON")
    vieja.executescript(
        "CREATE TABLE usuarios(usuario TEXT PRIMARY KEY, rol TEXT NOT NULL "
        "CHECK(rol IN ('invitado','empleado','analista','admin'))); INSERT INTO usuarios VALUES('ana.perez','empleado');"
        "CREATE TABLE correos(id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT NOT NULL, de TEXT NOT NULL, "
        "para_usuario TEXT NOT NULL REFERENCES usuarios(usuario), asunto TEXT NOT NULL, cuerpo TEXT NOT NULL, "
        "plantilla_id TEXT NOT NULL, ts TEXT NOT NULL);")
    schema.crear(vieja)
    sql = vieja.execute("SELECT sql FROM sqlite_master WHERE name='correos'").fetchone()[0]
    chk("migrar roles conserva las FK hacia usuarios", "usuarios_v1" not in sql
        and vieja.execute("PRAGMA foreign_keys").fetchone()[0] == 1)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
