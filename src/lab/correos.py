"""Plantillas FIJAS de correos de entrenamiento (sin LLM). Remitentes y dominios ficticios (.invalid).

El equipo Rojo solo elige plantilla y destinatario; las variables ({usuario}, {fecha}, {enlace}) las rellena el
SERVIDOR, y {enlace} es siempre una ruta local /l/<id> generada por él: nada sale del laboratorio.
"""

PLANTILLAS = {
    "soporte_tecnico": {
        "nombre": "Soporte técnico",
        "de": "soporte-ti@cybershield.invalid",
        "asunto": "Acción requerida: verificación de la cuenta de {usuario}",
        "cuerpo": ("Hola {usuario}:\n\nEl {fecha} detectamos un inicio de sesión inusual en tu cuenta. "
                   "Para evitar el bloqueo, confirma tus datos en las próximas 24 horas:\n{enlace}\n\n"
                   "Equipo de Soporte TI"),
    },
    "recursos_humanos": {
        "nombre": "Recursos humanos",
        "de": "rrhh-nomina@cybershield.invalid",
        "asunto": "Actualización de tu recibo de nómina ({fecha})",
        "cuerpo": ("Estimado/a {usuario}:\n\nYa está disponible la actualización de tu recibo de nómina. "
                   "Revisa el documento antes del cierre de mes:\n{enlace}\n\nDepartamento de Recursos Humanos"),
    },
    "paqueteria": {
        "nombre": "Paquetería",
        "de": "avisos@envios-rapidos.invalid",
        "asunto": "Tu paquete no pudo ser entregado",
        "cuerpo": ("Hola {usuario}:\n\nEl {fecha} intentamos entregar un paquete a tu nombre sin éxito. "
                   "Reprograma la entrega aquí:\n{enlace}\n\nServicio de mensajería"),
    },
}


def catalogo():
    """Vista para el equipo Rojo: id y nombre de cada plantilla (sin cuerpos)."""
    return [{"id": k, "nombre": p["nombre"]} for k, p in PLANTILLAS.items()]


def componer(plantilla_id, usuario, enlace, fecha):
    """-> (de, asunto, cuerpo). KeyError si la plantilla no existe. Las plantillas son constantes del código."""
    p = PLANTILLAS[plantilla_id]
    variables = {"usuario": usuario, "enlace": enlace, "fecha": fecha}
    return p["de"], p["asunto"].format(**variables), p["cuerpo"].format(**variables)
