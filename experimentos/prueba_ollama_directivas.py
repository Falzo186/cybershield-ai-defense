"""Nova con Ollama REAL en modo CONTROLADO: un «humano» guionizado arma las directivas (los combos) y la IA (qwen3:8b / llama3.1:8b) responde.
Mide, sin falsificar: ¿propone la acción pedida (no INVALIDA)?, ¿la acepta el motor?, ¿respetó la estructura de la credencial aleatoria o la tuvo que completar el motor?
Salida: data/nova_ollama_directivas.json y docs/evaluacion/NOVA_OLLAMA_DIRECTIVAS.md. Uso: python experimentos/prueba_ollama_directivas.py [--partidas 4]"""
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
MODELOS = ["qwen3:8b", "llama3.1:8b"]
SEC = Secretos(pepper="prueba-dir", clave_fernet=Fernet.generate_key())
H = {"kind": "human", "team": "RED", "user": "Rojo1"}


def nueva(semilla):
    m = NovaPartida(config={"seed": semilla, "duration_s": 900, "guess_cooldown_s": 0, "guess_attempts_per_round": 9, "detect_prob_fail": 0.0}, secretos=SEC)
    m.abrir_sala()
    m.unirse("Rojo1", "RED")
    m.unirse("Azul1", "BLUE")
    m.unirse("Azul2", "BLUE")
    m.marcar_lista()
    m.iniciar("ADMIN", True, "k")
    return m, ControlIA(m)


def humano_rojo(m, tipo, **p):
    return m.ejecutar({"action_type": tipo, "actor": H, "params": p})


DIR_ROJO = [
    ("reconocer", {"accion": "scan_directory", "objetivo": "info_administrativa", "estrategia": "ingenieria_social"}, None),
    ("correo", {"accion": "send_email", "objetivo": "consultar_reportes_financieros", "estrategia": "ingenieria_social", "identidad_id": "EMP-05", "plantilla": "aviso_soporte"}, "avanzar"),
    ("aleatoria_12Q", {"accion": "guess_credential", "objetivo": "consultar_ventas", "estrategia": "adivinacion", "identidad_id": "EMP-01", "credencial": {"modo": "aleatoria", "digitos_iniciales": "12", "letra": "Q"}}, None),
    ("aleatoria_1234", {"accion": "guess_credential", "objetivo": "consultar_inventario", "estrategia": "adivinacion", "identidad_id": "EMP-04", "credencial": {"modo": "aleatoria", "digitos_iniciales": "1234", "letra": ""}}, None),
    ("consulta_conocida", {"accion": "query_resource", "objetivo": "consultar_reportes_financieros", "estrategia": "uso_credencial_expuesta", "identidad_id": "EMP-05", "credencial": {"modo": "conocida"}}, None),
    ("extraer_conocida", {"accion": "extract_table", "objetivo": "extraer_tabla", "estrategia": "uso_credencial_expuesta", "identidad_id": "EMP-05", "tabla": "reportes_financieros", "credencial": {"modo": "conocida"}}, None),
]


def partida_rojo(modelo, semilla):
    m, ia = nueva(semilla)
    ia.configurar("RED", "auto", OllamaProvider(HOST, modelo, semilla=semilla))
    filas = []
    for nombre, d, post in DIR_ROJO:
        if m.resultado:
            break
        t0 = time.time()
        try:
            r = ia.proponer("RED", d)
            est = r["propuesta"]["estado"] if r.get("propuesta") else r["estado"]
            filas.append({"directiva": nombre, "estado": est, "motivo": r.get("propuesta", {}).get("reject_reason"), "ajustada": r.get("candidata_ajustada_por_motor"), "ms": r["latencia_ms"], "s": round(time.time() - t0, 1)})
        except ErrorNova as e:
            filas.append({"directiva": nombre, "estado": "NO_LANZADA", "motivo": e.motivo, "ajustada": None, "ms": 0, "s": 0})
        if post == "avanzar":
            m.avanzar(m.config["click_delay_s"] + 2)
        m.avanzar(25)
    if not m.resultado:
        m.detener()
    return {"modelo": modelo, "equipo": "RED", "semilla": semilla, "resultado": m.resultado["resultado"], "directivas": filas, "oportunidades": ia.oportunidades("RED")}


def partida_azul(modelo, semilla):
    m, ia = nueva(semilla)
    ia.configurar("BLUE", "auto", OllamaProvider(HOST, modelo, semilla=semilla))
    humano_rojo(m, "send_email", identidad_id="EMP-05", plantilla="aviso_soporte")
    m.avanzar(m.config["click_delay_s"] + 2)
    real = SEC.descifrar(m.creds["EMP-01"]["enc"])
    humano_rojo(m, "guess_credential", identidad_id="EMP-01", candidate_value=real[:4] + ("0" if real[4] != "0" else "1") + ("A" if real[5] != "A" else "B"))
    ap = next((a["id"] for a in m.aprobaciones.values() if a["operacion"] == "acceso_sospechoso"), None)
    al = next(iter(m.alertas), None)
    DIR = [("revocar_comprometida", {"foco": "identidad", "sujeto_id": "EMP-05", "accion_preferida": "revoke_credential"}),
           ("denegar_sospechosa", {"foco": "solicitud", "sujeto_id": ap, "accion_preferida": "reject_request"}),
           ("libre_alerta", {"foco": "alerta", "sujeto_id": al, "accion_preferida": None}),
           ("libre_general", {"foco": "general", "sujeto_id": None, "accion_preferida": None})]
    filas = []
    for nombre, d in DIR:
        t0 = time.time()
        try:
            r = ia.proponer("BLUE", d)
            est = r["propuesta"]["estado"] if r.get("propuesta") else r["estado"]
            filas.append({"directiva": nombre, "estado": est, "motivo": r.get("propuesta", {}).get("reject_reason"), "ajustada": None, "ms": r["latencia_ms"], "s": round(time.time() - t0, 1)})
        except ErrorNova as e:
            filas.append({"directiva": nombre, "estado": "NO_LANZADA", "motivo": e.motivo, "ajustada": None, "ms": 0, "s": 0})
        m.avanzar(5)
    if not m.resultado:
        m.detener()
    return {"modelo": modelo, "equipo": "BLUE", "semilla": semilla, "resultado": m.resultado["resultado"], "directivas": filas, "oportunidades": ia.oportunidades("BLUE")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partidas", type=int, default=4)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not co.ollama_disponible(HOST):
        print("Ollama no responde: NO VERIFICADO")
        return 2
    faltan = [m for m in MODELOS if m not in co.listar_modelos(HOST)]
    if faltan:
        print("modelos no instalados:", faltan, "-> NO VERIFICADO")
        return 2
    obs = []
    for modelo in MODELOS:
        for eq, fn in (("RED", partida_rojo), ("BLUE", partida_azul)):
            for k in range(1, a.partidas + 1):
                try:
                    o = fn(modelo, k)
                except Exception as exc:  # noqa: BLE001
                    o = {"modelo": modelo, "equipo": eq, "semilla": k, "resultado": "ERROR_TECNICO", "directivas": [], "error": f"{type(exc).__name__}: {exc}"[:160]}
                obs.append(o)
                print(modelo, eq, k, o["resultado"], [(f["directiva"], f["estado"]) for f in o["directivas"]], flush=True)
    (RAIZ / "data" / "nova_ollama_directivas.json").write_text(json.dumps(obs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    L = ["# Nova con Ollama REAL en modo controlado (directivas)\n", f"Generado por `experimentos/prueba_ollama_directivas.py`: {len(obs)} partidas; un «humano» guionizado arma cada directiva y el 8B responde en modo `auto` "
         "(el motor valida). Datos crudos: `data/nova_ollama_directivas.json`.\n",
         "| Modelo | Equipo | Directiva | Lanzadas | EJECUTADA | RECHAZADA (motor) | INVALIDA | FALLIDA | Ajustada por el motor | Latencia media (ms) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for mod in MODELOS:
        for eq in ("RED", "BLUE"):
            nombres = list(dict.fromkeys(f["directiva"] for o in obs if o["modelo"] == mod and o["equipo"] == eq for f in o["directivas"]))
            for n in nombres:
                fs = [f for o in obs if o["modelo"] == mod and o["equipo"] == eq for f in o["directivas"] if f["directiva"] == n]
                c = Counter(f["estado"] for f in fs)
                aj = sum(1 for f in fs if f["ajustada"])
                L.append(f"| {mod} | {eq} | {n} | {len(fs)} | {c['EJECUTADA']} | {c['RECHAZADA']} | {c['INVALIDA']} | {c['FALLIDA'] + c['NO_LANZADA']} | {aj if n.startswith('aleatoria') else '-'} | {round(sum(f['ms'] for f in fs) / max(1, len(fs)))} |")
    L += ["\n## Lectura y límites", "- INVALIDA = el modelo no cumplió el esquema o cambió de acción respecto a la directiva (el motor la descarta). RECHAZADA = el motor la rechazó por sus reglas (credencial, permiso, presupuesto).",
          "- «Ajustada por el motor» = la candidata de la credencial aleatoria no respetaba la estructura pedida y el motor la completó; mide cuánto hay que corregir al modelo, no su acierto.",
          "- Muestras pequeñas y exploratorias; el humano es un guion fijo, no un jugador real. No mide calidad táctica."]
    (RAIZ / "docs" / "evaluacion" / "NOVA_OLLAMA_DIRECTIVAS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
