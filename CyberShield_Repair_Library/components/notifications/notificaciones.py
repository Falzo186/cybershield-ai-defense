"""Notificaciones del buzón (CyberShield Repair §7.D). Dos cosas, ambas DERIVADAS de lo persistido (nunca un contador en memoria que se
desincronice):
  * contador de no leídos = correos de la entrada que NADIE ha leído todavía;
  * eventos SSE `correo_nuevo` / `buzon_estado` con el mínimo de información (sin asunto ni cuerpo: el SSE es público).
"""


def _lectores(c):
    return [x.strip() for x in str(c.get("leido_por") or "").split(",") if x.strip()]


def no_leidos(correos, quien=None):
    """Correos sin leer de la entrada. `correos` = filas de repositorio.buzon(). Con `quien` (nombre del participante), los que ESE
    participante no ha leído; sin él, los que nadie ha leído todavía."""
    return sum(1 for c in correos if not c.get("archivado") and ((quien not in _lectores(c)) if quien else not _lectores(c)))


def evento_correo_nuevo(usuario, correo_id, total_no_leidos):
    return {"usuario": usuario, "correo_id": correo_id, "no_leidos": total_no_leidos}


def evento_buzon(usuario, total_no_leidos):
    return {"usuario": usuario, "no_leidos": total_no_leidos}
