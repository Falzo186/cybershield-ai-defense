"""Pruebas del Wazuh SIMULADO. Ejecutar: python -m src.lab.test_wazuh_sim

Todo es simulación; lo que se comprueba es el contrato (esquema, idempotencia, correlación, ruido, ocultación de la
verdad de fondo y que el proveedor real NO inventa respuestas).
"""
import json
import os
import tempfile
from pathlib import Path

from .wazuh_sim import AGENTES, ETIQUETA, REGLAS, RealProvider, SimProvider, WazuhProvider

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def ev(clave="solicitud.referencia_invalida", turno=1, pid="p1", id_ev="e1", rel=True, ag="srv-bd"):
    return {"partida_id": pid, "turno": turno, "ts": "2026-11-18T10:00:07.000-06:00", "clave": clave, "agente": ag, "relevante": rel,
            "id_evento": id_ev, "data": {"x": 1}, "full_log": "log de prueba"}


def main():
    nd = Path(tempfile.mkdtemp()) / "alerts.ndjson"
    w = SimProvider(ruta_ndjson=nd, semilla=7)
    ids = w.alimentar(ev())
    al = w.consultar_alertas("p1")
    a = [x for x in al if x["rule"]["id"] == "100010"][0]
    chk("es un WazuhProvider con modo «simulado»", isinstance(w, WazuhProvider) and w.modo == "simulado" and w.estado()["etiqueta"] == ETIQUETA)
    chk("esquema: id, timestamp ISO con zona, rule{id,level,description,groups,mitre}, agent, manager, decoder, location, full_log, data, lab",
        all(k in a for k in ("id", "timestamp", "rule", "agent", "manager", "decoder", "location", "full_log", "data", "lab"))
        and all(k in a["rule"] for k in ("id", "level", "description", "groups", "mitre")) and a["timestamp"].endswith("-06:00"))
    chk("mitre con id, tactic y technique", a["rule"]["mitre"]["id"] == ["T1566"] and a["rule"]["mitre"]["tactic"] and a["rule"]["mitre"]["technique"])
    chk("campo propio lab{partida_id, turno, simulado:true}", a["lab"]["partida_id"] == "p1" and a["lab"]["turno"] == 1 and a["lab"]["simulado"] is True)
    chk("reglas con ids ≥ 100000 y niveles 0-15", all(int(r[0]) >= 100000 and 0 <= r[1] <= 15 for r in REGLAS.values()))
    chk("hay 4 agentes ficticios con id, nombre, IP privada, SO y grupo",
        len(AGENTES) == 4 and all(x["ip"].startswith("10.") and x["os"] and x["group"] for x in AGENTES))
    n = len(al)
    chk("ruido de fondo: 3 a 6 alertas benignas por cada alerta relevante", 4 <= n <= 7 and all(x["rule"]["level"] <= 4 for x in al if x["rule"]["id"] != "100010"))
    n_antes = w.db.execute("SELECT COUNT(*) FROM alertas").fetchone()[0]
    w.alimentar(ev())
    chk("idempotencia: reinyectar el mismo evento no duplica (ni alertas ni ruido)", w.db.execute("SELECT COUNT(*) FROM alertas").fetchone()[0] == n_antes)
    chk("el NDJSON append-only no duplica tampoco", len(nd.read_text(encoding="utf-8").splitlines()) == n_antes)
    w2 = SimProvider(semilla=7)
    w2.alimentar(ev())
    chk("ruido y ids reproducibles con la misma semilla", [x["id"] for x in w2.consultar_alertas("p1")] == [x["id"] for x in al])
    w3 = SimProvider(semilla=8)
    w3.alimentar(ev())
    chk("otra semilla -> otro ruido", [x["rule"]["id"] for x in w3.consultar_alertas("p1")] != [x["rule"]["id"] for x in al] or
        [x["id"] for x in w3.consultar_alertas("p1")] != [x["id"] for x in al])
    w.alimentar(ev(pid="p2", id_ev="z"))
    chk("correlación por partida_id: p1 y p2 no se mezclan", all(x["lab"]["partida_id"] == "p1" for x in w.consultar_alertas("p1"))
        and w.consultar_alertas("p2") and all(x["lab"]["partida_id"] == "p2" for x in w.consultar_alertas("p2")))
    chk("filtros por nivel mínimo, grupo y agente",
        all(x["rule"]["level"] >= 8 for x in w.consultar_alertas("p1", nivel_min=8)) and
        all("ingenieria_social" in x["rule"]["groups"] for x in w.consultar_alertas("p1", grupos=["ingenieria_social"])) and
        all(x["agent"]["name"] == "srv-bd" for x in w.consultar_alertas("p1", agente="srv-bd")))
    chk("la verdad de fondo se guarda aparte y marca solo la alerta relevante",
        sum(w.verdad_de_fondo("p1").values()) == 1 and len(w.alertas_relevantes("p1")) == 1)
    chk("consultar_alertas nunca expone `relevante`", "relevante" not in json.dumps(w.consultar_alertas("p1")))
    chk("una clave desconocida no inventa alertas", w.alimentar(ev(clave="inventada")) == [])
    r = RealProvider(env={})
    chk("RealProvider sin variables: desconectado y sin inventar respuestas", r.modo == "desconectado" and r.estado()["simulado"] is False)
    try:
        r.consultar_alertas("p1")
        chk("RealProvider no devuelve alertas inventadas", False)
    except NotImplementedError:
        chk("RealProvider no devuelve alertas inventadas (stub explícito)", True)
    rc = RealProvider(env={"WAZUH_URL": "https://x", "WAZUH_USUARIO": "u", "WAZUH_CLAVE": "c"})
    chk("RealProvider configurado pero sin implementación real: «con_errores» (visible, no se disfraza)", rc.modo == "con_errores")
    if os.environ.get("WAZUH_URL"):
        chk("(condicional) hay instancia real: prueba de humo omitida a propósito, el stub no la consulta", True)
    else:
        print("OMITIDA  integración con instancia real de Wazuh: no hay WAZUH_URL (esperado en este laboratorio)")
    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
