"""Avance del proyecto, con los pesos y los criterios de `docs/AUDITORIA_INTEGRACION.md` §5.

Por qué es un programa y no una suma a mano: el encargo exige que el porcentaje salga de una fórmula con
pesos fijados ANTES de medir, y que no se toquen después. Teniéndolo aquí, la aritmética es verificable, y
cualquier cambio de peso aparece en el historial de git en vez de dentro de una tabla de texto.

    avance = Σ(peso_i × cumplimiento_i) / Σ(peso_i)        cumplimiento ∈ {0, 0,5, 1}

Los PESOS no se han modificado desde la auditoría. Lo único que cambia entre etapas es el cumplimiento, y
cada cambio lleva al lado la evidencia que lo justifica.

Uso:  python experimentos/avance.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# (criterio, peso, auditoría, etapa de integración, campañas grandes, evidencia del valor actual)
# Los tres valores de cumplimiento son el histórico; no se reescriben, se añade una columna.
CRITERIOS = [
    ("Partida completa entre dos modelos reales",        10, 1,   1,   1,   "e2e/demo_partida.py 106/106"),
    ("Selección independiente de modelos Rojo/Azul",      6, 1,   1,   1,   "server/test_batalla_partida.py"),
    ("Acciones dentro de un escenario ficticio",          6, 1,   1,   1,   "test_escenarios_empresa 75"),
    ("Validación de acciones por el motor",              10, 1,   1,   1,   "test_motor 41 · seis capas"),
    ("Misiones defensivas funcionales",                   8, 1,   1,   1,   "test_misiones 17"),
    ("Consecuencias verificables",                        8, 1,   1,   1,   "test_incidentes 42"),
    ("Diagnóstico de cada ronda",                         6, 1,   1,   1,   "test_diagnostico 50"),
    ("Harness integrado",                                 8, 0,   1,   1,   "test_control_partida 56 · test_presupuesto 28"),
    ("Persistencia de partidas",                          6, 1,   1,   1,   "e2e/test_reinicio.py"),
    ("Cronología consultable",                            6, 1,   1,   1,   "test_correlacion 39"),
    ("Evaluación adversarial del defensor",               8, 0,   0.5, 1,
     "1 536 inferencias reales · 244 imputables × 6 condiciones · línea base trivial · CAMPANAS_GRANDES.md"),
    ("Evaluación del objetivo del atacante",              6, 0,   0.5, 1,
     "480 rondas en 40 sesiones · 2 condiciones · IC agrupado por sesión · CAMPANA_ATACANTE.md"),
    ("Panel coherente con la partida",                    6, 0.5, 1,   1,   "ui/tokens.css en las dos pantallas"),
    ("Vista de espectador de solo lectura",               4, 1,   1,   1,   "server/test_partida.py 73"),
    ("Separación real / simulado",                        6, 1,   1,   1,   "test_wazuh 105 · marca y color propios"),
    ("Wazuh real probado, o limitación documentada",      6, 0.5, 1,   1,
     "cliente, contrato y prueba condicional; sin instalación real, documentado en INTEGRACION_WAZUH.md"),
    ("Batería completa en verde",                         8, 1,   1,   1,   "ver el total de ejecutar_pruebas.py"),
    ("Documentación actualizada",                         4, 1,   1,   1,   "6 documentos al día"),
]
ETAPAS = ("auditoría", "integración", "campañas")


def avance(indice):
    """-> (suma_ponderada, suma_pesos, fraccion) de la etapa `indice` (0, 1 o 2)."""
    pesos = sum(c[1] for c in CRITERIOS)
    suma = sum(c[1] * c[2 + indice] for c in CRITERIOS)
    return suma, pesos, (suma / pesos if pesos else 0.0)


def main():
    print("AVANCE · pesos de docs/AUDITORIA_INTEGRACION.md §5, sin modificar\n")
    print(f"{'criterio':<48} {'peso':>4} " + " ".join(f"{e:>12}" for e in ETAPAS))
    for nombre, peso, a, b, c, _ in CRITERIOS:
        marca = "*" if c != b else " "
        print(f"{marca}{nombre:<47} {peso:>4} " + " ".join(f"{v:>12}" for v in (a, b, c)))
    print()
    for i, etapa in enumerate(ETAPAS):
        suma, pesos, frac = avance(i)
        print(f"{etapa:<14} Σ(peso × cumplimiento) = {suma:>5} / {pesos}  →  **{frac * 100:.1f} %**")

    pendientes = [(n, p, c) for n, p, _, _, c, _ in CRITERIOS if c < 1]
    print()
    if pendientes:
        print("Criterios que NO están a 1:")
        for n, p, c in pendientes:
            print(f"  {n} (peso {p}): {c}")
    else:
        print("Todos los criterios de la §18 del encargo están a 1 con evidencia.")
        print("Eso NO significa que el proyecto esté terminado: los criterios miden el encargo, no el")
        print("sistema. Lo que sigue abierto está en la §17 del informe y en las limitaciones de cada")
        print("documento de resultados (TLS sin desplegar, Wazuh sin instalación real, RAG sin embeddings,")
        print("y un objetivo del atacante de 0/462 cuyo intervalo por sesión llega al 16 %).")
    print("\n── Evidencia del valor actual")
    for nombre, _, _, _, _, ev in CRITERIOS:
        print(f"  {nombre:<48} {ev}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
