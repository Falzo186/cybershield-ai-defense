"""Capturas de las 4 vistas (general, rojo, azul, espectador) en 1366×768 y 1920×1080, para comparar cambios visuales.

Arranca su propio servidor con BD temporal (una partida nueva por resolución, porque los tokens de equipo se
entregan una sola vez por partida) y mide, por ventana del escritorio, si su contenido necesita scroll interno.

Ejecutar:  python e2e/capturas_vistas.py docs/capturas_antes
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
RESOLUCIONES = [(1366, 768), (1920, 1080)]
VISTAS = ["general", "azul", "rojo", "espectador"]  # Azul antes que Rojo, como en una partida real


def servidor():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    env = {**os.environ, "PUERTO": str(puerto), "CS_LAB_DB": str(Path(tempfile.mkdtemp()) / "lab.db")}
    proc = subprocess.Popen([sys.executable, "server/app.py"], cwd=RAIZ, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/estado", timeout=1)
            return proc, base
        except Exception:  # noqa: BLE001 - aún arrancando
            time.sleep(0.2)
    raise RuntimeError("el servidor no arrancó")


MEDIR = """() => [...document.querySelectorAll('.ventana:not([hidden])')].map(v => {
    const c = v.querySelector('.ventana-cuerpo > *');
    const scroll = c ? c.scrollHeight - c.clientHeight : 0;
    return {ventana: v.dataset.ventana, alto: v.offsetHeight, sobra_px: scroll};
})"""


def main(destino):
    salida = RAIZ / destino
    salida.mkdir(parents=True, exist_ok=True)
    informe = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        for ancho, alto in RESOLUCIONES:
            proc, base = servidor()
            try:
                for rol in VISTAS:
                    pg = nav.new_context(viewport={"width": ancho, "height": alto}).new_page()
                    pg.goto(f"{base}/?rol={rol}")
                    pg.wait_for_selector(".ventana", state="attached")
                    pg.wait_for_timeout(2500)  # token, SSE y estado de Ollama
                    archivo = f"{ancho}x{alto}_{rol}.png"
                    pg.screenshot(path=str(salida / archivo))
                    medidas = pg.evaluate(MEDIR)
                    con_scroll = [f"{m['ventana']} (+{m['sobra_px']} px)" for m in medidas if m["sobra_px"] > 2]
                    informe.append(f"{ancho}x{alto} {rol:10s} scroll interno: {', '.join(con_scroll) or 'ninguno'}")
                    print(informe[-1])
            finally:
                proc.terminate()
        nav.close()
    (salida / "medidas.txt").write_text("\n".join(informe) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/capturas_antes")
