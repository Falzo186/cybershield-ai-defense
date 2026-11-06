"""Pruebas del presupuesto de partida EN el camino de la batalla real (Fase B).
Ejecutar: python server/test_presupuesto.py

BD en memoria y Ollama FALSO (e2e/ollama_falso.py). Lo que se comprueba es que el harness está de verdad en
el camino de `/api/batalla/real/iniciar`: que el consumo que se publica es el que ocurrió, que los techos
cortan la batalla y la nombran, y que un corte nunca se presenta como un final normal.

No se mide ninguna calidad de modelo: el Ollama falso responde siempre lo mismo.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e2e"))

from fastapi.testclient import TestClient  # noqa: E402

import app as srv  # noqa: E402
import ollama_falso  # noqa: E402
from src.lab import harness, repositorio  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repositorio._DEFECTO = repositorio.abrir(":memory:")
    repo = repositorio.por_defecto()
    falso, url = ollama_falso.iniciar(retardo=0.05)
    c = TestClient(srv.app)
    c.__enter__()
    H = lambda t: {"X-Equipo-Token": t}  # noqa: E731
    unirse = lambda eq, nom, **x: c.post("/api/sesion", json={"nombre": nom, "equipo": eq, **x}).json()["token"]  # noqa: E731
    tg = unirse("general", "Juez", codigo=srv.CODIGO_ARBITRO)
    P = lambda ruta, tok, **j: c.post(ruta, json=j, headers=H(tok))  # noqa: E731

    def esperar(cond, limite=25):
        t0 = time.monotonic()
        while time.monotonic() - t0 < limite:
            if cond():
                return True
            time.sleep(0.05)
        return False

    def batalla(rondas):
        antes = len(repo.rondas_practica())
        r = P("/api/batalla/real/iniciar", tg, de_rol="general", modelo_atq="falso-atacante",
              modelo_def="falso-defensor", host_atacante=url, host_defensor=url, rondas=rondas,
              dificultad="media")
        esperar(lambda: not srv.ms.ESTADO["corriendo"])
        return r, len(repo.rondas_practica()) - antes

    # ── Antes de cualquier batalla ─────────────────────────────────────────────────────────────────────────
    srv.CONTROL_BATALLA = None
    j = c.get("/api/batalla/presupuesto").json()
    chk("sin ninguna batalla ejecutada, no se inventa un presupuesto",
        j["activo"] is False and j["presupuesto"] is None and "No se ha ejecutado" in j["nota"])
    chk("la ruta del presupuesto es de lectura pública (espectador sin sesión)",
        c.get("/api/batalla/presupuesto").status_code == 200)
    chk("y no acepta POST: nadie puede ampliar un techo desde fuera",
        c.post("/api/batalla/presupuesto", json={}, headers=H(tg)).status_code in (404, 405))

    # ── Una batalla normal: el consumo publicado es el que ocurrió ─────────────────────────────────────────
    r, guardadas = batalla(2)
    chk("la batalla de 2 rondas arranca y termina", r.status_code == 200 and guardadas == 2)
    p = c.get("/api/batalla/presupuesto").json()
    cons = p["presupuesto"]["consumo"]
    chk("el presupuesto de la partida queda publicado", p["presupuesto"] is not None)
    chk("cuenta las 2 rondas jugadas", cons["rondas"] == 2)
    chk("y 2 llamadas al modelo por ronda (atacante + defensor)", cons["llamadas_modelo"] == 4)
    chk("los tokens publicados son los que devolvió el Ollama falso",
        cons["tokens_salida"] == 4 * ollama_falso.TOKENS_SALIDA
        and cons["tokens_entrada"] == 4 * ollama_falso.TOKENS_ENTRADA)
    chk("terminar las rondas previstas es un final normal", p["presupuesto"]["estado"] == "terminado")
    chk("sin ningún corte del harness", cons["cortes_harness"] == 0)
    chk("la batalla terminada ya no está activa", p["activo"] is False)
    chk("se publica también el presupuesto de UNA solicitud",
        p["presupuesto_ronda"]["max_iteraciones"] == srv.PRESUPUESTO_RONDA.max_iteraciones)
    chk("el techo de rondas es el que se pidió, no uno fijo del código",
        p["presupuesto"]["presupuesto"]["max_rondas"] == 2)
    chk("ninguna ronda se cortó por falta de presupuesto",
        all(x["error"] is None or "harness" not in str(x["error"]) for x in repo.rondas_practica()))

    # ── El techo de llamadas corta la batalla y la nombra ──────────────────────────────────────────────────
    original = srv._presupuesto_partida
    try:
        # 2 llamadas = exactamente una ronda. La segunda no debe llegar a lanzarse.
        srv._presupuesto_partida = lambda rondas: harness.PresupuestoPartida(
            max_rondas=rondas, max_llamadas_modelo=2, timeout_global_s=120.0, max_errores_consecutivos=3)
        r, guardadas = batalla(3)
        p = c.get("/api/batalla/presupuesto").json()
        chk("con techo de 2 llamadas solo se juega 1 ronda de las 3 pedidas", guardadas == 1)
        chk("la batalla queda «agotado», no «terminado»", p["presupuesto"]["estado"] == "agotado")
        chk("y el motivo nombra el techo que se agotó",
            "llamadas al modelo" in (p["presupuesto"]["motivo_corte"] or ""))
        chk("el corte no inventa rondas: el contador se queda en 1",
            p["presupuesto"]["consumo"]["rondas"] == 1)

        # Techo de rondas por debajo de las pedidas: manda el presupuesto, no el cuerpo de la petición.
        srv._presupuesto_partida = lambda rondas: harness.PresupuestoPartida(
            max_rondas=1, max_llamadas_modelo=99, timeout_global_s=120.0, max_errores_consecutivos=3)
        r, guardadas = batalla(4)
        p = c.get("/api/batalla/presupuesto").json()
        chk("el techo de rondas del presupuesto manda sobre las rondas pedidas", guardadas == 1)
        chk("y agotar las rondas sí es un final normal", p["presupuesto"]["estado"] == "terminado")

        # Repetición idéntica: el Ollama falso manda siempre el mismo prompt, así que 3 rondas lo disparan.
        srv._presupuesto_partida = lambda rondas: harness.PresupuestoPartida(
            max_rondas=rondas, max_llamadas_modelo=99, timeout_global_s=120.0,
            max_errores_consecutivos=3, max_repeticiones_identicas=2)
        r, guardadas = batalla(4)
        p = c.get("/api/batalla/presupuesto").json()
        chk("el atacante repitiendo el mismo prompt corta la batalla", guardadas == 3)
        chk("y se marca como bucle, no como victoria de nadie", p["presupuesto"]["estado"] == "bucle")
        chk("con el motivo dicho", "repitió el mismo prompt" in (p["presupuesto"]["motivo_corte"] or ""))
    finally:
        srv._presupuesto_partida = original

    # ── El harness no cambia el resultado de las rondas ────────────────────────────────────────────────────
    r, guardadas = batalla(2)
    filas = repo.rondas_practica()[:2]
    chk("las rondas siguen guardándose con su veredicto", guardadas == 2 and all(f["veredicto"] for f in filas))
    chk("y con las métricas reales de los dos modelos",
        all(f["atq_tokens_entrada"] == ollama_falso.TOKENS_ENTRADA
            and f["def_tokens_salida"] == ollama_falso.TOKENS_SALIDA for f in filas))
    chk("el veredicto del Ollama falso es el mismo que antes de meter el harness",
        filas[0]["veredicto"] == "PERMITIDO_CORRECTO")

    # ── Detener a mitad: el presupuesto refleja la cancelación ─────────────────────────────────────────────
    P("/api/batalla/real/iniciar", tg, de_rol="general", modelo_atq="falso-atacante",
      modelo_def="falso-defensor", host_atacante=url, host_defensor=url, rondas=6, dificultad="media")
    esperar(lambda: srv.ms.ESTADO["corriendo"], 5)
    P("/api/detener", tg)
    esperar(lambda: not srv.ms.ESTADO["corriendo"])
    p = c.get("/api/batalla/presupuesto").json()
    chk("una batalla detenida no queda como terminada",
        p["presupuesto"]["estado"] in ("cancelado", "agotado", "en_curso", "bucle"))
    chk("detener no corrompe el presupuesto: sigue siendo serializable y coherente",
        p["presupuesto"]["consumo"]["rondas"] <= 6
        and p["presupuesto"]["consumo"]["llamadas_modelo"] >= 0)

    c.__exit__(None, None, None)
    falso.shutdown()
    print(f"\nTotal {sum(resultados)}/{len(resultados)}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
