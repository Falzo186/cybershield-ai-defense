"""Cronología y resultados de una partida (Fase G). Lógica pura: no toca la BD ni el servidor.

- Cronología: cada fila de la auditoría de la partida se traduce a una entrada legible (categoría, equipo, texto)
  con el minuto de partida en que ocurrió. Durante la partida, Rojo solo ve lo que una campaña real podría observar
  (VISIBLE_ROJO); al finalizar, todos ven todo.
- Resultados: desglose de los puntos de cada equipo, línea a línea, con la fórmula de cada línea. Usa las MISMAS
  constantes que el marcador (sesion.PUNTOS_ROJO, ataque_ia.*), así que la suma del desglose es el marcador.
"""
from datetime import datetime

from . import ataque_ia, sesion

CATEGORIAS = ("partida", "correo", "enlace", "documento", "credencial", "incidente", "mision", "batalla_ia", "acceso",
              "practica")
NIVELES = ("BAJO", "MEDIO", "ALTO", "CRITICO")

# accion -> (categoría, texto). El texto admite {usuario}, {recurso} y {resultado} (valores de la auditoría).
ACCIONES = {
    "PARTIDA_INICIADA": ("partida", "La partida empezó ({resultado})"),
    "PARTIDA_FINALIZADA": ("partida", "La partida terminó: {resultado}"),
    "CORREO_RECIBIDO": ("correo", "Rojo envió un correo a {usuario} ({recurso})"),
    "CORREO_ABIERTO": ("correo", "{usuario} abrió un correo ({recurso})"),
    "CORREO_ARCHIVADO": ("correo", "Azul archivó un correo ({recurso})"),
    "CORREO_REPORTADO": ("correo", "Azul reportó un correo ({recurso})"),
    "REMITENTE_VERIFICADO": ("correo", "Azul verificó el remitente ({recurso}): {resultado}"),
    "RESPUESTA_ENVIADA": ("correo", "Azul respondió un correo ({recurso})"),
    "CLIC_ENLACE": ("enlace", "{usuario} pulsó el enlace de un correo ({recurso})"),
    "CLIC_BLOQUEADO": ("enlace", "Clic en un enlace ya contenido: bloqueado ({recurso})"),
    "ENLACE_INSPECCIONADO": ("enlace", "Azul inspeccionó un enlace sin abrirlo ({recurso})"),
    "ENLACE_CONTENIDO": ("enlace", "Azul contuvo un enlace clicado ({recurso})"),
    "PDF_ABIERTO": ("documento", "{usuario} previsualizó un PDF adjunto ({recurso})"),
    "PDF_REPORTADO": ("documento", "Azul reportó un PDF adjunto ({recurso})"),
    "ARCHIVO_AISLADO": ("documento", "Azul aisló un adjunto ({recurso})"),
    "CREDENCIAL_COMPROMETIDA": ("credencial", "La credencial de {usuario} quedó COMPROMETIDA ({recurso})"),
    "CREDENCIAL_REVOCADA": ("credencial", "Azul revocó la credencial de {usuario} (por {resultado})"),
    "INCIDENTE_ABIERTO": ("incidente", "Azul abrió un incidente ({recurso})"),
    "INCIDENTE_ACTUALIZADO": ("incidente", "Un incidente cambió de estado ({recurso}: {resultado})"),
    "INCIDENTE_RESUELTO": ("incidente", "Azul resolvió un incidente ({recurso})"),
    "MISION_COMPLETADA": ("mision", "Misión completada ({recurso}): {resultado}"),
    "MISION_ASUMIDA": ("mision", "{resultado} asumió una misión ({recurso})"),
    "ATAQUE_IA_LANZADO": ("batalla_ia", "La IA de Rojo lanzó un ataque ({recurso}) como {usuario}: {resultado}"),
    "ATAQUE_IA_RESULTADO": ("batalla_ia", "Resultado del ataque IA ({recurso}): {resultado}"),
    "DEFENSOR_IA_CONFIGURADO": ("batalla_ia", "Azul fijó su defensor IA ({recurso})"),
    "RONDA_PRACTICA": ("practica", "Ronda de práctica ({recurso}) como {usuario}: {resultado}"),
}
# Lo que Rojo ve DURANTE la partida: sus propias acciones y lo que una campaña real podría medir (clics, adjuntos
# abiertos, credenciales obtenidas, sus accesos frenados o concedidos). Nunca si Azul reportó, contuvo o revocó.
VISIBLE_ROJO = {"PARTIDA_INICIADA", "PARTIDA_FINALIZADA", "CORREO_RECIBIDO", "CLIC_ENLACE", "PDF_ABIERTO",
                "CREDENCIAL_COMPROMETIDA", "ATAQUE_IA_LANZADO", "ATAQUE_IA_RESULTADO"}


def _dt(iso):
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def entrada(fila, inicio_iso=None):
    """Fila de auditoría -> entrada de la cronología, o None si no es un evento de partida conocido.
    Las consultas y herramientas de la base de datos (accesos de las IA) son la categoría «acceso»."""
    accion = fila["accion"]
    if accion in ACCIONES:
        categoria, plantilla = ACCIONES[accion]
        texto = plantilla.format(usuario=fila.get("usuario") or "—", recurso=fila.get("recurso") or "—",
                                 resultado=fila.get("resultado") or "—")
    elif accion == "CONSULTA" or accion.startswith("HERRAMIENTA:"):
        categoria = "acceso"
        que = accion.split(":", 1)[1] if ":" in accion else f"consulta a {fila.get('recurso')}"
        texto = f"Acceso de {fila.get('usuario')} ({fila.get('rol')}) a {que}: {fila.get('resultado')}"
    else:
        return None
    t0, t = _dt(inicio_iso), _dt(fila.get("ts"))
    return {"id": fila["id"], "ts": fila.get("ts"), "t_s": int((t - t0).total_seconds()) if t0 and t else None,
            "categoria": categoria, "equipo": fila.get("equipo") or "sistema", "accion": accion,
            "nivel": fila.get("nivel_riesgo"), "texto": texto}


def visible_para(entrada_, equipo, fase):
    """Rojo, durante la partida, solo ve VISIBLE_ROJO y sus propios accesos; el resto de vistas, todo."""
    if equipo != "rojo" or fase == "finalizada":
        return True
    return entrada_["accion"] in VISIBLE_ROJO or (entrada_["categoria"] == "acceso" and entrada_["equipo"] == "rojo")


def filtrar(entradas, categorias=None, equipo=None, nivel_min=None, texto=None):
    """Filtros de la cronología (todos opcionales y combinables)."""
    minimo = NIVELES.index(nivel_min) if nivel_min in NIVELES else 0
    q = (texto or "").strip().casefold()
    return [e for e in entradas
            if (not categorias or e["categoria"] in categorias) and (not equipo or e["equipo"] == equipo)
            and (e["nivel"] not in NIVELES or NIVELES.index(e["nivel"]) >= minimo)
            and (not q or q in e["texto"].casefold())]


def _linea(concepto, cantidad, unitario, subtotal, formula, explicacion):
    return {"concepto": concepto, "cantidad": cantidad, "unitario": unitario, "subtotal": subtotal,
            "formula": formula, "explicacion": explicacion}


def _media(valores):
    v = [x for x in valores if isinstance(x, int)]
    return {"n": len(v), "media": round(sum(v) / len(v)) if v else None, "min": min(v) if v else None,
            "max": max(v) if v else None, "total": sum(v) if v else None}


def desglose(logros, misiones, ataques, eventos_vistos, riesgo_final):
    """logros = Repositorio.logros_rojo; misiones = Repositorio.misiones; ataques = Repositorio.ataques_ia;
    eventos_vistos = EstadoSesion.eventos_vistos de la partida. -> {rojo, azul, riesgo, batalla_ia}."""
    p = sesion.PUNTOS_ROJO
    rojo = [
        _linea("Enlaces clicados sin contener", logros["enlaces_sin_contener"], p["enlace_sin_contener"],
               logros["enlaces_sin_contener"] * p["enlace_sin_contener"],
               f"{p['enlace_sin_contener']} × enlaces clicados que Azul no contuvo",
               "Se pierden en cuanto Azul contiene el enlace."),
        _linea("PDF abiertos sin reportar ni aislar", logros["pdfs_sin_reportar"], p["pdf_abierto_sin_reportar"],
               logros["pdfs_sin_reportar"] * p["pdf_abierto_sin_reportar"],
               f"{p['pdf_abierto_sin_reportar']} × PDF abiertos que Azul no reportó ni aisló",
               "Se pierden al reportar o aislar el adjunto."),
        _linea("Credenciales comprometidas sin revocar", logros["credenciales_sin_revocar"], p["credencial_sin_revocar"],
               logros["credenciales_sin_revocar"] * p["credencial_sin_revocar"],
               f"{p['credencial_sin_revocar']} × credenciales robadas que Azul no revocó",
               "Se pierden al revocar la credencial."),
    ]
    terminados = [a for a in ataques if a["estado"] == "terminado"]
    for sens, pts in ataque_ia.PUNTOS_DATOS.items():
        n = sum(a["resultado"] == "datos_expuestos" and a["sensibilidad_expuesta"] == sens for a in terminados)
        if n:
            rojo.append(_linea(f"Ataques IA: datos {sens} expuestos", n, pts, n * pts,
                               f"{pts} × ataques que sacaron datos {sens}",
                               "Permanentes: un dato filtrado no se recupera al revocar después."))
    n = sum(a["resultado"] == "ia_enganada" for a in terminados)
    if n:
        rojo.append(_linea("Ataques IA: IA defensora engañada (una capa lo frenó)", n, ataque_ia.PUNTOS_IA_ENGANADA,
                           n * ataque_ia.PUNTOS_IA_ENGANADA,
                           f"{ataque_ia.PUNTOS_IA_ENGANADA} × ataques en que la IA propuso un acceso indebido",
                           "No salió ningún dato, pero el modelo defensor se dejó convencer."))
    azul = []
    for m in misiones:
        if m["estado"] != "completada":
            continue
        obtenidos = m["puntos_obtenidos"] or 0
        tarde = m["a_tiempo"] is False
        azul.append(_linea(f"Misión: {m['titulo']}", 1, m["puntos"], obtenidos,
                           f"{m['puntos']} ÷ 2 (fuera de plazo)" if tarde else f"{m['puntos']} (puntos de la misión)",
                           f"Completada por {m['completada_por'] or '—'}" + (f" · evidencia {m['evidencia']}"
                                                                             if m["evidencia"] else "")))
    n = sum(a["resultado"] == "contenido" for a in terminados)
    if n:
        azul.append(_linea("Ataques IA contenidos por el defensor", n, ataque_ia.PUNTOS_CONTENIDO,
                           n * ataque_ia.PUNTOS_CONTENIDO, f"{ataque_ia.PUNTOS_CONTENIDO} × ataques rechazados",
                           "El defensor IA (o el filtro rápido) rechazó la solicitud: no salió ningún dato."))
    reglas = [{"evento": ev, "veces": n, "riesgo_unitario": sesion.REGLAS_EVENTO[ev]["riesgo"],
               "subtotal": n * sesion.REGLAS_EVENTO[ev]["riesgo"]}
              for ev, n in sorted(eventos_vistos.items()) if ev in sesion.REGLAS_EVENTO]
    por_resultado = {r: sum(a["resultado"] == r for a in ataques) for r in ataque_ia.RESULTADOS}
    return {
        "rojo": {"total": sum(x["subtotal"] for x in rojo), "lineas": rojo},
        "azul": {"total": sum(x["subtotal"] for x in azul), "lineas": azul},
        "formula_ganador": "Gana el equipo con más puntos; con los mismos puntos, empate.",
        "riesgo": {"final": riesgo_final, "reglas": reglas, "suma_sin_acotar": sum(r["subtotal"] for r in reglas),
                   "explicacion": "Cada evento suma o resta su riesgo fijo (REGLAS_EVENTO), en orden y acotado a "
                                  "0-100 en cada paso: el riesgo nunca baja de 0 ni deja «saldo a favor», así que el "
                                  "final puede diferir de la suma sin acotar."},
        "batalla_ia": {
            "lanzados": len(ataques), "por_resultado": {k: v for k, v in por_resultado.items() if v},
            "atacante_ms": _media([a["atq_ms"] for a in ataques]), "defensor_ms": _media([a["def_ms"] for a in ataques]),
            "tokens": {"atacante_entrada": _media([a["atq_tokens_entrada"] for a in ataques])["total"],
                       "atacante_salida": _media([a["atq_tokens_salida"] for a in ataques])["total"],
                       "defensor_entrada": _media([a["def_tokens_entrada"] for a in ataques])["total"],
                       "defensor_salida": _media([a["def_tokens_salida"] for a in ataques])["total"]},
            "carga_ms": _media([a["atq_carga_ms"] for a in ataques] + [a["def_carga_ms"] for a in ataques])["total"],
            "nota": "Métricas tal como las informa Ollama: los ataques sin una métrica (fallo, filtro rápido, "
                    "cancelado) no entran en su media ni en su total.",
        },
    }
