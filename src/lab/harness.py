"""Harness: capa de control sobre la interacción del modelo con las herramientas del laboratorio.

No es un agente con permisos ilimitados. Es lo contrario: un envoltorio que acota, observa y registra lo que
el defensor IA puede hacer, y que corta en cuanto se agota cualquier presupuesto.

Garantías que da este módulo:
  - El modelo solo ejecuta herramientas del catálogo cerrado de `herramientas.py`. Aquí no se añade ninguna.
  - El modelo NUNCA toca el sistema operativo, archivos arbitrarios ni la red. Las herramientas son funciones
    de Python registradas de antemano.
  - Hay techo de iteraciones, de llamadas al modelo, de tokens, de tiempo por herramienta y de tiempo global.
  - Se detectan bucles: la misma herramienta con los mismos parámetros, o la misma solicitud, repetidas.
  - Un reintento NUNCA sirve para eludir un permiso (ver REINTENTABLES y `_puede_reintentar`).
  - El estado es serializable: una ejecución interrumpida se puede inspeccionar y reanudar desde su registro.
  - Nunca lanza.

Lo que el harness NO hace: cambiar el veredicto, otorgar permisos ni sustituir a las capas deterministas.
"""
import hashlib
import threading
import time
from dataclasses import asdict, dataclass, field

from . import diagnostico, herramientas, motor, permisos

# Estados finales de una ejecución.
ESTADOS = ("en_curso", "terminado", "agotado", "cancelado", "bucle", "error")

# Clases de diagnóstico que justifican pedir al modelo que corrija. Son errores TÉCNICOS del modelo
# (formato ilegible, herramienta inexistente, parámetro mal formado), nunca denegaciones de política:
# reintentar un ERROR_PERMISO o un ERROR_AUTORIZACION convertiría el harness en un amplificador de ataque.
REINTENTABLES = ("ERROR_FORMATO", "ERROR_CATALOGO", "ERROR_PARAMETRO")


@dataclass(frozen=True)
class Presupuesto:
    """Techos de una ejecución. Todos son opcionales salvo los que tienen valor por defecto.

    Los tiempos son en segundos. `max_tokens_salida`/`max_tokens_entrada` a None = sin techo de tokens
    (Ollama puede no informarlos; en ese caso el contador se queda en lo conocido y no se estima)."""
    max_iteraciones: int = 3
    max_llamadas_modelo: int = 6
    max_tokens_salida: int | None = 4000
    max_tokens_entrada: int | None = None
    timeout_herramienta_s: float = 30.0
    timeout_global_s: float = 300.0
    max_repeticiones_identicas: int = 2


@dataclass
class Paso:
    """Una acción registrada del harness. `tipo`: modelo | herramienta | decision | corte."""
    n: int
    tipo: str
    nombre: str
    ok: bool
    ms: int
    detalle: dict = field(default_factory=dict)
    error: str | None = None


def huella(*partes):
    """Huella estable de una acción, para detectar repeticiones. Determinista y corta."""
    crudo = "\u0000".join(repr(p) for p in partes)
    return hashlib.sha256(crudo.encode("utf-8", "replace")).hexdigest()[:16]


class Ejecucion:
    """Estado observable y acotado de UNA ejecución controlada. Serializable con `a_json()`."""

    def __init__(self, presupuesto=None, reloj=time.monotonic):
        self.presupuesto = presupuesto or Presupuesto()
        self._reloj = reloj
        self.inicio = reloj()
        self.estado = "en_curso"
        self.motivo_corte = None
        self.iteraciones = 0
        self.llamadas_modelo = 0
        self.tokens_entrada = 0
        self.tokens_salida = 0
        self.pasos = []
        self.huellas = {}
        self._cancelar = threading.Event()

    # ── Control ────────────────────────────────────────────────────────────────────────────────────────────
    @property
    def transcurrido_s(self):
        return self._reloj() - self.inicio

    @property
    def restante_s(self):
        return max(0.0, self.presupuesto.timeout_global_s - self.transcurrido_s)

    def cancelar(self, motivo="cancelado por el usuario"):
        """Pide la cancelación. El harness la atiende entre pasos; nunca mata un hilo a medias."""
        self._cancelar.set()
        self.motivo_corte = motivo

    @property
    def cancelada(self):
        return self._cancelar.is_set()

    def puede_continuar(self):
        """-> (bool, motivo). Comprueba TODOS los presupuestos antes de cada paso."""
        p = self.presupuesto
        if self.cancelada:
            return False, self.motivo_corte or "cancelado"
        if self.transcurrido_s >= p.timeout_global_s:
            return False, f"timeout global de {p.timeout_global_s:g} s"
        if self.iteraciones >= p.max_iteraciones:
            return False, f"límite de {p.max_iteraciones} iteraciones"
        if self.llamadas_modelo >= p.max_llamadas_modelo:
            return False, f"límite de {p.max_llamadas_modelo} llamadas al modelo"
        if p.max_tokens_salida is not None and self.tokens_salida >= p.max_tokens_salida:
            return False, f"presupuesto de {p.max_tokens_salida} tokens de salida"
        if p.max_tokens_entrada is not None and self.tokens_entrada >= p.max_tokens_entrada:
            return False, f"presupuesto de {p.max_tokens_entrada} tokens de entrada"
        return True, None

    def _cortar(self, motivo, estado="agotado"):
        self.estado = estado
        self.motivo_corte = motivo
        self._anotar("corte", estado, False, 0, {"motivo": motivo})
        return False

    def _anotar(self, tipo, nombre, ok, ms, detalle=None, error=None):
        self.pasos.append(Paso(len(self.pasos) + 1, tipo, nombre, ok, int(ms), detalle or {}, error))
        return self.pasos[-1]

    def repetida(self, *partes):
        """Registra la huella de una acción y dice si ya se repitió más de lo permitido."""
        h = huella(*partes)
        self.huellas[h] = self.huellas.get(h, 0) + 1
        return self.huellas[h] > self.presupuesto.max_repeticiones_identicas

    # ── Contabilidad del modelo ────────────────────────────────────────────────────────────────────────────
    def registrar_modelo(self, nombre, resultado):
        """resultado = dict con ok/tiempo_ms/tokens/tokens_entrada/error (forma de cliente_ollama)."""
        self.llamadas_modelo += 1
        for campo, attr in (("tokens", "tokens_salida"), ("tokens_entrada", "tokens_entrada")):
            v = (resultado or {}).get(campo)
            if isinstance(v, int) and not isinstance(v, bool):
                setattr(self, attr, getattr(self, attr) + v)
        r = resultado or {}
        return self._anotar("modelo", nombre, bool(r.get("ok")), r.get("tiempo_ms") or 0,
                            {"tokens_salida": r.get("tokens"), "tokens_entrada": r.get("tokens_entrada")},
                            r.get("error"))

    # ── Herramientas ───────────────────────────────────────────────────────────────────────────────────────
    def usar_herramienta(self, nombre, parametros, identidad, repo=None, equipo=None):
        """Ejecuta UNA herramienta del catálogo cerrado, con timeout propio. Nunca lanza.

        -> el dict de `herramientas.ejecutar_herramienta`, más `timeout` (bool). Una herramienta que no esté
        en el catálogo se bloquea aquí igual que allí: el harness no amplía el catálogo."""
        if nombre not in herramientas.CATALOGO:
            r = {"ok": False, "datos": None, "capa_bloqueo": "catalogo", "sensibilidad": None,
                 "motivo": "herramienta no incluida en el catálogo", "requiere_autorizacion": False,
                 "error": None, "timeout": False}
            self._anotar("herramienta", str(nombre), False, 0, {"capa_bloqueo": "catalogo"})
            return r
        limite = min(self.presupuesto.timeout_herramienta_s, max(0.0, self.restante_s)) or 0.001
        caja = {}
        t0 = time.perf_counter()

        def trabajo():
            caja["r"] = herramientas.ejecutar_herramienta(nombre, parametros, identidad, repo, equipo)

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()
        hilo.join(limite)
        ms = (time.perf_counter() - t0) * 1000
        if hilo.is_alive():
            # El hilo es daemon y sigue vivo: Python no permite matarlo. Su resultado se descarta y la
            # ejecución continúa; queda registrado como timeout, no como bloqueo de una capa.
            r = {"ok": False, "datos": None, "capa_bloqueo": None, "sensibilidad": None,
                 "motivo": None, "requiere_autorizacion": False,
                 "error": f"TimeoutError: la herramienta superó {limite:.1f} s", "timeout": True}
            self._anotar("herramienta", nombre, False, ms, {"parametros": parametros}, r["error"])
            return r
        r = {**caja.get("r", {}), "timeout": False}
        self._anotar("herramienta", nombre, bool(r.get("ok")), ms,
                     {"parametros": parametros, "capa_bloqueo": r.get("capa_bloqueo"),
                      "sensibilidad": r.get("sensibilidad")}, r.get("error"))
        return r

    # ── Serialización ──────────────────────────────────────────────────────────────────────────────────────
    def a_json(self):
        """Estado completo, serializable. Es lo que permite inspeccionar o reanudar una ejecución cortada."""
        return {
            "estado": self.estado,
            "motivo_corte": self.motivo_corte,
            "presupuesto": asdict(self.presupuesto),
            "consumo": {"iteraciones": self.iteraciones, "llamadas_modelo": self.llamadas_modelo,
                        "tokens_entrada": self.tokens_entrada, "tokens_salida": self.tokens_salida,
                        "transcurrido_ms": int(self.transcurrido_s * 1000)},
            "pasos": [asdict(p) for p in self.pasos],
            "herramientas_usadas": [p.nombre for p in self.pasos if p.tipo == "herramienta"],
            "errores": [{"paso": p.n, "nombre": p.nombre, "error": p.error} for p in self.pasos if p.error],
        }


def _tiene_derecho(identidad, nombre, repo):
    """¿La identidad real podría usar esa herramienta? Se usa SOLO para decidir si un reintento es legítimo."""
    h = herramientas.CATALOGO.get(nombre)
    if h is None or repo is None:
        return False
    return permisos.evaluar_acceso(identidad, h.sensibilidad,
                                   repo.autorizador.vigente(identidad, h.tabla)).permitido


def _puede_reintentar(dg, defensa, identidad, repo):
    """Un reintento solo se concede ante un error TÉCNICO del modelo, y nunca para rodear un permiso.

    - ERROR_FORMATO: el modelo no produjo JSON utilizable. No hubo propuesta: reintentar es seguro.
    - ERROR_CATALOGO / ERROR_PARAMETRO: hubo propuesta, pero mal formada. Solo se reintenta si la identidad
      REAL tiene derecho a esa herramienta; si no lo tiene, el bloqueo es de política y se respeta."""
    tipo = (dg or {}).get("tipo")
    if tipo not in REINTENTABLES:
        return False
    if tipo == "ERROR_FORMATO":
        return True
    return _tiene_derecho(identidad, (defensa or {}).get("herramienta"), repo)


def ejecutar(host, modelo_def, solicitud, identidad, repo=None, presupuesto=None, equipo=None,
             riesgo_sesion=None, resumen_sesion=None, ejecucion=None, procesar=None):
    """Ciclo controlado para UNA solicitud: clasificar -> decidir -> validar -> ejecutar -> diagnosticar ->
    corregir (si procede) -> entregar, siempre dentro del presupuesto.

    Devuelve la MISMA forma que `motor.procesar_defensa` (veredicto, defensa, ejecucion, diagnostico…) más
    `harness` con el estado de la ejecución. Así los dos caminos son comparables sin tocar nada aguas abajo.

    `procesar` permite inyectar un sustituto de motor.procesar_defensa en las pruebas. Nunca lanza."""
    ej = ejecucion or Ejecucion(presupuesto)
    procesar = procesar or motor.procesar_defensa
    ultima = None
    try:
        while True:
            puede, motivo = ej.puede_continuar()
            if not puede:
                ej._cortar(motivo, "cancelado" if ej.cancelada else "agotado")
                break
            if ej.repetida("solicitud", solicitud):
                ej._cortar("la misma solicitud se repitió más de lo permitido", "bucle")
                break

            ej.iteraciones += 1
            t0 = time.perf_counter()
            r = procesar(host, modelo_def, solicitud, identidad, repo, riesgo_sesion, resumen_sesion, equipo)
            ms = (time.perf_counter() - t0) * 1000
            r = r if isinstance(r, dict) else {"veredicto": "ERROR", "error": "procesar devolvió algo no válido"}
            defensa = r.get("defensa") or {}
            # Una llamada al defensor por iteración (el reintento de JSON de cliente_ollama ya va contado en
            # `intentos`; se suma para no subestimar el consumo real).
            ej.llamadas_modelo += max(1, int(defensa.get("intentos") or 1)) - 1
            ej.registrar_modelo(f"defensor:{modelo_def}", {
                "ok": not r.get("error"), "tiempo_ms": defensa.get("tiempo_ms") or ms,
                "tokens": defensa.get("tokens"), "tokens_entrada": defensa.get("tokens_entrada"),
                "error": r.get("error")})
            dg = r.get("diagnostico") or diagnostico.diagnosticar(r)
            r["diagnostico"] = dg
            ej._anotar("decision", r.get("veredicto") or "?", not r.get("error"), ms,
                       {"decision_ia": defensa.get("decision"), "diagnostico": dg.get("tipo")})
            ultima = r

            # ¿Mismo intento una y otra vez? Es un bucle, no una corrección.
            if ej.repetida("propuesta", defensa.get("decision"), defensa.get("herramienta"),
                           defensa.get("parametros")):
                ej._cortar("el defensor repitió la misma propuesta", "bucle")
                break
            if not _puede_reintentar(dg, defensa, identidad, repo):
                ej.estado = "terminado"
                ej.motivo_corte = "criterio de salida alcanzado"
                break
        ultima = ultima if ultima is not None else {
            "defensa": None, "ejecucion": None, "veredicto": "ERROR", "nota": None, "ia_fallo": False,
            "nivel_fuga": "NINGUNA", "circuito_sesion": False, "origen_decision": "harness",
            "error": f"harness: {ej.motivo_corte or 'sin ejecución'}"}
        if "diagnostico" not in ultima or ultima["diagnostico"] is None:
            ultima["diagnostico"] = diagnostico.diagnosticar(ultima)
        ultima["harness"] = ej.a_json()
        return ultima
    except Exception as exc:  # noqa: BLE001
        ej.estado, ej.motivo_corte = "error", f"{type(exc).__name__}: {exc}"
        base = ultima if isinstance(ultima, dict) else {"defensa": None, "ejecucion": None, "nota": None}
        base.update(veredicto="ERROR", error=f"harness: {type(exc).__name__}: {exc}")
        base["diagnostico"] = diagnostico.diagnosticar(base)
        base["harness"] = ej.a_json()
        return base


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
# Control de una PARTIDA completa (Fase B)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
# `Ejecucion` acota UNA solicitud. Una partida son muchas, y hasta ahora nadie ponía techo al conjunto: una
# batalla podía gastar inferencia sin límite y repetir el mismo ataque ronda tras ronda sin que constara.
#
# `ControlPartida` es ese techo. Lo que NO hace, y es la razón de que se pueda poner en el camino de la
# batalla sin debilitarla:
#   - no cambia ningún veredicto;
#   - no reintenta nada (el único reintento del laboratorio sigue siendo el de `_puede_reintentar`);
#   - no concede permisos ni los retira;
#   - solo cuenta, y cuando se agota un techo, PARA y dice por qué.


@dataclass(frozen=True)
class PresupuestoPartida:
    """Techos de una partida completa. `max_rondas` lo fija quien inicia la partida; el resto son topes de
    seguridad para que una batalla no se coma la máquina ni gire en vacío.

    `max_errores_consecutivos` corta cuando algo está roto de verdad (Ollama caído, por ejemplo) en vez de
    quemar las rondas restantes produciendo errores. Cuenta errores de cualquier clase a propósito: el
    objetivo es detectar que el entorno no responde, y para eso da igual de quién sea la culpa."""
    max_rondas: int = 12
    max_llamadas_modelo: int = 64
    max_tokens_salida: int | None = None
    max_tokens_entrada: int | None = None
    timeout_global_s: float = 1800.0
    max_errores_consecutivos: int = 3
    max_repeticiones_identicas: int = 2


class ControlPartida:
    """Presupuesto observable y cancelable de UNA partida. Serializable con `a_json()`."""

    def __init__(self, presupuesto=None, reloj=time.monotonic):
        self.presupuesto = presupuesto or PresupuestoPartida()
        self._reloj = reloj
        self.inicio = reloj()
        self.estado = "en_curso"
        self.motivo_corte = None
        self.rondas = 0
        self.llamadas_modelo = 0
        self.tokens_entrada = 0
        self.tokens_salida = 0
        self.errores = 0
        self.errores_consecutivos = 0
        self.cortes = []          # rondas en las que el harness cortó, con su motivo
        self.huellas = {}
        self._cancelar = threading.Event()

    # -- Control -------------------------------------------------------------------------------------------
    @property
    def transcurrido_s(self):
        return self._reloj() - self.inicio

    @property
    def restante_s(self):
        return max(0.0, self.presupuesto.timeout_global_s - self.transcurrido_s)

    def cancelar(self, motivo="cancelado por el árbitro"):
        """Pide la detención. Se atiende ENTRE rondas: una ronda en curso termina y se registra entera, para
        que la partida no quede con una ronda a medias en la auditoría."""
        self._cancelar.set()
        if self.motivo_corte is None:
            self.motivo_corte = motivo

    @property
    def cancelada(self):
        return self._cancelar.is_set()

    def puede_jugar_ronda(self):
        """-> (bool, motivo). Se consulta ANTES de cada ronda. Fija `estado` cuando la respuesta es no."""
        p = self.presupuesto
        if self.cancelada:
            return self._no("cancelado", self.motivo_corte or "cancelado")
        if self.transcurrido_s >= p.timeout_global_s:
            return self._no("agotado", f"timeout global de partida ({p.timeout_global_s:g} s)")
        if self.rondas >= p.max_rondas:
            return self._no("terminado", f"se jugaron las {p.max_rondas} rondas previstas")
        if self.llamadas_modelo >= p.max_llamadas_modelo:
            return self._no("agotado", f"límite de {p.max_llamadas_modelo} llamadas al modelo en la partida")
        if p.max_tokens_salida is not None and self.tokens_salida >= p.max_tokens_salida:
            return self._no("agotado", f"presupuesto de {p.max_tokens_salida} tokens de salida")
        if p.max_tokens_entrada is not None and self.tokens_entrada >= p.max_tokens_entrada:
            return self._no("agotado", f"presupuesto de {p.max_tokens_entrada} tokens de entrada")
        if self.errores_consecutivos >= p.max_errores_consecutivos:
            return self._no("error",
                            f"{self.errores_consecutivos} rondas con error seguidas: el entorno no responde")
        return True, None

    def _no(self, estado, motivo):
        self.estado = estado
        self.motivo_corte = motivo
        return False, motivo

    def ataque_repetido(self, prompt):
        """¿El atacante ya mandó ese mismo texto más veces de las permitidas? Registra y responde.

        No corta la partida por sí mismo: quien decide es quien lleva el bucle de rondas. Un ataque repetido
        no es un fallo de seguridad, es un modelo girando en vacío, y conviene que se vea como tal."""
        if not prompt:
            return False
        h = huella("ataque", prompt)
        self.huellas[h] = self.huellas.get(h, 0) + 1
        return self.huellas[h] > self.presupuesto.max_repeticiones_identicas

    # -- Contabilidad --------------------------------------------------------------------------------------
    def _sumar(self, origen, pares):
        for campo, attr in pares:
            v = (origen or {}).get(campo)
            if isinstance(v, int) and not isinstance(v, bool):
                setattr(self, attr, getattr(self, attr) + v)

    def registrar_ronda(self, r):
        """Suma a la partida lo que consumió una ronda. `r` es el dict de `motor.ejecutar_ronda`.

        El consumo del defensor sale del bloque `harness` cuando la ronda pasó por él; si no pasó, se cuenta
        una llamada por el defensor. La del atacante se cuenta siempre aparte, porque ocurre fuera del
        harness. `intentos` incluye el reintento de JSON de `cliente_ollama`, que también es inferencia."""
        r = r if isinstance(r, dict) else {}
        self.rondas += 1
        at = r.get("ataque") or {}
        dfn = r.get("defensa") or {}
        hns = r.get("harness") or {}
        consumo = hns.get("consumo") or {}

        llamadas = max(1, int(at.get("intentos") or 1)) if at else 0
        if consumo:
            llamadas += int(consumo.get("llamadas_modelo") or 0)
        elif dfn:
            llamadas += max(1, int(dfn.get("intentos") or 1))
        self.llamadas_modelo += llamadas

        self._sumar(at, (("tokens", "tokens_salida"), ("tokens_entrada", "tokens_entrada")))
        if consumo:
            self._sumar(consumo, (("tokens_salida", "tokens_salida"), ("tokens_entrada", "tokens_entrada")))
        elif dfn:
            self._sumar(dfn, (("tokens", "tokens_salida"), ("tokens_entrada", "tokens_entrada")))

        if r.get("veredicto") == "ERROR":
            self.errores += 1
            self.errores_consecutivos += 1
        else:
            self.errores_consecutivos = 0

        if hns.get("estado") in ("agotado", "bucle", "cancelado", "error"):
            self.cortes.append({"ronda": r.get("ronda"), "estado": hns["estado"],
                                "motivo": hns.get("motivo_corte")})
        return self.consumo()

    def consumo(self):
        """Lo que la interfaz necesita para dibujar el presupuesto SIN inventar nada."""
        p = self.presupuesto
        return {"rondas": self.rondas, "max_rondas": p.max_rondas,
                "llamadas_modelo": self.llamadas_modelo, "max_llamadas_modelo": p.max_llamadas_modelo,
                "tokens_entrada": self.tokens_entrada, "tokens_salida": self.tokens_salida,
                "max_tokens_salida": p.max_tokens_salida,
                "errores": self.errores, "errores_consecutivos": self.errores_consecutivos,
                "max_errores_consecutivos": p.max_errores_consecutivos,
                "transcurrido_ms": int(self.transcurrido_s * 1000),
                "timeout_global_s": p.timeout_global_s,
                "estado": self.estado, "motivo_corte": self.motivo_corte,
                "cortes_harness": len(self.cortes)}

    def cerrar(self, motivo="partida finalizada"):
        """Marca el final normal. No sobreescribe un corte anterior: si la partida se agotó, se agotó."""
        if self.estado == "en_curso":
            self.estado, self.motivo_corte = "terminado", motivo
        return self.consumo()

    def a_json(self):
        return {"estado": self.estado, "motivo_corte": self.motivo_corte,
                "presupuesto": asdict(self.presupuesto), "consumo": self.consumo(),
                "cortes": list(self.cortes)}


def _sin_ejecucion(presupuesto, motivo):
    """Resultado de una solicitud que NO se lanzó porque la partida ya no tenía presupuesto. Es un error
    visible con la forma de siempre, nunca un veredicto inventado."""
    return {"defensa": None, "ejecucion": None, "veredicto": "ERROR", "nota": None, "ia_fallo": False,
            "nivel_fuga": "NINGUNA", "circuito_sesion": False, "origen_decision": "harness",
            "error": f"harness: {motivo}",
            "harness": {"estado": "agotado", "motivo_corte": motivo,
                        "presupuesto": asdict(presupuesto or Presupuesto()),
                        "consumo": {"iteraciones": 0, "llamadas_modelo": 0, "tokens_entrada": 0,
                                    "tokens_salida": 0, "transcurrido_ms": 0},
                        "pasos": [], "herramientas_usadas": [], "errores": []}}


def procesador(presupuesto=None, control=None):
    """-> una función con la MISMA firma que `motor.procesar_defensa` que pasa por el harness.

    Es la pieza que conecta el harness con la partida sin que `motor` tenga que importar `harness` (sería un
    ciclo: aquí se importa `motor`). Se le pasa a `motor.ejecutar_ronda(procesar=...)`.

    El presupuesto por defecto de una solicitud permite hasta 3 iteraciones, pero el harness solo itera ante
    un error TÉCNICO del modelo; ante cualquier decisión válida sale en la primera. Es decir: en una partida
    normal el número de inferencias es el mismo que por el camino directo."""
    def _procesar(host, modelo_def, solicitud, identidad, repo=None, riesgo_sesion=None, resumen_sesion=None,
                  equipo=None, **kw):
        pres = presupuesto
        if control is not None:
            if control.restante_s <= 0:
                return _sin_ejecucion(pres, "timeout global de partida agotado")
            base = pres or Presupuesto()
            # El techo de tiempo de una solicitud nunca puede pasarse del que le queda a la partida.
            pres = Presupuesto(**{**asdict(base),
                                  "timeout_global_s": min(base.timeout_global_s, control.restante_s)})
        return ejecutar(host, modelo_def, solicitud, identidad, repo, pres, equipo, riesgo_sesion,
                        resumen_sesion)
    return _procesar
