"""Pruebas del servidor sin Ollama (sesiones, partida, buzón, misiones, marcador), con BD en memoria.
Ejecutar: python server/test_app.py"""
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
    c.__enter__()  # un solo bucle de eventos para toda la prueba (la tarea del temporizador vive en él)
    H = lambda t: {"X-Equipo-Token": t}  # noqa: E731
    unirse = lambda equipo, nombre, **extra: c.post("/api/sesion", json={"nombre": nombre, "equipo": equipo, **extra})  # noqa: E731
    mensaje = lambda r: r.json().get("mensaje", "")  # noqa: E731

    # --- espectador (sin sesión) ---
    chk("espectador lee estado", c.get("/api/estado").status_code == 200)
    chk("espectador no lee usuarios", c.get("/api/usuarios").status_code == 403)
    chk("espectador no detiene", c.post("/api/detener", json={}).status_code == 403)
    chk("token falso rechazado", c.post("/api/detener", json={}, headers=H("falso")).status_code == 403)
    chk("no se puede unir a un equipo inventado", unirse("morado", "Nadie").status_code == 422)

    # --- sesiones por participante (nombre visible + equipo) ---
    tr = unirse("rojo", "Rita").json()["token"]
    chk("árbitro sin código -> 403", unirse("general", "Juez").status_code == 403)
    chk("árbitro con código erróneo -> 403", unirse("general", "Juez", codigo="no-es").status_code == 403)
    tg = unirse("general", "Juez", codigo=srv.CODIGO_ARBITRO).json()["token"]
    chk("nombre repetido (sin distinguir mayúsculas) -> 409", unirse("azul", "rita").status_code == 409)
    chk("nombre inválido -> 400", unirse("rojo", "<b>").status_code == 400)
    yo = c.get("/api/sesion", headers=H(tr)).json()["participante"]
    chk("reconexión: GET /api/sesion devuelve al participante",
        (yo["nombre"], yo["equipo"], yo["rol"]) == ("Rita", "rojo", "jugador") and "token" not in yo)
    chk("un token desconocido no reconecta", c.get("/api/sesion", headers=H("falso")).status_code == 403)
    te = unirse("espectador", "Público").json()["token"]
    chk("una sesión de espectador no puede modificar la partida",
        c.post("/api/detener", json={}, headers=H(te)).status_code == 403
        and c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(te)).status_code == 403)

    # --- partida en preparación: nada cuenta hasta que el árbitro la inicia ---
    p = c.get("/api/partida", headers=H(te)).json()
    chk("la partida empieza en preparación", p["fase"] == "preparacion" and p["restante_s"] is None)
    r = c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(tr))
    chk("antes de iniciar, Rojo no envía correos (409)", r.status_code == 409 and "no ha empezado" in mensaje(r))
    chk("finalizar antes de iniciar -> 409", c.post("/api/partida/finalizar", headers=H(tg)).status_code == 409)
    chk("Rojo no inicia la partida", c.post("/api/partida/iniciar", json={"duracion_min": 5}, headers=H(tr)).status_code == 403)
    chk("duración no permitida -> 400", c.post("/api/partida/iniciar", json={"duracion_min": 7}, headers=H(tg)).status_code == 400)
    chk("no hay partida nueva sin terminar la actual",
        c.post("/api/partida/nueva", headers=H(tg)).status_code == 409)
    r = c.post("/api/partida/iniciar", json={"duracion_min": 10}, headers=H(tg))
    chk("el árbitro inicia la partida de 10 min", r.status_code == 200 and r.json()["fase"] == "en_curso"
        and 598 <= r.json()["restante_s"] <= 600)
    chk("iniciar dos veces -> 409", c.post("/api/partida/iniciar", json={"duracion_min": 5}, headers=H(tg)).status_code == 409)

    # --- correo antes de que azul entre ---
    chk("correo sin azul en la partida -> 409",
        c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(tr)).status_code == 409)

    # --- Azul: varios participantes, un buzón de equipo ---
    chk("azul con usuario inexistente -> 400", unirse("azul", "Beto", usuario="nadie").status_code == 400)
    r = unirse("azul", "Beto", usuario="luis.gomez").json()
    ta = r["token"]
    chk("azul juega con el usuario semilla elegido", r["usuario_azul"] == "luis.gomez")
    r = unirse("azul", "Bea", usuario="ana.perez").json()
    ta2 = r["token"]
    chk("un segundo participante azul se une sin cambiar el usuario del buzón", r["usuario_azul"] == "luis.gomez")
    chk("tokens distintos por participante", len({tr, ta, ta2, tg, te}) == 5)
    parts = c.get("/api/partida", headers=H(te)).json()["participantes"]
    chk("la partida lista a los participantes (sin tokens)",
        {(x["nombre"], x["equipo"]) for x in parts} == {("Rita", "rojo"), ("Juez", "general"), ("Público", "espectador"),
                                                         ("Beto", "azul"), ("Bea", "azul")}
        and all("token" not in x for x in parts))

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
    estados = {x["id"]: x["estado"] for x in m["misiones"] if x["id"] <= 4}
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
        {x["id"]: x["estado"] for x in m["misiones"] if x["id"] <= 4} == {1: "completada", 2: "completada", 3: "completada",
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
    chk("abrir PDF -> vista previa del visor seguro + misión «Revisar un documento recibido»",
        r.status_code == 200 and r.json()["vista"]["id"] == "recibo_nomina" and r.json()["vista"]["texto"]
        and len(r.json()["vista"]["sha256"]) == 64 and "descarga" not in r.json()
        and [m["id"] for m in r.json()["regla"]["misiones_completadas"]] == [4]
        and repositorio.por_defecto().auditoria(5)[1]["accion"] == "PDF_ABIERTO")
    d = c.get("/pdf/recibo_nomina")  # la UI ya no lo descarga; la ruta sigue sirviéndolo solo como adjunto
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
    chk("las 4 misiones del buzón completadas (40 pts)",
        {x["estado"] for x in m["misiones"] if x["id"] <= 4} == {"completada"} and m["puntos"] == 40)

    # --- marcador de la partida (general / espectadores) ---
    mk = srv._marcador()
    chk("marcador: puntos de Azul y misiones", mk["usuario_azul"] == "luis.gomez" and mk["puntos_azul"] == 40
        and (mk["misiones_completadas"], mk["misiones_total"]) == (4, 8))
    chk("marcador: riesgo actual de la partida", mk["riesgo"] == srv.ESTADO_PARTIDA.riesgo_acumulado)
    chk("marcador: Rojo en 0 (el enlace clicado se contuvo y el PDF abierto se reportó)",
        (mk["puntos_rojo"], mk["rojo_enlaces_sin_contener"], mk["rojo_pdfs_sin_reportar"]) == (0, 0, 0))
    chk("marcador: sin batallas IA vs IA no hay denegaciones de Rojo", mk["denegaciones_rojo"] == 0)
    chk("marcador: conteo de eventos clave (el clic bloqueado no cuenta)",
        (mk["clics"], mk["contenciones"], mk["correos_reportados"], mk["pdf_abiertos"], mk["pdf_reportados"])
        == (2, 1, 1, 1, 1))  # 2 clics = el real + el CLIC_ENLACE aplicado a mano antes de reportar el PDF
    import asyncio, json  # noqa: E401
    sse = asyncio.run(srv._hook_marcador())
    sse = sse[sse.index("event: marcador_partida\n"):]  # el mismo hook envía antes el estado de la partida
    chk("el SSE entrega el marcador al conectar (también a espectadores)",
        sse.startswith("event: marcador_partida\n") and json.loads(sse.split("data: ", 1)[1])["puntos_azul"] == 40)
    eventos = []
    original = srv.ms.emitir
    srv.ms.emitir = lambda tipo, datos: eventos.append((tipo, datos))
    try:
        c.post(f"/api/correo/{pdf_id}/reportar", headers=H(ta))
    finally:
        srv.ms.emitir = original
    chk("cada regla aplicada difunde el marcador en vivo",
        [d["correos_reportados"] for t, d in eventos if t == "marcador_partida"] == [2])

    # --- puntaje de Rojo en vivo: un enlace clicado sin contener (+10) y un PDF abierto sin reportar (+5) ---
    nuevo = c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(tr)).json()["id"]
    x = [y for y in c.get("/api/buzon", headers=H(ta)).json()["correos"] if y["id"] == nuevo][0]
    c.get(x["enlace"])
    ev("pdf_abierto", f"correo:{nuevo}")
    chk("Rojo suma 15 (enlace sin contener + PDF sin reportar)", srv._marcador()["puntos_rojo"] == 15)

    # --- aplicación de correo (Fase D) ---
    sop_id = c.post("/api/correo", json={"plantilla": "soporte_tecnico"}, headers=H(tr)).json()["id"]
    com_id = c.post("/api/correo", json={"plantilla": "comunicado_interno"}, headers=H(tr)).json()["id"]
    P = lambda ruta, tok, **j: c.post(ruta, json=j or {}, headers=H(tok))  # noqa: E731
    chk("Rojo no gestiona el buzón de Azul (leer/verificar/responder/aislar -> 403)",
        all(P(f"/api/correo/{sop_id}/{a}", tr, **({"texto": "x"} if a == "responder" else {})).status_code == 403
            for a in ("leer", "verificar", "inspeccionar", "responder", "archivar", "aislar")))
    chk("el espectador tampoco", P(f"/api/correo/{sop_id}/leer", te).status_code == 403)
    r = P(f"/api/correo/{sop_id}/leer", ta)
    chk("Beto abre el correo: primera lectura con regla de riesgo 0", r.status_code == 200 and r.json()["nuevo"]
        and r.json()["regla"]["riesgo"] == 0 and r.json()["regla"]["explicacion"])
    chk("volver a abrirlo no repite la regla", P(f"/api/correo/{sop_id}/leer", ta).json()["regla"] is None)
    P(f"/api/correo/{sop_id}/leer", ta2)
    x = [y for y in c.get("/api/buzon", headers=H(ta)).json()["correos"] if y["id"] == sop_id][0]
    chk("el buzón dice quién lo leyó (cada participante con su nombre)", x["leido"] and x["leido_por"] == "Beto, Bea"
        and x["prioridad"] == "alta" and x["carpeta"] == "entrada")
    v = P(f"/api/correo/{sop_id}/verificar", ta).json()
    chk("verificar remitente: imitación del dominio oficial", not v["oficial"] and v["parecido"] and v["indicadores"])
    chk("verificar el comunicado interno: oficial", P(f"/api/correo/{com_id}/verificar", ta).json()["oficial"])
    i = P(f"/api/correo/{sop_id}/inspeccionar", ta).json()
    chk("inspeccionar: el destino real es la ruta local, distinto del texto visible",
        not i["coincide"] and i["destino_real"].startswith("/l/") and i["texto_mostrado"].startswith("https://"))
    riesgo0 = srv.ESTADO_PARTIDA.riesgo_acumulado
    r = P(f"/api/correo/{sop_id}/responder", ta, texto="¿Es real?")
    chk("responder al phishing: respuesta_a_phishing, riesgo +10 y explicación",
        r.status_code == 200 and r.json()["a_phishing"] and r.json()["regla"]["evento"] == "respuesta_a_phishing"
        and srv.ESTADO_PARTIDA.riesgo_acumulado == min(100, riesgo0 + 10) and "verificar el remitente" in r.json()["regla"]["explicacion"])
    r = P(f"/api/correo/{com_id}/responder", ta2, texto="Recibido.")
    chk("responder al comunicado interno: respuesta normal", r.json()["regla"]["evento"] == "respuesta_enviada")
    chk("respuesta vacía -> 422", P(f"/api/correo/{com_id}/responder", ta, texto="").status_code == 422)
    env = c.get("/api/buzon", headers=H(ta)).json()["enviados"]
    chk("las respuestas aparecen en «Enviados» con quién respondió", {(e["participante"], e["correo_id"]) for e in env}
        >= {("Beto", sop_id), ("Bea", com_id)})
    chk("archivar el comunicado", P(f"/api/correo/{com_id}/archivar", ta).json()["cambio"] is True and
        [y for y in c.get("/api/buzon", headers=H(ta)).json()["correos"] if y["id"] == com_id][0]["carpeta"] == "archivados")
    chk("desarchivarlo", P(f"/api/correo/{com_id}/archivar", ta, archivar=False).json()["cambio"] is True)
    chk("un correo ajeno -> 404", P(f"/api/correo/{ajeno}/verificar", ta).status_code == 404)
    chk("aislar sin adjunto -> 409", P(f"/api/correo/{sop_id}/aislar", ta).status_code == 409)
    r = P(f"/api/correo/{com_id}/aislar", ta)
    chk("aislar el adjunto: regla archivo_aislado", r.status_code == 200 and r.json()["regla"]["evento"] == "archivo_aislado")
    chk("el adjunto aislado ya no se previsualiza (409)", ev("pdf_abierto", f"correo:{com_id}").status_code == 409)
    e = {y["id"]: y for y in c.get("/api/correo/enviados", headers=H(tr)).json()["enviados"]}
    chk("Rojo ve su campaña (clic y adjunto abierto), no si se leyó o reportó", sop_id in e and "leido" not in e[sop_id]
        and "reportado" not in e[sop_id])

    # --- incidentes, credenciales ficticias y misiones con responsable (Fase E) ---
    enl_sop = [y for y in c.get("/api/buzon", headers=H(ta)).json()["correos"] if y["id"] == sop_id][0]["enlace"]
    chk("sin abrir el enlace no se pueden entregar credenciales (409)", c.post(enl_sop + "/credenciales").status_code == 409)
    pag = c.get(enl_sop)
    chk("la página del enlace de soporte imita un inicio de sesión SIN campos de texto",
        'action="' + enl_sop + '/credenciales"' in pag.text and "<input" not in pag.text
        and "form-action 'self'" in pag.headers["content-security-policy"])
    m7 = {x["id"]: x for x in c.get("/api/misiones", headers=H(ta)).json()["misiones"]}
    chk("revocar está bloqueada hasta abrir un incidente", m7[7]["estado"] == "bloqueada"
        and m7[7]["requiere"] == ["Abrir un incidente de seguridad"])
    rojo0 = srv._marcador()["puntos_rojo"]
    r = c.post(enl_sop + "/credenciales")
    chk("entregar la contraseña en la página falsa: credencial comprometida", r.status_code == 200
        and "COMPROMETIDA" in r.text and c.get("/api/credenciales", headers=H(ta)).json()["estado"] == "comprometida")
    mk = srv._marcador()
    chk("Rojo +15 por la credencial sin revocar y el marcador la cuenta",
        mk["puntos_rojo"] == rojo0 + 15 and mk["rojo_credenciales_sin_revocar"] == 1 and mk["credenciales_comprometidas"] == 1)
    chk("enviarla dos veces no suma otra vez", c.post(enl_sop + "/credenciales").status_code == 200
        and srv._marcador()["puntos_rojo"] == rojo0 + 15)
    chk("Rojo ve la credencial obtenida en su campaña", [y for y in c.get("/api/correo/enviados", headers=H(tr))
                                                          .json()["enviados"] if y["id"] == sop_id][0]["credencial_obtenida"])
    chk("Rojo y el espectador no ven credenciales ni incidentes",
        c.get("/api/credenciales", headers=H(tr)).status_code == 403 and c.get("/api/incidentes", headers=H(tr)).status_code == 403
        and c.get("/api/incidentes", headers=H(te)).status_code == 403)
    chk("Rojo no revoca ni abre incidentes", P("/api/credenciales/revocar", tr).status_code == 403
        and P("/api/incidentes", tr, titulo="x" * 5, severidad="alta").status_code == 403)
    chk("severidad inventada -> 422", P("/api/incidentes", ta, titulo="Phishing", severidad="enorme").status_code == 422)
    chk("asociar un correo ajeno -> 404", P("/api/incidentes", ta, titulo="Phishing", severidad="alta",
                                           correo_id=ajeno).status_code == 404)
    r = P("/api/incidentes", ta, titulo="Credencial robada por phishing", severidad="critica", correo_id=sop_id)
    inc = r.json()["incidente"]
    chk("Beto abre un incidente: completa su misión con él como autor y la evidencia",
        r.status_code == 200 and inc["abierto_por"] == "Beto"
        and [m["id"] for m in r.json()["regla"]["misiones_completadas"]] == [6])
    m6 = {x["id"]: x for x in c.get("/api/misiones", headers=H(ta)).json()["misiones"]}
    chk("la misión registra quién y la evidencia", (m6[6]["completada_por"], m6[6]["evidencia"]) ==
        ("Beto", f"incidente:{inc['id']}") and m6[7]["estado"] == "pendiente")
    chk("Bea asume la misión de revocar", P("/api/misiones/7/asumir", ta2).json()["responsable"] == "Bea"
        and {x["id"]: x for x in c.get("/api/misiones", headers=H(ta)).json()["misiones"]}[7]["responsable"] == "Bea")
    chk("Rojo no asume misiones", P("/api/misiones/7/asumir", tr).status_code == 403)
    chk("el árbitro ve los incidentes", c.get("/api/incidentes", headers=H(tg)).json()["incidentes"][0]["id"] == inc["id"])
    chk("no se salta de abierto a resuelto (409)", P(f"/api/incidentes/{inc['id']}/estado", ta, estado="resuelto",
                                                     resolucion="Todo arreglado ya.").status_code == 409)
    P(f"/api/incidentes/{inc['id']}/estado", ta, estado="en_investigacion")
    r = P(f"/api/incidentes/{inc['id']}/estado", ta, estado="resuelto", resolucion="Todo arreglado ya.")
    chk("no se resuelve con la amenaza activa y explica qué falta (409)", r.status_code == 409
        and "credencial" in mensaje(r) and "contenido" in mensaje(r))
    r = P("/api/credenciales/revocar", ta2)
    chk("Bea revoca la credencial: regla -15 y misión completada", r.status_code == 200
        and r.json()["regla"]["riesgo"] == -15 and [m["id"] for m in r.json()["regla"]["misiones_completadas"]] == [7])
    chk("revocar dos veces -> 409", P("/api/credenciales/revocar", ta).status_code == 409)
    chk("Rojo pierde los 15 de la credencial", srv._marcador()["puntos_rojo"] == rojo0)
    P(f"/api/correo/{sop_id}/contener", ta)
    r = P(f"/api/incidentes/{inc['id']}/estado", ta, estado="resuelto", resolucion="Credencial revocada y enlace contenido.")
    chk("con todo contenido, el incidente se resuelve y completa su misión", r.status_code == 200
        and r.json()["incidente"]["estado"] == "resuelto" and [m["id"] for m in r.json()["regla"]["misiones_completadas"]] == [8])
    chk("un incidente resuelto no cambia de estado (409)",
        P(f"/api/incidentes/{inc['id']}/estado", ta, estado="en_investigacion").status_code == 409)
    chk("asumir una misión completada -> 409", P("/api/misiones/8/asumir", ta).status_code == 409)
    chk("Azul no ve los envíos de Rojo", c.get("/api/correo/enviados", headers=H(ta)).status_code == 403)
    acc = {f["accion"] for f in repositorio.por_defecto().auditoria(500)}
    chk("todas las acciones del correo quedan en la auditoría", {"CORREO_RECIBIDO", "CORREO_ABIERTO", "REMITENTE_VERIFICADO",
        "ENLACE_INSPECCIONADO", "RESPUESTA_ENVIADA", "CORREO_ARCHIVADO", "ARCHIVO_AISLADO"} <= acc)

    # --- finalizar la partida ---
    chk("rojo no finaliza", c.post("/api/partida/finalizar", headers=H(tr)).status_code == 403)
    chk("azul no finaliza", c.post("/api/partida/finalizar", headers=H(ta)).status_code == 403)
    chk("espectador no finaliza", c.post("/api/partida/finalizar").status_code == 403)
    eventos = []
    srv.ms.emitir = lambda tipo, datos: eventos.append((tipo, datos))
    try:
        r = c.post("/api/partida/finalizar", headers=H(tg))
    finally:
        srv.ms.emitir = original
    fin = r.json()
    chk("general finaliza: puntajes congelados y ganador", r.status_code == 200
        and (fin["puntos_rojo"], fin["puntos_azul"], fin["ganador"]) == (15, 90, "azul"))  # 40 buzón + 5 verificar + 10 incidente + 20 revocar + 15 resolver
    chk("se difunde el resultado por SSE", [t for t, _ in eventos if t in ("marcador_partida", "partida_finalizada")]
        == ["marcador_partida", "partida_finalizada"])
    chk("finalizar dos veces -> 409", c.post("/api/partida/finalizar", headers=H(tg)).status_code == 409)
    chk("tras finalizar, Rojo no envía correos (409)",
        c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(tr)).status_code == 409)
    chk("tras finalizar, Azul no reporta (409)", c.post(f"/api/correo/{nuevo}/reportar", headers=H(ta)).status_code == 409)
    chk("tras finalizar, Azul no contiene (409)", c.post(f"/api/correo/{nuevo}/contener", headers=H(ta)).status_code == 409)
    chk("tras finalizar, Azul no registra eventos de PDF (409)", ev("pdf_reportado", f"correo:{nuevo}").status_code == 409)
    chk("tras finalizar, Azul no completa misiones (409)", c.post("/api/misiones/3/completar", headers=H(ta)).status_code == 409)
    antes = len(repositorio.por_defecto().auditoria(500))
    chk("tras finalizar, un clic no cuenta (409 sin auditoría)", c.get(x["enlace"]).status_code == 409
        and len(repositorio.por_defecto().auditoria(500)) == antes)
    mk = srv._marcador()
    chk("el marcador queda congelado con el resultado", mk["puntos_rojo"] == 15 and mk["final"]["ganador"] == "azul")
    chk("la finalización queda en auditoría", repositorio.por_defecto().auditoria(500)[0]["accion"] == "PARTIDA_FINALIZADA")
    chk("la vista de Azul sigue pudiendo leer su buzón", c.get("/api/buzon", headers=H(ta)).status_code == 200)
    p = c.get("/api/partida", headers=H(te)).json()
    chk("la partida queda finalizada por el árbitro", p["fase"] == "finalizada" and p["motivo_fin"] == "arbitro"
        and p["restante_s"] == 0)

    # --- partida nueva (sin reiniciar el servidor) y fin por tiempo ---
    chk("Rojo no empieza una partida nueva", c.post("/api/partida/nueva", headers=H(tr)).status_code == 403)
    anterior = srv.PARTIDA_ID
    r = c.post("/api/partida/nueva", headers=H(tg))
    chk("el árbitro empieza una partida nueva en preparación", r.status_code == 200 and r.json()["fase"] == "preparacion"
        and r.json()["id"] != anterior and srv.PARTIDA_ID == r.json()["id"])
    chk("las sesiones se conservan", c.get("/api/sesion", headers=H(ta)).status_code == 200)
    chk("buzón, marcador y riesgo empiezan de cero",
        c.get("/api/buzon", headers=H(ta)).json()["correos"] == [] and srv._marcador()["puntos_azul"] == 0
        and srv._marcador()["final"] is None and srv.ESTADO_PARTIDA.riesgo_acumulado == 0)
    c.post("/api/partida/iniciar", json={"duracion_min": 5}, headers=H(tg))
    chk("en la nueva partida Rojo vuelve a poder enviar",
        c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(tr)).status_code == 200)
    srv.PARTIDA._reloj = lambda: 10 ** 12  # el reloj del servidor llega al final de los 5 min
    r = c.post("/api/correo", json={"plantilla": "paqueteria"}, headers=H(tr))
    chk("al agotarse el tiempo la partida se cierra sola y las acciones dan 409",
        r.status_code == 409 and "finalizó" in mensaje(r))
    p = c.get("/api/partida", headers=H(te)).json()
    chk("fin por tiempo, con resultado congelado", p["fase"] == "finalizada" and p["motivo_fin"] == "tiempo"
        and srv._marcador()["final"]["motivo"] == "tiempo")
    c.__exit__(None, None, None)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
