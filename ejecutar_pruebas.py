"""Batería completa de pruebas en un solo comando (Fase H). Sin Ollama real: las pruebas que necesitan un modelo usan
el Ollama FALSO de e2e/ollama_falso.py (respuestas fijas), así que comprueban el camino, no la calidad de un modelo.

Uso:  python ejecutar_pruebas.py                 todo (unitarias, servidor, integración y navegador)
      python ejecutar_pruebas.py --rapido        sin las que abren navegadores (Playwright)
      python ejecutar_pruebas.py --conservar-capturas   no restaura docs/capturas_demo tras la prueba de navegador
Sale con código 1 si falla alguna suite. Ninguna toca data/lab.db ni data/eventos.jsonl.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
UNITARIAS = ["test_lab", "test_motor", "test_correos", "test_reglas", "test_misiones", "test_documentos", "test_eventos",
             "test_puntaje", "test_cliente", "test_correo_app", "test_incidentes", "test_ataque_ia", "test_informe",
             "test_apps"]
SERVIDOR = ["server/test_partida.py", "server/test_app.py", "server/test_batalla_partida.py", "server/test_resultados.py",
            "server/test_apps.py"]
INTEGRACION = ["e2e/test_reinicio.py", "integraciones/wazuh/test_reglas.py"]
NAVEGADOR = ["e2e/demo_partida.py"]
TOTAL = re.compile(r"(\d+)/(\d+)")


def correr(nombre, cmd):
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    lineas = [x for x in r.stdout.splitlines() if x.strip()]
    ultima = lineas[-1] if lineas else (r.stderr.strip().splitlines() or ["(sin salida)"])[-1]
    m = TOTAL.search(ultima)
    fallos = [x.strip() for x in lineas if x.lstrip().startswith("FALLO")]
    return {"suite": nombre, "ok": r.returncode == 0, "resultado": f"{m[1]}/{m[2]}" if m else ultima[:80],
            "n": (int(m[1]), int(m[2])) if m else (0, 0), "s": time.monotonic() - t0, "fallos": fallos,
            "error": "" if r.returncode == 0 or fallos else (r.stderr.strip().splitlines() or [""])[-1][:200]}


def main():
    rapido = "--rapido" in sys.argv
    trabajos = ([(f"src.lab.{u}", [sys.executable, "-m", f"src.lab.{u}"]) for u in UNITARIAS]
                + [(s, [sys.executable, s]) for s in SERVIDOR + INTEGRACION]
                + ([] if rapido else [(s, [sys.executable, s]) for s in NAVEGADOR]))
    res = []
    for nombre, cmd in trabajos:
        x = correr(nombre, cmd)
        res.append(x)
        print(f"{'OK   ' if x['ok'] else 'FALLO'} {nombre:<38} {x['resultado']:>9}  ({x['s']:.0f} s)", flush=True)
        for f in x["fallos"]:
            print("        " + f)
        if x["error"]:
            print("        " + x["error"])
    if not rapido and "--conservar-capturas" not in sys.argv:
        subprocess.run(["git", "checkout", "--", "docs/capturas_demo"], cwd=RAIZ, capture_output=True)
    buenos, total = sum(x["n"][0] for x in res), sum(x["n"][1] for x in res)
    malas = [x["suite"] for x in res if not x["ok"]]
    print(f"\n{len(res) - len(malas)}/{len(res)} suites en verde · {buenos}/{total} comprobaciones"
          + (" · sin navegador (--rapido)" if rapido else ""))
    if malas:
        print("Fallaron: " + ", ".join(malas))
    return not malas


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
