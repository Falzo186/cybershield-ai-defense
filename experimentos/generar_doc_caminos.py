"""Genera la parte automática de docs/CAMINOS.md (diagrama Mermaid y tabla de las 16 hojas) a partir del grafo versionado."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from src.lab.caminos import grafo as G  # noqa: E402


def main():
    g = G.cargar("caminos-sencillo")
    L = ["```mermaid", "flowchart TD"]
    for n in g["nodos"].values():
        forma = ("([", "])") if n["actor"] == "rojo" else ("[[", "]]")
        L.append(f'  {n["id"]}{forma[0]}"{n["id"]} · {n["actor"].upper()}"{forma[1]}')
    for h in g["hojas"].values():
        L.append(f'  {h["id"]}{{{{"{h["id"][2:]}"}}}}')
    for n in g["nodos"].values():
        for o in n["opciones"]:
            L.append(f'  {n["id"]} -->|{o["id"]}| {o["siguiente"]}')
    for h in g["hojas"].values():
        L.append(f'  style {h["id"]} fill:{"#8f2a35" if h["resultado"] == "VICTORIA_ROJA" else "#1b2f5e"},color:#fff')
    L.append("```")
    tabla = ["| # | Hoja | Resultado | Recorrido (nodo:opción) | Tipo | Qué enseña |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(G.recorridos(g), 1):
        h = g["hojas"][r["hoja"]]
        tipo = "reversión" if h["reversion"] else "giro del Rojo" if h["giro"] else "directa"
        tabla.append(f"| {i} | `{h['id']}` | {'🔴 Rojo' if h['resultado'] == 'VICTORIA_ROJA' else '🔵 Azul'} | " + " → ".join(f"{n}:{o}" for n, o in r["camino"]) + f" | {tipo} | {h['ensena']} |")
    out = RAIZ / "docs" / "CAMINOS_GENERADO.md"
    out.write_text("# Diagrama y hojas del grafo de Caminos (generado)\n\nGenerado por `experimentos/generar_doc_caminos.py`. Rojo = óvalo; Azul = rectángulo doble; hojas rojas = victoria Roja, azules = victoria Azul.\n\n" + "\n".join(L) + "\n\n## Las 16 hojas\n\n" + "\n".join(tabla) + "\n", encoding="utf-8")
    print("escrito", out)


if __name__ == "__main__":
    main()
