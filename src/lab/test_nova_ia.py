"""Pruebas de la capa de IA de Nova (proveedores falsos y etiquetados; sin Ollama). python -m src.lab.test_nova_ia"""
import json
import threading

from cryptography.fernet import Fernet

from .nova import escenario as E
from .nova.ia import ControlIA, OfflineProvider, ScriptedProvider, validar_endpoint, validar_propuesta_rojo, validar_veredicto_azul
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


class Fijo:
    """Proveedor que devuelve un texto fijo (para probar JSON inválido y esquemas)."""
    kind, etiqueta, endpoint, modelo = "scripted", "SIMULADO – no es una IA", None, "fijo"

    def __init__(self, texto, ok=True):
        self.texto, self.ok, self.llamadas = texto, ok, 0

    def generar(self, system, user, timeout=30):
        self.llamadas += 1
        return {"ok": self.ok, "contenido": self.texto, "error": None if self.ok else "caído", "tiempo_ms": 2, "tokens": 5}


def main():
    m, ia = nueva()
    chk("por defecto la IA está en modo off en los dos equipos: proponer se rechaza (AI_OFF)", lanza(lambda: ia.proponer("RED"), "AI_OFF") and lanza(lambda: ia.proponer("BLUE"), "AI_OFF"))
    ia.configurar("RED", "assist")
    run = ia.proponer("RED")
    chk("assist: la IA propone y NADA se ejecuta hasta que un humano confirme", run["estado"] == "COMPLETADA" and run["propuesta"]["estado"] == "PROPUESTA" and not m.extraido and sum(a["ok"] for a in m.acciones) == 0)
    chk("la corrida queda registrada con provider_kind=scripted (etiquetada como simulada), modelo, entrada y salida estructurada", run["provider_kind"] == "scripted" and run["salida_estructurada"]["proposed_action"]["action_type"] == "scan_directory"
        and m.db.execute("SELECT provider_kind, estado FROM nova_ai_runs WHERE run_id=?", (run["run_id"],)).fetchone() == ("scripted", "COMPLETADA"))
    res = ia.confirmar(run["run_id"], "Rojo1")
    chk("confirmar ejecuta la propuesta por el MISMO pipeline del motor (actor humano) y queda EJECUTADA", res["estado"] == "EJECUTADA" and any(v["estado"] == "IDENTIFICADA" for v in m.vista_rojo()))
    chk("confirmar dos veces la misma propuesta se rechaza (409)", lanza(lambda: ia.confirmar(run["run_id"], "Rojo1"), "INVALID_STATE"))
    ia.configurar("RED", "off")
    chk("el modo off de un equipo no afecta al otro (modos independientes por equipo)", ia.modo("RED") == "off" and ia.modo("BLUE") == "off" and lanza(lambda: ia.configurar("RED", "otro")))

    # IA Roja en auto: juega sola dentro de las validaciones y gana por el motor
    m, ia = nueva()
    ia.configurar("RED", "auto")
    for _ in range(4):
        ia.proponer("RED")
        m.avanzar(30)
        if m.resultado:
            break
    chk("auto: la IA Roja (scripted) reconoce, envía un correo, espera la exposición y extrae: VICTORIA_ROJA decidida por el motor", m.resultado and m.resultado["resultado"] == "VICTORIA_ROJA")
    chk("las acciones de la IA quedan con actor kind=ai y su ai_run_id", any(a["actor"].get("kind") == "ai" and a["actor"].get("ai_run_id") for a in m.acciones))
    chk("cada corrida está persistida con estado y latencia", m.db.execute("SELECT COUNT(*) FROM nova_ai_runs WHERE match_id=?", (m.id,)).fetchone()[0] >= 3)
    ctx = json.dumps(m.eventos_lista, ensure_ascii=False)
    chk("la IA nunca escribe en el estado: sin pasar por el pipeline no hay efecto (no hay API para ello)", not hasattr(ia, "aplicar_directo"))

    # contexto del Rojo sin secretos
    m, ia = nueva()
    ctx = json.dumps(__import__("src.lab.nova.ia", fromlist=["contexto_rojo"]).contexto_rojo(m), ensure_ascii=False)
    chk("el contexto del Rojo no contiene ninguna credencial ni el catálogo (solo patrón y estados)", not any(c["credencial"] in ctx for c in m.catalogo_admin()) and "5 dígitos" not in ctx and E.PATRON_CREDENCIAL in ctx)
    from .nova.ia import contexto_azul
    cza = json.dumps(contexto_azul(m), ensure_ascii=False)
    chk("el contexto del Azul trae identidades, permisos y estados (para decidir) pero ni valores de credencial ni el inventario del Rojo", "permiso" in cza and not any(c["credencial"] in cza for c in m.catalogo_admin()) and "rojo_conoce" not in cza)

    # robustez
    m, ia = nueva()
    ia.configurar("RED", "assist")
    ia.configurar("RED", proveedor=Fijo("esto no es json"))
    r = ia.proponer("RED")
    chk("JSON inválido: 1 reintento y la propuesta queda INVALIDA (no se inventa nada) y la partida sigue", r["propuesta"]["estado"] == "INVALIDA" and r["reintentos"] == 1 and m.estado == "EN_CURSO")
    ia.configurar("RED", proveedor=Fijo(json.dumps({"operation_name": "x", "justification": "y", "objective": "copia_bd", "strategy": "ingenieria_social", "risk_level": "ALTO", "proposed_action": {"action_type": "borrar_todo", "params": {}}})))
    chk("una acción fuera del catálogo se rechaza por esquema (INVALIDA)", ia.proponer("RED")["propuesta"]["estado"] == "INVALIDA")
    ia.configurar("RED", proveedor=OfflineProvider())
    r = ia.proponer("RED")
    chk("proveedor desconectado: FALLIDA con error claro, sin respuesta inventada y la partida sigue utilizable", r["estado"] == "FALLIDA" and r["error"] and m.estado == "EN_CURSO" and m.ejecutar({"action_type": "scan_directory", "actor": {"team": "RED", "user": "Rojo1"}})["ok"])
    chk("el error de un proveedor no deja la corrida colgada: se puede volver a proponer", ia._activa["RED"] is None)

    class Tarde:
        kind, etiqueta, endpoint, modelo = "scripted", "SIMULADO – no es una IA", None, "tarde"

        def generar(self, system, user, timeout=30):
            m.pausar()      # la partida se pausa mientras «piensa» el modelo
            return {"ok": True, "contenido": json.dumps(ScriptedProvider("RED")._rojo({"identidades": m.vista_rojo(), "extraido": [], "enviado_a": {}})), "error": None, "tiempo_ms": 5, "tokens": None}
    m, ia = nueva()
    ia.configurar("RED", "auto")
    ia.configurar("RED", proveedor=Tarde())
    r = ia.proponer("RED")
    chk("una respuesta tardía (la partida se pausó mientras tanto) se IGNORA: no ejecuta nada", r["estado"] == "IGNORADA_TARDIA" and sum(a["ok"] for a in m.acciones) == 0 and "ai.run_late_ignored" in [e["type"] for e in m.eventos_lista])

    class Lento:
        kind, etiqueta, endpoint, modelo = "scripted", "SIMULADO – no es una IA", None, "lento"

        def __init__(self):
            self.entra, self.sale = threading.Event(), threading.Event()

        def generar(self, system, user, timeout=30):
            self.entra.set()
            self.sale.wait(5)
            return {"ok": False, "contenido": None, "error": "x", "tiempo_ms": 1, "tokens": None}
    m, ia = nueva()
    ia.configurar("RED", "assist")
    lento = Lento()
    ia.configurar("RED", proveedor=lento)
    t = threading.Thread(target=lambda: ia.proponer("RED"))
    t.start()
    lento.entra.wait(3)
    chk("no hay inferencias duplicadas: una segunda petición del mismo equipo mientras corre la primera da AI_BUSY", lanza(lambda: ia.proponer("RED"), "AI_BUSY"))
    lento.sale.set()
    t.join(5)
    chk("al terminar la primera, el equipo queda libre", ia._activa["RED"] is None)

    # la IA Azul pide autorización humana
    m, ia = nueva()
    ia.configurar("BLUE", "auto")
    ia.configurar("BLUE", proveedor=Fijo(json.dumps({"verdict": "SOLICITAR_AUTORIZACION", "classification": "AMBIGUA", "confidence": 0.4, "subject": {"kind": "request", "id": "AP-001"}, "reasoning": "no está claro si es legítima",
                                                    "evidence": [], "recommended_action": {"action_type": "allow", "params": {}}})))
    r = ia.proponer("BLUE")
    chk("SOLICITAR_AUTORIZACION: la IA Azul NO actúa sola: crea una tarea para los jugadores humanos", r["propuesta"]["estado"] == "EJECUTADA" and any("Autorizar la acción propuesta por la IA Azul" in t["titulo"] for t in m.tareas.values()))

    # esquemas
    chk("validar_propuesta_rojo exige campos, catálogo de objetivo/estrategia, acción del Rojo y candidatas con el patrón", lanza(lambda: validar_propuesta_rojo({}), "INVALID_SCHEMA")
        and lanza(lambda: validar_propuesta_rojo({"operation_name": "a", "justification": "b", "objective": "copia_bd", "strategy": "adivinacion", "risk_level": "BAJO", "proposed_action": {"action_type": "guess_credential"}, "candidate_credentials": ["abc"]}), "INVALID_SCHEMA"))
    chk("validar_veredicto_azul exige veredicto del catálogo, confianza 0–1 y acción del Azul", lanza(lambda: validar_veredicto_azul({"verdict": "PERMITIR", "classification": "LEGITIMA", "confidence": 3, "recommended_action": {"action_type": "allow"}}), "INVALID_SCHEMA")
        and validar_veredicto_azul({"verdict": "PERMITIR", "classification": "LEGITIMA", "confidence": 0.5, "recommended_action": {"action_type": "allow"}}))

    # IA Azul y «rechazar todo»
    m, ia = nueva(duration_s=400)
    ia.configurar("BLUE", "auto")
    ia.configurar("BLUE", proveedor=ScriptedProvider("BLUE", "rechazar_todo"))
    m.avanzar(160)
    for _ in range(3):
        ia.proponer("BLUE")
    m.avanzar(300)
    chk("línea base «rechazar todo» con la IA Azul: rechaza solicitudes legítimas, la continuidad cae y el resultado NO es victoria Azul", m.resultado["resultado"] != "VICTORIA_AZUL" and m.continuidad() < 0.6)
    m, ia = nueva(duration_s=400)
    ia.configurar("BLUE", "auto")
    m.avanzar(210)
    for _ in range(4):
        ia.proponer("BLUE")
    m.avanzar(300)
    chk("la IA Azul razonable (scripted) aprueba lo legítimo y mantiene la continuidad: gana por tiempo", m.resultado["resultado"] == "VICTORIA_AZUL" and m.continuidad() >= 0.6)
    m, ia = nueva()
    ia.configurar("RED", "auto")
    ia.configurar("BLUE", "auto")
    m.pausar()
    chk("en pausa no se puede proponer (MATCH_NOT_RUNNING)", lanza(lambda: ia.proponer("RED"), "MATCH_NOT_RUNNING"))

    # anti-SSRF
    chk("anti-SSRF: loopback y red privada pasan; IP pública, esquema raro, credenciales en la URL y rutas se rechazan",
        validar_endpoint("http://127.0.0.1:11434") == "http://127.0.0.1:11434" and validar_endpoint("localhost") == "http://localhost:11434"
        and all(lanza(lambda u=u: validar_endpoint(u), "SSRF_BLOCKED") for u in ("http://8.8.8.8:11434", "file:///etc/passwd", "http://user:pw@127.0.0.1:11434", "http://127.0.0.1:11434/api/pull", "ftp://127.0.0.1")))
    chk("la lista permitida restringe los endpoints aunque sean privados", lanza(lambda: validar_endpoint("http://127.0.0.1:11434", permitidos=["192.168.1.50"]), "SSRF_BLOCKED"))
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
