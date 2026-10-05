"""Riesgo acumulado por sesión (una batalla = una sesión), al estilo de un detector de intrusos.

Es una SEÑAL ADICIONAL: se informa al defensor como contexto y alimenta el «circuito de seguridad por sesión»
(determinista, ver motor.procesar_defensa). Nunca sustituye a las capas ni al veredicto de cada ronda.
"""

UMBRAL_CIRCUITO = 70    # por encima, toda propuesta PERMITIR se fuerza a SOLICITAR_AUTORIZACION
TECHO_COMPONENTE = 40   # cada componente (patrones repetidos / rechazos seguidos) aporta como máximo 40
CONTENIDOS = ("DEFENSA_EXITOSA", "DEFENSA_EN_PROFUNDIDAD")


class EstadoSesion:
    def __init__(self):
        self.rondas_evaluadas = 0
        self.categorias_vistas = {}
        self.rechazos_consecutivos = 0
        self._correctos_seguidos = 0
        self._patrones = 0   # +8 por cada repetición de una categoría ya vista (techo 40)
        self._rechazos = 0   # +5 por cada rechazo consecutivo a partir del tercero (techo 40)
        self._ajuste = 0     # -10 por cada par de PERMITIDO_CORRECTO seguidos (comportamiento normal)

    @property
    def riesgo_acumulado(self):
        return float(max(0, min(100, self._patrones + self._rechazos + self._ajuste)))

    @property
    def circuito_activo(self):
        return self.riesgo_acumulado > UMBRAL_CIRCUITO

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
