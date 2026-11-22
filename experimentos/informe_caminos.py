"""Genera docs/evaluacion/INFORME_CAMINOS.md a partir de las observaciones de la campaña (todas las cifras salen de los datos, no de texto escrito a mano).
Uso: python experimentos/informe_caminos.py --campana caminos-v1
La interpretación va en secciones cortas que citan esas cifras; las limitaciones son fijas."""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "experimentos"))
import resumir_caminos as RC  # noqa: E402
import resumir_combate as R  # noqa: E402

IA = RC.IA


def pool(obs, modo, rojo, azul):
    return [o for o in obs if o["modo"] == modo and o["rojo"] == rojo and o["azul"] == azul]


def fila(nombre, o):
    v = [x for x in o if x["valida"]]
    n = len(v)
    c = Counter(x["resultado"] for x in v)
    return f"| {nombre.replace(chr(124), chr(166))} | {n} ({len(o) - n}) | {R.fmt(R.prop(c['VICTORIA_ROJA'], n))} | {R.fmt(R.prop(c['VICTORIA_AZUL'], n))} | {R.fmt(R.prop(c['EMPATE_DEGRADADO'], n))} |"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campana", default="caminos-v1")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    obs = RC.leer(a.campana)
    inf = json.loads((RAIZ / "docs" / "evaluacion" / a.campana / "resumen.json").read_text(encoding="utf-8"))
    ia = [o for o in obs if o["tipo"] == "CAMINOS_IA"]
    gu = [o for o in obs if o["tipo"] == "CAMINOS_GUION"]
    L = [f"# Informe de la campaña de Caminos (`{a.campana}`)\n",
         "Generado por `experimentos/informe_caminos.py` a partir de `data/campanas/%s/observaciones.jsonl`; análisis completo con IC de Wilson, bootstrap por partida y Fisher + Holm en `docs/evaluacion/%s/resumen.md`. **Prompts `c1` sin cambios durante la campaña.**\n" % (a.campana, a.campana),
         "## 1. Qué se midió y con qué honestidad",
         f"- **{len(obs)} partidas** ({len(gu)} `CAMINOS_GUION`: guiones y líneas base sin IA; {len(ia)} `CAMINOS_IA`: al menos un lado es un 8B real). **Válidas:** {sum(o['valida'] for o in obs)}; **inconclusas/errores (excluidas de las tasas):** {sum(not o['valida'] for o in obs)}.",
         "- Modos: **grafo** de 16 hojas (3 dificultades) y **automático** de credenciales (8 credenciales fijas, tráfico legítimo 30-40 %).",
         "- Modelos: `qwen3:8b` y `llama3.1:8b` (Ollama local). Fases: línea base sin GPU, 8B contra el otro equipo trivial, **espejo** y **cruzada**.",
         "- Una victoria Roja de `CAMINOS_GUION` demuestra que el diseño la permite; **solo las de `CAMINOS_IA` son victorias de un modelo, y solo en este modo.**\n",
         "## 2. Líneas base (sin IA)\n", "| Pareja (modo · Rojo vs Azul) | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado |", "|---|---|---|---|---|"]
    for modo in ("grafo", "auto"):
        rojos = ["primera", "aleatorio"] + [x for x in sorted({o["rojo"] for o in gu if o["modo"] == modo}) if x.startswith("guion")]
        for az in ("registro", "aprobar", "rechazar", "aleatorio"):
            for r in rojos:
                o = pool(gu, modo, r, az)
                if o:
                    L.append(fila(f"{modo} · {r[:24]} vs {az}", o))
    L += ["\n## 3. Un 8B como Rojo contra un Azul trivial\n", "| Pareja | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado |", "|---|---|---|---|---|"]
    for modo in ("grafo", "auto"):
        for m in IA:
            for az in ("aprobar", "registro", "aleatorio", "rechazar"):
                o = pool(ia, modo, m, az)
                if o:
                    L.append(fila(f"{modo} · Rojo {m} vs Azul {az}", o))
    L += ["\n## 4. Un 8B como Azul contra un Rojo trivial\n", "| Pareja | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado |", "|---|---|---|---|---|"]
    for modo in ("grafo", "auto"):
        for m in IA:
            for r in sorted({o["rojo"] for o in ia if o["modo"] == modo and o["azul"] == m and o["rojo"] not in IA}):
                o = pool(ia, modo, r, m)
                if o:
                    L.append(fila(f"{modo} · Rojo {r[:24]} vs Azul {m}", o))
    L += ["\n## 5. 8B contra 8B (espejo y cruzada)\n", "| Pareja | n válidas (no válidas) | Victoria Roja | Victoria Azul | Empate degradado |", "|---|---|---|---|---|"]
    for modo in ("grafo", "auto"):
        for r in IA:
            for az in IA:
                o = pool(ia, modo, r, az)
                if o:
                    L.append(fila(f"{modo} · {'espejo' if r == az else 'cruzada'} · Rojo {r} vs Azul {az}", o))
    # hojas alcanzadas por victorias Rojas de 8B en el grafo
    hojas = Counter(o["hoja"] for o in ia if o["modo"] == "grafo" and o["resultado"] == "VICTORIA_ROJA" and o["rojo"] in IA and o["azul"] in IA)
    L += ["\n## 6. Victorias Rojas de 8B contra 8B: hojas alcanzadas", ", ".join(f"`{h}` ×{n}" for h, n in hojas.most_common()) or "Ninguna en el grafo.",
          "\n## 7. Qué decisiones del Azul inclinaron el resultado (modo grafo, Azul 8B, partidas válidas)"]
    for m in IA:
        d = RC.decisiones_azul([o for o in obs if o["modo"] == "grafo" and o["azul"] == m and o["valida"]])
        crit = {n: ops for n, ops in d.items() if n in ("N1r2", "N1i2", "N1i4", "N2", "N2b", "N2c", "N2v1", "N3", "N4", "N4v1")}
        L.append(f"- **Azul {m}:** " + "; ".join(f"{n}: " + ", ".join(f"{op}×{c}" for op, c in ops.items()) for n, ops in crit.items()))
    sig = [p for p in inf["contrastes"]["contrastes"] if p["significativo_holm_0_05"]]
    L += [f"\n## 8. Contrastes (Fisher exacto + Holm sobre {len(inf['contrastes']['contrastes'])} comparaciones)",
          f"Significativos al 0,05 tras Holm: **{len(sig)}**. Los más relevantes:"]
    for p in sig[:10]:
        L.append(f"- {p['contraste']} — {p['metrica']}: {p['a']['exitos']}/{p['a']['n']} frente a {p['b']['exitos']}/{p['b']['n']} (p Holm = {p['p_holm']:.4f}).")
    n_cru = sum(1 for o in ia if o["fase"] == "cruzada")
    L += ["\n## 9. Limitaciones (fijas)",
          f"- **La fase cruzada quedó incompleta ({n_cru} partidas)**: la GPU se cedió al usuario; los ids son deterministas y la campaña se puede reanudar. Las filas «cruzada» son exploratorias (n < 30).",
          "- Las líneas base son deterministas: sus resultados no varían entre dificultades ni semillas; sirven de referencia, no de muestra.",
          "- Los prompts de los 8B (`c1`) se escribieron una vez y no se calibraron para este modo; otros prompts u otros modelos podrían dar otras tasas.",
          "- En el modo automático el Rojo 8B tiende a probar primero la credencial del administrador de respaldos (un señuelo): es una observación del modelo, no un ajuste del modo.",
          "- El grafo tiene 5 nodos del Rojo con una única opción (D-24): la decisión real del Rojo es su primer movimiento y la elección tras abrir sesión.",
          "- Las partidas lanzadas con `semilla` compartida entre parejas no son pareables partida a partida; los contrastes tratan las muestras como independientes.",
          "- Wazuh es **simulado**; las alertas no provienen de una instalación real."]
    out = RAIZ / "docs" / "evaluacion" / "INFORME_CAMINOS.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("escrito", out)


if __name__ == "__main__":
    main()
