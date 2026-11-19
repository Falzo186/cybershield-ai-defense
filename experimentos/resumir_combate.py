"""Análisis de las campañas de combate: métricas honestas con denominador, IC de Wilson, bootstrap por partida,
Fisher exacto con corrección de Holm, líneas base triviales y gráficas.

  python experimentos/resumir_combate.py --campana combate-v1 --salida docs/evaluacion

Reglas de este análisis (archivo 08 de la misión):
  * Las observaciones no válidas (INCONCLUSA / ERROR_TECNICO) NO entran en ninguna tasa de éxito; se cuentan aparte.
  * Cada proporción lleva su n. Con n pequeño se dice «evidencia exploratoria, no concluyente».
  * La unidad independiente es la PARTIDA. Las métricas por solicitud (VP/FP/FN/VN) se agregan con bootstrap de partidas.
  * Comparaciones múltiples: Holm sobre una familia de contrastes declarada (Fisher exacto bilateral).
  * Nada se reinterpreta: el resultado de cada partida es el que fijó el motor.
"""
import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.lab.evaluacion import metricas as M  # noqa: E402

VALIDOS = ("VICTORIA_ROJA", "VICTORIA_AZUL", "EMPATE", "EMPATE_DEGRADADO")
NIVEL_EXPLORATORIO = 30      # por debajo de este nº de partidas válidas por celda se avisa «exploratoria»
AZUL_MARINA, ROJO_OSCURO, GRIS = "#1b2f5e", "#8f2a35", "#8a9db8"


def leer(campana):
    f = RAIZ / "data" / "campanas" / campana / "observaciones.jsonl"
    ult = {}
    for linea in f.read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(linea)
            ult[o["id"]] = o          # la última observación de cada celda
        except (ValueError, KeyError):
            continue
    return list(ult.values())


# ── Estadística ────────────────────────────────────────────────────────────────────────────────────────
def _logcomb(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_bilateral(a, b, c, d):
    """p-valor exacto bilateral de Fisher para [[a, b], [c, d]] (a,b = éxitos/fracasos del grupo 1)."""
    n1, n2, k = a + b, c + d, a + c
    n = n1 + n2
    if n == 0 or n1 == 0 or n2 == 0:
        return None
    def p(x):
        return math.exp(_logcomb(n1, x) + _logcomb(n2, k - x) - _logcomb(n, k)) if 0 <= k - x <= n2 else 0.0
    p0 = p(a)
    return min(1.0, sum(p(x) for x in range(max(0, k - n2), min(n1, k) + 1) if p(x) <= p0 * (1 + 1e-9)))


def holm(pvalores):
    """Corrección de Holm-Bonferroni. -> p ajustados en el mismo orden (None se respeta)."""
    idx = [(i, p) for i, p in enumerate(pvalores) if p is not None]
    idx.sort(key=lambda x: x[1])
    m, out, previo = len(idx), [None] * len(pvalores), 0.0
    for r, (i, p) in enumerate(idx):
        previo = max(previo, min(1.0, (m - r) * p))
        out[i] = previo
    return out


def prop(exitos, n):
    w = M.wilson(exitos, n)
    return {"exitos": exitos, "n": n, "valor": w["valor"], "bajo": w["bajo"], "alto": w["alto"]}


def boot_cociente(grupos, rep=2000, semilla=0):
    """Cociente num/den agregado, con bootstrap de PARTIDAS. grupos = [(num, den)]."""
    r = M.bootstrap_agrupado([(e, n) for e, n in grupos], rep, semilla)
    return {"valor": r["valor"], "bajo": r["bajo"], "alto": r["alto"], "n": r["n"], "partidas": r["grupos"], "degenerado": r.get("degenerado", False)}


def fmt(p, pct=True):
    if p is None or p.get("valor") is None:
        return "sin datos"
    v = p["valor"] * 100 if pct else p["valor"]
    if p.get("bajo") is None:
        return f"{v:.1f} % (n={p.get('n')}; IC no estimable)"
    return f"{v:.1f} % [{p['bajo'] * 100:.1f}–{p['alto'] * 100:.1f}] (n={p['n']})"


# ── Resumen de un grupo de observaciones ───────────────────────────────────────────────────────────────
def resumen(obs):
    val = [o for o in obs if o["valida"]]
    inc = [o for o in obs if o["resultado"] == "INCONCLUSA"]
    err = [o for o in obs if o["resultado"] == "ERROR_TECNICO"]
    n = len(val)
    cnt = Counter(o["resultado"] for o in val)
    az = [o["azul_m"] for o in val]
    ro = [o["rojo_m"] for o in val]
    vp, fp, fn, vn = (sum((a.get(k) or 0) for a in az) for k in ("VP", "FP", "FN", "VN"))
    legit = [o["tasa_legitimas"] for o in val if o.get("tasa_legitimas") is not None]
    et = {k: sum((r.get(k) or 0) for r in ro) for k in ("intentos", "aceptadas", "efectos", "objetivos", "bloqueadas_por_capas", "repetidos", "vacios", "filtrados")}
    return {
        "n_total": len(obs), "n_validas": n, "n_inconclusas": len(inc), "n_error_tecnico": len(err),
        "pct_inconclusas": prop(len(inc) + len(err), len(obs)),
        "victoria_roja": prop(cnt["VICTORIA_ROJA"], n), "victoria_azul": prop(cnt["VICTORIA_AZUL"], n),
        "empate": prop(cnt["EMPATE"], n), "empate_degradado": prop(cnt["EMPATE_DEGRADADO"], n),
        "partidas_con_objetivo_rojo": prop(sum(1 for o in val if o["objetivos"] >= 1), n),
        "turnos_medios": (sum(o["turnos"] for o in val) / n) if n else None,
        "azul_prevencion_recall": boot_cociente([((o["azul_m"].get("VP") or 0), (o["azul_m"].get("VP") or 0) + (o["azul_m"].get("FN") or 0)) for o in val]),
        "azul_falsos_negativos_aprobo_maliciosa": prop(fn, vp + fn),
        "azul_falsos_positivos_rechazo_legitima": boot_cociente([((o["azul_m"].get("FP") or 0), (o["azul_m"].get("FP") or 0) + (o["azul_m"].get("VN") or 0)) for o in val]),
        "azul_precision": prop(vp, vp + fp),
        "azul_f1": (2 * vp / (2 * vp + fp + fn)) if (2 * vp + fp + fn) else None,
        "azul_legitimas_atendidas_media": (sum(legit) / len(legit)) if legit else None,
        "matriz": {"VP": vp, "FP": fp, "FN": fn, "VN": vn},
        "rojo_etapas": et,
        "rojo_conversion": {"aceptadas_por_intento": prop(et["aceptadas"], et["intentos"]), "efectos_por_aceptada": prop(et["efectos"], et["aceptadas"]),
                            "objetivos_por_efecto": prop(et["objetivos"], et["efectos"])},
        "rojo_engano_parcial_bloqueadas": et["bloqueadas_por_capas"],
        "decisiones": dict(sum((Counter(o.get("decisiones") or {}) for o in val), Counter())),
        "malformadas": sum((o.get("malformadas") or 0) for o in val),
        "llamadas_medias": (sum((o.get("llamadas") or 0) for o in val) / n) if n else None,
        "tokens_salida_medios": (sum((o.get("tokens_salida") or 0) for o in val) / n) if n else None,
        "duracion_media_s": (sum(o.get("duracion_s") or 0 for o in val) / n) if n else None,
        "aviso": ("evidencia exploratoria, no concluyente (n < %d partidas válidas)" % NIVEL_EXPLORATORIO) if n < NIVEL_EXPLORATORIO else None,
    }


def clave_celda(o):
    return (o["fase"], o["rojo"], o["azul"], o["config"])


# ── Informe ────────────────────────────────────────────────────────────────────────────────────────────
def construir(obs):
    celdas = defaultdict(list)
    for o in obs:
        celdas[clave_celda(o)].append(o)
    por_dif = defaultdict(list)
    por_fam = defaultdict(list)
    for o in obs:
        por_dif[clave_celda(o) + (o["dificultad"],)].append(o)
        por_fam[clave_celda(o) + (o["familia"],)].append(o)
    out = {"celdas": {" | ".join(k): resumen(v) for k, v in sorted(celdas.items())},
           "por_dificultad": {" | ".join(k): resumen(v) for k, v in sorted(por_dif.items())},
           "por_familia": {" | ".join(k): resumen(v) for k, v in sorted(por_fam.items())}}
    out["comparaciones"] = comparaciones(obs)
    out["totales"] = {"observaciones": len(obs), "validas": sum(1 for o in obs if o["valida"]), "invalidas": sum(1 for o in obs if not o["valida"]),
                      "por_resultado": dict(Counter(o["resultado"] for o in obs)), "por_fase": dict(Counter(o["fase"] for o in obs))}
    return out


def _tabla_prop(obs, extractor):
    val = [o for o in obs if o["valida"]]
    return sum(1 for o in val if extractor(o)), len(val)


def comparaciones(obs):
    """Familia declarada de contrastes (Fisher exacto bilateral sobre partidas válidas) con Holm.
    1) Espejo A vs espejo B (Azul): P(victoria Azul). 2) Cruzada vs espejo (misma pareja de modelos en el rol Azul).
    3) Cada variación vs su base (mismo modelo): P(victoria Azul) y P(Rojo logra ≥1 objetivo)."""
    por = defaultdict(list)
    for o in obs:
        por[clave_celda(o)].append(o)
    pruebas = []

    def anadir(nombre, a, b, metrica, f):
        ea, na = _tabla_prop(a, f)
        eb, nb = _tabla_prop(b, f)
        p = fisher_bilateral(ea, na - ea, eb, nb - eb) if na and nb else None
        pruebas.append({"contraste": nombre, "metrica": metrica, "a": {"exitos": ea, "n": na}, "b": {"exitos": eb, "n": nb}, "p_fisher": p})

    modelos = sorted({o["azul"] for o in obs if o["fase"] == "espejo"})
    esp = {m: por.get(("espejo", m, m, "base"), []) for m in modelos}
    for m1, m2 in [(a, b) for i, a in enumerate(modelos) for b in modelos[i + 1:]]:
        anadir(f"espejo {m1} vs espejo {m2}", esp[m1], esp[m2], "victoria_azul", lambda o: o["resultado"] == "VICTORIA_AZUL")
        anadir(f"espejo {m1} vs espejo {m2}", esp[m1], esp[m2], "rojo_logra_algun_objetivo", lambda o: o["objetivos"] >= 1)
    for k, v in por.items():
        if k[0] == "variaciones":
            base = esp.get(k[1], [])
            anadir(f"{k[1]}: variación «{k[3]}» vs base", base, v, "victoria_azul", lambda o: o["resultado"] == "VICTORIA_AZUL")
            anadir(f"{k[1]}: variación «{k[3]}» vs base", base, v, "rojo_logra_algun_objetivo", lambda o: o["objetivos"] >= 1)
    ajustados = holm([p["p_fisher"] for p in pruebas])
    for p, a in zip(pruebas, ajustados):
        p["p_holm"] = a
        p["significativo_holm_0_05"] = a is not None and a < 0.05
        p["aviso"] = "muestra pequeña: exploratorio" if min(p["a"]["n"], p["b"]["n"]) < NIVEL_EXPLORATORIO else None
    return {"metodo": "Fisher exacto bilateral por contraste; corrección de Holm-Bonferroni sobre toda la familia (conservadora; controla el error familiar)",
            "contrastes": pruebas}


def md(informe, obs):
    L = []
    t = informe["totales"]
    L.append("# Resumen estadístico de la campaña (generado por `experimentos/resumir_combate.py`)\n")
    L.append(f"Observaciones: **{t['observaciones']}** · válidas **{t['validas']}** · no válidas **{t['invalidas']}** "
             f"(inconclusas/errores técnicos, fuera de las tasas) · por resultado: {t['por_resultado']} · por fase: {t['por_fase']}\n")
    L.append("Cada porcentaje lleva su IC de Wilson al 95 % y su n. Las métricas por solicitud usan bootstrap de partidas. «Exploratoria» = menos de "
             f"{NIVEL_EXPLORATORIO} partidas válidas.\n")
    L.append("## Resultados por celda (fase | Rojo | Azul | configuración)\n")
    L.append("| Celda | n válidas (inconcl.) | Victoria Roja | Victoria Azul | Empate | Empate degradado | Azul prevención | Azul FP legítimas | Legítimas atendidas |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for k, r in informe["celdas"].items():
        L.append(f"| {k} | {r['n_validas']} ({r['n_inconclusas'] + r['n_error_tecnico']}) | {fmt(r['victoria_roja'])} | {fmt(r['victoria_azul'])} | {fmt(r['empate'])} | {fmt(r['empate_degradado'])} | "
                 f"{fmt(r['azul_prevencion_recall'])} | {fmt(r['azul_falsos_positivos_rechazo_legitima'])} | "
                 f"{'sin datos' if r['azul_legitimas_atendidas_media'] is None else '%.0f %%' % (r['azul_legitimas_atendidas_media'] * 100)} |")
    L.append("\n## Comparaciones (Fisher exacto + Holm)\n")
    L.append(informe["comparaciones"]["metodo"] + "\n")
    L.append("| Contraste | Métrica | A | B | p (Fisher) | p ajustado (Holm) | Significativo (0,05) | Aviso |")
    L.append("|---|---|---|---|---|---|---|---|")
    for p in informe["comparaciones"]["contrastes"]:
        f = lambda x: "—" if x is None else f"{x:.3f}"  # noqa: E731
        L.append(f"| {p['contraste']} | {p['metrica']} | {p['a']['exitos']}/{p['a']['n']} | {p['b']['exitos']}/{p['b']['n']} | {f(p['p_fisher'])} | {f(p['p_holm'])} | "
                 f"{'sí' if p['significativo_holm_0_05'] else 'no'} | {p['aviso'] or ''} |")
    return "\n".join(L) + "\n"


def graficas(informe, salida):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return []
    out = []
    col = {"victoria_roja": ROJO_OSCURO, "victoria_azul": AZUL_MARINA, "empate": "#b79a3a", "empate_degradado": GRIS}
    etiqueta = {"victoria_roja": "Victoria Roja", "victoria_azul": "Victoria Azul", "empate": "Empate", "empate_degradado": "Empate degradado"}
    celdas = {k: r for k, r in informe["celdas"].items() if r["n_validas"] > 0}
    if not celdas:
        return out
    fig, ax = plt.subplots(figsize=(11, max(3.2, 0.42 * len(celdas) + 1.2)), dpi=140)
    ys = list(range(len(celdas)))
    izq = [0.0] * len(celdas)
    for k in ("victoria_roja", "victoria_azul", "empate", "empate_degradado"):
        v = [r[k]["valor"] * 100 if r[k]["valor"] is not None else 0 for r in celdas.values()]
        ax.barh(ys, v, left=izq, color=col[k], label=etiqueta[k], edgecolor="white", linewidth=0.5)
        izq = [a + b for a, b in zip(izq, v)]
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{k}  (n={r['n_validas']})" for k, r in celdas.items()], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% de partidas válidas")
    ax.set_title("Resultados de los combates por celda (inconclusas excluidas)", fontsize=10)
    ax.legend(ncol=4, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.06))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    f = salida / "grafica_resultados_por_celda.png"
    fig.savefig(f, bbox_inches="tight")
    plt.close(fig)
    out.append(f.name)
    # Azul: prevención vs falsos positivos (precio de la prevención)
    llm = {k: r for k, r in celdas.items() if r["azul_prevencion_recall"]["valor"] is not None}
    if llm:
        fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=140)
        for k, r in llm.items():
            x = (r["azul_falsos_positivos_rechazo_legitima"]["valor"] or 0) * 100
            y = r["azul_prevencion_recall"]["valor"] * 100
            azul = k.split(" | ")[2]
            ax.scatter(x, y, s=40 + r["n_validas"], color=AZUL_MARINA if not azul.startswith("falso") else GRIS, alpha=0.8, edgecolor="white")
            ax.annotate(" | ".join(k.split(" | ")[:3])[:38], (x, y), fontsize=5.5, xytext=(3, 3), textcoords="offset points")
        ax.set_xlabel("Falsos positivos: % de solicitudes legítimas NO atendidas")
        ax.set_ylabel("Prevención: % de solicitudes maliciosas no aprobadas")
        ax.set_title("Azul: prevención frente a su costo en legítimas (azul = modelos 8B, gris = líneas base)", fontsize=9)
        ax.axhline(100, color=GRIS, lw=0.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        f = salida / "grafica_azul_prevencion_vs_falsos_positivos.png"
        fig.savefig(f)
        plt.close(fig)
        out.append(f.name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campana", default="combate-v1")
    ap.add_argument("--salida", default="docs/evaluacion")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    obs = leer(a.campana)
    salida = RAIZ / a.salida / a.campana
    salida.mkdir(parents=True, exist_ok=True)
    informe = construir(obs)
    (salida / "resumen.json").write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / "resumen.md").write_text(md(informe, obs), encoding="utf-8")
    with open(salida / "observaciones.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cols = ["id", "fase", "escenario", "familia", "dificultad", "rojo", "azul", "config", "rep", "resultado", "valida", "motivo_invalida", "turnos", "objetivos", "umbral",
                "tasa_legitimas", "duracion_s", "llamadas", "tokens_salida", "version_prompts"]
        w.writerow(cols + ["VP", "FP", "FN", "VN"])
        for o in obs:
            w.writerow([o.get(c) for c in cols] + [o["azul_m"].get(k) for k in ("VP", "FP", "FN", "VN")])
    g = graficas(informe, salida)
    print(f"{len(obs)} observaciones -> {salida}  ({', '.join(g) or 'sin gráficas'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
