"""E2E de la ventana «Simulación» (/simulacion/): catálogo, procedencia visible y una reproducción completa acelerada.
Servidor real + Playwright (Chromium, Edge o Chrome). Capturas en docs/capturas_caminos/. Ejecutar: python e2e/test_simulacion_ui.py [--ver] [--sin-capturas]"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402
import test_combate_ui as B  # noqa: E402

RAIZ = B.RAIZ
SALIDA = RAIZ / "docs" / "capturas_caminos"
R, CONSOLA, RED = [], [], []
chk, get = B.chk, B.get


def main(ver=False, capturas=True):
    port = B.puerto_libre()
    base = f"http://127.0.0.1:{port}"
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "PUERTO": str(port), "CS_LAB_DB": os.path.join(tmp, "lab.db"), "CS_COMBATE_DB": os.path.join(tmp, "c.db"), "CS_WAZUH_SIM_DB": os.path.join(tmp, "w.db"), "CS_CAMINOS_DB": os.path.join(tmp, "cam.db"), "CS_CODIGO_ARBITRO": "246810", "PYTHONIOENCODING": "utf-8"}
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
        cat = get(base, "/api/simulacion/catalogo")["simulaciones"]
        chk("el catálogo tiene ≥ 6 grabaciones: 3 victorias Rojas, 2 Azules y 1 reversión", len(cat) >= 6 and sum(x["resultado"] == "VICTORIA_ROJA" for x in cat) >= 3 and sum(x["resultado"] == "VICTORIA_AZUL" for x in cat) >= 3 and any(x["reversion"] for x in cat))
        chk("cada registro declara su procedencia (tipo) y la cadena de hashes se recomprueba íntegra", all(x["tipo"] in ("CAMINOS_GUION", "CAMINOS_IA", "LIBRE_IA") for x in cat) and all(get(base, f"/api/simulacion/{x['id']}")["cadena_integra"] for x in cat))
        import urllib.error, urllib.request
        codigos = []
        for r in ("/api/simulacion/sim-no-existe", "/api/simulacion/otra"):
            try:
                urllib.request.urlopen(base + r, timeout=5)
                codigos.append(200)
            except urllib.error.HTTPError as e:
                codigos.append(e.code)
        chk("una simulación desconocida o con ruta maliciosa da 404", codigos == [404, 404])

        with sync_playwright() as pw:
            nav = B.lanzar_navegador(pw, ver)
            ctx = nav.new_context(viewport=B.VISTAS["1366x768"], locale="es-MX")
            p = ctx.new_page()
            p.on("console", lambda m: CONSOLA.append(m.text) if m.type in ("error", "warning") else None)
            p.on("pageerror", lambda e: CONSOLA.append(str(e)))
            p.on("response", lambda r: RED.append((r.status, r.url)) if r.status >= 400 else None)
            p.goto(base + "/simulacion/")
            p.wait_for_selector(".sim-card", state="attached")
            chk("el catálogo muestra las tarjetas con insignia de procedencia visible", p.locator(".sim-card").count() == len(cat) and p.locator(".sim-card .insignia").count() == len(cat) and "GUION" in p.inner_text("#catalogo") and (("IA 8B" in p.inner_text("#catalogo")) == any(x["tipo"] == "CAMINOS_IA" for x in cat)))
            chk("el catálogo explica que un guion NO es «la IA venció»", "no es" in p.inner_text("#vista-catalogo").lower() and "ejecutadas de verdad" in p.inner_text("#vista-catalogo").lower())
            if capturas:
                p.screenshot(path=str(SALIDA / "01_catalogo_1366x768.png"))
            p.evaluate("window.__ritmoSim = 0.03")        # 10 min narrativos -> 18 s
            p.locator('.sim-card[data-id="sim-roja-giro-2f"] button').click()
            p.wait_for_selector("#vista-reproductor:not([hidden])")
            nota = p.inner_text("#nota-ritmo")
            chk("hay una nota fija «Reproducción a ritmo narrativo» y la insignia de procedencia", "ritmo narrativo" in nota.lower() and "GUION" in p.inner_text("#r-meta"))
            chk("antes de reproducir no hay resultado ni «qué enseña»", p.is_hidden("#banner-res") and p.is_hidden("#ensena"))
            chk("la barra de progreso tiene hitos marcados", p.locator("#hitos i").count() >= 5)
            p.click("#btn-hito")
            chk("«siguiente hito» salta al primer movimiento sin mostrar el resultado", p.locator("#cron li").count() >= 1 and p.is_hidden("#banner-res"))
            p.select_option("#sel-vel", "4")
            p.click("#btn-play")
            if capturas:
                time.sleep(2.0)
                p.screenshot(path=str(SALIDA / "02_reproduccion_en_curso_1366x768.png"))
            muestras = []
            t0 = time.time()
            while time.time() - t0 < 40:
                b_oculto, e_oculto = p.evaluate("[document.querySelector('#banner-res').hidden, document.querySelector('#ensena').hidden]")   # lectura atómica
                if not b_oculto:
                    break
                muestras.append(e_oculto)
                time.sleep(0.2)
            p.wait_for_selector("#banner-res:not([hidden])", timeout=30000)
            chk("el resultado y «qué enseña» aparecen solo al llegar al evento de resultado del registro", all(muestras) and p.is_visible("#ensena"), f"muestras={muestras[-3:]} n={len(muestras)} ens={p.is_visible('#ensena')}")
            chk("victoria Roja en CAMINOS_GUION: el banner aclara que NO es una victoria de un modelo", "Victoria del Equipo Rojo" in p.inner_text("#banner-res") and "NO es una victoria de un modelo" in p.inner_text("#banner-res"))
            chk("los paneles se sincronizaron: mensajes, inventario (C-01 válida confirmada), alertas SIMULADAS y base COMPROMETIDA",
                p.locator("#mensajes .m").count() >= 2 and "VÁLIDA" in p.inner_text("#inventario") and "SIMULADO" in p.inner_text("#alertas") and "COMPROMETIDA" in p.inner_text("#base-chip"))
            chk("el grafo resalta el camino recorrido y atenúa el resto", p.locator("#grafo .e.vis").count() >= 4 and p.locator("#grafo .n.vis, #grafo .h.vis").count() >= 5 and p.locator("#grafo .h:not(.vis)").count() >= 10)
            chk("la línea de tiempo está narrada en español con marca de tiempo simulada", "Equipo Rojo" in p.inner_text("#cron") and "09:" in p.inner_text("#cron"))
            if capturas:
                p.screenshot(path=str(SALIDA / "03_resultado_victoria_roja_1366x768.png"))
            # Pausa y arrastre de la barra: volver atrás oculta el resultado (nada se regenera)
            p.fill("#rng", "200") if False else p.evaluate("(() => { const r = document.querySelector('#rng'); r.value = 200; r.dispatchEvent(new Event('input', {bubbles: true})); })()")
            chk("arrastrar la barra hacia atrás oculta el resultado y recompone los paneles desde el registro", p.is_hidden("#banner-res") and "SIN PROBAR".lower() not in "x" and p.locator("#cron li").count() < 20)
            p.click("#btn-volver")
            # Reversión y victoria Azul
            p.locator('.sim-card[data-id="sim-reversion-rotacion"] button').click()
            p.wait_for_selector("#vista-reproductor:not([hidden])")
            p.select_option("#sel-vel", "4")
            p.click("#btn-play")
            p.wait_for_selector("#banner-res:not([hidden])", timeout=40000)
            chk("la reversión termina en victoria Azul, con la base CONTENIDA o ÍNTEGRA y su enseñanza", "Victoria del Equipo Azul" in p.inner_text("#banner-res") and ("ROTADA" in p.inner_text("#inventario")) and "COMPROMETIDA" not in p.inner_text("#base-chip") and len(p.inner_text("#ensena-txt")) > 20)
            if capturas:
                p.screenshot(path=str(SALIDA / "04_reversion_victoria_azul_1366x768.png"))
            p.click("#btn-volver")
            # ── Lanzar una partida desde la interfaz (árbitro) ────────────────────────────────────────────
            import urllib.request as _u
            rq = _u.Request(base + "/api/sesion", data=json.dumps({"nombre": "Arbitro", "equipo": "general", "codigo": "246810"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
            tok = json.loads(_u.urlopen(rq, timeout=10).read().decode())["token"]
            sin_token = None
            try:
                _u.urlopen(_u.Request(base + "/api/caminos/partidas", data=b"{}", headers={"Content-Type": "application/json"}, method="POST"), timeout=10)
            except urllib.error.HTTPError as e:
                sin_token = e.code
            chk("sin sesión de árbitro, lanzar una partida da 403", sin_token == 403)
            p.evaluate(f"localStorage.setItem('cs_sesion_general', {json.dumps(tok)})")
            p.reload()
            p.evaluate("document.querySelector('#lanzar').open = true; window.__ritmoSim = 0.02")
            p.wait_for_selector("#l-ir:not([disabled])", timeout=10000)
            p.select_option("#l-modo", "auto"); p.select_option("#l-rojo", "primera"); p.select_option("#l-azul", "aprobar")
            p.click("#l-ir")
            p.wait_for_selector("#vista-reproductor:not([hidden])", timeout=30000)
            chk("el modo automático se lanza desde la interfaz y se abre su reproducción con la insignia GUION (líneas base, sin IA)", "GUION" in p.inner_text("#r-meta") and "ritmo narrativo" in p.inner_text("#nota-ritmo").lower())
            p.select_option("#sel-vel", "4"); p.click("#btn-play")
            p.wait_for_selector("#banner-res:not([hidden])", timeout=40000)
            chk("automático: Azul «aprobar siempre» deja ganar al Rojo; el banner aclara que es un guion, y el inventario muestra la credencial VÁLIDA solo tras el motor",
                "Victoria del Equipo Rojo" in p.inner_text("#banner-res") and "NO es una victoria de un modelo" in p.inner_text("#banner-res") and "VÁLIDA" in p.inner_text("#inventario") and "COMPROMETIDA" in p.inner_text("#base-chip"),
                f"banner={p.inner_text('#banner-res')[:80]!r} inv={p.inner_text('#inventario')[:120]!r} base={p.inner_text('#base-chip')!r}")
            chk("en el modo automático no se pinta el grafo fijo", "no usa el grafo fijo" in p.inner_text("#grafo"))
            if capturas:
                p.screenshot(path=str(SALIDA / "06_automatico_lanzado_1366x768.png"))
            p.click("#btn-volver")
            p.select_option("#l-modo", "grafo"); p.select_option("#l-rojo", "primera"); p.select_option("#l-azul", "registro")
            p.click("#l-ir")
            p.wait_for_selector("#vista-reproductor:not([hidden])", timeout=30000)
            p.select_option("#sel-vel", "4"); p.click("#btn-play")
            p.wait_for_selector("#banner-res:not([hidden])", timeout=40000)
            chk("grafo lanzado desde la UI: Azul por registro gana y el grafo se resalta", "Victoria del Equipo Azul" in p.inner_text("#banner-res") and p.locator("#grafo .e.vis").count() >= 2)
            ctx.close()
            ctx2 = nav.new_context(viewport=B.VISTAS["1920x1080"], locale="es-MX")
            p2 = ctx2.new_page()
            p2.on("console", lambda m: CONSOLA.append(m.text) if m.type in ("error", "warning") else None)
            p2.goto(base + "/simulacion/#sim-roja-inyeccion-documento")
            p2.wait_for_selector("#vista-reproductor:not([hidden])")
            p2.evaluate("window.__ritmoSim = 0.03")
            p2.select_option("#sel-vel", "4")
            p2.click("#btn-play")
            p2.wait_for_selector("#banner-res:not([hidden])", timeout=40000)
            inv = p2.inner_text("#inventario")
            chk("en la inyección por documento ninguna credencial se usó: el inventario NO inventa validez (todo «sin probar»)", "VÁLIDA" not in inv and inv.count("sin probar") == 2)
            if capturas:
                p2.screenshot(path=str(SALIDA / "05_inyeccion_documento_1920x1080.png"))
            ctx2.close()
            nav.close()
        chk("consola sin errores ni warnings", not CONSOLA, str(CONSOLA[:3]))
        chk("sin respuestas 4xx/5xx inesperadas", not RED, str(RED[:3]))
    finally:
        srv.terminate()
        try:
            srv.wait(10)
        except Exception:  # noqa: BLE001
            srv.kill()
    print(f"\nTotal {sum(B.resultados)}/{len(B.resultados)}")
    return all(B.resultados)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(0 if main("--ver" in sys.argv, "--sin-capturas" not in sys.argv) else 1)
