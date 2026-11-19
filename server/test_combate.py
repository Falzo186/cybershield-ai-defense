"""Pruebas de las rutas del combate (/api/combate/...) con modelos FALSOS y bases temporales. Sin Ollama necesario.
Ejecutar: python server/test_combate.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = tempfile.mkdtemp()
os.environ["CS_COMBATE_DB"] = os.path.join(tmp, "combate.db")
os.environ["CS_WAZUH_SIM_DB"] = os.path.join(tmp, "wz.db")

from fastapi.testclient import TestClient  # noqa: E402

import app as srv  # noqa: E402
import combate as cb  # noqa: E402
from src.lab import repositorio  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def esperar(c, pid, hasta=40):
    t0 = time.time()
    while time.time() - t0 < hasta:
        d = c.get(f"/api/combate/partidas/{pid}").json()
        if d.get("resultado"):
            return d
        time.sleep(0.2)
    return c.get(f"/api/combate/partidas/{pid}").json()


def main():
    repositorio._DEFECTO = repositorio.abrir(":memory:")
    cb.PAUSA_FALSOS_S = 0.15
    c = TestClient(srv.app)
    c.__enter__()
    try:
        for ruta in ("/api/combate/estado", "/api/combate/modelos", "/api/combate/escenarios", "/api/combate/partidas", "/api/combate/campanas"):
            chk(f"GET {ruta} es público y responde 200", c.get(ruta).status_code == 200)
        esc = c.get("/api/combate/escenarios").json()["escenarios"]
        chk("el catálogo expone 15 escenarios con objetivos, umbral y hash (sin zonas ni verdad de fondo)",
            len(esc) == 15 and all("hash" in e and "umbral_victoria_roja" in e for e in esc) and "zona" not in str(esc))
        est = c.get("/api/combate/estado").json()
        chk("el estado declara Wazuh como SIMULADO", est["wazuh"]["etiqueta"] == "WAZUH SIMULADO" and est["wazuh"]["simulado"] is True)
        cuerpo = {"escenario": "verificacion_falsa-sencillo", "rojo": "falso:objetivos", "azul": "falso:aprobar", "semilla": 1}
        chk("crear partida sin sesión -> 403", c.post("/api/combate/partidas", json=cuerpo).status_code == 403)
        tr = c.post("/api/sesion", json={"nombre": "Roja Uno", "equipo": "rojo"}).json()["token"]
        te = c.post("/api/sesion", json={"nombre": "Mirón", "equipo": "espectador"}).json()["token"]
        tg = c.post("/api/sesion", json={"nombre": "Juez", "equipo": "general", "codigo": srv.CODIGO_ARBITRO}).json()["token"]
        chk("crear partida como Rojo -> 403", c.post("/api/combate/partidas", json=cuerpo, headers={"X-Equipo-Token": tr}).status_code == 403)
        chk("crear partida como espectador -> 403", c.post("/api/combate/partidas", json=cuerpo, headers={"X-Equipo-Token": te}).status_code == 403)
        H = {"X-Equipo-Token": tg}
        chk("escenario desconocido -> 400", c.post("/api/combate/partidas", json={**cuerpo, "escenario": "x"}, headers=H).status_code == 400)
        chk("modelo falso desconocido -> 400", c.post("/api/combate/partidas", json={**cuerpo, "rojo": "falso:magia"}, headers=H).status_code == 400)
        r = c.post("/api/combate/partidas", json={**cuerpo, "rojo": "modelo-que-no-existe:8b"}, headers=H)
        chk("modelo real inexistente (o Ollama caído) se rechaza sin simular nada", r.status_code in (400, 503))
        r = c.post("/api/combate/partidas", json={**cuerpo, "azul": "falso:registro", "rojo": "falso:aleatorio", "semilla": 2}, headers=H)
        chk("el árbitro crea una partida (200, id y hash del escenario)", r.status_code == 200 and "id" in r.json() and len(r.json()["hash_escenario"]) == 64)
        pid = r.json()["id"]
        chk("mientras corre, un segundo POST da 409", c.post("/api/combate/partidas", json=cuerpo, headers=H).status_code == 409)
        d0 = c.get(f"/api/combate/partidas/{pid}").json()
        chk("en curso: el resultado es NULO (la interfaz no puede mostrar victoria)", d0["resultado"] is None and "resultado_detalle" not in d0 and d0["en_curso"])
        ev = c.get(f"/api/combate/partidas/{pid}/eventos").json()
        chk("en curso: las zonas de política no se publican", all(r["zona"] is None for r in d0["recursos"]))
        chk("en curso: no hay evento partida.resultado ni verdad de fondo en los eventos",
            all(e["tipo"] != "partida.resultado" for e in ev["eventos"]) and "legitima" not in str(ev) or ev["terminada"])
        chk("exportar en curso -> 409", c.get(f"/api/combate/partidas/{pid}/exportar").status_code == 409 or ev["terminada"])
        d = esperar(c, pid)
        chk("al terminar, el resultado sale del evento persistido y coincide con él",
            d["resultado"] in ("VICTORIA_AZUL", "EMPATE", "EMPATE_DEGRADADO", "VICTORIA_ROJA") and d["resultado_detalle"]["resultado"] == d["resultado"])
        evf = c.get(f"/api/combate/partidas/{pid}/eventos").json()
        res_ev = [e for e in evf["eventos"] if e["tipo"] == "partida.resultado"]
        chk("exactamente un evento partida.resultado y es el último", len(res_ev) == 1 and evf["eventos"][-1]["tipo"] == "partida.resultado")
        chk("el resultado del detalle es el del evento", res_ev[0]["payload"]["resultado"] == d["resultado"])
        chk("la cadena de hashes se verifica", d["cadena"] is True)
        chk("tras el resultado, interrumpir -> 409 (o 404 si ya no está en memoria)", c.post(f"/api/combate/partidas/{pid}/interrumpir", headers=H).status_code in (404, 409))
        ex = c.get(f"/api/combate/partidas/{pid}/exportar")
        chk("exportar tras el resultado funciona e incluye alertas SIMULADAS", ex.status_code == 200 and ex.json()["etiqueta_wazuh"] == "WAZUH SIMULADO" and ex.json()["cadena_integra"])
        w = c.get(f"/api/combate/partidas/{pid}/wazuh").json()
        chk("Wazuh de la partida: alertas con marca SIMULADO y agentes", w["simulado"] is True and w["alertas"] and all(a["lab"]["simulado"] for a in w["alertas"]) and len(w["agentes"]) == 4)
        chk("Wazuh: el filtro por nivel funciona", all(a["rule"]["level"] >= 8 for a in c.get(f"/api/combate/partidas/{pid}/wazuh?nivel_min=8").json()["alertas"]))
        chk("el historial lista la partida y filtra por resultado",
            any(p["id"] == pid for p in c.get("/api/combate/partidas").json()["partidas"])
            and not c.get("/api/combate/partidas?resultado=VICTORIA_ROJA").json()["partidas"] or d["resultado"] == "VICTORIA_ROJA")
        # interrupción
        r = c.post("/api/combate/partidas", json={**cuerpo, "escenario": "escalada_privilegios-complejo", "azul": "falso:registro", "rojo": "falso:aleatorio"}, headers=H)
        p2 = r.json()["id"]
        chk("el espectador no puede interrumpir", c.post(f"/api/combate/partidas/{p2}/interrumpir", headers={"X-Equipo-Token": te}).status_code == 403)
        chk("el árbitro interrumpe", c.post(f"/api/combate/partidas/{p2}/interrumpir", headers=H).status_code == 200)
        d2 = esperar(c, p2)
        chk("interrumpida -> INCONCLUSA", d2["resultado"] == "INCONCLUSA" and d2["resultado_detalle"]["causa"] == "interrumpida")
        chk("detalle de partida inexistente -> 404", c.get("/api/combate/partidas/nada").status_code == 404)
        # victoria Roja de verdad por la API
        r = c.post("/api/combate/partidas", json=cuerpo, headers=H)
        d3 = esperar(c, r.json()["id"])
        chk("victoria ROJA por la API (Azul que aprueba todo): VICTORIA_ROJA con objetivos alcanzados", d3["resultado"] == "VICTORIA_ROJA" and d3["resultado_detalle"]["objetivos_alcanzados"])
    finally:
        c.__exit__(None, None, None)
    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
