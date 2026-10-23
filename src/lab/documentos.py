"""Catálogo FIJO de PDFs benignos de entrenamiento (data/pdf/). Solo texto: sin JavaScript, enlaces ni adjuntos.

Nunca se suben desde la UI ni se construye una ruta con datos del cliente: el id se busca en este catálogo y la
ruta sale de una constante del código.
"""
from pathlib import Path

RUTA_PDF = Path(__file__).resolve().parents[2] / "data" / "pdf"

DOCUMENTOS = {
    "recibo_nomina": {"archivo": "recibo_nomina.pdf", "titulo": "Recibo de nómina"},
    "comprobante_envio": {"archivo": "comprobante_envio.pdf", "titulo": "Comprobante de envío"},
    "politica_escritorio_limpio": {"archivo": "politica_escritorio_limpio.pdf", "titulo": "Política de escritorio limpio"},
}


def info(doc_id):
    """-> {id, archivo, titulo} o None si el documento no está en el catálogo."""
    d = DOCUMENTOS.get(doc_id) if isinstance(doc_id, str) else None
    return {"id": doc_id, **d} if d else None


def ruta(doc_id):
    """Ruta del PDF en disco. KeyError si no está en el catálogo."""
    return RUTA_PDF / DOCUMENTOS[doc_id]["archivo"]
