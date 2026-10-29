"""Plantillas FIJAS de correos de entrenamiento (sin LLM). Remitentes y dominios ficticios (.invalid).

El equipo Rojo solo elige plantilla y destinatario; las variables ({usuario}, {fecha}, {enlace}) las rellena el
SERVIDOR, y {enlace} es siempre una ruta local /l/<id> generada por él: nada sale del laboratorio.
"adjunto" es un id FIJO de documentos.DOCUMENTOS (PDF benigno) o None.

Fase D: cada plantilla declara su prioridad, el texto que el correo MUESTRA como enlace (el destino real es siempre la
ruta local) y los indicadores que un analista debería notar. Que el remitente sea o no de la organización NO se
declara: se calcula comparando su dominio con DOMINIO_OFICIAL (así un dominio parecido, como «cybershieId» con «I»
mayúscula, falla la verificación igual que en la vida real). «comunicado_interno» es legítimo: sirve para practicar
también los falsos positivos.
"""

DOMINIO_OFICIAL = "cybershield.invalid"

PLANTILLAS = {
    "soporte_tecnico": {
        "nombre": "Soporte técnico",
        "de": "soporte-ti@cybershield-soporte.invalid",
        "prioridad": "alta",
        "texto_enlace": "https://portal.cybershield.invalid/verificar-cuenta",
        "indicadores": ["Dominio parecido pero distinto del oficial (cybershield-soporte.invalid)",
                        "Urgencia: amenaza de bloqueo en 24 horas", "Pide confirmar datos en un enlace"],
        "asunto": "Acción requerida: verificación de la cuenta de {usuario}",
        "cuerpo": ("Hola {usuario}:\n\nEl {fecha} detectamos un inicio de sesión inusual en tu cuenta. "
                   "Para evitar el bloqueo, confirma tus datos en las próximas 24 horas:\n{enlace}\n\n"
                   "Equipo de Soporte TI"),
        "adjunto": None,
        # La página del enlace imita un inicio de sesión: si el empleado «envía» su contraseña (simulado, sin campos
        # de texto) la credencial ficticia de su cuenta queda comprometida hasta que Azul la revoque.
        "pide_credenciales": True,
    },
    "recursos_humanos": {
        "nombre": "Recursos humanos",
        "de": "rrhh-nomina@cybershieId.invalid",
        "prioridad": "normal",
        "texto_enlace": "https://rrhh.cybershield.invalid/acuse",
        "indicadores": ["El dominio usa una «I» mayúscula en lugar de «l» (cybershieId)",
                        "Adjunto de nómina no solicitado", "Enlace para un «acuse» que no hace falta"],
        "asunto": "Actualización de tu recibo de nómina ({fecha})",
        "cuerpo": ("Estimado/a {usuario}:\n\nYa está disponible la actualización de tu recibo de nómina. "
                   "Revisa el documento adjunto antes del cierre de mes:\n{enlace}\n\nDepartamento de Recursos Humanos"),
        "adjunto": "recibo_nomina",
    },
    "paqueteria": {
        "nombre": "Paquetería",
        "de": "avisos@envios-rapidos.invalid",
        "prioridad": "normal",
        "texto_enlace": "https://envios-rapidos.invalid/reprogramar",
        "indicadores": ["Remitente externo sin relación con la empresa", "Entrega que nadie esperaba",
                        "Enlace para «reprogramar» con datos personales"],
        "asunto": "Tu paquete no pudo ser entregado",
        "cuerpo": ("Hola {usuario}:\n\nEl {fecha} intentamos entregar un paquete a tu nombre sin éxito. "
                   "Reprograma la entrega aquí:\n{enlace}\n\nServicio de mensajería"),
        "adjunto": "comprobante_envio",
    },
    "comunicado_interno": {
        "nombre": "Comunicado interno",
        "de": "comunicaciones@cybershield.invalid",
        "prioridad": "baja",
        "texto_enlace": "https://intranet.cybershield.invalid/politicas",
        "indicadores": [],
        "asunto": "Nueva política de escritorio limpio",
        "cuerpo": ("Hola {usuario}:\n\nDesde el {fecha} entra en vigor la política de escritorio limpio. "
                   "Encontrarás el documento adjunto y el acuse de lectura aquí:\n{enlace}\n\n"
                   "Área de Comunicación Interna"),
        "adjunto": "politica_escritorio_limpio",
    },
}


def catalogo():
    """Vista para el equipo Rojo: id y nombre de cada plantilla (sin cuerpos)."""
    return [{"id": k, "nombre": p["nombre"]} for k, p in PLANTILLAS.items()]


def _esqueleto(dominio):
    """Forma «visual» de un dominio: los caracteres que se confunden a simple vista se igualan (I mayúscula y 1 -> l,
    0 -> o, rn -> m), así un homoglifo como «cybershieId» queda igual que «cybershield»."""
    d = dominio.replace("I", "l").lower().replace("1", "l").replace("0", "o").replace("rn", "m")
    return d


def verificar_remitente(de):
    """Verificación sintética del remitente. Oficial = el dominio oficial (los dominios no distinguen mayúsculas).
    Si no lo es, se mira si lo IMITA: el esqueleto visual convierte la «I» mayúscula ANTES de pasar a minúsculas, así
    «cybershieId» (con «I») se detecta como imitación. -> {dominio, oficial, parecido, detalle}"""
    dominio = de.rsplit("@", 1)[-1] if isinstance(de, str) and "@" in de else ""
    oficial = dominio.lower() == DOMINIO_OFICIAL
    nombre_oficial = DOMINIO_OFICIAL.split(".")[0]
    parecido = not oficial and (_esqueleto(dominio) == DOMINIO_OFICIAL or nombre_oficial in _esqueleto(dominio))
    if oficial:
        detalle = f"El dominio coincide exactamente con el oficial ({DOMINIO_OFICIAL})."
    elif parecido:
        detalle = (f"Dominio que IMITA al oficial: «{dominio}» se parece a «{DOMINIO_OFICIAL}» pero no es el mismo "
                   "(caracteres cambiados o palabras añadidas).")
    else:
        detalle = f"Remitente externo: «{dominio}» no pertenece a la organización."
    return {"dominio": dominio, "oficial": oficial, "parecido": parecido, "detalle": detalle}


def adjunto(plantilla_id):
    """Id del PDF adjunto FIJO de la plantilla, o None. KeyError si la plantilla no existe."""
    return PLANTILLAS[plantilla_id].get("adjunto")


def componer(plantilla_id, usuario, enlace, fecha):
    """-> (de, asunto, cuerpo). KeyError si la plantilla no existe. Las plantillas son constantes del código."""
    p = PLANTILLAS[plantilla_id]
    variables = {"usuario": usuario, "enlace": enlace, "fecha": fecha}
    return p["de"], p["asunto"].format(**variables), p["cuerpo"].format(**variables)
