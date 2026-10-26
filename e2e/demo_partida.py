"""Prueba de extremo a extremo: una partida Rojo vs Azul completa, sin intervención humana.

Arranca su propio servidor (puerto libre, BD temporal: no toca data/lab.db ni data/eventos.jsonl), abre cuatro
navegadores aislados (General, Rojo, Azul, Espectador) con Playwright y recorre la partida guardando capturas en
docs/capturas_demo/ y un resumen con lo observado en docs/capturas_demo/RESUMEN.md.

Ejecutar:  python e2e/demo_partida.py          (requiere: pip install playwright && playwright install chromium)
           python e2e/demo_partida.py --ver    (con el navegador visible)
Sale con código 1 si alguna comprobación falla.
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "capturas_demo"
VIEWPORT = {"width": 1366, "height": 768}
CODIGO_ARBITRO = "246810"  # se fija con CS_CODIGO_ARBITRO para el servidor de la prueba
NOMBRES = {"general": "Juez Demo", "rojo": "Rita Rojo", "azul": "Beto Azul"}

pasos = []       # [{titulo, notas, checks: [(ok, nombre, esperado, observado)], capturas: [archivo]}]
errores_js = []  # (paso, vista, texto) de los errores de consola


def paso(titulo):
    pasos.append({"titulo": titulo, "notas": [], "checks": [], "capturas": []})
    print(f"\n== {titulo}")


def nota(texto):
    pasos[-1]["notas"].append(texto)
    print("   · " + texto)


def chk(nombre, esperado, observado, ok=None):
    ok = (esperado == observado) if ok is None else bool(ok)
    pasos[-1]["checks"].append((ok, nombre, esperado, observado))
    print(("   OK    " if ok else "   FALLO ") + f"{nombre} (esperado {esperado!r}, observado {observado!r})")
    return ok


def captura(pg, nombre):
    archivo = f"{len([c for p in pasos for c in p['capturas']]) + 1:02d}_{nombre}.jpg"
    pg.screenshot(path=str(SALIDA / archivo), type="jpeg", quality=72)
    pasos[-1]["capturas"].append(archivo)


def esperar(cond, timeout=6.0):
    """Espera a que cond() sea verdadero (el SSE tarda ~1 s en propagar). -> último valor."""
    fin = time.time() + timeout
    v = cond()
    while not v and time.time() < fin:
        time.sleep(0.2)
        v = cond()
    return v


def marcador(pg):
    """Lee el marcador de la cabecera (General/Espectador) -> {etiqueta: texto}."""
    return pg.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#marcador-partida .mp-item')]
        .map(n => [n.querySelector('.mp-lbl').textContent.trim(), n.querySelector('b').textContent.trim()]))""")


def numero(texto):
    m = re.search(r"-?\d+", texto or "")
    return int(m.group()) if m else None


def valores(pg):
    """Riesgo, puntos de Rojo y de Azul y conteos del marcador como números."""
    m = marcador(pg)
    rojo = next((v for k, v in m.items() if "Rojo" in k and "denegados" not in k), "")
    azul = next((v for k, v in m.items() if "Azul" in k), "")
    return {"riesgo": numero(m.get("Riesgo")), "rojo": numero(rojo), "azul": numero(azul),
            "clics": numero(m.get("Clics")), "contenciones": numero(m.get("Contenciones")),
            "reportes": numero(m.get("Reportes")), "pdf": numero(m.get("PDF abiertos"))}


def arrancar_servidor():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    tmp = Path(tempfile.mkdtemp(prefix="cs_e2e_"))
    env = {**os.environ, "PUERTO": str(puerto), "CS_LAB_DB": str(tmp / "lab.db"), "PYTHONIOENCODING": "utf-8",
           "CS_CODIGO_ARBITRO": CODIGO_ARBITRO}
    proc = subprocess.Popen([sys.executable, "server/app.py"], cwd=RAIZ, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/estado", timeout=1)
            return proc, base, tmp
        except Exception:  # noqa: BLE001 - aún arrancando
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("el servidor no arrancó")


def abrir_correo(azul, texto):
    azul.locator(".buzon-item", has_text=texto).click()
    azul.wait_for_timeout(250)


def toast(pg):
    return pg.locator("#toast").inner_text() if pg.locator("#toast").is_visible() else ""


def main(ver=False):
    SALIDA.mkdir(parents=True, exist_ok=True)
    for viejo in SALIDA.glob("*.jpg"):
        viejo.unlink()
    proc, base, tmp = arrancar_servidor()
    inicio = time.time()
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch(headless=not ver)

            def vista(rol):
                ctx = nav.new_context(viewport=VIEWPORT, accept_downloads=True, locale="es-MX")
                pg = ctx.new_page()
                pg.on("console", lambda m, r=rol: errores_js.append((len(pasos), r, m.text)) if m.type == "error" else None)
                pg.on("pageerror", lambda e, r=rol: errores_js.append((len(pasos), r, str(e))))
                pg.on("dialog", lambda dlg: dlg.accept())  # confirmaciones (iniciar, finalizar)
                pg.goto(f"{base}/?rol={rol}")
                pg.wait_for_selector(".ventana", state="attached")
                if rol in NOMBRES:  # cada participante se une con su nombre (el árbitro, además, con su código)
                    pg.wait_for_selector("#unirse-modal:not([hidden])")
                    pg.fill("#unirse-nombre", NOMBRES[rol])
                    if rol == "general":
                        pg.fill("#unirse-codigo", CODIGO_ARBITRO)
                    pg.click("#unirse-entrar")
                    pg.wait_for_selector("#unirse-modal", state="hidden")
                pg.wait_for_timeout(700)
                return ctx, pg

            # ---------------------------------------------------------------------------------------------
            paso("1. Preparación: cada participante entra con su nombre, entra un espectador y el árbitro inicia la partida")
            nota("Cada vista se une con un nombre visible (POST /api/sesion); la General, además, con el código de árbitro.")
            _, general = vista("general")
            _, rojo = vista("rojo")
            _, azul = vista("azul")
            _, espectador = vista("espectador")
            for rol, pg in (("general", general), ("rojo", rojo), ("azul", azul)):
                chk(f"{rol} tiene su sesión y su nombre en la cabecera", True,
                    bool(pg.evaluate(f"localStorage.getItem('cs_sesion_{rol}')"))
                    and NOMBRES[rol] in pg.inner_text("#equipo-tag"))
            chk("todas las vistas ven la partida en preparación", ["PREPARACIÓN"] * 4,
                [pg.inner_text("#partida-estado") for pg in (general, rojo, azul, espectador)])
            rojo.click('[data-icono="correo"]')
            rojo.wait_for_selector('[data-ventana="buzon"]:not([hidden])')
            rojo.click("#btn-correo")
            t = esperar(lambda: "no ha empezado" in toast(rojo) and toast(rojo)) or toast(rojo)
            chk("antes de iniciar, Rojo no puede enviar (409)", True, "no ha empezado" in t)
            rojo.locator('[data-ventana="buzon"] .ventana-cerrar').click()
            captura(general, "general_preparacion")
            general.select_option("#sel-duracion", "5")
            general.click("#btn-iniciar-partida")
            ok = esperar(lambda: all(pg.inner_text("#partida-estado").startswith("⏱") for pg in (general, rojo, azul, espectador)))
            chk("al iniciar, las 4 vistas muestran la cuenta atrás", True, bool(ok))
            restantes = [pg.inner_text("#partida-estado") for pg in (general, rojo, azul, espectador)]
            nota("Reloj en cada vista: " + " | ".join(restantes))
            segundos = [int(r[2:4]) * 60 + int(r[5:7]) for r in restantes]
            chk("todas cuentan lo mismo (±2 s, el reloj lo manda el servidor)", True, max(segundos) - min(segundos) <= 2
                and 290 <= min(segundos) <= 300)
            chk("el espectador no tiene token ni botones de acción", True,
                espectador.locator("#main-wrap").is_hidden() and espectador.locator("#btn-finalizar").is_hidden())
            chk("marcador inicial en General", {"riesgo": 0, "rojo": 0, "azul": 0}, {k: valores(general)[k] for k in ("riesgo", "rojo", "azul")})
            captura(general, "general_inicio")
            captura(rojo, "rojo_inicio")
            captura(azul, "azul_inicio")

            # ---------------------------------------------------------------------------------------------
            paso("2. Rojo envía 3 correos (uno sin adjunto y dos con PDF)")
            rojo.click('[data-icono="correo"]')
            rojo.wait_for_selector('[data-ventana="buzon"]:not([hidden])')
            enviados = []
            for plantilla in ("soporte_tecnico", "recursos_humanos", "paqueteria"):
                rojo.select_option("#sel-plantilla", plantilla)
                rojo.click("#btn-correo")
                t = esperar(lambda: "Correo enviado" in toast(rojo) and toast(rojo)) or toast(rojo)
                enviados.append(t)
                rojo.wait_for_timeout(300)
            chk("los 3 envíos se confirman", 3, sum("Correo enviado" in t for t in enviados))
            nota("Avisos: " + " | ".join(enviados))
            captura(rojo, "rojo_envia_correos")
            n = esperar(lambda: azul.locator("#btn-buzon").inner_text().endswith("(3)") and 3)
            chk("el buzón de Azul se actualiza solo por SSE", 3, n or azul.locator("#btn-buzon").inner_text())

            # ---------------------------------------------------------------------------------------------
            paso("3a. Azul abre su buzón y lee un correo")
            azul.click('[data-icono="correo"]')
            azul.wait_for_selector('[data-ventana="buzon"]:not([hidden])')
            esperar(lambda: azul.locator(".buzon-item").count() == 3)
            chk("Azul ve los 3 correos", 3, azul.locator(".buzon-item").count())
            chk("dos traen PDF adjunto", 2, azul.locator(".buzon-item .marca-pdf").count())
            abrir_correo(azul, "Acción requerida")
            chk("el detalle muestra el enlace local", True, azul.locator("#buzon-detalle a[href^='/l/']").count() == 1)
            captura(azul, "azul_lee_correo")

            # ---------------------------------------------------------------------------------------------
            paso("3b. El «empleado distraído» hace clic en el enlace del correo de paquetería")
            abrir_correo(azul, "paquete")
            with azul.context.expect_page() as nueva:
                azul.locator("#buzon-detalle a[href^='/l/']").click()
            pagina = nueva.value
            pagina.wait_for_load_state()
            chk("se abre la página de enlace de prueba", True, "enlace de prueba del laboratorio" in pagina.content())
            captura(pagina, "enlace_de_prueba")
            pagina.close()
            v = esperar(lambda: valores(general)["clics"] == 1 and valores(general)) or valores(general)
            chk("General: clic contado", 1, v["clics"])
            chk("riesgo sube +15", 15, v["riesgo"])
            chk("Rojo gana +10 (enlace sin contener)", 10, v["rojo"])
            nota(f"Marcador tras el clic: {v}")
            captura(general, "general_tras_clic")

            # ---------------------------------------------------------------------------------------------
            paso("3c. Azul reporta el correo de soporte técnico")
            abrir_correo(azul, "Acción requerida")
            azul.locator("#buzon-detalle button", has_text="Reportar").click()
            t = esperar(lambda: "reportado" in toast(azul) and toast(azul)) or toast(azul)
            nota("Aviso: " + t)
            chk("misión «Reportar un correo sospechoso» completada", True, "Reportar un correo sospechoso" in t)
            v = esperar(lambda: valores(general)["riesgo"] == 5 and valores(general)) or valores(general)
            chk("riesgo baja −10", 5, v["riesgo"])
            chk("Azul suma 10", 10, v["azul"])

            # ---------------------------------------------------------------------------------------------
            paso("3d. Azul contiene el enlace clicado")
            abrir_correo(azul, "paquete")
            ok = esperar(lambda: azul.locator("#buzon-detalle button", has_text="Contener").count() == 1)
            chk("aparece el botón Contener (el enlace tuvo clic)", True, bool(ok))
            azul.locator("#buzon-detalle button", has_text="Contener").click()
            t = esperar(lambda: "contenido" in toast(azul) and toast(azul)) or toast(azul)
            nota("Aviso: " + t)
            v = esperar(lambda: valores(general)["contenciones"] == 1 and valores(general)) or valores(general)
            chk("riesgo baja (5 − 15, acotado a 0)", 0, v["riesgo"])
            chk("Rojo pierde los 10 del enlace", 0, v["rojo"])
            chk("Azul suma 15 (25)", 25, v["azul"])
            captura(azul, "azul_contiene_enlace")

            # ---------------------------------------------------------------------------------------------
            paso("3e. Azul abre el PDF de nómina y luego lo reporta")
            abrir_correo(azul, "nómina")
            with azul.expect_download() as descarga:
                azul.locator(".buzon-adjunto button", has_text="Abrir PDF").click()
            d = descarga.value
            ruta_pdf = Path(tmp) / d.suggested_filename
            d.save_as(ruta_pdf)
            chk("se descarga el PDF fijo", "recibo_nomina.pdf", d.suggested_filename)
            chk("es un PDF de verdad", True, ruta_pdf.read_bytes().startswith(b"%PDF-"))
            v = esperar(lambda: valores(general)["pdf"] == 1 and valores(general)) or valores(general)
            chk("Rojo gana +5 (PDF abierto sin reportar)", 5, v["rojo"])
            chk("Azul suma 10 (misión del documento) = 35", 35, v["azul"])
            captura(general, "general_pdf_abierto")
            azul.wait_for_timeout(500)
            abrir_correo(azul, "nómina")
            azul.locator(".buzon-adjunto button", has_text="Reportar PDF").click()
            t = esperar(lambda: "PDF reportado" in toast(azul) and toast(azul)) or toast(azul)
            nota("Aviso: " + t)
            v = esperar(lambda: valores(general)["rojo"] == 0 and valores(general)) or valores(general)
            chk("Rojo pierde los 5 del PDF", 0, v["rojo"])
            chk("riesgo sigue en 0 (no baja de 0)", 0, v["riesgo"])
            chk("el aviso dice el riesgo real de la partida, no solo el −10 de la regla", True,
                "riesgo de la partida 0/100" in t)
            esperar(lambda: azul.locator(".buzon-item", has_text="nómina").locator(".marca", has_text="PDF REPORTADO").count())
            chk("la lista del buzón marca el PDF como reportado", 1,
                azul.locator(".buzon-item", has_text="nómina").locator(".marca", has_text="PDF REPORTADO").count())
            captura(azul, "azul_reporta_pdf")

            # ---------------------------------------------------------------------------------------------
            paso("4. Verificación: misiones, marcador en General y Espectador")
            azul.click('[data-azul="misiones"]')
            esperar(lambda: azul.locator(".mision.completada").count() == 3)
            estados = azul.evaluate("""() => [...document.querySelectorAll('.mision')].map(m =>
                [m.querySelector('b').textContent, m.classList.contains('completada')])""")
            chk("misiones completadas: reportar, contener y documento; la manual pendiente",
                [True, True, False, True], [e for _, e in estados])
            captura(azul, "azul_misiones")
            vg, ve = valores(general), valores(espectador)
            chk("General y Espectador ven el mismo marcador", vg, ve)
            nota(f"Marcador final antes de cerrar: {vg}")
            captura(espectador, "espectador_marcador")
            # Escritorio: maximizar la auditoría para mostrar el rastro de eventos, y restaurarla.
            general.locator('[data-ventana="auditoria"] .ventana-maximizar').click()
            general.wait_for_timeout(300)
            lineas = general.locator("#aud-log .ln").count()
            chk("la auditoría de General registró la partida", True, lineas >= 10, ok=lineas >= 10)
            nota(f"Líneas de auditoría en General: {lineas}")
            captura(general, "general_auditoria_maximizada")
            general.locator('[data-ventana="auditoria"] .ventana-maximizar').click()

            # ---------------------------------------------------------------------------------------------
            paso("5. General finaliza la partida y se muestra el resultado")
            general.click('[data-icono="finalizar"]')
            ok = esperar(lambda: general.locator("#final-modal").is_visible())
            chk("General ve la pantalla de resultado", True, bool(ok))
            chk("ganador", "GANA EL EQUIPO AZUL", general.inner_text("#final-ganador"))
            chk("puntajes finales (Rojo — Azul)", ("0", "35"),
                (general.inner_text("#final-rojo"), general.inner_text("#final-azul")))
            captura(general, "general_resultado")
            ok = esperar(lambda: espectador.locator("#final-modal").is_visible())
            chk("el Espectador también ve el resultado", True, bool(ok))
            captura(espectador, "espectador_resultado")
            rojo.click("#btn-correo")
            t = esperar(lambda: "finalizó" in toast(rojo) and toast(rojo)) or toast(rojo)
            chk("tras finalizar, Rojo ya no puede enviar (409)", True, "finalizó" in t)
            captura(rojo, "rojo_tras_finalizar")
            inesperados = [f"{r}: {e}" for n, r, e in errores_js if not (n in (1, len(pasos)) and r == "rojo" and "409" in e)]
            chk("sin errores de consola inesperados en ninguna vista", [], inesperados)

            nav.close()
    finally:
        proc.terminate()

    eventos = [json.loads(x) for x in (tmp / "eventos.jsonl").read_text(encoding="utf-8").splitlines()] \
        if (tmp / "eventos.jsonl").exists() else []
    escribir_resumen(time.time() - inicio, eventos)
    return all(ok for p in pasos for ok, *_ in p["checks"])


def escribir_resumen(duracion, eventos):
    total = sum(len(p["checks"]) for p in pasos)
    buenos = sum(ok for p in pasos for ok, *_ in p["checks"])
    lineas = [
        "# Prueba de extremo a extremo — partida Rojo vs Azul",
        "",
        f"Generado por `e2e/demo_partida.py` el {datetime.now().astimezone().isoformat(timespec='seconds')} "
        f"en {duracion:.0f} s, con un servidor y una BD temporales (Chromium headless, 1366×768, 4 navegadores aislados).",
        "",
        f"**Resultado: {buenos}/{total} comprobaciones correctas.**",
        "",
    ]
    for p in pasos:
        lineas += [f"## {p['titulo']}", ""]
        lineas += [f"- {n}" for n in p["notas"]]
        lineas += [f"- {'✅' if ok else '❌'} {nombre}: esperado `{esp}`, observado `{obs}`" for ok, nombre, esp, obs in p["checks"]]
        lineas += [""] + [f"![{c}]({c})" for c in p["capturas"]] + [""]
    tipos = {}
    for e in eventos:
        tipos[e["tipo"]] = tipos.get(e["tipo"], 0) + 1
    lineas += ["## Eventos escritos en eventos.jsonl (formato para Wazuh)", ""]
    lineas += [f"- `{t}`: {n}" for t, n in sorted(tipos.items())] or ["- (ninguno)"]
    lineas += ["", "## Comportamientos inesperados", ""]
    fallos = [(p["titulo"], nombre, esp, obs) for p in pasos for ok, nombre, esp, obs in p["checks"] if not ok]
    lineas += [f"- ❌ {t} — {n}: esperado `{e}`, observado `{o}`" for t, n, e, o in fallos]
    # Los 409 de Rojo en el primer y el último paso son intentos deliberados de enviar antes de iniciar / tras finalizar.
    esperado = lambda n, r, e: n in (1, len(pasos)) and r == "rojo" and "409" in e  # noqa: E731
    lineas += [f"- Error de consola ({r}, paso {n}): `{e}`" for n, r, e in errores_js if not esperado(n, r, e)]
    lineas += [f"- (esperado) Error de consola ({r}, paso {n}): `{e}` — es un envío rechazado a propósito (antes de iniciar o tras finalizar)"
               for n, r, e in errores_js if esperado(n, r, e)]
    if not fallos and not [x for x in errores_js if not esperado(*x)]:
        lineas.append("- Ninguno: todas las comprobaciones pasaron y no hubo errores de consola inesperados.")
    (SALIDA / "RESUMEN.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\nResumen: {SALIDA / 'RESUMEN.md'} · {buenos}/{total} comprobaciones")


if __name__ == "__main__":
    raise SystemExit(0 if main(ver="--ver" in sys.argv) else 1)
