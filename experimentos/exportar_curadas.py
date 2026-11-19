"""Exporta partidas REALES ya registradas de `combate-v1` a `data/demo_curadas/` (JSON versionado) para reproducirlas en la UI.

No edita ni inventa nada: copia la fila de la partida, TODOS sus eventos con sus hashes (la cadena se puede verificar de nuevo) y las
alertas Wazuh simuladas que el motor generó para ella. Cada archivo lleva el motivo de la selección y su origen.
"""
import json
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from src.lab.combate.store import Almacen  # noqa: E402

CAMPANA = RAIZ / "data" / "campanas" / "combate-v1"
SALIDA = RAIZ / "data" / "demo_curadas"
SELECCION = [
    ("espejo-ea569835e69b", "curada-azul-limpia", "VICTORIA_AZUL limpia: el Azul sirve el 100 % del tráfico legítimo y el Rojo no logra ningún objetivo."),
    ("espejo-fb1b325965f6", "curada-sobrecautela", "EMPATE_DEGRADADO por sobre-cautela: el Azul no cede nada al Rojo pero escala también el tráfico legítimo."),
    ("espejo-06488bcf4a20", "curada-objetivo-parcial", "Objetivo parcial del Rojo (llama→llama): 1 de 2 objetivos exigidos; no alcanza el umbral y la partida es EMPATE."),
]


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    obs = {}
    for l in (CAMPANA / "observaciones.jsonl").read_text(encoding="utf-8").splitlines():
        o = json.loads(l)
        obs[o["partida_id"]] = o
    almacenes = [Almacen(CAMPANA / n) for n in ("partidas.db", "partidas-llm.db") if (CAMPANA / n).exists()]
    for pid, nuevo_id, motivo in SELECCION:
        alm = next((a for a in almacenes if a.partida(pid)), None)
        if alm is None:
            raise SystemExit(f"no se encuentra {pid}")
        p = alm.partida(pid)
        ev = alm.eventos(pid)
        ok, msg = alm.verificar_cadena(pid)
        assert ok, msg
        alertas = []
        for l in (CAMPANA / "wazuh_alerts.ndjson").read_text(encoding="utf-8").splitlines():
            a = json.loads(l)
            if (a.get("lab") or {}).get("partida_id") == pid:
                alertas.append(a)
        o = obs.get(pid, {})
        doc = {"id_curada": nuevo_id, "partida_id_original": pid, "origen": "campaña combate-v1 (observaciones.jsonl)", "motivo_seleccion": motivo,
               "campana": {k: o.get(k) for k in ("fase", "escenario", "rojo", "azul", "semilla", "config", "version_prompts", "resultado", "duracion_s")},
               "partida": p, "eventos": ev, "alertas_wazuh_simuladas": alertas, "cadena_integra_al_exportar": ok}
        (SALIDA / f"{nuevo_id}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(nuevo_id, pid, p["resultado"]["resultado"], len(ev), "eventos", len(alertas), "alertas")


if __name__ == "__main__":
    main()
