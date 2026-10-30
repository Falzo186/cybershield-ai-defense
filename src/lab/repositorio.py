"""Repositorio: ÚNICO punto de acceso a la BD. Consultas fijas y parametrizadas, autorizador y auditoría.

Es la última capa de defensa: aunque la IA o la capa de herramientas fallen, aquí se vuelve a
comprobar el acceso. No existe ningún camino para ejecutar SQL arbitrario.
"""
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import ataque_ia, correos, documentos, permisos, schema, seed, sesion
from .permisos import Identidad

# CS_LAB_DB permite usar otra BD (p. ej. la prueba de extremo a extremo usa una temporal y no toca data/lab.db).
RUTA_DB = Path(os.getenv("CS_LAB_DB") or Path(__file__).resolve().parents[2] / "data" / "lab.db")
# Salida para un SIEM (p. ej. Wazuh, aún sin integrar): una línea JSON por evento relevante.
RUTA_EVENTOS = RUTA_DB.parent / "eventos.jsonl"
PARTIDA = None  # id de la partida actual; lo fija server/app.py al arrancar

# Acciones de auditoría que van al JSONL -> (tipo de evento, equipo que actúa). Además, todo DENEGADO de una
# consulta o herramienta sale como "autorizacion_denegada" (equipo "rojo" en batallas IA vs IA; null si no se sabe).
EVENTOS_SIEM = {
    "CLIC_ENLACE": ("clic_enlace", "azul"), "CLIC_BLOQUEADO": ("clic_bloqueado", "azul"),
    "ENLACE_CONTENIDO": ("enlace_contenido", "azul"), "CORREO_REPORTADO": ("correo_reportado", "azul"),
    "PDF_ABIERTO": ("pdf_abierto", "azul"), "PDF_REPORTADO": ("pdf_reportado", "azul"),
    "MISION_COMPLETADA": ("mision_completada", "azul"), "PARTIDA_FINALIZADA": ("partida_finalizada", None),
    # Fase D: acciones del correo y de los documentos
    "CORREO_RECIBIDO": ("correo_recibido", "azul"), "CORREO_ABIERTO": ("correo_abierto", "azul"),
    "REMITENTE_VERIFICADO": ("remitente_verificado", "azul"), "ENLACE_INSPECCIONADO": ("enlace_inspeccionado", "azul"),
    "CORREO_ARCHIVADO": ("correo_archivado", "azul"), "RESPUESTA_ENVIADA": ("respuesta_enviada", "azul"),
    "ARCHIVO_AISLADO": ("archivo_aislado", "azul"),
    # Fase E: credenciales, incidentes y misiones
    "CREDENCIAL_COMPROMETIDA": ("credencial_comprometida", "azul"), "CREDENCIAL_REVOCADA": ("credencial_revocada", "azul"),
    "INCIDENTE_ABIERTO": ("incidente_abierto", "azul"), "INCIDENTE_ACTUALIZADO": ("incidente_actualizado", "azul"),
    "INCIDENTE_RESUELTO": ("incidente_resuelto", "azul"), "MISION_ASUMIDA": ("mision_asumida", "azul"),
    # Fase F: ataques IA dentro de la partida
    "ATAQUE_IA_LANZADO": ("ataque_ia_lanzado", "rojo"), "ATAQUE_IA_RESULTADO": ("ataque_ia_resultado", "rojo"),
    "DEFENSOR_IA_CONFIGURADO": ("defensor_ia_configurado", "azul"),
}
# Columnas de ataques_ia que se rellenan al terminar un ataque (constantes del código, nunca del cliente).
COLUMNAS_CIERRE_IA = ("estado", "resultado", "veredicto", "decision_ia", "origen_decision", "capa_bloqueo",
                      "herramienta", "objetivo", "sensibilidad_objetivo", "sensibilidad_expuesta", "categoria",
                      "prompt", "motivo", "error", "explicacion", "puntos_rojo", "puntos_azul",
                      "atq_ms", "atq_tokens_entrada", "atq_tokens_salida", "atq_carga_ms",
                      "def_ms", "def_tokens_entrada", "def_tokens_salida", "def_carga_ms")
SEVERIDADES = ("baja", "media", "alta", "critica")
# Estados del incidente y transiciones permitidas (no se puede reabrir ni saltar a resuelto sin investigar).
TRANSICIONES_INCIDENTE = {"abierto": ("en_investigacion",), "en_investigacion": ("resuelto",), "resuelto": ()}
_CANDADO_EVENTOS = threading.Lock()
LIMITE_FILAS = 50
NIVEL_RIESGO = {"PUBLICA": "BAJO", "INTERNA": "MEDIO", "CONFIDENCIAL": "ALTO", "CRITICA": "CRITICO"}

# Constantes del código (nunca vienen del usuario ni del modelo): tabla -> columnas y filtros permitidos.
ESPECIFICACION = {
    "productos": {"columnas": ("sku", "nombre", "stock", "precio"), "filtros": ("sku",)},
    "clientes": {"columnas": ("id", "nombre", "industria", "contacto"), "filtros": ("industria",)},
    "incidentes": {"columnas": ("id", "fecha", "sistema", "severidad", "causa_raiz"), "filtros": ("severidad",)},
    "configuracion_admin": {"columnas": ("clave", "valor"), "filtros": ("clave",)},
}


def _ahora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


class PermisoDenegado(Exception):
    def __init__(self, capa, motivo, requiere_autorizacion=False):
        super().__init__(motivo)
        self.capa = capa
        self.motivo = motivo
        self.requiere_autorizacion = requiere_autorizacion


class Autorizador:
    """Autorizaciones concedidas por humanos (analista/admin). El modelo no puede otorgarlas."""

    def __init__(self, conn):
        self.conn = conn

    def vigente(self, identidad, tabla):
        fila = self.conn.execute(
            "SELECT 1 FROM autorizaciones WHERE usuario=? AND recurso=? AND vigente=1",
            (identidad.usuario, tabla)).fetchone()
        return fila is not None

    def otorgar(self, otorgante, usuario, tabla):
        if otorgante.rol not in ("analista", "admin"):
            raise PermisoDenegado("autorizador", "solo analista o admin pueden otorgar autorizaciones")
        if permisos.TABLAS.get(tabla) != "CONFIDENCIAL":
            raise PermisoDenegado("autorizador", "solo se delegan recursos CONFIDENCIALES; los CRITICOS nunca")
        self.conn.execute(
            "INSERT INTO autorizaciones(usuario,recurso,vigente,otorgada_por,fecha) VALUES(?,?,1,?,?)",
            (usuario, tabla, otorgante.usuario, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()

    def revocar(self, otorgante, usuario, tabla):
        if otorgante.rol not in ("analista", "admin"):
            raise PermisoDenegado("autorizador", "solo analista o admin pueden revocar autorizaciones")
        self.conn.execute("UPDATE autorizaciones SET vigente=0 WHERE usuario=? AND recurso=?", (usuario, tabla))
        self.conn.commit()


class Repositorio:
    def __init__(self, conn, ruta_eventos=None):
        conn.row_factory = sqlite3.Row
        self.conn = conn
        self.autorizador = Autorizador(conn)
        self.ruta_eventos = ruta_eventos  # None = no se escribe JSONL (p. ej. BD en memoria de los tests)

    def identidad(self, usuario):
        """La identidad sale de la tabla de usuarios (el sistema), nunca de un prompt."""
        fila = self.conn.execute("SELECT usuario, rol FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
        if fila is None:
            raise KeyError(f"usuario desconocido: {usuario}")
        return Identidad(fila["usuario"], fila["rol"])

    def registrar(self, identidad, accion, recurso, resultado, nivel, equipo=None):
        """equipo = quién actúa ("rojo" en las batallas IA vs IA). Si no se indica, sale de EVENTOS_SIEM (acciones
        del buzón = azul) o queda NULL."""
        # ISO 8601 completo con zona horaria (p. ej. 2026-10-22T13:47:05-06:00): ordenable y listo para un SIEM.
        ts = datetime.now().astimezone().isoformat(timespec="seconds")
        usuario, rol = getattr(identidad, "usuario", None), getattr(identidad, "rol", None)
        equipo = equipo or EVENTOS_SIEM.get(accion, (None, None))[1]
        self.conn.execute(
            "INSERT INTO auditoria(ts,usuario,rol,accion,recurso,resultado,nivel_riesgo,equipo,partida) "
            "VALUES(?,?,?,?,?,?,?,?,?)", (ts, usuario, rol, accion, recurso, resultado, nivel, equipo, PARTIDA))
        self.conn.commit()
        self._evento_siem(ts, usuario, rol, accion, recurso, resultado, nivel, equipo)

    def denegaciones(self, partida, equipo):
        """Filas DENEGADO de la partida atribuidas a ese equipo (p. ej. intentos de Rojo frenados por las capas)."""
        return self.conn.execute(
            "SELECT COUNT(*) FROM auditoria WHERE partida=? AND equipo=? AND resultado='DENEGADO'",
            (partida, equipo)).fetchone()[0]

    def _evento_siem(self, ts, usuario, rol, accion, recurso, resultado, nivel, equipo):
        """Mismo registro que auditoría, como una línea JSON en eventos.jsonl (solo eventos relevantes). Un fallo
        al escribir el archivo nunca tumba la auditoría (la tabla SQLite sigue siendo la fuente de verdad)."""
        if not self.ruta_eventos:
            return
        tipo = EVENTOS_SIEM.get(accion, ("autorizacion_denegada",) if resultado == "DENEGADO" else (None,))[0]
        if tipo is None:
            return
        linea = json.dumps({"timestamp": ts, "partida": PARTIDA, "equipo": equipo, "usuario": usuario, "rol": rol,
                            "tipo": tipo, "accion": accion, "recurso": recurso, "resultado": resultado,
                            "riesgo": nivel, "origen": "cybershield-lab"}, ensure_ascii=False)
        try:
            with _CANDADO_EVENTOS, open(self.ruta_eventos, "a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except OSError:
            pass

    def consultar(self, identidad, tabla, filtros=None, equipo=None):
        esp = ESPECIFICACION.get(tabla)
        if esp is None:
            raise ValueError(f"tabla no permitida: {tabla}")
        filtros = filtros or {}
        invalidos = set(filtros) - set(esp["filtros"])
        if invalidos:
            raise ValueError(f"filtros no permitidos: {sorted(invalidos)}")
        if not all(isinstance(v, str) for v in filtros.values()):
            raise ValueError("los valores de filtro deben ser texto")

        sens = permisos.TABLAS[tabla]
        acceso = permisos.evaluar_acceso(identidad, sens, self.autorizador.vigente(identidad, tabla))
        if not acceso.permitido:
            self.registrar(identidad, "CONSULTA", tabla, "DENEGADO", NIVEL_RIESGO[sens], equipo)
            raise PermisoDenegado("repositorio", acceso.motivo, acceso.requiere_autorizacion)

        sql = f"SELECT {', '.join(esp['columnas'])} FROM {tabla}"  # solo constantes del código
        if filtros:
            sql += " WHERE " + " AND ".join(f"{k} = ?" for k in filtros)
        sql += f" LIMIT {LIMITE_FILAS}"
        filas = self.conn.execute(sql, tuple(filtros.values())).fetchall()
        self.registrar(identidad, "CONSULTA", tabla, "PERMITIDO", NIVEL_RIESGO[sens], equipo)
        return [dict(f) for f in filas]

    # ---------- buzón de entrenamiento (fuera de TABLAS: ninguna herramienta de la IA puede leerlo) ----------
    def crear_correo(self, partida, plantilla_id, para_usuario):
        """Correo desde una plantilla FIJA. El enlace lo genera el servidor (id aleatorio, ruta local /l/<id>).
        KeyError si la plantilla o el usuario no existen. -> {id, para_usuario, asunto, plantilla_id, ts}"""
        self.identidad(para_usuario)
        enlace_id = secrets.token_urlsafe(9)
        ruta = "/l/" + enlace_id
        ahora = datetime.now()
        de, asunto, cuerpo = correos.componer(plantilla_id, para_usuario, ruta, ahora.strftime("%d/%m/%Y"))
        adjunto = correos.adjunto(plantilla_id)
        ts = ahora.isoformat(timespec="seconds")
        with self.conn:  # correo y enlace en una sola transacción
            cur = self.conn.execute(
                "INSERT INTO correos(partida,de,para_usuario,asunto,cuerpo,plantilla_id,ts,adjunto) "
                "VALUES(?,?,?,?,?,?,?,?)", (partida, de, para_usuario, asunto, cuerpo, plantilla_id, ts, adjunto))
            self.conn.execute("INSERT INTO enlaces(id,correo_id,ruta_local) VALUES(?,?,?)",
                              (enlace_id, cur.lastrowid, ruta))
        self.registrar(self.identidad(para_usuario), "CORREO_RECIBIDO", f"correo:{cur.lastrowid}", plantilla_id, "BAJO")
        return {"id": cur.lastrowid, "para_usuario": para_usuario, "asunto": asunto, "plantilla_id": plantilla_id,
                "ts": ts}

    def buzon(self, partida, usuario, limite=LIMITE_FILAS):
        filas = self.conn.execute(
            "SELECT c.id, c.de, c.asunto, c.cuerpo, c.plantilla_id, c.ts, e.ruta_local AS enlace, "
            "r.correo_id IS NOT NULL AS reportado, k.correo_id IS NOT NULL AS contenido, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'CLIC_ENLACE' AND a.recurso = 'correo:' || c.id) "
            "AS clicado, c.adjunto, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'PDF_ABIERTO' AND a.recurso = 'correo:' || c.id) "
            "AS pdf_abierto, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'PDF_REPORTADO' AND a.recurso = 'correo:' || c.id) "
            "AS pdf_reportado, "
            "(SELECT group_concat(participante, ', ') FROM (SELECT l.participante FROM lecturas l "
            " WHERE l.correo_id = c.id ORDER BY l.ts, l.rowid)) AS leido_por, "  # en orden de lectura
            "EXISTS(SELECT 1 FROM archivados x WHERE x.correo_id = c.id) AS archivado, "
            "EXISTS(SELECT 1 FROM aislamientos s WHERE s.correo_id = c.id) AS aislado, "
            "(SELECT COUNT(*) FROM respuestas q WHERE q.correo_id = c.id) AS respuestas "
            "FROM correos c JOIN enlaces e ON e.correo_id = c.id LEFT JOIN reportes r ON r.correo_id = c.id "
            "LEFT JOIN contenciones k ON k.correo_id = c.id "
            "WHERE c.partida = ? AND c.para_usuario = ? ORDER BY c.id DESC LIMIT ?",
            (partida, usuario, limite)).fetchall()
        return [self._correo_publico(dict(f)) for f in filas]

    @staticmethod
    def _correo_publico(f):
        """Añade lo que sale de la plantilla (prioridad, texto visible del enlace) y la carpeta: archivados > sospechosos
        (reportado) > entrada. adjunto -> {id, archivo, titulo, riesgo} del catálogo fijo, o None."""
        p = correos.PLANTILLAS.get(f["plantilla_id"], {})
        carpeta = "archivados" if f["archivado"] else "sospechosos" if f["reportado"] else "entrada"
        return {**f, "adjunto": documentos.info(f["adjunto"]), "leido": bool(f["leido_por"]),
                "prioridad": p.get("prioridad", "normal"), "texto_enlace": p.get("texto_enlace"), "carpeta": carpeta}

    def _correo(self, partida, usuario, correo_id):
        """El correo correo_id del buzón de ese usuario en esa partida, o None (no existe o no es suyo)."""
        return next((c for c in self.buzon(partida, usuario, limite=-1) if c["id"] == correo_id), None)

    # ---------- acciones del correo (Fase D): todas exigen que el correo sea del buzón del usuario en la partida ----------
    def marcar_leido(self, partida, usuario, correo_id, participante):
        """-> "nuevo" (primera lectura de ese participante) · "ya" · None (no es suyo). Solo la primera se audita."""
        if self._correo(partida, usuario, correo_id) is None:
            return None
        with self.conn:
            cur = self.conn.execute("INSERT OR IGNORE INTO lecturas(correo_id,participante,ts) VALUES(?,?,?)",
                                    (correo_id, participante, _ahora()))
        if not cur.rowcount:
            return "ya"
        self.registrar(self.identidad(usuario), "CORREO_ABIERTO", f"correo:{correo_id}", participante, "BAJO")
        return "nuevo"

    def archivar(self, partida, usuario, correo_id, participante, archivar=True):
        """Archiva o devuelve a su carpeta. -> True (cambió) · False (ya estaba así) · None (no es suyo)."""
        c = self._correo(partida, usuario, correo_id)
        if c is None:
            return None
        if bool(c["archivado"]) == archivar:
            return False
        with self.conn:
            if archivar:
                self.conn.execute("INSERT INTO archivados(correo_id,participante,ts) VALUES(?,?,?)",
                                  (correo_id, participante, _ahora()))
            else:
                self.conn.execute("DELETE FROM archivados WHERE correo_id=?", (correo_id,))
        self.registrar(self.identidad(usuario), "CORREO_ARCHIVADO", f"correo:{correo_id}",
                       "ARCHIVADO" if archivar else "DESARCHIVADO", "BAJO")
        return True

    def verificar_remitente(self, partida, usuario, correo_id):
        """Comprueba el dominio del remitente contra el oficial. -> {de, dominio, oficial, parecido, detalle,
        indicadores} o None."""
        c = self._correo(partida, usuario, correo_id)
        if c is None:
            return None
        v = correos.verificar_remitente(c["de"])
        resultado = "OFICIAL" if v["oficial"] else "IMITACION" if v["parecido"] else "EXTERNO"
        self.registrar(self.identidad(usuario), "REMITENTE_VERIFICADO", f"correo:{correo_id}", resultado, "BAJO")
        indicadores = correos.PLANTILLAS.get(c["plantilla_id"], {}).get("indicadores", [])
        return {"de": c["de"], **v, "indicadores": list(indicadores)}

    def inspeccionar_enlace(self, partida, usuario, correo_id):
        """Muestra el destino REAL del enlace sin abrirlo. -> {texto_mostrado, destino_real, coincide, explicacion} o None."""
        c = self._correo(partida, usuario, correo_id)
        if c is None:
            return None
        self.registrar(self.identidad(usuario), "ENLACE_INSPECCIONADO", f"correo:{correo_id}", "INSPECCIONADO", "BAJO")
        mostrado = c["texto_enlace"] or c["enlace"]
        return {"texto_mostrado": mostrado, "destino_real": c["enlace"], "coincide": mostrado == c["enlace"],
                "explicacion": ("El correo presenta el enlace como «" + mostrado + "», pero lleva a «" + c["enlace"] +
                                "» (página de entrenamiento del laboratorio). En un ataque real, ese destino sería el "
                                "del atacante: no coincide con lo que se anuncia.")}

    def responder(self, partida, usuario, correo_id, participante, texto):
        """Respuesta que NUNCA sale del laboratorio. -> {id, ts, a_phishing} o None. ValueError si el texto no vale."""
        texto = (texto or "").strip()
        if not 1 <= len(texto) <= 1000:
            raise ValueError("La respuesta debe tener entre 1 y 1000 caracteres.")
        c = self._correo(partida, usuario, correo_id)
        if c is None:
            return None
        a_phishing = not correos.verificar_remitente(c["de"])["oficial"]
        ts = _ahora()
        with self.conn:
            cur = self.conn.execute("INSERT INTO respuestas(correo_id,participante,texto,ts) VALUES(?,?,?,?)",
                                    (correo_id, participante, texto, ts))
        self.registrar(self.identidad(usuario), "RESPUESTA_ENVIADA", f"correo:{correo_id}",
                       "A_PHISHING" if a_phishing else "OK", "MEDIO" if a_phishing else "BAJO")
        return {"id": cur.lastrowid, "ts": ts, "a_phishing": a_phishing}

    def respuestas(self, partida, usuario):
        """Carpeta «Enviados» de Azul: sus respuestas, con el correo al que contestan."""
        filas = self.conn.execute(
            "SELECT q.id, q.correo_id, q.participante, q.texto, q.ts, c.de AS para, c.asunto FROM respuestas q "
            "JOIN correos c ON c.id = q.correo_id WHERE c.partida = ? AND c.para_usuario = ? ORDER BY q.id DESC",
            (partida, usuario)).fetchall()
        return [dict(f) for f in filas]

    def aislar_adjunto(self, partida, usuario, correo_id, participante):
        """Aísla el PDF adjunto: ya no se puede previsualizar. -> "aislado" · "ya_aislado" · "sin_adjunto" · None."""
        c = self._correo(partida, usuario, correo_id)
        if c is None:
            return None
        if not c["adjunto"]:
            return "sin_adjunto"
        if c["aislado"]:
            return "ya_aislado"
        with self.conn:
            self.conn.execute("INSERT INTO aislamientos(correo_id,participante,ts) VALUES(?,?,?)",
                              (correo_id, participante, _ahora()))
        self.registrar(self.identidad(usuario), "ARCHIVO_AISLADO", f"correo:{correo_id}", c["adjunto"]["id"], "BAJO")
        return "aislado"

    def enviados_rojo(self, partida):
        """Carpeta «Enviados» de Rojo: sus correos y lo que una campaña de phishing real podría medir (clic en el
        enlace, apertura del adjunto, credencial enviada a su página). No revela si se leyó ni si se reportó."""
        filas = self.conn.execute(
            "SELECT c.id, c.para_usuario, c.asunto, c.plantilla_id, c.ts, c.adjunto IS NOT NULL AS con_adjunto, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'CLIC_ENLACE' AND a.recurso = 'correo:' || c.id) AS clicado, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'PDF_ABIERTO' AND a.recurso = 'correo:' || c.id) "
            "AS adjunto_abierto, "
            "EXISTS(SELECT 1 FROM compromisos_credencial q WHERE q.correo_id = c.id) AS credencial_obtenida "
            "FROM correos c WHERE c.partida = ? ORDER BY c.id DESC", (partida,)).fetchall()
        return [dict(f) for f in filas]

    def registrar_clic(self, enlace_id):
        """Registra en auditoría el clic en un enlace de entrenamiento. Si Azul ya lo contuvo, el clic queda
        BLOQUEADO (no es un CLIC_ENLACE). -> {correo_id, para_usuario, contenido} o None."""
        fila = self.conn.execute(
            "SELECT c.id AS correo_id, c.para_usuario, k.correo_id IS NOT NULL AS contenido "
            "FROM enlaces e JOIN correos c ON c.id = e.correo_id LEFT JOIN contenciones k ON k.correo_id = c.id "
            "WHERE e.id = ?", (enlace_id,)).fetchone()
        if fila is None:
            return None
        clic = {"correo_id": fila["correo_id"], "para_usuario": fila["para_usuario"], "contenido": bool(fila["contenido"])}
        if clic["contenido"]:
            self.registrar(self.identidad(clic["para_usuario"]), "CLIC_BLOQUEADO", f"correo:{clic['correo_id']}",
                           "BLOQUEADO", "BAJO")
        else:
            self.registrar(self.identidad(clic["para_usuario"]), "CLIC_ENLACE", f"correo:{clic['correo_id']}",
                           "CLIC", "ALTO")
        return clic

    def contener_enlace(self, partida, usuario, correo_id):
        """Azul contiene (bloquea) el enlace de un correo SUYO de esta partida que ya fue clicado.
        -> "contenido" (nuevo) · "ya_contenido" · "sin_clic" (no hay clic que contener) · None (no es suyo)."""
        fila = next((c for c in self.buzon(partida, usuario, limite=-1) if c["id"] == correo_id), None)
        if fila is None:
            return None
        if fila["contenido"]:
            return "ya_contenido"
        if not fila["clicado"]:
            return "sin_clic"
        with self.conn:
            self.conn.execute("INSERT INTO contenciones(correo_id,usuario,ts) VALUES(?,?,?)",
                              (correo_id, usuario, datetime.now().astimezone().isoformat(timespec="seconds")))
        self.registrar(self.identidad(usuario), "ENLACE_CONTENIDO", f"correo:{correo_id}", "CONTENIDO", "BAJO")
        return "contenido"

    def reportar_correo(self, partida, usuario, correo_id):
        """Azul marca un correo SUYO de esta partida como sospechoso. Un correo se reporta una sola vez.
        -> True (reporte nuevo) · False (ya estaba reportado) · None (no existe o no es de ese usuario/partida)."""
        fila = self.conn.execute("SELECT 1 FROM correos WHERE id=? AND partida=? AND para_usuario=?",
                                 (correo_id, partida, usuario)).fetchone()
        if fila is None:
            return None
        with self.conn:
            cur = self.conn.execute("INSERT OR IGNORE INTO reportes(correo_id,usuario,ts) VALUES(?,?,?)",
                                    (correo_id, usuario, datetime.now().astimezone().isoformat(timespec="seconds")))
        if not cur.rowcount:
            return False
        self.registrar(self.identidad(usuario), "CORREO_REPORTADO", f"correo:{correo_id}", "REPORTADO", "BAJO")
        return True

    def evento_pdf(self, partida, usuario, correo_id, tipo):
        """Azul abre o reporta el PDF adjunto de un correo SUYO de esta partida. No se ejecuta nada: es solo un
        evento en auditoría. tipo = "pdf_abierto" | "pdf_reportado" (un PDF se reporta una sola vez).
        -> {"doc": {...}} · "sin_adjunto" · "ya_reportado" · None (no es suyo)."""
        fila = self._correo(partida, usuario, correo_id)
        if fila is None:
            return None
        if not fila["adjunto"]:
            return "sin_adjunto"
        if tipo == "pdf_abierto" and fila["aislado"]:
            return "aislado"  # un adjunto aislado ya no se puede previsualizar
        if tipo == "pdf_reportado" and fila["pdf_reportado"]:
            return "ya_reportado"
        accion, resultado = ("PDF_ABIERTO", "ABIERTO") if tipo == "pdf_abierto" else ("PDF_REPORTADO", "REPORTADO")
        self.registrar(self.identidad(usuario), accion, f"correo:{correo_id}", resultado, "BAJO")
        r = {"doc": fila["adjunto"]}
        if tipo == "pdf_abierto":  # lo que muestra el visor seguro (texto del propio archivo + análisis)
            r["vista"] = documentos.vista_previa(fila["adjunto"]["id"], f"Adjunto del correo «{fila['asunto']}» "
                                                                       f"de {fila['de']}")
        return r

    def logros_rojo(self, partida):
        """Lo que cuenta para el puntaje de Rojo en la partida: correos con enlace clicado y NO contenido, correos
        con PDF abierto y NO reportado ni aislado, y credenciales comprometidas sin revocar.
        -> {enlaces_sin_contener, pdfs_sin_reportar, credenciales_sin_revocar}"""
        fila = self.conn.execute(
            "SELECT COALESCE(SUM(clicado AND NOT contenido), 0) AS enlaces, "
            "COALESCE(SUM(pdf_abierto AND NOT pdf_reportado AND NOT aislado), 0) AS pdfs FROM ("
            "  SELECT EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'CLIC_ENLACE' AND a.recurso = 'correo:' || c.id)"
            "         AS clicado,"
            "         EXISTS(SELECT 1 FROM contenciones k WHERE k.correo_id = c.id) AS contenido,"
            "         EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'PDF_ABIERTO' AND a.recurso = 'correo:' || c.id)"
            "         AS pdf_abierto,"
            "         EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'PDF_REPORTADO' AND a.recurso = 'correo:' || c.id)"
            "         AS pdf_reportado,"
            "         EXISTS(SELECT 1 FROM aislamientos s WHERE s.correo_id = c.id) AS aislado"
            "  FROM correos c WHERE c.partida = ?)", (partida,)).fetchone()
        cred = self.conn.execute("SELECT COUNT(*) FROM compromisos_credencial WHERE partida=? AND revocada_ts IS NULL",
                                 (partida,)).fetchone()[0]
        return {"enlaces_sin_contener": fila["enlaces"], "pdfs_sin_reportar": fila["pdfs"], "credenciales_sin_revocar": cred}

    # ---------- credenciales ficticias (Fase E) ----------
    # Cada usuario semilla tiene UNA credencial ficticia: la de su cuenta de correo. No hay contraseñas guardadas:
    # «comprometida» es un estado de la partida, no un secreto.
    def comprometer_credencial(self, partida, enlace_id):
        """El empleado «envía» su contraseña en la página de un enlace de phishing. Exige que el enlace sea de esta
        partida, que su plantilla pida credenciales, que se haya clicado y que no esté contenido.
        -> {usuario, correo_id, nuevo} · "no_existe" · "no_pide" · "sin_clic" · "contenido"."""
        fila = self.conn.execute(
            "SELECT c.id, c.para_usuario, c.plantilla_id, "
            "EXISTS(SELECT 1 FROM contenciones k WHERE k.correo_id = c.id) AS contenido, "
            "EXISTS(SELECT 1 FROM auditoria a WHERE a.accion = 'CLIC_ENLACE' AND a.recurso = 'correo:' || c.id) AS clicado "
            "FROM enlaces e JOIN correos c ON c.id = e.correo_id WHERE e.id = ? AND c.partida = ?",
            (enlace_id, partida)).fetchone()
        if fila is None:
            return "no_existe"
        if not correos.PLANTILLAS.get(fila["plantilla_id"], {}).get("pide_credenciales"):
            return "no_pide"
        if fila["contenido"]:
            return "contenido"
        if not fila["clicado"]:
            return "sin_clic"
        with self.conn:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO compromisos_credencial(partida,usuario,correo_id,ts) VALUES(?,?,?,?)",
                (partida, fila["para_usuario"], fila["id"], _ahora()))
        nuevo = bool(cur.rowcount)  # ya comprometida (sin revocar): no se duplica
        if nuevo:
            self.registrar(self.identidad(fila["para_usuario"]), "CREDENCIAL_COMPROMETIDA", f"correo:{fila['id']}",
                           "COMPROMETIDA", "CRITICO")
        return {"usuario": fila["para_usuario"], "correo_id": fila["id"], "nuevo": nuevo}

    def pide_credenciales(self, correo_id):
        f = self.conn.execute("SELECT plantilla_id FROM correos WHERE id=?", (correo_id,)).fetchone()
        return bool(f and correos.PLANTILLAS.get(f["plantilla_id"], {}).get("pide_credenciales"))

    def credenciales(self, partida, usuario):
        """Estado de la credencial ficticia del usuario en la partida: historial de compromisos (el más reciente primero)."""
        filas = self.conn.execute(
            "SELECT q.id, q.correo_id, c.asunto, q.ts, q.revocada_ts, q.revocada_por FROM compromisos_credencial q "
            "JOIN correos c ON c.id = q.correo_id WHERE q.partida = ? AND q.usuario = ? ORDER BY q.id DESC",
            (partida, usuario)).fetchall()
        hist = [dict(f) for f in filas]
        return {"usuario": usuario, "cuenta": f"Cuenta de correo de {usuario} (credencial ficticia)",
                "estado": "comprometida" if any(h["revocada_ts"] is None for h in hist) else
                          "revocada" if hist else "segura", "historial": hist}

    def revocar_credencial(self, partida, usuario, participante):
        """-> "revocada" · "sin_compromiso" (no hay compromiso activo que revocar)."""
        with self.conn:
            cur = self.conn.execute(
                "UPDATE compromisos_credencial SET revocada_ts=?, revocada_por=? "
                "WHERE partida=? AND usuario=? AND revocada_ts IS NULL", (_ahora(), participante, partida, usuario))
        if not cur.rowcount:
            return "sin_compromiso"
        self.registrar(self.identidad(usuario), "CREDENCIAL_REVOCADA", f"credencial:{usuario}", participante, "BAJO")
        return "revocada"

    # ---------- ataques IA dentro de la partida (Fase F) ----------
    def identidad_atacante(self, partida):
        """Con qué identidad ataca la IA de Rojo: la de una credencial comprometida sin revocar (la más antigua) o,
        si no tiene ninguna, la de invitado. -> (usuario, "credencial_robada" | "invitado")"""
        f = self.conn.execute("SELECT usuario FROM compromisos_credencial WHERE partida=? AND revocada_ts IS NULL "
                              "ORDER BY id LIMIT 1", (partida,)).fetchone()
        return (f["usuario"], "credencial_robada") if f else (ataque_ia.USUARIO_SIN_CREDENCIAL, "invitado")

    def crear_ataque_ia(self, partida, lanzado_por, usuario, origen_identidad, tecnica, intensidad, modelo_atq,
                        modelo_def):
        """Reserva el siguiente número de ataque de la partida (estado en_curso). -> dict del ataque, o None si ya
        se lanzaron los ataque_ia.MAX_ATAQUES."""
        with self.conn:
            n = self.conn.execute("SELECT COUNT(*) FROM ataques_ia WHERE partida=?", (partida,)).fetchone()[0] + 1
            if n > ataque_ia.MAX_ATAQUES:
                return None
            cur = self.conn.execute(
                "INSERT INTO ataques_ia(partida,n,lanzado_por,usuario,origen_identidad,tecnica,intensidad,estado,"
                "modelo_atq,modelo_def,ts_inicio) VALUES(?,?,?,?,?,?,?,'en_curso',?,?,?)",
                (partida, n, lanzado_por, usuario, origen_identidad, tecnica, intensidad, modelo_atq, modelo_def,
                 _ahora()))
        self.registrar(self.identidad(usuario), "ATAQUE_IA_LANZADO", f"ataque_ia:{n}",
                       f"{lanzado_por} · {origen_identidad}", "MEDIO")
        return self.ataque_ia(cur.lastrowid)

    def cerrar_ataque_ia(self, ataque_id, **campos):
        """Guarda el desenlace de un ataque (solo columnas de COLUMNAS_CIERRE_IA). -> dict del ataque."""
        malas = set(campos) - set(COLUMNAS_CIERRE_IA)
        if malas:
            raise ValueError(f"columnas no permitidas: {sorted(malas)}")
        cols = list(campos)
        with self.conn:
            self.conn.execute(f"UPDATE ataques_ia SET {', '.join(c + '=?' for c in cols)}, ts_fin=? WHERE id=?",
                              (*[campos[c] for c in cols], _ahora(), ataque_id))
        a = self.ataque_ia(ataque_id)
        if a["estado"] == "terminado":
            nivel = "CRITICO" if a["resultado"] == "datos_expuestos" else "MEDIO" if a["resultado"] == "ia_enganada" else "BAJO"
            self.registrar(self.identidad(a["usuario"]), "ATAQUE_IA_RESULTADO", f"ataque_ia:{a['n']}",
                           a["resultado"].upper(), nivel)
        return a

    def ataque_ia(self, ataque_id):
        f = self.conn.execute("SELECT * FROM ataques_ia WHERE id=?", (ataque_id,)).fetchone()
        return dict(f) if f else None

    def ataques_ia(self, partida):
        return [dict(f) for f in self.conn.execute("SELECT * FROM ataques_ia WHERE partida=? ORDER BY n", (partida,))]

    def puntos_ia(self, partida):
        """Puntos de los ataques IA terminados -> {rojo, azul, lanzados, datos_expuestos, contenidos}."""
        f = self.conn.execute(
            "SELECT COALESCE(SUM(puntos_rojo),0) AS rojo, COALESCE(SUM(puntos_azul),0) AS azul, COUNT(*) AS lanzados, "
            "COALESCE(SUM(resultado='datos_expuestos'),0) AS expuestos, COALESCE(SUM(resultado='contenido'),0) AS cont "
            "FROM ataques_ia WHERE partida=?", (partida,)).fetchone()
        return {"rojo": f["rojo"], "azul": f["azul"], "lanzados": f["lanzados"], "datos_expuestos": f["expuestos"],
                "contenidos": f["cont"]}

    # ---------- incidentes de la partida (Fase E) ----------
    def abrir_incidente(self, partida, usuario, participante, titulo, severidad, correo_id=None):
        """ValueError si título/severidad no valen; None si correo_id no es del buzón del usuario. -> incidente"""
        titulo = (titulo or "").strip()
        if not 3 <= len(titulo) <= 80:
            raise ValueError("El título debe tener entre 3 y 80 caracteres.")
        if severidad not in SEVERIDADES:
            raise ValueError("Severidad no válida (baja, media, alta o critica).")
        if correo_id is not None and self._correo(partida, usuario, correo_id) is None:
            return None
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO incidentes_partida(partida,titulo,severidad,estado,correo_id,abierto_por,ts_apertura) "
                "VALUES(?,?,?,'abierto',?,?,?)", (partida, titulo, severidad, correo_id, participante, _ahora()))
        self.registrar(self.identidad(usuario), "INCIDENTE_ABIERTO", f"incidente:{cur.lastrowid}",
                       f"{severidad} · {participante}", "MEDIO")
        return self._incidente(partida, cur.lastrowid)

    def _incidente(self, partida, inc_id):
        f = self.conn.execute("SELECT * FROM incidentes_partida WHERE id=? AND partida=?", (inc_id, partida)).fetchone()
        return dict(f) if f else None

    def incidentes(self, partida):
        return [dict(f) for f in self.conn.execute(
            "SELECT * FROM incidentes_partida WHERE partida=? ORDER BY id DESC", (partida,)).fetchall()]

    def pendiente_para_resolver(self, partida, inc):
        """Lo que impide cerrar el incidente: si tiene correo, su enlace clicado debe estar contenido y la credencial
        que se comprometió por él, revocada. -> lista de motivos (vacía = se puede resolver)."""
        if inc["correo_id"] is None:
            return []
        f = self.conn.execute(
            "SELECT EXISTS(SELECT 1 FROM auditoria a WHERE a.accion='CLIC_ENLACE' AND a.recurso='correo:' || c.id) AS clic, "
            "EXISTS(SELECT 1 FROM contenciones k WHERE k.correo_id = c.id) AS contenido, "
            "EXISTS(SELECT 1 FROM compromisos_credencial q WHERE q.correo_id = c.id AND q.revocada_ts IS NULL) AS cred "
            "FROM correos c WHERE c.id = ? AND c.partida = ?", (inc["correo_id"], partida)).fetchone()
        motivos = []
        if f and f["clic"] and not f["contenido"]:
            motivos.append("el enlace del correo se clicó y aún no está contenido")
        if f and f["cred"]:
            motivos.append("la credencial comprometida por ese correo aún no está revocada")
        return motivos

    def avanzar_incidente(self, partida, usuario, inc_id, participante, estado, resolucion=None):
        """abierto -> en_investigacion -> resuelto. -> incidente · None (no existe) · ValueError (transición o
        resolución no válida, o amenaza sin contener: el mensaje dice qué falta)."""
        inc = self._incidente(partida, inc_id)
        if inc is None:
            return None
        if estado not in TRANSICIONES_INCIDENTE[inc["estado"]]:
            raise ValueError(f"No se puede pasar de «{inc['estado']}» a «{estado}».")
        if estado == "resuelto":
            resolucion = (resolucion or "").strip()
            if not 10 <= len(resolucion) <= 500:
                raise ValueError("La resolución debe explicar en 10-500 caracteres qué se hizo.")
            if motivos := self.pendiente_para_resolver(partida, inc):
                raise ValueError("Aún no se puede resolver: " + " y ".join(motivos) + ".")
            with self.conn:
                self.conn.execute("UPDATE incidentes_partida SET estado='resuelto', resolucion=?, resuelto_por=?, "
                                  "ts_resolucion=? WHERE id=?", (resolucion, participante, _ahora(), inc_id))
            self.registrar(self.identidad(usuario), "INCIDENTE_RESUELTO", f"incidente:{inc_id}", participante, "BAJO")
        else:
            with self.conn:
                self.conn.execute("UPDATE incidentes_partida SET estado=? WHERE id=?", (estado, inc_id))
            self.registrar(self.identidad(usuario), "INCIDENTE_ACTUALIZADO", f"incidente:{inc_id}",
                           f"{estado} · {participante}", "BAJO")
        return self._incidente(partida, inc_id)

    # ---------- misiones del Equipo Azul ----------
    def misiones(self, partida, usuario, transcurrido_s=None):
        """Todas las misiones con el progreso de ese usuario EN ESA PARTIDA. estado: completada · bloqueada (falta
        alguna de depende_de) · vencida (pendiente y pasado su plazo: aún vale la mitad) · pendiente.
        transcurrido_s = segundos desde el inicio de la partida (None = sin reloj: nada vence)."""
        filas = self.conn.execute(
            "SELECT m.id, m.titulo, m.condicion_evento, m.puntos, m.prioridad, m.plazo_s, m.depende_de, m.descripcion, "
            "COALESCE(p.estado, 'pendiente') AS estado, p.ts, p.completada_por, p.evidencia, "
            "COALESCE(p.puntos_obtenidos, CASE WHEN p.estado = 'completada' THEN m.puntos END) AS puntos_obtenidos, "
            "p.a_tiempo, s.participante AS responsable "
            "FROM misiones m LEFT JOIN progreso_mision p ON p.mision_id = m.id AND p.partida = ? AND p.usuario = ? "
            "LEFT JOIN asignaciones_mision s ON s.mision_id = m.id AND s.partida = ? ORDER BY m.id",
            (partida, usuario, partida)).fetchall()
        lista = [dict(f) for f in filas]
        hechas = {m["id"] for m in lista if m["estado"] == "completada"}
        titulos = {m["id"]: m["titulo"] for m in lista}
        for m in lista:
            m["depende_de"] = [int(x) for x in m["depende_de"].split(",") if x.strip()]
            m["requiere"] = [titulos[d] for d in m["depende_de"] if d not in hechas and d in titulos]
            if m["estado"] != "completada":
                if m["requiere"]:
                    m["estado"] = "bloqueada"
                elif m["plazo_s"] is not None and transcurrido_s is not None and transcurrido_s > m["plazo_s"]:
                    m["estado"] = "vencida"
            m["a_tiempo"] = None if m["a_tiempo"] is None else bool(m["a_tiempo"])
        return lista

    def _completar(self, partida, usuario, mision, participante=None, evidencia=None, transcurrido_s=None):
        """Marca completada si no lo estaba, con quién, la evidencia y los puntos (mitad fuera de plazo).
        -> dict de la misión completada AHORA, o None si ya lo estaba."""
        puntos, a_tiempo = sesion.puntos_mision(mision["puntos"], mision["plazo_s"], transcurrido_s)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO progreso_mision(partida,usuario,mision_id,estado,ts,completada_por,evidencia,puntos_obtenidos,"
                "a_tiempo) VALUES(?,?,?,'completada',?,?,?,?,?) "
                "ON CONFLICT(partida, usuario, mision_id) DO UPDATE SET estado='completada', ts=excluded.ts, "
                "completada_por=excluded.completada_por, evidencia=excluded.evidencia, "
                "puntos_obtenidos=excluded.puntos_obtenidos, a_tiempo=excluded.a_tiempo "
                "WHERE progreso_mision.estado <> 'completada'",
                (partida, usuario, mision["id"], _ahora(), participante, evidencia, puntos, int(a_tiempo)))
        if not cur.rowcount:
            return None
        self.registrar(self.identidad(usuario), "MISION_COMPLETADA", f"mision:{mision['id']}",
                       f"COMPLETADA +{puntos}" + ("" if a_tiempo else " (fuera de plazo)"), "BAJO")
        return {**mision, "estado": "completada", "completada_por": participante, "evidencia": evidencia,
                "puntos_obtenidos": puntos, "a_tiempo": a_tiempo}

    def completar_misiones_evento(self, partida, usuario, evento, participante=None, evidencia=None,
                                  transcurrido_s=None):
        """Completa las misiones cuya condición es ese evento y que no están bloqueadas por sus dependencias.
        'manual' nunca se completa por evento. -> misiones completadas AHORA (las ya completadas no se repiten)."""
        if evento == "manual":
            return []
        hechas = []
        for m in self.misiones(partida, usuario, transcurrido_s):
            if m["condicion_evento"] == evento and m["estado"] in ("pendiente", "vencida"):
                if r := self._completar(partida, usuario, m, participante, evidencia, transcurrido_s):
                    hechas.append(r)
        return hechas

    def misiones_bloqueadas(self, partida, usuario, evento):
        """Misiones de ese evento que NO se completaron por faltar una dependencia (para explicarlo en el aviso)."""
        return [{"id": m["id"], "titulo": m["titulo"], "requiere": m["requiere"]}
                for m in self.misiones(partida, usuario) if m["condicion_evento"] == evento and m["estado"] == "bloqueada"]

    def completar_mision_manual(self, partida, usuario, mision_id, participante=None, transcurrido_s=None):
        """Solo misiones con condición 'manual'. -> dict (nueva) · False (ya completada) · None (no existe o no es manual)
        · "bloqueada"."""
        m = next((m for m in self.misiones(partida, usuario, transcurrido_s) if m["id"] == mision_id), None)
        if m is None or m["condicion_evento"] != "manual":
            return None
        if m["estado"] == "bloqueada":
            return "bloqueada"
        return self._completar(partida, usuario, m, participante, "manual", transcurrido_s) or False

    def asumir_mision(self, partida, usuario, mision_id, participante):
        """El participante se hace responsable de la misión (reemplaza al anterior). -> True · None (no existe) ·
        "completada" (ya no tiene sentido asignarla)."""
        m = next((m for m in self.misiones(partida, usuario) if m["id"] == mision_id), None)
        if m is None:
            return None
        if m["estado"] == "completada":
            return "completada"
        with self.conn:
            self.conn.execute("INSERT INTO asignaciones_mision(partida,mision_id,participante,ts) VALUES(?,?,?,?) "
                              "ON CONFLICT(partida, mision_id) DO UPDATE SET participante=excluded.participante, "
                              "ts=excluded.ts", (partida, mision_id, participante, _ahora()))
        self.registrar(self.identidad(usuario), "MISION_ASUMIDA", f"mision:{mision_id}", participante, "BAJO")
        return True

    def puntos_azul(self, partida, usuario):
        return sum(m["puntos_obtenidos"] or 0 for m in self.misiones(partida, usuario) if m["estado"] == "completada")

    def auditoria(self, limite=50):
        filas = self.conn.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
        return [dict(f) for f in filas]


def abrir(ruta=None, ruta_eventos=None):
    """ruta_eventos: archivo JSONL de eventos. Por defecto data/eventos.jsonl junto a la BD del laboratorio; una BD
    en memoria no escribe eventos salvo que se indique un archivo."""
    ruta = str(ruta or RUTA_DB)
    if ruta_eventos is None and ruta != ":memory:":
        ruta_eventos = Path(ruta).parent / RUTA_EVENTOS.name
    if ruta != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")  # correos/enlaces referencian usuarios/correos
    schema.crear(conn)
    seed.sembrar(conn)
    return Repositorio(conn, ruta_eventos)


_DEFECTO = None


def por_defecto():
    global _DEFECTO
    if _DEFECTO is None:
        _DEFECTO = abrir()
    return _DEFECTO
