"""Campañas PEQUEÑAS para validar la metodología de la Fase E. Ejecutar:
    python experimentos/validar_metodologia.py [modelo] [repeticiones] [rondas_atacante]

Qué hace y qué NO hace:

  - **Sí**: ejecuta las tres medidas contra un Ollama real y comprueba que la metodología funciona de
    extremo a extremo: que las cifras salen, que los denominadores son los que deben ser, que los errores
    de infraestructura quedan fuera del porcentaje y que el resultado se puede guardar y comparar.
  - **No**: no pretende medir la calidad de ningún modelo. Con ~19 casos maliciosos, el intervalo de
    confianza es tan ancho que casi cualquier diferencia sale como no concluyente. El propio informe que
    imprime lo dice en cada bloque.

Para una medición de verdad hacen falta n ≥ 200 por condición, y eso en esta máquina (CPU, sin GPU
utilizable) son horas: se hace con `evaluacion/lotes.py`, que permite partirlo y reanudarlo.

Escribe el resultado completo en `data/validacion_metodologia.json` y no toca nada más.
"""
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.lab import adversarial, cliente_ollama, defensor, motor, permisos, repositorio  # noqa: E402
from src.lab.evaluacion import metricas  # noqa: E402

HOST = "http://localhost:11434"
SALIDA = RAIZ / "data" / "validacion_metodologia.json"


def ic(w):
    """Intervalo de confianza en texto, o «sin muestra» cuando no hay denominador."""
    if w.get("valor") is None:
        return f"sin muestra (n={w.get('n', 0)})"
    return (f"{w['valor'] * 100:.1f} % (IC95 [{w['bajo'] * 100:.1f}, {w['alto'] * 100:.1f}], "
            f"{w['exitos']}/{w['n']})")


def main():
    modelo = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rondas = int(sys.argv[3]) if len(sys.argv) > 3 else 6

    if not cliente_ollama.ollama_disponible(HOST):
        print(f"Ollama no responde en {HOST}. No se ejecuta nada: no hay nada que medir.")
        return 2
    instalados = cliente_ollama.listar_modelos(HOST)
    if modelo not in instalados:
        print(f"El modelo «{modelo}» no está instalado. Disponibles: {', '.join(instalados)}")
        return 2

    repo = repositorio.abrir(":memory:")
    ident = permisos.Identidad("eval.empleado", "empleado")
    salida = {"modelo": modelo, "host": HOST, "repeticiones": reps, "rondas_atacante": rondas,
              "inicio": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    # ── 1 · Detección del filtro determinista (sin inferencia) ────────────────────────────────────────────
    print("1 · Detección del filtro determinista (0 inferencias, 100 % reproducible)")
    det = adversarial.campana_deteccion()
    md = det["metricas"]
    print(f"    sensibilidad: {ic(md['deteccion'])}")
    print(f"    falsos positivos: {ic(md['falsos_positivos'])}")
    print(f"    categorías no detectadas: {', '.join(md['categorias_no_detectadas']) or 'ninguna'}")
    salida["filtro"] = md

    # ── 2 · Resistencia del MODELO defensor (sin el filtro delante) ───────────────────────────────────────
    total = reps * len(adversarial.casos())
    print(f"\n2 · Resistencia del modelo «{modelo}» SIN el filtro delante ({total} inferencias)")
    t0 = time.monotonic()

    def avance(n, fila):
        print(f"\r    {n}/{total}  ({fila['id']}: {fila['decision'] or fila['resultado']})".ljust(70),
              end="", flush=True)

    rm = adversarial.campana_modelo(defensor.analizar, HOST, modelo, ident, repeticiones=reps,
                                    al_avanzar=avance)
    mm = rm["metricas"]
    cls = mm["clasificacion"]
    print(f"\r    {total}/{total} en {time.monotonic() - t0:.0f} s".ljust(70))
    print(f"    recall (contiene lo malicioso): {ic(cls['recall'])}")
    print(f"    precisión: {ic(cls['precision'])}")
    print(f"    especificidad (no molesta a lo benigno): {ic(cls['especificidad'])}")
    print(f"    F1: {cls['f1'] if cls['f1'] is None else round(cls['f1'], 3)}  ·  {cls['nota_f1']}")
    print(f"    indeterminados (fallo de inferencia): {mm['indeterminados']}")
    print(f"    repetibilidad: {mm['repetibilidad']['tasa']}")
    salida["modelo_defensor"] = mm

    # ── 3 · Filtro contra modelo ──────────────────────────────────────────────────────────────────────────
    print("\n3 · ¿Aporta el modelo algo sobre el filtro determinista?")
    comp = adversarial.comparar_filtro_y_modelo(det, rm)
    print(f"    {comp['comparacion']['veredicto']}: {comp['comparacion'].get('explicacion', '')}")
    print(f"    {comp['nota']}")
    salida["filtro_vs_modelo"] = comp["comparacion"]

    # ── 4 · Capacidad del modelo atacante (camino completo) ───────────────────────────────────────────────
    print(f"\n4 · Capacidad del atacante «{modelo}» contra el sistema completo ({rondas} rondas, "
          f"{rondas * 2} inferencias)")
    t0 = time.monotonic()

    def avance_a(n, fila):
        print(f"\r    ronda {n}/{rondas}  ({fila['veredicto']})".ljust(70), end="", flush=True)

    ra = adversarial.campana_atacante(motor.ejecutar_ronda, HOST, modelo, modelo, ident, repo,
                                      rondas=rondas, al_avanzar=avance_a)
    ma = ra["metricas"]
    print(f"\r    {rondas} rondas en {time.monotonic() - t0:.0f} s".ljust(70))
    print(f"    objetivo conseguido: {ic(ma['objetivo_conseguido'])}")
    print(f"    rondas no imputables (infraestructura): {ma['infraestructura']}")
    print(f"    frenado por: {ma['frenado_por']}")
    salida["modelo_atacante"] = ma

    # ── Lo que estas cifras NO dicen ──────────────────────────────────────────────────────────────────────
    n_mal = cls["positivos_reales"]
    print("\n" + "=" * 100)
    print("QUÉ SE HA VALIDADO: que las tres medidas se ejecutan de extremo a extremo contra un Ollama real,")
    print("que cada una tiene su propio denominador y que los fallos de infraestructura quedan fuera.")
    print(f"QUÉ NO: con {n_mal} casos maliciosos y {rondas} rondas, NINGUNA de estas cifras es concluyente.")
    print(f"        El tamaño mínimo de muestra de este laboratorio es {metricas.MUESTRA_MINIMA} por")
    print("        condición, y para comparar modelos hacen falta n ≥ 200: use evaluacion/lotes.py.")
    print("=" * 100)

    salida["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    salida["aviso"] = (f"Muestra pequeña ({n_mal} maliciosos, {rondas} rondas del atacante). Sirve para "
                       "validar la metodología, NO para sacar conclusiones sobre el modelo.")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nResultado completo: {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
