"""Pruebas del catálogo de aplicaciones por permiso, las recomendaciones de seguridad, Recursos y Ayuda (Fase B).
Ejecutar: python -m src.lab.test_apps"""
from . import apps, herramientas, permisos, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def ids(equipo):
    return [a["id"] for a in apps.catalogo(equipo)]


def main():
    chk("Rojo no tiene Misiones, Incidentes ni Seguridad", not {"misiones", "incidentes", "seguridad"} & set(ids("rojo")))
    chk("Azul tiene Correo, Archivos, Misiones, Incidentes y Seguridad",
        {"correo", "archivos", "misiones", "incidentes", "seguridad"} <= set(ids("azul")))
    chk("solo el árbitro finaliza", [e for e in apps.EQUIPOS if "finalizar" in ids(e)] == ["general"])
    chk("el espectador solo tiene aplicaciones de lectura",
        all(a["permiso"] == "lectura" for a in apps.catalogo("espectador")))
    chk("el espectador no ve Correo, Archivos ni Seguridad", not {"correo", "archivos", "seguridad"} & set(ids("espectador")))
    chk("sin sesión cuenta como espectador", apps.catalogo(None) == apps.catalogo("espectador")
        and apps.permiso("auditoria", None) == "lectura" and apps.permiso("correo", None) is None)
    chk("Azul gestiona su Seguridad y General solo la lee",
        (apps.permiso("seguridad", "azul"), apps.permiso("seguridad", "general")) == ("escritura", "lectura"))
    chk("una aplicación desconocida no da permiso", apps.permiso("inventada", "general") is None)
    orden = [g for g, _ in apps.GRUPOS]
    grupos = [orden.index(a["grupo"]) for a in apps.catalogo("general")]
    chk("el catálogo sale ordenado por grupo", grupos == sorted(grupos))
    chk("todas las aplicaciones tienen título, icono, grupo válido y descripción",
        all(t and ic and g in orden and d for t, ic, g, d, _ in apps.APPS.values()))
    chk("los permisos son solo lectura o escritura y los equipos, los del juego",
        all(set(p.values()) <= {apps.L, apps.E} and set(p) <= set(apps.EQUIPOS) for *_, p in apps.APPS.values()))

    base = {"credencial": "segura", "enlaces_sin_contener": 0, "pdfs_sin_reportar": 0, "defensor_ok": True,
            "defensor_modelo": "m", "incidentes_abiertos": 0, "correos_sin_revisar": 0, "riesgo": 0, "fase": "en_curso"}
    chk("sin nada pendiente lo dice (no inventa tareas)", [r["nivel"] for r in apps.recomendaciones(base)] == ["BAJO"]
        and "Nada pendiente" in apps.recomendaciones(base)[0]["texto"])
    chk("fuera de la partida, sin pendientes, la lista queda vacía", apps.recomendaciones({**base, "fase": "preparacion"}) == [])
    r = apps.recomendaciones({**base, "credencial": "comprometida", "enlaces_sin_contener": 2, "pdfs_sin_reportar": 1,
                              "defensor_modelo": None, "incidentes_abiertos": 1, "correos_sin_revisar": 3})
    chk("todo pendiente: de lo más grave a lo menos", [x["nivel"] for x in r] == ["CRITICO", "ALTO", "ALTO", "MEDIO", "MEDIO", "BAJO"])
    chk("cada recomendación dice qué hacer", all(x["accion"] for x in r) and "Revócala" in r[0]["accion"]
        and "2 enlace" in r[1]["texto"])
    chk("defensor configurado pero fallando también se avisa",
        "falló" in apps.recomendaciones({**base, "defensor_ok": False})[0]["texto"])
    chk("los puntos citados son los de las reglas", f"{sesion.PUNTOS_ROJO['credencial_sin_revocar']} puntos" in r[0]["texto"])

    rec = apps.recursos()
    por = {x["tabla"]: x["acceso"] for x in rec["recursos"]}
    chk("Recursos lista una fila por herramienta del catálogo", len(rec["recursos"]) == len(herramientas.CATALOGO))
    chk("CONFIDENCIAL: el empleado necesita autorización; el invitado no llega",
        (por["incidentes"]["empleado"], por["incidentes"]["invitado"], por["incidentes"]["analista"]) ==
        ("con autorización", "no", "sí"))
    chk("CRITICA solo admin y nunca con autorización",
        [r for r, v in por["configuracion_admin"].items() if v != "no"] == ["admin"])
    chk("coincide con permisos.evaluar_acceso para todos los roles y tablas", all(
        (v == "sí") == permisos.evaluar_acceso(permisos.Identidad("x", rol), permisos.TABLAS[t]).permitido
        for t, acc in por.items() for rol, v in acc.items()))

    a = apps.ayuda("azul")
    chk("la ayuda trae los pasos del equipo, sus aplicaciones y todas las reglas",
        a["pasos"] == apps.AYUDA_EQUIPO["azul"] and [x["id"] for x in a["apps"]] == ids("azul")
        and len(a["reglas"]) == len(sesion.REGLAS_EVENTO))
    chk("la ayuda sin equipo es la del espectador", apps.ayuda(None)["equipo"] == "espectador")

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
