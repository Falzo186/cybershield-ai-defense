"""Correos del ESCENARIO (CyberShield Repair §7.A): comunicaciones internas legítimas y ficticias, independientes del equipo Rojo.

Se programan por TIEMPO DE PARTIDA (segundos desde el inicio, congelados durante una pausa) y se entregan una sola vez cada una:
la entrega es idempotente por (partida, clave), así que reiniciar o reanudar no duplica nada. Todo es ficticio y local; no hay enlaces.
"""
CORREOS_ESCENARIO = (
    {"clave": "rrhh_bienvenida", "en_s": 5, "de": "rrhh@cybershield.example", "asunto": "Recordatorio: actualización de datos de contacto",
     "cuerpo": "Hola:\n\nEste mes recursos humanos pide revisar los datos de contacto en el portal interno de personal (no hace falta responder a este correo).\n\nGracias,\nRecursos Humanos"},
    {"clave": "finanzas_cierre", "en_s": 45, "de": "finanzas@cybershield.example", "asunto": "Cierre de mes: fecha límite de gastos",
     "cuerpo": "Hola:\n\nLa fecha límite para registrar gastos del mes es el viernes. Las dudas se resuelven con el equipo de finanzas en persona.\n\nSaludos,\nFinanzas"},
    {"clave": "direccion_aviso", "en_s": 90, "de": "direccion@cybershield.example", "asunto": "Reunión general del lunes",
     "cuerpo": "Equipo:\n\nLa reunión general del lunes será a las 10:00 en la sala principal. Se enviará el orden del día antes de la reunión.\n\nDirección"},
    {"clave": "soporte_mantenimiento", "en_s": 150, "de": "soporte@cybershield.example", "asunto": "Mantenimiento programado del sistema de correo",
     "cuerpo": "Hola:\n\nEl sábado de 02:00 a 04:00 habrá mantenimiento del sistema de correo. No se solicitará ninguna contraseña por este motivo.\n\nSoporte técnico"},
    {"clave": "interno_solicitud", "en_s": 210, "de": "operaciones@cybershield.example", "asunto": "Solicitud interna: inventario de equipos",
     "cuerpo": "Hola:\n\nOperaciones está actualizando el inventario de equipos. Cada área debe confirmar a su responsable cuántos equipos tiene asignados.\n\nOperaciones"},
    {"clave": "admin_politica", "en_s": 270, "de": "administracion@cybershield.example", "asunto": "Aviso administrativo: política de contraseñas",
     "cuerpo": "Hola:\n\nRecuerda que la política vigente exige contraseñas de al menos 12 caracteres. La administración nunca pide tu contraseña por correo.\n\nAdministración"},
)


def pendientes(transcurrido_s, entregados):
    """Correos cuyo momento ya llegó y que no se han entregado. `entregados` = conjunto de claves. Orden de programación."""
    if transcurrido_s is None:
        return []
    return [c for c in CORREOS_ESCENARIO if c["en_s"] <= transcurrido_s and c["clave"] not in entregados]


def calendario(entregados):
    return [{"clave": c["clave"], "en_s": c["en_s"], "asunto": c["asunto"], "de": c["de"], "entregado": c["clave"] in entregados}
            for c in CORREOS_ESCENARIO]
