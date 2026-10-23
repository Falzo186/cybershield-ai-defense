"""Pruebas offline del puntaje de Rojo (BD en memoria). Ejecutar: python -m src.lab.test_puntaje"""
from . import repositorio, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    chk("puntaje: +10 por enlace sin contener, +5 por PDF sin reportar", sesion.puntaje_rojo(2, 3) == 35)

    repo = repositorio.abrir(":memory:")
    pts = lambda: sesion.puntaje_rojo(**repo.logros_rojo("p1"))  # noqa: E731
    chk("sin eventos, Rojo tiene 0", pts() == 0)
    a = repo.crear_correo("p1", "soporte_tecnico", "ana.perez")
    b = repo.crear_correo("p1", "recursos_humanos", "ana.perez")
    enlaces = {c["id"]: c["enlace"][3:] for c in repo.buzon("p1", "ana.perez")}
    repo.registrar_clic(enlaces[a["id"]])
    repo.registrar_clic(enlaces[a["id"]])
    chk("un enlace clicado (aunque sea dos veces) vale +10 una vez", pts() == 10)
    repo.evento_pdf("p1", "ana.perez", b["id"], "pdf_abierto")
    repo.evento_pdf("p1", "ana.perez", b["id"], "pdf_abierto")
    chk("un PDF abierto (aunque sea dos veces) vale +5 una vez", pts() == 15)
    repo.contener_enlace("p1", "ana.perez", a["id"])
    chk("contener el enlace le quita esos 10 a Rojo", pts() == 5)
    repo.evento_pdf("p1", "ana.perez", b["id"], "pdf_reportado")
    chk("reportar el PDF le quita esos 5 a Rojo", pts() == 0)
    repo.registrar_clic(enlaces[a["id"]])
    chk("un clic sobre un enlace ya contenido no suma", pts() == 0)

    c = repo.crear_correo("p2", "paqueteria", "ana.perez")
    repo.evento_pdf("p2", "ana.perez", c["id"], "pdf_reportado")
    chk("reportar un PDF sin abrirlo no da puntos a Rojo", sesion.puntaje_rojo(**repo.logros_rojo("p2")) == 0)
    chk("el puntaje es por partida", pts() == 0 and repo.logros_rojo("otra") == {"enlaces_sin_contener": 0,
                                                                               "pdfs_sin_reportar": 0})

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
