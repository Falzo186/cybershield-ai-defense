"""Pruebas offline del motor de reglas evento -> consecuencia (BD en memoria). Ejecutar: python -m src.lab.test_reglas"""
from . import repositorio, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    # --- REGLAS_EVENTO sobre EstadoSesion ---
    s = sesion.EstadoSesion()
    chk("evento sin regla -> None y sin cambios", s.aplicar_evento("evento_inventado") is None and s.riesgo_acumulado == 0)
    r = s.aplicar_evento("CLIC_ENLACE")
    chk("CLIC_ENLACE suma 15", r["riesgo"] == 15 and s.riesgo_acumulado == 15 and r["mision"] is False)
    s.aplicar_evento("CLIC_ENLACE")
    r = s.aplicar_evento("correo_reportado")
    chk("correo_reportado resta 10 y marca misión", r["riesgo"] == -10 and r["mision"] is True
        and s.riesgo_acumulado == 20)
    chk("la regla es determinista (mismo evento, misma consecuencia)",
        sesion.EstadoSesion().aplicar_evento("CLIC_ENLACE")["riesgo_acumulado"] == 15)

    s = sesion.EstadoSesion()
    s.aplicar_evento("correo_reportado")
    chk("un reporte no deja saldo negativo", s.riesgo_acumulado == 0)
    s.aplicar_evento("CLIC_ENLACE")
    chk("tras reportar sin riesgo previo, un clic vuelve a sumar 15", s.riesgo_acumulado == 15)
    for _ in range(10):
        s.aplicar_evento("CLIC_ENLACE")
    chk("el riesgo por eventos tiene techo 100", s.riesgo_acumulado == 100)
    chk("eventos_vistos cuenta por evento", s.eventos_vistos == {"correo_reportado": 1, "CLIC_ENLACE": 11})

    s = sesion.EstadoSesion()
    s.registrar("rol_falso", "DEFENSA_EXITOSA", "RECHAZAR")
    s.registrar("rol_falso", "DEFENSA_EXITOSA", "RECHAZAR")
    s.aplicar_evento("CLIC_ENLACE")
    chk("los eventos se suman al riesgo de las rondas", s.riesgo_acumulado == 8 + 15)
    s = sesion.EstadoSesion()
    s.aplicar_evento("CLIC_ENLACE")
    chk("pdf_abierto no suma riesgo y marca misión", s.aplicar_evento("pdf_abierto")["riesgo"] == 0
        and s.riesgo_acumulado == 15 and sesion.REGLAS_EVENTO["pdf_abierto"]["mision"] is True)
    r = s.aplicar_evento("pdf_reportado")
    chk("pdf_reportado resta 10 sin misión", r["riesgo"] == -10 and r["mision"] is False and s.riesgo_acumulado == 5)
    s = sesion.EstadoSesion()
    s.aplicar_evento("CLIC_ENLACE")
    r = s.aplicar_evento("enlace_contenido")
    chk("enlace_contenido resta 15 (anula el clic) y marca misión",
        r["riesgo"] == -15 and r["mision"] is True and s.riesgo_acumulado == 0)

    # --- reporte de correos en el repositorio ---
    repo = repositorio.abrir(":memory:")
    c = repo.crear_correo("p1", "soporte_tecnico", "ana.perez")
    otro = repo.crear_correo("p1", "paqueteria", "luis.gomez")
    viejo = repo.crear_correo("p0", "paqueteria", "ana.perez")
    chk("reportar un correo propio -> True", repo.reportar_correo("p1", "ana.perez", c["id"]) is True)
    aud = repo.auditoria(1)[0]
    chk("el reporte queda en auditoría", aud["accion"] == "CORREO_REPORTADO" and aud["usuario"] == "ana.perez")
    chk("reportar dos veces -> False", repo.reportar_correo("p1", "ana.perez", c["id"]) is False)
    chk("no se reporta el correo de otro usuario", repo.reportar_correo("p1", "ana.perez", otro["id"]) is None)
    chk("no se reporta un correo de otra partida", repo.reportar_correo("p1", "ana.perez", viejo["id"]) is None)
    chk("el buzón marca el correo como reportado",
        [x["reportado"] for x in repo.buzon("p1", "ana.perez")] == [1])

    # --- contención de enlaces (solo después de un clic) ---
    chk("contener sin clic previo -> sin_clic", repo.contener_enlace("p1", "ana.perez", c["id"]) == "sin_clic")
    chk("contener el correo de otro usuario -> None", repo.contener_enlace("p1", "ana.perez", otro["id"]) is None)
    enlace_id = repo.buzon("p1", "ana.perez")[0]["enlace"][3:]
    repo.registrar_clic(enlace_id)
    chk("el buzón marca el correo como clicado", repo.buzon("p1", "ana.perez")[0]["clicado"] == 1)
    chk("contener tras el clic -> contenido", repo.contener_enlace("p1", "ana.perez", c["id"]) == "contenido")
    chk("la contención queda en auditoría", repo.auditoria(1)[0]["accion"] == "ENLACE_CONTENIDO")
    chk("contener dos veces -> ya_contenido", repo.contener_enlace("p1", "ana.perez", c["id"]) == "ya_contenido")
    clic = repo.registrar_clic(enlace_id)
    chk("un clic sobre un enlace contenido queda BLOQUEADO",
        clic["contenido"] is True and repo.auditoria(1)[0]["accion"] == "CLIC_BLOQUEADO")

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
