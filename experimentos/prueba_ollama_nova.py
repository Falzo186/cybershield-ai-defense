"""F20 del paquete del profesor: Nova con Ollama REAL (qwen3:8b y llama3.1:8b). Mide, sin falsificar nada: tasa de propuestas válidas (esquema), latencia, y
resultados de partidas con un 8B en un equipo y la heurística SIMULADA (etiquetada) en el otro. Salida: data/nova_ollama_real.json y docs/evaluacion/NOVA_OLLAMA_REAL.md.
Uso: python experimentos/prueba_ollama_nova.py [--partidas 8]"""
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
from src.lab.nova.ia import ControlIA, OllamaProvider, ScriptedProvider  # noqa: E402
from src.lab.nova.motor import ErrorNova, NovaPartida, Secretos  # noqa: E402

HOST = "http://127.0.0.1:11434"
MODELOS = ["qwen3:8b", "llama3.1:8b"]
SEC = Secretos(pepper="prueba-ollama", clave_fernet=Fernet.generate_key())


def nueva(semilla):
    m = NovaPartida(config={"seed": semilla, "duration_s": 300, "ai_prompt_mode": "libre"}, secretos=SEC)
    m.abrir_sala()
    m.unirse("Rojo1", "RED")
    m.unirse("Azul1", "BLUE")
    m.unirse("Azul2", "BLUE")
    m.marcar_lista()
    m.iniciar("ADMIN", True, "k")
    return m, ControlIA(m)


def partida(modelo, equipo, semilla, pasos=8):
    m, ia = nueva(semilla)
    ia.configurar("RED", "auto")
    ia.configurar("BLUE", "auto")
    prov = OllamaProvider(HOST, modelo, semilla=semilla)
    ia.configurar(equipo, proveedor=prov)
    otro = "BLUE" if equipo == "RED" else "RED"
    ia.configurar(otro, proveedor=ScriptedProvider(otro))
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
    runs = [r for r in ia.runs if r["provider_kind"] == "ollama"]
    return {"modelo": modelo, "equipo": equipo, "semilla": semilla, "resultado": m.resultado["resultado"], "motivo": m.resultado["motivo"], "segundos": round(time.time() - t0, 1),
            "corridas": len(runs), "validas": sum(1 for r in runs if r["salida_estructurada"]), "invalidas": sum(1 for r in runs if r.get("propuesta", {}).get("estado") == "INVALIDA"),
            "fallidas": sum(1 for r in runs if r["estado"] == "FALLIDA"), "ejecutadas_ok": sum(1 for r in runs if r.get("propuesta", {}).get("estado") == "EJECUTADA"),
            "rechazadas_motor": Counter(r["propuesta"].get("reject_reason") for r in runs if r.get("propuesta", {}).get("estado") == "RECHAZADA"), "latencia_ms_media": round(sum(r["latencia_ms"] for r in runs) / max(1, len(runs)))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partidas", type=int, default=8)
    ap.add_argument("--etiqueta", default="", help="sufijo de los archivos de salida (p. ej. v2 = prompts con esquema JSON)")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not co.ollama_disponible(HOST):
        print("Ollama no responde: NO VERIFICADO")
        return 2
    inst = co.listar_modelos(HOST)
    faltan = [m for m in MODELOS if m not in inst]
    if faltan:
        print("modelos no instalados:", faltan, "-> NO VERIFICADO")
        return 2
    obs = []
    for modelo in MODELOS:
        for equipo in ("RED", "BLUE"):
            for k in range(1, a.partidas + 1):
                try:
                    o = partida(modelo, equipo, k)
                except Exception as exc:  # noqa: BLE001
                    o = {"modelo": modelo, "equipo": equipo, "semilla": k, "resultado": "ERROR_TECNICO", "motivo": f"{type(exc).__name__}: {exc}"[:120], "corridas": 0, "validas": 0}
                obs.append(o)
                print(f"{modelo:<12} {equipo} #{k}: {o['resultado']:<16} corridas {o.get('corridas')} válidas {o.get('validas')} inválidas {o.get('invalidas')} fallidas {o.get('fallidas')} {o.get('segundos')}s", flush=True)
    (RAIZ / "data").mkdir(exist_ok=True)
    (RAIZ / "data" / f"nova_ollama_real{a.etiqueta}.json").write_text(json.dumps(obs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    L = ["# Nova con Ollama REAL (F20) — qwen3:8b y llama3.1:8b\n", f"Generado por `experimentos/prueba_ollama_nova.py`; **{len(obs)} partidas** (un 8B en un equipo y la heurística **SIMULADA** etiquetada en el otro). Datos crudos: `data/nova_ollama_real{a.etiqueta}.json`; prompts: {descr}.\n",
         "| Modelo | Equipo | Partidas | Corridas | Propuestas válidas | Inválidas | Fallidas | Ejecutadas por el motor | Rojo gana | Azul gana | Empate | Latencia media (ms) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in MODELOS:
        for e in ("RED", "BLUE"):
            g = [o for o in obs if o["modelo"] == m and o["equipo"] == e]
            c = sum(o.get("corridas", 0) for o in g)
            L.append(f"| {m} | {e} | {len(g)} | {c} | {sum(o.get('validas', 0) for o in g)} ({100 * sum(o.get('validas', 0) for o in g) / max(1, c):.0f} %) | {sum(o.get('invalidas', 0) for o in g)} | {sum(o.get('fallidas', 0) for o in g)} | {sum(o.get('ejecutadas_ok', 0) for o in g)} | "
                     f"{sum(o['resultado'] == 'VICTORIA_ROJA' for o in g)} | {sum(o['resultado'] == 'VICTORIA_AZUL' for o in g)} | {sum(o['resultado'] == 'EMPATE' for o in g)} | {round(sum(o.get('latencia_ms_media', 0) for o in g) / max(1, len(g)))} |")
    L += ["\n## Lectura y límites", "- «Propuestas válidas» = el JSON cumplió el esquema estricto del contrato (05 §5/§6); **no** mide si la propuesta fue buena. «Ejecutadas por el motor» = el pipeline la aceptó.",
          "- El equipo contrario es el `ScriptedProvider` (SIMULADO – no es una IA): estas cifras no dicen cómo juegan dos 8B entre sí.", "- Muestras pequeñas (n por celda en la tabla): exploratorio. No hay modelo de 4B instalado; solo se probaron los dos de ~8B.",
          "- Resultados que dependen de la semilla y de los prompts v1 de Nova (sin calibrar)."]
    (RAIZ / "docs" / "evaluacion").mkdir(parents=True, exist_ok=True)
    (RAIZ / "docs" / "evaluacion" / f"NOVA_OLLAMA_REAL{a.etiqueta}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
