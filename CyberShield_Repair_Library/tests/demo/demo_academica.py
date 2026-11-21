"""Demostración académica de 17 pasos (CyberShield Repair §15), ejecutada contra el SERVIDOR REAL con varios clientes conectados a la vez
(árbitro, 2 Rojo, 2 Azul, espectador). NO es una animación pregrabada: cada paso llama a la API real y comprueba el resultado.

MODO DE PRUEBA: como Ollama real puede no estar disponible, el defensor y el atacante son un Ollama FALSO etiquetado (e2e/ollama_falso.py);
sus respuestas no dicen nada de la calidad de ningún modelo. Con Ollama real: python demo_academica.py --ollama http://127.0.0.1:11434 --atacante M --defensor M.
Salida: una línea por paso con la evidencia y, al final, el resumen y el registro de eventos.
Ejecutar: python CyberShield_Repair_Library/tests/demo/demo_academica.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "regression"))
from arnes import Entorno, Sse  # noqa: E402

PASOS = []


def paso(n, texto, ok, evidencia=""):
    PASOS.append((n, texto, bool(ok)))
    print(f"{'OK   ' if ok else 'FALLO'} {n:>2}. {texto}" + (f"  → {evidencia}" if evidencia else ""), flush=True)


def main():
    t_ini = time.time()
    print("== DEMOSTRACIÓN ACADÉMICA · MODO DE PRUEBA (Ollama falso etiquetado) ==")
    with Entorno() as E:
        adm = E.unirse("Admin", "general")
        paso(1, "Entrar como administrador", adm.get("/api/sesion")["participante"]["rol"] == "arbitro", "rol árbitro")
        p0 = adm.get("/api/partida")
        paso(2, "Crear una partida (nace en PREPARACIÓN; no empieza sola)", p0["fase"] == "preparacion" and p0["inicio"] is None, f"id {p0['id']}")
        r1, r2, a1, a2, esp = E.unirse("Rojo1", "rojo"), E.unirse("Rojo2", "rojo"), E.unirse("Azul1", "azul"), E.unirse("Azul2", "azul"), E.unirse("Publico", "espectador")
        sse = Sse(E.base, adm.token)
        paso(3, "Conectar varios jugadores (2 Rojo, 2 Azul, 1 espectador)", len(adm.get("/api/partida")["participantes"]) == 6)
        pl = {x["nombre"]: (x["equipo"], x["conectado"]) for x in adm.get("/api/partida")["participantes"]}
        paso(4, "Mostrar participantes y equipos con su estado de conexión", pl["Rojo1"] == ("rojo", True) and pl["Azul2"] == ("azul", True), str(pl))
        d = a1.post("/api/ia/defensor", {"modelo": "falso-defensor", "host": E.url_ollama})
        t = r1.get(f"/api/ollama/probar?modelo=falso-atacante&host={E.url_ollama}&rol=rojo")
        paso(5, "Seleccionar modelos (atacante y defensor, independientes) [MODO PRUEBA]", d.status == 200 and t.get("ok") is True, "falso-atacante / falso-defensor")
        no_antes = r1.post("/api/correo", {"plantilla": "soporte_tecnico"}).status
        ini = adm.post("/api/partida/iniciar", {"duracion_min": 5})
        paso(6, "Iniciar manualmente (antes de iniciar, Rojo recibe 409)", no_antes == 409 and ini.status == 200 and ini["fase"] == "en_curso", f"antes={no_antes}")
        t0 = time.time()
        while time.time() - t0 < 12 and not any(str(x.get("plantilla_id", "")).startswith("escenario:") for x in a1.get("/api/buzon")["correos"]):
            time.sleep(0.4)
        esc = [x for x in a1.get("/api/buzon")["correos"] if str(x.get("plantilla_id", "")).startswith("escenario:")]
        paso(7, "Mostrar una comunicación del escenario (RR. HH.) en la bandeja de Azul", bool(esc), esc[0]["asunto"] if esc else "")
        c = r1.post("/api/correo/libre", {"asunto": "Verificación de cuenta", "cuerpo": "Hola, soporte pide confirmar tu usuario por este medio interno."})
        ev = sse.espera("correo_nuevo", hasta=3)
        paso(8, "Enviar un correo desde Rojo a Azul (llega a la bandeja y avisa en vivo)", c.status == 200 and ev is not None, f"correo #{c.get('id')}, notificación={'sí' if ev else 'no'}")
        nl0 = a2.get("/api/buzon")["no_leidos"]
        lee = a2.post(f"/api/correo/{c['id']}/leer")
        nl1 = a2.get("/api/buzon")["no_leidos"]
        paso(9, "Abrirlo desde la cuenta Azul (el contador de no leídos baja y abrir no compromete)", lee.status == 200 and nl1 == nl0 - 1, f"no leídos {nl0}→{nl1}")
        inc = a1.post("/api/incidentes", {"titulo": "Correo sospechoso de soporte", "severidad": "media", "correo_id": c["id"]})
        paso(10, "Generar un incidente a partir del correo", inc.status == 200, f"incidente #{(inc.get('incidente') or {}).get('id')}")
        sol = r2.post("/api/autorizaciones", {"identidad": "ana.perez", "operacion": "consultar_clientes", "recurso": "clientes", "motivo": "informe trimestral"})
        vista = a1.get("/api/autorizaciones")
        paso(11, "Mostrar una solicitud de autorización (llega a los dos jugadores de Azul)", sol.status == 200 and any(x["id"] == sol["id"] for x in vista["autorizaciones"]) and any(x["id"] == sol["id"] for x in a2.get("/api/autorizaciones")["autorizaciones"]), f"riesgo {sol.get('riesgo')}, vence en {sol.get('tiempo_restante_s')} s")
        dec = a2.post(f"/api/autorizaciones/{sol['id']}/rechazar")
        paso(12, "Rechazar desde Azul (Rojo y el árbitro ven el nuevo estado)", dec.status == 200 and dec["estado"] == "RECHAZADA" and any(x["estado"] == "RECHAZADA" for x in r2.get("/api/autorizaciones")["autorizaciones"]), f"resuelta por {dec.get('resuelta_por')}")
        at = r1.post("/api/ia/ataque", {"modelo": "falso-atacante", "host": E.url_ollama})
        paso(13, "Mostrar una operación del equipo Rojo (ataque IA lanzado) [MODO PRUEBA]", at.status == 200, "controlada: 1 a la vez, con identificador")
        t0 = time.time()
        while time.time() - t0 < 20 and adm.get("/api/ia/estado").get("en_curso"):
            time.sleep(0.4)
        est = adm.get("/api/ia/estado")
        ult = (est.get("ataques") or [{}])[-1]
        paso(14, "Mostrar la respuesta defensiva (decisión del defensor y capa que actuó)", ult.get("resultado") is not None, f"resultado {ult.get('resultado')}")
        pz = adm.post("/api/partida/pausar")
        r_p = r1.post("/api/correo/libre", {"asunto": "x", "cuerpo": "durante la pausa"}).status
        rz = adm.post("/api/partida/reanudar")
        paso(15, "Pausar y reanudar (en pausa las acciones dan 409; al reanudar continúa)", pz.status == 200 and r_p == 409 and rz.status == 200 and rz["fase"] == "en_curso", f"acción en pausa={r_p}")
        fin = adm.post("/api/partida/finalizar")
        tras = r1.post("/api/correo/libre", {"asunto": "x", "cuerpo": "tras finalizar"}).status
        paso(16, "Finalizar (después ya no se admiten acciones)", fin.status == 200 and tras == 409, f"ganador {fin.get('ganador')}, acción tras finalizar={tras}")
        cr = adm.get("/api/cronologia")
        textos = " | ".join(e["texto"] for e in cr["entradas"])
        paso(17, "Consultar el historial y los logs (cronología con filtros)", cr.status == 200 and cr["total"] >= 8 and "pausó" in textos and "reanudó" in textos, f"{cr['total']} eventos; categorías {cr['conteo']}")
        print("\n-- Últimos eventos registrados --")
        for e in cr["entradas"][-8:]:
            print(f"   [{e['categoria']:<13}] {e['texto']}")
        sse.cerrar()
    ok = all(x[2] for x in PASOS)
    print(f"\n{sum(x[2] for x in PASOS)}/{len(PASOS)} pasos OK en {time.time() - t_ini:.0f} s (modo de prueba con Ollama falso)")
    print(f"Total {sum(x[2] for x in PASOS)}/{len(PASOS)}")
    return ok


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(0 if main() else 1)
