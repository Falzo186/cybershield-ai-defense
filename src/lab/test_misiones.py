"""Pruebas offline de las misiones del Equipo Azul (BD en memoria). Ejecutar: python -m src.lab.test_misiones"""
import sqlite3

from . import repositorio, seed, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repo = repositorio.abrir(":memory:")
    ms = repo.misiones("p1", "ana.perez")
    chk("4 misiones fijas sembradas, todas pendientes",
        [m["titulo"] for m in ms] == ["Reportar un correo sospechoso", "Contener un enlace clicado",
                                      "Revisar el buzón diariamente", "Revisar un documento recibido"]
        and {m["estado"] for m in ms} == {"pendiente"})
    chk("cada condición es un evento con regla o 'manual'",
        all(m["condicion_evento"] in sesion.REGLAS_EVENTO or m["condicion_evento"] == "manual" for m in ms))

    hechas = repo.completar_misiones_evento("p1", "ana.perez", "correo_reportado")
    chk("correo_reportado completa 'Reportar un correo sospechoso'",
        [m["id"] for m in hechas] == [1] and repo.misiones("p1", "ana.perez")[0]["estado"] == "completada")
    chk("el progreso es por usuario", repo.misiones("p1", "luis.gomez")[0]["estado"] == "pendiente")
    chk("el progreso es por partida: una partida nueva arranca limpia",
        {m["estado"] for m in repo.misiones("p2", "ana.perez")} == {"pendiente"})
    chk("repetir el evento no vuelve a completarla", repo.completar_misiones_evento("p1", "ana.perez", "correo_reportado") == [])
    chk("la completación queda en auditoría", repo.auditoria(1)[0]["accion"] == "MISION_COMPLETADA")
    chk("'manual' no se completa por evento", repo.completar_misiones_evento("p1", "ana.perez", "manual") == [])

    chk("misión manual -> True", repo.completar_mision_manual("p1", "ana.perez", 3) is True)
    chk("misión manual dos veces -> False", repo.completar_mision_manual("p1", "ana.perez", 3) is False)
    chk("una misión por evento no se completa a mano", repo.completar_mision_manual("p1", "ana.perez", 2) is None)
    chk("misión inexistente -> None", repo.completar_mision_manual("p1", "ana.perez", 99) is None)

    try:
        repo.conn.execute("INSERT INTO progreso_mision VALUES('p1', 'ana.perez', 2, 'hackeada', 'x')")
        estado_libre = True
    except sqlite3.IntegrityError:
        estado_libre = False
    chk("la BD solo acepta estados pendiente/completada", not estado_libre)

    chk("'Contener un enlace clicado' se completa con enlace_contenido",
        [m["id"] for m in repo.completar_misiones_evento("p1", "ana.perez", "enlace_contenido")] == [2])
    chk("CLIC_ENLACE no completa ninguna misión", repo.completar_misiones_evento("p1", "luis.gomez", "CLIC_ENLACE") == [])

    repo.conn.execute("UPDATE misiones SET condicion_evento='CLIC_ENLACE' WHERE id=2")  # definición vieja
    seed.sembrar_misiones(repo.conn)
    chk("volver a sembrar no duplica y actualiza la definición",
        len(repo.misiones("p1", "ana.perez")) == 4 and repo.misiones("p1", "ana.perez")[1]["condicion_evento"] == "enlace_contenido")
    chk("re-sembrar conserva el progreso", repo.misiones("p1", "ana.perez")[1]["estado"] == "completada")

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
