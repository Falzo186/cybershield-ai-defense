"""E2E multijugador de Nova: 2 Rojos y 4 Azules (+ administrador) en navegadores distintos contra el servidor real.
Comprueba: lista lateral de jugadores por equipo, un Rojo que NO es el primero dirige una operación, y una solicitud misteriosa llega como cuadro
a los 4 Azules; opinan, decide la mayoría y la consecuencia cambia el estado. Ejecutar: python e2e/test_nova_multijugador_ui.py [--ver]"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CyberShield_Repair_Library" / "tests" / "regression"))
from playwright.sync_api import sync_playwright  # noqa: E402
from arnes import Entorno  # noqa: E402
import test_combate_ui as B  # noqa: E402
import test_nova_ui as T  # noqa: E402
from test_nova_ui import chk, esperar_texto, pagina, txt  # noqa: E402

AZULES = ["AzulUno", "AzulDos", "AzulTres", "AzulCuatro"]


def main(ver=False):
    with Entorno() as E, sync_playwright() as pw:
        nav = B.lanzar_navegador(pw, ver)
        adm = E.unirse("Admin", "general")
        rojos = [E.unirse("RojoUno", "rojo"), E.unirse("RojoDos", "rojo")]
        azules = [E.unirse(n, "azul") for n in AZULES]
        ctxs = []
        ca, pa = pagina(nav, E.base, "general", adm.token, "Admin", (1280, 720)); ctxs.append(ca)
        pr = []
        for n, c in zip(("RojoUno", "RojoDos"), rojos):
            cx, p = pagina(nav, E.base, "rojo", c.token, n, (1280, 720)); ctxs.append(cx); pr.append(p)
        pz = []
        for n, c in zip(AZULES, azules):
            cx, p = pagina(nav, E.base, "azul", c.token, n, (1280, 720)); ctxs.append(cx); pz.append(p)
        for p in [pa, *pr, *pz]:
            p.wait_for_selector("#principal:not([hidden])")
        cr = adm.post("/api/nova/partida", {"duration_s": 900, "time_scale": 5, "approval_window_s": 60, "guess_cooldown_s": 0, "guess_attempts_per_round": 9, "detect_prob_fail": 0.0})
        chk("la partida se crea con autorizaciones por votación", cr.status == 200 and cr["config"]["approval_mode"] == "votacion")
        adm.post("/api/nova/sala")
        for p in [*pr, *pz]:
            esperar_texto(p, "#chip-estado", "SALA DE ESPERA")
            p.click("#b-unirse")
        esperar_texto(pa, "#n-part", "6")
        chk("caben 2 Rojos y 4 Azules, cada Azul con su identidad", all(f"EMP-0{i}" in txt(pa, "#lista-part") for i in (1, 2, 3, 4)))
        pr[1].click("#b-jug")
        pr[1].wait_for_selector("#panel-jug:not([hidden])")
        esperar_texto(pr[1], "#jug-azul", "AzulCuatro")
        chk("el panel de jugadores lista solo nombres por equipo: el Rojo 2 ve a los 2 Rojos y a los 4 Azules, sin identidades", "RojoUno" in txt(pr[1], "#jug-rojo") and "RojoDos" in txt(pr[1], "#jug-rojo")
            and all(n in txt(pr[1], "#jug-azul") for n in AZULES) and "EMP-" not in txt(pr[1], "#panel-jug") and "2" in txt(pr[1], "#jug-n-rojo") and "4" in txt(pr[1], "#jug-n-azul"))
        chk("el panel marca con un punto verde a los 6 jugadores conectados", pr[1].locator("#panel-jug .punto.on").count() == 6)
        pz[0].click("#b-jug")
        chk("el Azul también ve la lista de ambos equipos y puede cerrarla", "RojoDos" in txt(pz[0], "#jug-rojo") and pz[0].is_visible("#panel-jug"))
        pz[0].click("#b-jug-cerrar")
        chk("cerrar el panel lo oculta", pz[0].is_hidden("#panel-jug"))
        adm.post("/api/nova/lista")
        adm.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "mj-1"})
        for p in [pa, *pr, *pz]:
            esperar_texto(p, "#chip-estado", "EN CURSO")
        # el segundo Rojo (no el primero) dirige una operación
        pr[1].select_option("#op-accion", "send_email"); pr[1].select_option("#op-ident", "EMP-02"); pr[1].select_option("#op-plant", "aviso_soporte"); pr[1].fill("#op-cuerpo", "Soporte TI")
        pr[1].click("#form-op button[type=submit]")
        esperar_texto(pr[1], "#op-resultado", "aceptada")
        esperar_texto(pz[1], "#az-correos", "Soporte TI")
        chk("un Rojo que no es el primero dirige un ataque y el correo llega al Azul correcto (EMP-02)", "Soporte TI" in txt(pz[1], "#az-correos") and "Soporte TI" not in txt(pz[0], "#az-correos"))
        # intento casi correcto del Rojo 2 → solicitud misteriosa a los 4 Azules
        T.MANUAL["on"] = True
        real = next(x["credencial"] for x in adm.get("/api/nova/estado")["catalogo"] if x["id"] == "EMP-03")
        cerca = real[:4] + ("0" if real[4] != "0" else "1") + ("A" if real[5] != "A" else "B")
        g = rojos[1].post("/api/nova/accion", {"action_type": "guess_credential", "params": {"identidad_id": "EMP-03", "candidate_value": cerca}})
        chk("el intento casi correcto lo ejecuta el Rojo 2 y el motor lo registra", g.status == 200)
        for p in pz:
            p.wait_for_selector("#dlg-sol[open]", timeout=20000)
        chk("a los 4 Azules les aparece el cuadro de solicitud con qué se pide, la identidad y la hora", all("MISTERIOSA" in txt(p, "#dlg-titulo").upper() and "EMP-03" in txt(p, "#dlg-detalle") and "HORA REAL" in txt(p, "#dlg-detalle").upper() for p in pz))
        pz[1].fill("#dlg-coment", "No lo reconozco"); pz[1].click("#dlg-no")
        esperar_texto(pz[0], "#dlg-votos", "AzulDos")
        chk("el primero que responde (AzulDos) queda como decisor y todos ven su opinión sin que se cierre", "DECIDE AZULDOS" in txt(pz[0], "#dlg-decisor").upper() and "No lo reconozco" in txt(pz[0], "#dlg-votos") and pz[0].is_visible("#dlg-sol"))
        pz[2].fill("#dlg-coment", "Fui yo, olvidé la clave"); pz[2].click("#dlg-ok")
        esperar_texto(pz[0], "#dlg-votos", "AzulTres")
        chk("una opinión distinta (a favor) queda registrada, la solicitud sigue abierta y el no decisor ve la nota", "a favor" in txt(pz[0], "#dlg-votos") and "opinión" in txt(pz[0], "#dlg-nota"))
        pz[0].click("#dlg-no"); pz[3].click("#dlg-no")
        for p in pz:
            p.wait_for_function("() => !document.querySelector('#dlg-sol').open", timeout=20000)
        chk("con 3 de 4 en contra se cierra para todos y se cierran los cuadros", all(p.is_hidden("#dlg-sol") for p in pz))
        bl = rojos[1].post("/api/nova/accion", {"action_type": "guess_credential", "params": {"identidad_id": "EMP-03", "candidate_value": "11111A"}})
        chk("la decisión cambia el estado del escenario: la identidad atacada queda bloqueada para el Rojo", bl["reject_reason"] == "IDENTITY_LOCKED")
        # la IA Azul (simulada) pide autorización humana desde el constructor de prompts
        adm.post("/api/nova/ia/config", {"BLUE": {"modo": "assist", "proveedor": {"tipo": "scripted"}}})
        pz[0].wait_for_selector("#ia-azul:not([hidden])", timeout=20000)
        pz[0].evaluate("document.querySelector('#e-avanzado').open = true")
        pz[0].select_option("#e-foco", "identidad"); pz[0].select_option("#e-suj", "EMP-04"); pz[0].select_option("#e-acc", "revoke_credential"); pz[0].check("#e-pedir")
        pz[0].click("#b-prop-azul")
        esperar_texto(pz[0], "#prop-azul", "Ejecutar")
        pz[0].click("#prop-azul button:has-text('Ejecutar')")
        for p in pz:
            p.wait_for_selector("#dlg-sol[open]", timeout=20000)
        chk("la IA Azul pide autorización: a los 4 Azules les sale el cuadro con qué pide, la corrida SIMULADA y el prompt (directiva) usado",
            all("AUTORIZACIÓN" in txt(p, "#dlg-titulo").upper() and "SIMULADO" in txt(p, "#dlg-detalle").upper() and "PROMPT" in txt(p, "#dlg-detalle").upper() and "REVOKE_CREDENTIAL" in txt(p, "#dlg-detalle").upper() for p in pz))
        chk("pedirla no ejecuta nada: la credencial de EMP-04 sigue protegida mientras votan", next(x["estado"] for x in adm.get("/api/nova/estado")["catalogo"] if x["id"] == "EMP-04") == "PROTEGIDA")
        for p in pz[:3]:
            p.click("#dlg-ok")
        for p in pz:
            p.wait_for_function("() => !document.querySelector('#dlg-sol').open", timeout=20000)
        chk("3 de 4 aprueban: se cierra para todos y el motor ejecuta SOLO la acción autorizada (EMP-04 revocada)", next(x["estado"] for x in adm.get("/api/nova/estado")["catalogo"] if x["id"] == "EMP-04") in ("REVOCADA", "SUSPENDIDA"))
        T.MANUAL["on"] = False
        chk("consola del navegador sin errores", not [c for c in T.CONSOLA if "favicon" not in c], str(T.CONSOLA[:3]))
        for c in ctxs:
            c.close()
        nav.close()
    print(f"Total {sum(T.R)}/{len(T.R)}")
    return all(T.R)


if __name__ == "__main__":
    sys.exit(0 if main("--ver" in sys.argv) else 1)
