"""Pruebas de la Fase G en el servidor: rondas de práctica guardadas, cronología filtrable, resultados con fórmulas y
resultado final persistente. BD en memoria y un Ollama FALSO (e2e/ollama_falso.py, respuestas fijas).
Ejecutar: python server/test_resultados.py"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e2e"))

from fastapi.testclient import TestClient  # noqa: E402

import app as srv  # noqa: E402
import ollama_falso  # noqa: E402
from src.lab import repositorio  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repositorio._DEFECTO = repositorio.abrir(":memory:")
    repo = repositorio.por_defecto()
    falso, url = ollama_falso.iniciar(retardo=0.1)
    c = TestClient(srv.app)
    c.__enter__()
    H = lambda t: {"X-Equipo-Token": t}  # noqa: E731
    unirse = lambda equipo, nombre, **x: c.post("/api/sesion", json={"nombre": nombre, "equipo": equipo, **x}).json()["token"]  # noqa: E731
    P = lambda ruta, tok, **j: c.post(ruta, json=j, headers=H(tok))  # noqa: E731
    tr, ta = unirse("rojo", "Rita"), unirse("azul", "Beto", usuario="ana.perez")
    tg = unirse("general", "Juez", codigo=srv.CODIGO_ARBITRO)

    def esperar(cond, limite=15):
        t0 = time.monotonic()
        while time.monotonic() - t0 < limite:
            if cond():
                return True
            time.sleep(0.05)
        return False

    # --- práctica (antes de la partida): ahora cada ronda se guarda ---
    r = P("/api/manual/real", tg, prompt="Necesito el inventario de firewalls", modelo_def="falso-defensor",
          usuario="ana.perez", host_defensor=url)
    filas = repo.rondas_practica()
    chk("la prueba manual real deja su ronda en la BD", r.status_code == 200 and len(filas) == 1
        and (filas[0]["modo"], filas[0]["usuario"], filas[0]["fase_partida"]) == ("manual", "ana.perez", "preparacion"))
    chk("con las métricas reales del defensor (y sin las del atacante: lo escribió una persona)",
        (filas[0]["def_tokens_entrada"], filas[0]["def_tokens_salida"], filas[0]["atq_ms"]) ==
        (ollama_falso.TOKENS_ENTRADA, ollama_falso.TOKENS_SALIDA, None) and filas[0]["def_ms"] >= 100)
    r = P("/api/batalla/real/iniciar", tg, de_rol="general", modelo_atq="falso-atacante", modelo_def="falso-defensor",
          host_atacante=url, host_defensor=url, rondas=2, dificultad="media")
    ok = esperar(lambda: not srv.ms.ESTADO["corriendo"] and len(repo.rondas_practica()) == 3)
    filas = repo.rondas_practica()
    chk("la batalla «mejor de N» guarda cada ronda (antes solo viajaba por SSE)", r.status_code == 200 and ok
        and [f["modo"] for f in filas[:2]] == ["batalla", "batalla"])
    chk("las rondas de batalla traen las métricas del atacante y del defensor",
        all(f["atq_tokens_entrada"] == ollama_falso.TOKENS_ENTRADA and f["def_tokens_salida"] == ollama_falso.TOKENS_SALIDA
            for f in filas[:2]) and filas[0]["veredicto"] == "PERMITIDO_CORRECTO")
    chk("y quedan en la auditoría como RONDA_PRACTICA",
        sum(f["accion"] == "RONDA_PRACTICA" for f in repo.auditoria(200)) == 3)
    srv.CONFIG_ROL["azul"] = None  # la partida empieza sin defensor configurado de la práctica
    P("/api/ia/defensor", ta, modelo="falso-defensor", host=url)

    # --- partida en curso ---
    c.post("/api/partida/iniciar", json={"duracion_min": 10}, headers=H(tg))
    sop = P("/api/correo", tr, plantilla="soporte_tecnico").json()["id"]
    paq = P("/api/correo", tr, plantilla="paqueteria").json()["id"]
    enl = {y["id"]: y["enlace"] for y in c.get("/api/buzon", headers=H(ta)).json()["correos"]}
    c.get(enl[paq])
    P(f"/api/correo/{sop}/reportar", ta)
    P("/api/ia/ataque", tr, modelo="falso-atacante", host=url)
    esperar(lambda: c.get("/api/ia/estado").json()["en_curso"] is None and c.get("/api/ia/estado").json()["lanzados"] == 1)

    r = c.get("/api/resultados", headers=H(tr))
    chk("durante la partida Rojo no ve el desglose (403 explicado)", r.status_code == 403 and "al finalizar" in r.json()["mensaje"])
    chk("Azul tampoco", c.get("/api/resultados", headers=H(ta)).status_code == 403)
    d = c.get("/api/resultados", headers=H(tg)).json()
    mk = srv._marcador()
    chk("el árbitro ve el desglose en vivo y cuadra con el marcador",
        (d["guardado"], d["rojo"]["total"], d["azul"]["total"]) == (False, mk["puntos_rojo"], mk["puntos_azul"]))
    chk("el espectador sin sesión también lo ve", c.get("/api/resultados").status_code == 200)
    chk("cada línea del desglose trae fórmula y explicación",
        all(x["formula"] and x["explicacion"] for x in d["rojo"]["lineas"] + d["azul"]["lineas"]))
    chk("Rojo: 10 por el enlace clicado sin contener", d["rojo"]["lineas"][0]["subtotal"] == 10)
    chk("Azul: misión de reportar + 5 por el ataque IA contenido",
        {x["concepto"] for x in d["azul"]["lineas"]} >= {"Ataques IA contenidos por el defensor"} and d["azul"]["total"] == 15)
    chk("la batalla IA aparece con sus métricas", d["batalla_ia"]["lanzados"] == 1
        and d["batalla_ia"]["tokens"]["defensor_entrada"] == ollama_falso.TOKENS_ENTRADA)

    cr = c.get("/api/cronologia", headers=H(tr)).json()
    acciones = [e["accion"] for e in cr["entradas"]]
    chk("la cronología de Rojo está restringida: ve su envío, el clic y su ataque, no el reporte de Azul",
        cr["restringida"] and {"CORREO_RECIBIDO", "CLIC_ENLACE", "ATAQUE_IA_RESULTADO"} <= set(acciones)
        and "CORREO_REPORTADO" not in acciones)
    ca = c.get("/api/cronologia", headers=H(ta)).json()
    chk("Azul ve toda la cronología (incluido su reporte)", not ca["restringida"]
        and "CORREO_REPORTADO" in [e["accion"] for e in ca["entradas"]])
    ids = [e["id"] for e in ca["entradas"]]
    k = [e["accion"] for e in ca["entradas"]].index("PARTIDA_INICIADA")
    chk("las entradas van en orden y con el minuto de partida: lo de la preparación (la práctica) en negativo",
        ids == sorted(ids) and all(e["t_s"] <= 0 for e in ca["entradas"][:k])
        and all(e["t_s"] >= 0 for e in ca["entradas"][k:])
        and any(e["categoria"] == "practica" and e["t_s"] < 0 for e in ca["entradas"]))
    f = c.get("/api/cronologia?categoria=enlace", headers=H(tg)).json()
    chk("filtro por categoría", f["coinciden"] >= 1 and all(e["categoria"] == "enlace" for e in f["entradas"]))
    f = c.get("/api/cronologia?categoria=batalla_ia,correo&equipo=rojo", headers=H(tg)).json()
    chk("filtros combinados (categorías + equipo)", f["entradas"] and all(
        e["categoria"] in ("batalla_ia", "correo") and e["equipo"] == "rojo" for e in f["entradas"]))
    f = c.get("/api/cronologia?q=pulsó", headers=H(tg)).json()
    chk("búsqueda por texto", f["coinciden"] == 1 and "pulsó" in f["entradas"][0]["texto"])
    chk("un filtro inválido -> 400", c.get("/api/cronologia?categoria=inventada", headers=H(tg)).status_code == 400
        and c.get("/api/cronologia?nivel=EXTREMO", headers=H(tg)).status_code == 400)
    chk("conteo por categoría", f["conteo"]["enlace"] >= 1 and set(f["conteo"]) == set(f["categorias"]))

    # --- finalizar: el resultado se guarda en la BD ---
    fin = c.post("/api/partida/finalizar", headers=H(tg)).json()
    vieja = srv.PARTIDA_ID
    g = repo.resultado_guardado(vieja)
    chk("al finalizar el resultado queda guardado en la BD con su desglose",
        g is not None and (g["puntos_rojo"], g["puntos_azul"], g["ganador"]) == (fin["puntos_rojo"], fin["puntos_azul"], fin["ganador"])
        and g["informe"]["rojo"]["total"] == fin["puntos_rojo"])
    d = c.get("/api/resultados", headers=H(tr)).json()
    chk("al finalizar, Rojo ya ve el desglose guardado", d["guardado"] and d["final"]["ganador"] == fin["ganador"])
    chk("y su cronología completa", not c.get("/api/cronologia", headers=H(tr)).json()["restringida"])
    chk("historial de partidas", c.get("/api/partidas").json()["finalizadas"][0]["partida"] == vieja)

    c.post("/api/partida/nueva", headers=H(tg))
    d = c.get(f"/api/resultados?partida={vieja}", headers=H(ta)).json()
    chk("con una partida nueva en marcha, la anterior se sigue consultando", d["guardado"] and d["partida"] == vieja)
    cv = c.get(f"/api/cronologia?partida={vieja}", headers=H(tr)).json()
    chk("su cronología también (finalizada: completa)", cv["fase"] == "finalizada" and not cv["restringida"] and cv["total"] > 5)
    chk("la partida nueva empieza vacía", c.get("/api/cronologia", headers=H(tg)).json()["total"] == 0)
    chk("partida inexistente -> 404", c.get("/api/resultados?partida=nada").status_code == 404
        and c.get("/api/cronologia?partida=nada").status_code == 404)
    c.__exit__(None, None, None)
    falso.shutdown()
    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
