"""Pruebas del formato de eventos para un SIEM (data/eventos.jsonl), sin Wazuh. Ejecutar: python -m src.lab.test_eventos"""
import json
import tempfile
from datetime import datetime
from pathlib import Path

from . import herramientas as H
from . import repositorio

resultados = []
CAMPOS = {"timestamp", "partida", "equipo", "usuario", "rol", "tipo", "accion", "recurso", "resultado", "riesgo",
          "origen"}


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    chk("una BD en memoria no escribe eventos por defecto", repositorio.abrir(":memory:").ruta_eventos is None)
    with tempfile.TemporaryDirectory() as d:
        archivo = Path(d) / "eventos.jsonl"
        repo = repositorio.abrir(":memory:", ruta_eventos=archivo)
        previo, repositorio.PARTIDA = repositorio.PARTIDA, "p-test"
        try:
            ana = repo.identidad("ana.perez")
            H.ejecutar_herramienta("consultar_inventario", {}, ana, repo)     # permitido: no es evento relevante
            H.ejecutar_herramienta("consultar_configuracion_admin", {}, ana, repo)  # autorización denegada
            c = repo.crear_correo("p-test", "recursos_humanos", "ana.perez")
            enlace = repo.buzon("p-test", "ana.perez")[0]["enlace"][3:]
            repo.registrar_clic(enlace)
            repo.contener_enlace("p-test", "ana.perez", c["id"])
            repo.registrar_clic(enlace)
            repo.reportar_correo("p-test", "ana.perez", c["id"])
            repo.evento_pdf("p-test", "ana.perez", c["id"], "pdf_abierto")
            repo.evento_pdf("p-test", "ana.perez", c["id"], "pdf_reportado")
            repo.completar_misiones_evento("p-test", "ana.perez", "pdf_abierto")
        finally:
            repositorio.PARTIDA = previo
        lineas = [json.loads(x) for x in archivo.read_text(encoding="utf-8").splitlines()]

    tipos = [e["tipo"] for e in lineas]
    chk("se escriben solo los eventos relevantes, en orden",
        tipos == ["autorizacion_denegada", "clic_enlace", "enlace_contenido", "clic_bloqueado", "correo_reportado",
                  "pdf_abierto", "pdf_reportado", "mision_completada"])
    chk("cada línea trae todos los campos", all(set(e) == CAMPOS for e in lineas))
    chk("timestamp ISO 8601 con zona", all(datetime.fromisoformat(e["timestamp"]).tzinfo is not None for e in lineas))
    chk("partida y origen en cada evento", {(e["partida"], e["origen"]) for e in lineas} == {("p-test", "cybershield-lab")})
    den = lineas[0]
    chk("autorización denegada: recurso, resultado y riesgo de la auditoría",
        (den["recurso"], den["resultado"], den["riesgo"], den["equipo"]) == ("configuracion_admin", "DENEGADO", "CRITICO", None))
    chk("eventos del buzón con equipo azul y su usuario",
        all(e["equipo"] == "azul" and e["usuario"] == "ana.perez" for e in lineas[1:]))
    chk("el JSONL coincide con la auditoría (mismo punto de registro)",
        [e["accion"] for e in lineas[1:]] == [a["accion"] for a in reversed(repo.auditoria(500))
                                             if a["accion"] in repositorio.EVENTOS_SIEM])

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
