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
if hasattr(sys.stdout, "reconfigure"):   # consolas de Windows en cp1252 rompían el informe con tildes/emoji
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UNITARIAS = ["test_lab", "test_motor", "test_correos", "test_reglas", "test_misiones", "test_documentos", "test_eventos",
             "test_puntaje", "test_cliente", "test_correo_app", "test_incidentes", "test_ataque_ia", "test_informe",
             "test_apps", "test_diagnostico", "test_harness", "test_rag", "test_evaluacion", "test_adversarial", "test_wazuh", "test_correlacion",
             "test_control_partida", "test_lotes", "test_escenarios_empresa", "test_combate", "test_wazuh_sim", "test_caminos", "test_caminos_auto", "test_nova", "test_nova_ia", "demo_nova"]
SERVIDOR = ["server/test_partida.py", "server/test_app.py", "server/test_batalla_partida.py", "server/test_resultados.py",
            "server/test_apps.py", "server/test_presupuesto.py", "server/test_combate.py", "server/test_nova.py"]
INTEGRACION = ["e2e/test_reinicio.py", "integraciones/wazuh/test_reglas.py", "server/test_panel.py",
               # CyberShield Repair: componentes, regresión de la presentación contra el servidor real, controles de Ollama y demostración de 17 pasos
               "CyberShield_Repair_Library/tests/unit/test_solicitudes.py", "CyberShield_Repair_Library/tests/unit/test_chat.py",
               "CyberShield_Repair_Library/tests/regression/test_regresion_presentacion.py", "CyberShield_Repair_Library/tests/regression/test_ollama_controles.py",
               "CyberShield_Repair_Library/tests/demo/demo_academica.py"]
NAVEGADOR = ["e2e/demo_partida.py", "e2e/test_combate_ui.py", "e2e/test_combate_extra.py", "e2e/test_simulacion_ui.py", "e2e/test_nova_ui.py", "CyberShield_Repair_Library/tests/e2e_sala_equipo.py"]
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
