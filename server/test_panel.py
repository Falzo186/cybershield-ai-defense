"""Pruebas de las rutas del panel de análisis (/api/panel/...). BD en memoria, sin Ollama encendido.
Ejecutar: python server/test_panel.py

Comprueban los contratos: que los GET son públicos y de solo lectura, que los POST exigen sesión, que nada
se presenta como real si no lo es, y que lanzar una campaña sin Ollama se rechaza en vez de simularse.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import app as srv  # noqa: E402
from src.lab import repositorio, wazuh  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repositorio._DEFECTO = repositorio.abrir(":memory:")
    previo = os.environ.get(wazuh.VAR_ENTORNO)
    c = TestClient(srv.app)
    c.__enter__()
    try:
        # ── Los GET del panel son públicos: no hace falta unirse a ningún equipo ───────────────────────────
        publicas = ["/api/panel/estado", "/api/panel/resumen", "/api/panel/escenarios",
                    "/api/panel/experimentos", "/api/panel/diagnostico", "/api/panel/rag",
                    "/api/panel/adversarial", "/api/panel/soc/alertas", "/api/panel/soc/cronologia",
                    "/api/panel/soc/correlacion", "/api/panel/campana"]
        for ruta in publicas:
            r = c.get(ruta)
            chk(f"GET {ruta} responde 200 sin sesión", r.status_code == 200)
        chk("todas devuelven JSON", all(isinstance(c.get(r).json(), dict) for r in publicas))

        # ── Las rutas de la partida siguen protegidas: el panel no abre un agujero ─────────────────────────
        chk("una ruta de la partida sigue exigiendo sesión", c.get("/api/buzon").status_code == 403)
        chk("un POST del panel sin sesión se rechaza",
            c.post("/api/panel/campana", json={"modelo": "x"}).status_code == 403)
        chk("reconstruir el índice sin sesión se rechaza",
            c.post("/api/panel/rag/reconstruir", json={}).status_code == 403)

        # ── Estado ────────────────────────────────────────────────────────────────────────────────────────
        e = c.get("/api/panel/estado").json()
        chk("el estado informa de Ollama con su host", "host" in e["ollama"] and "disponible" in e["ollama"])
        chk("el estado dice el modo de Wazuh", e["wazuh"]["modo"] in wazuh.MODOS)
        chk("el estado describe la base de datos como de consultas fijas",
            e["base_datos"]["solo_consultas_fijas"] is True)
        chk("el estado publica el presupuesto por defecto del harness",
            e["harness"]["presupuesto_por_defecto"]["max_iteraciones"] >= 1)
        chk("el estado publica qué clases no se imputan al modelo",
            "ERROR_INFRAESTRUCTURA" in e["diagnostico"]["no_imputables"])

        # ── Escenarios y referencia ───────────────────────────────────────────────────────────────────────
        esc = c.get("/api/panel/escenarios").json()
        chk("se publican los escenarios con su referencia",
            all(x["esperado"] in ("permitir", "autorizar", "contener")
                for x in esc["escenarios"] if x["verificable"]))
        chk("los exploratorios se marcan como no verificables",
            any(not x["verificable"] for x in esc["escenarios"]))
        chk("se puede filtrar por familia",
            {x["familia"] for x in c.get("/api/panel/escenarios?familia=imposible").json()["escenarios"]}
            == {"imposible"})

        # ── Diagnóstico ───────────────────────────────────────────────────────────────────────────────────
        d = c.get("/api/panel/diagnostico").json()["clases"]
        chk("el catálogo de fallos trae las 14 entradas", len(d) == 14)
        chk("y marca cuáles no cuentan para el modelo",
            d["ERROR_TIMEOUT"]["cuenta_para_modelo"] is False
            and d["FALLO_POLITICA"]["cuenta_para_modelo"] is True)

        # ── RAG ───────────────────────────────────────────────────────────────────────────────────────────
        r = c.get("/api/panel/rag/consulta?q=configuraci%C3%B3n%20de%20administraci%C3%B3n").json()
        chk("la consulta al RAG devuelve fragmentos con su similitud",
            r["fragmentos"] and all("similitud" in f for f in r["fragmentos"]))
        chk("y declara el modo de recuperación", r["modo"] in ("bm25",) or r["modo"].startswith("embeddings"))
        chk("una consulta vacía se rechaza", c.get("/api/panel/rag/consulta?q=%20").status_code == 400)
        chk("una consulta sin relación no recupera nada",
            c.get("/api/panel/rag/consulta?q=zzzz%20qwerty").json()["fragmentos"] == [])

        # ── Adversarial ───────────────────────────────────────────────────────────────────────────────────
        a = c.get("/api/panel/adversarial").json()
        chk("el laboratorio adversarial publica su matriz de confusión",
            all(k in a["metricas"] for k in ("VP", "FN", "FP", "VN")))
        chk("y el intervalo de confianza de la detección", a["metricas"]["deteccion"]["bajo"] is not None)
        chk("se puede filtrar por vector",
            {f["vector"] for f in c.get("/api/panel/adversarial?vector=documentacion").json()["filas"]}
            == {"documentacion"})

        # ── Wazuh: los tres modos, vistos desde la API ────────────────────────────────────────────────────
        os.environ[wazuh.VAR_ENTORNO] = "desactivado"
        al = c.get("/api/panel/soc/alertas").json()
        chk("desactivado: sin alertas y con explicación",
            al["modo"] == "desactivado" and al["alertas"] == [] and al["nota"])
        os.environ[wazuh.VAR_ENTORNO] = "simulado"
        al = c.get("/api/panel/soc/alertas").json()
        chk("simulado: hay alertas", al["modo"] == "simulado" and len(al["alertas"]) > 0)
        chk("TODAS marcadas como simuladas",
            all(x["simulado"] and x["origen"] == "simulado" for x in al["alertas"]))
        chk("ninguna se presenta como de Wazuh real",
            not any(x["origen"] == "wazuh_real" for x in al["alertas"]))
        os.environ[wazuh.VAR_ENTORNO] = "real"
        al = c.get("/api/panel/soc/alertas").json()
        chk("real sin conexión: error visible y cero alertas",
            al["ok"] is False and al["alertas"] == [])
        chk("y NO se sustituyen por simuladas", "No se muestran alertas simuladas" in al["nota"])
        os.environ[wazuh.VAR_ENTORNO] = "simulado"

        # ── Cronología ────────────────────────────────────────────────────────────────────────────────────
        cr = c.get("/api/panel/soc/cronologia").json()
        chk("la cronología declara las fuentes", set(cr["fuentes"]) == {"evento", "auditoria", "alerta"})
        chk("todo registro dice si es real o simulado",
            all(isinstance(f["simulado"], bool) and f["real"] != f["simulado"] for f in cr["filas"]))
        chk("las alertas de la cronología van marcadas como simuladas en modo simulado",
            all(f["simulado"] for f in cr["filas"] if f["fuente"] == "alerta"))
        chk("se puede filtrar por fuente",
            {f["fuente"] for f in c.get("/api/panel/soc/cronologia?fuentes=evento").json()["filas"]}
            <= {"evento"})

        # ── Correlación ───────────────────────────────────────────────────────────────────────────────────
        co = c.get("/api/panel/soc/correlacion").json()
        chk("la correlación publica sus reglas", len(co["reglas"]) >= 5)
        chk("cada regla explica por qué une dos eventos",
            all(x["explicacion"] and x["ventana_s"] > 0 for x in co["reglas"]))
        chk("el resumen cuadra con los incidentes", co["resumen"]["incidentes"] == len(co["incidentes"]))
        chk("cada incidente lleva gravedad y resumen",
            all(i["gravedad"] and i["resumen"] for i in co["incidentes"]))

        # ── Experimentos ──────────────────────────────────────────────────────────────────────────────────
        ex = c.get("/api/panel/experimentos").json()
        chk("se listan los tipos de experimento", "oficial" in ex["tipos"])
        chk("un experimento inexistente da 404",
            c.get("/api/panel/experimentos/no-existe").status_code == 404)
        chk("comparar con ids inexistentes da 404",
            c.get("/api/panel/comparar?a=x&b=y").status_code == 404)

        # ── Campañas: con sesión, pero sin Ollama no se simula nada ───────────────────────────────────────
        tok = c.post("/api/sesion", json={"nombre": "Juez", "equipo": "general",
                                          "codigo": srv.CODIGO_ARBITRO}).json()["token"]
        cab = {"X-Equipo-Token": tok}
        est = c.get("/api/panel/campana").json()
        chk("el estado de campaña publica los modos y pipelines",
            set(est["modos"]) >= {"rapido", "estandar", "intensivo", "estres", "comparativo"}
            and "directo" in est["pipelines"])
        chk("sin campaña lanzada, no hay progreso inventado",
            est["en_curso"] is False and est["progreso"] is None)
        r = c.post("/api/panel/campana", json={}, headers=cab)
        chk("lanzar sin modelo se rechaza", r.status_code == 400)
        r = c.post("/api/panel/campana", json={"modelo": "modelo-que-no-existe"}, headers=cab)
        chk("lanzar con un modelo que no está en Ollama se rechaza (503 o 400), nunca se simula",
            r.status_code in (400, 503) and "error" in r.json())
        chk("cancelar sin campaña en curso da 409",
            c.post("/api/panel/campana/cancelar", json={}, headers=cab).status_code == 409)

        # ── Mediciones de la Fase E: modelo, atacante y lotes ─────────────────────────────────────────────
        for ruta in ("/api/panel/adversarial/modelo", "/api/panel/adversarial/atacante", "/api/panel/lotes"):
            r = c.get(ruta)
            chk(f"GET {ruta} responde 200 sin sesión", r.status_code == 200)
            j = r.json()
            chk(f"{ruta} no inventa progreso si no se ha lanzado nada",
                j["en_curso"] is False and j["progreso"] is None and j["resultado"] is None)
            chk(f"{ruta} explica qué mide", bool(j.get("nota")))
        chk("lanzar una medición del modelo exige sesión",
            c.post("/api/panel/adversarial/modelo", json={"modelo": "x"}).status_code == 403)
        chk("lanzar una medición del atacante exige sesión",
            c.post("/api/panel/adversarial/atacante", json={"modelo_atacante": "x"}).status_code == 403)
        chk("lanzar un lote exige sesión",
            c.post("/api/panel/lotes", json={"modelo": "x"}).status_code == 403)

        # Las tres medidas están en rutas distintas: el filtro, el modelo y el camino completo no se mezclan.
        det = c.get("/api/panel/adversarial").json()
        chk("la ruta del filtro sigue midiendo solo el filtro determinista",
            "metricas" in det and "deteccion" in det["metricas"])
        chk("la del modelo declara que va sin el filtro delante",
            "sin el filtro" in c.get("/api/panel/adversarial/modelo").json()["nota"])
        chk("la del atacante define «objetivo conseguido» sobre la ejecución",
            "sobre la ejecución" in c.get("/api/panel/adversarial/atacante").json()["nota"])

        for ruta, cuerpo, que in (("/api/panel/adversarial/modelo", {}, "modelo"),
                                  ("/api/panel/adversarial/atacante", {}, "modelo_atacante"),
                                  ("/api/panel/adversarial/atacante", {"modelo_atacante": "x"},
                                   "modelo_defensor"),
                                  ("/api/panel/lotes", {}, "modelo")):
            r = c.post(ruta, json=cuerpo, headers=cab)
            chk(f"{ruta} sin {que} se rechaza", r.status_code in (400, 503) and "error" in r.json())
        r = c.post("/api/panel/adversarial/modelo", json={"modelo": "no-existe"}, headers=cab)
        chk("una medición con un modelo que no está en Ollama se rechaza, nunca se simula",
            r.status_code in (400, 503) and "error" in r.json())
        chk("cancelar una medición que no existe da 409",
            c.post("/api/panel/adversarial/cancelar", json={}, headers=cab).status_code == 409)

        chk("el listado de campañas por lotes es una lista",
            isinstance(c.get("/api/panel/lotes").json()["campanas"], list))
        r = c.get("/api/panel/lotes/no-existe-esta-campana")
        chk("consultar una campaña por lotes inexistente da 404",
            r.status_code == 404 and "error" in r.json())

        # El conjunto de evaluación publica fijos y generados por separado.
        cj = c.get("/api/panel/estado").json()["conjunto_evaluacion"]
        chk("el estado separa escenarios fijos de generados",
            cj["fijos"] > 0 and cj["generados"] > 0 and cj["total"] == cj["fijos"] + cj["generados"])
        chk("y publica la huella del conjunto generado, para saber qué se midió",
            bool(cj["huella_generados"]))
        chk("la familia generado aparece en el desglose por familias",
            cj["familias"]["generado"]["total"] == cj["generados"])

        # ── El panel estático se sirve ────────────────────────────────────────────────────────────────────
        p = c.get("/panel/")
        chk("la página del panel se sirve", p.status_code == 200 and "CyberShield" in p.text)
        chk("el panel no usa innerHTML con datos",
            "innerHTML" not in (Path(__file__).resolve().parents[1] / "ui" / "panel" / "panel.js")
            .read_text(encoding="utf-8").split("Los únicos `innerHTML`")[-1])
        chk("la hoja de estilos del panel define sus tokens",
            "--p-acento" in (Path(__file__).resolve().parents[1] / "ui" / "panel" / "panel.css")
            .read_text(encoding="utf-8"))
    finally:
        if previo is None:
            os.environ.pop(wazuh.VAR_ENTORNO, None)
        else:
            os.environ[wazuh.VAR_ENTORNO] = previo
        c.__exit__(None, None, None)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
