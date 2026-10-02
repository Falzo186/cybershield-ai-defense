import sqlite3
from datetime import datetime
from pathlib import Path

from tecnicas import clasificar_tecnica

RUTA_DB = Path(__file__).resolve().parent.parent / "data" / "redteam.db"


def _conn():
    RUTA_DB.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(RUTA_DB)


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS batallas(
            id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, nivel INTEGER,
            modelo_def TEXT, modelo_atq TEXT, rondas_usadas INTEGER,
            gano_atacante INTEGER, bloqueos_salida INTEGER, bloqueos_guardia INTEGER,
            bloqueos_entrada INTEGER, fugas_internas INTEGER);
        CREATE TABLE IF NOT EXISTS intercambios(
            id INTEGER PRIMARY KEY AUTOINCREMENT, batalla_id INTEGER, ronda INTEGER,
            ataque TEXT, respuesta TEXT, tecnica TEXT,
            FOREIGN KEY(batalla_id) REFERENCES batallas(id));
        """)


def guardar_batalla(d):
    init_db()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO batallas(fecha,nivel,modelo_def,modelo_atq,rondas_usadas,gano_atacante,"
            "bloqueos_salida,bloqueos_guardia,bloqueos_entrada,fugas_internas) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), d["nivel"], d["modelo_def"],
             d["modelo_atq"], d["rondas_usadas"], int(d["gano_atacante"]), d["bloqueos_salida"],
             d["bloqueos_guardia"], d["bloqueos_entrada"], d["fugas_internas"]))
        bid = cur.lastrowid
        c.executemany(
            "INSERT INTO intercambios(batalla_id,ronda,ataque,respuesta,tecnica) VALUES(?,?,?,?,?)",
            [(bid, i["ronda"], i["ataque"], i["respuesta"], clasificar_tecnica(i["ataque"]))
             for i in d["intercambios"]])
    return bid


def resumen_por_nivel():
    init_db()
    with _conn() as c:
        return c.execute(
            "SELECT nivel, COUNT(*), SUM(gano_atacante), "
            "ROUND(100.0*SUM(gano_atacante)/COUNT(*),1), ROUND(AVG(rondas_usadas),1), "
            "SUM(fugas_internas) FROM batallas GROUP BY nivel ORDER BY nivel").fetchall()


def victorias_por_tecnica():
    """Técnica del ataque que ganó (última ronda de cada batalla ganada)."""
    init_db()
    with _conn() as c:
        return c.execute(
            "SELECT b.nivel, i.tecnica, COUNT(*) FROM batallas b "
            "JOIN intercambios i ON i.batalla_id=b.id AND i.ronda=b.rondas_usadas "
            "WHERE b.gano_atacante=1 GROUP BY b.nivel, i.tecnica ORDER BY b.nivel, 3 DESC").fetchall()
