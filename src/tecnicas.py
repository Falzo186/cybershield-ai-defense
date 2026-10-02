import re

# Orden = prioridad. Editable.
PATRONES_TECNICA = [
    ("ignorar_instrucciones", r"ignora|ignore|olvida|forget|anula|deja de lado|disregard"),
    ("codificacion", r"base\s*64|hex|binario|rot13|cifr|codific|encod|al rev[eé]s|letra por letra|c[oó]digo morse"),
    ("traduccion", r"traduc|translat|en ingl[eé]s|en franc[eé]s|en alem[aá]n|in english|en otro idioma"),
    ("completar_texto", r"completa|complete|continu[aá]|\.\.\.|_{2,}|empieza con|comienza con|FLAG\{\s*$"),
    ("urgencia_emocional", r"urgente|emergencia|por favor|te lo suplico|vidas?|desesperad|ayuda|urgent|please|help me"),
    ("autoridad", r"administrador|admin|director|jefe|autoriz|auditor|soy (el|la) |ceo|supervisor|polic[ií]a|oficial|authorized"),
    ("rol_falso", r"act[uú]a como|finge|imagina|eres ahora|ahora eres|rol de|juego de rol|pretend|roleplay|you are now|modo"),
]
_REGEX = [(n, re.compile(p, re.IGNORECASE)) for n, p in PATRONES_TECNICA]


def clasificar_tecnica(ataque):
    for nombre, rx in _REGEX:
        if rx.search(ataque):
            return nombre
    return "otra"
