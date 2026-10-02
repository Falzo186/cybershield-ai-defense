"""Política de acceso determinista (sin IA). Datos 100% ficticios de CyberShield Industries.

La identidad (usuario, rol) la fija el SISTEMA al abrir la sesión; jamás se lee de un prompt.
"""
from dataclasses import dataclass

ROLES = {"invitado": 0, "empleado": 1, "analista": 2, "admin": 3}
SENSIBILIDAD = {"PUBLICA": 0, "INTERNA": 1, "CONFIDENCIAL": 2, "CRITICA": 3}

# Sensibilidad de cada tabla (única fuente de verdad).
TABLAS = {
    "productos": "PUBLICA",
    "clientes": "INTERNA",
    "incidentes": "CONFIDENCIAL",
    "configuracion_admin": "CRITICA",
}


@dataclass(frozen=True)
class Identidad:
    usuario: str
    rol: str


@dataclass(frozen=True)
class Acceso:
    permitido: bool
    requiere_autorizacion: bool
    motivo: str


def evaluar_acceso(identidad, sensibilidad, autorizacion_vigente=False):
    """Deny-by-default.

    - Rol >= nivel mínimo de la sensibilidad  -> permitido.
    - Un 'empleado' puede leer CONFIDENCIAL solo con una autorización vigente (concedida por un humano).
    - CRITICA es exclusiva de 'admin' y nunca se delega.
    """
    nivel_rol = ROLES.get(identidad.rol)
    nivel_req = SENSIBILIDAD.get(sensibilidad)
    if nivel_rol is None or nivel_req is None:
        return Acceso(False, False, "rol o sensibilidad desconocidos")
    if nivel_rol >= nivel_req:
        return Acceso(True, False, "rol suficiente")
    if sensibilidad == "CONFIDENCIAL" and identidad.rol == "empleado":
        if autorizacion_vigente:
            return Acceso(True, False, "autorización vigente")
        return Acceso(False, True, "requiere autorización explícita de un responsable")
    return Acceso(False, False, f"el rol '{identidad.rol}' no tiene acceso a datos {sensibilidad}")
