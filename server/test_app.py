"""Pruebas del servidor sin Ollama (tokens de equipo y buzón), con BD en memoria. Ejecutar: python server/test_app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

import app as srv  # noqa: E402
from src.lab import repositorio  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repositorio._DEFECTO = repositorio.abrir(":memory:")  # nunca toca data/lab.db
    c = TestClient(srv.app)
    H = lambda t: {"X-Equipo-Token": t}  # noqa: E731

    # --- espectador (sin token) ---
    chk("espectador lee estado", c.get("/api/estado").status_code == 200)
    chk("espectador no lee usuarios", c.get("/api/usuarios").status_code == 403)
    chk("espectador no detiene", c.post("/api/detener", json={}).status_code == 403)
    chk("token falso rechazado", c.post("/api/detener", json={}, headers=H("falso")).status_code == 403)
    chk("espectador no reclama token", c.post("/api/equipo/reclamar", json={"equipo": "espectador"}).status_code == 422)

    # --- correo antes de que azul entre ---
    tr = c.post("/api/equipo/reclamar", json={"equipo": "rojo"}).json()["token"]
    chk("correo sin azul en la partida -> 409",
        c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(tr)).status_code == 409)

    # --- reclamar ---
    chk("azul con usuario inexistente -> 400",
        c.post("/api/equipo/reclamar", json={"equipo": "azul", "usuario": "nadie"}).status_code == 400)
    r = c.post("/api/equipo/reclamar", json={"equipo": "azul", "usuario": "luis.gomez"}).json()
    ta = r["token"]
    chk("azul juega con el usuario semilla elegido", r["usuario"] == "luis.gomez")
    tg = c.post("/api/equipo/reclamar", json={"equipo": "general"}).json()["token"]
    chk("segundo reclamo de un equipo -> 409", c.post("/api/equipo/reclamar", json={"equipo": "rojo"}).status_code == 409)
    chk("tokens distintos por equipo", len({tr, ta, tg}) == 3)

    # --- el rol lo fija el token, no el cuerpo ---
    chk("rojo declarando azul -> 403",
        c.post("/api/batalla/real/iniciar", json={"de_rol": "azul"}, headers=H(tr)).status_code == 403)
    chk("rojo no confirma el modelo de azul",
        c.get("/api/ollama/probar?modelo=x&rol=azul", headers=H(tr)).status_code == 403)

    # --- detener: solo el árbitro ---
    chk("rojo no detiene", c.post("/api/detener", json={}, headers=H(tr)).status_code == 403)
    chk("azul no detiene", c.post("/api/detener", json={}, headers=H(ta)).status_code == 403)
    chk("general detiene", c.post("/api/detener", json={}, headers=H(tg)).status_code == 200)

    # --- buzón ---
    chk("plantillas visibles con token", len(c.get("/api/correo/plantillas", headers=H(tr)).json()["plantillas"]) >= 2)
    chk("azul no envía correos", c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(ta)).status_code == 403)
    chk("general no envía correos", c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(tg)).status_code == 403)
    chk("plantilla libre rechazada",
        c.post("/api/correo", json={"plantilla": "https://x.invalid"}, headers=H(tr)).status_code == 422)
    chk("campo de URL libre ignorado (no existe en el contrato)",
        "enlace" not in c.post("/api/correo", json={"plantilla": "paqueteria", "enlace": "https://evil.invalid"},
                               headers=H(tr)).json())
    r = c.post("/api/correo", json={"plantilla": "soporte_tecnico"}, headers=H(tr))
    chk("rojo envía al usuario de azul y no recibe el enlace",
        r.status_code == 200 and r.json()["para_usuario"] == "luis.gomez" and "enlace" not in r.json())
    chk("destinatario inexistente -> 400",
        c.post("/api/correo", json={"plantilla": "paqueteria", "para_usuario": "nadie"}, headers=H(tr)).status_code == 400)
    c.post("/api/correo", json={"plantilla": "paqueteria", "para_usuario": "ana.perez"}, headers=H(tr))

    chk("rojo no lee el buzón", c.get("/api/buzon", headers=H(tr)).status_code == 403)
    chk("espectador no lee el buzón", c.get("/api/buzon").status_code == 403)
    b = c.get("/api/buzon", headers=H(ta)).json()
    chk("azul ve solo sus correos (2: soporte y paquetería a luis)",
        b["usuario"] == "luis.gomez" and len(b["correos"]) == 2
        and {x["plantilla_id"] for x in b["correos"]} == {"soporte_tecnico", "paqueteria"})
    enlace = b["correos"][0]["enlace"]
    chk("enlace local generado por el servidor", enlace.startswith("/l/") and enlace in b["correos"][0]["cuerpo"])

    # --- clic ---
    antes = len(repositorio.por_defecto().auditoria(500))
    r = c.get(enlace)
    chk("clic muestra la página de entrenamiento",
        r.status_code == 200 and "enlace de prueba del laboratorio" in r.text
        and "default-src 'none'" in r.headers["content-security-policy"])
    aud = repositorio.por_defecto().auditoria(1)[0]
    chk("clic queda en auditoría", len(repositorio.por_defecto().auditoria(500)) == antes + 1
        and aud["accion"] == "CLIC_ENLACE" and aud["usuario"] == "luis.gomez")
    r = c.get("/l/inventado123")
    chk("enlace inventado -> 404 sin auditoría",
        r.status_code == 404 and len(repositorio.por_defecto().auditoria(500)) == antes + 1)
    chk("la página no refleja la petición", "<script" not in c.get("/l/%3Cscript%3Exx").text)

    # --- reglas evento -> consecuencia (riesgo de la partida) ---
    chk("el clic aplicó CLIC_ENLACE (+15)", srv.ESTADO_PARTIDA.riesgo_acumulado == 15)
    cid = b["correos"][0]["id"]
    chk("rojo no reporta correos", c.post(f"/api/correo/{cid}/reportar", headers=H(tr)).status_code == 403)
    chk("espectador no reporta correos", c.post(f"/api/correo/{cid}/reportar").status_code == 403)
    r = c.post(f"/api/correo/{cid}/reportar", headers=H(ta))
    chk("azul reporta su correo -> correo_reportado (-10)",
        r.status_code == 200 and r.json()["regla"]["riesgo"] == -10 and srv.ESTADO_PARTIDA.riesgo_acumulado == 5)
    chk("reportar dos veces -> 409 sin volver a restar",
        c.post(f"/api/correo/{cid}/reportar", headers=H(ta)).status_code == 409 and srv.ESTADO_PARTIDA.riesgo_acumulado == 5)
    ajeno = [x for x in repositorio.por_defecto().buzon(srv.PARTIDA_ID, "ana.perez")][0]["id"]
    chk("azul no reporta el correo de otro usuario -> 404",
        c.post(f"/api/correo/{ajeno}/reportar", headers=H(ta)).status_code == 404)
    chk("el buzón muestra el correo como reportado",
        [x["reportado"] for x in c.get("/api/buzon", headers=H(ta)).json()["correos"] if x["id"] == cid] == [1])

    # --- misiones del Equipo Azul ---
    chk("el reporte completó 'Reportar un correo sospechoso'",
        [m["titulo"] for m in r.json()["regla"]["misiones_completadas"]] == ["Reportar un correo sospechoso"])
    chk("rojo no ve misiones", c.get("/api/misiones", headers=H(tr)).status_code == 403)
    chk("espectador no ve misiones", c.get("/api/misiones").status_code == 403)
    m = c.get("/api/misiones", headers=H(ta)).json()
    estados = {x["id"]: x["estado"] for x in m["misiones"]}
    chk("azul ve su progreso (1 completada, CLIC_ENLACE no completa misiones, manual pendiente)",
        m["usuario"] == "luis.gomez" and estados == {1: "completada", 2: "pendiente", 3: "pendiente", 4: "pendiente"}
        and m["puntos"] == 10 and m["riesgo_partida"] == 5)
    chk("rojo no completa misiones", c.post("/api/misiones/3/completar", headers=H(tr)).status_code == 403)
    chk("azul no completa a mano una misión por evento", c.post("/api/misiones/2/completar", headers=H(ta)).status_code == 409)
    chk("azul completa la misión manual", c.post("/api/misiones/3/completar", headers=H(ta)).status_code == 200)
    chk("la manual no se completa dos veces", c.post("/api/misiones/3/completar", headers=H(ta)).status_code == 409)
    chk("puntos actualizados", c.get("/api/misiones", headers=H(ta)).json()["puntos"] == 15)

    # --- contener un enlace clicado ---
    sin_clic = [x for x in c.get("/api/buzon", headers=H(ta)).json()["correos"] if x["id"] != cid][0]
    chk("contener un enlace no clicado -> 409",
        c.post(f"/api/correo/{sin_clic['id']}/contener", headers=H(ta)).status_code == 409)
    chk("rojo no contiene enlaces", c.post(f"/api/correo/{cid}/contener", headers=H(tr)).status_code == 403)
    chk("azul no contiene el correo de otro usuario -> 404",
        c.post(f"/api/correo/{ajeno}/contener", headers=H(ta)).status_code == 404)
    r = c.post(f"/api/correo/{cid}/contener", headers=H(ta))
    chk("azul contiene el enlace clicado -> enlace_contenido (-15) completa la misión",
        r.status_code == 200 and r.json()["regla"]["riesgo"] == -15
        and [m["id"] for m in r.json()["regla"]["misiones_completadas"]] == [2]
        and srv.ESTADO_PARTIDA.riesgo_acumulado == 0)
    chk("contener dos veces -> 409", c.post(f"/api/correo/{cid}/contener", headers=H(ta)).status_code == 409)
    m = c.get("/api/misiones", headers=H(ta)).json()
    chk("misiones 1-3 completadas (30 pts), la del PDF pendiente",
        {x["id"]: x["estado"] for x in m["misiones"]} == {1: "completada", 2: "completada", 3: "completada",
                                                          4: "pendiente"} and m["puntos"] == 30)
    r = c.get(enlace)
    chk("un clic sobre el enlace contenido se bloquea y no suma riesgo",
        "bloqueado" in r.text.lower() and srv.ESTADO_PARTIDA.riesgo_acumulado == 0
        and repositorio.por_defecto().auditoria(1)[0]["accion"] == "CLIC_BLOQUEADO")

    # --- PDFs benignos adjuntos ---
    pdf_id = c.post("/api/correo", json={"plantilla": "recursos_humanos"}, headers=H(tr)).json()["id"]
    con_pdf = [x for x in c.get("/api/buzon", headers=H(ta)).json()["correos"] if x["id"] == pdf_id][0]
    chk("el correo de RR. HH. trae su PDF fijo", con_pdf["adjunto"]["archivo"] == "recibo_nomina.pdf")
    ev = lambda tipo, rec, t=ta: c.post("/api/evento", json={"tipo": tipo, "recurso": rec}, headers=H(t))  # noqa: E731
    chk("rojo no registra eventos de PDF", ev("pdf_abierto", f"correo:{pdf_id}", tr).status_code == 403)
    chk("espectador no registra eventos", c.post("/api/evento", json={"tipo": "pdf_abierto",
                                                                      "recurso": f"correo:{pdf_id}"}).status_code == 403)
    chk("tipo de evento libre rechazado", ev("ejecutar_macro", f"correo:{pdf_id}").status_code == 422)
    chk("recurso libre rechazado", ev("pdf_abierto", "../../data/lab.db").status_code == 422)
    chk("correo sin PDF -> 409", ev("pdf_abierto", f"correo:{cid}").status_code == 409)
    r = ev("pdf_abierto", f"correo:{pdf_id}")
    chk("abrir PDF -> descarga + misión «Revisar un documento recibido»",
        r.status_code == 200 and r.json()["descarga"] == "/pdf/recibo_nomina"
        and [m["id"] for m in r.json()["regla"]["misiones_completadas"]] == [4]
        and repositorio.por_defecto().auditoria(5)[1]["accion"] == "PDF_ABIERTO")
    d = c.get(r.json()["descarga"])
    chk("el PDF se sirve solo como descarga con nosniff",
        d.status_code == 200 and d.headers["content-type"] == "application/pdf"
        and d.headers["content-disposition"].startswith("attachment") and d.headers["x-content-type-options"] == "nosniff"
        and d.content.startswith(b"%PDF-"))
    chk("PDF fuera del catálogo -> 404", c.get("/pdf/..%2F..%2Fdata%2Flab.db").status_code == 404
        and c.get("/pdf/inventado").status_code == 404)
    antes = srv.ESTADO_PARTIDA.riesgo_acumulado
    srv.ESTADO_PARTIDA.aplicar_evento("CLIC_ENLACE")  # riesgo > 0 para ver el -10
    r = ev("pdf_reportado", f"correo:{pdf_id}")
    chk("reportar PDF -> riesgo -10", r.status_code == 200 and r.json()["regla"]["riesgo"] == -10
        and srv.ESTADO_PARTIDA.riesgo_acumulado == antes + 15 - 10)
    chk("reportar el PDF dos veces -> 409", ev("pdf_reportado", f"correo:{pdf_id}").status_code == 409)
    m = c.get("/api/misiones", headers=H(ta)).json()
    chk("las 4 misiones completadas (40 pts)", {x["estado"] for x in m["misiones"]} == {"completada"} and m["puntos"] == 40)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
