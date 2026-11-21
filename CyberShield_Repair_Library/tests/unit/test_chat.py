"""Pruebas del chat de equipo. Ejecutar: python CyberShield_Repair_Library/tests/unit/test_chat.py"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from CyberShield_Repair_Library.components.teams.chat import ChatEquipos, ErrorChat, MAX_POR_VENTANA  # noqa: E402

R = []


def chk(n, c):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n)


def lanza(fn, status):
    try:
        fn()
    except ErrorChat as e:
        return e.status == status
    return False


def main():
    t = [0.0]
    C = ChatEquipos(sqlite3.connect(":memory:"), lambda: t[0])
    m = C.enviar("P1", "rojo", "Rojo1", "  hola   equipo  ")
    chk("enviar normaliza espacios y devuelve id, autor y hora", m["texto"] == "hola equipo" and m["autor"] == "Rojo1" and m["id"] == 1)
    C.enviar("P1", "azul", "Azul1", "secreto azul")
    chk("el equipo lee solo su chat", [x["autor"] for x in C.leer("P1", "rojo")] == ["Rojo1"] and [x["autor"] for x in C.leer("P1", "azul")] == ["Azul1"])
    chk("el árbitro lee los dos y el espectador ninguno", len(C.leer("P1", "general")) == 2 and C.leer("P1", "espectador") == [])
    chk("desde_id devuelve solo lo nuevo", C.leer("P1", "general", desde_id=1)[0]["id"] == 2)
    chk("el chat es por partida", C.leer("P2", "general") == [])
    chk("mensaje vacío o demasiado largo -> 400", lanza(lambda: C.enviar("P1", "rojo", "R", "   "), 400) and lanza(lambda: C.enviar("P1", "rojo", "R", "x" * 501), 400))
    chk("el espectador no puede escribir (403)", lanza(lambda: C.enviar("P1", "espectador", "Esp", "hola"), 403))
    for i in range(MAX_POR_VENTANA):
        C.enviar("P1", "rojo", "Spam", f"m{i}")
    chk("límite de ritmo por participante -> 429", lanza(lambda: C.enviar("P1", "rojo", "Spam", "otro"), 429))
    t[0] += 11
    chk("pasada la ventana vuelve a poder escribir", C.enviar("P1", "rojo", "Spam", "ya")["id"] > 0)
    chk("el texto se guarda tal cual (la interfaz lo escapa con textContent)", C.enviar("P1", "azul", "Azul1", "<b>x</b>")["texto"] == "<b>x</b>")
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
