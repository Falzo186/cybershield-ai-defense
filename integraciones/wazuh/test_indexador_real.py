"""Prueba de integración contra un Wazuh REAL. Ejecutar: python integraciones/wazuh/test_indexador_real.py

**Esta prueba NO forma parte de la batería**, y es deliberado: en esta máquina no hay ninguna instalación de
Wazuh, así que ejecutarla aquí no demostraría nada. Si se añadiera a `ejecutar_pruebas.py` con un «saltada»
en verde, el informe diría que la integración real está probada cuando no lo está.

Se ejecuta sola cuando el entorno está configurado:

    CYBERSHIELD_WAZUH=real
    WAZUH_URL=https://TU-MANAGER:55000        WAZUH_USUARIO=...           WAZUH_CLAVE=...
    WAZUH_INDEXER_URL=https://TU-INDEXER:9200 WAZUH_INDEXER_USUARIO=...   WAZUH_INDEXER_CLAVE=...
    WAZUH_TLS=0                               (solo si el certificado es autofirmado)

Sin esas variables **termina diciendo que no se ejecutó**, con código de salida 2, que no es un fallo pero
tampoco un éxito: es «no comprobado». Los requisitos de instalación están en docs/INTEGRACION_WAZUH.md.

Lo que comprueba contra la instalación real:
  - que el manager responde y da su versión;
  - que el indexador responde y da la suya;
  - que las reglas del laboratorio están cargadas en el manager;
  - que una búsqueda de alertas devuelve documentos con la forma esperada;
  - que TODA alerta leída viene marcada como real y ninguna como simulada;
  - que el cliente sigue negándose a cualquier operación que no sea de lectura, también contra el servidor
    de verdad.

Nunca escribe nada, nunca lanza una respuesta activa y nunca modifica configuración.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.lab import wazuh  # noqa: E402
from src.lab.wazuh import cliente as mod_cliente, indexador as mod_indexador  # noqa: E402
from src.lab.wazuh.cliente import ErrorWazuh  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def requisitos():
    """-> lista de variables que faltan para poder ejecutar la prueba."""
    faltan = [v for v in ("WAZUH_USUARIO", "WAZUH_CLAVE") if not os.environ.get(v)]
    if not mod_indexador.configurado():
        faltan.append("WAZUH_INDEXER_USUARIO / WAZUH_INDEXER_CLAVE")
    if (os.environ.get(wazuh.VAR_ENTORNO) or "").strip().lower() != "real":
        faltan.append(f"{wazuh.VAR_ENTORNO}=real")
    return faltan


def main():
    faltan = requisitos()
    if faltan:
        print("NO EJECUTADA: falta configurar " + ", ".join(faltan))
        print("Esto no es un éxito ni un fallo: la integración real no se ha comprobado en esta máquina.")
        print("Requisitos de instalación: docs/INTEGRACION_WAZUH.md")
        return 2

    tls = os.environ.get("WAZUH_TLS", "1") != "0"
    c = mod_cliente.ClienteWazuh(url=os.environ.get("WAZUH_URL", "https://localhost:55000"),
                                 verificar_tls=tls)
    ix = mod_indexador.ClienteIndexador(verificar_tls=tls)

    # ── Manager ───────────────────────────────────────────────────────────────────────────────────────────
    m = c.comprobar()
    chk(f"el manager responde ({m.get('version') or 'sin versión'}, {m['ms']} ms)", m["conectado"])
    if not m["conectado"]:
        print(f"\nNo se puede continuar: {m['error']}")
        print(f"Total {sum(resultados)}/{len(resultados)}")
        return 1
    r = c.reglas_cybershield()
    ids = {str(x.get("id")) for x in (((r.get("datos") or {}).get("data") or {}).get("affected_items") or [])}
    chk("las reglas del laboratorio están cargadas en el manager", r["ok"] and bool(ids))
    chk("y están las del rango 1001xx", any(i.startswith("1001") for i in ids) if ids else False)
    chk("los agentes se pueden listar (solo lectura)", c.agentes(limite=5)["ok"])

    # ── Indexador ─────────────────────────────────────────────────────────────────────────────────────────
    i = ix.comprobar()
    chk(f"el indexador responde ({i.get('version') or 'sin versión'}, {i['ms']} ms)", i["conectado"])
    if not i["conectado"]:
        print(f"\nIndexador inalcanzable: {i['error']}")
        print(f"Total {sum(resultados)}/{len(resultados)}")
        return 1

    a = ix.alertas(limite=20)
    chk("la búsqueda de alertas responde", a["ok"])
    print(f"      ({len(a['alertas'])} alertas leídas de {a['total']} en el índice {ix.indice})")
    if a["alertas"]:
        chk("TODA alerta leída del indexador viene marcada como real",
            all(x["simulado"] is False and x["origen"] == "wazuh_real" for x in a["alertas"]))
        chk("cada alerta trae marca de tiempo y regla",
            all(x["timestamp"] and x["regla_id"] is not None for x in a["alertas"]))
        chk("y el documento del que salió, para poder volver a él",
            all(x["indice"] and x["documento"] for x in a["alertas"]))
        chk("el filtro por nivel mínimo lo aplica el indexador, no este código",
            all((x["nivel"] or 0) >= 7 for x in ix.alertas(nivel_minimo=7, limite=20)["alertas"]))
    else:
        print("      Sin alertas en el índice: genere eventos en el laboratorio antes de volver a ejecutar.")

    # ── Solo lectura, también contra el servidor real ────────────────────────────────────────────────────
    for metodo, ruta in (("POST", "/_bulk"), ("POST", "/wazuh-alerts-*/_delete_by_query")):
        try:
            ix._peticion(metodo, ruta, {})
            chk(f"debía rechazar {metodo} {ruta}", False)
        except ErrorWazuh:
            chk(f"rechaza {metodo} {ruta} sin llegar al servidor", True)
    try:
        c._peticion("PUT", "/active-response", {})
        chk("debía rechazar la respuesta activa", False)
    except ErrorWazuh:
        chk("rechaza cualquier respuesta activa sin llegar al servidor", True)

    # ── La fachada en modo real ───────────────────────────────────────────────────────────────────────────
    r = wazuh.alertas(limite=5)
    chk("la fachada en modo real devuelve alertas del indexador", r["ok"] and r["modo"] == "real")
    chk("ninguna va marcada como simulada", all(not x["simulado"] for x in r["alertas"]))
    e = wazuh.estado()
    chk("el estado dice que los dos servicios están conectados",
        e["conectado"] and e["indexador"]["conectado"])

    print(f"\nTotal {sum(resultados)}/{len(resultados)}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
