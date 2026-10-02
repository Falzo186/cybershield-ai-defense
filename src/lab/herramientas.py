"""Catálogo de herramientas controladas y ejecución en capas deterministas.

Capas (en orden): catalogo -> validacion -> permisos/autorizacion -> repositorio.
La IA solo PROPONE una herramienta y parámetros; esta función decide si se ejecuta.
Los errores internos NO se disfrazan de bloqueo: devuelven error y capa_bloqueo=None.
"""
import re
from dataclasses import dataclass

from . import permisos, repositorio
from .repositorio import PermisoDenegado

# Valores permitidos por parámetro (whitelist estricta; rechaza comillas, espacios raros, etc.).
PATRONES = {
    "sku": r"[A-Za-z0-9-]{1,20}",
    "industria": r"[A-Za-zÁÉÍÓÚáéíóúñÑ ]{1,40}",
    "severidad": r"BAJA|MEDIA|ALTA|CRITICA",
    "clave": r"[A-Z0-9_]{1,40}",
}


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    descripcion: str
    tabla: str
    parametros: tuple  # nombres de parámetros opcionales aceptados

    @property
    def sensibilidad(self):
        return permisos.TABLAS[self.tabla]


CATALOGO = {h.nombre: h for h in (
    Herramienta("consultar_inventario", "Stock y precio de productos de CyberShield.", "productos", ("sku",)),
    Herramienta("consultar_clientes", "Listado de clientes de CyberShield.", "clientes", ("industria",)),
    Herramienta("consultar_incidentes", "Incidentes de seguridad internos.", "incidentes", ("severidad",)),
    Herramienta("consultar_configuracion_admin", "Configuración y secretos de administración.",
                "configuracion_admin", ("clave",)),
)}


def catalogo():
    """Vista para el defensor IA: nombre, descripción, sensibilidad y parámetros."""
    return [{"nombre": h.nombre, "descripcion": h.descripcion, "sensibilidad": h.sensibilidad,
             "parametros": list(h.parametros)} for h in CATALOGO.values()]


def _validar(h, parametros):
    if not isinstance(parametros, dict):
        raise ValueError("parametros debe ser un objeto")
    extra = set(parametros) - set(h.parametros)
    if extra:
        raise ValueError(f"parámetros no permitidos: {sorted(extra)}")
    for k, v in parametros.items():
        if not isinstance(v, str) or not re.fullmatch(PATRONES[k], v):
            raise ValueError(f"valor inválido para '{k}'")


def ejecutar_herramienta(nombre, parametros, identidad, repo=None):
    """Nunca lanza. Devuelve {ok, datos, capa_bloqueo, sensibilidad, motivo, requiere_autorizacion, error}."""
    r = {"ok": False, "datos": None, "capa_bloqueo": None, "sensibilidad": None,
         "motivo": None, "requiere_autorizacion": False, "error": None}
    try:
        h = CATALOGO.get(nombre) if isinstance(nombre, str) else None
        if h is None:
            r.update(capa_bloqueo="catalogo", motivo="herramienta no incluida en el catálogo")
            return r
        r["sensibilidad"] = h.sensibilidad
        parametros = parametros or {}
        try:
            _validar(h, parametros)
        except ValueError as exc:
            r.update(capa_bloqueo="validacion", motivo=str(exc))
            return r

        repo = repo or repositorio.por_defecto()
        acceso = permisos.evaluar_acceso(identidad, h.sensibilidad, repo.autorizador.vigente(identidad, h.tabla))
        if not acceso.permitido:
            repo.registrar(identidad, "HERRAMIENTA:" + h.nombre, h.tabla, "DENEGADO",
                           repositorio.NIVEL_RIESGO[h.sensibilidad])
            r.update(capa_bloqueo="autorizacion" if acceso.requiere_autorizacion else "permisos",
                     motivo=acceso.motivo, requiere_autorizacion=acceso.requiere_autorizacion)
            return r

        try:
            r["datos"] = repo.consultar(identidad, h.tabla, parametros)
        except PermisoDenegado as exc:
            r.update(capa_bloqueo=exc.capa, motivo=exc.motivo, requiere_autorizacion=exc.requiere_autorizacion)
            return r
        r["ok"] = True
        return r
    except Exception as exc:  # noqa: BLE001 - fallo interno, no es un bloqueo
        r.update(ok=False, datos=None, capa_bloqueo=None, error=f"{type(exc).__name__}: {exc}")
        return r
