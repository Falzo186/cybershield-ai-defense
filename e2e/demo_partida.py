"""Prueba de extremo a extremo: una partida Rojo vs Azul completa, sin intervención humana.

Arranca su propio servidor (puerto libre, BD temporal: no toca data/lab.db ni data/eventos.jsonl) y un Ollama FALSO
(e2e/ollama_falso.py: respuestas fijas, solo para probar el camino de la batalla, no la calidad de un modelo), abre cuatro
navegadores aislados (General, Rojo, Azul, Espectador) con Playwright y recorre la partida guardando capturas en
docs/capturas_demo/ y un resumen con lo observado en docs/capturas_demo/RESUMEN.md.

Ejecutar:  python e2e/demo_partida.py          (requiere: pip install playwright && playwright install chromium)
           python e2e/demo_partida.py --ver    (con el navegador visible)
Sale con código 1 si alguna comprobación falla.
"""
import hashlib
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

import ollama_falso  # mismo directorio

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "capturas_demo"
VIEWPORT = {"width": 1366, "height": 768}
CODIGO_ARBITRO = "246810"  # se fija con CS_CODIGO_ARBITRO para el servidor de la prueba
NOMBRES = {"general": "Juez Demo", "rojo": "Rita Rojo", "azul": "Beto Azul"}

pasos = []       # [{titulo, notas, checks: [(ok, nombre, esperado, observado)], capturas: [archivo]}]
errores_js = []  # (paso, vista, texto) de los errores de consola
provocados = set()  # (paso, vista) donde la prueba provoca a propósito un 409 (acción que el servidor debe rechazar)


def esperado(n, r, e):
    """Error de consola esperado: 409 de Rojo en el primer y el último paso (enviar antes de iniciar / tras finalizar)
    o un 409 provocado a propósito en ese paso y vista."""
    return "409" in e and ((n in (1, len(pasos)) and r == "rojo") or (n, r) in provocados)


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


def abrir_correo(azul, texto, carpeta="entrada"):
    azul.click(f'[data-carpeta="{carpeta}"]')
    azul.locator(".buzon-item", has_text=texto).click()
    azul.wait_for_timeout(250)


def toast(pg):
    return pg.locator("#toast").inner_text() if pg.locator("#toast").is_visible() else ""


def main(ver=False):
    SALIDA.mkdir(parents=True, exist_ok=True)
    for viejo in SALIDA.glob("*.jpg"):
        viejo.unlink()
    proc, base, tmp = arrancar_servidor()
    falso, url_falso = ollama_falso.iniciar(retardo=1.0)  # cada inferencia tarda 1 s: se ven las fases
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
            # Batalla de la partida: cada equipo apunta a su Ollama (aquí, el falso) y Azul fija su defensor IA.
            for pg, lado in ((rojo, "atq"), (azul, "def")):
                pg.fill(f"#host-{lado}", url_falso)
                pg.dispatch_event(f"#host-{lado}", "change")
                pg.click(f'[data-probar="{lado}"]')
                esperar(lambda pg=pg, lado=lado: pg.locator(f"#sel-{lado} option").count() > 1)
            rojo.select_option("#sel-atq", "falso-atacante")
            azul.select_option("#sel-def", "falso-defensor")
            azul.click("#bp-defender")
            t = esperar(lambda: "verificado" in toast(azul) and toast(azul)) or toast(azul)
            chk("Azul fija su defensor IA y el servidor lo comprueba contra su Ollama", True, "verificado" in t)
            chk("todas las vistas ven el defensor de Azul verificado", [True] * 4,
                ["falso-defensor" in pg.inner_text("#bp-defensor") and "verificado" in pg.inner_text("#bp-defensor")
                 for pg in (general, rojo, azul, espectador)])
            chk("solo Rojo ve el formulario de ataque y solo Azul el de defensor", (True, False, False, True),
                (rojo.locator("#bp-rojo").is_visible(), azul.locator("#bp-rojo").is_visible(),
                 rojo.locator("#bp-azul").is_visible(), azul.locator("#bp-azul").is_visible()))
            chk("antes de iniciar, el botón de ataque está desactivado", True, rojo.locator("#bp-lanzar").is_disabled())
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
            chk("durante la partida la práctica queda en pausa (botón desactivado y explicado)", (True, True),
                (rojo.locator("#btn-main").is_disabled(), "pausa" in (rojo.get_attribute("#main-wrap", "title") or "")))
            chk("el marcador de la práctica («BATALLA IA vs IA») se oculta durante la partida", True,
                rojo.locator("#marcador").is_hidden())
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
            paso("3e. Azul verifica el remitente de nómina, inspecciona el enlace y previsualiza el PDF")
            abrir_correo(azul, "nómina")
            azul.locator("#buzon-detalle button", has_text="Verificar remitente").click()
            r = esperar(lambda: azul.locator(".buzon-resultado").inner_text().strip()) or ""
            nota("Verificación: " + r.replace(chr(10), " | "))
            chk("detecta que el remitente IMITA al dominio oficial", True, "IMITA" in r)
            azul.locator("#buzon-detalle button", has_text="Inspeccionar enlace").click()
            r = esperar(lambda: "Destino real" in azul.locator(".buzon-resultado").inner_text()
                        and azul.locator(".buzon-resultado").inner_text()) or ""
            chk("inspeccionar muestra que el enlace no va a donde dice", True, "NO va a donde dice" in r)
            chk("inspeccionar no cuenta como clic (sin «ENLACE CLICADO»)", 0,
                azul.locator(".buzon-item", has_text="nómina").locator(".marca-clic").count())
            descargas = []
            azul.on("download", lambda d: descargas.append(d))
            azul.locator(".buzon-adjunto button", has_text="Previsualizar").click()
            ok = esperar(lambda: azul.locator("#visor-modal").is_visible())
            chk("se abre el visor seguro", True, bool(ok))
            texto_visor = azul.locator("#visor-texto").inner_text()
            meta = azul.locator("#visor-meta").inner_text()
            chk("el visor muestra el texto del propio PDF", True, "Recibo de nomina" in texto_visor)
            sha = hashlib.sha256((RAIZ / "data" / "pdf" / "recibo_nomina.pdf").read_bytes()).hexdigest()
            chk("el visor muestra el SHA-256 real del archivo", True, sha in meta)
            captura(azul, "azul_visor_pdf")
            azul.keyboard.press("Escape")
            chk("Esc cierra el visor", False, azul.locator("#visor-modal").is_visible())
            chk("no se descargó nada al equipo", 0, len(descargas))
            v = esperar(lambda: valores(general)["pdf"] == 1 and valores(general)) or valores(general)
            chk("Rojo gana +5 (PDF abierto sin reportar)", 5, v["rojo"])
            chk("Azul: +5 por verificar el remitente y +10 por el documento = 40", 40, v["azul"])
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
            paso("3f. Carpetas y aislamiento del adjunto")
            azul.click('[data-carpeta="sospechosos"]')
            chk("el correo reportado está en «Sospechosos»", 1,
                azul.locator(".buzon-item", has_text="Acción requerida").count())
            abrir_correo(azul, "nómina")
            azul.locator(".buzon-adjunto button", has_text="Aislar").click()
            t = esperar(lambda: "aislado" in toast(azul) and toast(azul)) or toast(azul)
            nota("Aviso: " + t)
            ok = esperar(lambda: azul.locator(".buzon-adjunto button", has_text="Aislado").count() >= 1)
            chk("tras aislarlo, el adjunto ya no se puede previsualizar", True,
                bool(ok) and azul.locator(".buzon-adjunto button", has_text="Aislado").first.is_disabled())
            v = valores(general)
            chk("aislar no cambia el marcador (Rojo 0, Azul 40)", (0, 40), (v["rojo"], v["azul"]))
            rojo.click('[data-icono="correo"]')  # Rojo vuelve a abrir su aplicación de correo
            ok = esperar(lambda: rojo.locator("#rojo-enviados-lista .marca", has_text="ENLACE CLICADO").count() == 1
                         and rojo.locator("#rojo-enviados-lista .marca", has_text="ADJUNTO ABIERTO").count() == 1)
            chk("Rojo ve en su campaña 1 clic y 1 adjunto abierto (sin saber si se leyó o reportó)", True, bool(ok)
                and "REPORTADO" not in rojo.locator("#rojo-enviados-lista").inner_text())
            captura(rojo, "rojo_seguimiento_campana")

            # ---------------------------------------------------------------------------------------------
            paso("3g. Credencial robada: el empleado entrega su contraseña en la página falsa de soporte")
            abrir_correo(azul, "Acción requerida", "sospechosos")
            with azul.context.expect_page() as nueva:
                azul.locator("#buzon-detalle a[href^='/l/']").click()
            pagina = nueva.value
            pagina.wait_for_load_state()
            chk("la página imita un inicio de sesión sin campos para escribir", (True, 0),
                ("Iniciar sesión" in pagina.content(), pagina.locator("input").count()))
            pagina.locator("button", has_text="Iniciar sesión").click()
            pagina.wait_for_load_state()
            chk("la página explica que la credencial queda comprometida", True, "COMPROMETIDA" in pagina.content())
            captura(pagina, "pagina_falsa_credencial")
            pagina.close()
            v = esperar(lambda: valores(general)["rojo"] == 25 and valores(general)) or valores(general)
            chk("Rojo: +10 por el nuevo clic y +15 por la credencial = 25", 25, v["rojo"])
            chk("riesgo: +15 (clic) +20 (credencial) = 35", 35, v["riesgo"])
            ok = esperar(lambda: "COMPROMETIDA" in toast(azul))
            chk("Azul recibe el aviso de credencial comprometida", True, bool(ok))

            paso("3g'. Batalla de la partida: la IA de Rojo ataca con la credencial robada")
            ok = esperar(lambda: "credencial robada" in rojo.inner_text("#bp-identidad"))
            chk("Rojo ve que su IA atacará como la cuenta robada", True, bool(ok))
            nota("Identidad del atacante: " + rojo.inner_text("#bp-identidad"))
            rojo.select_option("#bp-tecnica", "autoridad")
            rojo.click("#bp-lanzar")
            ok = esperar(lambda: "esperando a la Ollama" in azul.inner_text("#bp-encurso"))
            chk("todas las vistas ven la fase real del ataque (esperando a la Ollama…)", True, bool(ok))
            nota("En curso (Azul): " + azul.inner_text("#bp-encurso").splitlines()[0])
            chk("mientras dura, Rojo no puede lanzar otro", True, rojo.locator("#bp-lanzar").is_disabled())
            captura(rojo, "rojo_ataque_ia_en_curso")
            ok = esperar(lambda: "DATOS EXPUESTOS" in rojo.inner_text("#bp-lista"), timeout=15)
            chk("el defensor atiende una petición válida para esa cuenta: DATOS EXPUESTOS", True, bool(ok))
            item = rojo.locator("#bp-lista .bp-ataque").first.inner_text()
            nota("Ataque #1: " + " · ".join(item.splitlines()[:6]))
            chk("Rojo +10 (datos INTERNA) y la explicación nombra la credencial sin revocar", True,
                "Rojo +10" in item and "credencial" in item and "revocándola" in item)
            chk("tokens de entrada/salida tal como los informa Ollama", True,
                f"{ollama_falso.TOKENS_ENTRADA} entrada / {ollama_falso.TOKENS_SALIDA} salida" in item)
            v = esperar(lambda: valores(general)["rojo"] == 35 and valores(general)) or valores(general)
            chk("marcador de la partida: Rojo 25 + 10 = 35; riesgo 35 + 20 = 55", (35, 55), (v["rojo"], v["riesgo"]))
            ok = esperar(lambda: "Ataque IA #1" in toast(azul))
            chk("Azul recibe el aviso del ataque y su explicación", True, bool(ok))
            captura(rojo, "rojo_ataque_ia_datos_expuestos")

            paso("3h. Azul abre un incidente desde el correo, revoca la credencial y lo resuelve")
            abrir_correo(azul, "Acción requerida", "sospechosos")
            azul.locator("#buzon-detalle button", has_text="Abrir incidente").click()
            esperar(lambda: azul.locator("#azul-incidentes").is_visible())
            esperar(lambda: azul.locator("#inc-correo").input_value() != "")
            chk("el formulario trae el correo ya elegido", True,
                azul.locator("#inc-correo").input_value() != ""
                and "Acción requerida" in azul.locator("#inc-titulo").input_value())
            azul.select_option("#inc-severidad", "critica")
            azul.locator("#incidente-form button[type=submit]").click()
            t = esperar(lambda: "Incidente #" in toast(azul) and toast(azul)) or toast(azul)
            nota("Aviso: " + t)
            chk("abrir el incidente completa su misión", True, "Abrir un incidente de seguridad" in t)
            esperar(lambda: azul.locator("#credencial button", has_text="Revocar").count() == 1)
            chk("la credencial aparece COMPROMETIDA con botón para revocarla", True,
                "COMPROMETIDA" in azul.locator("#credencial").inner_text())
            captura(azul, "azul_incidente_credencial")
            azul.locator("#credencial button", has_text="Revocar").click()
            t = esperar(lambda: "revocada" in toast(azul) and toast(azul)) or toast(azul)
            nota("Aviso: " + t)
            chk("revocar completa su misión (desbloqueada por el incidente)", True, "Revocar una credencial" in t)
            v = esperar(lambda: valores(general)["rojo"] == 20 and valores(general)) or valores(general)
            chk("Rojo pierde los 15 de la credencial (le quedan 10 del clic y 10 de la fuga, que no se recupera)", 20, v["rojo"])
            esperar(lambda: azul.locator("#incidentes-lista button", has_text="Investigar").count() == 1)
            azul.locator("#incidentes-lista button", has_text="Investigar").click()
            esperar(lambda: azul.locator("#incidentes-lista textarea").count() == 1)
            azul.fill("#incidentes-lista textarea", "Credencial revocada; enlace de soporte contenido.")
            provocados.add((len(pasos), "azul"))  # resolver con la amenaza activa: el servidor debe rechazarlo (409)
            azul.locator("#incidentes-lista button", has_text="Resolver").click()
            t = esperar(lambda: "Aún no se puede resolver" in toast(azul) and toast(azul)) or toast(azul)
            nota("Aviso: " + t)
            chk("no deja resolver con el enlace clicado sin contener, y explica por qué", True, "contenido" in t)
            azul.locator('[data-azul="correos"]').click()
            abrir_correo(azul, "Acción requerida", "sospechosos")
            azul.locator("#buzon-detalle button", has_text="Contener").click()
            # No basta con buscar «contenido» en el aviso: el aviso anterior («…aún no está contenido») sigue visible.
            ok = esperar(lambda: valores(general)["contenciones"] == 2)
            chk("el enlace de soporte queda contenido", True, bool(ok))
            azul.locator('[data-azul="incidentes"]').click()
            ok = esperar(lambda: "Para resolverlo falta" not in azul.locator("#incidentes-lista").inner_text())
            chk("la lista ya no muestra nada pendiente para resolver", True, bool(ok))
            chk("el texto de resolución escrito antes se conserva al redibujar", "Credencial revocada; enlace de soporte contenido.",
                azul.locator("#incidentes-lista textarea").input_value())
            azul.locator("#incidentes-lista button", has_text="Resolver").click()
            t = esperar(lambda: "Incidente resuelto" in toast(azul) and toast(azul)) or toast(azul)
            nota("Aviso: " + t)
            chk("resolver el incidente completa su misión", True, "Resolver el incidente" in t)
            v = esperar(lambda: valores(general)["azul"] == 85 and valores(general)) or valores(general)
            chk("marcador: Rojo 10 (la fuga), Azul 85 (40 + 10 incidente + 20 revocar + 15 resolver), riesgo 20",
                (10, 85, 20), (v["rojo"], v["azul"], v["riesgo"]))
            captura(azul, "azul_incidente_resuelto")

            paso("3i. Con la credencial revocada, la IA de Rojo vuelve a atacar como invitado y el defensor lo contiene")
            ok = esperar(lambda: "sin credencial robada" in rojo.inner_text("#bp-identidad"))
            chk("revocar devolvió a Rojo a invitado", True, bool(ok))
            rojo.click("#bp-lanzar")
            ok = esperar(lambda: "CONTENIDO" in rojo.inner_text("#bp-lista"), timeout=15)
            chk("el defensor IA rechaza: CONTENIDO", True, bool(ok))
            item = rojo.locator("#bp-lista .bp-ataque").first.inner_text()
            nota("Ataque #2: " + " · ".join(item.splitlines()[:6]))
            chk("Azul +5 y la propuesta de la IA fue RECHAZAR", True, "Azul +5" in item and "RECHAZAR" in item)
            v = esperar(lambda: valores(general)["azul"] == 90 and valores(general)) or valores(general)
            chk("marcador: Rojo 10, Azul 90", (10, 90), (v["rojo"], v["azul"]))
            chk("el marcador de General resume la batalla IA", True,
                "2 · Rojo +10 / Azul +5" in general.inner_text("#marcador-partida"))
            captura(general, "general_batalla_partida")

            # ---------------------------------------------------------------------------------------------
            paso("4. Verificación: misiones, marcador en General y Espectador")
            azul.click('[data-azul="misiones"]')
            esperar(lambda: azul.locator("#misiones-lista .mision.completada").count() == 7)
            estados = azul.evaluate("""() => [...document.querySelectorAll('#misiones-lista .mision')].map(m =>
                [m.querySelector('b').textContent, m.classList.contains('completada')])""")
            chk("misiones completadas: todas salvo la manual", [True, True, False, True, True, True, True, True],
                [e for _, e in estados])
            evid = azul.locator('#misiones-lista [data-mision="7"] .mision-evidencia').inner_text()
            nota("Evidencia de «Revocar»: " + evid)
            chk("cada misión dice quién la completó y con qué evidencia", True, "por " in evid and "credencial:" in evid)
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
            chk("puntajes finales (Rojo — Azul)", ("10", "90"),
                (general.inner_text("#final-rojo"), general.inner_text("#final-azul")))
            captura(general, "general_resultado")
            ok = esperar(lambda: espectador.locator("#final-modal").is_visible())
            chk("el Espectador también ve el resultado", True, bool(ok))
            captura(espectador, "espectador_resultado")
            provocados.add((len(pasos), "rojo"))  # enviar tras finalizar: el servidor debe rechazarlo (409)
            rojo.click("#btn-correo")
            t = esperar(lambda: "finalizó" in toast(rojo) and toast(rojo)) or toast(rojo)
            chk("tras finalizar, Rojo ya no puede enviar (409)", True, "finalizó" in t)
            captura(rojo, "rojo_tras_finalizar")

            # ---------------------------------------------------------------------------------------------
            paso("6. Resultados con fórmulas y cronología filtrable (guardados en el servidor)")
            general.click("#final-desglose")
            ok = esperar(lambda: general.locator(".inf-equipo.rojo .inf-total").count() == 1)
            chk("desde la pantalla final, General abre el desglose", True, bool(ok))
            leer = lambda: (general.inner_text(".inf-equipo.rojo .inf-total"), general.inner_text(".inf-equipo.azul .inf-total"))  # noqa: E731
            totales = esperar(lambda: leer() == ("10 pts", "90 pts") and leer()) or leer()
            if totales != ("10 pts", "90 pts"):  # diagnóstico: qué devuelve el servidor en ese momento
                nota("API /api/resultados: " + str(general.evaluate(
                    "fetch('/api/resultados').then(r => r.json()).then(d => [d.guardado, d.rojo.total, d.azul.total, d.partida])")))
            chk("los totales del desglose coinciden con el resultado final", ("10 pts", "90 pts"), totales)
            texto = general.inner_text("#inf-equipos")
            chk("cada línea muestra su fórmula (fuga IA, misiones, ataques contenidos)", True,
                "10 × ataques que sacaron datos INTERNA" in texto and "5 × ataques rechazados" in texto
                and "Misión: Reportar un correo sospechoso" in texto)
            chk("el resultado consta como guardado en el servidor", True, "guardado" in general.inner_text("#inf-aviso"))
            nota("Batalla IA en el desglose: " + general.inner_text("#inf-extra").replace(chr(10), " · ")[:300])
            general.wait_for_timeout(400)  # fin de la animación de apertura de la ventana
            captura(general, "general_desglose")
            general.click('[data-inf="cronologia"]')
            ok = esperar(lambda: general.locator("#inf-lista .inf-ev").count() > 10)
            total = general.locator("#inf-lista .inf-ev").count()
            chk("la cronología lista la partida completa", True, bool(ok))
            chk("las pestañas de Resultados no tocan las de la práctica (el botón conserva su texto)",
                "INICIAR SIMULACIÓN", general.inner_text("#btn-main"))
            general.locator("#inf-cats label", has_text="Batalla IA").click()
            ok = esperar(lambda: 0 < general.locator("#inf-lista .inf-ev").count() < total
                         and all("BATALLA IA" in x.upper() for x in general.locator("#inf-lista .cat").all_inner_texts()))
            chk("filtrar por «Batalla IA» deja solo los ataques", True, bool(ok))
            nota("Cronología filtrada: " + " | ".join(general.locator("#inf-lista .inf-ev").all_inner_texts()[:4]).replace(chr(10), " "))
            captura(general, "general_cronologia_filtrada")
            rojo.click('[data-icono="resultados"]')
            ok = esperar(lambda: rojo.locator(".inf-equipo.azul .inf-total").count() == 1)
            chk("tras finalizar, Rojo también ve el desglose", True, bool(ok))
            captura(rojo, "rojo_desglose")
            inesperados = [f"{r}: {e}" for n, r, e in errores_js if not esperado(n, r, e)]
            chk("sin errores de consola inesperados en ninguna vista", [], inesperados)

            nav.close()
    finally:
        proc.terminate()
        falso.shutdown()

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
    lineas += [f"- Error de consola ({r}, paso {n}): `{e}`" for n, r, e in errores_js if not esperado(n, r, e)]
    lineas += [f"- (esperado) Error de consola ({r}, paso {n}): `{e}` — es una acción rechazada a propósito (enviar antes de iniciar o tras finalizar, resolver un incidente con la amenaza activa)"
               for n, r, e in errores_js if esperado(n, r, e)]
    if not fallos and not [x for x in errores_js if not esperado(*x)]:
        lineas.append("- Ninguno: todas las comprobaciones pasaron y no hubo errores de consola inesperados.")
    (SALIDA / "RESUMEN.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\nResumen: {SALIDA / 'RESUMEN.md'} · {buenos}/{total} comprobaciones")


if __name__ == "__main__":
    raise SystemExit(0 if main(ver="--ver" in sys.argv) else 1)
