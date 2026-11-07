"""Campañas grandes (n >= 200 por condición), por lotes y reanudables.

Por qué este programa existe: el informe de la etapa de integración cerró dos criterios a 0,5 porque la
maquinaria de medición estaba probada pero la medición seria no se había hecho. Las cifras de la §11 de
`docs/INFORME_INTEGRACION.md` salieron de 40 inferencias: sirven para validar el método, no para concluir
nada. Esto ejecuta el conjunto completo con repeticiones hasta pasar de 200 observaciones imputables por
condición, que es el tamaño que el propio laboratorio exige para interpretar una diferencia.

Cómo está montado, y por qué así:

  - **El plan es el mismo para las seis condiciones.** `familias=None` (las doce, incluidas las difíciles),
    `repeticiones=4`, `semilla=0`. 256 rondas planificadas, 244 verificables. Si el plan cambiara entre
    condiciones, los números no serían comparables y `lotes.py` se negaría a reanudar.
  - **Cada condición tiene un nombre fijo**, no un identificador con hora. Así este programa se puede
    cortar y volver a lanzar: busca la campaña por su nombre, y si existe, sigue donde la dejó.
  - **Se ejecuta por lotes** de 32 rondas. Cada lote deja su marca en el JSONL de la campaña. Un corte
    pierde como mucho la ronda en curso.
  - **No interpreta.** Sumar, dividir y sacar intervalos es cosa de `metricas.py`; aquí solo se ejecuta y se
    imprime el progreso.

Lo que NO hace: no borra campañas, no reescribe resultados y no rellena rondas que no se ejecutaron. Si una
condición queda a medias, su resumen sale marcado como parcial.

Uso:
    python experimentos/campanas_grandes.py                  # todas, en orden, hasta terminar
    python experimentos/campanas_grandes.py --estado          # solo informar de lo que hay
    python experimentos/campanas_grandes.py --solo l32-fewshot
    python experimentos/campanas_grandes.py --max-segundos 3600
"""
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.lab import repositorio                                      # noqa: E402
from src.lab.evaluacion import campana, lotes                        # noqa: E402

HOST = "http://localhost:11434"
RONDAS_POR_LOTE = 32

# El plan, idéntico en las seis condiciones. Fijado ANTES de medir y no se toca después.
PLAN = {"modo": "intensivo", "familias": None, "repeticiones": 4, "semilla": 0,
        "solo_verificables": False}

# Las condiciones. Cada una cambia UNA cosa respecto de la base `l32-fewshot`, para que la diferencia que
# se mida sea atribuible a ese cambio y no a dos a la vez.
CONDICIONES = [
    ("l32-fewshot",     {"modelo": "llama3.2:3b", "tecnica": "fewshot",     "pipeline": "directo"},
     "Base: llama3.2:3b con ejemplos en el prompt."),
    ("l32-base",        {"modelo": "llama3.2:3b", "tecnica": "base",        "pipeline": "directo"},
     "Sin ejemplos: mide cuánto aportan los pocos ejemplos del prompt."),
    ("l32-rag",         {"modelo": "llama3.2:3b", "tecnica": "rag",         "pipeline": "directo"},
     "Documentación recuperada, sin ejemplos."),
    ("l32-fewshot-rag", {"modelo": "llama3.2:3b", "tecnica": "fewshot_rag", "pipeline": "directo"},
     "Ejemplos y documentación recuperada."),
    ("q25-fewshot",     {"modelo": "qwen2.5:7b",  "tecnica": "fewshot",     "pipeline": "directo"},
     "Mismo conjunto con un modelo más grande: compara modelos, no técnicas."),
    ("l32-harness",     {"modelo": "llama3.2:3b", "tecnica": "fewshot",     "pipeline": "harness"},
     "La base, pero pasando por el harness: mide su coste real."),
]
NOMBRES = {n for n, _, _ in CONDICIONES}
PREFIJO = "grande-"


def config_de(nombre):
    base = next(c for n, c, _ in CONDICIONES if n == nombre)
    return dict(PLAN) | dict(base) | {"host": HOST}


def id_de(nombre):
    return PREFIJO + nombre


def abrir_o_crear(nombre):
    """-> id de la campaña. La crea con nombre fijo si no existe; si existe, no la toca."""
    idc, config = id_de(nombre), config_de(nombre)
    try:
        lotes.leer(idc)
        return idc
    except lotes.ErrorLote:
        pass
    trabajos = campana.plan(config["modo"], config["familias"], config["repeticiones"],
                            config["semilla"], repositorio.abrir(":memory:"),
                            bool(config["solo_verificables"]))
    lotes.crear(config, trabajos, id_campana=idc)
    return idc


def estado():
    print(f"Plan común: {PLAN}")
    print(f"{'condición':<18} {'hechas':>7} {'de':>5} {'%':>6}  estado")
    for nombre, _, _ in CONDICIONES:
        try:
            p = lotes.progreso(id_de(nombre))
        except lotes.ErrorLote:
            print(f"{nombre:<18} {'-':>7} {'-':>5} {'-':>6}  sin empezar")
            continue
        print(f"{nombre:<18} {p['hechas']:>7} {p['planificadas']:>5} {p['fraccion'] * 100:>5.1f}%  "
              f"{'completa' if p['completa'] else 'parcial'}")


def ejecutar(nombre, max_segundos=None):
    """Lleva una condición hasta el final, lote a lote. -> progreso final."""
    idc = abrir_o_crear(nombre)
    t0 = time.monotonic()
    while True:
        p = lotes.progreso(idc)
        if p["completa"]:
            return p
        if max_segundos is not None and (time.monotonic() - t0) >= max_segundos:
            print(f"  [{nombre}] tope de tiempo de esta tanda; quedan {p['pendientes']} rondas")
            return p
        restante = None if max_segundos is None else max(1.0, max_segundos - (time.monotonic() - t0))
        r = lotes.ejecutar_lote(id_campana=idc, config=config_de(nombre),
                                max_rondas=RONDAS_POR_LOTE, max_segundos=restante)
        pr, lt = r["progreso"], r["lote"]
        por_ronda = (lt["duracion_s"] / lt["rondas"]) if lt["rondas"] else 0.0
        ex = r["metricas"]["exactitud"]
        print(f"  [{nombre}] {pr['hechas']:>3}/{pr['planificadas']} "
              f"({pr['fraccion'] * 100:4.1f}%) · lote {lt['rondas']} rondas en "
              f"{lt['duracion_s'] / 60:.1f} min ({por_ronda:.1f} s/ronda) · "
              f"exactitud acumulada {ex['valor'] if ex['valor'] is None else round(ex['valor'] * 100, 1)}"
              f" n={ex['n']}", flush=True)
        if lt["rondas"] == 0:
            print(f"  [{nombre}] un lote no avanzó ninguna ronda: se para para no girar en vacío")
            return pr


def main(argv):
    if "--estado" in argv:
        estado()
        return 0
    solo = None
    if "--solo" in argv:
        solo = argv[argv.index("--solo") + 1]
        if solo not in NOMBRES:
            print(f"condición desconocida: {solo}. Son: {', '.join(sorted(NOMBRES))}")
            return 2
    max_s = None
    if "--max-segundos" in argv:
        max_s = float(argv[argv.index("--max-segundos") + 1])

    pendientes = [n for n, _, _ in CONDICIONES if solo is None or n == solo]
    print(f"Campañas grandes · {len(pendientes)} condición(es) · plan {PLAN}")
    print(f"Host de Ollama: {HOST}\n")
    t0 = time.monotonic()
    resultados = {}
    for nombre in pendientes:
        descripcion = next(d for n, _, d in CONDICIONES if n == nombre)
        print(f"── {nombre} · {descripcion}")
        p = ejecutar(nombre, None if max_s is None else max(1.0, max_s - (time.monotonic() - t0)))
        resultados[nombre] = p
        print(f"   {'TERMINADA' if p['completa'] else 'PARCIAL'}: "
              f"{p['hechas']}/{p['planificadas']}\n", flush=True)
        if max_s is not None and (time.monotonic() - t0) >= max_s:
            print("Tope de tiempo de la tanda. Vuelva a lanzar el programa para seguir.")
            break
    print(f"Total de esta tanda: {(time.monotonic() - t0) / 60:.1f} min")
    estado()
    return 0 if all(p["completa"] for p in resultados.values()) else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nInterrumpido. Lo ejecutado está guardado; vuelva a lanzar para seguir.")
        sys.exit(130)
