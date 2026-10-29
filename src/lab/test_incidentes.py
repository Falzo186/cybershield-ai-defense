"""Pruebas offline de la Fase E: misiones con responsable, plazo, evidencia y dependencias; incidentes; credenciales
ficticias comprometidas/revocadas (BD en memoria). Ejecutar: python -m src.lab.test_incidentes"""
import sqlite3

from . import repositorio, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repo = repositorio.abrir(":memory:")
    P, U = "p1", "ana.perez"
    m = {x["id"]: x for x in repo.misiones(P, U)}

    # --- definición de las misiones ---
    chk("cada misión trae prioridad, descripción y dependencias",
        all(x["prioridad"] in ("alta", "media", "baja") and x["descripcion"] for x in m.values())
        and m[7]["depende_de"] == [6] and m[8]["depende_de"] == [6])
    chk("toda condición es un evento con regla o 'manual'",
        all(x["condicion_evento"] in sesion.REGLAS_EVENTO or x["condicion_evento"] == "manual" for x in m.values()))
    chk("toda misión por evento tiene su regla con mision=True",
        all(sesion.REGLAS_EVENTO[x["condicion_evento"]]["mision"] for x in m.values() if x["condicion_evento"] != "manual"))
    chk("revocar sin incidente abierto: bloqueada y explica qué falta",
        m[7]["estado"] == "bloqueada" and m[7]["requiere"] == ["Abrir un incidente de seguridad"])

    # --- responsable ---
    chk("asumir una misión", repo.asumir_mision(P, U, 1, "Beto") is True and repo.misiones(P, U)[0]["responsable"] == "Beto")
    chk("reasignarla a otro participante", repo.asumir_mision(P, U, 1, "Bea") is True
        and repo.misiones(P, U)[0]["responsable"] == "Bea")
    chk("asumir una misión inexistente -> None", repo.asumir_mision(P, U, 99, "Beto") is None)

    # --- plazo y evidencia ---
    h = repo.completar_misiones_evento(P, U, "correo_reportado", "Beto", "correo:7", transcurrido_s=30)
    chk("dentro de plazo: puntos completos, quién y evidencia",
        h and (h[0]["puntos_obtenidos"], h[0]["a_tiempo"], h[0]["completada_por"], h[0]["evidencia"])
        == (10, True, "Beto", "correo:7"))
    chk("asumir una misión completada -> 'completada'", repo.asumir_mision(P, U, 1, "Beto") == "completada")
    chk("pasado el plazo una misión pendiente aparece vencida",
        next(x for x in repo.misiones(P, U, transcurrido_s=200) if x["id"] == 5)["estado"] == "vencida")
    h = repo.completar_misiones_evento(P, U, "remitente_verificado", "Bea", "correo:7", transcurrido_s=200)
    chk("fuera de plazo vale la mitad (5 -> 2)", h and (h[0]["puntos_obtenidos"], h[0]["a_tiempo"]) == (2, False))
    chk("los puntos de Azul suman lo obtenido (10 + 2)", repo.puntos_azul(P, U) == 12)
    chk("sin reloj nada vence", sesion.puntos_mision(10, 60, None) == (10, True))

    # --- credenciales ficticias ---
    sop = repo.crear_correo(P, "soporte_tecnico", U)["id"]
    paq = repo.crear_correo(P, "paqueteria", U)["id"]
    enl = {c["id"]: c["enlace"][3:] for c in repo.buzon(P, U)}
    chk("sin clic previo no hay compromiso", repo.comprometer_credencial(P, enl[sop]) == "sin_clic")
    repo.registrar_clic(enl[sop])
    repo.registrar_clic(enl[paq])
    chk("una plantilla que no pide credenciales no compromete nada", repo.comprometer_credencial(P, enl[paq]) == "no_pide")
    chk("un enlace de otra partida no existe para esta", repo.comprometer_credencial("p2", enl[sop]) == "no_existe")
    r = repo.comprometer_credencial(P, enl[sop])
    chk("enviar la contraseña en la página falsa compromete la credencial", r == {"usuario": U, "correo_id": sop, "nuevo": True})
    chk("queda en auditoría como CRITICO", repo.auditoria(1)[0]["accion"] == "CREDENCIAL_COMPROMETIDA"
        and repo.auditoria(1)[0]["nivel_riesgo"] == "CRITICO")
    chk("enviarla otra vez no la duplica", repo.comprometer_credencial(P, enl[sop])["nuevo"] is False)
    chk("estado de la credencial: comprometida", repo.credenciales(P, U)["estado"] == "comprometida")
    chk("Rojo suma +15 por la credencial sin revocar",
        repo.logros_rojo(P)["credenciales_sin_revocar"] == 1 and sesion.PUNTOS_ROJO["credencial_sin_revocar"] == 15)
    chk("Rojo ve en su campaña la credencial obtenida",
        next(c for c in repo.enviados_rojo(P) if c["id"] == sop)["credencial_obtenida"] == 1)
    repo.contener_enlace(P, U, sop)
    chk("contener el enlace NO revoca la credencial", repo.logros_rojo(P)["credenciales_sin_revocar"] == 1)
    chk("con el enlace contenido ya no se puede volver a enviar", repo.comprometer_credencial(P, enl[sop]) == "contenido")

    # --- incidentes ---
    try:
        repo.abrir_incidente(P, U, "Beto", "x", "alta")
        corto = False
    except ValueError:
        corto = True
    chk("un título demasiado corto se rechaza", corto)
    try:
        repo.abrir_incidente(P, U, "Beto", "Phishing", "apocaliptica")
        sev = False
    except ValueError:
        sev = True
    chk("una severidad desconocida se rechaza", sev)
    otro = repo.crear_correo(P, "paqueteria", "luis.gomez")["id"]
    chk("un correo de otro buzón no se puede asociar", repo.abrir_incidente(P, U, "Beto", "Phishing", "alta", otro) is None)
    inc = repo.abrir_incidente(P, U, "Beto", "Phishing de soporte", "alta", sop)
    chk("abrir un incidente", inc["estado"] == "abierto" and inc["abierto_por"] == "Beto" and inc["correo_id"] == sop)
    try:
        repo.avanzar_incidente(P, U, inc["id"], "Beto", "resuelto", "Credencial revocada y enlace contenido.")
        salto = False
    except ValueError:
        salto = True
    chk("no se puede saltar de abierto a resuelto", salto)
    chk("abierto -> en investigación", repo.avanzar_incidente(P, U, inc["id"], "Bea", "en_investigacion")["estado"]
        == "en_investigacion")
    try:
        repo.avanzar_incidente(P, U, inc["id"], "Bea", "resuelto", "Enlace contenido, todo bien.")
        motivo = ""
    except ValueError as e:
        motivo = str(e)
    chk("no se resuelve con la credencial aún comprometida (y lo explica)", "credencial" in motivo)
    chk("hasta que se completa «Abrir un incidente», revocar sigue bloqueada",
        next(x for x in repo.misiones(P, U) if x["id"] == 7)["estado"] == "bloqueada")
    repo.completar_misiones_evento(P, U, "incidente_abierto", "Beto", f"incidente:{inc['id']}")
    chk("con el incidente abierto, la misión de revocar se desbloquea",
        next(x for x in repo.misiones(P, U) if x["id"] == 7)["estado"] == "pendiente")
    chk("revocar la credencial", repo.revocar_credencial(P, U, "Bea") == "revocada"
        and repo.credenciales(P, U)["estado"] == "revocada")
    chk("revocarla dos veces -> sin_compromiso", repo.revocar_credencial(P, U, "Bea") == "sin_compromiso")
    chk("Rojo pierde los puntos de la credencial", repo.logros_rojo(P)["credenciales_sin_revocar"] == 0)
    try:
        repo.avanzar_incidente(P, U, inc["id"], "Bea", "resuelto", "corto")
        breve = False
    except ValueError:
        breve = True
    chk("la resolución debe explicar lo que se hizo (10-500)", breve)
    inc = repo.avanzar_incidente(P, U, inc["id"], "Bea", "resuelto", "Credencial revocada y enlace contenido.")
    chk("resolver el incidente", inc["estado"] == "resuelto" and inc["resuelto_por"] == "Bea" and inc["ts_resolucion"])
    chk("un incidente resuelto no se reabre", _rechaza(lambda: repo.avanzar_incidente(P, U, inc["id"], "Bea", "abierto")))
    chk("la BD solo acepta severidades válidas", _rechaza_bd(repo, "INSERT INTO incidentes_partida(partida,titulo,"
                                                                   "severidad,estado,abierto_por,ts_apertura) "
                                                                   "VALUES('p1','abc','x','abierto','b','t')"))
    chk("la BD permite un único compromiso activo por usuario",
        _rechaza_bd(repo, f"INSERT INTO compromisos_credencial(partida,usuario,correo_id,ts) VALUES('p9','{U}',{sop},'t'),"
                          f"('p9','{U}',{sop},'t')"))
    chk("tras revocar, un nuevo envío vuelve a comprometerla (otro correo)",
        _nuevo_compromiso(repo, P, U))

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


def _nuevo_compromiso(repo, P, U):
    c = repo.crear_correo(P, "soporte_tecnico", U)["id"]
    enlace = next(x["enlace"][3:] for x in repo.buzon(P, U) if x["id"] == c)
    repo.registrar_clic(enlace)
    return repo.comprometer_credencial(P, enlace)["nuevo"] and repo.credenciales(P, U)["estado"] == "comprometida"


def _rechaza(f):
    try:
        f()
    except ValueError:
        return True
    return False


def _rechaza_bd(repo, sql):
    try:
        repo.conn.execute(sql)
    except sqlite3.IntegrityError:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
