"""Pruebas de la batalla integrada en la partida (Fase F) con BD en memoria y un Ollama FALSO (e2e/ollama_falso.py).

El Ollama falso devuelve respuestas fijas: estas pruebas comprueban el camino completo del servidor (permisos,
fases, capas, clasificación, puntos, fallo seguro, métricas transmitidas tal cual), NO la calidad de un modelo.
Ejecutar: python server/test_batalla_partida.py"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e2e"))

from fastapi.testclient import TestClient  # noqa: E402

import app as srv  # noqa: E402
import ollama_falso  # noqa: E402
from src.lab import ataque_ia, repositorio  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repositorio._DEFECTO = repositorio.abrir(":memory:")
    falso, url = ollama_falso.iniciar(retardo=0.3)
    lento, url_lento = ollama_falso.iniciar(retardo=3)
    c = TestClient(srv.app)
    c.__enter__()
    H = lambda t: {"X-Equipo-Token": t}  # noqa: E731
    unirse = lambda equipo, nombre, **x: c.post("/api/sesion", json={"nombre": nombre, "equipo": equipo, **x}).json()["token"]  # noqa: E731
    P = lambda ruta, tok, **j: c.post(ruta, json=j, headers=H(tok))  # noqa: E731
    mensaje = lambda r: r.json().get("mensaje", "")  # noqa: E731
    tr, ta = unirse("rojo", "Rita"), unirse("azul", "Beto", usuario="ana.perez")
    tg, te = unirse("general", "Juez", codigo=srv.CODIGO_ARBITRO), unirse("espectador", "Público")
    atacar = lambda tok=tr, modelo="falso-atacante", host=url, **x: P("/api/ia/ataque", tok, modelo=modelo, host=host, **x)  # noqa: E731

    def esperar_fin(limite=20):
        t0 = time.monotonic()
        while time.monotonic() - t0 < limite:
            e = c.get("/api/ia/estado").json()
            if e["en_curso"] is None:
                return e
            time.sleep(0.05)
        return c.get("/api/ia/estado").json()

    # --- antes de la partida ---
    e = c.get("/api/ia/estado").json()
    chk("el estado de la batalla es público (espectador sin sesión)", e["fase_partida"] == "preparacion"
        and e["max_ataques"] == ataque_ia.MAX_ATAQUES and e["lanzados"] == 0)
    chk("sin credencial robada, Rojo atacaría como invitado",
        e["identidad"] == {"usuario": "visita.demo", "origen": "invitado", "rol": "invitado"})
    r = atacar()
    chk("antes de iniciar, Rojo no ataca (409)", r.status_code == 409 and "no ha empezado" in mensaje(r))
    chk("Azul no lanza ataques (403)", atacar(ta).status_code == 403)
    chk("Rojo no configura el defensor (403)", P("/api/ia/defensor", tr, modelo="falso-defensor", host=url).status_code == 403)
    chk("el espectador no ataca (403)", atacar(te).status_code == 403)
    r = P("/api/ia/defensor", ta, modelo="no-existe", host=url)
    chk("defensor con un modelo que su Ollama no tiene -> 409 y queda marcado como no verificado",
        r.status_code == 409 and "no existe" in mensaje(r) and c.get("/api/ia/estado").json()["defensor"]["ok"] is False)
    r = P("/api/ia/defensor", ta, modelo="falso-defensor", host=url)
    chk("Azul configura su defensor: comprobado de verdad contra su Ollama", r.status_code == 200
        and r.json()["defensor"]["modelo"] == "falso-defensor" and r.json()["defensor"]["ok"] is True)
    chk("antes de la partida la práctica sigue disponible",
        c.post("/api/simulacion/iniciar", headers=H(tg)).status_code == 200)
    c.post("/api/detener", json={}, headers=H(tg))
    time.sleep(0.3)

    # --- partida en curso ---
    c.post("/api/partida/iniciar", json={"duracion_min": 10}, headers=H(tg))
    r = c.post("/api/simulacion/iniciar", headers=H(tg))
    chk("durante la partida la simulación es práctica: 409 explicado", r.status_code == 409 and "práctica" in mensaje(r))
    chk("durante la partida tampoco hay prueba manual real (409)",
        P("/api/manual/real", tg, prompt="hola", modelo_def="falso-defensor", host_defensor=url).status_code == 409)
    chk("ni batalla «mejor de N» (409)", P("/api/batalla/real/iniciar", tg, de_rol="general").status_code == 409)
    r = atacar(modelo="no-existe")
    chk("atacante con un modelo inexistente -> 409 y no gasta ataque", r.status_code == 409
        and c.get("/api/ia/estado").json()["lanzados"] == 0)

    r = atacar(tecnica="autoridad", intensidad=1)
    chk("Rojo lanza un ataque: responde enseguida con la fase real (esperando al atacante)", r.status_code == 200
        and r.json()["ataque"]["fase"] == "atacante" and r.json()["ataque"]["n"] == 1)
    r2 = atacar()
    chk("un segundo ataque mientras hay uno en curso -> 409", r2.status_code == 409 and "en curso" in mensaje(r2))
    t0 = time.monotonic()
    fases = set()
    while time.monotonic() - t0 < 10:
        en = c.get("/api/ia/estado").json()["en_curso"]
        if en is None:
            break
        fases.add(en["fase"])
        time.sleep(0.05)
    chk("las fases difundidas son las reales: atacante y después defensor", fases == {"atacante", "defensor"})
    e = esperar_fin()
    a = e["ataques"][0]
    chk("como invitado, el defensor rechaza: CONTENIDO y +5 para Azul", (a["estado"], a["resultado"], a["puntos_azul"],
        a["puntos_rojo"]) == ("terminado", "contenido", ataque_ia.PUNTOS_CONTENIDO, 0))
    chk("el ataque guarda identidad, técnica e intensidad", (a["usuario"], a["origen_identidad"], a["tecnica"],
        a["intensidad"], a["lanzado_por"]) == ("visita.demo", "invitado", "autoridad", 1, "Rita"))
    chk("tokens de entrada y salida y carga del modelo: exactamente los que informa Ollama (atacante)",
        (a["atq_tokens_entrada"], a["atq_tokens_salida"], a["atq_carga_ms"]) ==
        (ollama_falso.TOKENS_ENTRADA, ollama_falso.TOKENS_SALIDA, ollama_falso.CARGA_NS // 1_000_000))
    chk("… y del defensor", (a["def_tokens_entrada"], a["def_tokens_salida"], a["def_carga_ms"]) ==
        (ollama_falso.TOKENS_ENTRADA, ollama_falso.TOKENS_SALIDA, ollama_falso.CARGA_NS // 1_000_000))
    chk("los tiempos son medidos (incluyen el retardo real del servidor falso)", a["atq_ms"] >= 300 and a["def_ms"] >= 300)
    chk("la explicación dice qué pasó", "rechazó" in a["explicacion"] and "invitado" in a["explicacion"])
    mk = srv._marcador()
    chk("el marcador de la PARTIDA suma la defensa IA", (mk["puntos_azul"], mk["puntos_azul_ia"], mk["ataques_ia"],
        mk["ia_contenidos"]) == (5, 5, 1, 1))

    # --- con una credencial robada, Rojo ataca como esa empleada ---
    sop = P("/api/correo", tr, plantilla="soporte_tecnico").json()["id"]
    enl = [y for y in c.get("/api/buzon", headers=H(ta)).json()["correos"] if y["id"] == sop][0]["enlace"]
    c.get(enl)
    c.post(enl + "/credenciales")
    e = c.get("/api/ia/estado").json()
    chk("tras el phishing con credenciales, la identidad del atacante es la cuenta robada",
        e["identidad"] == {"usuario": "ana.perez", "origen": "credencial_robada", "rol": "empleado"})
    rojo0 = srv._marcador()["puntos_rojo"]
    riesgo0 = srv.ESTADO_PARTIDA.riesgo_acumulado
    atacar()
    a = esperar_fin()["ataques"][1]
    chk("el defensor atiende una petición válida para esa cuenta: DATOS EXPUESTOS (INTERNA) +10 para Rojo",
        (a["resultado"], a["sensibilidad_expuesta"], a["puntos_rojo"], a["herramienta"]) ==
        ("datos_expuestos", "INTERNA", ataque_ia.PUNTOS_DATOS["INTERNA"], "consultar_clientes"))
    chk("la explicación nombra el control que falló (credencial sin revocar) y cómo se evita",
        "credencial robada" in a["explicacion"] and "revocándola" in a["explicacion"])
    mk = srv._marcador()
    chk("el marcador de la partida suma la fuga a Rojo y la regla sube el riesgo",
        mk["puntos_rojo"] == rojo0 + 10 and mk["puntos_rojo_ia"] == 10 and mk["ia_datos_expuestos"] == 1
        and srv.ESTADO_PARTIDA.riesgo_acumulado == min(100, riesgo0 + 20))
    emitidos, original = [], srv.ms.emitir
    srv.ms.emitir = lambda tipo, datos: emitidos.append((tipo, datos))
    try:
        P("/api/credenciales/revocar", ta)
    finally:
        srv.ms.emitir = original
    chk("revocar difunde el estado de la batalla (las vistas ven el cambio de identidad al momento)",
        any(tp == "ia_estado" and d["identidad"]["origen"] == "invitado" for tp, d in emitidos))
    e = c.get("/api/ia/estado").json()
    chk("revocar la credencial devuelve a Rojo a invitado", e["identidad"]["origen"] == "invitado")
    chk("lo filtrado no se des-filtra: los 10 puntos de la fuga se mantienen", srv._marcador()["puntos_rojo_ia"] == 10)

    # --- defensor ingenuo: la IA cae, una capa lo frena ---
    P("/api/ia/defensor", ta, modelo="falso-ingenuo", host=url)
    atacar()
    a = esperar_fin()["ataques"][2]
    chk("IA ENGAÑADA: la IA propone dar clientes a un invitado y la capa de permisos lo frena (+5 Rojo, sin datos)",
        (a["resultado"], a["capa_bloqueo"], a["puntos_rojo"], a["sensibilidad_expuesta"]) ==
        ("ia_enganada", "permisos", ataque_ia.PUNTOS_IA_ENGANADA, None))

    # --- fallo seguro ---
    P("/api/ia/defensor", ta, modelo="falso-roto", host=url)
    atacar()
    e = esperar_fin()
    a = e["ataques"][3]
    chk("defensor caído: FALLO SEGURO, no se ejecuta nada y no puntúa nadie",
        (a["resultado"], a["herramienta"], a["puntos_rojo"], a["puntos_azul"]) == ("fallo_seguro", None, 0, 0))
    chk("el error real de Ollama queda registrado y el defensor pasa a no verificado",
        "500" in (a["error"] or "") and e["defensor"]["ok"] is False and "500" in e["defensor"]["error"])
    srv.CONFIG_ROL["azul"] = None  # Azul sin defensor configurado
    atacar()
    a = esperar_fin()["ataques"][4]
    chk("sin defensor configurado también es fallo seguro, explicado",
        a["resultado"] == "fallo_seguro" and "no ha configurado" in a["error"])
    P("/api/ia/defensor", ta, modelo="falso-defensor", host=url)
    r = atacar(modelo="falso-roto")
    a = esperar_fin()["ataques"][5]
    chk("atacante caído: ERROR DEL ATACANTE, nada llega al defensor y cuenta como ataque gastado",
        r.status_code == 200 and (a["resultado"], a["veredicto"], a["def_ms"]) == ("error_atacante", None, None))

    # --- tope de ataques ---
    for _ in range(ataque_ia.MAX_ATAQUES - 6):
        atacar()
        esperar_fin()
    e = c.get("/api/ia/estado").json()
    r = atacar()
    chk(f"tope de {ataque_ia.MAX_ATAQUES} ataques por partida (409)", e["restantes"] == 0 and r.status_code == 409
        and "Ya lanzaste" in mensaje(r))
    acc = [f["accion"] for f in repositorio.por_defecto().auditoria(500)]
    chk("cada ataque deja auditoría (lanzado y resultado)",
        acc.count("ATAQUE_IA_LANZADO") == ataque_ia.MAX_ATAQUES and acc.count("ATAQUE_IA_RESULTADO") == ataque_ia.MAX_ATAQUES)
    fin = c.post("/api/partida/finalizar", headers=H(tg)).json()
    mk = srv._marcador()
    chk("el resultado final incluye los puntos de la batalla IA", fin["puntos_rojo"] == mk["puntos_rojo"]
        and mk["puntos_rojo_ia"] == 15 and mk["puntos_azul_ia"] == 5 * (1 + ataque_ia.MAX_ATAQUES - 6))
    chk("tras finalizar, Rojo no ataca (409)", atacar().status_code == 409)
    chk("tras finalizar vuelve la práctica", c.post("/api/simulacion/iniciar", headers=H(tg)).status_code == 200)
    c.post("/api/detener", json={}, headers=H(tg))
    time.sleep(0.3)

    # --- partida nueva: contador a cero; un ataque a medias al finalizar no cuenta ---
    c.post("/api/partida/nueva", headers=H(tg))
    e = c.get("/api/ia/estado").json()
    chk("partida nueva: ataques y puntos IA a cero", e["lanzados"] == 0 and e["puntos"]["rojo"] == 0)
    c.post("/api/partida/iniciar", json={"duracion_min": 5}, headers=H(tg))
    atacar(host=url_lento)
    time.sleep(0.2)
    chk("el ataque está en curso (esperando a la Ollama lenta)", c.get("/api/ia/estado").json()["en_curso"] is not None)
    c.post("/api/partida/finalizar", headers=H(tg))
    e = esperar_fin()
    a = e["ataques"][0]
    chk("finalizar con un ataque a medias lo cancela: no cuenta para nadie",
        (a["estado"], a["resultado"], a["puntos_rojo"], a["puntos_azul"]) == ("cancelado", "cancelado", 0, 0)
        and srv._marcador()["final"]["puntos_rojo"] == 0)
    c.__exit__(None, None, None)
    falso.shutdown()
    lento.shutdown()
    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
