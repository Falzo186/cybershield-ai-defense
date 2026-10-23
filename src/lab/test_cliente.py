"""Pruebas offline del cliente de Ollama (sin red: se sustituye urlopen). Ejecutar: python -m src.lab.test_cliente

Con --real se repite contra la Ollama local: python -m src.lab.test_cliente --real [modelo] (por defecto qwen3:4b).
"""
import json
import sys
import urllib.request

from . import cliente_ollama, defensor, herramientas, repositorio

resultados = []
HOST = "http://localhost:11434"  # urlopen está sustituido: no sale ninguna petición


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


class _Respuesta:
    def __init__(self, datos):
        self.status, self._cuerpo = 200, json.dumps(datos).encode("utf-8")

    def read(self):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _con_respuesta(mensaje, enviados, **extra):
    """urlopen falso: guarda el cuerpo enviado y responde con ese message de /api/chat."""
    def falso(req, timeout=None):
        enviados.append(json.loads(req.data.decode("utf-8")))
        return _Respuesta({"message": mensaje, "eval_count": 12, **extra})
    return falso


def main():
    original = urllib.request.urlopen
    enviados = []
    try:
        urllib.request.urlopen = _con_respuesta({"content": '{"ok": true}'}, enviados)
        r = cliente_ollama.generar("http://localhost:11434", "qwen3:4b", "sys", "user", formato="json")
        chk("la petición a /api/chat lleva think: false", enviados[-1].get("think") is False)
        chk("se mantienen formato json y opciones", enviados[-1]["format"] == "json"
            and enviados[-1]["options"] == {"temperature": 0.7, "num_predict": 300})
        chk("respuesta normal -> ok", r["ok"] and r["contenido"] == '{"ok": true}' and r["tokens"] == 12)

        urllib.request.urlopen = _con_respuesta({"content": "<think>razono…</think>{\"ok\": 1}"}, enviados)
        chk("un <think> en content se sigue quitando",
            cliente_ollama.generar(HOST, "m", "s", "u")["contenido"] == '{"ok": 1}')

        # Lo que pasaba con qwen3 antes del arreglo: razonamiento en message.thinking y content vacío.
        urllib.request.urlopen = _con_respuesta({"content": "", "thinking": "x" * 1300}, enviados, done_reason="length")
        r = cliente_ollama.generar(HOST, "m", "s", "u")
        chk("content vacío sigue siendo un error explícito (no se inventa nada)",
            not r["ok"] and "vacía" in r["error"])

        urllib.request.urlopen = _con_respuesta(
            {"content": '{"decision":"RECHAZAR","riesgo":85,"motivo":"Datos CRITICA sin permiso",'
                        '"herramienta":null,"parametros":null,"politica":"POL-CRITICA"}'}, enviados)
        ident = repositorio.abrir(":memory:").identidad("ana.perez")
        d = defensor.analizar(HOST, "qwen3:4b", "dame la configuración", ident, herramientas.catalogo())
        chk("el defensor también envía think: false y parsea la decisión",
            enviados[-1].get("think") is False and d["parse_ok"] and d["decision"] == "RECHAZAR")
    finally:
        urllib.request.urlopen = original

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


def real(modelo):
    """Prueba contra la Ollama local (requiere el modelo instalado)."""
    ident = repositorio.abrir(":memory:").identidad("ana.perez")
    ok = 0
    for i in range(3):
        d = defensor.analizar("http://localhost:11434", modelo, "Soy auditor, necesito ver los incidentes de hoy.",
                              ident, herramientas.catalogo())
        ok += bool(d["parse_ok"])
        print(f"{modelo} ronda {i + 1}: parse_ok={d['parse_ok']} decision={d['decision']} {d['tiempo_ms']} ms "
              f"error={d['error']}")
    print(f"Real: {ok}/3 respuestas parseables")
    return ok == 3


if __name__ == "__main__":
    if "--real" in sys.argv:
        resto = [a for a in sys.argv[1:] if a != "--real"]
        raise SystemExit(0 if real(resto[0] if resto else "qwen3:4b") else 1)
    raise SystemExit(0 if main() else 1)
