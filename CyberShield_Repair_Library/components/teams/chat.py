"""Chat de equipo (CyberShield Repair §5/§10). Persistente por partida y aislado por equipo: Rojo no lee a Azul ni al revés.
El árbitro (general) lee los dos; el espectador no lee ninguno. Límite de longitud y de ritmo (anti-inundación). Texto plano: la
interfaz lo inserta siempre con textContent. Sin HTTP: recibe la conexión SQLite y un reloj.
"""
import sqlite3
import threading
import time
from datetime import datetime

MAX_TEXTO = 500
MAX_POR_VENTANA = 8        # mensajes por participante...
VENTANA_S = 10             # ...en esta ventana de segundos
EQUIPOS_CHAT = ("rojo", "azul", "general")


class ErrorChat(Exception):
    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status, self.mensaje = status, mensaje


class ChatEquipos:
    def __init__(self, conn, reloj=time.monotonic):
        self.conn, self._reloj = conn, reloj
        self._c = threading.RLock()
        self._recientes = {}   # autor -> [instantes]
        with self._c, self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS chat_equipo(
                id INTEGER PRIMARY KEY AUTOINCREMENT, partida TEXT NOT NULL, equipo TEXT NOT NULL, autor TEXT NOT NULL,
                texto TEXT NOT NULL, ts TEXT NOT NULL)""")

    def enviar(self, partida, equipo, autor, texto):
        if equipo not in EQUIPOS_CHAT:
            raise ErrorChat(403, "Este rol no participa en el chat de equipo.")
        texto = " ".join(str(texto or "").split())
        if not texto:
            raise ErrorChat(400, "El mensaje está vacío.")
        if len(texto) > MAX_TEXTO:
            raise ErrorChat(400, f"El mensaje supera {MAX_TEXTO} caracteres.")
        with self._c:
            ahora = self._reloj()
            r = [t for t in self._recientes.get(autor, []) if ahora - t < VENTANA_S]
            if len(r) >= MAX_POR_VENTANA:
                raise ErrorChat(429, "Demasiados mensajes seguidos: espera unos segundos.")
            r.append(ahora)
            self._recientes[autor] = r
            ts = datetime.now().astimezone().isoformat(timespec="seconds")
            with self.conn:
                cur = self.conn.execute("INSERT INTO chat_equipo(partida,equipo,autor,texto,ts) VALUES(?,?,?,?,?)", (partida, equipo, autor, texto, ts))
            return {"id": cur.lastrowid, "equipo": equipo, "autor": autor, "texto": texto, "ts": ts}

    def leer(self, partida, equipo, desde_id=0, limite=200):
        """Mensajes visibles para `equipo`: el suyo (el árbitro ve los tres). El espectador no ve ninguno."""
        if equipo == "espectador":
            return []
        cur = self.conn.cursor()
        cur.row_factory = sqlite3.Row
        if equipo == "general":
            filas = cur.execute("SELECT * FROM chat_equipo WHERE partida=? AND id>? ORDER BY id LIMIT ?", (partida, int(desde_id), limite)).fetchall()
        else:
            filas = cur.execute("SELECT * FROM chat_equipo WHERE partida=? AND equipo=? AND id>? ORDER BY id LIMIT ?",
                                (partida, equipo, int(desde_id), limite)).fetchall()
        return [dict(f) for f in filas]
