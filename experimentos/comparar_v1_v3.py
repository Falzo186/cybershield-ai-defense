"""Compara la campaña combate-v1 (prompts v2) con combate-v2 (prompts v3), pareja por pareja, con el MISMO analizador estadístico
(`resumir_combate.py`: IC de Wilson, bootstrap por partida, Fisher exacto + Holm). No modifica ninguna de las dos campañas.

  python experimentos/comparar_v1_v3.py            -> docs/evaluacion/combate-v2/comparacion_v1_v3.{md,json}

Las celdas se emparejan por (fase, rol Rojo, rol Azul) quitando el sufijo «@v3». Solo se comparan las fases espejo y cruzada, en
configuración «base». Ojo: v1 tiene 3 repeticiones por escenario y v3 hasta 8 (las repeticiones 1-3 usan las mismas semillas): la
comparación NO es por parejas de partidas, sino de dos muestras independientes de partidas.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "experimentos"))
import resumir_combate as R  # noqa: E402

SALIDA = RAIZ / "docs" / "evaluacion" / "combate-v2"


def sin_version(s):
    return s.split("@")[0]


def agrupar(obs):
    g = defaultdict(list)
    for o in obs:
        if o["fase"] in ("espejo", "cruzada") and o["config"] == "base" and not o["rojo"].startswith("falso") and not o["azul"].startswith("falso"):
            g[(o["fase"], sin_version(o["rojo"]), sin_version(o["azul"]))].append(o)
    return g


def fila(obs):
    r = R.resumen(obs)
    d = Counter()
    for o in obs:
        if o["valida"]:
            d.update(o.get("decisiones") or {})
    tot = sum(d.values()) or 1
    return {"n_total": r["n_total"], "n_validas": r["n_validas"], "n_invalidas": r["n_total"] - r["n_validas"],
            "victoria_roja": r["victoria_roja"], "victoria_azul": r["victoria_azul"], "empate": r["empate"], "empate_degradado": r["empate_degradado"],
            "rojo_algun_objetivo": r["partidas_con_objetivo_rojo"], "azul_fp_legitimas": r["azul_falsos_positivos_rechazo_legitima"],
            "azul_fn_maliciosas": r["azul_falsos_negativos_aprobo_maliciosa"], "legitimas_atendidas_media": r["azul_legitimas_atendidas_media"],
            "decisiones": dict(d), "pct_escalar": d["ESCALAR"] / tot, "pct_solicitar": d["SOLICITAR_AUTORIZACION"] / tot, "pct_rechazar": d["RECHAZAR"] / tot,
            "pct_aprobar": d["APROBAR"] / tot, "malformadas": r["malformadas"], "duracion_media_s": r["duracion_media_s"], "obs": obs}


def main():
    v1 = agrupar(R.leer("combate-v1"))
    v3 = agrupar(R.leer("combate-v2"))
    claves = sorted(set(v1) | set(v3))
    filas, pruebas = [], []
    for k in claves:
        a, b = v1.get(k, []), v3.get(k, [])
        fa, fb = fila(a), fila(b)
        filas.append((k, fa, fb))
        for metrica, f in (("victoria_azul", lambda o: o["resultado"] == "VICTORIA_AZUL"), ("empate_degradado", lambda o: o["resultado"] == "EMPATE_DEGRADADO"),
                           ("rojo_algun_objetivo", lambda o: o["objetivos"] >= 1)):
            ea, na = R._tabla_prop(a, f)
            eb, nb = R._tabla_prop(b, f)
            p = R.fisher_bilateral(ea, na - ea, eb, nb - eb) if na and nb else None
            pruebas.append({"pareja": " | ".join(k), "metrica": metrica, "v1": [ea, na], "v3": [eb, nb], "p_fisher": p})
    ad = R.holm([p["p_fisher"] for p in pruebas])
    for p, x in zip(pruebas, ad):
        p["p_holm"] = x
        p["significativo_holm_0_05"] = x is not None and x < 0.05
    SALIDA.mkdir(parents=True, exist_ok=True)
    out = {"nota": "v1 = prompts v2 (campaña combate-v1); v3 = prompts v3 (campaña combate-v2). Dos muestras independientes; Fisher bilateral + Holm sobre toda la familia.",
           "parejas": {" | ".join(k): {"v1": {x: y for x, y in fa.items() if x != "obs"}, "v3": {x: y for x, y in fb.items() if x != "obs"}} for k, fa, fb in filas},
           "contrastes": pruebas}
    (SALIDA / "comparacion_v1_v3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    L = ["# Comparación v1 (prompts v2) vs v3 (prompts v3), por pareja — generada por `experimentos/comparar_v1_v3.py`\n",
         "Cada porcentaje lleva IC de Wilson al 95 % y su n. «n válidas» excluye INCONCLUSA y ERROR_TECNICO.\n",
         "| Pareja (fase \\| Rojo \\| Azul) | Versión | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado | Rojo logra ≥1 objetivo | Legítimas atendidas | ESCALAR % | SOLICITAR % | RECHAZAR % | APROBAR % |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, fa, fb in filas:
        for et, f in (("v2", fa), ("v3", fb)):
            leg = "—" if f["legitimas_atendidas_media"] is None else f"{f['legitimas_atendidas_media'] * 100:.0f} %"
            L.append(f"| {' \\| '.join(k)} | {et} | {f['n_validas']} ({f['n_invalidas']}) | {R.fmt(f['victoria_roja'])} | {R.fmt(f['victoria_azul'])} | {R.fmt(f['empate_degradado'])} | "
                     f"{R.fmt(f['rojo_algun_objetivo'])} | {leg} | {f['pct_escalar'] * 100:.0f} % | {f['pct_solicitar'] * 100:.0f} % | {f['pct_rechazar'] * 100:.0f} % | {f['pct_aprobar'] * 100:.0f} % |")
    L += ["\n## Contrastes v1 vs v3 (Fisher exacto bilateral + Holm)\n", "| Pareja | Métrica | v1 (éxitos/n) | v3 (éxitos/n) | p | p Holm | Significativo (0,05) |", "|---|---|---|---|---|---|---|"]
    for p in pruebas:
        f = lambda x: "—" if x is None else f"{x:.3f}"  # noqa: E731
        L.append(f"| {p['pareja'].replace('|', '\\|')} | {p['metrica']} | {p['v1'][0]}/{p['v1'][1]} | {p['v3'][0]}/{p['v3'][1]} | {f(p['p_fisher'])} | {f(p['p_holm'])} | {'sí' if p['significativo_holm_0_05'] else 'no'} |")
    (SALIDA / "comparacion_v1_v3.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
