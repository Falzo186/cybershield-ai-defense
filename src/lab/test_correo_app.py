"""Pruebas offline de la aplicación de correo y del visor de documentos (Fase D, BD en memoria).
Ejecutar: python -m src.lab.test_correo_app"""
import hashlib
import sqlite3

from . import correos, documentos, repositorio, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repo = repositorio.abrir(":memory:")
    P, U = "p1", "ana.perez"
    sop = repo.crear_correo(P, "soporte_tecnico", U)["id"]
    rrhh = repo.crear_correo(P, "recursos_humanos", U)["id"]
    com = repo.crear_correo(P, "comunicado_interno", U)["id"]
    ajeno = repo.crear_correo(P, "paqueteria", "luis.gomez")["id"]
    chk("crear un correo registra CORREO_RECIBIDO", any(a["accion"] == "CORREO_RECIBIDO" for a in repo.auditoria(20)))
    b = {c["id"]: c for c in repo.buzon(P, U)}
    chk("el buzón trae prioridad, texto del enlace y carpeta",
        (b[sop]["prioridad"], b[com]["prioridad"], b[sop]["carpeta"]) == ("alta", "baja", "entrada")
        and b[sop]["texto_enlace"].startswith("https://portal."))
    chk("al llegar ningún correo está leído", not any(c["leido"] for c in b.values()))

    # --- lectura (por participante) ---
    chk("abrir un correo: primera lectura", repo.marcar_leido(P, U, sop, "Beto") == "nuevo")
    chk("volver a abrirlo no duplica el evento", repo.marcar_leido(P, U, sop, "Beto") == "ya")
    chk("otro participante del equipo también cuenta", repo.marcar_leido(P, U, sop, "Bea") == "nuevo")
    c = repo._correo(P, U, sop)
    chk("leído y por quién", c["leido"] and c["leido_por"] == "Beto, Bea")
    chk("abrir NO es comprometer: riesgo 0 en la regla", sesion.REGLAS_EVENTO["correo_abierto"]["riesgo"] == 0)
    chk("un correo de otro usuario no se puede abrir", repo.marcar_leido(P, U, ajeno, "Beto") is None)

    # --- verificar remitente (calculado del dominio, no declarado) ---
    v = repo.verificar_remitente(P, U, rrhh)
    chk("RR. HH. con «cybershieId»: imitación del dominio oficial", not v["oficial"] and v["parecido"]
        and "cybershieId" in v["dominio"] and v["indicadores"])
    chk("comunicado interno: dominio oficial", repo.verificar_remitente(P, U, com)["oficial"])
    chk("la verificación queda en auditoría", repo.auditoria(1)[0]["accion"] == "REMITENTE_VERIFICADO")

    # --- inspeccionar enlace sin abrirlo ---
    i = repo.inspeccionar_enlace(P, U, sop)
    chk("inspeccionar: el texto visible no coincide con el destino real",
        not i["coincide"] and i["destino_real"].startswith("/l/") and i["texto_mostrado"].startswith("https://"))
    chk("inspeccionar no cuenta como clic", not repo._correo(P, U, sop)["clicado"]
        and repo.auditoria(1)[0]["accion"] == "ENLACE_INSPECCIONADO")

    # --- responder (nunca sale del laboratorio) ---
    r = repo.responder(P, U, sop, "Beto", "¿Es real este aviso?")
    chk("responder a un correo de imitación se marca como respuesta a phishing", r["a_phishing"])
    chk("responder al comunicado interno no", not repo.responder(P, U, com, "Bea", "Recibido, gracias.")["a_phishing"])
    env = repo.respuestas(P, U)
    chk("las respuestas aparecen en «Enviados» con su destinatario", len(env) == 2 and env[0]["para"].endswith(".invalid"))
    try:
        repo.responder(P, U, sop, "Beto", "   ")
        vacia = False
    except ValueError:
        vacia = True
    chk("una respuesta vacía se rechaza", vacia)
    chk("la BD limita la respuesta a 1000 caracteres", _rechaza(repo, "INSERT INTO respuestas(correo_id,participante,texto,ts) "
                                                                  f"VALUES({sop},'x','{'a' * 1001}','t')"))
    chk("responder a un correo ajeno -> None", repo.responder(P, U, ajeno, "Beto", "hola") is None)

    # --- carpetas ---
    chk("archivar", repo.archivar(P, U, com, "Bea") is True and repo._correo(P, U, com)["carpeta"] == "archivados")
    chk("archivar dos veces no cambia nada", repo.archivar(P, U, com, "Bea") is False)
    chk("desarchivar vuelve a la entrada", repo.archivar(P, U, com, "Bea", archivar=False) is True
        and repo._correo(P, U, com)["carpeta"] == "entrada")
    repo.reportar_correo(P, U, sop)
    chk("un correo reportado pasa a «Sospechosos»", repo._correo(P, U, sop)["carpeta"] == "sospechosos")

    # --- visor seguro de documentos ---
    r = repo.evento_pdf(P, U, rrhh, "pdf_abierto")
    vista = r["vista"]
    datos = documentos.ruta("recibo_nomina").read_bytes()
    chk("el visor muestra el texto extraído del propio PDF", vista["texto"] == documentos.texto("recibo_nomina")
        and any("Recibo de nomina" in linea for linea in vista["texto"]))
    chk("el visor da el SHA-256 y el tamaño reales del archivo", vista["sha256"] == hashlib.sha256(datos).hexdigest()
        and vista["tamano_bytes"] == len(datos))
    chk("el visor explica el análisis y la procedencia", "solo texto" in vista["analisis"] and "cybershieId" in vista["procedencia"])
    chk("cada línea del visor está en el archivo", all(linea.encode("latin-1").replace(b"(", b"\\(").replace(b")", b"\\)")
                                                       in datos for linea in vista["texto"] if linea))
    chk("Rojo suma por el PDF abierto sin reportar ni aislar", repo.logros_rojo(P)["pdfs_sin_reportar"] == 1)

    # --- aislar adjunto ---
    chk("aislar el adjunto", repo.aislar_adjunto(P, U, rrhh, "Beto") == "aislado")
    chk("aislarlo dos veces -> ya_aislado", repo.aislar_adjunto(P, U, rrhh, "Beto") == "ya_aislado")
    chk("aislar sin adjunto -> sin_adjunto", repo.aislar_adjunto(P, U, sop, "Beto") == "sin_adjunto")
    chk("un adjunto aislado ya no se puede previsualizar", repo.evento_pdf(P, U, rrhh, "pdf_abierto") == "aislado")
    chk("aislar quita los puntos de Rojo por ese PDF", repo.logros_rojo(P)["pdfs_sin_reportar"] == 0)

    # --- Rojo: seguimiento de campaña ---
    e = {c["id"]: c for c in repo.enviados_rojo(P)}
    chk("Rojo ve sus envíos con clic y apertura de adjunto", e[rrhh]["adjunto_abierto"] == 1 and e[sop]["clicado"] == 0)
    chk("Rojo no ve si se leyó ni si se reportó", "leido" not in e[sop] and "reportado" not in e[sop])

    # --- reglas: todas explican su consecuencia ---
    chk("cada regla trae su explicación", all(r.get("explicacion") for r in sesion.REGLAS_EVENTO.values()))
    chk("responder a phishing sube el riesgo; aislar lo baja",
        sesion.REGLAS_EVENTO["respuesta_a_phishing"]["riesgo"] > 0 > sesion.REGLAS_EVENTO["archivo_aislado"]["riesgo"])
    chk("el dominio oficial es el de las plantillas legítimas", correos.verificar_remitente(
        correos.PLANTILLAS["comunicado_interno"]["de"])["oficial"])

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


def _rechaza(repo, sql):
    try:
        repo.conn.execute(sql)
    except sqlite3.IntegrityError:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
