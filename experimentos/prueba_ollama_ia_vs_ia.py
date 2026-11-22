"""Nova: IA Roja vs IA Azul, AMBAS con Ollama real (8B), modo libre y auto, sin guion humano. Responde «¿gana el Rojo cuando el Azul reacciona?».
Mide resultados por emparejamiento y modalidad, sin maquillar. Salida: data/nova_ollama_ia_vs_ia.json y docs/evaluacion/NOVA_OLLAMA_IA_VS_IA.md.
Uso: python experimentos/prueba_ollama_ia_vs_ia.py [--partidas 6] [--pasos 14]"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from cryptography.fernet import Fernet  # noqa: E402
from src.lab import cliente_ollama as co  # noqa: E402
from src.lab.nova.ia import ControlIA, OllamaProvider  # noqa: E402
from src.lab.nova.motor import ErrorNova, NovaPartida, Secretos  # noqa: E402

HOST = "http://127.0.0.1:11434"
PARES = [("qwen3:8b", "qwen3:8b"), ("llama3.1:8b", "llama3.1:8b"), ("qwen3:8b", "llama3.1:8b"), ("llama3.1:8b", "qwen3:8b")]   # (rojo, azul)
SEC = Secretos(pepper="prueba-iavsia", clave_fernet=Fernet.generate_key())


def partida(rojo, azul, modalidad, semilla, pasos):
    m = NovaPartida(config={"seed": semilla, "duration_s": 600, "modalidad": modalidad, "ai_prompt_mode": "libre", "approval_mode": "votacion"}, secretos=SEC)
    m.abrir_sala()
    m.unirse("Rojo1", "RED")
    m.unirse("Azul1", "BLUE")
    m.unirse("Azul2", "BLUE")
    m.marcar_lista()
    m.iniciar("ADMIN", True, "k")
    ia = ControlIA(m)
    ia.configurar("RED", "auto", OllamaProvider(HOST, rojo, semilla=semilla))
    ia.configurar("BLUE", "auto", OllamaProvider(HOST, azul, semilla=semilla))
    t0 = time.time()
    for _ in range(pasos):
        for eq in ("RED", "BLUE"):
            try:
                ia.proponer(eq)
            except ErrorNova:
                pass
        m.avanzar(20)
        if m.resultado:
            break
    if not m.resultado:
        m.detener()
    runs = ia.runs
    return {"rojo": rojo, "azul": azul, "modalidad": modalidad, "semilla": semilla, "resultado": m.resultado["resultado"], "motivo": m.resultado["motivo"], "segundos": round(time.time() - t0, 1),
            "validas_rojo": sum(1 for r in runs if r["team"] == "RED" and r["salida_estructurada"]), "validas_azul": sum(1 for r in runs if r["team"] == "BLUE" and r["salida_estructurada"]),
            "corridas_rojo": sum(1 for r in runs if r["team"] == "RED"), "corridas_azul": sum(1 for r in runs if r["team"] == "BLUE"),
            "ejecutadas_rojo": sum(1 for r in runs if r["team"] == "RED" and r.get("propuesta", {}).get("estado") == "EJECUTADA"),
            "ejecutadas_azul": sum(1 for r in runs if r["team"] == "BLUE" and r.get("propuesta", {}).get("estado") == "EJECUTADA"), "tablas_extraidas": sorted(m.extraido)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partidas", type=int, default=6)
    ap.add_argument("--pasos", type=int, default=14)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not co.ollama_disponible(HOST):
        print("Ollama no responde: NO VERIFICADO")
        return 2
    inst = co.listar_modelos(HOST)
    if any(x not in inst for par in PARES for x in par):
        print("faltan modelos -> NO VERIFICADO")
        return 2
    obs = []
    for rojo, azul in PARES:
        for modalidad in ("BALANCED", "RED_ADVANTAGE", "BLUE_ADVANTAGE"):
            for k in range(1, a.partidas + 1):
                try:
                    o = partida(rojo, azul, modalidad, k, a.pasos)
                except Exception as exc:  # noqa: BLE001
                    o = {"rojo": rojo, "azul": azul, "modalidad": modalidad, "semilla": k, "resultado": "ERROR_TECNICO", "motivo": f"{type(exc).__name__}: {exc}"[:120]}
                obs.append(o)
                print(f"{rojo:<12} vs {azul:<12} {modalidad:<14} #{k}: {o['resultado']:<14} {o.get('segundos')}s tablas {o.get('tablas_extraidas')}", flush=True)
    (RAIZ / "data" / "nova_ollama_ia_vs_ia.json").write_text(json.dumps(obs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    L = ["# Nova: IA Roja vs IA Azul con Ollama REAL\n", f"Generado por `experimentos/prueba_ollama_ia_vs_ia.py`: {len(obs)} partidas, ambos equipos con un 8B en modo libre y `auto` (sin guion humano), 2 Azules en la sala, duración 600 s de partida. Datos: `data/nova_ollama_ia_vs_ia.json`.\n",
         "| Rojo | Azul | Modalidad | Partidas | Rojo gana | Azul gana | Empate | Error | % Rojo |", "|---|---|---|---|---|---|---|---|---|"]
    for rojo, azul in PARES:
        for mod in ("BALANCED", "RED_ADVANTAGE", "BLUE_ADVANTAGE"):
            g = [o for o in obs if o["rojo"] == rojo and o["azul"] == azul and o["modalidad"] == mod]
            c = Counter(o["resultado"] for o in g)
            L.append(f"| {rojo} | {azul} | {mod} | {len(g)} | {c['VICTORIA_ROJA']} | {c['VICTORIA_AZUL']} | {c['EMPATE']} | {c['ERROR_TECNICO']} | {100 * c['VICTORIA_ROJA'] / max(1, len(g)):.0f} % |")
    tot = Counter(o["resultado"] for o in obs)
    L += [f"\n**Total:** {len(obs)} partidas · Rojo {tot['VICTORIA_ROJA']} · Azul {tot['VICTORIA_AZUL']} · Empate {tot['EMPATE']} · Error técnico {tot['ERROR_TECNICO']}.",
          "\n## Límites", "- Muestras pequeñas (n por celda en la tabla), exploratorio: no es una probabilidad estable.", "- Los dos equipos son modelos 8B sin calibrar, con prompts v1; no refleja a jugadores humanos.",
          "- El Azul de IA decide solo (auto); en una partida real los humanos votan las autorizaciones."]
    (RAIZ / "docs" / "evaluacion" / "NOVA_OLLAMA_IA_VS_IA.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
