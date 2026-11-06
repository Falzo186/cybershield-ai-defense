"""Pruebas offline de la cronología unificada y la correlación. Ejecutar: python -m src.lab.test_correlacion"""
from . import correlacion as cor, wazuh

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def ev(tipo, segundo, usuario="ana.perez", partida="p1", **kw):
    return {"timestamp": f"2026-11-06T10:{segundo // 60:02d}:{segundo % 60:02d}-06:00", "partida": partida,
            "equipo": "azul", "usuario": usuario, "rol": "empleado", "tipo": tipo, "accion": tipo.upper(),
            "recurso": "correo:1", "resultado": "OK", "riesgo": "ALTO", "origen": "cybershield-lab", **kw}


def main():
    # ── Cronología ──────────────────────────────────────────────────────────────────────────────────────────
    eventos = [ev("clic_enlace", 0), ev("credencial_comprometida", 60)]
    auditoria = [{"ts": "2026-11-06T10:00:30-06:00", "usuario": "ana.perez", "rol": "empleado",
                  "accion": "CONSULTA", "recurso": "clientes", "resultado": "PERMITIDO",
                  "nivel_riesgo": "MEDIO", "equipo": "azul", "partida": "p1"}]
    alertas = wazuh.alertas_simuladas(eventos)["alertas"]
    c = cor.cronologia(eventos, auditoria, alertas)
    chk("la cronología une las tres fuentes", {f["fuente"] for f in c} == {"evento", "auditoria", "alerta"})
    chk("va de más reciente a más antigua",
        [f["timestamp"] for f in c] == sorted((f["timestamp"] for f in c), reverse=True))
    chk("TODO registro declara su fuente", all(f["fuente"] in cor.FUENTES for f in c))
    chk("TODO registro declara si es real o simulado",
        all(isinstance(f["simulado"], bool) and f["real"] == (not f["simulado"]) for f in c))
    chk("las alertas simuladas salen marcadas como simuladas",
        all(f["simulado"] for f in c if f["fuente"] == "alerta"))
    chk("los eventos y la auditoría del laboratorio son reales",
        all(f["real"] for f in c if f["fuente"] in ("evento", "auditoria")))
    chk("se puede filtrar por fuente",
        {f["fuente"] for f in cor.cronologia(eventos, auditoria, alertas, fuentes=["evento"])} == {"evento"})
    chk("se puede filtrar por partida",
        cor.cronologia(eventos + [ev("clic_enlace", 90, partida="p2")], partida="p2", limite=99)
        and all(f["partida"] == "p2"
                for f in cor.cronologia(eventos + [ev("clic_enlace", 90, partida="p2")], partida="p2")))
    chk("el límite se respeta", len(cor.cronologia(eventos, auditoria, alertas, limite=2)) == 2)
    chk("cada registro trae un texto legible", all(f["texto"] for f in c))
    chk("sin nada que mostrar, la cronología es una lista vacía", cor.cronologia([], [], []) == [])

    # ── Correlación: la cadena del laboratorio ──────────────────────────────────────────────────────────────
    cadena = [ev("correo_recibido", 0), ev("clic_enlace", 30), ev("credencial_comprometida", 90),
              ev("ataque_ia_lanzado", 300), ev("ataque_ia_resultado", 310, resultado="DATOS_EXPUESTOS")]
    incs = cor.correlacionar(cadena)
    chk("la cadena completa queda en un solo incidente", len(incs) == 1)
    i = incs[0]
    chk("el incidente recoge los eventos encadenados", i["n_eventos"] >= 4)
    chk("cada vínculo nombra la regla que lo justifica",
        all(v["regla"] and v["explicacion"] for v in i["vinculos"]))
    chk("los vínculos guardan cuántos segundos pasaron",
        all(isinstance(v["segundos"], float) and v["segundos"] >= 0 for v in i["vinculos"]))
    chk("la gravedad la marca el evento más grave", i["gravedad"] == "critica")
    chk("el resumen describe la cadena", "→" in i["resumen"])
    chk("sin contención, el resumen lo dice", "Sin contención" in i["resumen"])
    # El incidente arranca en el primer evento de riesgo (clic_enlace, s=30), no en el correo recibido:
    # «correo_recibido» no es semilla, así que por sí solo no abre un incidente. 310 − 30 = 280 s.
    chk("se calcula la duración desde el primer evento de riesgo", i["duracion_s"] == 280.0)
    chk("un correo recibido por sí solo no abre un incidente",
        cor.correlacionar([ev("correo_recibido", 0)]) == [])

    # ── Contención ──────────────────────────────────────────────────────────────────────────────────────────
    con_respuesta = cadena + [ev("credencial_revocada", 400)]
    i2 = cor.correlacionar(con_respuesta)[0]
    chk("la revocación se suma al incidente y lo marca contenido",
        i2["contenido"] and "credencial_revocada" in i2["tipos"])
    chk("y el resumen lo refleja", "respuesta defensiva" in i2["resumen"])

    # ── No se inventan relaciones ───────────────────────────────────────────────────────────────────────────
    lejos = [ev("clic_enlace", 0), ev("credencial_comprometida", 0)]
    lejos[1]["timestamp"] = "2026-11-06T23:59:00-06:00"   # fuera de la ventana de 900 s
    incs = cor.correlacionar(lejos)
    chk("dos eventos fuera de la ventana NO se correlacionan", len(incs) == 2)
    chk("y quedan como incidentes aislados sin vínculos", all(not x["vinculos"] for x in incs))
    chk("un evento aislado lo dice en su resumen", "Evento aislado" in incs[0]["resumen"])
    distintas = [ev("clic_enlace", 0, partida="p1"), ev("credencial_comprometida", 60, partida="p2")]
    chk("eventos de partidas distintas no se correlacionan", len(cor.correlacionar(distintas)) == 2)
    rutina = [ev("correo_abierto", 0), ev("remitente_verificado", 10)]
    chk("eventos rutinarios que no son semilla no abren incidente", cor.correlacionar(rutina) == [])
    hacia_atras = [ev("credencial_comprometida", 0), ev("clic_enlace", 60)]
    incs = cor.correlacionar(hacia_atras)
    chk("la causa debe preceder al efecto: no se encadena hacia atrás",
        len(incs) == 2 and all(not x["vinculos"] for x in incs))

    # ── Tanteo de permisos ──────────────────────────────────────────────────────────────────────────────────
    tanteo = [ev("autorizacion_denegada", s) for s in (0, 30, 60)]
    i3 = cor.correlacionar(tanteo)
    chk("tres denegaciones seguidas forman un solo incidente de tanteo",
        len(i3) == 1 and i3[0]["n_eventos"] == 3)

    # ── Resumen ─────────────────────────────────────────────────────────────────────────────────────────────
    r = cor.resumen_correlacion(cor.correlacionar(con_respuesta + tanteo))
    chk("el resumen cuenta incidentes, encadenados y aislados",
        r["incidentes"] == r["encadenados"] + r["aislados"])
    chk("y los eventos agrupados", r["eventos_agrupados"] > 0)
    chk("el resumen vacío no inventa nada", cor.resumen_correlacion([])["incidentes"] == 0)

    # ── Sobre los eventos REALES del laboratorio ────────────────────────────────────────────────────────────
    reales = cor.leer_eventos("integraciones/wazuh/eventos_ejemplo.jsonl")
    chk("se leen los eventos reales de ejemplo", len(reales) == 12)
    inc_reales = cor.correlacionar(reales)
    chk("la partida real produce al menos un incidente", len(inc_reales) >= 1)
    chk("y encadena el phishing con el acceso de la IA",
        any({"clic_enlace", "credencial_comprometida"} <= set(x["tipos"]) for x in inc_reales))

    # ── Robustez ────────────────────────────────────────────────────────────────────────────────────────────
    chk("un archivo inexistente devuelve lista vacía", cor.leer_eventos("no/existe.jsonl") == [])
    chk("un timestamp inválido no rompe la correlación",
        isinstance(cor.correlacionar([{**ev("clic_enlace", 0), "timestamp": "no-es-fecha"}]), list))
    chk("eventos sin tipo no rompen nada", isinstance(cor.correlacionar([{"partida": "p1"}]), list))
    chk("la cronología tolera registros incompletos",
        isinstance(cor.cronologia([{"tipo": "x"}], [{}], [{}]), list))

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
