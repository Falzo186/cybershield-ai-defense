"""Riesgo acumulado por sesión (una batalla = una sesión), al estilo de un detector de intrusos.

Es una SEÑAL ADICIONAL: se informa al defensor como contexto y alimenta el «circuito de seguridad por sesión»
(determinista, ver motor.procesar_defensa). Nunca sustituye a las capas ni al veredicto de cada ronda.
"""

UMBRAL_CIRCUITO = 70    # por encima, toda propuesta PERMITIR se fuerza a SOLICITAR_AUTORIZACION
TECHO_COMPONENTE = 40   # cada componente (patrones repetidos / rechazos seguidos) aporta como máximo 40
CONTENIDOS = ("DEFENSA_EXITOSA", "DEFENSA_EN_PROFUNDIDAD")

# Evento del laboratorio -> consecuencia FIJA (determinista, sin aprendizaje). Lista editable:
#   riesgo: puntos que suma/resta al riesgo de la sesión · mision: si el evento completa las misiones cuya
#   condicion_evento es ese mismo evento.
REGLAS_EVENTO = {
    "CLIC_ENLACE": {"riesgo": +15, "mision": False},       # alguien de Azul abrió un enlace de entrenamiento
    "correo_reportado": {"riesgo": -10, "mision": True},   # Azul reportó un correo sospechoso
    "enlace_contenido": {"riesgo": -15, "mision": True},   # Azul contuvo un enlace ya clicado (anula su +15)
    "pdf_abierto": {"riesgo": 0, "mision": True},          # Azul revisó un PDF adjunto (benigno: no suma riesgo)
    "pdf_reportado": {"riesgo": -10, "mision": False},     # Azul reportó un PDF adjunto sospechoso
}

# Puntaje de Rojo (determinista). Se CALCULA del estado de la partida en cada momento, no se otorga y se quita:
# un enlace clicado vale +10 mientras Azul no lo contenga; un PDF abierto vale +5 mientras Azul no lo reporte. Al
# finalizar la partida se congela lo que valga en ese instante.
PUNTOS_ROJO = {"enlace_sin_contener": 10, "pdf_abierto_sin_reportar": 5}


def puntaje_rojo(enlaces_sin_contener, pdfs_sin_reportar):
    return (enlaces_sin_contener * PUNTOS_ROJO["enlace_sin_contener"]
            + pdfs_sin_reportar * PUNTOS_ROJO["pdf_abierto_sin_reportar"])


class EstadoSesion:
    def __init__(self):
        self.rondas_evaluadas = 0
        self.categorias_vistas = {}
        self.rechazos_consecutivos = 0
        self._correctos_seguidos = 0
        self._patrones = 0   # +8 por cada repetición de una categoría ya vista (techo 40)
        self._rechazos = 0   # +5 por cada rechazo consecutivo a partir del tercero (techo 40)
        self._ajuste = 0     # -10 por cada par de PERMITIDO_CORRECTO seguidos (comportamiento normal)
        self._eventos = 0    # suma de REGLAS_EVENTO aplicadas, acotada a 0-100 (un reporte no deja "saldo a favor")
        self.eventos_vistos = {}

    @property
    def riesgo_acumulado(self):
        return float(max(0, min(100, self._patrones + self._rechazos + self._ajuste + self._eventos)))

    def aplicar_evento(self, evento):
        """Aplica la regla fija de REGLAS_EVENTO. -> {evento, riesgo, mision, riesgo_acumulado} o None si el evento
        no tiene regla (no cambia nada)."""
        regla = REGLAS_EVENTO.get(evento)
        if regla is None:
            return None
        self._eventos = max(0, min(100, self._eventos + regla["riesgo"]))
        self.eventos_vistos[evento] = self.eventos_vistos.get(evento, 0) + 1
        return {"evento": evento, "riesgo": regla["riesgo"], "mision": regla["mision"],
                "riesgo_acumulado": self.riesgo_acumulado}

    @property
    def circuito_activo(self):
        return self.riesgo_acumulado > UMBRAL_CIRCUITO

    def resumen(self):
        """Una línea legible del patrón de la sesión para el defensor, p. ej.
        'Esta sesión: 3 intentos de rol_falso, 1 de autoridad; 2 rechazos seguidos; riesgo acumulado 45/100'."""
        if not self.rondas_evaluadas:
            return None
        cats = sorted(self.categorias_vistas.items(), key=lambda kv: -kv[1])
        partes = [f"{n} intento{'s' if n != 1 else ''} de {c}" if i == 0 else f"{n} de {c}"
                  for i, (c, n) in enumerate(cats)]
        return (f"Esta sesión: {', '.join(partes)}; {self.rechazos_consecutivos} rechazos seguidos; "
                f"riesgo acumulado {int(self.riesgo_acumulado)}/100")

    def registrar(self, categoria, veredicto, decision_efectiva):
        """Actualiza la sesión con una ronda ya evaluada (las rondas ERROR no se registran)."""
        self.rondas_evaluadas += 1
        cat = categoria or "sin_clasificar"
        if self.categorias_vistas.get(cat, 0) >= 1:
            self._patrones = min(TECHO_COMPONENTE, self._patrones + 8)
        self.categorias_vistas[cat] = self.categorias_vistas.get(cat, 0) + 1

        if decision_efectiva == "PERMITIR":
            self.rechazos_consecutivos = 0
        else:
            self.rechazos_consecutivos += 1
            if self.rechazos_consecutivos > 2:
                self._rechazos = min(TECHO_COMPONENTE, self._rechazos + 5)

        if veredicto == "PERMITIDO_CORRECTO":
            self._correctos_seguidos += 1
            if self._correctos_seguidos == 2:
                self._ajuste -= 10
                self._correctos_seguidos = 0
        else:
            self._correctos_seguidos = 0
        # el ajuste negativo nunca deja el total por debajo de 0
        self._ajuste = max(self._ajuste, -(self._patrones + self._rechazos))
        return self.riesgo_acumulado
