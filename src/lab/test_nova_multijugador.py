"""Nova con 4 Rojos y 4 Azules: cualquier Rojo dirige ataques, todos los Azules ven y opinan las solicitudes, decide el primero o la mayoría.
Lógica pura con reloj virtual. python -m src.lab.test_nova_multijugador"""
import json

from cryptography.fernet import Fernet

from .nova.ia import ControlIA
from .nova.motor import ErrorNova, NovaPartida, Secretos

SEC = Secretos(pepper="p", clave_fernet=Fernet.generate_key())
R = []
ROJOS = ["Rojo1", "Rojo2", "Rojo3", "Rojo4"]
AZULES = ["Azul1", "Azul2", "Azul3", "Azul4"]


def chk(n, c):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n)


def lanza(fn, motivo=None):
    try:
        fn()
    except ErrorNova as e:
        return motivo is None or e.motivo == motivo
    return False


def nueva(**cfg):
    cfg.setdefault("approval_mode", "primero")
    m = NovaPartida(config=cfg, secretos=SEC)
    m.abrir_sala()
    for n in ROJOS:
        m.unirse(n, "RED")
    for n in AZULES:
        m.unirse(n, "BLUE")
    m.marcar_lista()
    m.iniciar("ADMIN", True, "k")
    return m


def rojo(m, user, tipo, **p):
    return m.ejecutar({"action_type": tipo, "actor": {"kind": "human", "team": "RED", "user": user}, "params": p})


def azul(m, user, tipo, **p):
    return m.ejecutar({"action_type": tipo, "actor": {"kind": "human", "team": "BLUE", "user": user}, "params": p})


def suspechosa(m, iid="EMP-01"):
    real = SEC.descifrar(m.creds[iid]["enc"])
    rojo(m, "Rojo2", "guess_credential", identidad_id=iid, candidate_value=real[:4] + ("0" if real[4] != "0" else "1") + ("A" if real[5] != "A" else "B"))
    return next(a for a in m.aprobaciones.values() if a["operacion"] == "acceso_sospechoso")


def main():
    m = NovaPartida(secretos=SEC)
    m.abrir_sala()
    for n in ROJOS + AZULES:
        m.unirse(n, "RED" if n.startswith("Rojo") else "BLUE")
    chk("caben 4 Rojos y 4 Azules, cada Azul con su identidad distinta", len([p for p in m.participantes.values() if p["equipo"] == "RED"]) == 4
        and len({p["identidad"] for p in m.participantes.values() if p["equipo"] == "BLUE"}) == 4)
    chk("un quinto Rojo o un quinto Azul reciben TEAM_FULL", lanza(lambda: m.unirse("Rojo5", "RED"), "TEAM_FULL") and lanza(lambda: m.unirse("Azul5", "BLUE"), "TEAM_FULL"))
    m.marcar_lista()
    m.iniciar("ADMIN", True, "k")

    # ── cualquier Rojo (no solo el primero) dirige ataques ──────────────────────────────────────────
    chk("el Rojo 2, 3 y 4 ejecutan operaciones (no solo el host)", rojo(m, "Rojo2", "scan_directory")["ok"] and rojo(m, "Rojo3", "send_email", identidad_id="EMP-05", plantilla="aviso_soporte")["ok"])
    m.avanzar(m.config["click_delay_s"] + 2)
    chk("lo que consigue un Rojo lo ve todo el equipo: Rojo4 usa la credencial que obtuvo Rojo3", m.creds["EMP-05"]["estado"] == "COMPROMETIDA" and rojo(m, "Rojo4", "query_resource", identidad_id="EMP-05")["ok"])
    chk("las acciones quedan atribuidas a quien las hizo", {a["actor"].get("user") for a in m.acciones if a["ok"]} >= {"Rojo2", "Rojo3", "Rojo4"})
    chk("alguien que no se unió no puede actuar (NOT_A_PLAYER)", rojo(m, "Intruso", "scan_directory")["reject_reason"] == "NOT_A_PLAYER" and azul(m, "Intruso", "allow")["reject_reason"] == "NOT_A_PLAYER")
    chk("un Rojo no puede ejecutar acciones del Azul ni al revés (WRONG_TEAM)", rojo(m, "Rojo1", "revoke_credential", identidad_id="EMP-05")["reject_reason"] == "WRONG_TEAM"
        and azul(m, "Azul1", "scan_directory")["reject_reason"] == "WRONG_TEAM")
    m0 = nueva(guess_attempts_per_round=3, guess_cooldown_s=0, guess_lockout_after_fails=9)
    res = [rojo(m0, u, "guess_credential", identidad_id="EMP-01", candidate_value="99999Z")["reject_reason"] for u in ROJOS]
    chk("el presupuesto de intentos es del equipo, no de cada jugador: el cuarto Rojo ya no tiene intentos", res == [None, None, None, "BUDGET_EXCEEDED"])
    ia = ControlIA(m0)
    ia.configurar("RED", "assist")
    ia.proponer("RED", {"accion": "scan_directory", "objetivo": "info_administrativa"})
    chk("el contador de prompts de IA es del equipo: lo gasta cualquier Rojo", ia.oportunidades("RED")["usadas"] == 1)

    # ── solicitudes: todos los Azules las ven; el primero que interviene es el decisor ───────────────
    m = nueva(guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    ap = suspechosa(m)
    chk("los 4 Azules ven la solicitud con identidad, jugador posible y credencial enmascarada", all(any(x["id"] == ap["id"] for x in m.vista_azul(u)["aprobaciones"]) for u in AZULES)
        and ap["detalle"]["jugador_posible"] and "***" in ap["detalle"]["candidato"])
    chk("el Rojo no ve votos ni decisor de las solicitudes del Azul", "votos" not in json.dumps(m.vista_rojo()))
    chk("un voto de opinión de Azul3 lo convierte en el decisor y no cierra la solicitud", azul(m, "Azul3", "vote_request", approval_id=ap["id"], voto="RECHAZAR", comentario="No fui yo")["data"].get("voto_registrado")
        and ap["decisor"] == "Azul3" and ap["estado"] == "PENDIENTE")
    r = azul(m, "Azul1", "approve_request", approval_id=ap["id"])
    chk("un Azul que NO es el decisor no cierra por su cuenta: su aprobación cuenta como voto de opinión", r["ok"] and r["data"].get("voto_registrado") and ap["estado"] == "PENDIENTE" and ap["votos"]["Azul1"]["voto"] == "APROBAR")
    chk("los votos y comentarios son visibles para los Azules", m.vista_azul("Azul4")["aprobaciones"][0]["votos"]["Azul3"]["comentario"] == "No fui yo")
    chk("el decisor cierra de inmediato y se aplica la consecuencia (identidad bloqueada)", azul(m, "Azul3", "reject_request", approval_id=ap["id"])["ok"] and ap["estado"] == "RECHAZADA" and m.bloqueo_hasta.get("EMP-01", 0) > m.t_s())
    chk("una solicitud ya cerrada no admite más votos ni decisiones", azul(m, "Azul2", "vote_request", approval_id=ap["id"], voto="APROBAR")["reject_reason"] == "INVALID_TRANSITION"
        and azul(m, "Azul2", "approve_request", approval_id=ap["id"])["reject_reason"] == "INVALID_TRANSITION")
    chk("voto inválido se rechaza", azul(m, "Azul1", "vote_request", approval_id="AP-999", voto="APROBAR")["reject_reason"] == "UNKNOWN_TARGET")

    # ── cierre por mayoría ─────────────────────────────────────────────────────────────────────────
    m = nueva(guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    ap = suspechosa(m, "EMP-02")
    azul(m, "Azul1", "vote_request", approval_id=ap["id"], voto="APROBAR")
    azul(m, "Azul2", "vote_request", approval_id=ap["id"], voto="RECHAZAR")
    chk("2 contra 1 de 4 todavía no es mayoría absoluta", ap["estado"] == "PENDIENTE")
    azul(m, "Azul3", "vote_request", approval_id=ap["id"], voto="RECHAZAR")
    azul(m, "Azul4", "vote_request", approval_id=ap["id"], voto="RECHAZAR")
    chk("3 de 4 es mayoría absoluta: la solicitud se cierra sola con el voto mayoritario y el evento lo dice", ap["estado"] == "RECHAZADA" and any(e["type"] == "approval.rejected" for e in m.eventos("BLUE")))
    m = nueva(guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    ap = suspechosa(m, "EMP-03")
    for u, v in (("Azul2", "APROBAR"), ("Azul1", "RECHAZAR"), ("Azul3", "APROBAR"), ("Azul4", "RECHAZAR")):
        azul(m, u, "vote_request", approval_id=ap["id"], voto=v)
    chk("empate 2 a 2 con todos votados: manda el voto del decisor (el primero, Azul2: APROBAR)", ap["decisor"] == "Azul2" and ap["estado"] == "APROBADA")
    chk("el Rojo y el espectador no pueden votar", m.ejecutar({"action_type": "vote_request", "actor": {"kind": "human", "team": "RED", "user": "Rojo1"}, "params": {"approval_id": ap["id"], "voto": "APROBAR"}})["reject_reason"] == "WRONG_TEAM")

    # ── la IA Azul pide autorización: todos la ven, con detalle, y la acción solo se ejecuta si se aprueba ──
    m = nueva()
    rojo(m, "Rojo1", "send_email", identidad_id="EMP-05", plantilla="aviso_soporte")
    m.avanzar(m.config["click_delay_s"] + 2)
    r = azul(m, "Azul1", "request_authorization", motivo="credencial comprometida", accion_propuesta={"action_type": "revoke_credential", "params": {"identidad_id": "EMP-05"}}, identidad_id="EMP-05")
    apid = r["data"]["approval_id"]
    ap = m.aprobaciones[apid]
    d = ap["detalle"]
    chk("la solicitud de autorización trae qué pide, sobre quién, credencial enmascarada, quién la origina y la hora", d["que_pide"] == "revoke_credential" and d["sujeto"] == "EMP-05" and "***" in d["credencial"]
        and d["solicitante"] == "Azul1" and d["hora_real"] and d["hora_partida_s"] >= 0)
    chk("pedir autorización NO ejecuta la acción: la credencial sigue comprometida", m.creds["EMP-05"]["estado"] == "COMPROMETIDA")
    chk("una acción no autorizable (aprobar solicitudes) no se puede pedir como autorización", azul(m, "Azul1", "request_authorization", accion_propuesta={"action_type": "approve_request", "params": {}})["reject_reason"] == "INVALID_SCHEMA")
    for u in ("Azul2", "Azul3", "Azul4"):
        azul(m, u, "vote_request", approval_id=apid, voto="APROBAR")
    chk("mayoría que aprueba: el motor ejecuta la acción autorizada y solo esa (credencial revocada)", ap["estado"] == "APROBADA" and ap["ejecucion"]["ok"] and m.creds["EMP-05"]["estado"] in ("REVOCADA", "SUSPENDIDA"))
    m = nueva()
    r = azul(m, "Azul1", "request_authorization", motivo="x", accion_propuesta={"action_type": "revoke_credential", "params": {"identidad_id": "EMP-04"}}, identidad_id="EMP-04")
    for u in ("Azul2", "Azul3", "Azul4"):
        azul(m, u, "vote_request", approval_id=r["data"]["approval_id"], voto="RECHAZAR")
    chk("mayoría que rechaza: la acción NO se ejecuta", m.aprobaciones[r["data"]["approval_id"]]["estado"] == "RECHAZADA" and m.creds["EMP-04"]["estado"] == "PROTEGIDA")

    # ── IA Azul real (simulada) → solicitud ──────────────────────────────────────────────────────────
    from .nova.ia import ScriptedProvider
    m = nueva()
    ia = ControlIA(m)
    ia.configurar("BLUE", "auto", ScriptedProvider("BLUE"))
    run = ia.proponer("BLUE", {"foco": "identidad", "sujeto_id": "EMP-05", "accion_preferida": "revoke_credential"})
    chk("la directiva del Azul con la IA en auto ejecuta la acción (revocación directa)", run["propuesta"]["estado"] == "EJECUTADA")
    # ── modo votación: responder = opinar; cierra la mayoría o el fin de la ventana; empate → decisor ─────────
    m = nueva(approval_mode="votacion", approval_window_s=15, guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    ap = suspechosa(m, "EMP-01")
    r = azul(m, "Azul2", "approve_request", approval_id=ap["id"], comentario="Fui yo")
    chk("votación: la primera respuesta NO cierra sola (opina), fija al decisor y abre la ventana de 15 s", r["data"]["voto_registrado"] and ap["estado"] == "PENDIENTE" and ap["decisor"] == "Azul2" and ap["cierra_s"] is not None)
    azul(m, "Azul3", "reject_request", approval_id=ap["id"], comentario="No lo conozco")
    chk("los demás opinan y todos ven los votos con sus comentarios", {u: v["voto"] for u, v in m.vista_azul("Azul4")["aprobaciones"][0]["votos"].items()} == {"Azul2": "APROBAR", "Azul3": "RECHAZAR"})
    azul(m, "Azul1", "reject_request", approval_id=ap["id"])
    chk("2 en contra y 1 a favor de 4 todavía no es mayoría absoluta: sigue abierta", ap["estado"] == "PENDIENTE")
    azul(m, "Azul4", "reject_request", approval_id=ap["id"])
    chk("3 de 4 en contra cierra la solicitud al instante, aunque el decisor votara a favor", ap["estado"] == "RECHAZADA" and m.bloqueo_hasta.get("EMP-01", 0) > m.t_s())
    m = nueva(approval_mode="votacion", approval_window_s=15, guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    ap = suspechosa(m, "EMP-02")
    azul(m, "Azul3", "reject_request", approval_id=ap["id"])
    m.avanzar(10)
    chk("antes de que termine la ventana la solicitud sigue abierta", ap["estado"] == "PENDIENTE")
    m.avanzar(10)
    chk("al terminar la ventana se aplica el voto del decisor si nadie más opinó (Azul3: rechazar)", ap["estado"] == "RECHAZADA" and any(e["type"] == "approval.rejected" for e in m.eventos("BLUE")))
    m = nueva(approval_mode="votacion", approval_window_s=15, guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    ap = suspechosa(m, "EMP-03")
    azul(m, "Azul4", "approve_request", approval_id=ap["id"])
    azul(m, "Azul2", "reject_request", approval_id=ap["id"])
    m.avanzar(20)
    chk("empate 1 a 1 al cerrar la ventana: manda el decisor (Azul4, el primero en responder: APROBAR)", ap["estado"] == "APROBADA" and ap["decisor"] == "Azul4")
    m1 = NovaPartida(config={"approval_mode": "votacion", "guess_cooldown_s": 0, "detect_prob_fail": 0.0}, secretos=SEC)
    m1.abrir_sala(); m1.unirse("Rojo1", "RED"); m1.unirse("Azul1", "BLUE"); m1.marcar_lista(); m1.iniciar("ADMIN", True, "k")
    real = SEC.descifrar(m1.creds["EMP-01"]["enc"])
    m1.ejecutar({"action_type": "guess_credential", "actor": {"kind": "human", "team": "RED", "user": "Rojo1"}, "params": {"identidad_id": "EMP-01", "candidate_value": real[:4] + ("0" if real[4] != "0" else "1") + ("A" if real[5] != "A" else "B")}})
    ap1 = next(a for a in m1.aprobaciones.values() if a["operacion"] == "acceso_sospechoso")
    azul(m1, "Azul1", "reject_request", approval_id=ap1["id"])
    chk("con un solo Azul en la partida su respuesta cierra de inmediato (mayoría absoluta de 1)", ap1["estado"] == "RECHAZADA")
    m = nueva(approval_mode="votacion", guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    ap = suspechosa(m, "EMP-04")
    r = m.ejecutar({"action_type": "reject_request", "actor": {"kind": "ai", "team": "BLUE", "user": "IA BLUE"}, "params": {"approval_id": ap["id"]}})
    chk("la IA Azul en modo auto y el administrador no esperan votación (decisión inmediata)", r["ok"] and ap["estado"] == "RECHAZADA")
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
