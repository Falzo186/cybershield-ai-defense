"""Cronología unificada y correlación de incidentes. Determinista, sin IA.

Dos funciones para el centro de operaciones:

  `cronologia(...)`  une en una sola línea de tiempo lo que hoy vive en sitios distintos: la auditoría de
      SQLite, los eventos del laboratorio (`eventos.jsonl`) y las alertas de Wazuh. **Cada registro dice de
      dónde viene (`fuente`) y si es real o simulado (`simulado`).**

  `correlacionar(...)` agrupa eventos que probablemente pertenecen al mismo incidente, con reglas fijas y
      explicables. No hay modelo, no hay puntuación aprendida: cada vínculo se justifica por una regla con
      nombre, y si no hay regla no se inventa una relación.

Nada de esto cambia el puntaje ni los veredictos: es una vista.
"""
import json
from datetime import datetime
from pathlib import Path

RUTA_EVENTOS = Path(__file__).resolve().parents[2] / "data" / "eventos.jsonl"

# Fuentes posibles de un registro de la cronología y si son datos reales del laboratorio.
FUENTES = {
    "auditoria": "Auditoría append-only de SQLite (fuente de verdad del laboratorio)",
    "evento": "Línea de data/eventos.jsonl emitida por el laboratorio",
    "alerta": "Alerta de Wazuh (real o deducida por el adaptador simulado)",
}

# Reglas de correlación: (nombre, evento_origen, eventos_consecuentes, ventana_s, explicación).
# Son relaciones causales que el laboratorio conoce de antemano. Si dos eventos no encajan en ninguna, NO
# se relacionan: una coincidencia temporal no es una cadena de ataque.
REGLAS = (
    ("phishing_a_credencial", "clic_enlace", ("credencial_comprometida",), 900,
     "El clic en el enlace de phishing llevó a la página falsa donde se entregó la credencial."),
    ("credencial_a_acceso", "credencial_comprometida", ("ataque_ia_resultado", "ataque_ia_lanzado"), 1800,
     "La credencial robada se usó para atacar al asistente de la base de datos."),
    ("phishing_a_adjunto", "correo_recibido", ("pdf_abierto", "clic_enlace"), 1800,
     "El correo recibido es el origen de la acción del empleado sobre su contenido."),
    ("escalada_denegada", "autorizacion_denegada", ("autorizacion_denegada",), 120,
     "Varias autorizaciones denegadas seguidas: patrón de tanteo de permisos."),
    ("acceso_a_incidente", "ataque_ia_resultado", ("incidente_abierto",), 3600,
     "El resultado del ataque motivó la apertura de un incidente."),
    ("contencion", "clic_enlace", ("enlace_contenido", "correo_reportado"), 3600,
     "Respuesta defensiva de Azul sobre el mismo correo."),
    ("revocacion", "credencial_comprometida", ("credencial_revocada",), 3600,
     "La credencial comprometida se revocó."),
)
# Eventos que, por sí solos, abren un incidente aunque no encadenen con nada.
SEMILLAS = ("clic_enlace", "credencial_comprometida", "ataque_ia_resultado", "autorizacion_denegada",
            "pdf_abierto")
# Gravedad del incidente a partir del evento más grave que contiene.
GRAVEDAD = {"credencial_comprometida": 4, "ataque_ia_resultado": 4, "clic_enlace": 3, "pdf_abierto": 2,
            "autorizacion_denegada": 2}
NOMBRE_GRAVEDAD = {4: "critica", 3: "alta", 2: "media", 1: "baja"}


def _ts(valor):
    """ISO 8601 -> datetime, o None. Nunca lanza."""
    try:
        return datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return None


def _segundos(a, b):
    ta, tb = _ts(a), _ts(b)
    if ta is None or tb is None:
        return None
    return (tb - ta).total_seconds()


def leer_eventos(ruta=RUTA_EVENTOS, limite=None):
    """Lee data/eventos.jsonl. Una línea corrupta se salta, no rompe la vista."""
    try:
        lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for linea in lineas:
        if not linea.strip():
            continue
        try:
            e = json.loads(linea)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out[-limite:] if limite else out


def _registro(fuente, ts, tipo, texto, simulado, extra=None):
    return {"fuente": fuente, "timestamp": ts, "tipo": tipo, "texto": texto,
            "simulado": bool(simulado), "real": not simulado, **(extra or {})}


def cronologia(eventos=None, auditoria=None, alertas=None, partida=None, fuentes=None, limite=200):
    """Línea de tiempo unificada, de más reciente a más antigua.

    Cada registro declara su `fuente` y si es `simulado`. Una alerta del adaptador simulado **nunca** sale
    marcada como real."""
    permitidas = set(fuentes) if fuentes else set(FUENTES)
    filas = []

    for e in (eventos if eventos is not None else leer_eventos()):
        if "evento" not in permitidas or (partida and e.get("partida") != partida):
            continue
        filas.append(_registro(
            "evento", e.get("timestamp"), e.get("tipo"),
            f"{e.get('tipo')} · {e.get('usuario') or '-'} ({e.get('rol') or '-'}) · {e.get('recurso') or '-'}"
            f" → {e.get('resultado') or '-'}", False,
            {"usuario": e.get("usuario"), "rol": e.get("rol"), "equipo": e.get("equipo"),
             "recurso": e.get("recurso"), "resultado": e.get("resultado"), "riesgo": e.get("riesgo"),
             "partida": e.get("partida")}))

    for a in (auditoria or []):
        if "auditoria" not in permitidas or (partida and a.get("partida") != partida):
            continue
        filas.append(_registro(
            "auditoria", a.get("ts"), a.get("accion"),
            f"{a.get('accion')} · {a.get('usuario') or '-'} · {a.get('recurso') or '-'} → "
            f"{a.get('resultado')}", False,
            {"usuario": a.get("usuario"), "rol": a.get("rol"), "equipo": a.get("equipo"),
             "recurso": a.get("recurso"), "resultado": a.get("resultado"),
             "riesgo": a.get("nivel_riesgo"), "partida": a.get("partida")}))

    for al in (alertas or []):
        if "alerta" not in permitidas:
            continue
        filas.append(_registro(
            "alerta", al.get("timestamp"), al.get("tipo"),
            f"[regla {al.get('regla_id')} nivel {al.get('nivel')}] {al.get('descripcion')}",
            bool(al.get("simulado")),
            {"usuario": al.get("usuario"), "rol": al.get("rol"), "equipo": al.get("equipo"),
             "nivel": al.get("nivel"), "regla_id": al.get("regla_id"), "mitre": al.get("mitre"),
             "origen_alerta": al.get("origen"), "partida": al.get("correlacion")}))

    filas.sort(key=lambda f: (f["timestamp"] or ""), reverse=True)
    return filas[:limite] if limite else filas


def _grupo_nuevo(evento, n):
    return {"id": f"INC-{n:03d}", "partida": evento.get("partida"), "eventos": [evento],
            "vinculos": [], "inicio": evento.get("timestamp"), "fin": evento.get("timestamp")}


def correlacionar(eventos=None, partida=None):
    """Agrupa eventos en incidentes probables con las reglas fijas de REGLAS.

    -> lista de incidentes, cada uno con sus eventos, los vínculos que los unen (con la regla y el motivo),
    su gravedad y su duración. Un evento que no encaja en ninguna regla y no es semilla **no se agrupa**:
    no se inventan relaciones por cercanía temporal."""
    evs = [e for e in (eventos if eventos is not None else leer_eventos())
           if not partida or e.get("partida") == partida]
    evs = sorted(evs, key=lambda e: (e.get("timestamp") or ""))
    incidentes, de_evento = [], {}

    for i, ev in enumerate(evs):
        tipo = ev.get("tipo")
        destino = None
        # ¿Encadena con algún evento ya agrupado, por una regla y dentro de su ventana?
        for nombre, origen, consecuentes, ventana, explicacion in REGLAS:
            if tipo not in consecuentes:
                continue
            for anterior in reversed(evs[:i]):   # solo hacia atrás: la causa precede al efecto
                if anterior.get("tipo") != origen or anterior.get("partida") != ev.get("partida"):
                    continue
                dt = _segundos(anterior.get("timestamp"), ev.get("timestamp"))
                if dt is None or dt < 0 or dt > ventana:
                    continue
                inc = de_evento.get(id(anterior))
                if inc is None:
                    continue
                inc["eventos"].append(ev)
                inc["vinculos"].append({"regla": nombre, "de": anterior.get("tipo"), "a": tipo,
                                        "segundos": dt, "explicacion": explicacion})
                destino = inc
                break
            if destino:
                break
        if destino is None and tipo in SEMILLAS:
            destino = _grupo_nuevo(ev, len(incidentes) + 1)
            incidentes.append(destino)
        if destino is not None:
            de_evento[id(ev)] = destino
            destino["fin"] = max(filter(None, (destino["fin"], ev.get("timestamp"))), default=None)
            destino["inicio"] = min(filter(None, (destino["inicio"], ev.get("timestamp"))), default=None)

    for inc in incidentes:
        grav = max((GRAVEDAD.get(e.get("tipo"), 1) for e in inc["eventos"]), default=1)
        inc["gravedad"] = NOMBRE_GRAVEDAD[grav]
        inc["tipos"] = sorted({e.get("tipo") for e in inc["eventos"]})
        inc["usuarios"] = sorted({e.get("usuario") for e in inc["eventos"] if e.get("usuario")})
        inc["n_eventos"] = len(inc["eventos"])
        inc["duracion_s"] = _segundos(inc["inicio"], inc["fin"])
        inc["contenido"] = any(e.get("tipo") in ("enlace_contenido", "credencial_revocada",
                                                 "correo_reportado", "incidente_resuelto")
                               for e in inc["eventos"])
        inc["resumen"] = _resumen(inc)
    incidentes.sort(key=lambda i: (i["inicio"] or ""), reverse=True)
    return incidentes


def _resumen(inc):
    if not inc["vinculos"]:
        return f"Evento aislado: {inc['tipos'][0]}. No encadena con ningún otro evento por una regla conocida."
    cadena = " → ".join([inc["vinculos"][0]["de"]] + [v["a"] for v in inc["vinculos"]])
    cola = " La respuesta defensiva ya actuó." if inc["contenido"] else " Sin contención registrada."
    return f"Cadena {cadena}." + cola


def resumen_correlacion(incidentes):
    """Cifras del panel: cuántos incidentes, de qué gravedad y cuántos quedaron contenidos."""
    incs = incidentes or []
    por_gravedad = {}
    for i in incs:
        por_gravedad[i["gravedad"]] = por_gravedad.get(i["gravedad"], 0) + 1
    encadenados = [i for i in incs if i["vinculos"]]
    return {"incidentes": len(incs), "encadenados": len(encadenados),
            "aislados": len(incs) - len(encadenados),
            "contenidos": sum(1 for i in incs if i["contenido"]),
            "por_gravedad": por_gravedad,
            "eventos_agrupados": sum(i["n_eventos"] for i in incs)}
