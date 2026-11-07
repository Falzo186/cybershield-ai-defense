"""Sesiones de participantes y ciclo de vida de la partida (Fase C). Lógica pura: sin HTTP ni base de datos.

- Sala: las sesiones del servidor. Cada participante tiene su propio token, un nombre visible único (sin distinguir
  mayúsculas) y un equipo; el árbitro («general») además necesita el código que el servidor imprime al arrancar.
  Las sesiones sobreviven entre partidas: los mismos participantes pueden jugar la siguiente.
- Partida: preparación -> en_curso -> finalizada, con una duración de 5, 10 o 15 minutos. El tiempo lo cuenta el
  SERVIDOR con un reloj monótono: recargar la página, perder la conexión o cambiar la hora del equipo del jugador no
  alteran el tiempo restante ni el resultado.
"""
import hashlib
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
# Fase H · autenticación por persona
CLAVE_MINIMA = 8               # longitud mínima de la clave personal, si se usa
CLAVE_MAXIMA = 128
INTENTOS_CLAVE = 5             # claves personales erróneas por cliente antes de bloquearlo...
BLOQUEO_CLAVE_S = 300          # ...durante 5 minutos
INACTIVIDAD_S = 4 * 3600       # una sesión sin actividad caduca a las 4 horas
PBKDF2_VUELTAS = 200_000       # coste del derivado; suficiente para un laboratorio local


class ErrorSesion(Exception):
    """Error comprensible para el cliente: status HTTP + mensaje."""

    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def ahora_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def derivar(clave, sal):
    """PBKDF2-HMAC-SHA256. La clave personal NUNCA se guarda en claro ni se puede recuperar desde aquí."""
    return hashlib.pbkdf2_hmac("sha256", str(clave).encode("utf-8"), sal, PBKDF2_VUELTAS)


@dataclass
class Participante:
    id: str
    nombre: str
    equipo: str
    token: str = field(repr=False)
    unido: str = field(default_factory=ahora_iso)
    # Autenticación por persona (Fase H). Opcional: sin clave, el participante vale solo para esta sesión y
    # no puede recuperarla desde otro navegador. Con clave, puede volver a entrar con su mismo nombre.
    sal: bytes | None = field(default=None, repr=False)
    derivado: bytes | None = field(default=None, repr=False)
    ultima_actividad: float = field(default=0.0, repr=False)
    sesiones: int = 1

    @property
    def rol(self):
        return ROL_POR_EQUIPO[self.equipo]

    @property
    def autenticado(self):
        """¿Tiene clave propia? Si no, su identidad solo vale mientras conserve el token."""
        return self.derivado is not None

    def comprueba(self, clave):
        """Comparación en tiempo constante del derivado. Sin clave configurada, siempre False."""
        if self.derivado is None or self.sal is None or not clave:
            return False
        return hmac.compare_digest(derivar(clave, self.sal), self.derivado)

    def publico(self):
        """Lo que pueden ver los demás. Nunca el token, nunca la sal, nunca el derivado."""
        return {"id": self.id, "nombre": self.nombre, "equipo": self.equipo, "rol": self.rol,
                "unido": self.unido, "autenticado": self.autenticado}


class Sala:
    def __init__(self, codigo_arbitro, reloj=time.monotonic):
        self.codigo_arbitro = codigo_arbitro
        self._reloj = reloj
        self._participantes = {}  # id -> Participante
        self._fallos = {}         # cliente -> [fallos, bloqueado_hasta]

    def unirse(self, nombre, equipo, codigo=None, cliente="?", clave=None):
        """Entra en la sala. Con `clave`, el nombre queda reservado para esa persona y puede volver a entrar
        desde otro navegador demostrando que la sabe; sin ella, el nombre vale solo mientras dure la sesión.

        Si el nombre ya está en uso **y tiene clave**, esto es una reautenticación: se comprueba la clave y
        se emite un token nuevo (el anterior deja de valer). Si está en uso y NO tiene clave, se rechaza:
        sin secreto no hay forma de saber si quien pide el nombre es la misma persona."""
        nombre = " ".join(str(nombre or "").split())
        if equipo not in EQUIPOS:
            raise ErrorSesion(400, f"Equipo desconocido: {equipo}")
        if not NOMBRE.match(nombre):
            raise ErrorSesion(400, "El nombre debe tener de 2 a 24 caracteres (letras, números, espacio, . _ -).")
        if clave is not None:
            clave = str(clave)
            if not (CLAVE_MINIMA <= len(clave) <= CLAVE_MAXIMA):
                raise ErrorSesion(400, f"La clave personal debe tener entre {CLAVE_MINIMA} y {CLAVE_MAXIMA} "
                                       "caracteres.")
        if equipo == "general":
            self._comprobar_codigo(codigo, cliente)
        existente = next((p for p in self._participantes.values()
                          if p.nombre.casefold() == nombre.casefold()), None)
        if existente is not None:
            return self._reautenticar(existente, equipo, clave, cliente)
        p = Participante(id=secrets.token_hex(4), nombre=nombre, equipo=equipo,
                         token=secrets.token_urlsafe(24), ultima_actividad=self._reloj())
        if clave:
            p.sal = secrets.token_bytes(16)
            p.derivado = derivar(clave, p.sal)
        self._participantes[p.id] = p
        return p

    def _reautenticar(self, p, equipo, clave, cliente):
        """Vuelve a entrar con un nombre ya usado. Solo con clave correcta, y rota el token."""
        if not p.autenticado:
            raise ErrorSesion(409, f"El nombre «{p.nombre}» ya está en uso en esta sala. Elige otro.")
        self._comprobar_intentos(cliente)
        if not p.comprueba(clave):
            self._fallo(cliente)
            raise ErrorSesion(403, "Clave personal incorrecta.")
        if p.equipo != equipo:
            raise ErrorSesion(409, f"«{p.nombre}» ya está en el equipo {p.equipo} en esta sala.")
        self._fallos.pop(cliente, None)
        # Rotación: el token anterior deja de valer en cuanto esta persona vuelve a entrar. Así una sesión
        # abandonada en otro equipo no sigue siendo válida indefinidamente.
        p.token = secrets.token_urlsafe(24)
        p.ultima_actividad = self._reloj()
        p.sesiones += 1
        return p

    def _comprobar_intentos(self, cliente):
        fallos, hasta = self._fallos.get(cliente, [0, 0.0])
        if hasta > self._reloj():
            raise ErrorSesion(429, "Demasiados intentos fallidos. Espera unos minutos.")

    def _fallo(self, cliente):
        fallos, _ = self._fallos.get(cliente, [0, 0.0])
        fallos += 1
        self._fallos[cliente] = ([0, self._reloj() + BLOQUEO_CLAVE_S] if fallos >= INTENTOS_CLAVE
                                 else [fallos, 0.0])

    def caducar(self, inactividad_s=INACTIVIDAD_S):
        """Elimina las sesiones sin actividad desde hace más de `inactividad_s`. -> nombres caducados.

        Una sesión que nadie usa es una credencial viva sin dueño. Las de participantes CON clave también
        caducan: pueden volver a entrar demostrando que la saben."""
        limite = self._reloj() - inactividad_s
        viejos = [p for p in self._participantes.values() if p.ultima_actividad and p.ultima_actividad < limite]
        for p in viejos:
            self._participantes.pop(p.id, None)
        return [p.nombre for p in viejos]

    def _comprobar_codigo(self, codigo, cliente):
        fallos, hasta = self._fallos.get(cliente, [0, 0.0])
        if hasta > self._reloj():
            raise ErrorSesion(429, "Demasiados códigos de árbitro erróneos. Espera unos minutos.")
        if not codigo or not hmac.compare_digest(str(codigo).strip().encode(), self.codigo_arbitro.encode()):
            fallos += 1
            self._fallos[cliente] = [0, self._reloj() + BLOQUEO_ARBITRO_S] if fallos >= INTENTOS_ARBITRO else [fallos, 0.0]
            raise ErrorSesion(403, "Código de árbitro incorrecto (se muestra en la consola del servidor al arrancar).")
        self._fallos.pop(cliente, None)

    def por_token(self, token, tocar=True):
        """-> Participante dueño del token o None. Comparación en tiempo constante (se recorren todos).

        `tocar` actualiza la marca de actividad: es lo que hace que una sesión en uso no caduque y una
        abandonada sí. Las comprobaciones de solo lectura pueden pasar `tocar=False`."""
        if not token:
            return None
        encontrado = None
        for p in self._participantes.values():
            if hmac.compare_digest(str(token).encode(), p.token.encode()):
                encontrado = p
        if encontrado is not None and tocar:
            encontrado.ultima_actividad = self._reloj()
        return encontrado

    def cerrar_sesion(self, token):
        """Invalida el token de quien lo presenta. -> nombre, o None si el token no valía.

        El participante desaparece de la sala; si tenía clave, puede volver a entrar con ella."""
        p = self.por_token(token, tocar=False)
        if p is None:
            return None
        self._participantes.pop(p.id, None)
        return p.nombre

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

    def transcurrido_s(self):
        """Segundos desde el inicio (None en preparación): base de los plazos de las misiones."""
        if self.fase == "preparacion":
            return None
        return self.duracion_s - self.restante_s()

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
