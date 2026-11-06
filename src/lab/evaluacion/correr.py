"""Lanzador de campañas reales contra Ollama. Ejecutar:

    python -m src.lab.evaluacion.correr --modelo qwen2.5:1.5b --modo rapido
    python -m src.lab.evaluacion.correr --modelo qwen2.5:1.5b --modo comparativo --matriz
    python -m src.lab.evaluacion.correr --modelo llama3.2:3b --familias oficiales,parecidos --repeticiones 3

Esto SÍ usa Ollama de verdad. Si Ollama no responde, lo dice y no ejecuta nada (no hay modo simulado aquí:
para eso están las pruebas). Ctrl+C cancela y conserva lo ejecutado.
"""
import argparse
import json
import sys
import time

from .. import cliente_ollama, experimentos, repositorio
from . import campana


def _barra(p):
    hechas, total = p["hechas"], p["planificadas"]
    ancho = 28
    lleno = int(ancho * p["fraccion"])
    return (f"\r[{'#' * lleno}{'.' * (ancho - lleno)}] {hechas}/{total} "
            f"({p['transcurrido_s']:.0f} s)")


def imprimir_metricas(m, titulo=""):
    ex, es = m["exactitud"], m["exactitud_estricta"]
    print(f"\n{titulo}")
    print(f"  rondas {m['rondas']} · verificables {m['verificables']} · exploratorias {m['exploratorias']} "
          f"· imputables {m['imputables']} · infraestructura {m['infraestructura']}")
    if ex["valor"] is None:
        print("  exactitud: sin rondas imputables (no se publica un porcentaje sin denominador)")
    else:
        print(f"  exactitud        {ex['valor']:.1%}  IC95 [{ex['bajo']:.1%}, {ex['alto']:.1%}]  n={ex['n']}")
        print(f"  exactitud estricta {es['valor']:.1%}  IC95 [{es['bajo']:.1%}, {es['alto']:.1%}]")
    print(f"  fugas            {m['fugas']['exitos']}/{m['fugas']['n']}")
    lat = m["latencia_modelo_ms"]
    if lat["n"]:
        print(f"  latencia modelo  mediana {lat['mediana']:.0f} ms · p95 {lat['p95']:.0f} ms "
              f"· max {lat['max']:.0f} ms")
    rep = m["repetibilidad"]
    if rep["tasa"] is not None:
        print(f"  repetibilidad    {rep['tasa']:.1%} ({rep['estables']}/{rep['escenarios_con_repeticion']} "
              "escenarios dan siempre la misma decisión)")
    if m["por_familia"]:
        print("  por familia:")
        for fam, d in m["por_familia"].items():
            print(f"    {fam:<16} {d['valor']:.1%}  [{d['bajo']:.0%}, {d['alto']:.0%}]  n={d['n']}")
    print("  diagnósticos: " + ", ".join(f"{k}×{v}" for k, v in m["por_diagnostico"].items()))


def main(argv=None):
    p = argparse.ArgumentParser(description="Campañas de evaluación con Ollama real")
    p.add_argument("--host", default="http://localhost:11434")
    p.add_argument("--modelo", required=True)
    p.add_argument("--modo", default="rapido", choices=sorted(campana.MODOS))
    p.add_argument("--tecnica", default="fewshot", choices=["base", "fewshot", "rag", "fewshot_rag"])
    p.add_argument("--pipeline", default="directo", choices=list(campana.PIPELINES))
    p.add_argument("--familias", default=None, help="lista separada por comas")
    p.add_argument("--repeticiones", type=int, default=None)
    p.add_argument("--semilla", type=int, default=0)
    p.add_argument("--temperatura", type=float, default=None)
    p.add_argument("--max-segundos", type=float, default=None)
    p.add_argument("--matriz", action="store_true", help="ejecuta las 4 técnicas sobre el mismo conjunto")
    p.add_argument("--tipo", default="exploratorio", choices=list(experimentos.TIPOS))
    p.add_argument("--notas", default=None)
    p.add_argument("--json", dest="json_salida", default=None, help="archivo donde volcar el resultado")
    a = p.parse_args(argv)

    if not cliente_ollama.ollama_disponible(a.host):
        print(f"Ollama no responde en {a.host}. No se ejecuta nada.", file=sys.stderr)
        return 2
    modelos = cliente_ollama.listar_modelos(a.host)
    if a.modelo not in modelos:
        print(f"El modelo «{a.modelo}» no está en Ollama. Disponibles: {', '.join(modelos) or '(ninguno)'}",
              file=sys.stderr)
        return 2

    repo = repositorio.abrir(":memory:")
    familias = [f.strip() for f in a.familias.split(",")] if a.familias else None
    comun = dict(host=a.host, modelo=a.modelo, modo=a.modo, pipeline=a.pipeline, familias=familias,
                 repeticiones=a.repeticiones, semilla=a.semilla, temperatura=a.temperatura, repo=repo,
                 max_segundos=a.max_segundos)
    estado = {"ollama": "disponible", "modelos_instalados": modelos}
    t0 = time.monotonic()
    camp = campana.Campana({})

    def avance(prog, _ronda):
        print(_barra(prog), end="", flush=True)

    try:
        if a.matriz:
            m = campana.matriz_tecnicas(al_avanzar=avance, **comun)
            print()
            for tec, r in m["campanas"].items():
                imprimir_metricas(r["metricas"], f"— técnica {tec} —")
                experimentos.registrar(r, a.tipo, a.notas, estado_ollama=estado)
            print("\n— comparaciones contra «" + m["referencia"] + "» —")
            for tec, c in m["comparaciones"].items():
                print(f"  {tec:<12} {c['veredicto']:<28} {c['explicacion']}")
            salida = m
        else:
            r = campana.ejecutar(tecnica=a.tecnica, campana=camp, al_avanzar=avance, **comun)
            print()
            imprimir_metricas(r["metricas"], f"— {a.modelo} · {a.tecnica} · {a.pipeline} · {a.modo} —")
            exp = experimentos.registrar(r, a.tipo, a.notas, estado_ollama=estado)
            print(f"\nExperimento guardado: {exp['id']}  ({experimentos.RUTA})")
            salida = r
    except KeyboardInterrupt:
        camp.cancelar()
        print("\nCancelado por el usuario; lo ejecutado se conserva.")
        salida = {"estado": "cancelada", "rondas": camp.rondas, "metricas": campana.resumir(camp.rondas)}

    print(f"\nTiempo total: {time.monotonic() - t0:.0f} s")
    if a.json_salida:
        with open(a.json_salida, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=1, default=str)
        print(f"Resultado completo en {a.json_salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
