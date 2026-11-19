"""E2E de las pantallas nuevas de la misión extra (/combate/): partidas curadas con «Reproducir cronología» y modo «Guion determinista (sin IA)».

Solo modelos FALSOS (no usa la GPU ni Ollama). Comprueba:
  * las 3 partidas curadas aparecen en el Historial con modelo, semilla, versión de prompts y enlace a sus eventos;
  * «Reproducir cronología» avanza turno a turno y termina con el resultado persistido (nada se calcula en el navegador);
  * una curada muestra el aviso «REPRODUCCIÓN de una partida real registrada»; sus eventos son de solo lectura;
  * el guion determinista da VICTORIA_ROJA contra «APROBAR siempre» y VICTORIA_AZUL contra el Azul por registro, con la etiqueta
    permanente «GUION DETERMINISTA — NO ES UN MODELO» visible mientras dura la partida y al terminar;
  * una partida con modelos reales (no falsos) NO lleva esa etiqueta;
  * consola sin errores ni warnings, sin respuestas 4xx/5xx inesperadas; capturas 1366×768 y 1920×1080 en docs/capturas_final/extra/.
Ejecutar: python e2e/test_combate_extra.py [--ver] [--sin-capturas]
"""
import json
import os
import sys
import tempfile
import time
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import test_combate_ui as B  # noqa: E402  (reutiliza el arnés: servidor, navegador, utilidades)

RAIZ = B.RAIZ
SALIDA = RAIZ / "docs" / "capturas_final" / "extra"
chk, get = B.chk, B.get


def main(ver=False, capturas=True):
    port = B.puerto_libre()
    base = f"http://127.0.0.1:{port}"
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "PUERTO": str(port), "CS_CODIGO_ARBITRO": B.CODIGO, "CS_COMBATE_DB": os.path.join(tmp, "c.db"),
           "CS_WAZUH_SIM_DB": os.path.join(tmp, "w.db"), "PYTHONIOENCODING": "utf-8"}
    srv = subprocess.Popen([sys.executable, str(RAIZ / "server" / "app.py")], cwd=str(RAIZ), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                get(base, "/api/combate/estado")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            chk("el servidor arranca", False)
            return False
        if capturas:
            SALIDA.mkdir(parents=True, exist_ok=True)

        # ── API: curadas ─────────────────────────────────────────────────────────────────────────────
        cur = get(base, "/api/combate/curadas")["curadas"]
        chk("la API lista 3 partidas curadas con resultados distintos", len(cur) == 3 and {c["resultado"] for c in cur} == {"VICTORIA_AZUL", "EMPATE_DEGRADADO", "EMPATE"})
        for c in cur:
            d = get(base, f"/api/combate/partidas/{c['id']}")
            chk(f"curada {c['id']}: cadena de hashes íntegra y resultado persistido", d["cadena"] is True and d["resultado"] == c["resultado"] and d["curada"] is True)
        chk("una curada inexistente o con ruta maliciosa da 404", all(_codigo(base, r) == 404 for r in ("/api/combate/partidas/curada-xx", "/api/combate/partidas/curada-..%2f..")))
        fallo_post = _post_sin_sesion(base)
        chk("nadie sin sesión de árbitro puede crear partidas (403)", fallo_post == 403)

        with sync_playwright() as pw:
            nav = B.lanzar_navegador(pw, ver)
            ctx = nav.new_context(viewport=B.VISTAS["1366x768"], locale="es-MX")
            page = ctx.new_page()
            B.enganchar(page, "extra")
            page.goto(base + "/combate/#historial")
            page.wait_for_selector("#h-curadas-lista .curada", state="attached")
            tarjetas = page.locator("#h-curadas-lista .curada")
            chk("el Historial muestra 3 tarjetas curadas", tarjetas.count() == 3)
            txt = page.inner_text("#h-curadas")
            chk("cada curada muestra modelo, semilla y versión de prompts", txt.count("semilla") >= 3 and txt.count("prompts v2") >= 3 and "qwen3:8b" in txt and "llama3.1:8b" in txt)
            chk("cada curada enlaza a sus eventos", page.locator("#h-curadas-lista a[href*='/eventos']").count() == 3)
            chk("se rotula como reproducción de partidas REALES", "partidas REALES" in txt)
            if capturas:
                page.screenshot(path=str(SALIDA / "01_historial_curadas_1366x768.png"))

            # ── Reproducir cronología ────────────────────────────────────────────────────────────────
            page.evaluate("window.__ritmoRep = 150")
            tarjetas.nth(0).locator("button", has_text="Reproducir cronología").click()
            page.wait_for_function("document.querySelector('#teatro') && !document.querySelector('#teatro').hidden")
            page.wait_for_function("!document.querySelector('#banner-curada').hidden")
            chk("la curada lleva el aviso «REPRODUCCIÓN de una partida real registrada»", "REPRODUCCIÓN de una partida real" in page.inner_text("#banner-curada"))
            chk("la curada no lleva la etiqueta de guion (sus modelos son 8B reales)", page.is_hidden("#etiqueta-guion"))
            page.wait_for_function("document.querySelector('#rep-valor').textContent.startsWith('0 de') || document.querySelector('#btn-reproducir').textContent.includes('Pausar')", timeout=15000)
            chk("durante la reproducción el banner de resultado está oculto", page.is_hidden("#banner") or "Pausar" not in page.inner_text("#btn-reproducir"))
            page.wait_for_function("document.querySelector('#btn-reproducir').textContent.includes('Reproducir') && !document.querySelector('#banner').hidden", timeout=30000)
            chk("al terminar la reproducción se muestra el resultado persistido", "Victoria del Equipo Azul" in page.inner_text("#banner"))
            chk("la reproducción dejó el deslizador en el último turno", page.input_value("#rep-turno") == page.get_attribute("#rep-turno", "max"))
            chk("sin sesión de árbitro no hay botón de interrumpir en una curada", page.is_hidden("#btn-interrumpir"))
            if capturas:
                page.screenshot(path=str(SALIDA / "02_curada_reproduccion_1366x768.png"))

            # ── Guion determinista (necesita árbitro) ────────────────────────────────────────────────
            page.goto(base + "/combate/")
            page.wait_for_selector("#f-escenario option", state="attached")
            page.fill("#e-codigo", B.CODIGO)
            page.click("#form-entrar button")
            page.wait_for_function("!document.querySelector('#btn-iniciar').disabled")
            page.evaluate("document.querySelector('#demo-guion').open = true; document.querySelector('#f-escenario').value = 'verificacion_falsa-intermedio'; window.__ritmo = 0.5")
            chk("la tarjeta del guion dice que NO es un modelo", "NO ES UN MODELO" in page.inner_text("#demo-guion"))
            if capturas:
                page.screenshot(path=str(SALIDA / "03_guion_tarjeta_1366x768.png"))
            for boton, esperado, texto in (("#btn-guion-aprobar", "VICTORIA_ROJA", "Victoria del Equipo Rojo"), ("#btn-guion-registro", "VICTORIA_AZUL", "Victoria del Equipo Azul")):
                anterior = page.evaluate("location.hash.split('/')[1] || ''")
                page.click(boton)
                page.wait_for_function("(a) => (location.hash.split('/')[1] || '') !== a && !document.querySelector('#teatro').hidden", arg=anterior, timeout=15000)
                pid = page.evaluate("location.hash.split('/')[1]")
                try:
                    page.wait_for_selector("#etiqueta-guion", state="visible", timeout=3000)
                except Exception:  # noqa: BLE001
                    pass
                chk(f"{boton}: la etiqueta permanente está visible mientras la partida corre (antes del resultado)",
                    page.is_visible("#etiqueta-guion") and "GUION DETERMINISTA — NO ES UN MODELO" in page.inner_text("#etiqueta-guion") and page.is_hidden("#banner"))
                B.esperar_resultado(page, base, pid)
                det = get(base, f"/api/combate/partidas/{pid}")
                chk(f"{boton}: el motor persiste {esperado} y la pantalla lo muestra", det["resultado"] == esperado and texto in page.inner_text("#banner"))
                chk(f"{boton}: la etiqueta sigue visible con la partida terminada", page.is_visible("#etiqueta-guion"))
                chk(f"{boton}: el Rojo es el guion y no un modelo", det["rojo"] == "rojo_objetivos" and det["cadena"] is True)
                if capturas:
                    page.screenshot(path=str(SALIDA / f"04_guion_{esperado.lower()}_1366x768.png"))
            ctx.close()

            # ── 1920×1080 ───────────────────────────────────────────────────────────────────────────
            ctx2 = nav.new_context(viewport=B.VISTAS["1920x1080"], locale="es-MX")
            p2 = ctx2.new_page()
            B.enganchar(p2, "extra-1080")
            p2.goto(base + "/combate/#historial")
            p2.wait_for_selector("#h-curadas-lista .curada", state="attached")
            if capturas:
                p2.screenshot(path=str(SALIDA / "01_historial_curadas_1920x1080.png"))
            p2.goto(base + "/combate/#teatro/curada-sobrecautela")
            p2.reload()
            p2.wait_for_function("document.querySelector('#teatro') && !document.querySelector('#teatro').hidden && !document.querySelector('#banner').hidden", timeout=15000)
            chk("la curada de sobre-cautela muestra EMPATE_DEGRADADO", "Empate degradado" in p2.inner_text("#banner"))
            chk("la curada del objetivo parcial es un EMPATE con 1 objetivo", (get(base, "/api/combate/partidas/curada-objetivo-parcial")["resultado_detalle"]["objetivos_alcanzados"] or [None]) != [])
            if capturas:
                p2.screenshot(path=str(SALIDA / "02_curada_sobrecautela_1920x1080.png"))
            ctx2.close()
            nav.close()

        malos = [c for c in B.consola]
        chk("consola sin errores ni warnings", not malos, str(malos[:3]))
        feos = [r for r in B.red_mala if "/api/combate/partidas/curada-xx" not in r[2]]
        chk("sin respuestas 4xx/5xx inesperadas", not feos, str(feos[:3]))
    finally:
        srv.terminate()
        try:
            srv.wait(10)
        except Exception:  # noqa: BLE001
            srv.kill()
    ok = all(B.resultados)
    print(f"\n{sum(B.resultados)}/{len(B.resultados)} comprobaciones OK")
    return ok


def _codigo(base, ruta):
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen(base + ruta, timeout=10)
        return 200
    except urllib.error.HTTPError as e:
        return e.code


def _post_sin_sesion(base):
    import urllib.error
    import urllib.request
    rq = urllib.request.Request(base + "/api/combate/partidas", data=json.dumps({"escenario": "verificacion_falsa-sencillo", "rojo": "falso:objetivos", "azul": "falso:registro"}).encode(),
                                headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(rq, timeout=10)
        return 200
    except urllib.error.HTTPError as e:
        return e.code


if __name__ == "__main__":
    sys.exit(0 if main("--ver" in sys.argv, "--sin-capturas" not in sys.argv) else 1)
