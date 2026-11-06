"""Pruebas del catálogo de escenarios de empresa y de los estados de misión (Fase D).
Ejecutar: python -m src.lab.test_escenarios_empresa

Sin Ollama ni red. La parte de misiones usa una BD en memoria.

Lo que se demuestra:
  - un escenario no promete nada que la partida no pueda hacer (rol, técnica, eventos y acciones existen);
  - la sensibilidad que muestra un escenario sale del catálogo de herramientas, no de su descripción;
  - los estados `en_progreso` y `cancelada` funcionan sin romper las transiciones anteriores;
  - la migración del esquema conserva el progreso histórico.
"""
import sqlite3

from . import atacante, escenarios_empresa as ee, herramientas, permisos, repositorio, schema

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    # ── El catálogo es coherente con el resto del laboratorio ──────────────────────────────────────────────
    chk("hay escenarios en el catálogo", len(ee.CATALOGO) >= 3)
    chk("los ids del dict coinciden con el id de cada escenario",
        all(k == e["id"] for k, e in ee.CATALOGO.items()))
    for e in ee.CATALOGO.values():
        chk(f"el escenario {e['id']} declara todas sus claves y es coherente", ee.validar(e) == [])
    chk("todos los escenarios declaran las 15 claves del encargo",
        all(set(ee.CLAVES) <= set(e) for e in ee.CATALOGO.values()))
    chk("hay una dificultad de cada nivel",
        {e["dificultad"] for e in ee.CATALOGO.values()} == set(ee.DIFICULTADES))
    chk("cada escenario declara objetivo de Rojo y de Azul, y no son el mismo texto",
        all(e["objetivo_rojo"] and e["objetivo_azul"] and e["objetivo_rojo"] != e["objetivo_azul"]
            for e in ee.CATALOGO.values()))
    chk("cada escenario declara condiciones de victoria para los dos equipos",
        all(e["victoria_rojo"] and e["victoria_azul"] for e in ee.CATALOGO.values()))
    chk("y criterios de evaluación", all(e["criterios_evaluacion"] for e in ee.CATALOGO.values()))
    chk("todos los roles objetivo existen en la capa de permisos",
        all(e["rol_objetivo"] in permisos.ROLES for e in ee.CATALOGO.values()))
    chk("ninguno usa el rol admin: con admin no hay falla posible",
        all(e["rol_objetivo"] != "admin" for e in ee.CATALOGO.values()))
    chk("las técnicas declaradas existen en atacante.ESCENARIOS",
        all(e["tecnica_atacante"] is None or e["tecnica_atacante"] in atacante.ESCENARIOS
            for e in ee.CATALOGO.values()))
    chk("todos los eventos declarados los emite el repositorio de verdad",
        all(ev in {v[0] for v in repositorio.EVENTOS_SIEM.values()} | {"autorizacion_denegada"}
            for e in ee.CATALOGO.values() for ev in e["eventos"]))
    chk("las reglas base están en todos los escenarios",
        all(set(ee.REGLAS_BASE) <= set(e["reglas"]) for e in ee.CATALOGO.values()))
    chk("una de esas reglas es que la IA no se concede permisos",
        any("conceder" in r or "concederse" in r for r in ee.REGLAS_BASE))

    # `validar` detecta de verdad lo que promete detectar.
    bueno = dict(ee.CATALOGO["soporte_interno"])
    chk("validar acepta un escenario correcto", ee.validar(bueno) == [])
    chk("validar rechaza un rol inventado",
        any("rol desconocido" in p for p in ee.validar({**bueno, "rol_objetivo": "jefazo"})))
    chk("validar rechaza una dificultad inventada",
        any("dificultad desconocida" in p for p in ee.validar({**bueno, "dificultad": "imposible"})))
    chk("validar rechaza una técnica de atacante que no existe",
        any("técnica de atacante" in p for p in ee.validar({**bueno, "tecnica_atacante": "telepatia"})))
    chk("validar rechaza un evento que nadie emite",
        any("evento inexistente" in p for p in ee.validar({**bueno, "eventos": ("llamada_telefonica",)})))
    chk("validar rechaza una acción que la partida no ofrece",
        any("acción inexistente" in p for p in ee.validar({**bueno, "acciones_permitidas": ("borrar_bd",)})))
    chk("validar avisa de una clave que falta",
        any("falta nombre" in p for p in ee.validar({k: v for k, v in bueno.items() if k != "nombre"})))

    # ── La sensibilidad sale del catálogo de herramientas, no del texto ────────────────────────────────────
    for e in ee.CATALOGO.values():
        r = ee.recursos_sensibles(e)
        h = herramientas.CATALOGO[atacante.OBJETIVO_POR_ROL[e["rol_objetivo"]]]
        chk(f"{e['id']}: la sensibilidad del objetivo es la del catálogo ({h.sensibilidad})",
            r["sensibilidad"] == h.sensibilidad and r["herramienta_objetivo"] == h.nombre)
    chk("el escenario difícil pone en juego datos CRÍTICOS",
        ee.obtener("auditoria_externa")["objetivo"]["sensibilidad"] == "CRITICA")
    chk("el escenario fácil no pone en juego datos críticos",
        ee.obtener("correo_proveedor")["objetivo"]["sensibilidad"] != "CRITICA")

    # ── Forma pública ─────────────────────────────────────────────────────────────────────────────────────
    pub = ee.obtener("soporte_interno")
    chk("la forma pública es serializable (listas, no tuplas)",
        all(not isinstance(v, tuple) for v in pub.values()))
    chk("y añade el objetivo real", "objetivo" in pub)
    chk("obtener con un id inexistente devuelve None", ee.obtener("no-existe") is None)
    chk("listar los ordena por dificultad",
        [e["dificultad"] for e in ee.listar()] == sorted([e["dificultad"] for e in ee.listar()],
                                                         key=lambda d: ee.DIFICULTADES.index(d)))

    # ══ Estados de misión: en_progreso y cancelada ═════════════════════════════════════════════════════════
    repo = repositorio.abrir(":memory:")
    P, U = "p-test", "ana.perez"
    todas = repo.misiones(P, U)
    chk("hay misiones semilla", len(todas) > 0)
    chk("una misión sin progreso está pendiente, y su estado registrado también",
        all(m["estado"] == m["estado_registrado"] == "pendiente"
            for m in todas if not m["requiere"]))
    chk("el estado registrado se publica siempre", all("estado_registrado" in m for m in todas))

    # Elegimos una misión manual sin dependencias, para poder manejarla a mano.
    libre = next(m for m in todas if not m["depende_de"])
    mid = libre["id"]

    # asumir -> en_progreso
    chk("asumir una misión la pone en progreso", repo.asumir_mision(P, U, mid, "Beto") is True)
    m = next(x for x in repo.misiones(P, U) if x["id"] == mid)
    chk("y así queda registrado", m["estado_registrado"] == "en_progreso" and m["estado"] == "en_progreso")
    chk("con su responsable", m["responsable"] == "Beto")
    chk("volver a asumirla solo cambia el responsable",
        repo.asumir_mision(P, U, mid, "Bea") is True
        and next(x for x in repo.misiones(P, U) if x["id"] == mid)["responsable"] == "Bea")
    chk("y no la saca de en_progreso",
        next(x for x in repo.misiones(P, U) if x["id"] == mid)["estado_registrado"] == "en_progreso")

    # Una misión en progreso SÍ se puede completar por su evento.
    chk("una misión en progreso sigue estando entre las completables",
        "en_progreso" in repo.COMPLETABLES)

    # cancelar
    chk("cancelar una misión en progreso funciona",
        repo.cancelar_mision(P, U, mid, "Bea", "el correo era legítimo") is True)
    m = next(x for x in repo.misiones(P, U) if x["id"] == mid)
    chk("queda cancelada", m["estado"] == "cancelada" and m["estado_registrado"] == "cancelada")
    chk("con su motivo guardado", m["motivo_cancelacion"] == "el correo era legítimo")
    chk("y sin puntos", (m["puntos_obtenidos"] or 0) == 0)
    chk("cancelarla otra vez no hace nada", repo.cancelar_mision(P, U, mid, "Bea") is False)
    chk("una misión cancelada no se puede asumir", repo.asumir_mision(P, U, mid, "Beto") == "cancelada")
    chk("ni completar a mano", repo.completar_mision_manual(P, U, mid, "Beto") in ("cancelada", None))
    chk("cancelar queda en la auditoría",
        any(f["accion"] == "MISION_CANCELADA" for f in repo.auditoria(50)))
    chk("cancelar una misión inexistente devuelve None", repo.cancelar_mision(P, U, 99999, "Beto") is None)

    # Una misión cancelada NO se completa por su evento.
    # Tiene que ser OTRA misión: si fuera `mid`, el bloque siguiente la dejaría completada y las
    # comprobaciones de reabrir dejarían de medir lo que creen medir.
    por_evento = next((m for m in repo.misiones(P, U)
                       if m["id"] != mid and m["condicion_evento"] != "manual" and not m["depende_de"]), None)
    if por_evento is not None:
        ev = por_evento["condicion_evento"]
        repo.cancelar_mision(P, U, por_evento["id"], "Bea", "no procede")
        hechas = repo.completar_misiones_evento(P, U, ev, "Bea")
        chk("una misión cancelada no la completa su evento",
            por_evento["id"] not in {h["id"] for h in hechas})
        chk("y sigue cancelada",
            next(x for x in repo.misiones(P, U) if x["id"] == por_evento["id"])["estado"] == "cancelada")
        chk("reabrirla la devuelve a pendiente", repo.reabrir_mision(P, U, por_evento["id"], "Bea") is True)
        chk("y entonces su evento sí la completa",
            por_evento["id"] in {h["id"] for h in repo.completar_misiones_evento(P, U, ev, "Bea")})

    # reabrir
    chk("reabrir una misión cancelada funciona", repo.reabrir_mision(P, U, mid, "Bea") is True)
    m = next(x for x in repo.misiones(P, U) if x["id"] == mid)
    chk("vuelve a pendiente", m["estado_registrado"] == "pendiente")
    chk("y su motivo de cancelación se limpia", m["motivo_cancelacion"] is None)
    chk("reabrir una que no estaba cancelada no hace nada", repo.reabrir_mision(P, U, mid, "Bea") is False)
    chk("reabrir queda en la auditoría",
        any(f["accion"] == "MISION_REABIERTA" for f in repo.auditoria(50)))
    chk("reabrir una misión inexistente devuelve None", repo.reabrir_mision(P, U, 99999, "Bea") is None)

    # Una misión completada es terminal: no se cancela ni se reabre.
    manual = next((m for m in repo.misiones(P, U) if m["condicion_evento"] == "manual"
                   and not m["depende_de"]), None)
    if manual is not None:
        repo.completar_mision_manual(P, U, manual["id"], "Beto")
        chk("una misión completada no se puede cancelar",
            repo.cancelar_mision(P, U, manual["id"], "Beto") == "completada")
        chk("ni reabrir", repo.reabrir_mision(P, U, manual["id"], "Beto") is False)
        chk("y conserva sus puntos",
            (next(x for x in repo.misiones(P, U) if x["id"] == manual["id"])["puntos_obtenidos"] or 0) > 0)

    # Los estados terminales no los sobreescribe el reloj ni una dependencia.
    repo2 = repositorio.abrir(":memory:")
    con_plazo = next((m for m in repo2.misiones(P, U) if m["plazo_s"] is not None
                      and not m["depende_de"]), None)
    if con_plazo is not None:
        repo2.cancelar_mision(P, U, con_plazo["id"], "Bea", "fuera")
        m = next(x for x in repo2.misiones(P, U, con_plazo["plazo_s"] + 10_000) if x["id"] == con_plazo["id"])
        chk("una misión cancelada no pasa a vencida por el reloj", m["estado"] == "cancelada")
    con_dep = next((m for m in repo2.misiones(P, U) if m["depende_de"]), None)
    if con_dep is not None:
        chk("una misión con dependencia pendiente sale bloqueada", con_dep["estado"] == "bloqueada")
        repo2.cancelar_mision(P, U, con_dep["id"], "Bea", "no procede")
        m = next(x for x in repo2.misiones(P, U) if x["id"] == con_dep["id"])
        chk("y si se cancela, la cancelación manda sobre el bloqueo", m["estado"] == "cancelada")

    chk("los estados guardados son los cuatro declarados",
        set(repositorio.Repositorio.ESTADOS_MISION) == {"pendiente", "en_progreso", "completada", "cancelada"})
    chk("y los derivados no se guardan nunca",
        not (set(repositorio.Repositorio.ESTADOS_DERIVADOS) & set(repositorio.Repositorio.ESTADOS_MISION)))

    # ══ La migración del esquema conserva el progreso histórico ════════════════════════════════════════════
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE usuarios(usuario TEXT PRIMARY KEY, rol TEXT NOT NULL);
        CREATE TABLE misiones(id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, condicion_evento TEXT NOT NULL,
                              puntos INTEGER NOT NULL CHECK(puntos >= 0));
        CREATE TABLE progreso_mision(
            partida TEXT NOT NULL, usuario TEXT NOT NULL, mision_id INTEGER NOT NULL,
            estado TEXT NOT NULL CHECK(estado IN ('pendiente','completada')), ts TEXT NOT NULL,
            PRIMARY KEY(partida, usuario, mision_id));
        INSERT INTO usuarios VALUES('vieja.usuaria','empleado');
        INSERT INTO misiones VALUES(1,'Antigua','manual',10);
        INSERT INTO progreso_mision VALUES('p-vieja','vieja.usuaria',1,'completada','2026-01-01 10:00:00');
        """)
    antes = conn.execute("SELECT COUNT(*) FROM progreso_mision").fetchone()[0]
    schema._migrar_estados_mision(conn)
    filas = conn.execute("SELECT * FROM progreso_mision").fetchall()
    chk("la migración conserva el progreso existente", antes == 1 and len(filas) == 1)
    chk("con su estado y su marca de tiempo",
        filas[0]["estado"] == "completada" and filas[0]["ts"] == "2026-01-01 10:00:00")
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='progreso_mision'").fetchone()[0]
    chk("y la tabla ya acepta los estados nuevos", "en_progreso" in sql and "cancelada" in sql)
    chk("la columna del motivo existe",
        "motivo_cancelacion" in {f[1] for f in conn.execute("PRAGMA table_info(progreso_mision)")})
    conn.execute("INSERT INTO progreso_mision(partida,usuario,mision_id,estado,ts) "
                 "VALUES('p','vieja.usuaria',1,'en_progreso','x')")
    chk("y se puede escribir en_progreso después de migrar",
        conn.execute("SELECT COUNT(*) FROM progreso_mision WHERE estado='en_progreso'").fetchone()[0] == 1)
    try:
        conn.execute("INSERT INTO progreso_mision(partida,usuario,mision_id,estado,ts) "
                     "VALUES('q','vieja.usuaria',1,'inventado','x')")
        chk("un estado inventado debía rechazarse", False)
    except sqlite3.IntegrityError:
        chk("un estado que no está en la lista sigue rechazándose", True)
    schema._migrar_estados_mision(conn)
    chk("volver a migrar no duplica ni pierde filas",
        conn.execute("SELECT COUNT(*) FROM progreso_mision").fetchone()[0] == 2)
    conn.close()

    print(f"\nTotal {sum(resultados)}/{len(resultados)}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
