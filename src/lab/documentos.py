"""Catálogo FIJO de PDFs benignos de entrenamiento (data/pdf/). Solo texto: sin JavaScript, enlaces ni adjuntos.

Nunca se suben desde la UI ni se construye una ruta con datos del cliente: el id se busca en este catálogo y la
ruta sale de una constante del código. Desde la Fase D los documentos se ven en un VISOR dentro de la aplicación
(texto extraído del propio archivo + metadatos de análisis); ya no se descargan al sistema del participante.
"""
import hashlib
import re
from pathlib import Path

RUTA_PDF = Path(__file__).resolve().parents[2] / "data" / "pdf"

# Metadatos sintéticos de análisis. El riesgo describe el CONTEXTO (quién lo envía y para qué), no el archivo: los
# tres son PDFs de solo texto e inofensivos; eso es justo lo que muestra el análisis.
DOCUMENTOS = {
    "recibo_nomina": {
        "archivo": "recibo_nomina.pdf", "titulo": "Recibo de nómina", "riesgo": "medio",
        "indicadores": ["Llega en un correo cuyo dominio imita al oficial (cybershieId con «I» mayúscula)",
                        "Nómina no solicitada fuera del calendario habitual"],
    },
    "comprobante_envio": {
        "archivo": "comprobante_envio.pdf", "titulo": "Comprobante de envío", "riesgo": "medio",
        "indicadores": ["Remitente externo sin relación con la empresa", "Envío que nadie esperaba"],
    },
    "politica_escritorio_limpio": {
        "archivo": "politica_escritorio_limpio.pdf", "titulo": "Política de escritorio limpio", "riesgo": "bajo",
        "indicadores": [],
    },
}
ANALISIS = ("PDF de solo texto: sin JavaScript, acciones automáticas, enlaces ni archivos incrustados. "
            "Se muestra como texto en el visor; nada se ejecuta en tu equipo.")
_TEXTO = re.compile(rb"\(((?:\\.|[^\\)])*)\) '")


def info(doc_id):
    """-> {id, archivo, titulo, riesgo} o None si el documento no está en el catálogo."""
    d = DOCUMENTOS.get(doc_id) if isinstance(doc_id, str) else None
    return {"id": doc_id, "archivo": d["archivo"], "titulo": d["titulo"], "riesgo": d["riesgo"]} if d else None


def ruta(doc_id):
    """Ruta del PDF en disco. KeyError si no está en el catálogo."""
    return RUTA_PDF / DOCUMENTOS[doc_id]["archivo"]


def texto(doc_id):
    """Líneas de texto extraídas del PROPIO archivo (flujo de contenido sin comprimir de estos PDFs): lo que se ve en
    el visor es lo que contiene el documento, no una copia aparte."""
    datos = ruta(doc_id).read_bytes()
    return [re.sub(rb"\\(.)", rb"\1", m.group(1)).decode("latin-1") for m in _TEXTO.finditer(datos)]


def vista_previa(doc_id, procedencia):
    """Lo que muestra el visor seguro. procedencia: texto sobre el correo que lo trajo."""
    d = DOCUMENTOS[doc_id]
    datos = ruta(doc_id).read_bytes()
    return {**info(doc_id), "tipo": "PDF (solo texto)", "tamano_bytes": len(datos),
            "sha256": hashlib.sha256(datos).hexdigest(), "procedencia": procedencia,
            "indicadores": list(d["indicadores"]), "analisis": ANALISIS, "texto": texto(doc_id)}
