"""Persistencia del combate: SQLite con cadena de hashes por partida (auditoría)."""
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
RUTA_POR_DEFECTO = RAIZ / "data" / "combate.db"


def _canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Almacen:
    def __init__(self, ruta=RUTA_POR_DEFECTO):
        if str(ruta) != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(ruta), check_same_thread=False)
        self._c = threading.RLock()
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS partidas(id TEXT PRIMARY KEY, escenario_id TEXT, hash_escenario TEXT, estado TEXT,
            config TEXT, resultado TEXT, creada TEXT, fin TEXT);
        CREATE TABLE IF NOT EXISTS eventos(partida_id TEXT, seq INT, turno INT, ts TEXT, tipo TEXT, payload TEXT,
            hash_prev TEXT, hash TEXT, PRIMARY KEY(partida_id, seq));
        CREATE UNIQUE INDEX IF NOT EXISTS ux_resultado ON eventos(partida_id) WHERE tipo='partida.resultado';
        """)
        self.db.commit()

    def crear(self, pid, esc_id, hash_esc, config, ts):
        with self._c:
            self.db.execute("INSERT INTO partidas VALUES(?,?,?,?,?,?,?,?)",
                            (pid, esc_id, hash_esc, "en_curso", _canon(config), None, ts, None))
            self.db.commit()

    def añadir(self, pid, turno, ts, tipo, payload):
        """Añade un evento encadenado. -> {seq, hash}. El índice único impide un segundo `partida.resultado`."""
        with self._c:
            fila = self.db.execute("SELECT seq, hash FROM eventos WHERE partida_id=? ORDER BY seq DESC LIMIT 1", (pid,)).fetchone()
            seq, prev = (fila[0] + 1, fila[1]) if fila else (1, "0" * 64)
            h = hashlib.sha256((prev + _canon([pid, seq, turno, tipo, payload])).encode("utf-8")).hexdigest()
            self.db.execute("INSERT INTO eventos VALUES(?,?,?,?,?,?,?,?)", (pid, seq, turno, ts, tipo, _canon(payload), prev, h))
            self.db.commit()
            return {"seq": seq, "hash": h}

    def cerrar(self, pid, estado, resultado, ts):
        with self._c:
            self.db.execute("UPDATE partidas SET estado=?, resultado=?, fin=? WHERE id=? AND estado='en_curso'",
                            (estado, _canon(resultado), ts, pid))
            self.db.commit()

    def eventos(self, pid, desde_seq=0):
        with self._c:
            filas = self.db.execute("SELECT seq,turno,ts,tipo,payload,hash_prev,hash FROM eventos WHERE partida_id=? AND seq>? ORDER BY seq",
                                    (pid, desde_seq)).fetchall()
        return [{"seq": a, "turno": b, "ts": c, "tipo": d, "payload": json.loads(e), "hash_prev": f, "hash": g}
                for a, b, c, d, e, f, g in filas]

    def partida(self, pid):
        f = self.db.execute("SELECT id,escenario_id,hash_escenario,estado,config,resultado,creada,fin FROM partidas WHERE id=?", (pid,)).fetchone()
        if not f:
            return None
        return {"id": f[0], "escenario_id": f[1], "hash_escenario": f[2], "estado": f[3], "config": json.loads(f[4]),
                "resultado": json.loads(f[5]) if f[5] else None, "creada": f[6], "fin": f[7]}

    def listar(self, limite=200):
        filas = self.db.execute("SELECT id FROM partidas ORDER BY creada DESC LIMIT ?", (limite,)).fetchall()
        return [self.partida(i) for (i,) in filas]

    def verificar_cadena(self, pid):
        """-> (ok, mensaje). Recalcula toda la cadena: detecta cualquier alteración posterior."""
        prev = "0" * 64
        for e in self.eventos(pid):
            h = hashlib.sha256((prev + _canon([pid, e["seq"], e["turno"], e["tipo"], e["payload"]])).encode("utf-8")).hexdigest()
            if e["hash_prev"] != prev or e["hash"] != h:
                return False, f"cadena rota en seq {e['seq']}"
            prev = e["hash"]
        return True, "cadena íntegra"
