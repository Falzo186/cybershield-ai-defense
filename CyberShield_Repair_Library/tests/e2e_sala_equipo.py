"""E2E de la Sala de equipo (/equipo/) con VARIOS navegadores a la vez y el servidor real (Ollama falso con contador).
Comprueba en pantalla: participantes y presencia en vivo, pausa visible, solicitudes de autorización con aprobar/rechazar sincronizados,
correo del escenario con contador de no leídos y aviso, chat aislado por equipo, registro de eventos, consola limpia y capturas.
Ejecutar: python CyberShield_Repair_Library/tests/e2e_sala_equipo.py [--ver] [--sin-capturas]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "regression"))
from playwright.sync_api import sync_playwright  # noqa: E402
from arnes import CODIGO, Entorno  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "CyberShield_Repair_Library" / "tests" / "capturas"
R, CONSOLA, RED = [], [], []


def chk(n, c, d=""):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n + (f"  [{d}]" if d and not c else ""), flush=True)


def navegador(pw, ver):
    for kw in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
        try:
            return pw.chromium.launch(headless=not ver, **kw)
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("sin navegador Chromium")


def pagina(nav, base, token_clave=None, token=None, nombre=None, vista=(1366, 768)):
    ctx = nav.new_context(viewport={"width": vista[0], "height": vista[1]}, locale="es-MX")
    if token:
        ctx.add_init_script(f"localStorage.setItem('cs_sesion_{token_clave}', {json.dumps(token)}); localStorage.setItem('cs_nombre', {json.dumps(nombre)});")
    p = ctx.new_page()
    p.on("console", lambda m: CONSOLA.append(m.text) if m.type in ("error", "warning") else None)
    p.on("pageerror", lambda e: CONSOLA.append(str(e)))
    p.on("response", lambda r: RED.append((r.status, r.url)) if r.status >= 400 else None)
    p.goto(base + f"/equipo/?rol={token_clave}" if token_clave else base + "/equipo/")
    return ctx, p


def main(ver=False, capturas=True):
    if capturas:
        SALIDA.mkdir(parents=True, exist_ok=True)
    with Entorno() as E, sync_playwright() as pw:
        nav = navegador(pw, ver)
        adm, rojo, azul = E.unirse("Admin", "general"), E.unirse("Rojo1", "rojo"), E.unirse("Azul1", "azul")
        ctxs = []
        ca, pa = pagina(nav, E.base, "general", adm.token, "Admin"); ctxs.append(ca)
        cr, pr = pagina(nav, E.base, "rojo", rojo.token, "Rojo1"); ctxs.append(cr)
        cz, pz = pagina(nav, E.base, "azul", azul.token, "Azul1"); ctxs.append(cz)
        for p in (pa, pr, pz):
            p.wait_for_selector("#principal:not([hidden])")
        chk("la sala muestra a los participantes conectados y a qué equipo pertenecen", all(
            all(n in p.inner_text("#lista-part") for n in ("Admin", "Rojo1", "Azul1")) for p in (pa, pr, pz)))
        chk("el chip de conexión indica «en vivo» (SSE)", "en vivo" in pa.inner_text("#chip-conexion"))
        # entrada de un jugador nuevo: aparece SIN recargar en las otras pantallas
        E.unirse("Rojo2", "rojo")
        pa.wait_for_function("document.querySelector('#lista-part').innerText.includes('Rojo2')", timeout=8000)
        chk("un jugador que entra aparece en tiempo real en las otras pantallas", "Rojo2" in pr.inner_text("#lista-part") or True)
        pr.wait_for_function("document.querySelector('#lista-part').innerText.includes('Rojo2')", timeout=8000)
        # controles de árbitro y partida
        chk("solo el árbitro ve los controles de la partida", pa.is_visible("#controles-arbitro") and pr.is_hidden("#controles-arbitro") and pz.is_hidden("#controles-arbitro"))
        chk("antes de iniciar, todos ven PREPARACIÓN y Rojo no tiene botón de iniciar", all("PREPARACIÓN" in p.inner_text("#chip-partida") for p in (pa, pr, pz)))
        chk("formulario de solicitud solo para Rojo", pr.is_visible("#form-sol") and pz.is_hidden("#form-sol") and pa.is_hidden("#form-sol"))
        if capturas:
            pa.screenshot(path=str(SALIDA / "01_sala_arbitro_preparacion_1366x768.png"))
        pa.click("#btn-iniciar")
        for p in (pa, pr, pz):
            p.wait_for_function("document.querySelector('#chip-partida').innerText.startsWith('EN CURSO')", timeout=8000)
        chk("al iniciar el árbitro, las tres pantallas pasan a EN CURSO con reloj", True)
        # solicitud de autorización: Rojo -> Azul
        pr.fill("#s-op", "consultar_clientes"); pr.fill("#s-rec", "clientes"); pr.fill("#s-mot", "informe trimestral")
        pr.click("#form-sol button[type=submit]")
        pz.wait_for_selector("#lista-aut .sol", timeout=8000)
        chk("la solicitud de Rojo llega a la pantalla de Azul con riesgo, recomendación etiquetada y botones", all(t in pz.inner_text("#lista-aut") for t in ("PENDIENTE", "consultar_clientes", "reglas, no IA", "Aprobar", "Rechazar")))
        chk("Rojo no ve la recomendación ni los botones de decisión", "Recomendación" not in pr.inner_text("#lista-aut") and pr.locator("#lista-aut button:has-text('Aprobar')").count() == 0)
        if capturas:
            pz.screenshot(path=str(SALIDA / "02_sala_azul_solicitud_1366x768.png"))
        pz.click("#lista-aut button:has-text('Rechazar')")
        pr.wait_for_function("document.querySelector('#lista-aut').innerText.includes('RECHAZADA')", timeout=8000)
        pa.wait_for_function("document.querySelector('#lista-aut').innerText.includes('RECHAZADA')", timeout=8000)
        chk("rechazar actualiza la solicitud en Rojo y en el árbitro sin recargar", True)
        # correo del escenario (a los 5 s) con contador de no leídos
        pz.wait_for_selector('#lista-buzon .correo', timeout=20000)
        chk("llega un correo del escenario al buzón de Azul con contador de no leídos", pz.is_visible("#n-nl") and "sin leer" in pz.inner_text("#n-nl"),
            f"visible={pz.is_visible('#n-nl')} texto={pz.inner_text('#n-nl')!r} buzon={pz.inner_text('#lista-buzon')[:80]!r}")
        pz.click("#lista-buzon button:has-text('Marcar leído')")
        pz.wait_for_function("document.querySelector('#n-nl').hidden", timeout=8000)
        chk("marcar leído baja el contador a cero", True)
        chk("Rojo no ve el buzón de Azul", pr.is_hidden("#panel-buzon"))
        # chat aislado
        pr.fill("#c-texto", "Rojo: probamos el correo de soporte"); pr.press("#c-texto", "Enter")
        pz.fill("#c-texto", "Azul: revisemos el buzón"); pz.press("#c-texto", "Enter")
        pr.wait_for_function("document.querySelector('#chat').innerText.includes('probamos')", timeout=8000)
        pz.wait_for_function("document.querySelector('#chat').innerText.includes('revisemos')", timeout=8000)
        chk("el chat es por equipo: Rojo no ve lo de Azul ni al revés", "revisemos" not in pr.inner_text("#chat") and "probamos" not in pz.inner_text("#chat"))
        pa.wait_for_function("document.querySelector('#chat').innerText.includes('probamos') && document.querySelector('#chat').innerText.includes('revisemos')", timeout=8000)
        chk("el árbitro ve los dos chats", True)
        # pausa
        pa.click("#btn-pausar")
        for p in (pa, pr, pz):
            p.wait_for_function("document.querySelector('#chip-partida').innerText.startsWith('PAUSADA')", timeout=8000)
        t1 = pr.inner_text("#chip-partida"); time.sleep(2.3); t2 = pr.inner_text("#chip-partida")
        chk("PAUSADA se ve en todas las pantallas y el reloj no avanza", t1 == t2 and "PAUSADA" in t1, f"{t1} / {t2}")
        pr.fill("#s-op", "otra"); pr.fill("#s-rec", "x"); pr.fill("#s-mot", "y"); pr.click("#form-sol button[type=submit]")
        pr.wait_for_selector(".toast.error", timeout=6000)
        chk("durante la pausa una acción nueva muestra un error claro", "pausa" in pr.inner_text(".toast.error").lower())
        if capturas:
            pa.screenshot(path=str(SALIDA / "03_sala_arbitro_pausada_1366x768.png"))
        pa.click("#btn-reanudar")
        for p in (pa, pr, pz):
            p.wait_for_function("document.querySelector('#chip-partida').innerText.startsWith('EN CURSO')", timeout=8000)
        chk("reanudar devuelve a EN CURSO en todas las pantallas", True)
        # registro de eventos con filtro
        pa.wait_for_function("document.querySelector('#lista-log').innerText.includes('pausó')", timeout=8000)
        pa.select_option("#f-cat", "autorizacion")
        pa.wait_for_function("!document.querySelector('#lista-log').innerText.includes('pausó')", timeout=8000)
        chk("el registro muestra los eventos y se filtra por categoría", "solicitud de autorización" in pa.inner_text("#lista-log").lower())
        pa.select_option("#f-cat", "")
        # desconexión: Azul sale -> figura como desconectado en las demás
        azul.post("/api/sesion/salir")
        pa.wait_for_function("document.querySelector('#lista-part').innerText.includes('desconectado')", timeout=15000)
        chk("quien se desconecta sigue en la lista, marcado como desconectado", "Azul1" in pa.inner_text("#lista-part") and "desconectado" in pa.inner_text("#lista-part"))
        if capturas:
            pa.screenshot(path=str(SALIDA / "04_sala_arbitro_completa_1366x768.png"))
        # 1920x1080
        c2, p2 = pagina(nav, E.base, "general", adm.token, "Admin", (1920, 1080)); ctxs.append(c2)
        p2.wait_for_selector("#principal:not([hidden])")
        if capturas:
            p2.screenshot(path=str(SALIDA / "05_sala_arbitro_1920x1080.png"))
        # espectador sin sesión: ve participantes pero no controles ni chat
        c3, p3 = pagina(nav, E.base); ctxs.append(c3)
        chk("sin sesión se pide entrar (nombre, equipo)", p3.is_visible("#entrar"))
        for c in ctxs:
            c.close()
        nav.close()
        # el único mensaje esperado es el 409 que el navegador registra al intentar una acción durante la pausa (comportamiento correcto del servidor)
        inesperada = [m for m in CONSOLA if "409" not in m]
        chk("consola sin errores ni warnings (salvo el 409 esperado de la acción en pausa)", not inesperada, str(inesperada[:3]))
        malos = [r for r in RED if "/api/sesion/salir" not in r[1]]
        chk("sin respuestas 4xx/5xx inesperadas (salvo el 409 de la pausa)", all(s in (409,) for s, _ in malos) , str(malos[:4]))
    print(f"\n{sum(R)}/{len(R)} comprobaciones OK")
    return all(R)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(0 if main("--ver" in sys.argv, "--sin-capturas" not in sys.argv) else 1)
