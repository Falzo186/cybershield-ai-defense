"""Constructor de prompts CONTROLADO de Nova: la IA solo se lanza con una directiva de catálogo, consume oportunidades y el motor hace cumplir la directiva.
Incluye el aviso de acceso sospechoso al Azul. Sin Ollama. python -m src.lab.test_nova_prompts"""
import re

from cryptography.fernet import Fernet

from .nova.ia import ControlIA
from .nova.motor import ErrorNova, NovaPartida, Secretos

SEC = Secretos(pepper="p", clave_fernet=Fernet.generate_key())
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


def nueva(**cfg):
    m = NovaPartida(config=cfg, secretos=SEC)
    m.abrir_sala()
    m.unirse("Rojo1", "RED")
    m.unirse("Azul1", "BLUE")
    m.unirse("Azul2", "BLUE")
    m.marcar_lista()
    m.iniciar("ADMIN", True, "k")
    return m, ControlIA(m)


def rojo(m, tipo, **p):
    return m.ejecutar({"action_type": tipo, "actor": {"kind": "human", "team": "RED", "user": "Rojo1"}, "params": p})


def azul(m, tipo, **p):
    return m.ejecutar({"action_type": tipo, "actor": {"kind": "human", "team": "BLUE", "user": "Azul1"}, "params": p})


def dr(**k):
    return {"accion": "scan_directory", "objetivo": "info_administrativa", "estrategia": "ingenieria_social", **k}


def main():
    # ── la IA espera: sin directiva no se lanza nada y no se gasta nada ─────────────────────────────────
    m, ia = nueva()
    ia.configurar("RED", "assist")
    chk("el modo por defecto es controlado con 10 oportunidades por equipo", m.config["ai_prompt_mode"] == "controlado" and ia.oportunidades("RED") == {"usadas": 0, "total": 10, "restantes": 10, "modo": "controlado"})
    chk("sin directiva la IA NO se lanza (DIRECTIVA_REQUIRED), no hay corridas ni oportunidades gastadas", lanza(lambda: ia.proponer("RED"), "DIRECTIVA_REQUIRED") and not ia.runs and ia.usadas["RED"] == 0)
    for malo in (dr(accion="drop_database"), dr(objetivo="hackear_todo"), dr(identidad_id="EMP-99"), dr(tabla="secretos"), dr(plantilla="otra"), dr(estrategia="magia"), "texto libre"):
        chk(f"directiva fuera del catálogo se rechaza sin gastar oportunidad: {str(malo)[:40]}", lanza(lambda malo=malo: ia.proponer("RED", malo)) and ia.usadas["RED"] == 0 and not ia.runs)

    # ── credenciales desbloqueadas: solo las que el Rojo obtuvo ──────────────────────────────────────────
    cr_known = dr(accion="extract_table", objetivo="extraer_tabla", identidad_id="EMP-05", tabla="reportes_financieros", credencial={"modo": "conocida"})
    chk("una credencial «conocida» que el Rojo aún no tiene NO se puede elegir (CREDENTIAL_NOT_KNOWN) y no gasta oportunidad", lanza(lambda: ia.proponer("RED", cr_known), "CREDENTIAL_NOT_KNOWN") and ia.usadas["RED"] == 0)
    rojo(m, "send_email", identidad_id="EMP-05", plantilla="aviso_soporte")
    m.avanzar(m.config["click_delay_s"] + 2)
    run = ia.proponer("RED", cr_known)
    chk("tras comprometer a EMP-05 la credencial queda desbloqueada: la IA recibe la directiva y propone la acción pedida", run["propuesta"]["estado"] == "PROPUESTA" and run["directiva"]["credencial"]["modo"] == "conocida"
        and run["salida_estructurada"]["proposed_action"]["action_type"] == "extract_table" and run["salida_estructurada"]["proposed_action"]["params"]["tabla"] == "reportes_financieros")
    chk("la directiva queda registrada en la corrida y consume 1 oportunidad", ia.usadas["RED"] == 1 and ia.oportunidades("RED")["restantes"] == 9)
    chk("la credencial real nunca viaja al modelo", SEC.descifrar(m.creds["EMP-05"]["enc"]) not in str(run["entrada"]))

    # ── credencial aleatoria con estructura ──────────────────────────────────────────────────────────────
    m, ia = nueva(guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    ia.configurar("RED", "auto")
    run = ia.proponer("RED", dr(accion="guess_credential", objetivo="consultar_inventario", identidad_id="EMP-01", credencial={"modo": "aleatoria", "digitos_iniciales": "12", "letra": "Q"}))
    cand = run["salida_estructurada"]["proposed_action"]["params"]["candidate_value"]
    chk("credencial aleatoria: la candidata respeta la estructura pedida (12xxxQ) y el motor la ejecutó", re.fullmatch(r"12[0-9]{3}Q", cand) and run["propuesta"]["estado"] == "EJECUTADA" and run.get("candidata_ajustada_por_motor") is True)
    chk("estructura inválida o acción distinta de guess_credential se rechaza",
        lanza(lambda: ia.proponer("RED", dr(accion="guess_credential", identidad_id="EMP-01", credencial={"modo": "aleatoria", "digitos_iniciales": "123456"})), "INVALID_SCHEMA")
        and lanza(lambda: ia.proponer("RED", dr(accion="scan_directory", identidad_id="EMP-01", credencial={"modo": "aleatoria"})), "INVALID_SCHEMA")
        and lanza(lambda: ia.proponer("RED", dr(accion="guess_credential", credencial={"modo": "aleatoria"})), "INVALID_SCHEMA"))

    # ── tope de oportunidades ────────────────────────────────────────────────────────────────────────────
    m, ia = nueva(ai_prompt_budget=3)
    ia.configurar("RED", "assist")
    for _ in range(3):
        ia.proponer("RED", dr())
    chk("al agotar las oportunidades el cuarto prompt se rechaza (PROMPT_BUDGET_EXCEEDED) y el contador queda en 0", lanza(lambda: ia.proponer("RED", dr()), "PROMPT_BUDGET_EXCEEDED") and ia.oportunidades("RED")["restantes"] == 0
        and len(ia.runs) == 3)
    chk("las oportunidades son por equipo: el Azul conserva las suyas", ia.oportunidades("BLUE")["restantes"] == 3)

    # ── la directiva manda sobre lo que devuelva el modelo ──────────────────────────────────────────────
    from .test_nova_ia import Fijo
    import json
    m, ia = nueva()
    ia.configurar("RED", "assist", Fijo(json.dumps({"operation_name": "x", "justification": "y", "identity_id": None, "objective": "info_administrativa", "strategy": "ingenieria_social",
                                                  "proposed_action": {"action_type": "export_database", "params": {}}, "risk_level": "BAJO"})))
    r = ia.proponer("RED", dr())
    chk("si el modelo cambia de acción, la propuesta se descarta como INVALIDA (el humano mandó otra cosa)", r["propuesta"]["estado"] == "INVALIDA" and ia.usadas["RED"] == 1)

    # ── Azul: directiva con foco/sujeto/acción ───────────────────────────────────────────────────────────
    m, ia = nueva()
    ia.configurar("BLUE", "assist")
    chk("Azul: sin directiva no se lanza; sujeto inexistente o acción fuera del catálogo se rechazan sin gastar",
        lanza(lambda: ia.proponer("BLUE"), "DIRECTIVA_REQUIRED") and lanza(lambda: ia.proponer("BLUE", {"foco": "alerta", "sujeto_id": "AL-999"}), "UNKNOWN_TARGET")
        and lanza(lambda: ia.proponer("BLUE", {"foco": "alerta", "accion_preferida": "borrar_todo"}), "INVALID_SCHEMA") and ia.usadas["BLUE"] == 0)
    r = ia.proponer("BLUE", {"foco": "identidad", "sujeto_id": "EMP-05", "accion_preferida": "revoke_credential"})
    chk("Azul: la directiva fija la acción recomendada sobre el sujeto elegido", r["propuesta"]["estado"] == "PROPUESTA" and r["salida_estructurada"]["recommended_action"]["action_type"] == "revoke_credential"
        and r["salida_estructurada"]["recommended_action"]["params"] == {"identidad_id": "EMP-05"} and ia.usadas["BLUE"] == 1)

    # ── la IA Azul pide autorización humana por directiva ───────────────────────────────────────────────
    m, ia = nueva()
    ia.configurar("BLUE", "auto")
    chk("pedir autorización con una acción que no es autorizable se rechaza", lanza(lambda: ia.proponer("BLUE", {"foco": "identidad", "sujeto_id": "EMP-05", "accion_preferida": "approve_request", "pedir_autorizacion": True}), "INVALID_SCHEMA")
        and lanza(lambda: ia.proponer("BLUE", {"foco": "identidad", "sujeto_id": "EMP-05", "pedir_autorizacion": True}), "INVALID_SCHEMA"))
    r = ia.proponer("BLUE", {"foco": "identidad", "sujeto_id": "EMP-05", "accion_preferida": "revoke_credential", "pedir_autorizacion": True})
    ap = next(a for a in m.aprobaciones.values() if a["operacion"] == "autorizacion_ia")
    chk("con la directiva, la IA Azul crea una SOLICITUD (no actúa sola) con la directiva y la corrida en el detalle, y la credencial sigue sin revocarse",
        r["propuesta"]["estado"] == "EJECUTADA" and ap["estado"] == "PENDIENTE" and ap["detalle"]["ia"]["directiva"]["pedir_autorizacion"] is True and ap["accion_propuesta"]["action_type"] == "revoke_credential"
        and ap["detalle"]["sujeto"] == "EMP-05" and m.creds["EMP-05"]["estado"] == "PROTEGIDA")
    # ── modo libre sigue disponible (solo ensayos) ───────────────────────────────────────────────────────
    m, ia = nueva(ai_prompt_mode="libre")
    ia.configurar("RED", "assist")
    chk("modo libre: se lanza sin directiva y no consume oportunidades", ia.proponer("RED")["propuesta"]["estado"] == "PROPUESTA" and ia.usadas["RED"] == 0)

    # ── acceso sospechoso: intento casi correcto → solicitud misteriosa para el Azul ─────────────────────
    def casi(m, iid="EMP-01", n=4):
        real = SEC.descifrar(m.creds[iid]["enc"])
        mal = real[:n] + ("0" if real[n] != "0" else "1") + ("A" if real[-1] != "A" else "B") if n == 4 else real[:n]
        return mal

    m, ia = nueva(guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    lejos = rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="99999Z")
    chk("un intento lejano NO abre solicitud sospechosa", not any(a["operacion"] == "acceso_sospechoso" for a in m.aprobaciones.values()) and lejos["ok"])
    r = rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value=casi(m))
    sosp = [a for a in m.aprobaciones.values() if a["operacion"] == "acceso_sospechoso"]
    chk("un intento casi correcto abre una solicitud misteriosa con la identidad, el jugador y la credencial enmascarada", len(sosp) == 1 and sosp[0]["detalle"]["jugador_posible"] and sosp[0]["detalle"]["identidad"] == "EMP-01"
        and "***" in sosp[0]["detalle"]["candidato"] and sosp[0]["riesgo"] == "ALTO" and sosp[0]["estado"] == "PENDIENTE")
    chk("el Rojo no ve la solicitud ni la similitud", not any("approval" in e["type"] for e in m.eventos("RED")) and not [a for a in m.vista_rojo() if "coincidencias" in str(a)])
    chk("el Azul la ve en su panel de solicitudes", any(a["id"] == sosp[0]["id"] for a in m.vista_azul("Azul1")["aprobaciones"]))
    rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value=casi(m))
    chk("no se duplica mientras haya una pendiente para esa identidad", len([a for a in m.aprobaciones.values() if a["operacion"] == "acceso_sospechoso"]) == 1)
    p0 = m.puntos["BLUE"]
    azul(m, "reject_request", approval_id=sosp[0]["id"])
    chk("DENEGAR bloquea la identidad y suma puntos al Azul (cambia el estado)", m.bloqueo_hasta.get("EMP-01", 0) > m.t_s() and m.puntos["BLUE"] == p0 + 5
        and rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value="11111A")["reject_reason"] == "IDENTITY_LOCKED")
    m2, _ = nueva(guess_cooldown_s=0, guess_attempts_per_round=9, detect_prob_fail=0.0)
    rojo(m2, "guess_credential", identidad_id="EMP-02", candidate_value=casi(m2, "EMP-02"))
    ap = next(a for a in m2.aprobaciones.values() if a["operacion"] == "acceso_sospechoso")
    p0 = m2.puntos["BLUE"]
    azul(m2, "approve_request", approval_id=ap["id"])
    chk("ACEPTAR lo da por legítimo: la defensa pierde puntos, no se bloquea y queda el evento", m2.puntos["BLUE"] == p0 - 5 and m2.bloqueo_hasta.get("EMP-02", 0) <= m2.t_s()
        and any(e["type"] == "access.suspicious_accepted" for e in m2.eventos("ADMIN")))
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
