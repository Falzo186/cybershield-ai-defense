"""Pruebas del motor Nova (paquete del profesor). Lógica pura con reloj VIRTUAL (sin sleep). python -m src.lab.test_nova"""
import json

from cryptography.fernet import Fernet

from .nova import escenario as E
from .nova.motor import ErrorNova, NovaPartida, Reloj, Secretos

SEC = Secretos(pepper="pimienta-de-prueba", clave_fernet=Fernet.generate_key())
R = []


def chk(n, c):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n)


def lanza(fn, motivo=None):
    try:
        fn()
    except ErrorNova as e:
        return motivo is None or e.motivo == motivo
    return False


def nueva(azules=4, **cfg):
    m = NovaPartida(config=cfg, secretos=SEC)
    m.abrir_sala()
    m.unirse("Rojo1", "RED")
    for i in range(azules):
        m.unirse(f"Azul{i + 1}", "BLUE")
    m.marcar_lista()
    m.iniciar("ADMIN", True, "k-" + m.id)
    return m


def rojo(m, tipo, **p):
    return m.ejecutar({"action_type": tipo, "actor": {"kind": "human", "team": "RED", "user": "Rojo1"}, "params": p})


def azul(m, tipo, user="Azul1", **p):
    return m.ejecutar({"action_type": tipo, "actor": {"kind": "human", "team": "BLUE", "user": user}, "params": p})


def tipos(m, para="ADMIN"):
    return [e["type"] for e in m.eventos(para)]


def exponer(m, iid):
    """Un correo malicioso a una identidad NO conectada: el empleado guionizado pulsa solo, sin intervención de nadie."""
    r = rojo(m, "send_email", identidad_id=iid, plantilla="aviso_soporte")
    m.avanzar(m.config["click_delay_s"] + 2)
    return r


def main():
    # ── ciclo de vida: la partida NO inicia sola ─────────────────────────────────────────────────────
    m = NovaPartida(secretos=SEC)
    chk("una partida nueva queda en CONFIGURACION: nada corre ni se genera solo", m.estado == "CONFIGURACION" and m.reloj.ahora_ms() == 0)
    m.abrir_sala()
    m.unirse("Rojo1", "RED")
    m.unirse("Azul1", "BLUE")
    m.avanzar(60)
    chk("en la sala de espera el reloj no avanza y el motor no dispara nada (aunque se llame a tick/avanzar)", m.reloj.ahora_ms() == 0 and "scheduler.event_fired" not in tipos(m))
    chk("sin LISTA no se puede iniciar (transición inválida)", lanza(lambda: m.iniciar("ADMIN", True, "k"), "INVALID_TRANSITION"))
    chk("marcar LISTA exige al menos un Rojo y un Azul", lanza(lambda: NovaPartida(secretos=SEC).marcar_lista(), "INVALID_TRANSITION"))
    m.marcar_lista()
    chk("solo el administrador inicia (jugador → 403) y exige confirmación e idempotencia", lanza(lambda: m.iniciar("RED", True, "k"), "FORBIDDEN") and lanza(lambda: m.iniciar("ADMIN", False, "k"), "CONFIRM_REQUIRED")
        and lanza(lambda: m.iniciar("ADMIN", True, None), "CONFIRM_REQUIRED") and m.estado == "LISTA")
    m.iniciar("ADMIN", True, "una-clave")
    m.iniciar("ADMIN", True, "una-clave")
    chk("iniciar con la misma clave dos veces NO inicia dos veces (idempotente)", m.estado == "EN_CURSO" and tipos(m).count("match.started") == 1)
    m.avanzar(30)
    t = m.reloj.ahora_ms()
    m.pausar()
    m.avanzar(100)
    chk("pausar detiene el reloj; avanzar en pausa no mueve nada", m.estado == "PAUSADA" and m.reloj.ahora_ms() == t)
    chk("en pausa las acciones se rechazan (MATCH_NOT_RUNNING)", rojo(m, "scan_directory")["reject_reason"] == "MATCH_NOT_RUNNING")
    m.reanudar()
    m.avanzar(5)
    chk("reanudar continúa desde el tiempo guardado", m.estado == "EN_CURSO" and m.reloj.ahora_ms() == t + 5000)
    m.detener()
    chk("detener pasa por DETENIENDO y termina FINALIZADA con resultado; después no hay acciones", m.estado == "FINALIZADA" and m.resultado is not None and "match.stopping" in tipos(m)
        and rojo(m, "scan_directory")["reject_reason"] == "MATCH_NOT_RUNNING")
    mc = nueva()
    mc.detener(cancelar=True)
    chk("cancelar termina CANCELADA con SIN_RESULTADO_CANCELADA", mc.estado == "CANCELADA" and mc.resultado["resultado"] == "SIN_RESULTADO_CANCELADA")
    chk("estados terminales no admiten transiciones", lanza(lambda: mc.pausar(), "INVALID_TRANSITION"))

    # ── jugadores e identidades ──────────────────────────────────────────────────────────────────────
    m = nueva()
    ids = [p["identidad"] for p in m.participantes.values() if p["equipo"] == "BLUE"]
    chk("hasta 4 jugadores Azul con identidades EMP-01..EMP-04 por defecto", ids == ["EMP-01", "EMP-02", "EMP-03", "EMP-04"])
    chk("el quinto Azul se rechaza (TEAM_FULL)", lanza(lambda: m.unirse("Azul5", "BLUE"), "TEAM_FULL"))
    ma = NovaPartida(secretos=SEC)
    ma.abrir_sala()
    ma.unirse("A", "BLUE")
    ma.unirse("B", "BLUE")
    ma.reasignar("ADMIN", "B", "EMP-06")
    chk("el administrador reasigna identidades en la sala; no se duplican ni se reasigna sin ser admin", ma.participantes["B"]["identidad"] == "EMP-06"
        and lanza(lambda: ma.reasignar("ADMIN", "B", "EMP-01"), "IDENTITY_TAKEN") and lanza(lambda: ma.reasignar("RED", "B", "EMP-05"), "FORBIDDEN"))
    chk("catálogo fijo de 6 identidades estable entre partidas", [i["id"] for i in E.IDENTIDADES] == [f"EMP-0{k}" for k in range(1, 7)] and E.generar_credenciales() == E.generar_credenciales())
    m2 = nueva()
    chk("reiniciar el escenario NO cambia las credenciales (mismas credenciales en otra partida)", [d["credencial"] for d in m.catalogo_admin()] == [d["credencial"] for d in m2.catalogo_admin()])

    # ── credenciales ─────────────────────────────────────────────────────────────────────────────────
    cat = m.catalogo_admin()
    chk("todas cumplen ^[0-9]{5}[A-Z]$, son únicas y nacen PROTEGIDAS", all(__import__("re").match(E.PATRON_CREDENCIAL, c["credencial"]) for c in cat) and len({c["credencial"] for c in cat}) == 6
        and all(c["estado"] == "PROTEGIDA" for c in cat))
    chk("EMP-04 es la identidad débil (12345A, weak=true) y solo ella", [c["id"] for c in cat if c["debil"]] == ["EMP-04"] and [c["credencial"] for c in cat if c["id"] == "EMP-04"] == ["12345A"])
    chk("se guardan solo hash HMAC y cifrado Fernet (nunca el valor en claro) y se enmascaran en vistas", all("12345A" not in str(v) for v in m.creds["EMP-04"].values()) and Secretos.enmascarar("48271K") == "48***K")
    vr = m.vista_rojo()
    chk("el Rojo no recibe el catálogo ni valores al inicio: todas las identidades DESCONOCIDAS y sin credencial", all(v["estado"] == "DESCONOCIDA" and "credencial" not in v for v in vr))

    # ── reconocimiento y adivinación (presupuesto, cooldown, lockout, detección) ──────────────────────
    r = rojo(m, "scan_directory")
    chk("scan_directory identifica identidades (IDENTIFICADA), nunca la credencial", r["ok"] and all(v["estado"] == "IDENTIFICADA" and "credencial" not in v for v in m.vista_rojo() if v["estado"] != "DESCONOCIDA"))
    chk("el presupuesto de reconocimiento por ronda se agota", rojo(m, "scan_directory")["ok"] and rojo(m, "scan_directory")["reject_reason"] == "BUDGET_EXCEEDED")
    g = rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="00000A")
    chk("una candidata incorrecta no da acceso y se registra el intento (candidata enmascarada en el evento)", g["ok"] and g["data"]["acierto"] is False and m.creds["EMP-01"]["estado"] == "PROTEGIDA"
        and "00000A" not in str([e for e in m.eventos_lista if e["type"] == "credential.guess_attempt"]))
    chk("formato inválido -> INVALID_SCHEMA", rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="abc")["reject_reason"] == "INVALID_SCHEMA")
    chk("cooldown tras cada intento (20 s de tiempo de partida)", rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="11111B")["reject_reason"] == "COOLDOWN")
    m.avanzar(21)
    rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="22222C")
    m.avanzar(21)
    g3 = rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="33333D")
    chk("tras 3 fallos seguidos la identidad se BLOQUEA y siempre genera alerta", g3["data"]["bloqueada"] and any(a["titulo"].startswith("Identidad bloqueada") for a in m.alertas.values()))
    m.avanzar(21)
    chk("una identidad bloqueada rechaza nuevos intentos (IDENTITY_LOCKED)", rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="44444E")["reject_reason"] == "IDENTITY_LOCKED")
    m.avanzar(100)
    mg = nueva()
    ok = rojo(mg, "guess_credential", identidad_id="EMP-04", candidate_value="12345A")
    chk("la identidad débil (patrón predecible) se adivina: el motor valida, la credencial queda COMPROMETIDA y aparece en el panel Rojo",
        ok["ok"] and ok["data"]["acierto"] and mg.creds["EMP-04"]["estado"] == "COMPROMETIDA" and next(v for v in mg.vista_rojo() if v["id"] == "EMP-04")["estado"] == "VALIDA_DESCUBIERTA"
        and next(v for v in mg.vista_rojo() if v["id"] == "EMP-04")["credencial"] == "12***A")
    mp = nueva(guess_attempts_per_round=3, guess_cooldown_s=0)
    res = [rojo(mp, "guess_credential", identidad_id=f"EMP-0{k}", candidate_value="99999Z")["reject_reason"] for k in (1, 2, 3, 5)]
    chk("el presupuesto por ronda (3) impide la fuerza bruta aunque no haya cooldown", res[:3] == [None, None, None] and res[3] == "BUDGET_EXCEEDED")
    mm = nueva(guess_attempts_per_match=2, guess_cooldown_s=0, guess_attempts_per_round=9)
    rr = [rojo(mm, "guess_credential", identidad_id="EMP-01", candidate_value="55555F")["reject_reason"] for _ in range(3)]
    chk("el presupuesto por partida también limita", rr == [None, None, "BUDGET_EXCEEDED"])
    md = nueva(detect_prob_fail=1.0, guess_lockout_after_fails=9, guess_cooldown_s=0)
    rojo(md, "guess_credential", identidad_id="EMP-02", candidate_value="66666G")
    chk("con detect_prob_fail=1 cada fallo alerta al Azul («Intento de acceso denegado»)", any(a["titulo"] == "Intento de acceso denegado" for a in md.alertas.values()))
    mn = nueva(detect_prob_fail=0.0, guess_lockout_after_fails=9, guess_cooldown_s=0)
    rojo(mn, "guess_credential", identidad_id="EMP-02", candidate_value="66666G")
    chk("con detect_prob_fail=0 el fallo no genera alerta (detección probabilística)", not any(a["titulo"] == "Intento de acceso denegado" for a in mn.alertas.values()))

    # ── cadena de correo ─────────────────────────────────────────────────────────────────────────────
    m = nueva()
    r = rojo(m, "send_email", identidad_id="EMP-01", plantilla="aviso_soporte")
    eid = r["data"]["email_id"]
    chk("el correo de Rojo llega a la bandeja de la identidad del jugador Azul correcto", any(e["id"] == eid for e in m.vista_azul("Azul1")["correos"]) and not any(e["id"] == eid for e in m.vista_azul("Azul2")["correos"]))
    chk("un Azul no puede abrir el correo de otra bandeja", azul(m, "open_email", "Azul2", email_id=eid)["reject_reason"] == "NOT_YOUR_INBOX")
    azul(m, "open_email", "Azul1", email_id=eid)
    chk("abrir un correo NO compromete la identidad", m.creds["EMP-01"]["estado"] == "PROTEGIDA" and "credential.exposed" not in tipos(m))
    lid = m.emails[eid]["link_id"]
    azul(m, "view_link", "Azul1", link_id=lid)
    cl = azul(m, "click_link", "Azul1", link_id=lid)
    chk("pulsar el enlace abre una página interna SIN campo de contraseña y todavía no expone nada", "no existe ningún campo" in cl["data"]["aviso"] and m.creds["EMP-01"]["estado"] == "PROTEGIDA")
    chk("la cadena de eventos está separada: recibido → abierto → visto → pulsado", [t for t in tipos(m) if t in ("email.received", "email.opened", "link.viewed", "link.clicked")][-4:] == ["email.received", "email.opened", "link.viewed", "link.clicked"])
    azul(m, "risk_action", "Azul1", link_id=lid)
    chk("solo la acción de riesgo expone la credencial de LA identidad del jugador que actuó (COMPROMETIDA y en el panel Rojo)", m.creds["EMP-01"]["estado"] == "COMPROMETIDA"
        and next(v for v in m.vista_rojo() if v["id"] == "EMP-01")["estado"] == "VALIDA_DESCUBIERTA" and m.creds["EMP-02"]["estado"] == "PROTEGIDA")
    m = nueva()
    r = rojo(m, "send_email", identidad_id="EMP-01", plantilla="consulta_cordial")
    chk("un correo no malicioso no trae enlace y no puede exponer nada", m.emails[r["data"]["email_id"]]["link_id"] is None)
    m = nueva()
    r = rojo(m, "send_email", identidad_id="EMP-01", plantilla="aviso_soporte")
    lid = m.emails[r["data"]["email_id"]]["link_id"]
    azul(m, "block_link", "Azul1", link_id=lid)
    azul(m, "click_link", "Azul1", link_id=lid)
    azul(m, "risk_action", "Azul1", link_id=lid)
    chk("un enlace neutralizado por Azul no expone la credencial", m.creds["EMP-01"]["estado"] == "PROTEGIDA")
    m = nueva()
    r = rojo(m, "send_email", identidad_id="EMP-01", plantilla="aviso_soporte")
    lid = m.emails[r["data"]["email_id"]]["link_id"]
    azul(m, "suspend_identity", "Azul1", identidad_id="EMP-01")
    azul(m, "risk_action", "Azul1", link_id=lid)
    chk("una identidad suspendida no se compromete aunque pulse el enlace", m.creds["EMP-01"]["estado"] == "SUSPENDIDA")
    chk("correo con URL externa o plantilla inventada se rechaza (INVALID_SCHEMA)", rojo(m, "send_email", identidad_id="EMP-02", plantilla="consulta_cordial", cuerpo="entra a https://externo.example")["reject_reason"] == "INVALID_SCHEMA"
        and rojo(m, "send_email", identidad_id="EMP-02", plantilla="inventada")["reject_reason"] == "INVALID_SCHEMA")
    m = nueva(emails_per_round=2)
    rs = [rojo(m, "send_email", identidad_id="EMP-02", plantilla="consulta_cordial")["reject_reason"] for _ in range(3)]
    chk("límite de frecuencia de correos del Rojo por ronda", rs == [None, None, "BUDGET_EXCEEDED"])
    m = nueva()
    m.avanzar(15)
    chk("los correos programados llegan solos (sin Rojo) y UNA sola vez (scenario_event_id único)", sum(e["scenario_id"] == "SC-01" for e in m.emails.values()) == 1)
    m.avanzar(15)
    n1 = len([e for e in m.emails.values() if e["origen"] == "ESCENARIO"])
    m.tick()
    m.tick()
    chk("repetir tick no duplica correos programados", len([e for e in m.emails.values() if e["origen"] == "ESCENARIO"]) == n1)

    # ── extracción y victoria del Rojo ───────────────────────────────────────────────────────────────
    m = nueva()
    chk("usar o extraer con una identidad cuya credencial el Rojo NO conoce se rechaza (nada de lo no descubierto)", rojo(m, "extract_table", identidad_id="EMP-05", tabla="reportes_financieros")["reject_reason"] == "CREDENTIAL_NOT_KNOWN"
        and rojo(m, "query_resource", identidad_id="EMP-05")["reject_reason"] == "CREDENTIAL_NOT_KNOWN")
    exponer(m, "EMP-05")
    chk("el empleado NO conectado (EMP-05) pulsa el enlace solo, tras el retardo: credencial expuesta y panel Rojo desbloqueado", m.creds["EMP-05"]["estado"] == "COMPROMETIDA")
    q = rojo(m, "query_resource", identidad_id="EMP-05")
    chk("consultar el recurso con la credencial válida funciona y genera alerta por ser protegido", q["ok"] and any("recurso protegido" in a["titulo"] for a in m.alertas.values()))
    chk("una identidad no puede leer tablas de otra (permiso) y el intento queda bloqueado", rojo(m, "extract_table", identidad_id="EMP-05", tabla="ventas")["reject_reason"] == "PERMISSION_DENIED"
        and "extraction.blocked" in tipos(m))
    x = rojo(m, "extract_table", identidad_id="EMP-05", tabla="reportes_financieros")
    chk("W1: extraer reportes_financieros con la credencial válida de EMP-05 da VICTORIA_ROJA por el motor, con evidencia de eventos", x["ok"] and m.resultado["resultado"] == "VICTORIA_ROJA" and m.estado == "FINALIZADA"
        and {"extraction.completed", "win.condition_met", "match.result"} <= set(tipos(m)))
    chk("tras el resultado el resultado es único e inmutable (acciones rechazadas) y está persistido", rojo(m, "scan_directory")["reject_reason"] == "MATCH_NOT_RUNNING"
        and m.db.execute("SELECT COUNT(*) FROM nova_results WHERE match_id=?", (m.id,)).fetchone()[0] == 1)
    chk("la descarga CSV/JSON/SQL contiene SOLO lo extraído", set(__import__("json").loads(m.descarga("json")[1])) == {"reportes_financieros"} and "INSERT INTO reportes_financieros" in m.descarga("sql")[1]
        and "# tabla: reportes_financieros" in m.descarga("csv")[1] and "INSERT INTO ventas" not in m.descarga("sql")[1])
    m0 = nueva()
    chk("sin datos extraídos no hay descarga (NO_DATA)", lanza(lambda: m0.descarga("json"), "NO_DATA"))
    chk("el texto de un modelo no concede victoria: no existe forma de declararla fuera del motor", not hasattr(m0, "declarar_victoria") and m0.resultado is None)
    me = nueva(azules=2)
    exponer(me, "EMP-03")
    ex = rojo(me, "extract_table", identidad_id="EMP-03", tabla="empleados")
    chk("extraer la tabla protegida empleados expone las demás credenciales (cascada del escenario) y alerta crítica", ex["ok"] and all(me.creds[i]["estado"] == "COMPROMETIDA" for i in me.creds)
        and any(a["severidad"] == "CRITICA" for a in me.alertas.values()))
    for iid, tabla in (("EMP-01", "ventas"), ("EMP-01", "detalle_venta"), ("EMP-01", "clientes"), ("EMP-02", "compras"), ("EMP-04", "productos"), ("EMP-04", "inventario"), ("EMP-05", "reportes_financieros")):
        rojo(me, "extract_table", identidad_id=iid, tabla=tabla)
    chk("camino alternativo W2: extraer las 8 tablas una a una con sus credenciales da VICTORIA_ROJA", me.resultado and me.resultado["resultado"] == "VICTORIA_ROJA" and len(me.extraido) >= 1)
    mw = nueva(win={"modo": "any_of", "reglas": ["W2"], "w1_tabla": "reportes_financieros", "w1_identidades": [], "w3_umbral_registros": 50})
    exponer(mw, "EMP-05")
    rojo(mw, "extract_table", identidad_id="EMP-05", tabla="reportes_financieros")
    chk("las condiciones de victoria son configurables: sin W1 extraer solo reportes_financieros no gana", mw.resultado is None)

    # ── aprobaciones / elevación ─────────────────────────────────────────────────────────────────────
    m = nueva()
    chk("export_database sin permiso db_export se rechaza (nadie lo tiene por defecto)", rojo(m, "export_database")["reject_reason"] == "PERMISSION_DENIED")
    e = rojo(m, "request_elevation", motivo="Soy de soporte TI y necesito una copia para el mantenimiento", identidad_id="EMP-03")
    apid = e["data"]["approval_id"]
    chk("la solicitud del Rojo llega a la bandeja de Azul (PENDIENTE, riesgo ALTO, recomendación etiquetada «reglas»)", m.aprobaciones[apid]["estado"] == "PENDIENTE" and m.aprobaciones[apid]["riesgo"] == "ALTO"
        and m.aprobaciones[apid]["recomendacion"]["origen"] == "reglas" and any(a["id"] == apid for a in m.vista_azul("Azul1")["aprobaciones"]))
    azul(m, "request_more_info", approval_id=apid)
    chk("INFO_SOLICITADA: el Rojo puede responder y la decisión sigue abierta", m.aprobaciones[apid]["estado"] == "INFO_SOLICITADA" and rojo(m, "respond_info", approval_id=apid, texto="Ticket TCK-1")["ok"])
    ap = azul(m, "approve_request", approval_id=apid)
    chk("aprobar CAMBIA el estado del escenario: concede db_export por un tiempo", ap["ok"] and m.grants_db_export_hasta > m.t_s() and "credential.permissions_changed" in tipos(m))
    ex = rojo(m, "export_database")
    chk("W2: con la elevación aprobada el Rojo copia la base completa y gana por el motor", ex["ok"] and m.resultado["resultado"] == "VICTORIA_ROJA" and len(m.extraido) == 8)
    m = nueva()
    ap2 = rojo(m, "request_elevation", motivo="Necesito la base")["data"]["approval_id"]
    azul(m, "reject_request", approval_id=ap2)
    chk("rechazar impide la copia: export_database sigue denegado y la decisión es definitiva (409)", rojo(m, "export_database")["reject_reason"] == "PERMISSION_DENIED" and azul(m, "approve_request", approval_id=ap2)["reject_reason"] == "INVALID_TRANSITION")
    m = nueva()
    ap3 = rojo(m, "request_elevation", motivo="x")["data"]["approval_id"]
    m.avanzar(100)
    chk("una solicitud sin respuesta EXPIRA (nunca queda pendiente indefinidamente)", m.aprobaciones[ap3]["estado"] == "EXPIRADA")
    chk("el Rojo no puede aprobar su propia solicitud (WRONG_TEAM)", rojo(m, "approve_request", approval_id=ap3)["reject_reason"] == "WRONG_TEAM")

    # ── Azul, alertas, incidentes, victoria justa ────────────────────────────────────────────────────
    m = nueva()
    exponer(m, "EMP-05")
    al = next(iter(m.alertas))
    chk("una máquina de estados de alerta: NUEVA → EN_ANALISIS → ASIGNADA → CONTENIDA → RESUELTA → CERRADA, sin saltos", azul(m, "set_alert_status", alert_id=al, estado="CONTENIDA")["reject_reason"] == "INVALID_TRANSITION"
        and azul(m, "set_alert_status", alert_id=al, estado="EN_ANALISIS")["ok"])
    inc = next(iter(m.incidentes))
    chk("no se puede contener el incidente mientras haya credenciales comprometidas sin revocar", azul(m, "contain_incident", incident_id=inc)["reject_reason"] == "INVALID_STATE")
    azul(m, "revoke_credential", identidad_id="EMP-05")
    chk("revocar una credencial comprometida impide toda operación posterior del Rojo", rojo(m, "extract_table", identidad_id="EMP-05", tabla="reportes_financieros")["reject_reason"] == "CREDENTIAL_UNUSABLE"
        and next(v for v in m.vista_rojo() if v["id"] == "EMP-05")["estado"] == "BLOQUEADA")
    azul(m, "contain_incident", incident_id=inc)
    m.avanzar(1)
    chk("VICTORIA_AZUL anticipada: credenciales revocadas, incidente CONTENIDO y continuidad ≥ 0,6", m.resultado and m.resultado["resultado"] == "VICTORIA_AZUL" and m.resultado["continuidad"] >= 0.6)
    # rechazar todo no gana
    m = nueva(duration_s=400)
    exponer(m, "EMP-05")
    m.avanzar(160)                    # llegan las solicitudes legítimas SC-05 (150 s)
    for ap in [a for a in m.aprobaciones.values() if a["estado"] == "PENDIENTE" and a["legitima"]]:
        azul(m, "reject_request", approval_id=ap["id"])
    for iid in m.identidades:
        azul(m, "revoke_credential", identidad_id=iid)
    inc = next(iter(m.incidentes))
    azul(m, "contain_incident", incident_id=inc)
    m.avanzar(300)
    chk("«RECHAZAR TODO» no gana: con la continuidad legítima por debajo del umbral el resultado es EMPATE (defensa abusiva)", m.resultado["resultado"] == "EMPATE" and m.resultado["continuidad"] < 0.6)
    chk("revocar identidades que no estaban comprometidas penaliza (falsos positivos) y rechazar solicitudes legítimas también", m.puntos["BLUE"] < 10)
    m = nueva(duration_s=60)
    m.avanzar(70)
    chk("sin ataque y con continuidad suficiente, al agotarse el tiempo gana el Azul", m.resultado["resultado"] == "VICTORIA_AZUL")

    # ── visibilidad, registro y determinismo ─────────────────────────────────────────────────────────
    m = nueva(detect_prob_fail=0.0)
    rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="12345B")
    chk("el Azul NUNCA ve eventos solo-Rojo (los intentos de adivinación) y el Rojo no ve la alerta del Azul", "credential.guess_attempt" not in tipos(m, "BLUE") and "credential.guess_attempt" in tipos(m, "RED"))
    exponer(m, "EMP-05")
    chk("ningún evento de ningún rol contiene valores de credencial en claro", not any(v in str(m.eventos_lista) for v in (c["credencial"] for c in m.catalogo_admin())))
    chk("el espectador ve lo público (resultado, extracciones) pero no correos ni credenciales", "email.received" not in tipos(m, "SPECTATOR") and "credential.validated_by_engine" not in tipos(m, "SPECTATOR"))
    seqs = [e["seq"] for e in m.eventos_lista]
    chk("los eventos tienen seq monótono y se piden por hueco (after_seq)", seqs == sorted(seqs) and len(set(seqs)) == len(seqs) and all(e["seq"] > 5 for e in m.eventos("ADMIN", after_seq=5)))
    chk("cada evento queda persistido (nova_events) con visibilidad y tiempo de partida", m.db.execute("SELECT COUNT(*) FROM nova_events WHERE match_id=?", (m.id,)).fetchone()[0] == len(m.eventos_lista))

    def corrida():
        z = nueva(seed=7)
        rojo(z, "scan_directory")
        exponer(z, "EMP-05")
        rojo(z, "extract_table", identidad_id="EMP-05", tabla="reportes_financieros")
        return [e["type"] for e in z.eventos_lista], dict(z.puntos), z.resultado["resultado"]
    chk("determinismo: la misma semilla y las mismas acciones dan los mismos eventos, puntos y resultado", corrida() == corrida())
    chk("acciones mal formadas o de otro equipo se rechazan con motivo tipificado", m.ejecutar({"action_type": "extract_table"})["reject_reason"] == "INVALID_SCHEMA"
        and rojo(nueva(), "approve_request", approval_id="AP-001")["reject_reason"] == "WRONG_TEAM" and azul(nueva(), "guess_credential", identidad_id="EMP-01", candidate_value="12345A")["reject_reason"] == "WRONG_TEAM")
    # ── modalidades (D13): modifican parámetros reales y quedan congeladas ───────────────────────────
    mr, mb, mn = nueva(modalidad="RED_ADVANTAGE"), nueva(modalidad="BLUE_ADVANTAGE"), nueva()
    chk("las modalidades cuantifican parámetros reales distintos (intentos, cooldown, detección, retardo del clic)", (mr.config["guess_attempts_per_round"], mb.config["guess_attempts_per_round"], mn.config["guess_attempts_per_round"]) == (5, 2, 3)
        and mr.config["detect_prob_fail"] < mn.config["detect_prob_fail"] < mb.config["detect_prob_fail"] and mr.config["click_delay_s"] < mb.config["click_delay_s"])
    rr = [rojo(mr, "guess_credential", identidad_id="EMP-01", candidate_value="77777H")["reject_reason"] for _ in range(1)]
    mr.avanzar(11)
    n_ok = sum(1 for k in range(4) if (mr.avanzar(11) or True) and rojo(mr, "guess_credential", identidad_id="EMP-02", candidate_value=f"8888{k}J")["ok"])
    chk("RED_ADVANTAGE: más intentos por ronda y cooldown corto permiten más adivinación que BLUE_ADVANTAGE (2 por ronda, cooldown 30)", n_ok >= 3 and rojo(mb, "guess_credential", identidad_id="EMP-01", candidate_value="11111A")["ok"]
        and rojo(mb, "guess_credential", identidad_id="EMP-01", candidate_value="11112A")["reject_reason"] == "COOLDOWN")
    rojo(mr, "scan_directory")
    chk("RED_ADVANTAGE cambia la visibilidad: al identificar, el Rojo ve el permiso de la identidad (BALANCED no)", any("permiso" in v for v in mr.vista_rojo()) and not any("permiso" in v for v in (rojo(mn, "scan_directory"), mn.vista_rojo())[1]))
    exponer(mb, "EMP-05")
    chk("BLUE_ADVANTAGE: las alertas llegan con detalle y el empleado tarda más en caer (45 s de retardo)", any("detalle" in a for a in mb.alertas.values()) and mb.config["click_delay_s"] == 45)
    chk("la modalidad queda CONGELADA al iniciar: los parámetros cuantificados guardados al inicio coinciden con los vigentes", json.loads(mb.config_congelada)["modalidad_params"] == mb.config["modalidad_params"] and json.loads(mb.config_congelada)["guess_attempts_per_round"] == mb.config["guess_attempts_per_round"] == 2)
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
