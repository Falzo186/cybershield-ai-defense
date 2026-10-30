"""Pruebas de la lógica pura de los ataques IA de la partida (Fase F). Ejecutar: python -m src.lab.test_ataque_ia"""
from . import ataque_ia, repositorio, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def r(veredicto, ok=None, sens=None):
    return {"veredicto": veredicto, "ejecucion": None if ok is None else {"ok": ok, "sensibilidad": sens}}


def main():
    c = ataque_ia.clasificar
    chk("ERROR del defensor -> fallo seguro, 0 / 0", c(r("ERROR"), "invitado") ==
        {"resultado": "fallo_seguro", "puntos_rojo": 0, "puntos_azul": 0, "sensibilidad_expuesta": None})
    chk("defensa exitosa -> contenido, +5 Azul", (c(r("DEFENSA_EXITOSA"), "invitado")["resultado"],
                                                c(r("DEFENSA_EXITOSA"), "invitado")["puntos_azul"]) == ("contenido", 5))
    x = c(r("DEFENSA_EN_PROFUNDIDAD", False, "INTERNA"), "invitado")
    chk("IA engañada frenada por una capa -> +5 Rojo, sin datos", (x["resultado"], x["puntos_rojo"], x["puntos_azul"],
                                                                     x["sensibilidad_expuesta"]) == ("ia_enganada", 5, 0, None))
    x = c(r("PERMITIDO_CORRECTO", True, "INTERNA"), "credencial_robada")
    chk("petición válida con credencial robada que devuelve INTERNA -> datos expuestos +10",
        (x["resultado"], x["puntos_rojo"], x["sensibilidad_expuesta"]) == ("datos_expuestos", 10, "INTERNA"))
    x = c(r("PERMITIDO_CORRECTO", True, "CONFIDENCIAL"), "credencial_robada")
    chk("… CONFIDENCIAL -> +20", x["puntos_rojo"] == ataque_ia.PUNTOS_DATOS["CONFIDENCIAL"] == 20)
    x = c(r("PERMITIDO_CORRECTO", True, "PUBLICA"), "credencial_robada")
    chk("datos PÚBLICOS con credencial robada no son una fuga (0 puntos)", (x["resultado"], x["puntos_rojo"]) == ("legitimo", 0))
    x = c(r("PERMITIDO_CORRECTO", True, "PUBLICA"), "invitado")
    chk("invitado que lee datos públicos -> sin impacto", (x["resultado"], x["puntos_rojo"], x["puntos_azul"]) == ("legitimo", 0, 0))
    x = c(r("FALLA_DEFENSA", True, "CRITICA"), "invitado")
    chk("FALLA_DEFENSA (sin derecho) con CRITICA -> datos expuestos +30", (x["resultado"], x["puntos_rojo"]) == ("datos_expuestos", 30))

    e = ataque_ia.explicar
    t = e("datos_expuestos", "ana.perez", "credencial_robada", "INTERNA")
    chk("la explicación de una fuga con credencial robada dice acción, control que falló y cómo se evita",
        "ana.perez" in t and "Control que falló" in t and "revocándola" in t)
    t = e("ia_enganada", "visita.demo", "invitado", capa="permisos")
    chk("la de IA engañada nombra la capa que frenó", "«permisos»" in t and "Control que falló" in t)
    chk("la de fallo seguro dice que no se ejecutó nada y por qué", "no se ejecuta nada" in e(
        "fallo_seguro", "visita.demo", "invitado", error="HTTP 500") and "HTTP 500" in e("fallo_seguro", "x", "invitado", error="HTTP 500"))
    chk("la del filtro rápido lo menciona", "filtro rápido" in e("contenido", "x", "invitado", filtro=True))
    chk("todo resultado con regla tiene su explicación general en REGLAS_EVENTO",
        all(ev in sesion.REGLAS_EVENTO and sesion.REGLAS_EVENTO[ev]["explicacion"] for ev in ataque_ia.EVENTO.values()))
    chk("todos los resultados tienen título para la UI", set(ataque_ia.TITULO) == set(ataque_ia.RESULTADOS))

    # --- repositorio: identidad del atacante y tope de ataques ---
    repo = repositorio.abrir(":memory:")
    chk("sin compromiso, la IA de Rojo ataca como invitado", repo.identidad_atacante("p1") == ("visita.demo", "invitado"))
    cid = repo.crear_correo("p1", "soporte_tecnico", "ana.perez")["id"]
    repo.conn.execute("INSERT INTO compromisos_credencial(partida,usuario,correo_id,ts) VALUES('p1','ana.perez',?, 't')", (cid,))
    chk("con una credencial comprometida sin revocar, ataca como esa cuenta",
        repo.identidad_atacante("p1") == ("ana.perez", "credencial_robada"))
    chk("el compromiso es por partida (otra partida sigue como invitado)", repo.identidad_atacante("p2")[1] == "invitado")
    repo.revocar_credencial("p1", "ana.perez", "Bea")
    chk("al revocarla vuelve a invitado", repo.identidad_atacante("p1")[1] == "invitado")
    ids = [repo.crear_ataque_ia("p1", "Rita", "visita.demo", "invitado", None, 2, "m", "d") for _ in range(ataque_ia.MAX_ATAQUES + 1)]
    chk(f"el repositorio reserva como mucho {ataque_ia.MAX_ATAQUES} ataques por partida",
        [a["n"] for a in ids[:-1]] == list(range(1, ataque_ia.MAX_ATAQUES + 1)) and ids[-1] is None)
    try:
        repo.cerrar_ataque_ia(ids[0]["id"], partida="otra")
        chk("cerrar un ataque solo acepta columnas permitidas", False)
    except ValueError:
        chk("cerrar un ataque solo acepta columnas permitidas", True)
    repo.cerrar_ataque_ia(ids[0]["id"], estado="terminado", resultado="contenido", puntos_azul=5)
    repo.cerrar_ataque_ia(ids[1]["id"], estado="terminado", resultado="datos_expuestos", puntos_rojo=10)
    chk("los puntos IA se suman desde los ataques guardados", repo.puntos_ia("p1") ==
        {"rojo": 10, "azul": 5, "lanzados": ataque_ia.MAX_ATAQUES, "datos_expuestos": 1, "contenidos": 1})
    try:
        repo.conn.execute("INSERT INTO ataques_ia(partida,n,usuario,origen_identidad,intensidad,estado,ts_inicio) "
                          "VALUES('p9',1,'visita.demo','inventado',2,'en_curso','t')")
        chk("la tabla rechaza un origen de identidad inventado", False)
    except Exception:  # noqa: BLE001 - CHECK de SQLite
        chk("la tabla rechaza un origen de identidad inventado", True)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
