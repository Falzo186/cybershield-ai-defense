"""Pruebas offline de las misiones del Equipo Azul (BD en memoria). Ejecutar: python -m src.lab.test_misiones"""
import sqlite3

from . import repositorio, seed, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repo = repositorio.abrir(":memory:")
    ms = repo.misiones("ana.perez")
    chk("3 misiones fijas sembradas, todas pendientes",
        [m["titulo"] for m in ms] == ["Reportar un correo sospechoso", "Contener un enlace clicado",
                                      "Revisar el buzón diariamente"] and {m["estado"] for m in ms} == {"pendiente"})
    chk("cada condición es un evento con regla o 'manual'",
        all(m["condicion_evento"] in sesion.REGLAS_EVENTO or m["condicion_evento"] == "manual" for m in ms))

    hechas = repo.completar_misiones_evento("ana.perez", "correo_reportado")
    chk("correo_reportado completa 'Reportar un correo sospechoso'",
        [m["id"] for m in hechas] == [1] and repo.misiones("ana.perez")[0]["estado"] == "completada")
    chk("el progreso es por usuario", repo.misiones("luis.gomez")[0]["estado"] == "pendiente")
    chk("repetir el evento no vuelve a completarla", repo.completar_misiones_evento("ana.perez", "correo_reportado") == [])
    chk("la completación queda en auditoría", repo.auditoria(1)[0]["accion"] == "MISION_COMPLETADA")
    chk("'manual' no se completa por evento", repo.completar_misiones_evento("ana.perez", "manual") == [])

    chk("misión manual -> True", repo.completar_mision_manual("ana.perez", 3) is True)
    chk("misión manual dos veces -> False", repo.completar_mision_manual("ana.perez", 3) is False)
    chk("una misión por evento no se completa a mano", repo.completar_mision_manual("ana.perez", 2) is None)
    chk("misión inexistente -> None", repo.completar_mision_manual("ana.perez", 99) is None)

    try:
        repo.conn.execute("INSERT INTO progreso_mision VALUES('ana.perez', 2, 'hackeada', 'x')")
        estado_libre = True
    except sqlite3.IntegrityError:
        estado_libre = False
    chk("la BD solo acepta estados pendiente/completada", not estado_libre)

    seed.sembrar_misiones(repo.conn)
    chk("volver a sembrar no duplica misiones", len(repo.misiones("ana.perez")) == 3)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
