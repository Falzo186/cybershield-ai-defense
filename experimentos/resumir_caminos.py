"""Análisis de la campaña de Caminos con el MISMO instrumental estadístico que el combate libre: IC de Wilson (Wilson 95 %), bootstrap por partida,
Fisher exacto bilateral y corrección de Holm. Lee data/campanas/<campana>/observaciones.jsonl y escribe docs/evaluacion/<campana>/.

  python experimentos/resumir_caminos.py --campana caminos-v1

Solo cuentan las partidas VÁLIDAS (victoria Roja, victoria Azul o empate degradado); las inconclusas y los errores técnicos se reportan aparte.
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "experimentos"))
import resumir_combate as R  # noqa: E402

NIVEL_EXPLORATORIO = 30
IA = ("qwen3:8b", "llama3.1:8b")


def leer(campana):
    ult = {}
    for f in sorted((RAIZ / "data" / "campanas" / campana).glob("observaciones*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(l)
                ult[o["id"]] = o
            except (ValueError, KeyError):
                continue
    return list(ult.values())


def clave(o, con_dif=True):
    return (o["modo"], o["rojo"], o["azul"]) + ((o.get("dificultad") or "-",) if con_dif else ())


def etiqueta(k):
    return " | ".join(str(x) for x in k)


def resumen(obs):
    val = [o for o in obs if o["valida"]]
    n = len(val)
    c = Counter(o["resultado"] for o in val)
    hojas = Counter(o["hoja"] for o in val if o.get("hoja"))
    return {"n_total": len(obs), "n_validas": n, "n_inconclusas": sum(o["resultado"] == "INCONCLUSA" for o in obs), "n_error_tecnico": sum(o["resultado"] == "ERROR_TECNICO" for o in obs),
            "victoria_roja": R.prop(c["VICTORIA_ROJA"], n), "victoria_azul": R.prop(c["VICTORIA_AZUL"], n), "empate_degradado": R.prop(c["EMPATE_DEGRADADO"], n),
            "hojas": dict(hojas.most_common()), "reversiones": sum(1 for o in val if o.get("reversion")), "giros": sum(1 for o in val if o.get("giro")),
            "tipos": dict(Counter(o.get("tipo") for o in obs)), "turnos_medios": (sum(o["turnos"] or 0 for o in val) / n) if n else None,
            "duracion_media_s": (sum(o.get("duracion_s") or 0 for o in val) / n) if n else None,
            "aviso": ("evidencia exploratoria, no concluyente (n < %d partidas válidas)" % NIVEL_EXPLORATORIO) if n < NIVEL_EXPLORATORIO else None}


def decisiones_azul(obs):
    """Para cada decisión crítica del Azul (nodo:opción), cuántas veces se tomó: indica qué decisiones inclinaron el resultado."""
    por_nodo = defaultdict(Counter)
    for o in obs:
        for k, v in (o.get("decisiones_azul") or {}).items():
            nodo, _, op = k.partition(":") if ":" in k else ("auto", "", k)
            por_nodo[nodo][op] += v
    return {n: dict(c) for n, c in sorted(por_nodo.items())}


def tasa(obs, f):
    val = [o for o in obs if o["valida"]]
    return sum(1 for o in val if f(o)), len(val)


def contrastes(obs):
    por = defaultdict(list)
    for o in obs:
        por[clave(o, False)].append(o)
    pruebas = []

    def anadir(nombre, a, b, metrica, f):
        ea, na = tasa(a, f)
        eb, nb = tasa(b, f)
        p = R.fisher_bilateral(ea, na - ea, eb, nb - eb) if na and nb else None
        pruebas.append({"contraste": nombre, "metrica": metrica, "a": {"exitos": ea, "n": na}, "b": {"exitos": eb, "n": nb}, "p_fisher": p})

    roja = lambda o: o["resultado"] == "VICTORIA_ROJA"  # noqa: E731
    azul = lambda o: o["resultado"] == "VICTORIA_AZUL"  # noqa: E731
    for modo in ("grafo", "auto"):
        azules = sorted({k[2] for k in por if k[0] == modo})
        rojos = sorted({k[1] for k in por if k[0] == modo})
        for a in azules:                  # ¿difiere el Rojo qwen del Rojo llama frente al mismo Azul?
            x, y = por.get((modo, IA[0], a), []), por.get((modo, IA[1], a), [])
            if x and y:
                anadir(f"[{modo}] Rojo {IA[0]} vs Rojo {IA[1]} · Azul {a}", x, y, "victoria_roja", roja)
        for r in rojos:                   # ¿difiere el Azul qwen del Azul llama frente al mismo Rojo?
            x, y = por.get((modo, r, IA[0]), []), por.get((modo, r, IA[1]), [])
            if x and y:
                anadir(f"[{modo}] Azul {IA[0]} vs Azul {IA[1]} · Rojo {r}", x, y, "victoria_azul", azul)
        for a in ("aprobar", "aleatorio", "registro"):          # ¿un Rojo 8B hace más que el aleatorio contra el mismo Azul?
            alea = por.get((modo, "aleatorio", a), [])
            for m in IA:
                x = por.get((modo, m, a), [])
                if x and alea:
                    anadir(f"[{modo}] Rojo {m} vs Rojo aleatorio · Azul {a}", x, alea, "victoria_roja", roja)
        for m in IA:                      # ¿espejo vs cruzada con el mismo Azul?
            esp, cru = por.get((modo, m, m), []), por.get((modo, IA[1] if m == IA[0] else IA[0], m), [])
            if esp and cru:
                anadir(f"[{modo}] Azul {m}: Rojo espejo vs Rojo cruzado", esp, cru, "victoria_roja", roja)
    aj = R.holm([p["p_fisher"] for p in pruebas])
    for p, a in zip(pruebas, aj):
        p["p_holm"] = a
        p["significativo_holm_0_05"] = a is not None and a < 0.05
        p["aviso"] = "muestra pequeña: exploratorio" if min(p["a"]["n"], p["b"]["n"]) < NIVEL_EXPLORATORIO else None
    return {"metodo": "Fisher exacto bilateral por contraste; corrección de Holm-Bonferroni sobre toda la familia", "contrastes": pruebas}


def md(inf, obs):
    L = ["# Resumen estadístico de la campaña de Caminos (generado por `experimentos/resumir_caminos.py`)\n",
         f"Observaciones: **{inf['totales']['observaciones']}** · válidas **{inf['totales']['validas']}** · no válidas **{inf['totales']['invalidas']}** · por resultado: {inf['totales']['por_resultado']} · por tipo: {inf['totales']['por_tipo']}\n",
         "Cada porcentaje lleva IC de Wilson al 95 % y su n. «Exploratoria» = menos de 30 partidas válidas. `tipo`: CAMINOS_GUION (guiones/líneas base) vs CAMINOS_IA (algún lado es un 8B).\n",
         "## Resultados por celda (modo | Rojo | Azul | dificultad)\n",
         "| Celda | Tipo | n válidas (inconcl.) | Victoria Roja | Victoria Azul | Empate degradado | Hojas más frecuentes |", "|---|---|---|---|---|---|---|"]
    for k, r in inf["celdas"].items():
        top = ", ".join(f"{h}×{n}" for h, n in list(r["hojas"].items())[:3]) or "—"
        L.append(f"| {k} | {','.join(t for t in r['tipos'] if t)} | {r['n_validas']} ({r['n_inconclusas'] + r['n_error_tecnico']}) | {R.fmt(r['victoria_roja'])} | {R.fmt(r['victoria_azul'])} | {R.fmt(r['empate_degradado'])} | {top} |")
    L += ["\n## Comparaciones (Fisher exacto + Holm)\n", inf["contrastes"]["metodo"] + "\n", "| Contraste | Métrica | A | B | p (Fisher) | p Holm | Signif. | Aviso |", "|---|---|---|---|---|---|---|---|"]
    for p in inf["contrastes"]["contrastes"]:
        f = lambda x: "—" if x is None else f"{x:.3f}"  # noqa: E731
        L.append(f"| {p['contraste']} | {p['metrica']} | {p['a']['exitos']}/{p['a']['n']} | {p['b']['exitos']}/{p['b']['n']} | {f(p['p_fisher'])} | {f(p['p_holm'])} | {'sí' if p['significativo_holm_0_05'] else 'no'} | {p['aviso'] or ''} |")
    L.append("\n## Decisiones del Azul por nodo (modo grafo, solo Azul 8B)\n")
    for m in IA:
        d = decisiones_azul([o for o in obs if o["modo"] == "grafo" and o["azul"] == m and o["valida"]])
        L.append(f"**Azul {m}** — " + "; ".join(f"{n}: " + ", ".join(f"{op}×{c}" for op, c in ops.items()) for n, ops in d.items()))
        L.append("")
    return "\n".join(L) + "\n"


def graficas(inf, salida):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return []
    celdas = [(k, r) for k, r in inf["celdas"].items() if r["n_validas"] and any(m in k for m in IA) and k.endswith("| -") is False or ("auto" in k and any(m in k for m in IA) and r["n_validas"])]
    # una barra por (modo, rojo, azul) agregando dificultades
    agg = defaultdict(lambda: Counter())
    for o in inf["_obs"]:
        if o["valida"] and (o["rojo"] in IA or o["azul"] in IA):
            agg[(o["modo"], o["rojo"], o["azul"])][o["resultado"]] += 1
    claves = sorted(agg)
    fig, ax = plt.subplots(figsize=(11, max(4, 0.32 * len(claves) + 1.5)))
    y = range(len(claves))
    izq = [0] * len(claves)
    for res, col in (("VICTORIA_ROJA", "#8f2a35"), ("VICTORIA_AZUL", "#1b2f5e"), ("EMPATE_DEGRADADO", "#8a9db8")):
        v = [agg[k][res] / max(1, sum(agg[k].values())) * 100 for k in claves]
        ax.barh(list(y), v, left=izq, color=col, label=res.replace("_", " ").title())
        izq = [a + b for a, b in zip(izq, v)]
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{k[0]}: {k[1]} vs {k[2]}" for k in claves], fontsize=7)
    ax.set_xlabel("% de partidas válidas")
    ax.set_title("Resultados por pareja (modo Caminos; solo celdas con un 8B)")
    ax.legend(loc="lower right", fontsize=7)
    fig.tight_layout()
    ruta = salida / "grafica_resultados_caminos.png"
    fig.savefig(ruta, dpi=140)
    plt.close(fig)
    return [ruta.name]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campana", default="caminos-v1")
    ap.add_argument("--salida", default="docs/evaluacion")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    obs = leer(a.campana)
    celdas = defaultdict(list)
    for o in obs:
        celdas[clave(o)].append(o)
    inf = {"celdas": {etiqueta(k): resumen(v) for k, v in sorted(celdas.items())},
           "totales": {"observaciones": len(obs), "validas": sum(o["valida"] for o in obs), "invalidas": sum(not o["valida"] for o in obs), "por_resultado": dict(Counter(o["resultado"] for o in obs)),
                       "por_tipo": dict(Counter(o.get("tipo") for o in obs)), "por_fase": dict(Counter(o["fase"] for o in obs))},
           "contrastes": contrastes(obs), "_obs": obs}
    carp = RAIZ / a.salida / a.campana
    carp.mkdir(parents=True, exist_ok=True)
    graf = graficas(inf, carp)
    texto = md(inf, obs)
    del inf["_obs"]
    inf["decisiones_azul_8b"] = {m: decisiones_azul([o for o in obs if o["modo"] == "grafo" and o["azul"] == m and o["valida"]]) for m in IA}
    (carp / "resumen.json").write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding="utf-8")
    (carp / "resumen.md").write_text(texto, encoding="utf-8")
    campos = ["id", "fase", "modo", "dificultad", "rojo", "azul", "semilla", "resultado", "hoja", "tipo", "valida", "turnos", "tasa_legitimas", "reversion", "giro", "duracion_s", "version_prompts"]
    with open(carp / "observaciones.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(campos)
        for o in obs:
            w.writerow([o.get(c) for c in campos])
    print(f"{len(obs)} observaciones -> {carp} ({', '.join(graf)})")


if __name__ == "__main__":
    main()
