"""Carga y evaluación APROXIMADA de las reglas locales de Wazuh (`integraciones/wazuh/local_rules.xml`).

Esto **no es Wazuh**. Es un modelo simplificado: decodificador JSON, campos comparados con expresiones
regulares y descenso por `if_sid` (primera regla hija que coincide, en orden). No simula correlaciones
(`frequency` / `if_matched_sid`), ni listas, ni la sintaxis exacta de OS_Regex; las reglas del laboratorio
solo usan `^`, `$` y `|`, que aquí significan lo mismo.

Sirve para dos cosas, y para ninguna más:
  - comprobar sin conexión que las reglas cubren todos los eventos que emite el laboratorio;
  - alimentar el **modo simulado** del panel, donde cada alerta va marcada como simulada.

Una alerta producida aquí NUNCA debe presentarse como una alerta de un Wazuh real.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
RUTA_REGLAS = RAIZ / "integraciones" / "wazuh" / "local_rules.xml"
RUTA_EJEMPLOS = RAIZ / "integraciones" / "wazuh" / "eventos_ejemplo.jsonl"
CAMPOS = ("timestamp", "partida", "equipo", "usuario", "rol", "tipo", "accion", "recurso", "resultado",
          "riesgo", "origen")
_VAR = re.compile(r"\$\((\w+)\)")


def cargar(ruta=RUTA_REGLAS):
    """-> (raiz_xml, lista de reglas). Lanza si el XML no es válido: eso debe fallar, no pasar inadvertido."""
    raiz = ET.parse(ruta).getroot()
    reglas = []
    for r in raiz.iter("rule"):
        reglas.append({
            "id": int(r.get("id")), "nivel": int(r.get("level")),
            "padre": r.findtext("if_sid"), "correlacion": r.findtext("if_matched_sid"),
            "json": r.findtext("decoded_as") == "json",
            "campos": {f.get("name"): f.text for f in r.findall("field")},
            "descripcion": r.findtext("description") or "",
            "grupos": [g.strip() for g in (r.findtext("group") or "").split(",") if g.strip()],
            # Sin filtrar: un id MITRE mal formado debe verse, no esconderse (lo comprueba test_reglas.py).
            "mitre": [m.text for m in r.iter("id")],
        })
    return raiz, reglas


def coincide(regla, evento):
    return all(re.search(patron, "" if evento.get(campo) is None else str(evento.get(campo)))
               for campo, patron in regla["campos"].items())


def evaluar(reglas, evento):
    """-> la regla más profunda que coincide, o None. Modelo simplificado (ver la cabecera del módulo)."""
    actual = next((r for r in reglas
                   if r["padre"] is None and r["correlacion"] is None and r["json"] and coincide(r, evento)),
                  None)
    while actual:
        hija = next((r for r in reglas if r["padre"] == str(actual["id"]) and coincide(r, actual and evento)),
                    None)
        if hija is None:
            return actual
        actual = hija
    return None


def describir(regla, evento):
    """Sustituye $(campo) en la descripción, como haría Wazuh. Un campo ausente queda como «-»."""
    def valor(m):
        v = evento.get(m.group(1))
        return "-" if v is None else str(v)   # un campo presente pero vacío también es «-»
    return _VAR.sub(valor, regla["descripcion"])


def eventos_ejemplo(ruta=RUTA_EJEMPLOS, limite=None):
    """Eventos reales de una partida jugada con el Ollama falso. Son eventos del laboratorio, de verdad;
    lo simulado es la alerta que se deduce de ellos, no el evento."""
    import json
    try:
        lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for linea in lineas:
        if not linea.strip():
            continue
        try:
            out.append(json.loads(linea))
        except ValueError:
            continue
    return out[:limite] if limite else out
