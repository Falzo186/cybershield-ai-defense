"""Aplicaciones del escritorio por permiso (Fase B). Lógica pura: catálogo, recomendaciones de seguridad y la
información de Recursos y Ayuda.

El catálogo es la FUENTE ÚNICA de qué aplicación ve cada equipo y con qué permiso. El escritorio lo pide al servidor
para pintar iconos y ventanas, y las rutas nuevas (archivos, seguridad) lo usan para decidir el acceso. Las rutas
anteriores siguen con sus comprobaciones propias; una prueba verifica que coinciden con el catálogo.
"""
from . import ataque_ia, herramientas, permisos, sesion

EQUIPOS = ("rojo", "azul", "general", "espectador")
L, E = "lectura", "escritura"

# id -> (título, icono, grupo, descripción, {equipo: permiso}). Un equipo que no aparece no ve la aplicación.
APPS = {
    "atacante": ("IA Atacante", "🗡️", "ia", "Modelo y Ollama del atacante; ataques de práctica.",
                 {"rojo": E, "azul": L, "general": E, "espectador": L}),
    "control": ("Centro de control", "🎛️", "ia", "Pipeline de defensa de la práctica (simulación, manual, mejor de N).",
                {"rojo": L, "azul": L, "general": E, "espectador": L}),
    "defensor": ("IA Defensora", "🛡️", "ia", "Modelo y Ollama del defensor; su decisión en cada ronda.",
                 {"rojo": L, "azul": E, "general": E, "espectador": L}),
    "batalla": ("Batalla de la partida", "⚔️", "ia", "Ataques IA dentro de la partida: Rojo los lanza, Azul defiende.",
                {"rojo": E, "azul": E, "general": L, "espectador": L}),
    "correo": ("Correo", "📬", "comunicacion", "Rojo envía correos de entrenamiento; Azul los gestiona en su buzón.",
               {"rojo": E, "azul": E}),
    "archivos": ("Archivos", "🗂️", "comunicacion", "Adjuntos PDF de la partida, su riesgo y su estado; visor seguro.",
                 {"rojo": L, "azul": E, "general": L}),
    "misiones": ("Misiones", "🎯", "seguridad", "Misiones del Equipo Azul: responsable, plazo y evidencia.",
                 {"azul": E}),
    "incidentes": ("Incidentes", "🚨", "seguridad", "Incidentes abiertos, en investigación y resueltos.",
                   {"azul": E, "general": L}),
    "seguridad": ("Seguridad", "🔐", "seguridad", "Estado de la defensa: credencial, defensor IA, controles y qué falta.",
                  {"azul": E, "general": L}),
    "recursos": ("Recursos", "🏢", "registro", "Datos de la empresa ficticia, su sensibilidad y qué rol puede leerlos.",
                 {"rojo": L, "azul": L, "general": L, "espectador": L}),
    "auditoria": ("Auditoría", "📜", "registro", "Registro en vivo de todo lo que pasa.",
                  {"rojo": L, "azul": L, "general": L, "espectador": L}),
    "resultados": ("Resultados", "📊", "registro", "Desglose de puntos con fórmulas y cronología filtrable.",
                   {"rojo": L, "azul": L, "general": L, "espectador": L}),
    "ayuda": ("Ayuda", "❓", "registro", "Cómo se juega, tus aplicaciones y las reglas con sus puntos.",
              {"rojo": L, "azul": L, "general": L, "espectador": L}),
    "finalizar": ("Finalizar partida", "🏁", "registro", "Congela los puntajes y declara el ganador.", {"general": E}),
}
GRUPOS = (("ia", "Herramientas de IA"), ("comunicacion", "Comunicación"), ("seguridad", "Seguridad"),
          ("registro", "Registro y seguimiento"))


def permiso(app_id, equipo):
    """-> "escritura" · "lectura" · None (sin acceso). Sin sesión cuenta como espectador."""
    app = APPS.get(app_id)
    return app[4].get(equipo or "espectador") if app else None


def catalogo(equipo):
    """Aplicaciones de ese equipo, en orden de grupo. -> [{id, titulo, icono, grupo, descripcion, permiso}]"""
    eq = equipo or "espectador"
    orden = [g for g, _ in GRUPOS]
    return [{"id": i, "titulo": t, "icono": ic, "grupo": g, "descripcion": d, "permiso": p[eq]}
            for i, (t, ic, g, d, p) in sorted(APPS.items(), key=lambda kv: orden.index(kv[1][2])) if eq in p]


def recomendaciones(s):
    """Qué le falta a la defensa, de lo más grave a lo menos, con la acción que lo arregla. Determinista.
    s = {credencial, enlaces_sin_contener, pdfs_sin_reportar, defensor_ok, defensor_modelo, incidentes_abiertos,
    correos_sin_revisar, riesgo, fase}. -> [{nivel, texto, accion}]"""
    r = []
    if s["credencial"] == "comprometida":
        r.append({"nivel": "CRITICO", "texto": "Hay una credencial comprometida sin revocar: Rojo puede usarla en la "
                  "batalla y suma 15 puntos mientras siga activa.", "accion": "Revócala (Incidentes o aquí mismo)."})
    if s["enlaces_sin_contener"]:
        r.append({"nivel": "ALTO", "texto": f"{s['enlaces_sin_contener']} enlace(s) clicado(s) sin contener: Rojo "
                  "suma 10 puntos por cada uno.", "accion": "Abre el correo y pulsa «Contener»."})
    if not s["defensor_modelo"]:
        r.append({"nivel": "ALTO", "texto": "El defensor IA no está configurado: cada ataque IA se deniega por fallo "
                  "seguro y Azul no puntúa.", "accion": "En «IA Defensora», elige un modelo y pulsa «Usar mi modelo "
                  "como defensor» (Batalla de la partida)."})
    elif s["defensor_ok"] is False:
        r.append({"nivel": "ALTO", "texto": "La última comprobación del defensor IA falló: los ataques se están "
                  "denegando por fallo seguro.", "accion": "Revisa su Ollama y vuelve a fijar el defensor."})
    if s["pdfs_sin_reportar"]:
        r.append({"nivel": "MEDIO", "texto": f"{s['pdfs_sin_reportar']} PDF abierto(s) sin reportar ni aislar: Rojo "
                  "suma 5 puntos por cada uno.", "accion": "En «Archivos» o en el correo: «Reportar PDF» o «Aislar»."})
    if s["incidentes_abiertos"]:
        r.append({"nivel": "MEDIO", "texto": f"{s['incidentes_abiertos']} incidente(s) sin resolver.",
                  "accion": "Investígalo y resuélvelo con una explicación cuando la amenaza esté contenida."})
    if s["correos_sin_revisar"]:
        r.append({"nivel": "BAJO", "texto": f"{s['correos_sin_revisar']} correo(s) sin leer en la bandeja.",
                  "accion": "Revísalos: verifica el remitente antes de pulsar nada."})
    if not r and s["fase"] == "en_curso":
        r.append({"nivel": "BAJO", "texto": "Nada pendiente ahora mismo.", "accion": "Vigila el buzón y la batalla."})
    return r


def recursos():
    """Datos de la empresa ficticia: qué tabla, su sensibilidad, con qué herramienta se pide y qué rol la puede leer
    (calculado con permisos.evaluar_acceso, la misma regla que aplican las capas)."""
    roles = [r for r in permisos.ROLES if r != "espectador"]
    filas = []
    for h in herramientas.CATALOGO.values():
        acceso = {}
        for rol in roles:
            ident = permisos.Identidad("x", rol)
            if permisos.evaluar_acceso(ident, h.sensibilidad).permitido:
                acceso[rol] = "sí"
            elif permisos.evaluar_acceso(ident, h.sensibilidad, True).permitido:
                acceso[rol] = "con autorización"
            else:
                acceso[rol] = "no"
        filas.append({"tabla": h.tabla, "herramienta": h.nombre, "descripcion": h.descripcion,
                      "sensibilidad": h.sensibilidad, "acceso": acceso})
    return {"roles": roles, "recursos": filas,
            "nota": "Deny-by-default: la IA solo propone; las capas deciden con el rol real de la sesión. CRITICA es "
                    "exclusiva de admin y nunca se delega; CONFIDENCIAL exige una autorización concedida por una persona."}


AYUDA_EQUIPO = {
    "rojo": ["Envía correos de entrenamiento (Correo) y sigue tu campaña: clics, adjuntos abiertos, credenciales.",
             "Lanza ataques IA cuando quieras (Batalla de la partida). Si robaste una credencial, atacas con ella.",
             "Tus puntos se pierden si Azul contiene, reporta o revoca a tiempo; los datos filtrados son permanentes."],
    "azul": ["Revisa el buzón: verifica remitentes, inspecciona enlaces, reporta, contiene y aísla adjuntos.",
             "Fija tu defensor IA en la Batalla de la partida: responde solo a cada ataque de Rojo.",
             "Si una credencial cae, abre un incidente, revócala y resuélvelo. Seguridad te dice qué falta."],
    "general": ["Eres el árbitro: inicias la partida (5, 10 o 15 min), la sigues en el marcador y la finalizas.",
                "Resultados y la cronología explican cada punto; Incidentes y Seguridad muestran la defensa."],
    "espectador": ["Solo observas: ves el marcador, la batalla, la auditoría, los resultados y la cronología."],
}


def ayuda(equipo):
    eq = equipo or "espectador"
    return {"equipo": eq, "pasos": AYUDA_EQUIPO[eq], "apps": catalogo(eq),
            "reglas": [{"evento": k, "riesgo": v["riesgo"], "completa_mision": v["mision"],
                        "explicacion": v.get("explicacion")} for k, v in sesion.REGLAS_EVENTO.items()],
            "puntos_rojo": {"enlace_sin_contener": sesion.PUNTOS_ROJO["enlace_sin_contener"],
                            "pdf_abierto_sin_reportar": sesion.PUNTOS_ROJO["pdf_abierto_sin_reportar"],
                            "credencial_sin_revocar": sesion.PUNTOS_ROJO["credencial_sin_revocar"],
                            "datos_expuestos": dict(ataque_ia.PUNTOS_DATOS), "ia_enganada": ataque_ia.PUNTOS_IA_ENGANADA},
            "puntos_azul": {"ataque_contenido": ataque_ia.PUNTOS_CONTENIDO,
                            "misiones": "los puntos de cada misión (la mitad fuera de plazo)"},
            "max_ataques_ia": ataque_ia.MAX_ATAQUES}
