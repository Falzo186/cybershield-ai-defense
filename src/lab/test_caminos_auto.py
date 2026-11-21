"""Pruebas del modo automático de credenciales con proveedores deterministas (sin Ollama). python -m src.lab.test_caminos_auto"""
import json

from . import caminos as _c  # noqa: F401
from .caminos import auto as A, proveedores as P
from .caminos.motor import ErrorCaminos
from .wazuh_sim import SimProvider
from .combate.store import Almacen

R = []


def chk(n, c):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n)


class Muerto:
    es_ia, nombre = True, "muerto"

    def decidir(self, ctx):
        return {"ok": False, "meta": {"modelo": "m", "error": "caído", "llamadas": 1}}


class Malo:
    es_ia, nombre = True, "malo"

    def decidir(self, ctx):
        return {"ok": True, "opcion": "C-99|vpn", "mensaje": "", "meta": {"modelo": "m", "llamadas": 1}}


def ev(p, tipo):
    return [e for e in p.almacen.eventos(p.id) if e["tipo"] == tipo]


def main():
    # contramedidas
    p = A.jugar(P.Guion(["C-04|externo"] * 5), P.AzulRegistro(), semilla=3)
    aut = [e["payload"]["resultado"] for e in ev(p, "motor.autenticacion")]
    chk("lockout: tres fallos bloquean la cuenta y los intentos posteriores reciben «cuenta_bloqueada»", aut[:3] == ["fallo"] * 3 and "cuenta_bloqueada" in aut)
    chk("las alertas de intentos repetidos (a los 2 fallos) y de cuenta bloqueada (a los 3) se emiten como Wazuh SIMULADO",
        {"caminos.intentos_repetidos", "caminos.cuenta_bloqueada"} <= {e["payload"]["clave"] for e in ev(p, "caminos.alerta")})
    ph = A.jugar(P.Guion(["C-07|portal_interno"]), P.AzulFijo("aprobar"), semilla=3)
    chk("honeytoken: alerta crítica, cuenta bloqueada y VICTORIA_AZUL inmediata (aunque el Azul apruebe todo)", ph.resultado["resultado"] == "VICTORIA_AZUL" and ph.resultado["hoja"] == "honeytoken"
        and ph.resultado["metricas"]["rojo"]["honeytoken"] == 1)
    # compromiso legítimo de credenciales
    pv = A.jugar(P.Guion(["C-01|portal_interno"]), P.AzulFijo("aprobar"), semilla=3)
    chk("credencial válida del gerente sin señales y Azul «APROBAR siempre»: el Rojo GANA (el motor entrega la base)", pv.resultado["resultado"] == "VICTORIA_ROJA" and not pv.resultado["base_integra"]
        and len(ev(pv, "motor.base_entregada")) == 1)
    pr = A.jugar(P.Guion(["C-01|externo", "C-01|externo", "C-01|externo"] * 4), P.AzulRegistro(), semilla=3)
    chk("la misma credencial válida con señales de riesgo y verificación exigida NO gana (Azul por registro)", pr.resultado["resultado"] in ("VICTORIA_AZUL", "EMPATE_DEGRADADO") and pr.resultado["base_integra"])
    chk("Azul por registro atiende a los legítimos y gana por turnos", pr.resultado["resultado"] == "VICTORIA_AZUL" and (pr.tasa_legitimas() or 0) >= 0.7)
    prr = A.jugar(P.PrimeraOpcion(), P.AzulFijo("rechazar"), semilla=3)
    chk("Azul «rechazar siempre»: la base queda íntegra pero falla a los legítimos -> EMPATE_DEGRADADO (no es victoria Azul)", prr.resultado["resultado"] == "EMPATE_DEGRADADO" and prr.resultado["base_integra"])
    # visibilidad
    p0 = A.PartidaAuto(P.PrimeraOpcion(), P.AzulRegistro(), semilla=3, almacen=Almacen(":memory:"))
    cr = json.dumps(p0.ctx_rojo(), ensure_ascii=False)
    chk("el contexto del Rojo no revela la validez de las credenciales (ni «honeytoken», ni «válida/inválida»)", "honeytoken" not in cr.lower() and "valida" not in cr.lower() and "inválida" not in cr.lower() and cr.count("C-0") >= 8)
    ca = json.dumps(p0.ctx_azul({"origen": "rojo", "cid": "C-01", "canal": "externo", "mensaje": "hola"}), ensure_ascii=False)
    chk("el contexto del Azul no incluye el inventario del Rojo ni la verdad de fondo (solo la identidad que se presenta)", "inventario" not in ca and "C-07" not in ca and "honeytoken" not in ca.lower())
    # robustez
    pm = A.jugar(Muerto(), P.AzulRegistro(), semilla=3)
    chk("modelo del Rojo sin respuesta 3 veces: INCONCLUSA (excluida de las tasas)", pm.resultado["resultado"] == "INCONCLUSA" and pm.resultado["causa"] == "errores")
    pa = A.jugar(P.Guion(["C-04|externo", "C-05|externo", "C-06|externo"] * 10), P.AzulRegistro(), semilla=7)
    chk("presupuesto de turnos: con credenciales inútiles se agotan los turnos y el resultado lo da el motor (nadie gana por mensaje)", pa.resultado["turnos_jugados"] <= 12 and pa.resultado["resultado"] in ("VICTORIA_AZUL", "EMPATE_DEGRADADO"))
    pj = A.jugar(Malo(), P.AzulRegistro(), semilla=3)
    chk("opciones fuera del menú se rechazan y a la 3.ª queda INCONCLUSA", pj.resultado["resultado"] == "INCONCLUSA" and pj.resultado["opciones_invalidas"] == 3)
    # determinismo, inmutabilidad, congelado
    a1, a2 = A.jugar(P.Aleatorio(4), P.Aleatorio(9), semilla=5), A.jugar(P.Aleatorio(4), P.Aleatorio(9), semilla=5)
    chk("determinismo: misma semilla -> mismos eventos y hashes", [e["hash"] for e in a1.almacen.eventos(a1.id)] == [e["hash"] for e in a2.almacen.eventos(a2.id)])
    try:
        pv.paso()
        ok = False
    except ErrorCaminos as e:
        ok = e.status == 409
    chk("tras el resultado, cualquier acción da 409", ok and len(ev(pv, "partida.resultado")) == 1)
    pq = A.PartidaAuto(P.PrimeraOpcion(), P.AzulRegistro(), semilla=3, almacen=Almacen(":memory:"))
    pq._e["credenciales"][3]["estado"] = "valida"
    chk("el escenario se congela por hash: alterarlo corta la partida", pq.paso()["resultado"] == "ERROR_TECNICO")
    chk("el tipo se declara: líneas base/guiones = CAMINOS_GUION", pv.resultado["tipo"] == "CAMINOS_GUION" and pv.resultado["modo"] == "automatico")
    chk("la cadena de hashes es íntegra y el tráfico legítimo es 30-40 % de la agenda", pv.almacen.verificar_cadena(pv.id)[0] and 3 <= pv.agenda.count("legit") <= 5)
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
