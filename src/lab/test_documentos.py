"""Pruebas offline de los PDFs benignos adjuntos (BD en memoria). Ejecutar: python -m src.lab.test_documentos"""
from . import correos, documentos, repositorio

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    chk("los PDFs del catálogo existen en data/pdf", all(documentos.ruta(d).is_file() for d in documentos.DOCUMENTOS))
    chk("los PDFs son solo texto (sin JavaScript, acciones ni adjuntos)",
        all(not any(x in documentos.ruta(d).read_bytes() for x in (b"/JavaScript", b"/JS", b"/OpenAction", b"/Launch",
                                                                   b"/EmbeddedFile", b"/URI"))
            for d in documentos.DOCUMENTOS))
    chk("un id fuera del catálogo no da ruta", documentos.info("../../etc/passwd") is None)
    chk("cada adjunto de plantilla está en el catálogo",
        all(p.get("adjunto") is None or p["adjunto"] in documentos.DOCUMENTOS for p in correos.PLANTILLAS.values()))

    repo = repositorio.abrir(":memory:")
    con = repo.crear_correo("p1", "recursos_humanos", "ana.perez")
    sin = repo.crear_correo("p1", "soporte_tecnico", "ana.perez")
    ajeno = repo.crear_correo("p1", "paqueteria", "luis.gomez")
    b = {c["id"]: c for c in repo.buzon("p1", "ana.perez")}
    chk("el buzón trae el adjunto del catálogo", b[con["id"]]["adjunto"]["archivo"] == "recibo_nomina.pdf"
        and b[sin["id"]]["adjunto"] is None)

    r = repo.evento_pdf("p1", "ana.perez", con["id"], "pdf_abierto")
    chk("abrir el PDF -> evento en auditoría", r["doc"]["id"] == "recibo_nomina"
        and repo.auditoria(1)[0]["accion"] == "PDF_ABIERTO" and repo.auditoria(1)[0]["recurso"] == f"correo:{con['id']}")
    chk("abrir dos veces se permite (es solo un evento)", isinstance(repo.evento_pdf("p1", "ana.perez", con["id"],
                                                                                    "pdf_abierto"), dict))
    chk("correo sin adjunto -> sin_adjunto", repo.evento_pdf("p1", "ana.perez", sin["id"], "pdf_abierto") == "sin_adjunto")
    chk("PDF de otro usuario -> None", repo.evento_pdf("p1", "ana.perez", ajeno["id"], "pdf_reportado") is None)
    chk("reportar el PDF -> evento", isinstance(repo.evento_pdf("p1", "ana.perez", con["id"], "pdf_reportado"), dict)
        and repo.auditoria(1)[0]["accion"] == "PDF_REPORTADO")
    chk("reportar dos veces -> ya_reportado", repo.evento_pdf("p1", "ana.perez", con["id"], "pdf_reportado") == "ya_reportado")
    b = {c["id"]: c for c in repo.buzon("p1", "ana.perez")}
    chk("el buzón marca el PDF como abierto y reportado", b[con["id"]]["pdf_abierto"] == 1 and b[con["id"]]["pdf_reportado"] == 1)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
