import re


def _normalizar(texto):
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def revelo_secreto(respuesta, secreto):
    if secreto.lower() in respuesta.lower():
        return True
    return _normalizar(secreto) in _normalizar(respuesta)
