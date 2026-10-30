"""Comprobación SIN CONEXIÓN del adaptador de Wazuh (Fase H). No sustituye a wazuh-logtest ni a un Wazuh real.

1. Estructura: los XML son válidos, los ids son únicos y del rango local, y toda referencia (if_sid) existe.
2. Cobertura: cada tipo de evento que emite el laboratorio (EVENTOS_SIEM y autorizacion_denegada) tiene su regla.
3. Simulación APROXIMADA: aplica las reglas a eventos (los reales de eventos_ejemplo.jsonl y uno sintético por tipo)
   con este modelo simplificado de Wazuh: decodificador JSON, campos comparados con expresiones regulares y descenso
   por if_sid (primera regla hija que coincide, en orden). No simula correlaciones (frequency/if_matched_sid), listas,
   ni la sintaxis exacta de OS_Regex: las reglas solo usan ^, $ y |, que aquí significan lo mismo.
Ejecutar: python integraciones/wazuh/test_reglas.py
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR.parents[1]))

from src.lab import repositorio  # noqa: E402

CAMPOS = ("timestamp", "partida", "equipo", "usuario", "rol", "tipo", "accion", "recurso", "resultado", "riesgo", "origen")
TIPOS = sorted({t for t, _ in repositorio.EVENTOS_SIEM.values()} | {"autorizacion_denegada"})
resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def cargar_reglas():
    raiz = ET.parse(DIR / "local_rules.xml").getroot()
    reglas = []
    for r in raiz.iter("rule"):
        reglas.append({"id": int(r.get("id")), "nivel": int(r.get("level")), "padre": r.findtext("if_sid"),
                       "correlacion": r.findtext("if_matched_sid"), "json": r.findtext("decoded_as") == "json",
                       "campos": {f.get("name"): f.text for f in r.findall("field")},
                       "descripcion": r.findtext("description") or "", "mitre": [m.text for m in r.iter("id")]})
    return raiz, reglas


def coincide(regla, ev):
    return all(re.search(patron, "" if ev.get(campo) is None else str(ev.get(campo)))
               for campo, patron in regla["campos"].items())


def evaluar(reglas, ev):
    """-> regla final (la más profunda que coincide) o None. Modelo simplificado (ver la cabecera)."""
    actual = next((r for r in reglas if r["padre"] is None and r["correlacion"] is None and r["json"] and coincide(r, ev)), None)
    while actual:
        hija = next((r for r in reglas if r["padre"] == str(actual["id"]) and coincide(r, ev)), None)
        if hija is None:
            return actual
        actual = hija
    return None


def sintetico(tipo, resultado="OK"):
    return {"timestamp": "2026-10-30T10:00:00-06:00", "partida": "p-prueba", "equipo": "azul", "usuario": "ana.perez",
            "rol": "empleado", "tipo": tipo, "accion": tipo.upper(), "recurso": "correo:1", "resultado": resultado,
            "riesgo": "BAJO", "origen": "cybershield-lab"}


def main():
    raiz, reglas = cargar_reglas()
    ids = [r["id"] for r in reglas]
    chk("local_rules.xml es XML válido con un único grupo «cybershield»", raiz.tag == "group" and "cybershield" in raiz.get("name"))
    chk("ids únicos y en el rango local reservado (100100-100199)", len(ids) == len(set(ids)) and all(100100 <= i <= 100199 for i in ids))
    chk("toda referencia if_sid / if_matched_sid apunta a una regla existente",
        all(int(x) in ids for r in reglas for x in (r["padre"], r["correlacion"]) if x))
    chk("una sola regla base, que exige el decodificador JSON y origen cybershield-lab",
        [r["id"] for r in reglas if r["padre"] is None and r["correlacion"] is None] == [100100]
        and reglas[0]["json"] and reglas[0]["campos"] == {"origen": "^cybershield-lab$"})
    chk("niveles válidos de Wazuh (0-15)", all(0 <= r["nivel"] <= 15 for r in reglas))
    usados = {m for r in reglas for m in re.findall(r"\$\((\w+)\)", r["descripcion"])} | {c for r in reglas for c in r["campos"]}
    chk("las reglas solo usan campos del contrato del JSONL", usados <= set(CAMPOS))
    chk("las técnicas MITRE tienen formato válido", all(re.fullmatch(r"T\d{4}(\.\d{3})?", m) for r in reglas for m in r["mitre"]))

    loc = ET.parse(DIR / "ossec_localfile.xml").getroot().find("localfile")
    chk("ossec_localfile.xml: log_format json apuntando a eventos.jsonl",
        loc.findtext("log_format") == "json" and loc.findtext("location").endswith("eventos.jsonl"))

    # --- cobertura: cada tipo del laboratorio cae en una regla propia (no solo en la base) ---
    sin_regla = [t for t in TIPOS if (evaluar(reglas, sintetico(t)) or {}).get("id") in (None, 100100)]
    chk(f"los {len(TIPOS)} tipos de evento del laboratorio tienen regla propia", sin_regla == [])
    if sin_regla:
        print("      sin regla: " + ", ".join(sin_regla))

    # --- simulación: niveles esperados de los casos importantes ---
    esperado = {("credencial_comprometida", "COMPROMETIDA"): (100114, 12), ("clic_enlace", "CLIC"): (100111, 8),
                ("ataque_ia_resultado", "DATOS_EXPUESTOS"): (100132, 12), ("ataque_ia_resultado", "IA_ENGANADA"): (100133, 8),
                ("ataque_ia_resultado", "FALLO_SEGURO"): (100134, 7), ("ataque_ia_resultado", "CONTENIDO"): (100131, 3),
                ("autorizacion_denegada", "DENEGADO"): (100135, 6), ("credencial_revocada", "Bea"): (100120, 4),
                ("correo_recibido", "paqueteria"): (100110, 3)}
    obtenido = {k: (lambda r: (r["id"], r["nivel"]) if r else None)(evaluar(reglas, sintetico(*k))) for k in esperado}
    chk("simulación: compromiso y exposición de datos a nivel 12, clic 8, intentos frenados 6-8, rutina 3",
        obtenido == esperado)
    chk("un evento que no es del laboratorio no dispara ninguna regla", evaluar(reglas, {**sintetico("clic_enlace"), "origen": "otro"}) is None)
    chk("un tipo desconocido se queda en la regla base (visible, nivel 3)", evaluar(reglas, sintetico("inventado"))["id"] == 100100)

    # --- eventos REALES del laboratorio (exportados por e2e/test_reinicio.py) ---
    reales = [json.loads(x) for x in (DIR / "eventos_ejemplo.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    chk("eventos_ejemplo.jsonl: eventos reales con los 11 campos", reales and all(tuple(sorted(e)) == tuple(sorted(CAMPOS)) for e in reales))
    finales = [evaluar(reglas, e) for e in reales]
    chk("cada evento real cae en una regla propia del adaptador", all(f and f["id"] != 100100 for f in finales))
    for e, f in zip(reales, finales):
        print(f"      {e['tipo']:<24} {str(e['resultado'])[:22]:<22} -> regla {f['id']} nivel {f['nivel']}")
    print("      (simulación aproximada sin Wazuh: la correlación 100136 no se simula)")
    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
