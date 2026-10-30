"""Pruebas de la cronología y el desglose de resultados (Fase G). Ejecutar: python -m src.lab.test_informe"""
from . import ataque_ia, informe, repositorio, sesion

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def fila(i, accion, ts="2026-10-30T10:01:30-06:00", **x):
    return {"id": i, "accion": accion, "ts": ts, "usuario": x.get("usuario", "ana.perez"), "rol": x.get("rol", "empleado"),
            "recurso": x.get("recurso", "correo:1"), "resultado": x.get("resultado", "OK"),
            "nivel_riesgo": x.get("nivel", "BAJO"), "equipo": x.get("equipo", "azul")}


def main():
    ini = "2026-10-30T10:00:00-06:00"
    e = informe.entrada(fila(1, "CLIC_ENLACE"), ini)
    chk("una fila de auditoría se traduce a una entrada legible con el minuto de partida",
        (e["categoria"], e["t_s"], e["equipo"]) == ("enlace", 90, "azul") and "ana.perez pulsó el enlace" in e["texto"])
    e = informe.entrada(fila(2, "HERRAMIENTA:consultar_clientes", resultado="DENEGADO", equipo="rojo",
                             usuario="visita.demo", rol="invitado"), ini)
    chk("los accesos de las IA a la BD son la categoría «acceso»", e["categoria"] == "acceso"
        and "consultar_clientes: DENEGADO" in e["texto"] and e["equipo"] == "rojo")
    chk("una acción desconocida no entra en la cronología", informe.entrada(fila(3, "ALGO_RARO"), ini) is None)
    chk("sin hora de inicio (partida en preparación) el minuto es None", informe.entrada(fila(4, "CORREO_RECIBIDO"))["t_s"] is None)
    chk("toda acción del SIEM tiene texto en la cronología (salvo las denegaciones genéricas)",
        set(repositorio.EVENTOS_SIEM) <= set(informe.ACCIONES))

    ents = [informe.entrada(f, ini) for f in (
        fila(1, "CORREO_RECIBIDO"), fila(2, "CORREO_REPORTADO"), fila(3, "CLIC_ENLACE"),
        fila(4, "ENLACE_CONTENIDO", nivel="MEDIO"), fila(5, "CREDENCIAL_REVOCADA"),
        fila(6, "CONSULTA", recurso="clientes", resultado="PERMITIDO", equipo="rojo", nivel="MEDIO"),
        fila(7, "CONSULTA", recurso="clientes", resultado="PERMITIDO", equipo=None),
        fila(8, "ATAQUE_IA_RESULTADO", resultado="CONTENIDO", equipo="rojo"))]
    rojo = [x["accion"] for x in ents if informe.visible_para(x, "rojo", "en_curso")]
    chk("durante la partida Rojo no ve si Azul reportó, contuvo o revocó",
        rojo == ["CORREO_RECIBIDO", "CLIC_ENLACE", "CONSULTA", "ATAQUE_IA_RESULTADO"])
    chk("… y solo ve SUS accesos, no los de otros", sum(a == "CONSULTA" for a in rojo) == 1)
    chk("al finalizar, Rojo lo ve todo", all(informe.visible_para(x, "rojo", "finalizada") for x in ents))
    chk("Azul, General y Espectador (sin sesión) lo ven todo",
        all(informe.visible_para(x, q, "en_curso") for x in ents for q in ("azul", "general", None)))
    chk("filtro por categorías", [x["id"] for x in informe.filtrar(ents, ["enlace", "credencial"])] == [3, 4, 5])
    chk("filtro por equipo", [x["id"] for x in informe.filtrar(ents, equipo="sistema")] == [7])
    chk("filtro por nivel mínimo", [x["id"] for x in informe.filtrar(ents, nivel_min="MEDIO")] == [4, 6])
    chk("filtro por texto (sin distinguir mayúsculas)", [x["id"] for x in informe.filtrar(ents, texto="CONTUVO")] == [4])
    chk("filtros combinados", [x["id"] for x in informe.filtrar(ents, ["acceso"], "rojo", "MEDIO")] == [6])

    # --- desglose: la suma de líneas es exactamente el marcador ---
    logros = {"enlaces_sin_contener": 2, "pdfs_sin_reportar": 1, "credenciales_sin_revocar": 1}
    misiones = [{"titulo": "Reportar", "estado": "completada", "puntos": 10, "puntos_obtenidos": 10, "a_tiempo": True,
                 "completada_por": "Bea", "evidencia": "correo:1"},
                {"titulo": "Contener", "estado": "completada", "puntos": 15, "puntos_obtenidos": 7, "a_tiempo": False,
                 "completada_por": "Beto", "evidencia": None},
                {"titulo": "Otra", "estado": "pendiente", "puntos": 5, "puntos_obtenidos": None, "a_tiempo": None,
                 "completada_por": None, "evidencia": None}]
    base = {"estado": "terminado", "sensibilidad_expuesta": None, "atq_ms": 1000, "def_ms": 2000,
            "atq_tokens_entrada": 300, "atq_tokens_salida": 40, "def_tokens_entrada": 400, "def_tokens_salida": 70,
            "atq_carga_ms": 5, "def_carga_ms": None}
    ataques = [{**base, "resultado": "datos_expuestos", "sensibilidad_expuesta": "INTERNA"},
               {**base, "resultado": "contenido"}, {**base, "resultado": "contenido", "def_ms": None},
               {**base, "resultado": "ia_enganada"},
               {**base, "resultado": "cancelado", "estado": "cancelado", "atq_ms": None, "def_ms": None}]
    d = informe.desglose(logros, misiones, ataques, {"CLIC_ENLACE": 2, "enlace_contenido": 1}, 15.0)
    esperado_rojo = 2 * 10 + 5 + 15 + ataque_ia.PUNTOS_DATOS["INTERNA"] + ataque_ia.PUNTOS_IA_ENGANADA
    chk("total de Rojo = 10·enlaces + 5·PDF + 15·credenciales + puntos IA", d["rojo"]["total"] == esperado_rojo == 55)
    chk("el total de Rojo coincide con el puntaje del marcador",
        d["rojo"]["total"] == sesion.puntaje_rojo(**logros) + 10 + 5)
    chk("total de Azul = misiones (la tardía vale la mitad) + 5 por ataque contenido", d["azul"]["total"] == 10 + 7 + 2 * 5)
    tarde = [x for x in d["azul"]["lineas"] if "Contener" in x["concepto"]][0]
    chk("cada línea trae su fórmula y quién la completó", "÷ 2" in tarde["formula"] and "Beto" in tarde["explicacion"])
    chk("las misiones pendientes no aparecen", not any("Otra" in x["concepto"] for x in d["azul"]["lineas"]))
    chk("cada línea cuadra: cantidad × unitario = subtotal (salvo misiones fuera de plazo)",
        all(x["cantidad"] * x["unitario"] == x["subtotal"] for x in d["rojo"]["lineas"]))
    chk("riesgo: reglas aplicadas con su subtotal y la suma sin acotar",
        d["riesgo"]["reglas"] == [{"evento": "CLIC_ENLACE", "veces": 2, "riesgo_unitario": 15, "subtotal": 30},
                                  {"evento": "enlace_contenido", "veces": 1, "riesgo_unitario": -15, "subtotal": -15}]
        and d["riesgo"]["suma_sin_acotar"] == 15)
    b = d["batalla_ia"]
    chk("estadística de la batalla: por resultado (el cancelado cuenta como lanzado)",
        b["lanzados"] == 5 and b["por_resultado"] == {"datos_expuestos": 1, "ia_enganada": 1, "contenido": 2, "cancelado": 1})
    chk("las medias solo usan las métricas que existen (sin inventar las que faltan)",
        b["atacante_ms"] == {"n": 4, "media": 1000, "min": 1000, "max": 1000, "total": 4000} and b["defensor_ms"]["n"] == 3
        and b["carga_ms"] == 25)  # 5 ataques × 5 ms del atacante; el defensor no informó carga
    chk("tokens totales tal cual", b["tokens"] == {"atacante_entrada": 1500, "atacante_salida": 200,
                                                   "defensor_entrada": 2000, "defensor_salida": 350})
    vacio = informe.desglose({"enlaces_sin_contener": 0, "pdfs_sin_reportar": 0, "credenciales_sin_revocar": 0}, [], [], {}, 0.0)
    chk("partida vacía: todo a 0 y medias en None", vacio["rojo"]["total"] == vacio["azul"]["total"] == 0
        and vacio["batalla_ia"]["atacante_ms"]["media"] is None and vacio["batalla_ia"]["tokens"]["atacante_entrada"] is None)

    # --- persistencia (repositorio) ---
    repo = repositorio.abrir(":memory:")
    repositorio.PARTIDA = "pG"
    rid = repo.guardar_ronda_practica(partida="pG", fase_partida="preparacion", modo="manual", ronda=1,
                                      usuario="ana.perez", rol="empleado", veredicto="DEFENSA_EXITOSA", def_ms=1234)
    chk("una ronda de práctica se guarda y deja auditoría", repo.rondas_practica("pG")[0]["id"] == rid
        and repo.auditoria(1)[0]["accion"] == "RONDA_PRACTICA")
    try:
        repo.guardar_ronda_practica(modo="manual", ronda=2, veredicto="ERROR", hackeo=1)
        chk("guardar una ronda solo acepta columnas permitidas", False)
    except ValueError:
        chk("guardar una ronda solo acepta columnas permitidas", True)
    repo.guardar_resultado("pG", "t1", "arbitro", "azul", 10, 90, "t0", 300, {"rojo": {"total": 10}})
    repo.guardar_resultado("pG", "t2", "tiempo", "rojo", 99, 0, "t0", 300, {})
    g = repo.resultado_guardado("pG")
    chk("el resultado final se guarda una sola vez (no se sobrescribe)", (g["ganador"], g["puntos_azul"], g["informe"]) ==
        ("azul", 90, {"rojo": {"total": 10}}))
    chk("historial de partidas finalizadas", [p["partida"] for p in repo.partidas_finalizadas()] == ["pG"])
    chk("una partida desconocida no tiene resultado", repo.resultado_guardado("nada") is None)
    chk("la auditoría de una partida sale en orden cronológico", [f["accion"] for f in repo.auditoria_partida("pG")] ==
        ["RONDA_PRACTICA"])
    repositorio.PARTIDA = None

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
