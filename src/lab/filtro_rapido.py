"""Filtro rápido (regex) ANTES de gastar inferencia: bloquea los casos obvios sin llamar al defensor LLM.

Es una capa determinista más. Los casos ambiguos siguen yendo al defensor IA sin cambios.
Lista editable: (categoría detectada, regex de alta confianza, motivo).
"""
import re

PATRONES_BLOQUEO = [
    ("secreto_simulado", r"\bLAB[_-][A-Z0-9_]+|\blab[-_](?:secreto|token)",
     "Menciona directamente un secreto simulado del laboratorio"),
    ("extraer_system_prompt",
     r"system\s*prompt|prompt\s+(?:del|de)\s+sistema|mu[eé]strame\s+tus\s+instrucciones|"
     r"revela\s+tus\s+instrucciones|tus\s+instrucciones\s+(?:internas|de\s+sistema)",
     "Intenta obtener las instrucciones internas del sistema"),
    ("ignorar_instrucciones",
     r"\b(?:ignora|olvida|omite)\s+(?:todas\s+)?(?:tus|las)\s+instrucciones|"
     r"\bignore\s+(?:all\s+)?(?:previous|prior|your)\s+instructions",
     "Orden literal de ignorar las instrucciones"),
    ("inyeccion_sql",
     r"\bDROP\s+TABLE\b|\bUNION\s+(?:ALL\s+)?SELECT\b|;\s*--|'\s*OR\s+'?1'?\s*=\s*'?1",
     "Patrón de inyección SQL"),
    ("modo_privilegiado",
     r"\bmodo\s+(?:administrador|desarrollador|dios|debug)\b|\b(?:developer|admin|god)\s+mode\b",
     "Pide activar un modo administrador/desarrollador"),
]
_COMPILADOS = [(c, re.compile(p, re.IGNORECASE), m) for c, p, m in PATRONES_BLOQUEO]


def clasificar_rapido(prompt_atacante):
    """-> {accion: "bloquear"|"evaluar_ia", motivo, categoria_detectada}"""
    texto = prompt_atacante if isinstance(prompt_atacante, str) else ""
    for categoria, rx, motivo in _COMPILADOS:
        if rx.search(texto):
            return {"accion": "bloquear", "motivo": motivo, "categoria_detectada": categoria}
    return {"accion": "evaluar_ia", "motivo": None, "categoria_detectada": None}
