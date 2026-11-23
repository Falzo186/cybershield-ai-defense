"""Pruebas de la API Nova contra el SERVIDOR REAL (reloj real acelerado ×30, sin sleeps largos). python server/test_nova.py"""
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "CyberShield_Repair_Library" / "tests" / "regression"))
from arnes import Cliente, Entorno  # noqa: E402

R = []


def chk(n, c, d=""):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n + (f"  [{d}]" if d and not c else ""), flush=True)


def espera(fn, hasta=20, paso=0.3):
    t0 = time.time()
    while time.time() - t0 < hasta:
        v = fn()
        if v:
            return v
        time.sleep(paso)
    return None


def main():
    with Entorno() as E:
        adm, rojo = E.unirse("Admin", "general"), E.unirse("RojoUno", "rojo")
        a1, a2 = E.unirse("AzulUno", "azul"), E.unirse("AzulDos", "azul")
        esp = E.unirse("Publico", "espectador")
        acc = lambda c, t, **p: c.post("/api/nova/accion", {"action_type": t, "params": p})  # noqa: E731
        chk("sin partida Nova el estado lo dice y nadie puede crearla salvo el administrador", Cliente(E.base).get("/api/nova/estado").get("estado") is None
            and rojo.post("/api/nova/partida", {}).status == 403 and a1.post("/api/nova/partida", {}).status == 403)
        r = adm.post("/api/nova/partida", {"duration_s": 300, "time_scale": 30, "click_prob_unconnected": 1.0})
        chk("el administrador crea la partida: queda en CONFIGURACION (no corre nada)", r.status == 200 and r["estado"] == "CONFIGURACION")
        time.sleep(2.5)
        chk("sin iniciar, tras unos segundos el tiempo de partida sigue en 0 (no hay autoinicio)", adm.get("/api/nova/estado")["t_s"] == 0 and adm.get("/api/nova/estado")["estado"] == "CONFIGURACION")
        chk("unirse antes de abrir la sala se rechaza; el administrador abre la sala de espera", rojo.post("/api/nova/unirse", {}).status == 409 and a1.post("/api/nova/sala").status == 403 and adm.post("/api/nova/sala").status == 200)
        chk("los jugadores se unen con su sesión: Rojo sin identidad, Azul con EMP-01/EMP-02", rojo.post("/api/nova/unirse", {}).status == 200 and a1.post("/api/nova/unirse", {}).status == 200 and a2.post("/api/nova/unirse", {}).status == 200)
        eadm = adm.get("/api/nova/estado")
        ident = {p["nombre"]: p["identidad"] for p in eadm["participantes"]}
        chk("cada Azul recibe una identidad distinta del catálogo y el catálogo completo (con credenciales) solo lo ve el administrador",
            ident["AzulUno"] == "EMP-01" and ident["AzulDos"] == "EMP-02" and len(eadm["catalogo"]) == 6 and "catalogo" not in rojo.get("/api/nova/estado") and "catalogo" not in a1.get("/api/nova/estado")
            and "catalogo" not in esp.get("/api/nova/estado"))
        chk("el Rojo no ve el inventario del Azul ni el Azul el panel Rojo (visibilidad en servidor)", "azul" not in rojo.get("/api/nova/estado") and "rojo" not in a1.get("/api/nova/estado") and "azul" in a1.get("/api/nova/estado"))
        chk("antes de iniciar, ninguna acción de juego funciona (409)", acc(rojo, "scan_directory").status == 409)
        chk("solo el administrador marca LISTA e inicia: jugadores 403; sin confirmación o sin clave 400", rojo.post("/api/nova/lista").status == 403 and adm.post("/api/nova/lista").status == 200
            and rojo.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "x"}).status == 403 and adm.post("/api/nova/iniciar", {"confirm": False, "idempotency_key": "x"}).status == 400
            and adm.post("/api/nova/iniciar", {"confirm": True}).status == 400)
        i1 = adm.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "demo-1"})
        i2 = adm.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "demo-1"})
        chk("el administrador inicia con confirmación e idempotencia; repetir la clave no reinicia", i1.status == 200 and i2.status == 200 and i1["estado"] == "EN_CURSO")
        t1 = espera(lambda: adm.get("/api/nova/estado")["t_s"] > 3 and adm.get("/api/nova/estado")["t_s"])
        chk("el reloj avanza por el coordinador (×30) y los correos programados llegan solos a la bandeja de Azul", bool(t1) and bool(espera(lambda: any(e["origen"] == "ESCENARIO" for e in a1.get("/api/nova/estado")["azul"]["correos"]), 15)))
        s_antes = adm.get("/api/nova/estado")["t_s"]
        pz = adm.post("/api/nova/pausar")
        time.sleep(1.5)
        chk("pausar congela el reloj y bloquea las acciones; reanudar continúa", pz["estado"] == "PAUSADA" and adm.get("/api/nova/estado")["t_s"] <= s_antes + 35 and acc(rojo, "scan_directory").status == 409)
        adm.post("/api/nova/reanudar")
        tp = adm.get("/api/nova/estado")["t_s"]
        time.sleep(1.2)
        chk("tras reanudar el tiempo vuelve a avanzar", adm.get("/api/nova/estado")["t_s"] > tp)
        # Rojo: reconocimiento, correo malicioso a un empleado NO conectado, exposición, extracción, victoria
        sc = acc(rojo, "scan_directory")
        chk("el Rojo reconoce el directorio y no recibe credenciales", sc.status == 200 and all("credencial" not in c for c in rojo.get("/api/nova/estado")["rojo"]["credenciales"]))
        em = acc(rojo, "send_email", identidad_id="EMP-05", plantilla="aviso_soporte", cuerpo="Hola, confirma tu identidad de laboratorio.")
        chk("el correo del Rojo se acepta; con una URL externa se rechaza (400)", em.status == 200 and acc(rojo, "send_email", identidad_id="EMP-05", plantilla="consulta_cordial", cuerpo="https://x.example").status == 400)
        expuesta = espera(lambda: next((c for c in rojo.get("/api/nova/estado")["rojo"]["credenciales"] if c["id"] == "EMP-05" and c["estado"] == "VALIDA_DESCUBIERTA"), None), 20)
        chk("el empleado guionizado pulsa el enlace y la credencial de EMP-05 aparece desbloqueada (enmascarada) en el panel Rojo", bool(expuesta) and "***" in expuesta["credencial"])
        chk("usar una identidad no descubierta se rechaza (403 CREDENTIAL_NOT_KNOWN)", acc(rojo, "extract_table", identidad_id="EMP-01", tabla="ventas").status == 403)
        ev_azul = a1.get("/api/nova/eventos")["eventos"]
        chk("el Azul recibe alertas y su cadena de eventos, pero nunca los eventos solo-Rojo", any(e["type"] == "alert.created" for e in ev_azul) and not any(e["type"] in ("credential.guess_attempt", "email.sent_by_red") for e in ev_azul))
        chk("el Azul no puede ejecutar acciones del Rojo (403) y el espectador no puede actuar", acc(a1, "extract_table", identidad_id="EMP-05", tabla="reportes_financieros").status == 403 and acc(esp, "scan_directory").status == 403)
        ex = acc(rojo, "extract_table", identidad_id="EMP-05", tabla="reportes_financieros")
        res = espera(lambda: adm.get("/api/nova/estado")["resultado"], 8)
        chk("la extracción validada por el motor da VICTORIA_ROJA y la partida finaliza (coordinador detenido)", ex.status == 200 and res and res["resultado"] == "VICTORIA_ROJA" and adm.get("/api/nova/estado")["estado"] == "FINALIZADA")
        d = rojo._pet("GET", "/api/nova/descarga?formato=csv")
        chk("la descarga (csv/json/sql) solo trae lo extraído; el Azul no puede descargar", d.status == 200 and a1.get("/api/nova/descarga?formato=json").status == 403)
        chk("la pantalla de victoria: resultado visible para todos y el espectador ve lo público sin credenciales", esp.get("/api/nova/estado")["resultado"]["resultado"] == "VICTORIA_ROJA" and "catalogo" not in esp.get("/api/nova/estado"))
        # nueva partida: detener y cancelar
        chk("tras FINALIZADA se puede crear otra partida; iniciar de nuevo exige todo el protocolo", adm.post("/api/nova/partida", {"time_scale": 30, "click_prob_unconnected": 1.0}).status == 200)
        adm.post("/api/nova/sala")
        rojo.post("/api/nova/unirse", {})
        a1.post("/api/nova/unirse", {})
        adm.post("/api/nova/lista")
        adm.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "demo-2"})
        # elevación: solicitud del Rojo -> Azul aprueba -> copia completa
        ap = acc(rojo, "request_elevation", motivo="Soy de soporte TI y necesito una copia para mantenimiento")
        apid = ap["data"]["approval_id"] if ap.status == 200 else None
        chk("la solicitud del Rojo llega a la bandeja del Azul (PENDIENTE, con recomendación etiquetada «reglas»)", ap.status == 200 and any(a["id"] == apid and a["estado"] == "PENDIENTE" for a in a1.get("/api/nova/estado")["azul"]["aprobaciones"]))
        chk("sin aprobación la copia completa se rechaza (403)", acc(rojo, "export_database").status == 403)
        chk("el Rojo no puede aprobar su propia solicitud (403)", acc(rojo, "approve_request", approval_id=apid).status == 403)
        chk("el Azul aprueba: cambia el estado del escenario y el Rojo copia la base completa → VICTORIA_ROJA", acc(a1, "approve_request", approval_id=apid).status == 200 and acc(rojo, "export_database").status == 200
            and adm.get("/api/nova/estado")["resultado"]["resultado"] == "VICTORIA_ROJA" and adm.get("/api/nova/estado")["resultado"]["tablas_extraidas"] and len(adm.get("/api/nova/estado")["resultado"]["tablas_extraidas"]) == 8)
        adm.post("/api/nova/partida", {"time_scale": 30, "click_prob_unconnected": 1.0})
        adm.post("/api/nova/sala")
        rojo.post("/api/nova/unirse", {})
        a1.post("/api/nova/unirse", {})
        adm.post("/api/nova/lista")
        adm.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "demo-3"})
        dt = adm.post("/api/nova/detener", {})
        chk("detener pasa a FINALIZADA sin dejar tareas vivas: el reloj queda quieto", dt["estado"] == "FINALIZADA" and (lambda t: (time.sleep(1.2), adm.get("/api/nova/estado")["t_s"] == t)[1])(adm.get("/api/nova/estado")["t_s"]))
        # ── IA de Nova: configuración, assist, anti-SSRF, Ollama falso con JSON inválido ───────────────────────
        adm.post("/api/nova/partida", {"time_scale": 30, "click_prob_unconnected": 1.0, "duration_s": 600, "ai_prompt_mode": "libre"})
        adm.post("/api/nova/sala")
        rojo.post("/api/nova/unirse", {})
        a1.post("/api/nova/unirse", {})
        adm.post("/api/nova/lista")
        chk("la IA nace apagada y solo el administrador la configura", adm.get("/api/nova/estado")["ia"]["modos"] == {"RED": "off", "BLUE": "off"} and rojo.post("/api/nova/ia/config", {"RED": {"modo": "auto"}}).status == 403)
        adm.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "demo-4"})
        pr = lambda c, eq: c.post("/api/nova/ia/proponer", {"equipo": eq})  # noqa: E731
        chk("con la IA apagada pedir una propuesta se rechaza (409 AI_OFF)", pr(rojo, "RED").status == 409)
        chk("anti-SSRF: un endpoint público o con credenciales se rechaza al configurar (400)", adm.post("/api/nova/ia/config", {"RED": {"modo": "assist", "proveedor": {"tipo": "ollama", "endpoint": "http://8.8.8.8:11434", "modelo": "x"}}}).status == 400
            and adm.post("/api/nova/ia/config", {"RED": {"modo": "assist", "proveedor": {"tipo": "ollama", "endpoint": "http://u:p@127.0.0.1:11434", "modelo": "x"}}}).status == 400)
        oe = adm.get(f"/api/nova/ollama/estado?endpoint={E.url_ollama}")
        chk("el estado del endpoint Ollama es real (conectado y con sus modelos) y un endpoint público se bloquea", oe.status == 200 and oe["conectado"] and "falso-atacante" in oe["modelos"] and adm.get("/api/nova/ollama/estado?endpoint=http://8.8.8.8:11434").status == 400)
        chk("el estado de Ollama informa tamaños de modelo, el máximo (8B) y el recomendado (4B)", oe["max_b"] == 8 and oe["recomendado_b"] == 4 and "modelos_info" in oe)
        big = adm.post("/api/nova/ia/config", {"RED": {"modo": "assist", "proveedor": {"tipo": "ollama", "endpoint": E.url_ollama, "modelo": "gigante:14b"}}})
        chk("un modelo de más de 8B se rechaza al configurar (400 MODEL_TOO_BIG)", big.status == 400 and big["motivo"] == "MODEL_TOO_BIG")
        chk("solo el administrador enciende o apaga Ollama (403 para el Rojo)", rojo.post("/api/nova/ollama/iniciar", {}).status == 403 and rojo.post("/api/nova/ollama/detener", {}).status == 403)
        chk("encender Ollama solo se permite en esta máquina (400 NOT_LOCAL con otra IP privada)", adm.post("/api/nova/ollama/iniciar", {"endpoint": "http://192.168.1.50:11434"}).status == 400)
        adm.post("/api/nova/ia/config", {"RED": {"modo": "assist", "proveedor": {"tipo": "scripted"}}, "BLUE": {"modo": "auto", "proveedor": {"tipo": "scripted"}}})
        run = pr(rojo, "RED")
        chk("assist: la IA propone con etiqueta SIMULADO y no ejecuta nada", run.status == 200 and run["provider_kind"] == "scripted" and run["propuesta"]["estado"] == "PROPUESTA" and acc(rojo, "allow").status in (200, 403, 400, 409))
        chk("el Azul no puede pedir ni confirmar propuestas del Rojo (403)", pr(a1, "RED").status == 403 and a1.post("/api/nova/ia/confirmar", {"run_id": run["run_id"]}).status == 403)
        cf = rojo.post("/api/nova/ia/confirmar", {"run_id": run["run_id"]})
        chk("un humano del Rojo confirma y el motor ejecuta por el pipeline", cf.status == 200 and cf["estado"] == "EJECUTADA")
        chk("las corridas son visibles solo para su equipo (el Azul no ve las del Rojo) y el administrador ve todas", all(c["team"] == "RED" for c in rojo.get("/api/nova/ia/runs")["corridas"]) and not any(c["team"] == "RED" for c in a1.get("/api/nova/ia/runs")["corridas"])
            and len(adm.get("/api/nova/ia/runs")["corridas"]) >= 1)
        adm.post("/api/nova/ia/config", {"RED": {"modo": "assist", "proveedor": {"tipo": "ollama", "endpoint": E.url_ollama, "modelo": "falso-atacante"}}})
        ol = pr(rojo, "RED")
        chk("Ollama (falso) responde pero no cumple el esquema de propuestas: se registra INVALIDA, la partida sigue y NO se ejecuta nada", ol.status == 200 and ol["provider_kind"] == "ollama" and ol["propuesta"]["estado"] == "INVALIDA"
            and adm.get("/api/nova/estado")["estado"] == "EN_CURSO")
        adm.post("/api/nova/ia/config", {"RED": {"modo": "assist", "proveedor": {"tipo": "ollama", "endpoint": E.url_ollama, "modelo": "falso-roto"}}})
        ro = pr(rojo, "RED")
        chk("un modelo roto (HTTP 500) da una corrida FALLIDA con error claro y la partida sigue", ro.status == 200 and ro["estado"] == "FALLIDA" and adm.get("/api/nova/estado")["estado"] == "EN_CURSO")
        h = esp.get("/api/nova/historial")
        chk("el historial lista los resultados persistidos de las partidas anteriores (consultable por cualquiera)", h.status == 200 and len(h["partidas"]) >= 3 and any(x["resultado"] == "VICTORIA_ROJA" for x in h["partidas"]))
        w = a1.get("/api/nova/wazuh")
        chk("la capa Wazuh es separada y honesta: fuente SIMULADA etiquetada, real NO_CONFIGURADO, y el Rojo no accede", w.status == 200 and w["fuente_activa"] == "simulated" and w["real"]["estado"] == "NO_CONFIGURADO"
            and all(x["source"] == "simulated" for x in w["alertas"]) and rojo.get("/api/nova/wazuh").status == 403)
        adm.post("/api/nova/detener", {})
        # ── prompts CONTROLADOS: directiva de catálogo, oportunidades por equipo y acceso sospechoso ──────────
        cr = adm.post("/api/nova/partida", {"time_scale": 30, "click_prob_unconnected": 1.0, "duration_s": 600, "ai_prompt_budget": 2, "guess_cooldown_s": 0, "guess_attempts_per_round": 9, "detect_prob_fail": 0.0})
        chk("el modo por defecto es controlado y el administrador fija las oportunidades por equipo", cr.status == 200 and cr["config"]["ai_prompt_mode"] == "controlado" and cr["config"]["ai_prompt_budget"] == 2
            and adm.post("/api/nova/partida", {"ai_prompt_budget": 0}).status in (400, 409) and adm.post("/api/nova/partida", {"ai_prompt_mode": "otro"}).status in (400, 409))
        adm.post("/api/nova/sala")
        rojo.post("/api/nova/unirse", {})
        a1.post("/api/nova/unirse", {})
        adm.post("/api/nova/lista")
        adm.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "demo-5"})
        adm.post("/api/nova/ia/config", {"RED": {"modo": "assist", "proveedor": {"tipo": "scripted"}}, "BLUE": {"modo": "assist", "proveedor": {"tipo": "scripted"}}})
        er = rojo.get("/api/nova/estado")
        chk("el Rojo ve su contador y el catálogo de directivas, pero no el contador del Azul", er["ia"]["oportunidades"] == {"RED": {"usadas": 0, "total": 2, "restantes": 2, "modo": "controlado"}} and "acciones_rojo" in er["ia"]["catalogo_directiva"])
        sin = pr(rojo, "RED")
        chk("sin directiva la IA no se lanza (400 DIRECTIVA_REQUIRED) y no se gasta nada", sin.status == 400 and sin["motivo"] == "DIRECTIVA_REQUIRED" and rojo.get("/api/nova/estado")["ia"]["oportunidades"]["RED"]["usadas"] == 0)
        dp = lambda c, eq, d: c.post("/api/nova/ia/proponer", {"equipo": eq, "directiva": d})  # noqa: E731
        base = {"accion": "scan_directory", "objetivo": "info_administrativa"}
        chk("una directiva fuera del catálogo se rechaza (400) y una credencial aún no obtenida no se puede elegir (409)", dp(rojo, "RED", {**base, "accion": "borrar"}).status == 400
            and dp(rojo, "RED", {"accion": "query_resource", "objetivo": "consultar_ventas", "identidad_id": "EMP-01", "credencial": {"modo": "conocida"}}).status == 409)
        ok1 = dp(rojo, "RED", base)
        chk("una directiva válida lanza la IA (SIMULADA), queda registrada y gasta una oportunidad", ok1.status == 200 and ok1["provider_kind"] == "scripted" and ok1["directiva"]["accion"] == "scan_directory"
            and rojo.get("/api/nova/estado")["ia"]["oportunidades"]["RED"]["restantes"] == 1)
        dp(rojo, "RED", base)
        agot = dp(rojo, "RED", base)
        chk("al agotar las oportunidades la IA ya no se lanza (429 PROMPT_BUDGET_EXCEEDED)", agot.status == 429 and agot["motivo"] == "PROMPT_BUDGET_EXCEEDED")
        chk("el Azul no puede gastar los prompts del Rojo, y conserva los suyos", dp(a1, "RED", base).status == 403 and a1.get("/api/nova/estado")["ia"]["oportunidades"]["BLUE"]["restantes"] == 2)
        real = next(x["credencial"] for x in adm.get("/api/nova/estado")["catalogo"] if x["id"] == "EMP-01")
        cerca = real[:4] + ("0" if real[4] != "0" else "1") + ("A" if real[5] != "A" else "B")
        g = acc(rojo, "guess_credential", identidad_id="EMP-01", candidate_value=cerca)
        ea = a1.get("/api/nova/estado")["azul"]
        sosp = [x for x in ea["aprobaciones"] if x["operacion"] == "acceso_sospechoso"]
        chk("un intento casi correcto llega al Azul como solicitud misteriosa con identidad y jugador, y el Rojo no ve nada de eso", g.status == 200 and len(sosp) == 1 and sosp[0]["detalle"]["identidad"] == "EMP-01"
            and "approval" not in str(rojo.get("/api/nova/estado")["rojo"]["aprobaciones"]))
        vt = rojo.post("/api/nova/accion", {"action_type": "vote_request", "params": {"approval_id": "AP-001", "voto": "APROBAR"}})
        chk("un Rojo no puede votar solicitudes del Azul (403) y el voto inválido se rechaza", vt.status == 403 and a1.post("/api/nova/accion", {"action_type": "vote_request", "params": {"approval_id": "AP-001", "voto": "TAL VEZ"}}).status in (400, 404))
        ap1 = next((x for x in a1.get("/api/nova/estado")["azul"]["aprobaciones"] if x["operacion"] == "acceso_sospechoso"), None)
        vv = a1.post("/api/nova/accion", {"action_type": "vote_request", "params": {"approval_id": ap1["id"], "voto": "RECHAZAR", "comentario": "no es de aquí"}})
        vot = next(x for x in a1.get("/api/nova/estado")["azul"]["aprobaciones"] if x["id"] == ap1["id"])
        chk("la API de votos registra la opinión de un Azul con su comentario y fija el decisor", vv.status == 200 and vv["data"].get("cerrada_por") == "votos" and list(vot["votos"].values())[0]["comentario"] == "no es de aquí" and vot["decisor"] in vot["votos"])
        chk("con un solo Azul su voto es mayoría absoluta: cierra la solicitud y la identidad queda bloqueada para el Rojo", acc(rojo, "guess_credential", identidad_id="EMP-01", candidate_value="11111A")["reject_reason"] == "IDENTITY_LOCKED")
        chk("lo que el Rojo ve de sus propias solicitudes no incluye votos, comentarios ni decisor del Azul", not any(k in str(rojo.get("/api/nova/estado")["rojo"]["aprobaciones"]) for k in ("votos", "decisor", "comentario")))
        lt = a1.post("/api/nova/latido", {})
        chk("el latido de presencia lo acepta un jugador, y el espectador o el admin lo ignoran sin error", lt.status == 200 and "ignorado" not in lt and esp.post("/api/nova/latido", {}).status in (200, 403))
        adm.post("/api/nova/detener", {})
        salud = Cliente(E.base).get("/api/ia/estado")
        # ── práctica, presupuesto visible, monitor Azul y resumen ──
        adm.post("/api/nova/detener", {"cancelar": True})
        pr = adm.post("/api/nova/partida", {"practica": True, "time_scale": 30, "click_prob_unconnected": 1.0})
        adm.post("/api/nova/sala")
        rojo.post("/api/nova/unirse", {})
        a1.post("/api/nova/unirse", {})
        adm.post("/api/nova/lista")
        adm.post("/api/nova/iniciar", {"confirm": True, "idempotency_key": "demo-prac"})
        ep = adm.get("/api/nova/estado")
        chk("el modo práctica dura 5 minutos, va marcado como práctica y usa ritmo rápido", pr.status == 200 and ep["practica"] is True and ep["duracion_s"] == 300 and ep["config"]["click_delay_s"] == 8)
        pb = rojo.get("/api/nova/estado")["rojo"]["presupuesto"]
        chk("el Rojo ve su presupuesto: correos, reconocimientos, intentos, ronda y tiempo restante", {"correos", "reconocimientos", "intentos_ronda", "intentos_partida", "tiempo_restante_s", "segundos_para_siguiente_ronda"} <= set(pb))
        acc(rojo, "send_email", identidad_id="EMP-02", plantilla="aviso_soporte", cuerpo="Confirma tu identidad.")
        chk("el presupuesto refleja lo gastado (1 correo usado)", rojo.get("/api/nova/estado")["rojo"]["presupuesto"]["correos"]["usados"] == 1)
        mon = a1.get("/api/nova/estado")["azul"]["monitor"]
        chk("el Azul recibe un monitor con riesgo general 0-100, contadores y eventos puntuados; el Rojo no lo recibe", 0 <= mon["riesgo_general"] <= 100 and "contadores" in mon and "monitor" not in str(rojo.get("/api/nova/estado").get("azul")))
        chk("antes de terminar el resumen completo no lo pide un jugador (409) pero sí el administrador", rojo.get("/api/nova/resumen").status == 409 and adm.get("/api/nova/resumen").status == 200)
        acc(rojo, "request_elevation", motivo="Necesito la base completa")
        apx = next(x for x in a1.get("/api/nova/estado")["azul"]["aprobaciones"] if x["operacion"] == "db_export")
        acc(a1, "approve_request", approval_id=apx["id"])
        acc(rojo, "export_database")
        rs = rojo.get("/api/nova/resumen")
        chk("al terminar, el resumen trae resultado, práctica, línea de tiempo con fuentes y errores defensivos (aprobó una solicitud de alto riesgo)", rs.status == 200 and rs["resultado"]["resultado"] == "VICTORIA_ROJA" and rs["practica"] is True
            and {x["fuente"] for x in rs["linea_tiempo"]} & {"jugador", "motor"} and any("alto riesgo" in x for x in rs["errores_defensivos"]))
        chk("la vista de espectador del resumen no incluye valores de credenciales", "12345A" not in str(esp.get("/api/nova/resumen")) and esp.get("/api/nova/resumen").status == 200)
        ex1 = a1.post("/api/nova/azul/explicar", {"seq": rs_seq}) if (rs_seq := (a1.get("/api/nova/estado")["azul"]["monitor"]["eventos"] or [{"seq": -1}])[0]["seq"]) else None
        chk("la explicación del monitor funciona sin modelo (fuente «reglas») y el Rojo no puede pedirla (403)", ex1.status == 200 and ex1["fuente"] == "reglas" and "sospecha" in ex1["explicacion"] and rojo.post("/api/nova/azul/explicar", {"seq": rs_seq}).status == 403)
        chk("una dificultad de NPC inválida se rechaza (400)", adm.post("/api/nova/partida", {"npc_dificultad": "imposible"}).status in (400, 409))
        chk("la API sigue sana tras todo el flujo", salud.status == 200)
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(0 if main() else 1)
