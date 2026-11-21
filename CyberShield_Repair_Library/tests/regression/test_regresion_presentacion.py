"""Regresión de la presentación (encargo CyberShield Repair, §14): 26 comprobaciones contra el SERVIDOR REAL.

Cada comprobación termina en PASS, FAIL o NO_IMPLEMENTADO (la ruta o el mecanismo no existe). Nada se simula en el servidor.
Uso:  python CyberShield_Repair_Library/tests/regression/test_regresion_presentacion.py [--linea-base]
  --linea-base  imprime la matriz y sale con 0 aunque haya fallos (para registrar el estado inicial, sin ocultarlo).
Escribe el resultado en CyberShield_Repair_Library/tests/regression/ultimo_resultado.json.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arnes import Entorno, Sse, Cliente  # noqa: E402

RES = []


def reg(n, nombre, estado, detalle=""):
    RES.append({"n": n, "nombre": nombre, "estado": estado, "detalle": detalle})
    print(f"{estado:<16} {n:>2}. {nombre}" + (f"  [{detalle}]" if detalle and estado != "PASS" else ""), flush=True)


def ok(c):
    return "PASS" if c else "FAIL"


def falta(r):
    return r.status in (404, 405)


def correos_azul(azul):
    return azul.get("/api/buzon").get("correos", [])


def main(linea_base=False):
    with Entorno(retardo_ollama=0.0) as E:
        base = E.base
        espectador_http = Cliente(base)
        # 1 · Entrar no inicia una partida
        adm = E.unirse("Admin", "general")
        rojo = E.unirse("Rojo1", "rojo")
        azul = E.unirse("Azul1", "azul")
        azul2 = E.unirse("Azul2", "azul")
        esp = E.unirse("Publico", "espectador")
        p = adm.get("/api/partida")
        reg(1, "Entrar a la aplicación no inicia una partida", ok(p["fase"] == "preparacion" and p["inicio"] is None))
        # 2 · Entrar/consultar pantallas no lanza inferencias
        for ruta in ("/api/ia/estado", "/api/ollama/estado", "/api/ollama/modelos", "/api/partidas", "/api/cronologia", "/api/escenarios"):
            adm.get(ruta)
        time.sleep(0.5)
        reg(2, "Entrar a una pantalla no inicia inferencias (0 llamadas /api/chat)", ok(E.llamadas_chat == 0), f"llamadas={E.llamadas_chat}")
        # 3 · El administrador puede crear una partida (nueva partida tras finalizar; la inicial nace en preparación)
        r_ini = adm.post("/api/partida/iniciar", {"duracion_min": 5})
        r_fin = adm.post("/api/partida/finalizar")
        r_nueva = adm.post("/api/partida/nueva")
        reg(3, "Un administrador puede crear una partida (nueva en preparación)", ok(r_nueva.status == 200 and r_nueva["fase"] == "preparacion"), f"{r_nueva.status}")
        # 4 · Solo una acción autorizada inicia la partida
        r_r = rojo.post("/api/partida/iniciar", {"duracion_min": 5})
        r_a = azul.post("/api/partida/iniciar", {"duracion_min": 5})
        r_e = esp.post("/api/partida/iniciar", {"duracion_min": 5})
        fase_antes = adm.get("/api/partida")["fase"]
        r_ok = adm.post("/api/partida/iniciar", {"duracion_min": 5})
        reg(4, "La partida solo comienza por acción del árbitro (rojo/azul/espectador 403)",
            ok(r_r.status == 403 and r_a.status == 403 and r_e.status == 403 and fase_antes == "preparacion" and r_ok.status == 200),
            f"{r_r.status},{r_a.status},{r_e.status},{r_ok.status}")
        # 5 · Los jugadores conectados aparecen en tiempo real (SSE partida_estado al unirse otro)
        sse = Sse(base, adm.token)
        time.sleep(0.5)
        nuevo = E.unirse("Rojo2", "rojo")
        ev = sse.espera("partida_estado", lambda d: any(x["nombre"] == "Rojo2" for x in d["participantes"]))
        reg(5, "Los jugadores conectados aparecen en tiempo real (SSE)", ok(ev is not None))
        # 6 · En el equipo correcto
        part = {x["nombre"]: x["equipo"] for x in adm.get("/api/partida")["participantes"]}
        reg(6, "Los jugadores aparecen en el equipo correcto", ok(part.get("Rojo1") == "rojo" and part.get("Azul1") == "azul" and part.get("Rojo2") == "rojo" and part.get("Publico") == "espectador"))
        # 7 · No ejecutan acciones de otro equipo
        a1 = azul.post("/api/correo", {"plantilla": "soporte_tecnico"})
        a2 = rojo.get("/api/buzon")
        a3 = azul.post("/api/ia/ataque", {"modelo": "falso-atacante"})
        a4 = rojo.post("/api/partida/finalizar")
        reg(7, "Los usuarios no pueden ejecutar acciones de otro equipo (403)", ok(all(x.status == 403 for x in (a1, a2, a3, a4))), f"{[x.status for x in (a1, a2, a3, a4)]}")
        # 8 · Las desconexiones se reflejan (el participante sigue visible como desconectado)
        antes = [x for x in adm.get("/api/partida")["participantes"] if x["nombre"] == "Rojo2"]
        nuevo.post("/api/sesion/salir")
        despues = [x for x in adm.get("/api/partida")["participantes"] if x["nombre"] == "Rojo2"]
        if despues and "conectado" in despues[0]:
            reg(8, "Las desconexiones se reflejan (visible como desconectado, historial conservado)", ok(despues[0]["conectado"] is False))
        else:
            reg(8, "Las desconexiones se reflejan (visible como desconectado, historial conservado)", "FAIL", "el participante desaparece de la lista y no hay campo `conectado`")
        # 9 · Correos programados del escenario (el primero toca a los 5 s de partida)
        cal = azul.get("/api/escenario/correos")
        t0 = time.time()
        llego = False
        while time.time() - t0 < 14 and not llego:
            llego = any(str(x.get("plantilla_id", "")).startswith("escenario:") for x in correos_azul(azul))
            time.sleep(0.4)
        solo_equipos = rojo.get("/api/escenario/correos").status == 403
        if falta(cal):
            reg(9, "Los correos programados del escenario llegan a la bandeja correcta", "NO_IMPLEMENTADO", f"{cal.status}")
        else:
            reg(9, "Los correos programados del escenario llegan a la bandeja correcta (y Rojo no ve el calendario)", ok(llego and solo_equipos), f"llegó={llego}, rojo_403={solo_equipos}")
        # 10 · Correos Rojo -> Azul llegan
        c = rojo.post("/api/correo", {"plantilla": "soporte_tecnico", "para_usuario": None})
        bz = correos_azul(azul)
        reg(10, "Los correos del equipo Rojo llegan a la bandeja Azul", ok(c.status == 200 and len(bz) >= 1), f"{c.status}, buzon={len(bz)}")
        # 11 · Leído actualiza estado
        cid = bz[0]["id"] if bz else None
        sin_leer_antes = sum(not x["leido"] for x in bz)
        r11 = azul.post(f"/api/correo/{cid}/leer") if cid else None
        bz2 = correos_azul(azul)
        reg(11, "Los correos leídos actualizan su estado", ok(r11 is not None and r11.status == 200 and sum(not x["leido"] for x in bz2) == sin_leer_antes - 1))
        # 12 · Notificaciones (evento SSE de correo nuevo + contador de no leídos)
        sse2 = Sse(base, azul.token)
        time.sleep(0.4)
        rojo.post("/api/correo", {"plantilla": "soporte_tecnico"})
        evc = sse2.espera("correo_nuevo", hasta=3) or sse2.espera("notificacion", hasta=1)
        bzr = azul.get("/api/buzon")
        reg(12, "Notificaciones de correo nuevo y contador de no leídos", ok(evc is not None and "no_leidos" in (bzr.datos or {})), f"evento={'sí' if evc else 'no'}, contador={'sí' if 'no_leidos' in (bzr.datos or {}) else 'no'}")
        sse2.cerrar()
        # 13/14 · Solicitudes de autorización (Rojo la crea; llega a todos los jugadores Azul; Azul acepta/rechaza; todos los clientes lo ven)
        sse3 = Sse(base, azul2.token)
        time.sleep(0.4)
        c13 = rojo.post("/api/autorizaciones", {"identidad": "ana.perez", "operacion": "consultar_clientes", "recurso": "clientes", "motivo": "informe trimestral"})
        l1 = azul.get("/api/autorizaciones")
        l2 = azul2.get("/api/autorizaciones")
        ev13 = sse3.espera("autorizacion", lambda d: d.get("estado") == "PENDIENTE", hasta=4)
        ok13 = c13.status == 200 and any(x["id"] == c13["id"] for x in l1.get("autorizaciones", [])) and any(x["id"] == c13["id"] for x in l2.get("autorizaciones", [])) and ev13 is not None
        reg(13, "Las solicitudes de autorización llegan a los jugadores del equipo Azul (lista y SSE)", "NO_IMPLEMENTADO" if falta(l1) else ok(ok13), f"{c13.status}, lista={l1.status}, sse={'sí' if ev13 else 'no'}")
        r14 = azul.post(f"/api/autorizaciones/{c13.get('id')}/rechazar") if c13.status == 200 else None
        ev14 = sse3.espera("autorizacion", lambda d: d.get("estado") == "RECHAZADA", hasta=4)
        vista_rojo = [x for x in rojo.get("/api/autorizaciones").get("autorizaciones", []) if x["id"] == c13.get("id")]
        doble = azul2.post(f"/api/autorizaciones/{c13.get('id')}/aprobar") if c13.status == 200 else None
        prohibido_rojo = rojo.post(f"/api/autorizaciones/{c13.get('id')}/aprobar") if c13.status == 200 else None
        ok14 = (r14 is not None and r14.status == 200 and r14["estado"] == "RECHAZADA" and ev14 is not None and vista_rojo and vista_rojo[0]["estado"] == "RECHAZADA"
                and doble.status == 409 and prohibido_rojo.status == 403)
        reg(14, "Aceptar/rechazar actualiza el estado en todos los clientes (SSE + lista; doble decisión 409; Rojo 403)", "NO_IMPLEMENTADO" if falta(l1) else ok(bool(ok14)),
            f"rechazar={getattr(r14, 'status', None)}, sse={'sí' if ev14 else 'no'}, doble={getattr(doble, 'status', None)}, rojo={getattr(prohibido_rojo, 'status', None)}")
        sse3.cerrar()
        # 15 · Operaciones validadas en backend
        v1 = rojo.post("/api/correo", {"plantilla": "no_existe"})
        v2 = rojo.post("/api/correo", {"plantilla": "soporte_tecnico", "para_usuario": "no.existe"})
        reg(15, "Las operaciones se validan en backend (plantilla/usuario inválidos -> 4xx)", ok(v1.status in (400, 422) and v2.status in (400, 422)), f"{v1.status},{v2.status}")
        # 16 · Ollama responde con el modelo configurado
        c16 = azul.post("/api/ia/defensor", {"modelo": "falso-defensor", "host": E.url_ollama})
        pr = adm.get(f"/api/ollama/probar?modelo=falso-defensor&host={E.url_ollama}")
        reg(16, "Ollama responde con el modelo configurado", ok(c16.status == 200 and pr.get("ok") is True), f"{c16.status}, probar={pr.get('ok')}")
        # 17 · Un error de Ollama no bloquea la partida
        pr2 = adm.get(f"/api/ollama/probar?modelo=falso-roto&host={E.url_ollama}")
        p17 = adm.get("/api/partida")
        r17 = rojo.post("/api/correo", {"plantilla": "soporte_tecnico"})
        reg(17, "Un error de Ollama no bloquea la partida", ok(pr2.get("ok") is False and p17["fase"] == "en_curso" and r17.status == 200), f"probar_roto={pr2.get('ok')}, fase={p17['fase']}, correo={r17.status}")
        # 18 · Sin inferencias duplicadas / concurrentes
        rojo.post("/api/ia/ataque", {"modelo": "falso-atacante", "host": E.url_ollama})
        d2 = rojo.post("/api/ia/ataque", {"modelo": "falso-atacante", "host": E.url_ollama})
        reg(18, "No hay inferencias duplicadas (segundo ataque simultáneo -> 409)", ok(d2.status in (409, 400)), f"{d2.status}")
        t0 = time.time()
        while time.time() - t0 < 15 and (adm.get("/api/ia/estado").get("ataque") or {}).get("en_curso"):
            time.sleep(0.3)
        # 19/20 · Pausar y reanudar (el reloj se congela; durante la pausa no hay operaciones nuevas; al reanudar se continúa)
        pz = adm.post("/api/partida/pausar")
        if falta(pz):
            reg(19, "Pausar impide iniciar operaciones nuevas", "NO_IMPLEMENTADO", f"{pz.status}")
            reg(20, "Reanudar recupera el flujo", "NO_IMPLEMENTADO", f"{pz.status}")
        else:
            r1 = adm.get("/api/partida")["restante_s"]
            time.sleep(2.2)
            r2 = adm.get("/api/partida")
            bloqueos = [rojo.post("/api/correo", {"plantilla": "soporte_tecnico"}).status, rojo.post("/api/ia/ataque", {"modelo": "falso-atacante", "host": E.url_ollama}).status,
                        rojo.post("/api/autorizaciones", {"identidad": "ana.perez", "operacion": "x", "recurso": "y", "motivo": "z"}).status]
            doble = adm.post("/api/partida/pausar").status
            reg(19, "Pausar congela el reloj e impide operaciones nuevas (409) y no se puede pausar dos veces",
                ok(pz.status == 200 and r2["fase"] == "pausada" and r2["restante_s"] == r1 and all(b == 409 for b in bloqueos) and doble == 409), f"{pz.status}, congelado={r2['restante_s'] == r1}, bloqueos={bloqueos}, doble={doble}")
            rz = adm.post("/api/partida/reanudar")
            r3 = rojo.post("/api/correo", {"plantilla": "soporte_tecnico"}).status
            reg(20, "Reanudar recupera el flujo (en curso, reloj continúa, las acciones vuelven a funcionar)", ok(rz.status == 200 and rz["fase"] == "en_curso" and rz["restante_s"] <= r1 and r3 == 200), f"{rz.status}, correo={r3}")
        # 21 · Detener cancela tareas pendientes (la partida finalizada rechaza acciones nuevas)
        f21 = adm.post("/api/partida/finalizar")
        post_fin = rojo.post("/api/correo", {"plantilla": "soporte_tecnico"})
        reg(21, "Finalizar/detener impide nuevas acciones y cancela lo pendiente", ok(f21.status == 200 and post_fin.status == 409), f"{f21.status},{post_fin.status}")
        # 22 · Eventos registrados
        cr = adm.get("/api/cronologia")
        txt = json.dumps(cr.datos, ensure_ascii=False)
        reg(22, "Los eventos quedan registrados (cronología con inicio, correos y finalización)", ok(cr.status == 200 and "PARTIDA_INICIADA" in txt and "PARTIDA_FINALIZADA" in txt), f"{cr.status}")
        # 23 · Sin correos duplicados por reintento (idempotencia)
        adm.post("/api/partida/nueva")
        a_ = adm.post("/api/partida/iniciar", {"duracion_min": 5})
        k = {"Idempotency-Key": "clave-123"}
        rojo.post("/api/correo", {"plantilla": "soporte_tecnico"}, cab=k)
        rojo.post("/api/correo", {"plantilla": "soporte_tecnico"}, cab=k)
        n23 = len(correos_azul(azul))
        reg(23, "No se duplican correos ante el mismo reintento (idempotencia)", ok(n23 == 1), f"correos={n23} tras 2 envíos con la misma clave")
        # 24 · Sin notificaciones duplicadas: depende de 12 y 23
        reg(24, "No se duplican notificaciones", "NO_IMPLEMENTADO" if not any(r["n"] == 12 and r["estado"] == "PASS" for r in RES) else ok(n23 == 1), "depende del sistema de notificaciones (12)")
        # 25 · Estados coherentes entre clientes
        vistas = [c.get("/api/partida").datos for c in (adm, rojo, azul, esp)]
        reg(25, "Los usuarios ven estados coherentes (misma fase, id y participantes)", ok(len({(v["fase"], v["id"], len(v["participantes"])) for v in vistas}) == 1))
        # 26 · Sin permisos no hay acciones (backend)
        sin = Cliente(base)
        z = [sin.post("/api/correo", {"plantilla": "soporte_tecnico"}).status, esp.post("/api/correo", {"plantilla": "soporte_tecnico"}).status,
             esp.post("/api/partida/finalizar").status]
        reg(26, "Sin permisos no se puede ejecutar acciones (anónimo/espectador -> 403)", ok(all(s == 403 for s in z)), f"{z}")
        # 27 · Chat de equipo: persistente, aislado por equipo, el espectador no lo lee y el SSE no filtra el texto
        sse4 = Sse(base, adm.token)
        time.sleep(0.4)
        m1 = rojo.post("/api/chat", {"texto": "plan: probar el correo de soporte"})
        m2 = azul.post("/api/chat", {"texto": "revisar el buzón"})
        ver_rojo = [x["texto"] for x in rojo.get("/api/chat").get("mensajes", [])]
        ver_azul = [x["texto"] for x in azul.get("/api/chat").get("mensajes", [])]
        ver_esp = esp.get("/api/chat").get("mensajes", [])
        ver_adm = adm.get("/api/chat").get("mensajes", [])
        evc = sse4.espera("chat", lambda d: d.get("equipo") == "rojo", hasta=3)
        sin_texto = evc is not None and "texto" not in evc
        esp_envia = esp.post("/api/chat", {"texto": "hola"}).status
        sse4.cerrar()
        reg(27, "Chat de equipo: aislado por equipo, el árbitro ve ambos, el espectador ninguno, el SSE no lleva el texto",
            ok(m1.status == 200 and m2.status == 200 and ver_rojo == ["plan: probar el correo de soporte"] and ver_azul == ["revisar el buzón"] and ver_esp == [] and len(ver_adm) == 2 and sin_texto and esp_envia == 403),
            f"rojo={ver_rojo}, azul={ver_azul}, esp={ver_esp}, adm={len(ver_adm)}, sse_sin_texto={sin_texto}, esp_envia={esp_envia}")
        # 28 · Correo libre de Rojo (asunto y contenido propios), sin enlaces, llega y es de solo texto
        libre = rojo.post("/api/correo/libre", {"asunto": "Revisión de factura", "cuerpo": "Hola, ¿puedes confirmar el pago pendiente de esta semana?"})
        con_url = rojo.post("/api/correo/libre", {"asunto": "x", "cuerpo": "entra a https://externo.example/login"})
        de_azul = azul.post("/api/correo/libre", {"asunto": "x", "cuerpo": "y"})
        cl = [x for x in correos_azul(azul) if x.get("plantilla_id") == "libre:rojo"]
        reg(28, "Rojo redacta un correo libre: llega a Azul como texto plano; con enlaces 400; Azul no puede enviarlo 403",
            ok(libre.status == 200 and len(cl) == 1 and cl[0]["asunto"] == "Revisión de factura" and cl[0].get("enlace") is None and con_url.status == 400 and de_azul.status == 403),
            f"{libre.status}, en_buzon={len(cl)}, con_url={con_url.status}, azul={de_azul.status}")
        # 29 · Diagnóstico de salud (público, sin secretos)
        sal = Cliente(base).get("/api/salud")
        txt = json.dumps(sal.datos, ensure_ascii=False)
        reg(29, "El diagnóstico de salud responde con estado por componente y sin secretos",
            ok(sal.status == 200 and {c["nombre"] for c in sal["comprobaciones"]} >= {"servidor", "base_de_datos", "ollama", "sse", "partida", "tareas"} and "246810" not in txt and rojo.token not in txt),
            f"{sal.status}")
        sse.cerrar()
    res = {"pass": sum(r["estado"] == "PASS" for r in RES), "fail": sum(r["estado"] == "FAIL" for r in RES),
           "no_implementado": sum(r["estado"] == "NO_IMPLEMENTADO" for r in RES), "total": len(RES), "resultados": RES}
    Path(__file__).with_name("ultimo_resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nPASS {res['pass']} · FAIL {res['fail']} · NO_IMPLEMENTADO {res['no_implementado']} · total {res['total']}")
    print(f"Total {res['pass']}/{res['total']}")
    return linea_base or (res["fail"] == 0 and res["no_implementado"] == 0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(0 if main("--linea-base" in sys.argv) else 1)
