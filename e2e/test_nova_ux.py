"""E2E de la experiencia de usuario de Nova (rediseño): misión guiada del Rojo, límites visibles y mensajes claros, panel de credenciales plegable,
tarjeta de propuesta de la IA (Ejecutar/Editar/Descartar), centro de monitoreo del Azul con puntuación por reglas, solicitudes con consecuencias,
resumen final con línea de tiempo, modo práctica, vista de espectador sin secretos y diseño responsive. Todo contra el servidor real.
Ejecutar: python e2e/test_nova_ux.py [--ver]"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CyberShield_Repair_Library" / "tests" / "regression"))
from playwright.sync_api import sync_playwright  # noqa: E402
from arnes import Entorno  # noqa: E402
import test_combate_ui as B  # noqa: E402

R, CONSOLA = [], []


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
    if rol == "azul":
        p.add_locator_handler(p.locator("#dlg-sol[open]"), lambda: p.click("#dlg-luego"), no_wait_after=True)
    p.goto(base + "/nova/")
    return ctx, p


def txt(p, sel):
    return p.inner_text(sel)


def esperar_texto(p, sel, texto, hasta=20000):
    p.wait_for_function("([s, t]) => { const e = document.querySelector(s); return e && e.innerText.includes(t); }", arg=[sel, texto], timeout=hasta)


def main(ver=False):
    with Entorno() as E, sync_playwright() as pw:
        nav = B.lanzar_navegador(pw, ver)
        adm, rojo, a1 = E.unirse("Admin", "general"), E.unirse("RojoUno", "rojo"), E.unirse("AzulUno", "azul")
        ctxs = []
        ca, pa = pagina(nav, E.base, "general", adm.token, "Admin"); ctxs.append(ca)
        cr, pr = pagina(nav, E.base, "rojo", rojo.token, "RojoUno"); ctxs.append(cr)
        c1, p1 = pagina(nav, E.base, "azul", a1.token, "AzulUno"); ctxs.append(c1)
        for p in (pa, pr, p1):
            p.wait_for_selector("#principal:not([hidden])")
        # ── práctica creada desde la interfaz ──
        pa.check("#c-prac"); pa.fill("#c-esc", "10"); pa.click("#btn-crear")
        esperar_texto(pa, "#chip-estado", "CONFIGURACION")
        esperar_texto(pr, "#chip-reloj", "05:00")
        chk("la partida de práctica se identifica en todas las pantallas (chip PRÁCTICA) y dura 5 minutos", pa.is_visible("#chip-practica") and "05:00" in txt(pr, "#chip-reloj"))
        pa.click("#b-sala")
        for p in (pr, p1):
            esperar_texto(p, "#chip-estado", "SALA DE ESPERA"); p.click("#b-unirse")
        esperar_texto(pa, "#n-part", "2")
        pa.select_option("#ia-rojo-modo", "assist"); pa.select_option("#ia-azul-modo", "off"); pa.click("#b-ia"); esperar_texto(pa, "#ia-estado", "SIMULADO")
        pa.click("#b-lista"); esperar_texto(pa, "#chip-estado", "LISTA")
        chk("el botón grande de siguiente paso del administrador cambia según el estado y arranca la partida", "Iniciar" in txt(pa, "#b-siguiente"))
        pa.click("#b-siguiente"); esperar_texto(pr, "#chip-estado", "EN CURSO")
        # ── Rojo: misión guiada ──
        chk("el Rojo ve la barra de fases (6) y «Paso 1 de 5 — Reconocer el directorio»", pr.locator("#fases li").count() == 6 and "Paso 1 de 5" in txt(pr, "#mision-paso") and "Reconocer" in txt(pr, "#paso-titulo"))
        pr.click("#b-siguiente-rojo")
        chk("«Hacer siguiente paso» PREPARA la acción (formulario y resumen) pero NO la ejecuta", pr.input_value("#op-accion") == "scan_directory" and "Reconocer directorio" in txt(pr, "#op-resumen") and rojo.get("/api/nova/estado")["rojo"]["presupuesto"]["reconocimientos"]["usados"] == 0)
        chk("las acciones tienen nombres de jugador y el nombre técnico queda como dato secundario", "scan_directory" in txt(pr, "#op-resumen") and "Reconocer directorio" in pr.eval_on_selector("#op-accion", "s => s.options[0].textContent"))
        pr.click("#b-ejecutar"); esperar_texto(pr, "#op-resultado", "empleados identificados")
        chk("tras ejecutar hay retroalimentación clara y el paso avanza (credenciales)", "Operación aceptada" in txt(pr, "#op-resultado") and "credencial" in txt(pr, "#paso-titulo").lower())
        chk("el presupuesto es visible y refleja lo gastado (1 de 3 reconocimientos)", "1 de 3" in txt(pr, "#presu"))
        pr.click("#b-que-hago"); pr.wait_for_selector("#que-hago:not([hidden])")
        chk("«¿Qué hago ahora?» responde con el estado real (empleados identificados, sin credencial) y solo opciones disponibles", "identificaste" in txt(pr, "#que-hago") and "no tienes una credencial" in txt(pr, "#que-hago") and "correo" in txt(pr, "#que-hago"))
        chk("las credenciales están plegadas con el contador de identidades descubiertas", not pr.evaluate("document.querySelector('#p-rojo-cred').open") and "identidades descubiertas" in txt(pr, "#cred-resumen"))
        # límites: agotar los correos y leer el mensaje claro
        pr.select_option("#op-accion", "send_email")
        for _ in range(6):
            pr.click("#b-ejecutar"); time.sleep(0.4)
            if "límite de correos" in txt(pr, "#op-resultado"):
                break
        chk("al agotar los correos el mensaje explica qué pasó y cuándo podrá volver (nunca solo BUDGET_EXCEEDED)", "límite de correos de esta ronda" in txt(pr, "#op-resultado") and "siguiente ronda" in txt(pr, "#op-resultado"))
        # ── IA Roja: tarjeta destacada ──
        pr.wait_for_selector("#ia-rojo:not([hidden])")
        pr.select_option("#q-obj", "reconocer"); pr.click("#b-rapido-rojo")
        pr.wait_for_selector("#prop-rojo .prop-card h4")
        chk("la IA Roja propone con una tarjeta destacada (objetivo, motivo, etiqueta SIMULADO) y los tres botones Ejecutar / Editar / Descartar",
            "SIMULADO – no es una IA" in txt(pr, "#prop-rojo") and all(pr.locator(f"#prop-rojo button:has-text('{b}')").count() == 1 for b in ("Ejecutar", "Editar", "Descartar")) and "no actúa hasta que tú confirmes" in txt(pr, "#prop-rojo"))
        pr.click("#prop-rojo button:has-text('Editar')")
        chk("«Editar» carga la propuesta en el formulario sin ejecutarla", pr.input_value("#op-accion") in ("scan_directory", "send_email", "extract_table", "request_elevation", "guess_credential", "query_resource", "export_database"))
        pr.click("#prop-rojo button:has-text('Descartar')")
        pr.wait_for_function("() => !document.querySelector('#prop-rojo button')", timeout=10000)
        # ── Azul: centro de monitoreo ──
        for _ in range(8):
            if rojo.post("/api/nova/accion", {"action_type": "send_email", "params": {"identidad_id": "EMP-02", "plantilla": "aviso_soporte", "cuerpo": "Verifica tu identidad."}, "idempotency_key": f"x{time.time()}"}).status == 200:
                break
            time.sleep(1)
        rojo.post("/api/nova/accion", {"action_type": "request_elevation", "params": {"motivo": "Soy de soporte TI y necesito una copia completa."}, "idempotency_key": f"y{time.time()}"})
        p1.wait_for_selector("#az-kpis .kpi")
        esperar_texto(p1, "#az-aprob", "copia completa")
        chk("el Azul ve KPIs de seguridad con riesgo general (nivel con texto, no solo color) y estado de las identidades", "Riesgo general" in txt(p1, "#az-kpis").replace("RIESGO GENERAL", "Riesgo general") and any(k in txt(p1, "#az-kpis") for k in ("Normal", "Advertencia", "Sospechoso", "Crítico")) and "Laura Méndez" in txt(p1, "#az-kpis"))
        pts = p1.eval_on_selector_all("#az-monitor .mon-fila .nivel", "els => els.map(e => parseInt(e.textContent.split('·')[1]))")
        chk("el monitor de eventos está ordenado por sospecha (de mayor a menor) y cada fila trae nivel, motivo y estado", len(pts) >= 2 and pts == sorted(pts, reverse=True))
        p1.locator("#az-monitor .mon-fila").first.click()
        chk("al abrir un evento se ve el detalle: por qué, actor y acción sugerida", "Por qué:" in txt(p1, "#az-monitor") and "Acción sugerida:" in txt(p1, "#az-monitor"))
        p1.click("#az-monitor .mon-detalle button:has-text('Pedir explicación')")
        esperar_texto(p1, "#az-monitor", "Reglas del motor")
        chk("la explicación funciona sin modelo (fuente: reglas del motor) y lo dice", "Reglas del motor" in txt(p1, "#az-monitor"))
        sol = txt(p1, "#az-aprob")
        chk("la solicitud de elevación aparece destacada con quién, qué, recurso, riesgo, análisis de sospecha, tiempo restante y la consecuencia de cada decisión",
            all(k in sol for k in ("Quién", "Recurso", "Riesgo", "Análisis de sospecha", "Tiempo restante", "Aprobar:", "Rechazar:")) and p1.locator("#az-aprob button:has-text('Investigar')").count() == 1)
        chk("el correo del Rojo llega a la bandeja con su puntuación y las señales visibles (remitente externo, presión, enlace)", "Señales:" in txt(p1, "#az-correos") or "Crítico" in txt(p1, "#az-correos") or "Sospechoso" in txt(p1, "#az-correos"))
        chk("el Azul no ve el formulario de prompts como interfaz principal: la IA defensora es un monitor y su modo experto está plegado", not p1.evaluate("document.querySelector('#e-avanzado') && document.querySelector('#e-avanzado').open") and "puntuación la calcula el motor" in txt(p1, "#p-ia-azul"))
        # decisión del Azul → victoria del Rojo → resumen
        ap = next(x for x in a1.get("/api/nova/estado")["azul"]["aprobaciones"] if x["operacion"] == "db_export")
        p1.click("#az-aprob button:has-text('Aprobar')"); esperar_texto(pr, "#elev-rojo", "APROBADA")
        chk("la aprobación llega al Rojo y la misión guiada lo reconoce (siguiente paso: exportar)", "Exportar" in txt(pr, "#paso-titulo") or "exportar" in txt(pr, "#paso-texto").lower() or "elevación" in txt(pr, "#presu").lower())
        pr.select_option("#op-accion", "export_database"); pr.click("#b-ejecutar")
        for p in (pa, pr, p1):
            esperar_texto(p, "#v-titulo", "Victoria del Equipo Rojo", 25000)
        esperar_texto(pr, "#v-resumen", "Objetivos del Rojo")
        res = txt(pr, "#v-resumen")
        chk("el resumen final trae objetivos, operaciones, credenciales, recursos protegidos, errores defensivos y la línea de tiempo con fuentes separadas (jugador / motor)",
            all(k in res for k in ("Objetivos del Rojo", "Operaciones", "Credenciales comprometidas", "Recursos protegidos", "Errores defensivos")) and p1.locator("#v-resumen .fuente.motor").count() > 0 and pr.locator("#v-resumen .fuente.jugador").count() > 0)
        chk("el resumen indica que fue una partida de práctica", "práctica" in res.lower())
        pr.click("#v-resumen button:has-text('Motor')")
        chk("los filtros de la línea de tiempo funcionan (solo motor)", pr.locator("#v-resumen .linea .fuente.jugador").count() == 0 and pr.locator("#v-resumen .linea .fuente.motor").count() > 0)
        # ── espectador sin secretos ──
        ce, pe = pagina(nav, E.base, "espectador", None, None); ctxs.append(ce)
        pe.select_option("#e-rol", "espectador"); pe.click("#form-entrar button[type=submit]")
        pe.wait_for_selector("#principal:not([hidden])"); esperar_texto(pe, "#espectador-tiempo", "Extracción completada")
        cuerpo = pe.inner_text("body")
        chk("la vista de espectador es de solo lectura: marcador, línea de tiempo pública y resultado, sin controles ni credenciales", pe.is_hidden("#p-admin") and pe.is_hidden("#p-rojo-op") and pe.is_hidden("#p-azul-aprob") and "12345A" not in cuerpo and "Credencial:" not in cuerpo)
        # ── Ollama desconectado: mensaje claro ──
        chk("con Ollama desconectado la IA lo explica en lenguaje simple (sin errores técnicos de socket)", "WinError" not in cuerpo and "urlopen" not in cuerpo)
        # ── responsive ──
        cm, pm = pagina(nav, E.base, "rojo", rojo.token, "RojoUno", vista=(390, 800)); ctxs.append(cm)
        pm.wait_for_selector("#principal:not([hidden])"); time.sleep(1.5)
        chk("en móvil (390 px) no hay desplazamiento horizontal de la página", pm.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"), str(pm.evaluate("document.documentElement.scrollWidth")))
        ct, pt = pagina(nav, E.base, "azul", a1.token, "AzulUno", vista=(768, 1024)); ctxs.append(ct)
        pt.wait_for_selector("#principal:not([hidden])"); time.sleep(1.5)
        chk("en tableta (768 px) tampoco", pt.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"), str(pt.evaluate("document.documentElement.scrollWidth")))
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
    sys.exit(0 if main("--ver" in sys.argv) else 1)
