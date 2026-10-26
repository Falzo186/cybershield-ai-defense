"""Sesiones de participantes y ciclo de vida de la partida (Fase C). Lógica pura: sin HTTP ni base de datos.

- Sala: las sesiones del servidor. Cada participante tiene su propio token, un nombre visible único (sin distinguir
  mayúsculas) y un equipo; el árbitro («general») además necesita el código que el servidor imprime al arrancar.
  Las sesiones sobreviven entre partidas: los mismos participantes pueden jugar la siguiente.
- Partida: preparación -> en_curso -> finalizada, con una duración de 5, 10 o 15 minutos. El tiempo lo cuenta el
  SERVIDOR con un reloj monótono: recargar la página, perder la conexión o cambiar la hora del equipo del jugador no
  alteran el tiempo restante ni el resultado.
"""
import hmac
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime

EQUIPOS = ("rojo", "azul", "general", "espectador")
ROL_POR_EQUIPO = {"rojo": "jugador", "azul": "jugador", "general": "arbitro", "espectador": "espectador"}
FASES = ("preparacion", "en_curso", "finalizada")
DURACIONES_MIN = (5, 10, 15)
NOMBRE = re.compile(r"^[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ][0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ ._-]{1,23}$")
INTENTOS_ARBITRO = 5           # códigos de árbitro erróneos por cliente antes de bloquearlo...
BLOQUEO_ARBITRO_S = 300        # ...durante 5 minutos


class ErrorSesion(Exception):
    """Error comprensible para el cliente: status HTTP + mensaje."""

    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def ahora_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class Participante:
    id: str
    nombre: str
    equipo: str
    token: str = field(repr=False)
    unido: str = field(default_factory=ahora_iso)

    @property
    def rol(self):
        return ROL_POR_EQUIPO[self.equipo]

    def publico(self):
        """Lo que pueden ver los demás (nunca el token)."""
        return {"id": self.id, "nombre": self.nombre, "equipo": self.equipo, "rol": self.rol, "unido": self.unido}


class Sala:
    def __init__(self, codigo_arbitro, reloj=time.monotonic):
        self.codigo_arbitro = codigo_arbitro
        self._reloj = reloj
        self._participantes = {}  # id -> Participante
        self._fallos = {}         # cliente -> [fallos, bloqueado_hasta]

    def unirse(self, nombre, equipo, codigo=None, cliente="?"):
        nombre = " ".join(str(nombre or "").split())
        if equipo not in EQUIPOS:
            raise ErrorSesion(400, f"Equipo desconocido: {equipo}")
        if not NOMBRE.match(nombre):
            raise ErrorSesion(400, "El nombre debe tener de 2 a 24 caracteres (letras, números, espacio, . _ -).")
        if equipo == "general":
            self._comprobar_codigo(codigo, cliente)
        if any(p.nombre.casefold() == nombre.casefold() for p in self._participantes.values()):
            raise ErrorSesion(409, f"El nombre «{nombre}» ya está en uso en esta sala. Elige otro.")
        p = Participante(id=secrets.token_hex(4), nombre=nombre, equipo=equipo, token=secrets.token_urlsafe(24))
        self._participantes[p.id] = p
        return p

    def _comprobar_codigo(self, codigo, cliente):
        fallos, hasta = self._fallos.get(cliente, [0, 0.0])
        if hasta > self._reloj():
            raise ErrorSesion(429, "Demasiados códigos de árbitro erróneos. Espera unos minutos.")
        if not codigo or not hmac.compare_digest(str(codigo).strip().encode(), self.codigo_arbitro.encode()):
            fallos += 1
            self._fallos[cliente] = [0, self._reloj() + BLOQUEO_ARBITRO_S] if fallos >= INTENTOS_ARBITRO else [fallos, 0.0]
            raise ErrorSesion(403, "Código de árbitro incorrecto (se muestra en la consola del servidor al arrancar).")
        self._fallos.pop(cliente, None)

    def por_token(self, token):
        """-> Participante dueño del token o None. Comparación en tiempo constante."""
        if not token:
            return None
        encontrado = None
        for p in self._participantes.values():
            if hmac.compare_digest(str(token).encode(), p.token.encode()):
                encontrado = p
        return encontrado

    def participantes(self, equipo=None):
        return [p for p in self._participantes.values() if equipo is None or p.equipo == equipo]


class Partida:
    def __init__(self, reloj=time.monotonic):
        self.id = datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
        self.fase = "preparacion"
        self.duracion_s = None
        self.inicio = None      # ISO, para mostrar
        self.fin = None
        self.motivo_fin = None  # "tiempo" | "arbitro"
        self._reloj = reloj
        self._fin_mono = None

    def iniciar(self, duracion_min):
        if self.fase != "preparacion":
            raise ErrorSesion(409, "La partida ya empezó." if self.fase == "en_curso" else "La partida ya finalizó.")
        if duracion_min not in DURACIONES_MIN:
            raise ErrorSesion(400, f"Duración no permitida: {duracion_min} min (5, 10 o 15).")
        self.fase = "en_curso"
        self.duracion_s = duracion_min * 60
        self.inicio = ahora_iso()
        self._fin_mono = self._reloj() + self.duracion_s

    def restante_s(self):
        if self.fase == "preparacion":
            return self.duracion_s
        if self.fase == "finalizada":
            return 0
        return max(0, int(round(self._fin_mono - self._reloj())))

    def vencida(self):
        return self.fase == "en_curso" and self._reloj() >= self._fin_mono

    def finalizar(self, motivo):
        if self.fase != "en_curso":
            raise ErrorSesion(409, "La partida no ha empezado." if self.fase == "preparacion" else "La partida ya finalizó.")
        self.fase = "finalizada"
        self.motivo_fin = motivo
        self.fin = ahora_iso()

    def publico(self):
        return {"id": self.id, "fase": self.fase, "duracion_s": self.duracion_s, "restante_s": self.restante_s(),
                "inicio": self.inicio, "fin": self.fin, "motivo_fin": self.motivo_fin}
