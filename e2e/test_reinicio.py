"""Prueba de integración con REINICIO del servidor (Fase H): un servidor real (proceso aparte, BD en archivo temporal)
juega una partida completa por la API, se para y se vuelve a arrancar dos veces sobre la misma BD.

Comprueba lo que debe sobrevivir (resultado final con su desglose, cronología, ataques IA, rondas de práctica, eventos
del SIEM), lo que no (sesiones y partida en memoria: hay que volver a unirse) y que las migraciones son idempotentes.
Sin Ollama real (usa e2e/ollama_falso.py) y sin navegador. No toca data/lab.db ni data/eventos.jsonl.
Ejecutar: python e2e/test_reinicio.py
"""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ollama_falso  # noqa: E402
from src.lab import repositorio  # noqa: E402

CODIGO = "135790"
resultados = []
CAMPOS_SIEM = {"timestamp", "partida", "equipo", "usuario", "rol", "tipo", "accion", "recurso", "resultado", "riesgo", "origen"}
TIPOS_SIEM = {t for t, _ in repositorio.EVENTOS_SIEM.values()} | {"autorizacion_denegada"}


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


class Servidor:
    def __init__(self, db):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.puerto = s.getsockname()[1]
        s.close()
        env = {**os.environ, "PUERTO": str(self.puerto), "CS_LAB_DB": str(db), "PYTHONIOENCODING": "utf-8",
               "CS_CODIGO_ARBITRO": CODIGO}
        self.proc = subprocess.Popen([sys.executable, "server/app.py"], cwd=RAIZ, env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.base = f"http://127.0.0.1:{self.puerto}"
        for _ in range(100):
            try:
                urllib.request.urlopen(self.base + "/api/estado", timeout=1)
                return
            except Exception:  # noqa: BLE001 - aún arrancando
                time.sleep(0.2)
        self.parar()
        raise RuntimeError("el servidor no arrancó")

    def req(self, metodo, ruta, cuerpo=None, token=None):
        data = json.dumps(cuerpo).encode() if cuerpo is not None else None
        h = {"Content-Type": "application/json", **({"X-Equipo-Token": token} if token else {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + ruta, data=data, method=metodo, headers=h),
                                        timeout=30) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            cuerpo = e.read()
            try:
                return e.code, json.loads(cuerpo)
            except ValueError:
                return e.code, None

    def html(self, metodo, ruta):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + ruta, method=metodo, data=b"" if metodo == "POST" else None),
                                        timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def unirse(self, equipo, nombre, **x):
        return self.req("POST", "/api/sesion", {"nombre": nombre, "equipo": equipo, **x})[1]["token"]

    def parar(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def esquema(db):
    with sqlite3.connect(db) as c:
        return sorted(c.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall())


def esperar(cond, limite=20):
    t0 = time.monotonic()
    while time.monotonic() - t0 < limite:
        if cond():
            return True
        time.sleep(0.1)
    return False


def main():
    tmp = Path(tempfile.mkdtemp(prefix="cs_reinicio_"))
    db, jsonl = tmp / "lab.db", tmp / "eventos.jsonl"
    falso, url = ollama_falso.iniciar(retardo=0.2)
    s = Servidor(db)
    try:
        tg, tr = s.unirse("general", "Juez", codigo=CODIGO), s.unirse("rojo", "Rita")
        ta = s.unirse("azul", "Beto", usuario="ana.perez")
        chk("Azul fija su defensor (Ollama falso)", s.req("POST", "/api/ia/defensor", {"modelo": "falso-defensor", "host": url}, ta)[0] == 200)
        st, _ = s.req("POST", "/api/manual/real", {"prompt": "Necesito el stock de firewalls", "modelo_def": "falso-defensor",
                                                   "usuario": "ana.perez", "host_defensor": url}, tg)
        chk("una ronda de práctica antes de empezar", st == 200)
        s.req("POST", "/api/partida/iniciar", {"duracion_min": 5}, tg)
        sop = s.req("POST", "/api/correo", {"plantilla": "soporte_tecnico"}, tr)[1]["id"]
        paq = s.req("POST", "/api/correo", {"plantilla": "paqueteria"}, tr)[1]["id"]
        enl = {c["id"]: c["enlace"] for c in s.req("GET", "/api/buzon", token=ta)[1]["correos"]}
        s.html("GET", enl[sop])
        s.html("POST", enl[sop] + "/credenciales")
        s.req("POST", f"/api/correo/{paq}/reportar", {}, ta)
        s.req("POST", "/api/ia/ataque", {"modelo": "falso-atacante", "host": url, "tecnica": "autoridad"}, tr)
        ok = esperar(lambda: s.req("GET", "/api/ia/estado")[1]["lanzados"] == 1 and s.req("GET", "/api/ia/estado")[1]["en_curso"] is None)
        chk("un ataque IA con la credencial robada termina", ok)
        st, fin = s.req("POST", "/api/partida/finalizar", {}, tg)
        partida = s.req("GET", "/api/partidas")[1]["actual"]["id"]
        res = s.req("GET", "/api/resultados", token=tg)[1]
        cro = s.req("GET", "/api/cronologia", token=tg)[1]
        chk("la partida se finaliza con resultado", st == 200 and res["guardado"] and res["rojo"]["total"] == fin["puntos_rojo"])
        nota_puntos = (fin["puntos_rojo"], fin["puntos_azul"], fin["ganador"])
        print(f"      resultado: Rojo {nota_puntos[0]} — Azul {nota_puntos[1]} ({nota_puntos[2]}); "
              f"{cro['total']} eventos en la cronología")
    finally:
        s.parar()

    # --- con el servidor parado: lo guardado en disco ---
    with sqlite3.connect(db) as c:
        guardado = c.execute("SELECT puntos_rojo, puntos_azul, ganador FROM resultados_partida WHERE partida=?",
                             (partida,)).fetchone()
        n_ataques = c.execute("SELECT COUNT(*) FROM ataques_ia WHERE partida=? AND estado='terminado'", (partida,)).fetchone()[0]
        n_practica = c.execute("SELECT COUNT(*) FROM rondas_practica").fetchone()[0]
        n_audit = c.execute("SELECT COUNT(*) FROM auditoria WHERE partida=?", (partida,)).fetchone()[0]
    chk("en la BD: el resultado final, el ataque IA y la ronda de práctica",
        guardado == nota_puntos and n_ataques == 1 and n_practica == 1)
    lineas = jsonl.read_text(encoding="utf-8").splitlines()
    eventos = [json.loads(x) for x in lineas]
    chk("eventos.jsonl: cada línea es JSON con los 11 campos del contrato", eventos and all(set(e) == CAMPOS_SIEM for e in eventos))
    chk("solo tipos conocidos (los de EVENTOS_SIEM y autorizacion_denegada)", {e["tipo"] for e in eventos} <= TIPOS_SIEM)
    chk("todos con origen cybershield-lab y la partida en curso",
        all(e["origen"] == "cybershield-lab" and e["partida"] == partida for e in eventos))
    tipos = {e["tipo"] for e in eventos}
    chk("la partida dejó en el SIEM el phishing, la credencial, el ataque IA, la práctica y el cierre",
        {"correo_recibido", "clic_enlace", "credencial_comprometida", "correo_reportado", "ataque_ia_lanzado",
         "ataque_ia_resultado", "ronda_practica", "defensor_ia_configurado", "partida_finalizada"} <= tipos)
    expuesto = [e for e in eventos if e["tipo"] == "ataque_ia_resultado"]
    chk("el resultado del ataque con datos expuestos va con riesgo CRITICO",
        expuesto and expuesto[0]["resultado"] == "DATOS_EXPUESTOS" and expuesto[0]["riesgo"] == "CRITICO")
    esquema1 = esquema(db)

    # --- primer reinicio ---
    s = Servidor(db)
    try:
        chk("las sesiones viven en memoria: el token anterior ya no vale (hay que volver a unirse)",
            s.req("GET", "/api/sesion", token=tg)[0] == 403)
        p = s.req("GET", "/api/partidas")[1]
        chk("tras reiniciar hay una partida nueva en preparación", p["actual"]["id"] != partida and p["actual"]["fase"] == "preparacion")
        chk("y la anterior sigue en el historial con su resultado",
            [(x["partida"], x["puntos_rojo"], x["puntos_azul"], x["ganador"]) for x in p["finalizadas"]] == [(partida, *nota_puntos)])
        r2 = s.req("GET", f"/api/resultados?partida={partida}")[1]
        chk("su desglose guardado es idéntico al de antes del reinicio", {k: r2[k] for k in ("rojo", "azul", "riesgo", "batalla_ia")}
            == {k: res[k] for k in ("rojo", "azul", "riesgo", "batalla_ia")} and r2["guardado"])
        c2 = s.req("GET", f"/api/cronologia?partida={partida}")[1]
        chk("y su cronología también (mismas entradas)", c2["total"] == cro["total"] and c2["fase"] == "finalizada"
            and [e["id"] for e in c2["entradas"]] == [e["id"] for e in cro["entradas"]])
        chk("la partida nueva empieza vacía", s.req("GET", "/api/cronologia")[1]["total"] == 0
            and s.req("GET", "/api/ia/estado")[1]["lanzados"] == 0)
        tg2 = s.unirse("general", "Juez", codigo=CODIGO)
        chk("se puede volver a jugar: el árbitro se une e inicia", s.req("POST", "/api/partida/iniciar", {"duracion_min": 5}, tg2)[0] == 200)
        ta2 = s.unirse("azul", "Beto", usuario="ana.perez")
        chk("Azul vuelve a fijar su defensor (escribe un evento nuevo en el SIEM)",
            s.req("POST", "/api/ia/defensor", {"modelo": "falso-defensor", "host": url}, ta2)[0] == 200)
    finally:
        s.parar()
    chk("el reinicio no cambia el esquema de la BD (migraciones idempotentes)", esquema(db) == esquema1)
    lineas2 = jsonl.read_text(encoding="utf-8").splitlines()
    chk("eventos.jsonl se amplía, nunca se reescribe", lineas2[:len(lineas)] == lineas and len(lineas2) > len(lineas))
    with sqlite3.connect(db) as c:
        chk("la auditoría de la partida anterior no se tocó (append-only)",
            c.execute("SELECT COUNT(*) FROM auditoria WHERE partida=?", (partida,)).fetchone()[0] == n_audit)
        try:
            c.execute("DELETE FROM auditoria WHERE partida=?", (partida,))
            chk("la auditoría rechaza borrar filas", False)
        except sqlite3.DatabaseError:
            chk("la auditoría rechaza borrar filas", True)

    # --- segundo reinicio: sigue arrancando sobre la misma BD ---
    s = Servidor(db)
    try:
        chk("segundo reinicio: el historial sigue ahí", partida in [x["partida"] for x in s.req("GET", "/api/partidas")[1]["finalizadas"]])
    finally:
        s.parar()
    chk("y el esquema sigue igual", esquema(db) == esquema1)
    falso.shutdown()
    if os.getenv("CS_EXPORTAR_EVENTOS"):  # copia de los eventos reales de esta prueba (muestra para el adaptador de Wazuh)
        Path(os.environ["CS_EXPORTAR_EVENTOS"]).write_text(jsonl.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
