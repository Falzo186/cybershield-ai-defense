import argparse
import json
from pathlib import Path

import config
import db
from batalla import ejecutar_batalla

RUTA_JSONL = Path(__file__).resolve().parent.parent / "data" / "batallas.jsonl"


def guardar_jsonl(res):
    RUTA_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")


def imprimir_tablas():
    print("\nNivel | Batallas | Victorias atq | Tasa % | Rondas prom | Fugas internas")
    for f in db.resumen_por_nivel():
        print(" | ".join(str(x) for x in f))
    print("\nNivel | Técnica ganadora | Victorias")
    for f in db.victorias_por_tecnica():
        print(" | ".join(str(x) for x in f))


def main():
    p = argparse.ArgumentParser(description="Simulador de red teaming de LLMs")
    p.add_argument("--rondas", type=int, default=config.MAX_RONDAS)
    p.add_argument("--modelo-def", default=config.MODEL_DEFENSOR)
    p.add_argument("--modelo-atq", default=config.MODEL_ATACANTE)
    p.add_argument("--nivel", type=int, choices=[0, 1, 2, 3, 4], default=1)
    p.add_argument("--campana", type=int, metavar="N", help="N batallas por nivel")
    p.add_argument("--niveles", default="0,1,2,3,4")
    p.add_argument("--solo-resumen", action="store_true")
    a = p.parse_args()

    if a.solo_resumen:
        imprimir_tablas()
        return

    if a.campana:
        niveles = [int(x) for x in a.niveles.split(",")]
        for nivel in niveles:
            for i in range(1, a.campana + 1):
                res = ejecutar_batalla(nivel=nivel, rondas=a.rondas,
                                       modelo_def=a.modelo_def, modelo_atq=a.modelo_atq)
                db.guardar_batalla(res)
                guardar_jsonl(res)
                print(f"N{nivel} #{i}: {'GANA ATQ' if res['gano_atacante'] else 'resiste'} "
                      f"({res['rondas_usadas']} rondas)")
        imprimir_tablas()
        return

    res = ejecutar_batalla(nivel=a.nivel, rondas=a.rondas,
                           modelo_def=a.modelo_def, modelo_atq=a.modelo_atq)
    for i in res["intercambios"]:
        print(f"[R{i['ronda']}] ATQ: {i['ataque'][:150]}")
        print(f"      DEF: {i['respuesta'][:150]}")
    print(f"Resultado: {'GANÓ EL ATACANTE' if res['gano_atacante'] else 'DEFENSOR RESISTIÓ'} "
          f"({res['rondas_usadas']} rondas)")
    db.guardar_batalla(res)
    guardar_jsonl(res)


if __name__ == "__main__":
    main()
