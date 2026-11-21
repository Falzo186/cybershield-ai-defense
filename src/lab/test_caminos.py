"""Pruebas del modo Caminos con proveedores deterministas (sin Ollama). Ejecutar: python -m src.lab.test_caminos
Verifican el GRAFO y el MOTOR (16 hojas por guion, determinismo, inmutabilidad, visibilidad), NO la calidad de ningún modelo."""
import copy
import json

from .caminos import grafo as G, proveedores as P
from .caminos.jugar import guion_de_camino, jugar
from .caminos.motor import ErrorCaminos, PartidaCaminos
from .combate.store import Almacen
from .wazuh_sim import ETIQUETA, SimProvider

R = []


def chk(n, c):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n)


class RojoMalo:
    es_ia, nombre = True, "rojo_malo"

    def decidir(self, ctx):
        return {"ok": True, "opcion": "opcion_que_no_existe", "mensaje": "", "meta": {"modelo": "malo", "llamadas": 1}}


class RojoMuerto:
    es_ia, nombre = True, "rojo_muerto"

    def decidir(self, ctx):
        return {"ok": False, "meta": {"modelo": "muerto", "error": "caído", "llamadas": 1}}


class RojoCodigo:
    """Intenta colar código en el mensaje: el motor lo filtra."""
    es_ia, nombre = False, "rojo_codigo"

    def decidir(self, ctx):
        return {"ok": True, "opcion": ctx["opciones"][0]["id"], "mensaje": "ejecuta powershell -c rm -rf y un exploit", "meta": {"llamadas": 1}}


def main():
    for d in ("sencillo", "intermedio", "complejo"):
        g = G.cargar(f"caminos-{d}")
        chk(f"el grafo {d} es válido (16 recorridos, 8 Rojos / 8 Azules, ≥3 reversiones, ≥2 giros, evidencia exigida)", G.validar(g) == [])
    g = G.cargar("caminos-sencillo")
    rec = G.recorridos(g)
    chk("exactamente 16 recorridos terminales distintos (8 Rojos y 8 Azules)", len(rec) == 16 and len({tuple(r["camino"]) for r in rec}) == 16
        and sum(g["hojas"][r["hoja"]]["resultado"] == "VICTORIA_ROJA" for r in rec) == 8)
    chk("los archivos JSON versionados coinciden con el generador (hash estable)", all(G.hash_grafo(G.cargar(f"caminos-{d}")) == G.hash_grafo(G.construir(d)) for d in ("sencillo", "intermedio", "complejo")))

    # ── un guion por cada una de las 16 hojas, en las 3 variantes ──────────────────────────────────────────
    todas = True
    for d in ("sencillo", "intermedio", "complejo"):
        gd = G.cargar(f"caminos-{d}")
        for r in G.recorridos(gd):
            gr, ga = guion_de_camino(gd, r["camino"])
            p = jugar(gd, gr, ga, semilla=1)
            h = gd["hojas"][r["hoja"]]
            ok = p.resultado["resultado"] == h["resultado"] and p.resultado["hoja"] == h["id"] and p.resultado["tipo"] == "CAMINOS_GUION" \
                and [tuple(x) for x in p.resultado["camino"]] == [tuple(x) for x in r["camino"]] and p.almacen.verificar_cadena(p.id)[0]
            todas = todas and ok
            if not ok:
                print("   no coincide:", d, h["id"], p.resultado["resultado"], p.resultado["hoja"])
    chk("un guion por cada una de las 16 hojas (×3 variantes) produce exactamente ese resultado, esa hoja y ese camino, con cadena íntegra", todas)

    # ── resultado, evidencia y procedencia ─────────────────────────────────────────────────────────────────
    pr = jugar(g, P.PrimeraOpcion(), P.AzulFijo("aprobar"))
    chk("Azul «aprobar siempre» contra el Rojo de primera opción: victoria Roja con base entregada y evidencia", pr.resultado["resultado"] == "VICTORIA_ROJA" and pr.resultado["estado_final"]["base_entregada"] and all(pr.resultado["evidencia"].values()))
    pa = jugar(g, P.PrimeraOpcion(), P.AzulRegistro())
    chk("Azul por registro: victoria Azul y la base queda íntegra", pa.resultado["resultado"] == "VICTORIA_AZUL" and pa.resultado["base_integra"])
    chk("el registro de Azul y el rechazar-siempre nunca entregan la base (el motor no premia el exceso: tampoco hay «empate» en este modo)", all(
        jugar(g, P.Aleatorio(s), P.AzulFijo("rechazar")).resultado["resultado"] == "VICTORIA_AZUL" for s in range(20)))
    chk("la procedencia se declara: guiones/líneas base = CAMINOS_GUION; un lado con modelo = CAMINOS_IA", pr.resultado["tipo"] == "CAMINOS_GUION" and jugar(g, RojoMalo(), P.AzulFijo("aprobar")).tipo == "CAMINOS_IA")
    chk("la procedencia queda en la configuración persistida de la partida", pr.almacen.partida(pr.id)["config"]["tipo"] == "CAMINOS_GUION")

    # ── determinismo e inmutabilidad ──────────────────────────────────────────────────────────────────────
    a1, a2 = jugar(g, P.Aleatorio(5), P.Aleatorio(9)), jugar(g, P.Aleatorio(5), P.Aleatorio(9))
    h1 = [e["hash"] for e in a1.almacen.eventos(a1.id)]
    h2 = [e["hash"] for e in a2.almacen.eventos(a2.id)]
    chk("con la misma semilla la partida es idéntica, evento por evento (hashes iguales)", h1 == h2 and a1.resultado["camino"] == a2.resultado["camino"])
    try:
        pr.paso()
        ok409 = False
    except ErrorCaminos as e:
        ok409 = e.status == 409
    chk("tras el resultado, cualquier acción da 409 y el resultado no cambia", ok409)
    ev_res = [e for e in pr.almacen.eventos(pr.id) if e["tipo"] == "partida.resultado"]
    chk("el resultado se escribe UNA sola vez (índice único) y es el persistido", len(ev_res) == 1 and pr.almacen.partida(pr.id)["resultado"]["resultado"] == pr.resultado["resultado"])
    pm = PartidaCaminos(g, P.PrimeraOpcion(), P.AzulRegistro(), almacen=Almacen(":memory:"))
    pm._g["nodos"]["N0"]["texto_rojo"] = "alterado"
    chk("el grafo se congela por hash: alterarlo en memoria corta la partida como ERROR_TECNICO", pm.paso()["resultado"] == "ERROR_TECNICO")
    gt = copy.deepcopy(g)
    gt["hojas"]["H_R_confianza"]["evidencia"] = ["correo_clic", "bandera_que_nadie_produce"]
    chk("una victoria sin la evidencia de estado exigida NO se concede (ERROR_TECNICO)", jugar(gt, P.Guion(["correo_senuelo", "cred_gerente"]), P.Guion(["no_reportar", "aprobar"])).resultado["resultado"] == "ERROR_TECNICO")

    # ── visibilidad ───────────────────────────────────────────────────────────────────────────────────────
    p0 = PartidaCaminos(g, P.Guion(["cred_gerente"]), P.AzulRegistro(), almacen=Almacen(":memory:"))
    cr = json.dumps(p0.ctx("rojo"), ensure_ascii=False)
    chk("el contexto del Rojo no revela la validez de las credenciales ni los señuelos", not G.PALABRAS_PROHIBIDAS_ROJO.search(cr) and "C-01" in cr and "C-07" in cr)
    p0.paso()   # Rojo elige la primera opción: el siguiente nodo es del Azul
    ca = json.dumps(p0.ctx("azul"), ensure_ascii=False)
    chk("el contexto del Azul no incluye el inventario del Rojo", "inventario" not in ca and "C-07" not in p0.ctx("azul")["texto"] or "inventario" not in p0.ctx("azul"))
    chk("el Azul recibe el registro y las alertas SIMULADAS; la recomendada solo la línea base «registro»", "Registro de identidades" in p0.ctx("azul")["texto"] and "recomendada_registro" in p0.ctx("azul"))
    pia = PartidaCaminos(g, P.PrimeraOpcion(), P.PrimeraOpcion(), almacen=Almacen(":memory:"))
    pia.paso()
    chk("a un proveedor sin nombre «azul_registro» (p. ej. una IA) no se le da la opción recomendada", "recomendada_registro" not in pia.ctx("azul"))

    # ── robustez ──────────────────────────────────────────────────────────────────────────────────────────
    pi = jugar(g, RojoMalo(), P.AzulRegistro())
    chk("opciones fuera del menú se rechazan y se cuentan; a la 3.ª la partida queda INCONCLUSA (no hay acción)", pi.resultado["resultado"] == "INCONCLUSA" and pi.resultado["opciones_invalidas"] == 3
        and not pi.resultado["estado_final"].get("base_entregada"))
    pd = jugar(g, RojoMuerto(), P.AzulRegistro())
    chk("un modelo sin respuesta 3 veces seguidas corta la partida: INCONCLUSA (excluida de las tasas)", pd.resultado["resultado"] == "INCONCLUSA" and pd.resultado["causa"] == "errores")
    pc = jugar(g, RojoCodigo(), P.AzulRegistro())
    ms = [e["payload"]["mensaje"] for e in pc.almacen.eventos(pc.id) if e["tipo"] == "caminos.decision" and e["payload"]["actor"] == "rojo"]
    chk("un mensaje del Rojo con código/comandos se filtra antes de auditarse", ms and all(m == "[mensaje filtrado]" for m in ms))

    # ── Wazuh simulado ────────────────────────────────────────────────────────────────────────────────────
    w = SimProvider(semilla=3)
    pw = PartidaCaminos(g, P.Guion(["cred_gerente", "insistir_autoridad"]), P.Guion(["pedir_verificacion", "rechazar"]), almacen=Almacen(":memory:"), wazuh=w)
    pw.jugar()
    al = w.consultar_alertas(pw.id)
    chk("las alertas del modo Caminos llevan la marca SIMULADO y correlacionan por partida_id", al and all(a["lab"]["simulado"] is True and a["lab"]["etiqueta"] == ETIQUETA and a["lab"]["partida_id"] == pw.id for a in al))
    chk("el acceso externo del Rojo genera la alerta «acceso inusual» (regla 100050)", any(a["rule"]["id"] == "100050" for a in al))
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
