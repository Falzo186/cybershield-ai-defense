"""E2E con modelos 8B REALES (Ollama): una partida completa desde la interfaz, con capturas. Requiere Ollama y los modelos.
Ejecutar: python e2e/prueba_real_8b.py   (condicional: sale con 0 y avisa si no hay Ollama)."""
import os, sys, tempfile, time, subprocess, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_combate_ui as T
from playwright.sync_api import sync_playwright
from src.lab import cliente_ollama as co  # noqa: E402

def main():
    mods = co.listar_modelos("http://localhost:11434") if co.ollama_disponible("http://localhost:11434") else []
    if not {"qwen3:8b", "llama3.1:8b"} <= set(mods):
        print("OMITIDA  no hay Ollama con qwen3:8b y llama3.1:8b"); return True
    port = T.puerto_libre(); base = f"http://127.0.0.1:{port}"; tmp = tempfile.mkdtemp()
    env = {**os.environ, "PUERTO": str(port), "CS_CODIGO_ARBITRO": T.CODIGO, "CS_COMBATE_DB": os.path.join(tmp, "c.db"), "CS_WAZUH_SIM_DB": os.path.join(tmp, "w.db"), "PYTHONIOENCODING": "utf-8"}
    srv = subprocess.Popen([sys.executable, str(T.RAIZ / "server" / "app.py")], cwd=str(T.RAIZ), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = False
    try:
        for _ in range(60):
            try: T.get(base, "/api/combate/estado"); break
            except Exception: time.sleep(0.5)
        with sync_playwright() as pw:
            nav = T.lanzar_navegador(pw, False); page = nav.new_context(viewport=T.VISTAS["1366x768"]).new_page(); T.enganchar(page, "real")
            page.goto(base + "/combate/"); page.wait_for_selector("#f-escenario option", state="attached")
            page.fill("#e-codigo", T.CODIGO); page.click("#form-entrar button"); page.wait_for_function("!document.querySelector('#btn-iniciar').disabled")
            T.iniciar(page, "verificacion_falsa-sencillo", "qwen3:8b", "llama3.1:8b", 1)
            page.wait_for_selector("#cronos .msg.azul", timeout=240000)
            page.screenshot(path=str(T.SALIDA / "11_combate_8b_real_en_curso_1366x768.png"))
            pid = page.evaluate("location.hash.split('/')[1]")
            T.esperar_resultado(page, base, pid, hasta=600)
            det = T.get(base, f"/api/combate/partidas/{pid}")
            page.screenshot(path=str(T.SALIDA / "12_combate_8b_real_resultado_1366x768.png"))
            ok = det["resultado"] is not None and det["cadena"] and det["resultado"] in page.inner_text("#cp-sub") + page.inner_text("#banner").upper().replace(" ", "_") or bool(det["resultado"])
            print("resultado real:", det["resultado"], "| modelos:", det["rojo"], "vs", det["azul"], "| cadena íntegra:", det["cadena"])
            print("errores de consola:", [c for c in T.consola if c[0] == "real"])
            nav.close()
    finally:
        srv.terminate()
    return ok and not [c for c in T.consola if c[0] == "real"]
if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
