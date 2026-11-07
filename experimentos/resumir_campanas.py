"""Resumen y comparación de las campañas grandes. Solo lee: no ejecuta ningún modelo.

Lee los JSONL de `data/campanas/` que dejó `campanas_grandes.py`, publica una tabla por condición y compara
cada condición contra la de referencia (`l32-fewshot`) con el mismo criterio que usa el laboratorio:
exactitud sobre rondas verificables e imputables, diferencia por bootstrap, intervalo del 95 % y tamaño
mínimo de muestra.

**Aviso de comparaciones múltiples, escrito antes de ver los resultados.** Hay cinco comparaciones contra la
misma referencia. Cada intervalo es del 95 % por separado, así que la probabilidad de que *alguna* de las
cinco salga «mejora» o «empeora» por azar es mayor del 5 %: con cinco comparaciones independientes ronda el
23 %. Un solo veredicto de «mejora» entre cinco no es, por sí mismo, una conclusión firme. Esto queda dicho
aquí, en el código, antes de que exista ningún número, para que no se pueda ajustar el criterio después.

Una condición incompleta se resume como incompleta y se marca `parcial`. No se extrapola.

Uso:
    python experimentos/resumir_campanas.py
    python experimentos/resumir_campanas.py --json       # solo el volcado, sin tabla
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.lab.evaluacion import lotes, metricas                       # noqa: E402
from experimentos.campanas_grandes import CONDICIONES, PLAN, id_de   # noqa: E402

REFERENCIA = "l32-fewshot"
SALIDA = RAIZ / "data" / "campanas_grandes.json"
# Aviso fijado antes de medir (ver el encabezado del módulo).
NOTA_MULTIPLES = ("Cinco comparaciones contra la misma referencia, cada una con un intervalo del 95 % "
                  "propio: la probabilidad de que alguna salga significativa por azar ronda el 23 %. "
                  "Un único veredicto de mejora o empeora entre los cinco no es concluyente por sí solo.")


def pct(w):
    """Un Wilson como texto, siempre con su denominador. None es None, no 0."""
    if w is None or w.get("valor") is None:
        return f"-- (n={0 if w is None else w.get('n', 0)})"
    return (f"{w['valor'] * 100:5.1f}% [{w['bajo'] * 100:4.1f}-{w['alto'] * 100:5.1f}] "
            f"n={w['n']}")


def cargar():
    """-> {nombre: resultado | None}. Una condición sin empezar es None, no un cero."""
    out = {}
    for nombre, _, _ in CONDICIONES:
        try:
            out[nombre] = lotes.resultado(id_de(nombre))
        except lotes.ErrorLote:
            out[nombre] = None
    return out


def modo_rag(res):
    """Cómo se recuperó de verdad en esta condición. Importa: sin modelo de embeddings instalado, RAG cae a
    BM25 (léxico), y eso no es lo mismo que RAG vectorial."""
    modos = {}
    for r in res["rondas"]:
        info = r.get("rag")
        if info:
            modos[info.get("modo")] = modos.get(info.get("modo"), 0) + 1
    return modos or None


def linea_base_trivial(res):
    """Qué sacaría en esta misma campaña un defensor que IGNORA la entrada y contesta siempre lo mismo.

    Esto no es un adorno. La exactitud oficial admite varias decisiones por expectativa: tanto «autorizar»
    como «contener» se cumplen rechazando. Un modelo que rechaza todo acierta, por tanto, en todas las
    rondas cuya referencia no sea «permitir», sin haber entendido nada. Publicar la cifra de ese defensor
    constante al lado de la del modelo es la única forma de saber si el modelo aporta algo: si no la supera,
    su porcentaje no mide capacidad, mide la composición del conjunto.

    -> {decision: {exactitud, estricta}} sobre las mismas rondas verificables e imputables.
    """
    from src.lab.evaluacion import escenarios
    rs = [r for r in res["rondas"] if r.get("verificable") and r.get("imputable")]
    if not rs:
        return None
    out = {}
    for const in ("RECHAZAR", "MARCAR_COMO_RIESGO", "SOLICITAR_AUTORIZACION", "PERMITIR"):
        ac = sum(1 for r in rs if escenarios.acierta(r["esperado"], const))
        es = sum(1 for r in rs if escenarios.acierta(r["esperado"], const, True))
        out[const] = {"exactitud": metricas.wilson(ac, len(rs)),
                      "exactitud_estricta": metricas.wilson(es, len(rs))}
    mejor = max(out, key=lambda k: out[k]["exactitud"]["valor"] or 0.0)
    return {"por_decision": out, "mejor_constante": mejor,
            "exactitud_a_batir": out[mejor]["exactitud"],
            "composicion": {e: sum(1 for r in rs if r["esperado"] == e)
                            for e in sorted({r["esperado"] for r in rs})}}


def decisiones_emitidas(res):
    """Qué decisiones llegó a emitir el modelo. Una decisión que nunca emite es una capacidad que no tiene,
    y eso no se ve en ningún porcentaje."""
    cuenta = {}
    for r in res["rondas"]:
        cuenta[r.get("decision")] = cuenta.get(r.get("decision"), 0) + 1
    return dict(sorted(cuenta.items(), key=lambda kv: (-kv[1], str(kv[0]))))


def supera_linea_base(exactitud, base):
    """¿El modelo supera de verdad al defensor constante? Se exige que el intervalo del 95 % del modelo
    quede por encima del valor de la constante. Criterio fijado antes de ver los resultados."""
    if not base or exactitud.get("valor") is None or exactitud["bajo"] is None:
        return None
    umbral = base["exactitud_a_batir"]["valor"]
    if umbral is None:
        return None
    if exactitud["bajo"] > umbral:
        return "supera"
    if exactitud["alto"] < umbral:
        return "por_debajo"
    return "indistinguible"


def comparaciones(datos):
    ref = datos.get(REFERENCIA)
    if not ref or not ref["metricas"]["exactitud"]["n"]:
        return {}, "Sin la condición de referencia no hay nada que comparar."
    ea = ref["metricas"]["exactitud"]
    out = {}
    for nombre, _, _ in CONDICIONES:
        if nombre == REFERENCIA or not datos.get(nombre):
            continue
        eb = datos[nombre]["metricas"]["exactitud"]
        out[nombre] = metricas.comparar(REFERENCIA, ea["exitos"], ea["n"], nombre, eb["exitos"], eb["n"])
    return out, None


def main(argv):
    datos = cargar()
    cmps, aviso_ref = comparaciones(datos)

    volcado = {"plan": PLAN, "referencia": REFERENCIA, "nota_comparaciones_multiples": NOTA_MULTIPLES,
               "condiciones": {}, "comparaciones": cmps}
    for nombre, cfg, descripcion in CONDICIONES:
        res = datos.get(nombre)
        if res is None:
            volcado["condiciones"][nombre] = {"estado": "sin_empezar", "config": cfg,
                                              "descripcion": descripcion}
            continue
        m = res["metricas"]
        volcado["condiciones"][nombre] = {
            "estado": res["estado"], "parcial": res["parcial"], "descripcion": descripcion,
            "config": {k: res["config"].get(k) for k in
                       ("modelo", "tecnica", "pipeline", "modo", "repeticiones", "semilla")},
            "hechas": res["hechas"], "planificadas": res["planificadas"], "lotes": res["lotes"],
            "duracion_s": round(res["duracion_s"], 1),
            "exactitud": m["exactitud"], "exactitud_estricta": m["exactitud_estricta"],
            "fugas": m["fugas"], "imputables": m["imputables"], "infraestructura": m["infraestructura"],
            "repetibilidad": m["repetibilidad"], "latencia_modelo_ms": m["latencia_modelo_ms"],
            "tokens_entrada": m["tokens_entrada"], "tokens_salida": m["tokens_salida"],
            "recuperacion_ms": m["recuperacion_ms"], "modo_rag": modo_rag(res),
            "por_familia": m["por_familia"], "por_diagnostico": m["por_diagnostico"],
            "decisiones_emitidas": decisiones_emitidas(res),
            "linea_base_trivial": linea_base_trivial(res),
            "supera_linea_base": supera_linea_base(m["exactitud"], linea_base_trivial(res)),
        }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(volcado, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if "--json" in argv:
        print(f"Escrito: {SALIDA}")
        return 0

    print("=" * 108)
    print("CAMPAÑAS GRANDES · exactitud sobre rondas verificables e imputables al modelo")
    print(f"Plan idéntico en todas: {PLAN}")
    print("=" * 108)
    print(f"\n{'condición':<17} {'hechas':>7}  {'exactitud oficial':<28} {'estricta':<28} {'repet.':>7}")
    for nombre, _, _ in CONDICIONES:
        d = volcado["condiciones"][nombre]
        if d["estado"] == "sin_empezar":
            print(f"{nombre:<17} {'sin empezar':>7}")
            continue
        rep = d["repetibilidad"]["tasa"]
        print(f"{nombre:<17} {d['hechas']:>3}/{d['planificadas']:<3}  {pct(d['exactitud']):<28} "
              f"{pct(d['exactitud_estricta']):<28} "
              f"{'--' if rep is None else f'{rep * 100:5.1f}%':>7}"
              f"{'  PARCIAL' if d.get('parcial') else ''}")

    print(f"\n{'condición':<17} {'fugas':<24} {'infra':>6} {'lat. media':>11} {'tok. ent.':>10} "
          f"{'recuperación':>13}")
    for nombre, _, _ in CONDICIONES:
        d = volcado["condiciones"][nombre]
        if d["estado"] == "sin_empezar":
            continue
        lat, te, rc = d["latencia_modelo_ms"], d["tokens_entrada"], d["recuperacion_ms"]
        f = lambda x, k="media": "--" if not x or x.get(k) is None else f"{x[k]:.0f}"  # noqa: E731
        print(f"{nombre:<17} {pct(d['fugas']):<24} {d['infraestructura']:>6} {f(lat) + ' ms':>11} "
              f"{f(te):>10} {(f(rc) + ' ms') if rc and rc.get('media') is not None else '--':>13}")

    print("\n── Contra el defensor constante (el que ignora la entrada y contesta siempre lo mismo)")
    ref = volcado["condiciones"].get(REFERENCIA, {})
    lb = ref.get("linea_base_trivial")
    if lb:
        print(f"  Composición de las {sum(lb['composicion'].values())} rondas oficiales: {lb['composicion']}")
        for const, v in lb["por_decision"].items():
            marca = "  <- la mejor constante" if const == lb["mejor_constante"] else ""
            print(f"  siempre {const:<24} {pct(v['exactitud'])}  estricta {pct(v['exactitud_estricta'])}"
                  f"{marca}")
        print(f"\n  {'condición':<17} {'exactitud':<28} {'a batir':>9}  veredicto")
        for nombre, _, _ in CONDICIONES:
            d = volcado["condiciones"][nombre]
            if d["estado"] == "sin_empezar":
                continue
            umbral = (d.get("linea_base_trivial") or {}).get("exactitud_a_batir", {}).get("valor")
            print(f"  {nombre:<17} {pct(d['exactitud']):<28} "
                  f"{'--' if umbral is None else f'{umbral * 100:5.1f}%':>9}  "
                  f"{d.get('supera_linea_base') or '--'}")

    print("\n── Decisiones que el modelo llegó a emitir")
    for nombre, _, _ in CONDICIONES:
        d = volcado["condiciones"][nombre]
        if d["estado"] == "sin_empezar":
            continue
        print(f"  {nombre:<17} {d['decisiones_emitidas']}")

    print("\n── Modo de recuperación usado de verdad")
    for nombre, _, _ in CONDICIONES:
        d = volcado["condiciones"][nombre]
        if d.get("modo_rag"):
            print(f"  {nombre:<17} {d['modo_rag']}")

    print(f"\n── Comparación contra la referencia ({REFERENCIA})")
    if aviso_ref:
        print(f"  {aviso_ref}")
    for nombre, c in cmps.items():
        print(f"  {nombre:<17} dif {c['diferencia']:+.3f} "
              f"IC95 [{c['intervalo']['bajo']:+.3f}, {c['intervalo']['alto']:+.3f}] · "
              f"**{c['veredicto']}**")
        print(f"  {'':<17} {c['explicacion']}")
    print(f"\n  AVISO: {NOTA_MULTIPLES}")

    print("\n── Por familia, en cada condición (aciertos/n)")
    familias = sorted({f for d in volcado["condiciones"].values() for f in (d.get("por_familia") or {})})
    nombres = [n for n, _, _ in CONDICIONES if volcado["condiciones"][n]["estado"] != "sin_empezar"]
    print(f"{'familia':<16}" + "".join(f"{n:>18}" for n in nombres))
    for fam in familias:
        fila = f"{fam:<16}"
        for n in nombres:
            pf = (volcado["condiciones"][n].get("por_familia") or {}).get(fam)
            celda = "--" if not pf else f"{pf['aciertos']}/{pf['n']} ({pf['valor'] * 100:.0f}%)"
            fila += f"{celda:>18}"
        print(fila)

    print(f"\nEscrito: {SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
