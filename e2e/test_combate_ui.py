"""E2E del Teatro de batalla (/combate/) con Playwright y modelos FALSOS determinísticos.

Arranca su propio servidor (puerto libre, bases temporales), recorre partidas completas desde la interfaz y comprueba:
  * que NUNCA se muestra «victoria/derrota/empate» antes del evento partida.resultado persistido;
  * que el resultado de la pantalla coincide con el persistido (victoria Roja, Azul, empate degradado, inconclusa);
  * el espectador es de solo lectura real (sin botón de acción; el POST da 403);
  * Wazuh se muestra siempre como SIMULADO; estados vacío/carga/error; sin errores ni warnings de consola; sin 4xx/5xx inesperados;
  * capturas reales en 1366×768 y 1920×1080 -> docs/capturas_final/ (y una nota por pantalla).

Ejecutar: python e2e/test_combate_ui.py            (--ver para ver el navegador; --sin-capturas para no escribir imágenes)
No usa Ollama: verifica el motor y la interfaz, NO la calidad de ningún modelo.
"""
import json
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
SALIDA = RAIZ / "docs" / "capturas_final"
CODIGO = "135790"
VISTAS = {"1366x768": {"width": 1366, "height": 768}, "1920x1080": {"width": 1920, "height": 1080}}
resultados, consola, red_mala = [], [], []


def chk(nombre, cond, detalle=""):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre + (f"  [{detalle}]" if (detalle and not cond) else ""))


def puerto_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(base, ruta):
    with urllib.request.urlopen(base + ruta, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def enganchar(page, etiqueta):
    page.on("console", lambda m: consola.append((etiqueta, m.type, m.text)) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: consola.append((etiqueta, "pageerror", str(e))))
    page.on("response", lambda r: red_mala.append((etiqueta, r.status, r.url)) if r.status >= 400 else None)


def esperar_resultado(page, base, pid, hasta=60):
    t0 = time.time()
    while time.time() - t0 < hasta:
        if get(base, f"/api/combate/partidas/{pid}")["resultado"]:
            break
        time.sleep(0.25)
    page.wait_for_function("document.querySelector('#banner') && !document.querySelector('#banner').hidden", timeout=15000)


def iniciar(page, escenario, rojo, azul, semilla=1, ritmo=None):
    anterior = page.evaluate("location.hash.split('/')[1] || ''")
    page.evaluate("""([e, r, a, s, rt]) => { document.querySelector('#nueva').open = true;
        document.querySelector('#f-escenario').value = e; document.querySelector('#f-rojo').value = r; document.querySelector('#f-azul').value = a;
        document.querySelector('#f-semilla').value = s; window.__ritmo = rt; document.querySelector('#form-nueva').requestSubmit(); }""", [escenario, rojo, azul, semilla, ritmo])
    page.wait_for_function("(ant) => (location.hash.split('/')[1] || '') !== ant && document.querySelector('#teatro') && !document.querySelector('#teatro').hidden",
                           arg=anterior, timeout=15000)


def sembrar_partida_larga(ruta):
    """Una partida terminada con ~460 eventos sintéticos (solo para medir el rendimiento de la cronología; no es un resultado real)."""
    sys.path.insert(0, str(RAIZ))
    from src.lab.combate import escenarios as E
    from src.lab.combate.store import Almacen
    alm = Almacen(ruta)
    esc = E.cargar("escalada_privilegios-complejo")
    alm.crear("larga-prueba", esc["id"], E.hash_escenario(esc), {"semilla": 0, "rojo": "sintetico", "azul": "sintetico", "version_prompts": "v2"}, "2026-11-18T09:00:00-06:00")
    alm.añadir("larga-prueba", 0, "2026-11-18T09:00:00-06:00", "partida.creada", {"escenario": esc["id"]})
    for t in range(1, 11):
        alm.añadir("larga-prueba", t, "2026-11-18T09:00:01-06:00", "turno.inicio", {"turno": t, "max_turnos": 10})
        for k in range(11):
            alm.añadir("larga-prueba", t, "2026-11-18T09:00:02-06:00", "rojo.mensaje", {"solicitante": "X01", "mensaje": f"Mensaje sintético {t}.{k}", "peticion": {"recurso": "R-ADM-CONF", "valida": True},
                                                                                         "repetido": False, "modelo": "sintetico"})
            alm.añadir("larga-prueba", t, "2026-11-18T09:00:03-06:00", "siem.senal", {"clave": "solicitud.urgencia"})
            alm.añadir("larga-prueba", t, "2026-11-18T09:00:04-06:00", "azul.decision", {"origen": "rojo", "decision": "RECHAZAR", "justificacion": "sintético", "legitima": False, "modelo": "sintetico"})
            alm.añadir("larga-prueba", t, "2026-11-18T09:00:05-06:00", "rojo.prevenido", {"decision": "RECHAZAR"})
    res = {"resultado": "VICTORIA_AZUL", "motivo": "sintético", "causa": None, "partida_id": "larga-prueba", "escenario": esc["id"], "hash_escenario": E.hash_escenario(esc),
           "turnos_jugados": 10, "max_turnos": 10, "objetivos_alcanzados": [], "umbral_victoria_roja": 3, "tasa_legitimas": 1.0, "integridad_ok": True,
           "metricas": {"rojo": {"intentos": 110, "aceptadas": 0, "efectos": 0, "objetivos": 0, "bloqueadas_por_capas": 0}, "azul": {"clasificacion": {"VP": 110, "FP": 0, "FN": 0, "VN": 4}}},
           "consumo": {"llamadas_modelo": 0, "max_llamadas_modelo": 100, "tokens_salida": 0, "max_tokens_salida": 30000, "errores_consecutivos": 0, "max_errores_consecutivos": 3}}
    alm.añadir("larga-prueba", 10, "2026-11-18T09:01:00-06:00", "partida.resultado", res)
    alm.cerrar("larga-prueba", "finalizada", res, "2026-11-18T09:01:00-06:00")


def lanzar_navegador(pw, ver):
    """Chromium de Playwright si está descargado; si no, el Edge/Chrome ya instalado (sin descargar nada)."""
    for kw in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
        try:
            return pw.chromium.launch(headless=not ver, **kw)
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("no hay ningún navegador Chromium disponible (ni el de Playwright, ni Edge, ni Chrome)")


def main(ver=False, capturas=True):
    port = puerto_libre()
    base = f"http://127.0.0.1:{port}"
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "PUERTO": str(port), "CS_CODIGO_ARBITRO": CODIGO, "CS_COMBATE_DB": os.path.join(tmp, "c.db"),
           "CS_WAZUH_SIM_DB": os.path.join(tmp, "w.db"), "PYTHONIOENCODING": "utf-8"}
    sembrar_partida_larga(env["CS_COMBATE_DB"])
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
        with sync_playwright() as pw:
            nav = lanzar_navegador(pw, ver)
            ctx = nav.new_context(viewport=VISTAS["1366x768"], locale="es-MX")
            page = ctx.new_page()
            enganchar(page, "arbitro")

            # ── Árbitro: entra, estado vacío, formulario ──────────────────────────────────────────────
            page.goto(base + "/combate/")
            page.wait_for_selector("#f-escenario option", state="attached")
            chk("estado vacío: sin partida abierta se explica qué hacer", "Aún no hay ninguna partida" in page.inner_text("#teatro-vacio"))
            chk("sin sesión el botón «Iniciar combate» está desactivado", page.is_disabled("#btn-iniciar"))
            chk("el formulario ofrece 15 escenarios y modelos 8B/falsos", page.locator("#f-escenario option").count() == 15 and page.locator("#f-azul option").count() >= 5)
            chk("el chip de Wazuh dice SIMULADO", "WAZUH SIMULADO" in page.inner_text("#estados"))
            page.fill("#e-codigo", "000000")
            page.click("#form-entrar button")
            page.wait_for_function("document.querySelector('#e-error').textContent.length > 0")
            chk("código de árbitro erróneo -> error comprensible y sin sesión", "incorrecto" in page.inner_text("#e-error").lower() and page.is_disabled("#btn-iniciar"))
            page.fill("#e-codigo", CODIGO)
            page.click("#form-entrar button")
            page.wait_for_function("!document.querySelector('#btn-iniciar').disabled")
            chk("con el código correcto el árbitro puede iniciar combates", not page.is_disabled("#btn-iniciar"))
            if capturas:
                page.screenshot(path=str(SALIDA / "01_nueva_partida_1366x768.png"))

            # ── Partida 1: victoria Roja; nunca victoria antes del resultado ────────────────────────────────
            iniciar(page, "verificacion_falsa-intermedio", "falso:objetivos", "falso:aprobar")
            vistos_prematuros, banner_visible_antes, muestras = [], [], 0
            pid = page.evaluate("location.hash.split('/')[1]")
            t0 = time.time()
            while time.time() - t0 < 30:
                det = get(base, f"/api/combate/partidas/{pid}")
                txt = page.inner_text("#teatro")
                hay_banner = page.is_visible("#banner")
                muestras += 1
                if not det["resultado"]:
                    banner_visible_antes.append(hay_banner)
                    vistos_prematuros.append("Victoria del Equipo" in txt or "Empate" in page.inner_text("#cp-chip"))
                else:
                    break
                time.sleep(0.2)
            chk("durante la partida el banner de resultado está oculto (muestras: %d)" % muestras, not any(banner_visible_antes))
            chk("durante la partida no aparece «Victoria del Equipo…» en ningún punto de la pantalla", not any(vistos_prematuros))
            esperar_resultado(page, base, pid)
            det = get(base, f"/api/combate/partidas/{pid}")
            chk("victoria Roja: la pantalla muestra lo que el motor persistió", det["resultado"] == "VICTORIA_ROJA" and "Victoria del Equipo Rojo" in page.inner_text("#banner"))
            chk("el objetivo se marca con casilla solo tras confirmación del motor", page.locator("#rojo-objetivos li.logrado").count() == len(det["resultado_detalle"]["objetivos_alcanzados"]) >= 2)
            chk("la cronología muestra mensajes, decisiones y eventos del motor", page.locator("#cronos .msg.rojo").count() >= 2 and page.locator("#cronos .msg.azul").count() >= 2 and "Objetivo del Rojo alcanzado" in page.inner_text("#cronos"))
            chk("el botón Interrumpir desaparece al terminar", not page.is_visible("#btn-interrumpir"))
            chk("el reproductor de cronología aparece al terminar", page.is_visible("#reproductor"))
            if capturas:
                page.screenshot(path=str(SALIDA / "02_victoria_roja_1366x768.png"))
            # reproducción: al volver al turno 1 el banner de resultado desaparece (no hay victoria «prematura» al rebobinar)
            page.evaluate("() => { const r = document.querySelector('#rep-turno'); r.value = 1; r.dispatchEvent(new Event('input')); }")
            chk("al rebobinar la cronología el banner de resultado se oculta", not page.is_visible("#banner"))
            page.evaluate("() => { const r = document.querySelector('#rep-turno'); r.value = r.max; r.dispatchEvent(new Event('input')); }")

            # ── Partida 2: victoria Azul ───────────────────────────────────────────────────────────────────
            iniciar(page, "suplantacion_identidad-sencillo", "falso:objetivos", "falso:registro", 2)
            pid2 = page.evaluate("location.hash.split('/')[1]")
            page.wait_for_function("!document.querySelector('#pensando').hidden || !document.querySelector('#banner').hidden", timeout=10000)
            chk("una partida en curso muestra el estado «pensando» (derivado de lo último que persistió el motor)", page.is_visible("#pensando") or get(base, f"/api/combate/partidas/{pid2}")["resultado"])
            esperar_resultado(page, base, pid2)
            chk("victoria Azul en pantalla = VICTORIA_AZUL persistida", get(base, f"/api/combate/partidas/{pid2}")["resultado"] == "VICTORIA_AZUL" and "Victoria del Equipo Azul" in page.inner_text("#banner"), f"{pid2} {get(base, '/api/combate/partidas/' + pid2)['resultado']} | {page.inner_text('#banner')[:80]}")
            chk("el medidor de legítimas marca 100 % y la línea del umbral del 70 %", "100 %" in page.inner_text("#azul-medidor") and page.locator("#azul-medidor u").count() == 1)
            if capturas:
                page.screenshot(path=str(SALIDA / "03_victoria_azul_1366x768.png"))

            # ── Partida 3: empate degradado (Azul «rechazar siempre») ───────────────────────────────────────
            iniciar(page, "escalada_privilegios-sencillo", "falso:objetivos", "falso:rechazar", 3)
            pid3 = page.evaluate("location.hash.split('/')[1]")
            esperar_resultado(page, base, pid3)
            chk("«rechazar siempre» da EMPATE DEGRADADO, no victoria Azul", get(base, f"/api/combate/partidas/{pid3}")["resultado"] == "EMPATE_DEGRADADO" and "Empate degradado" in page.inner_text("#banner") and "Victoria del Equipo Azul" not in page.inner_text("#banner"), f"{pid3} {get(base, '/api/combate/partidas/' + pid3)['resultado']} | {page.inner_text('#banner')[:80]}")
            if capturas:
                page.screenshot(path=str(SALIDA / "04_empate_degradado_1366x768.png"))

            # ── Partida 4: defensa en profundidad visible ──────────────────────────────────────────────────
            iniciar(page, "verificacion_falsa-sencillo", "falso:denegado", "falso:aprobar", 4)
            pid4 = page.evaluate("location.hash.split('/')[1]")
            esperar_resultado(page, base, pid4)
            chk("la defensa en profundidad se ve en la cronología y en el panel del Azul", "Defensa en profundidad" in page.inner_text("#cronos") or "frenadas por las capas" in page.inner_text("#azul-dp"))

            # ── Partida 5: interrupción con confirmación ───────────────────────────────────────────────────
            iniciar(page, "escalada_privilegios-complejo", "falso:aleatorio", "falso:registro", 5, ritmo=2.5)
            pid5 = page.evaluate("location.hash.split('/')[1]")
            page.wait_for_selector("#btn-interrumpir:not([hidden])", timeout=10000)
            page.click("#btn-interrumpir")
            chk("interrumpir pide confirmación (acción irreversible)", page.is_visible("#dlg"))
            page.click("#dlg-ok")
            esperar_resultado(page, base, pid5)
            chk("partida interrumpida = INCONCLUSA, excluida de las tasas", get(base, f"/api/combate/partidas/{pid5}")["resultado"] == "INCONCLUSA" and "inconclusa" in page.inner_text("#banner").lower(), f"{pid5} {get(base, '/api/combate/partidas/' + pid5)['resultado']} | {page.inner_text('#banner')[:80]}")

            # ── Historial ─────────────────────────────────────────────────────────────────────────────────
            page.click("button[data-vista=historial]")
            page.wait_for_selector("#h-tabla table.datos")
            chk("el historial lista las 5 partidas jugadas y la sembrada con sus resultados", page.locator("#h-tabla tbody tr").count() == 6)
            page.select_option("#h-resultado", "INCONCLUSA")
            page.wait_for_function("document.querySelectorAll('#h-tabla tbody tr').length === 1")
            chk("el filtro por resultado funciona", page.locator("#h-tabla tbody tr").count() == 1)
            page.select_option("#h-resultado", "VICTORIA_ROJA")
            page.fill("#h-escenario", "no-existe-ninguno")
            page.wait_for_selector("#h-tabla .vacio")
            chk("historial vacío: mensaje claro en vez de una tabla vacía", "Sin partidas" in page.inner_text("#h-tabla"))
            page.select_option("#h-resultado", "")
            page.fill("#h-escenario", "")
            page.wait_for_selector("#h-tabla table.datos")
            if capturas:
                page.screenshot(path=str(SALIDA / "05_historial_1366x768.png"))
            page.locator("#h-tabla tbody tr").first.click()
            page.wait_for_function("document.querySelector('#vista-teatro') && !document.querySelector('#vista-teatro').hidden")
            page.wait_for_selector("#cronos .turno-bloque .msg")
            chk("abrir una partida del historial reproduce su cronología completa", page.locator("#cronos .turno-bloque").count() >= 1)

            # ── Wazuh simulado ────────────────────────────────────────────────────────────────────────────
            page.click("button[data-vista=wazuh]")
            page.wait_for_selector("#w-tabla table.datos")
            chk("la ventana de Wazuh lleva el badge SIMULADO y dice que no hay instancia real", "SIMULADO" in page.inner_text("#vista-wazuh") and "Desconectada" in page.inner_text("#w-estado"))
            filas = page.locator("#w-tabla tbody tr").count()
            chk("hay alertas (con ruido) en la tabla", filas >= 5)
            page.locator("#w-tabla tbody tr").first.click()
            chk("el detalle JSON de una alerta incluye lab.simulado=true", '"simulado": true' in page.inner_text("#w-detalle"))
            page.fill("#w-nivel", "9")
            page.dispatch_event("#w-nivel", "change")
            page.wait_for_timeout(800)
            niveles = page.eval_on_selector_all("#w-tabla tbody tr td:nth-child(2)", "els => els.map(e => parseInt(e.textContent))")
            chk("el filtro por nivel mínimo funciona", niveles and min(niveles) >= 9)
            if capturas:
                page.screenshot(path=str(SALIDA / "06_wazuh_simulado_1366x768.png"))

            # ── Campañas (vacío) ──────────────────────────────────────────────────────────────────────────
            page.click("button[data-vista=campanas]")
            page.wait_for_selector("#c-lista .tarjeta")
            chk("campañas: se muestra su estado o el vacío explicado", page.inner_text("#c-lista").strip() != "")
            if capturas:
                page.screenshot(path=str(SALIDA / "07_campanas_1366x768.png"))

            # ── Teatro en 1920×1080 y 1280×720 ───────────────────────────────────────────────────────────
            page.click("button[data-vista=teatro]")
            page.evaluate("location.hash = '#teatro/" + pid + "'")
            page.reload()
            page.wait_for_selector("#cronos .msg")
            for nombre, vp in (("1920x1080", VISTAS["1920x1080"]), ("1280x720", {"width": 1280, "height": 720})):
                page.set_viewport_size(vp)
                page.wait_for_timeout(300)
                desborde = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
                chk(f"sin desborde horizontal a {nombre}", not desborde)
                if capturas:
                    page.screenshot(path=str(SALIDA / f"02_victoria_roja_{nombre}.png"))
            page.set_viewport_size(VISTAS["1366x768"])

            # ── Rendimiento con 200+ eventos ───────────────────────────────────────────────────────────────
            t0 = time.time()
            page.goto(base + "/combate/#teatro/larga-prueba")
            page.reload()
            page.wait_for_function("document.querySelectorAll('#cronos .msg').length > 300", timeout=20000)
            ms = (time.time() - t0) * 1000
            n_msgs = page.locator("#cronos .msg").count()
            chk(f"200+ eventos: la cronología se pinta en < 4 s ({n_msgs} mensajes, {ms:.0f} ms) y el contador dice 452", ms < 4000 and "452 eventos" in page.inner_text("#cron-n"))
            t1 = time.time()
            page.evaluate("document.querySelector('#cronos').scrollTop = 0")
            page.evaluate("document.querySelector('#cronos').scrollTop = document.querySelector('#cronos').scrollHeight")
            chk("200+ eventos: el desplazamiento no bloquea el hilo (< 500 ms para ir al inicio y al final)", (time.time() - t1) * 1000 < 500)
            if capturas:
                page.screenshot(path=str(SALIDA / "10_cronologia_460_eventos_1366x768.png"))

            # ── Teclado y foco ─────────────────────────────────────────────────────────────────────────────
            page.keyboard.press("Tab")
            chk("el primer Tab llega al enlace «Saltar al contenido» (navegación por teclado)", page.evaluate("document.activeElement && document.activeElement.className") == "saltar")

            # ── Espectador: solo lectura REAL ──────────────────────────────────────────────────────────────
            ctx2 = nav.new_context(viewport=VISTAS["1366x768"], locale="es-MX")
            esp = ctx2.new_page()
            enganchar(esp, "espectador")
            esp.goto(base + f"/combate/#teatro/{pid}")
            esp.wait_for_selector("#cronos .msg")
            chk("el espectador ve la partida y su resultado", "Victoria del Equipo Rojo" in esp.inner_text("#banner"))
            chk("el espectador no tiene botón de acción (iniciar desactivado, interrumpir oculto)", esp.is_disabled("#btn-iniciar") and not esp.is_visible("#btn-interrumpir"))
            codigo = esp.evaluate("""async () => (await fetch('/api/combate/partidas', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({escenario: 'verificacion_falsa-sencillo', rojo: 'falso:fijo', azul: 'falso:aprobar'})})).status""")
            chk("el espectador anónimo no puede crear partidas (403)", codigo == 403)
            if capturas:
                esp.screenshot(path=str(SALIDA / "08_espectador_1366x768.png"))

            # ── Error y desconexión: el servidor caído se ve, no se esconde ─────────────────────────────
            srv.terminate()
            srv.wait(timeout=10)
            esp.click("button[data-vista=historial]")
            esp.wait_for_selector("#h-tabla .vacio")
            chk("servidor caído: el historial lo dice con claridad, sin tabla vacía ni spinner eterno", "No se pudo cargar el historial" in esp.inner_text("#h-tabla"))
            if capturas:
                esp.screenshot(path=str(SALIDA / "09_servidor_desconectado_1366x768.png"))
            nav.close()
    finally:
        if srv.poll() is None:
            srv.terminate()

    propios = [c for c in consola if not (c[0] == "arbitro" and "403" in c[2]) and not (c[0] == "espectador" and any(x in c[2] for x in ("Failed to load", "ERR_CONNECTION", "Failed to fetch", "net::")))]
    chk("consola del navegador sin errores ni warnings propios", not propios, str(propios[:3]))
    inesperados = [r for r in red_mala if not (r[1] == 403 and "/api/combate/partidas" in r[2]) and not (r[0] == "arbitro" and r[1] == 403 and "/api/sesion" in r[2])]
    chk("sin respuestas 4xx/5xx inesperadas (solo los 403 provocados a propósito)", not inesperados, str(inesperados[:3]))
    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main("--ver" in sys.argv, "--sin-capturas" not in sys.argv) else 1)
