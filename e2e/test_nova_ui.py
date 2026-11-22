"""E2E de la interfaz Nova (/nova/) con VARIOS navegadores a la vez (administrador, Rojo, dos Azul, espectador) contra el servidor real,
reloj acelerado ×30. Comprueba en pantalla: no autoinicio, sala de espera, correo → enlace → exposición, aprobación de elevación, extracción, victoria
(con descarga), victoria Azul por contención, pausa, IA en modo assist (etiquetada SIMULADO), consola limpia y capturas en docs/capturas_nova/.
Ejecutar: python e2e/test_nova_ui.py [--ver] [--sin-capturas]"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CyberShield_Repair_Library" / "tests" / "regression"))
from playwright.sync_api import sync_playwright  # noqa: E402
from arnes import Entorno  # noqa: E402
import test_combate_ui as B  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "capturas_nova"
R, CONSOLA, RED = [], [], []
MANUAL = {"on": False}      # True cuando la prueba quiere interactuar con el diálogo de solicitudes; si no, se pospone solo para no tapar la pantalla


def chk(n, c, d=""):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n + (f"  [{d}]" if d and not c else ""), flush=True)


def pagina(nav, base, rol, token, nombre, vista=(1366, 768)):
    ctx = nav.new_context(viewport={"width": vista[0], "height": vista[1]}, locale="es-MX")
    if token:
        ctx.add_init_script(f"localStorage.setItem('cs_sesion_{rol}', {json.dumps(token)}); localStorage.setItem('cs_nombre', {json.dumps(nombre)});")
    p = ctx.new_page()
    p.on("dialog", lambda d: d.accept())
    p.on("console", lambda m: CONSOLA.append(m.text) if m.type in ("error", "warning") else None)
    p.on("pageerror", lambda e: CONSOLA.append(str(e)))
    p.on("response", lambda r: RED.append((r.status, r.url)) if r.status >= 400 else None)
    if rol == "azul":
        p.add_locator_handler(p.locator("#dlg-sol[open]"), lambda: None if MANUAL["on"] else p.click("#dlg-luego"), no_wait_after=True)
    p.goto(base + "/nova/")
    return ctx, p


def txt(p, sel):
    return p.inner_text(sel)


def esperar_texto(p, sel, texto, hasta=20000):
    p.wait_for_function("([s, t]) => { const e = document.querySelector(s); return e && e.innerText.includes(t); }", arg=[sel, texto], timeout=hasta)


def main(ver=False, capturas=True):
    if capturas:
        SALIDA.mkdir(parents=True, exist_ok=True)
    with Entorno() as E, sync_playwright() as pw:
        nav = B.lanzar_navegador(pw, ver)
        adm, rojo, a1, a2, esp = E.unirse("Admin", "general"), E.unirse("RojoUno", "rojo"), E.unirse("AzulUno", "azul"), E.unirse("AzulDos", "azul"), E.unirse("Publico", "espectador")
        ctxs = []
        ca, pa = pagina(nav, E.base, "general", adm.token, "Admin"); ctxs.append(ca)
        cr, pr = pagina(nav, E.base, "rojo", rojo.token, "RojoUno"); ctxs.append(cr)
        c1, p1 = pagina(nav, E.base, "azul", a1.token, "AzulUno"); ctxs.append(c1)
        c2, p2 = pagina(nav, E.base, "azul", a2.token, "AzulDos"); ctxs.append(c2)
        for p in (pa, pr, p1, p2):
            p.wait_for_selector("#principal:not([hidden])")
        chk("sin partida todos lo ven y el administrador puede crearla", "No hay partida" in txt(pa, "#banner-estado") and "Esperando" in txt(pr, "#banner-estado") and pa.is_visible("#p-admin") and pr.is_hidden("#p-admin"))
        pa.fill("#c-dur", "900"); pa.fill("#c-esc", "30"); pa.click("#btn-crear")
        esperar_texto(pa, "#chip-estado", "CONFIGURACION")
        time.sleep(2.2)
        chk("la partida creada NO inicia sola: pasan segundos y el reloj sigue en 00:00 en todas las pantallas", all("00:00 /" in txt(p, "#chip-reloj") for p in (pa, pr, p1)))
        pa.click("#b-sala")
        for p in (pr, p1, p2):
            esperar_texto(p, "#chip-estado", "SALA DE ESPERA")
        for p in (pr, p1, p2):
            p.click("#b-unirse")
        esperar_texto(pa, "#n-part", "3")
        for p in (pr, p1, p2):
            p.wait_for_selector("#b-listo:not([hidden])")
            p.click("#b-listo")
        esperar_texto(pa, "#lista-part", "EMP-02")
        chk("la sala muestra a los 3 jugadores con su equipo, su identidad (Azul: EMP-01 y EMP-02) y si están listos", all(t in txt(pa, "#lista-part") for t in ("RojoUno", "AzulUno", "EMP-01", "EMP-02", "listo")))
        chk("el Rojo no ve el panel del administrador ni el Azul el panel Rojo (cada rol su interfaz)", pr.is_hidden("#p-admin") and p1.is_hidden("#p-rojo-op") and p1.is_visible("#p-azul-bandeja") and pr.is_hidden("#p-azul-bandeja"))
        chk("el administrador ve el catálogo de 6 identidades con la credencial enmascarada y puede mostrarla; el Rojo y el Azul no tienen ese panel",
            pa.locator("#catalogo .cat").count() == 6 and "***" in txt(pa, "#catalogo") and pr.is_hidden("#p-catalogo") and p1.is_hidden("#p-catalogo"))
        pa.click("#b-mostrar")
        chk("«Mostrar valores» revela las credenciales (formato 5 dígitos + letra) y EMP-04 es la débil", "***" not in txt(pa, "#catalogo") and "12345A" in txt(pa, "#catalogo") and "débil" in txt(pa, "#catalogo"))
        pa.click("#b-mostrar")
        pa.locator("#lista-part .part", has_text="AzulDos").locator("select").select_option("EMP-06")
        esperar_texto(pa, "#lista-part", "EMP-06")
        esperar_texto(p2, "#az-ident", "EMP-06")
        chk("el administrador reasigna la identidad de un Azul en la sala y el jugador la ve en su tarjeta «Mi identidad»", "Miguel Ortega" in txt(p2, "#az-ident"))
        pa.locator("#lista-part .part", has_text="AzulDos").locator("select").select_option("EMP-02")
        esperar_texto(pa, "#lista-part", "EMP-02")
        if capturas:
            pa.screenshot(path=str(SALIDA / "01_admin_sala_1366x768.png"))
        chk("el botón «Iniciar» está desactivado hasta que el administrador marque LISTA", pa.is_disabled("#b-iniciar"))
        pa.click("#b-lista")
        esperar_texto(pa, "#chip-estado", "LISTA")
        chk("en LISTA el reloj sigue parado y solo entonces se habilita Iniciar", pa.is_enabled("#b-iniciar") and "00:00 /" in txt(pa, "#chip-reloj"))
        pa.click("#b-iniciar")
        for p in (pa, pr, p1, p2):
            esperar_texto(p, "#chip-estado", "EN CURSO")
        chk("el administrador inicia (con confirmación): todos pasan a EN CURSO y el reloj corre", "EN CURSO" in txt(pr, "#chip-estado"))
        esperar_texto(p1, "#az-correos", "Recordatorio")
        chk("llega un correo programado del escenario a la bandeja de Azul sin intervención del Rojo (con contador de no leídos)", "sin leer" in txt(p1, "#n-nl") and "escenario" in txt(p1, "#az-correos"))
        chk("el otro Azul no ve el correo de la bandeja de su compañero: cada identidad tiene la suya", "Recordatorio" not in txt(p2, "#az-correos"))
        # Rojo envía un correo malicioso a EMP-01 (el jugador Azul 1)
        pr.select_option("#op-accion", "send_email"); pr.select_option("#op-ident", "EMP-01"); pr.select_option("#op-plant", "aviso_soporte"); pr.fill("#op-cuerpo", "Soporte TI: confirma tu identidad.")
        pr.click("#form-op button[type=submit]")
        esperar_texto(pr, "#op-resultado", "aceptada")
        esperar_texto(p1, "#az-correos", "Soporte TI")
        chk("el correo del Rojo llega a la bandeja del jugador Azul correcto", "Soporte TI" in txt(p1, "#az-correos") and "Soporte TI" not in txt(p2, "#az-correos"))
        c_soporte = p1.locator(".corr", has_text="Soporte TI").first
        c_soporte.locator("button", has_text="Abrir").click()
        p1.wait_for_timeout(500)
        c_soporte = p1.locator(".corr", has_text="Soporte TI").first
        c_soporte.locator("button", has_text="Ver enlace").click()
        p1.wait_for_timeout(500)
        chk("abrir el correo y ver el enlace NO compromete: la credencial de EMP-01 sigue PROTEGIDA y el Rojo no la tiene", "PROTEGIDA" in txt(p1, "#az-estado") and "Credencial válida descubierta" not in txt(pr, "#creds"))
        p1.locator(".corr", has_text="Soporte TI").first.locator("button", has_text="Pulsar enlace").click()
        esperar_texto(p1, "#az-estado", "COMPROMETIDA")
        chk("tras pulsar el enlace y completar la acción de riesgo (confirmando la página interna sin campo de contraseña) la credencial queda COMPROMETIDA", "COMPROMETIDA" in txt(p1, "#az-estado"))
        esperar_texto(pr, "#creds", "Credencial válida descubierta")
        chk("el panel «Credenciales y accesos descubiertos» del Rojo desbloquea EMP-01 (enmascarada) automáticamente", "Credencial válida descubierta" in txt(pr, "#creds") and "***" in txt(pr, "#creds"))
        esperar_texto(p1, "#az-inc", "INC-001")
        chk("Azul recibe alertas y un incidente por la exposición", "Credencial expuesta" in txt(p1, "#az-alertas") and "INC-001" in txt(p1, "#az-inc"))
        if capturas:
            p1.screenshot(path=str(SALIDA / "02_azul_incidente_1366x768.png"))
            pr.screenshot(path=str(SALIDA / "03_rojo_credencial_desbloqueada_1366x768.png"))
        p1.locator("#az-ident-acc button", has_text="Revocar EMP-01").click()
        esperar_texto(pr, "#creds", "Bloqueada")
        chk("al revocar, el Rojo ve la identidad BLOQUEADA y no puede usarla", "Bloqueada" in txt(pr, "#creds"))
        p1.locator("#az-inc button", has_text="Contener incidente").click()
        for p in (pa, pr, p1, esp_p := None):
            if p is None:
                continue
            esperar_texto(p, "#v-titulo", "Victoria del Equipo Azul", 25000)
        chk("VICTORIA AZUL por contención (credenciales revocadas, incidente contenido, continuidad ≥ 0,6): la pantalla de victoria aparece en todas las vistas", all("Azul" in txt(p, "#v-titulo") for p in (pa, pr, p1)))
        if capturas:
            pa.screenshot(path=str(SALIDA / "04_victoria_azul_1366x768.png"))
        # ── segunda partida: victoria del Rojo con aprobación humana y descarga ───────────────────────────
        pa.fill("#c-dur", "900"); pa.fill("#c-esc", "30"); pa.click("#btn-crear")
        esperar_texto(pa, "#chip-estado", "CONFIGURACION")
        pa.click("#b-sala")
        for p in (pr, p1):
            esperar_texto(p, "#chip-estado", "SALA DE ESPERA")
            p.click("#b-unirse")
        esperar_texto(pa, "#n-part", "2")
        pa.click("#b-lista")
        esperar_texto(pa, "#chip-estado", "LISTA")
        pa.click("#b-iniciar")
        esperar_texto(pr, "#chip-estado", "EN CURSO")
        pr.select_option("#op-accion", "request_elevation"); pr.fill("#op-cuerpo", "Soy de soporte TI y necesito una copia completa para el mantenimiento")
        pr.click("#form-op button[type=submit]")
        esperar_texto(p1, "#az-aprob", "db_export")
        chk("la solicitud de elevación del Rojo llega a la bandeja de Azul con riesgo ALTO y recomendación etiquetada «reglas, no IA»", "ALTO" in txt(p1, "#az-aprob") and "reglas, no IA" in txt(p1, "#az-aprob"))
        pr.select_option("#op-accion", "export_database"); pr.click("#form-op button[type=submit]")
        esperar_texto(pr, "#op-resultado", "Rechazada")
        chk("sin aprobación la exportación completa la rechaza el motor (PERMISSION_DENIED)", "PERMISSION_DENIED" in txt(pr, "#op-resultado"))
        MANUAL["on"] = True
        p1.wait_for_selector("#dlg-sol[open]")
        chk("a todos los Azules les aparece un cuadro con la solicitud: qué pide, quién, hora y recomendación", all(k.upper() in txt(p1, "#dlg-detalle").upper() for k in ("Qué pide", "Quién lo pide", "Hora real", "Riesgo")) and "ALTO" in txt(p1, "#dlg-detalle"))
        p1.click("#dlg-ok")
        MANUAL["on"] = False
        esperar_texto(pr, "#elev-rojo", "APROBADA")
        chk("Azul aprueba y el Rojo ve la solicitud APROBADA (la decisión cambia el estado del escenario)", "APROBADA" in txt(pr, "#elev-rojo"))
        pr.select_option("#op-accion", "export_database"); pr.click("#form-op button[type=submit]")
        for p in (pa, pr, p1):
            esperar_texto(p, "#v-titulo", "Victoria del Equipo Rojo", 25000)
        chk("el Rojo copia la base completa y gana por el motor: pantalla de victoria roja con las 8 tablas", "Rojo" in txt(pr, "#v-titulo") and "Tablas extraídas: 8" in txt(pr, "#v-datos"))
        chk("la pantalla de victoria ofrece descargar CSV, JSON y SQL (Rojo y administrador) pero no al Azul", pr.locator("#v-descargas button").count() == 3 and p1.locator("#v-descargas button").count() == 0)
        with pr.expect_download() as d:
            pr.locator("#v-descargas button", has_text="JSON").click()
        chk("la descarga trae los datos reales extraídos", len(json.loads(Path(d.value.path()).read_text(encoding="utf-8"))) == 8)
        if capturas:
            pr.screenshot(path=str(SALIDA / "05_victoria_roja_descarga_1366x768.png"))
        # ── tercera partida: pausa + IA assist ───────────────────────────────────────────────────────────
        pa.fill("#c-dur", "900"); pa.fill("#c-esc", "30"); pa.click("#btn-crear")
        esperar_texto(pa, "#chip-estado", "CONFIGURACION")
        pa.click("#b-sala")
        for p in (pr, p1):
            esperar_texto(p, "#chip-estado", "SALA DE ESPERA")
            p.click("#b-unirse")
        esperar_texto(pa, "#n-part", "2")
        pa.select_option("#ia-rojo-modo", "assist"); pa.select_option("#ia-azul-modo", "off"); pa.click("#b-ia")
        esperar_texto(pa, "#ia-estado", "SIMULADO")
        pa.click("#b-lista"); esperar_texto(pa, "#chip-estado", "LISTA"); pa.click("#b-iniciar"); esperar_texto(pr, "#chip-estado", "EN CURSO")
        pa.click("#b-pausar")
        for p in (pa, pr, p1):
            esperar_texto(p, "#chip-estado", "PAUSADA")
        t1 = txt(pr, "#chip-reloj"); time.sleep(1.6)
        chk("PAUSADA se ve en todas las pantallas, el reloj no avanza y el banner lo explica", t1 == txt(pr, "#chip-reloj") and "PAUSADA" in txt(pr, "#banner-estado"))
        pr.select_option("#op-accion", "scan_directory"); pr.click("#form-op button[type=submit]")
        esperar_texto(pr, "#op-resultado", "Rechazada")
        chk("durante la pausa el motor rechaza la acción con un mensaje claro", "no está en curso" in txt(pr, "#op-resultado"))
        pa.click("#b-reanudar")
        esperar_texto(pr, "#chip-estado", "EN CURSO")
        pr.wait_for_selector("#ia-rojo:not([hidden])")
        pr.fill("#m-texto", "Probemos primero el reconocimiento"); pr.press("#m-texto", "Enter")
        esperar_texto(pr, "#msgs", "reconocimiento")
        p1.fill("#t-titulo", "Revisar la bandeja"); p1.click("#form-tarea button")
        esperar_texto(p1, "#tareas", "TK-001")
        p1.locator("#tareas button", has_text="Pasar a EN PROGRESO").click()
        esperar_texto(p1, "#tareas", "EN_PROGRESO")
        chk("mensajería y tareas: el mensaje del Rojo no aparece en el Azul y la tarea avanza por su máquina de estados", "reconocimiento" not in txt(p1, "#msgs") and "EN_PROGRESO" in txt(p1, "#tareas"))
        chk("las misiones de cada equipo se derivan del estado real (el Rojo parte con misiones disponibles, el Azul también)", "Identificar identidades" in txt(pr, "#misiones") and "Reportar un correo" in txt(p1, "#misiones") and "COMPLETADA" not in txt(pr, "#misiones"))
        esperar_texto(pr, "#op-restantes-rojo", "10 DE 10")
        chk("la IA espera: antes de que el jugador arme y lance el prompt no hay propuesta y quedan las 10 oportunidades", txt(pr, "#prop-rojo") == "" and "10 DE 10" in txt(pr, "#op-restantes-rojo"))
        opts = pr.eval_on_selector_all("#d-cred option", "els => els.map(e => e.value)")
        chk("el combo de credencial ofrece «sin credencial» y «aleatoria», y NO ofrece ninguna credencial obtenida mientras el Rojo no tenga una", "aleatoria" in opts and "ninguna" in opts and not any(o.startswith("conocida:") for o in opts))
        pr.select_option("#d-cred", "aleatoria"); pr.wait_for_selector("#d-estruct:not([hidden])")
        chk("al elegir credencial aleatoria aparece la estructura (dígitos iniciales y letra)", pr.is_visible("#d-dig") and pr.is_visible("#d-letra"))
        pr.select_option("#d-cred", "ninguna")
        pr.select_option("#d-accion", "scan_directory"); pr.select_option("#d-obj", "info_administrativa")
        pr.click("#b-prop-rojo")
        esperar_texto(pr, "#prop-rojo", "SIMULADO – no es una IA")
        esperar_texto(pr, "#op-restantes-rojo", "9 DE 10")
        chk("lanzar el prompt gasta una oportunidad (9 de 10)", "9 DE 10" in txt(pr, "#op-restantes-rojo"))
        chk("assist: la IA propone con la etiqueta «SIMULADO – no es una IA» y NO ejecuta hasta que el humano confirme", "Confirmar y ejecutar" in txt(pr, "#prop-rojo") and "IDENTIFICADA" not in txt(pr, "#creds"))
        pr.click("#prop-rojo button:has-text('Confirmar y ejecutar')")
        esperar_texto(pr, "#creds", "Identificada")
        chk("al confirmar, el motor ejecuta la propuesta por su pipeline (identidades identificadas en el panel)", "Identificada" in txt(pr, "#creds"))
        pa.click("#b-detener")
        esperar_texto(pa, "#chip-estado", "FINALIZADA")
        # espectador
        ce, pe = pagina(nav, E.base, "espectador", None, None); ctxs.append(ce)
        pe.wait_for_selector("#entrar:not([hidden])")
        pe.select_option("#e-rol", "espectador"); pe.click("#form-entrar button[type=submit]")
        pe.wait_for_selector("#principal:not([hidden])")
        esperar_texto(pe, "#pub", "Tablas extraídas")
        chk("el espectador observa el estado público sin controles de equipo ni credenciales", pe.is_hidden("#p-admin") and pe.is_hidden("#p-rojo-cred") and pe.is_hidden("#p-azul-bandeja") and "Creden" not in txt(pe, "#pub"))
        if capturas:
            pe.screenshot(path=str(SALIDA / "06_espectador_1366x768.png"))
        c3, p3 = pagina(nav, E.base, "general", adm.token, "Admin", (1920, 1080)); ctxs.append(c3)
        p3.wait_for_selector("#principal:not([hidden])")
        if capturas:
            p3.screenshot(path=str(SALIDA / "07_admin_1920x1080.png"))
        for c in ctxs:
            c.close()
        nav.close()
        inesperada = [m for m in CONSOLA if "40" not in m and "429" not in m and "409" not in m]
        chk("consola sin errores ni warnings (salvo los 4xx esperados de acciones rechazadas por el motor)", not inesperada, str(inesperada[:3]))
    print(f"\nTotal {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(0 if main("--ver" in sys.argv, "--sin-capturas" not in sys.argv) else 1)
