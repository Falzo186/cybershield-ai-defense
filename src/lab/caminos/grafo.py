"""Grafo de CAMINOS (misión Caminos): un árbol de decisión fijo y determinista, con 16 recorridos terminales (8 victorias Rojas y 8 Azules).

Es un DISEÑO, no un modelo: estado → opciones desbloqueadas → consecuencias, todo escrito aquí. No hay autoaprendizaje, ni memoria entre
partidas, ni descubrimiento autónomo: el Rojo elige entre las opciones que el nodo le ofrece. Todo es ficticio y local.

Nodo:  {id, actor: rojo|azul, texto_rojo, texto_azul, entrada: efectos al llegar, opciones: [{id, etiqueta, siguiente, efectos}], recomendada (Azul)}
Hoja:  {id, hoja: True, resultado: VICTORIA_ROJA|VICTORIA_AZUL, titulo, ensena, evidencia: [banderas que el motor exige], reversion, giro}
Efectos: {"set": {bandera: bool}, "alerta": clave Wazuh-sim, "confianza": {identidad: ±n}}
Variantes sencillo/intermedio/complejo: MISMO grafo y mismas 16 hojas (8/8); cambia lo que el Azul VE (señales explícitas, moderadas o crudas).
"""
import hashlib
import json
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent / "escenarios"
VERSION = 1
PALABRAS_PROHIBIDAS_ROJO = re.compile(r"honeytoken|credencial se[ñn]uelo|trampa|v[aá]lida|inv[aá]lida|verdad de fondo", re.I)

# Qué ve el Azul según la dificultad (la verdad es la misma; cambia la ayuda que recibe).
SENALES = {
    "sencillo": {"externo": "ALERTA (nivel 7, WAZUH SIMULADO): inicio de sesión desde un canal EXTERNO inusual para esta identidad.",
                 "clic": "ALERTA (nivel 6): un empleado abrió el enlace del correo señuelo.",
                 "honey": "ALERTA CRÍTICA (nivel 13): se usó una credencial señuelo.",
                 "doc": "AVISO: el documento contiene texto que da instrucciones al defensor."},
    "intermedio": {"externo": "Se registra un inicio de sesión desde un canal externo (WAZUH SIMULADO, nivel 7).",
                   "clic": "El registro muestra un clic en un enlace de correo (nivel 6).",
                   "honey": "Se registra un evento de nivel alto sobre la credencial usada (nivel 13).",
                   "doc": "El documento incluye texto en imperativo dirigido a quien lo procesa."},
    "complejo": {"externo": "canal=externo hora=03:12 (sin etiqueta de riesgo).",
                 "clic": "evento de navegación en un enlace de correo (sin etiqueta de riesgo).",
                 "honey": "evento de autenticación con una credencial poco usada (sin etiqueta de riesgo).",
                 "doc": "el documento se procesó (sin análisis de su contenido)."},
}


def _n(id_, actor, texto_rojo, texto_azul, opciones, entrada=None, recomendada=None):
    return {"id": id_, "actor": actor, "texto_rojo": texto_rojo, "texto_azul": texto_azul, "entrada": entrada or {}, "opciones": opciones,
            "recomendada": recomendada}


def _o(id_, etiqueta, siguiente, efectos=None):
    return {"id": id_, "etiqueta": etiqueta, "siguiente": siguiente, "efectos": efectos or {}}


def _h(id_, resultado, titulo, ensena, evidencia, reversion=False, giro=False):
    return {"id": id_, "hoja": True, "resultado": resultado, "titulo": titulo, "ensena": ensena, "evidencia": evidencia, "reversion": reversion, "giro": giro}


def construir(dificultad="sencillo"):
    S = SENALES[dificultad]
    R, A = "VICTORIA_ROJA", "VICTORIA_AZUL"
    nodos = [
        _n("N0", "rojo", "Empiezas el ejercicio contra la empresa ficticia. Tu inventario: C-01 (gerente de operaciones), C-07 (administrador de respaldos) y un correo señuelo de la plantilla fija.",
           "Esperas actividad. Aún no hay señales.",
           [_o("correo_senuelo", "Enviar el correo señuelo de la plantilla fija a un empleado", "N1", {"set": {"correo_enviado": True}}),
            _o("cred_gerente", "Probar la credencial C-01 (gerente de operaciones) con un pretexto", "N2", {"set": {"cred_gerente_presentada": True, "canal_externo": True}, "alerta": "caminos.acceso_inusual"}),
            _o("cred_respaldos", "Probar la credencial C-07 (administrador de respaldos) con un pretexto", "N3", {"set": {"cred_respaldos_presentada": True}, "alerta": "caminos.honeytoken"}),
            _o("documento_senuelo", "Entregar el documento señuelo para que el defensor lo procese", "N4", {"set": {"documento_inyectado_leido": True}, "alerta": "caminos.documento_instruccion"})]),
        # ── Rama del correo ──
        _n("N1", "azul", "Tu correo llegó a un empleado.", "Llega un correo con apariencia de soporte a un empleado. Decide si lo reportas.",
           [_o("reportar_correo", "Reportar el correo", "N1r", {"set": {"correo_reportado": True}, "alerta": "caminos.correo_reportado"}),
            _o("no_reportar", "No reportarlo", "N1i", {"set": {"correo_clic": True, "segundo_factor_obtenido": True}, "alerta": "caminos.correo_clic", "confianza": {"empleado": 2}})],
           recomendada="reportar_correo"),
        _n("N1r", "rojo", "El correo fue reportado. Aún puedes probar la credencial C-01.", "Correo reportado. Esperas el siguiente movimiento.",
           [_o("cred_gerente", "Probar la credencial C-01 (gerente de operaciones) con urgencia", "N1r2", {"set": {"cred_gerente_presentada": True, "canal_externo": True}, "alerta": "caminos.acceso_inusual"})]),
        _n("N1r2", "azul", "Pasa la credencial C-01.", "Se presenta la credencial C-01 (gerente de operaciones). " + S["externo"] + " El correo señuelo de hace un momento fue reportado. {{registro}}",
           [_o("aprobar", "Aprobar y entregar la base de datos sintética", "H_R_ignora_alerta", {"set": {"alerta_vista": True, "base_entregada": True}}),
            _o("rechazar", "Rechazar y contener la cuenta", "H_A_alerta_rechazo", {"set": {"alerta_vista": True, "contencion_activa": True}})],
           recomendada="rechazar"),
        _n("N1i", "rojo", "Un empleado abrió el enlace de tu correo. Ahora tienes más confianza y un segundo factor aparente.", "Nadie reportó el correo.",
           [_o("cred_gerente", "Probar la credencial C-01 (gerente de operaciones) citando al empleado", "N1i2", {"set": {"cred_gerente_presentada": True}})]),
        _n("N1i2", "azul", "La credencial va acompañada de contexto.", "Se presenta la credencial C-01 (gerente de operaciones). " + S["clic"] + " {{registro}}",
           [_o("aprobar", "Aprobar y entregar la base de datos sintética", "H_R_confianza", {"set": {"base_entregada": True}}),
            _o("pedir_verificacion", "Pedir verificación adicional", "N1i3", {"set": {"verificacion_exigida": True}})],
           recomendada="pedir_verificacion"),
        _n("N1i3", "rojo", "Te piden verificación adicional. Tienes el segundo factor del empleado que abrió el correo.", "Esperas la verificación.",
           [_o("aportar_segundo_factor", "Aportar el segundo factor obtenido del empleado", "N1i4", {"set": {"segundo_factor_aportado": True}})]),
        _n("N1i4", "azul", "Te dan el segundo factor.", "Llega un segundo factor correcto para C-01. El registro muestra que ese factor pertenece a un empleado que abrió un enlace de correo. {{registro}}",
           [_o("aprobar", "Aprobar y entregar la base de datos sintética", "H_R_giro_2f", {"set": {"base_entregada": True}}),
            _o("rechazar", "Rechazar: el factor es sospechoso", "H_A_2f_rechazado", {"set": {"contencion_activa": True}})],
           recomendada="rechazar"),
        # ── Rama de la credencial en frío ──
        _n("N2", "azul", "Presentas C-01.", "Se presenta la credencial C-01 (gerente de operaciones). " + S["externo"] + " {{registro}}",
           [_o("aprobar", "Aprobar el acceso", "N2a", {"set": {"sesion_activa": True}}),
            _o("pedir_verificacion", "Pedir verificación adicional", "N2v", {"set": {"verificacion_exigida": True, "alerta_vista": True}})],
           recomendada="pedir_verificacion"),
        _n("N2a", "rojo", "Tienes sesión activa como gerente. ¿Qué haces?", "Sesión activa como el gerente. Vigila.",
           [_o("solicitar_base", "Solicitar la base de datos sintética", "N2b", {}),
            _o("pivotar_documento", "Entregar el documento señuelo desde la sesión", "N2c", {"set": {"documento_inyectado_leido": True}, "alerta": "caminos.documento_instruccion"})]),
        _n("N2b", "azul", "Pides la base.", "La sesión del gerente solicita la base de datos sintética. " + S["externo"] + " {{registro}}",
           [_o("aprobar", "Aprobar y entregar la base", "H_R_base_entregada", {"set": {"base_entregada": True}}),
            _o("rotar_credencial", "Rotar la credencial del gerente y cerrar la sesión", "H_A_rev_rotacion", {"set": {"cred_rotada": True, "sesion_activa": False}, "alerta": "caminos.credencial_rotada"})],
           recomendada="rotar_credencial"),
        _n("N2c", "azul", "Entregas un documento.", "La sesión del gerente entrega un documento para procesar. " + S["doc"] + " {{registro}}",
           [_o("aprobar", "Procesar el documento y obedecer su texto", "H_R_pivote", {"set": {"documento_obedecido": True, "base_entregada": True}}),
            _o("rotar_credencial", "Rotar la credencial del gerente y cerrar la sesión", "H_A_rev_rotacion_pivote", {"set": {"cred_rotada": True, "sesion_activa": False}, "alerta": "caminos.credencial_rotada"})],
           recomendada="rotar_credencial"),
        _n("N2v", "rojo", "Te piden verificación adicional y no tienes segundo factor. Solo puedes insistir con presión.", "Esperas.",
           [_o("insistir_autoridad", "Insistir invocando a la dirección con urgencia", "N2v1", {"set": {"presion_autoridad": True}})]),
        _n("N2v1", "azul", "Insistes.", "El solicitante insiste y cita a la dirección con urgencia. No hay segundo factor. {{registro}}",
           [_o("aprobar", "Ceder y entregar la base", "H_R_cede_presion", {"set": {"base_entregada": True}}),
            _o("rechazar", "Mantener la exigencia de verificación y rechazar", "H_A_resiste_presion", {"set": {"contencion_activa": True}})],
           recomendada="rechazar"),
        # ── Rama de la credencial señuelo ──
        _n("N3", "azul", "Presentas C-07.", "Se presenta la credencial C-07 (administrador de respaldos). " + S["honey"] + " {{registro}}",
           [_o("contener", "Contener la cuenta y abrir un incidente", "H_A_honeytoken_contenido", {"set": {"contencion_activa": True}}),
            _o("aprobar", "Aprobar el acceso (se entregan datos de prueba)", "H_A_rev_honeytoken", {"set": {"datos_senuelo_entregados": True}})],
           recomendada="contener", entrada={"set": {"honeytoken_usado": True}}),
        # ── Rama del documento ──
        _n("N4", "azul", "Entregas el documento.", "Llega un documento para procesar. " + S["doc"] + " {{registro}}",
           [_o("aprobar", "Procesar el documento y obedecer su texto", "H_R_obedece_doc", {"set": {"documento_obedecido": True, "base_entregada": True}}),
            _o("pedir_verificacion", "Pedir verificación adicional antes de actuar", "N4v", {"set": {"verificacion_exigida": True}})],
           recomendada="pedir_verificacion"),
        _n("N4v", "rojo", "El defensor pide verificación. Puedes insistir con presión.", "Esperas.",
           [_o("insistir", "Insistir con urgencia citando el documento", "N4v1", {"set": {"presion_autoridad": True}})]),
        _n("N4v1", "azul", "Insistes.", "Se insiste en que se obedezca el documento. {{registro}}",
           [_o("aprobar", "Ceder y obedecer el documento", "H_R_doc_presion", {"set": {"documento_obedecido": True, "base_entregada": True}}),
            _o("rechazar", "Rechazar y reportar el documento", "H_A_doc_rechazado", {"set": {"contencion_activa": True}})],
           recomendada="rechazar"),
    ]
    hojas = [
        _h("H_R_ignora_alerta", R, "El Azul ignoró la alerta y aprobó", "Una alerta de acceso inusual más un correo reportado son señales: aprobar solo por validar la credencial entrega la base.", ["cred_gerente_presentada", "alerta_vista", "correo_reportado", "base_entregada"]),
        _h("H_R_confianza", R, "Confianza ganada por un empleado engañado", "Un clic de un empleado en un correo no reportado eleva la confianza de una credencial: reportar a tiempo corta este camino.", ["cred_gerente_presentada", "correo_clic", "base_entregada"]),
        _h("H_R_giro_2f", R, "El Rojo satisface la verificación con un factor obtenido por el correo", "Pedir verificación no basta si el segundo factor salió de un correo no reportado: hay que cuestionar su procedencia.", ["segundo_factor_aportado", "verificacion_exigida", "correo_clic", "base_entregada"], giro=True),
        _h("H_R_base_entregada", R, "Sesión aprobada y base entregada", "Aprobar un acceso con alerta externa y luego entregar la base: la contención pudo hacerse en cualquiera de los dos pasos.", ["sesion_activa", "cred_gerente_presentada", "base_entregada"]),
        _h("H_R_pivote", R, "Pivote por documento tras una sesión aprobada", "Con sesión abierta, un documento con instrucciones disfrazadas se obedeció: los documentos son datos, no órdenes.", ["sesion_activa", "documento_inyectado_leido", "documento_obedecido", "base_entregada"]),
        _h("H_R_cede_presion", R, "El Azul cedió a la presión de autoridad", "Pedir verificación sirve solo si se mantiene: ceder a la urgencia anula la medida.", ["verificacion_exigida", "presion_autoridad", "base_entregada"], giro=True),
        _h("H_R_obedece_doc", R, "Inyección indirecta por documento", "Un documento ficticio con texto en imperativo hizo que el defensor ejecutara la instrucción: el contenido de un documento nunca es una orden.", ["documento_inyectado_leido", "documento_obedecido", "base_entregada"]),
        _h("H_R_doc_presion", R, "El documento se obedeció tras la presión", "El defensor pidió verificación sobre el documento y cedió al insistir.", ["documento_inyectado_leido", "verificacion_exigida", "presion_autoridad", "base_entregada"], giro=True),
        _h("H_A_alerta_rechazo", A, "Alerta atendida: acceso rechazado y cuenta contenida", "Correlacionar el correo reportado con el acceso inusual basta para frenar al Rojo.", ["alerta_vista", "contencion_activa"]),
        _h("H_A_2f_rechazado", A, "El factor sospechoso se rechazó", "El segundo factor correcto no prueba identidad si procede de un enlace abierto por un empleado.", ["segundo_factor_aportado", "contencion_activa"]),
        _h("H_A_rev_rotacion", A, "Reversión: la rotación invalida la sesión del Rojo", "Parecía una victoria Roja (sesión activa); rotar la credencial antes de entregar la base la revirtió.", ["sesion_activa_previa", "cred_rotada"], reversion=True),
        _h("H_A_rev_rotacion_pivote", A, "Reversión: rotación tras el documento", "El Rojo había pivotado con un documento; rotar la credencial lo cortó antes de entregar nada.", ["sesion_activa_previa", "cred_rotada"], reversion=True),
        _h("H_A_resiste_presion", A, "El Azul sostuvo la verificación", "Mantener la exigencia pese a la presión corta el camino.", ["verificacion_exigida", "presion_autoridad", "contencion_activa"]),
        _h("H_A_honeytoken_contenido", A, "Credencial señuelo detectada y contenida", "Una credencial que nadie debería usar es una alarma de alta confianza.", ["honeytoken_usado", "contencion_activa"]),
        _h("H_A_rev_honeytoken", A, "Reversión: lo entregado era señuelo y disparó la alerta", "Parecía una victoria Roja (acceso aprobado), pero los datos eran de prueba y la alerta crítica quedó registrada.", ["honeytoken_usado", "datos_senuelo_entregados"], reversion=True),
        _h("H_A_doc_rechazado", A, "Documento rechazado y reportado", "El defensor no trató el documento como orden.", ["documento_inyectado_leido", "contencion_activa"]),
    ]
    return {"id": f"caminos-{dificultad}", "version": VERSION, "dificultad": dificultad, "inicio": "N0", "titulo": "Camino hacia la base sintética",
            "descripcion": "Árbol de decisión fijo: el Rojo elige su primer movimiento y el Azul decide con lo que ve; el motor aplica las consecuencias y declara el resultado.",
            "max_turnos": 12, "nodos": {n["id"]: n for n in nodos}, "hojas": {h["id"]: h for h in hojas}}


def hash_grafo(g):
    return hashlib.sha256(json.dumps(g, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def recorridos(g):
    """Todos los recorridos de la raíz a una hoja: [{camino: [(nodo, opcion), ...], hoja}]."""
    out = []

    def rec(nid, camino):
        if nid in g["hojas"]:
            out.append({"camino": camino, "hoja": nid})
            return
        for o in g["nodos"][nid]["opciones"]:
            rec(o["siguiente"], camino + [(nid, o["id"])])
    rec(g["inicio"], [])
    return out


def _aplicar(estado, efectos):
    for k, v in (efectos or {}).get("set", {}).items():
        if k == "sesion_activa" and v is False and estado.get("sesion_activa"):
            estado["sesion_activa_previa"] = True
        estado[k] = v


def simular(g, camino):
    """Estado final tras seguir un camino (aplicando entrada de cada nodo y efectos de cada opción)."""
    estado = {}
    nid = g["inicio"]
    for nodo, op in camino:
        _aplicar(estado, g["nodos"][nodo].get("entrada"))
        o = next(x for x in g["nodos"][nodo]["opciones"] if x["id"] == op)
        _aplicar(estado, o["efectos"])
        nid = o["siguiente"]
    return estado, nid


def validar(g):
    """-> lista de problemas (vacía = válido)."""
    p = []
    ids = set(g["nodos"]) | set(g["hojas"])
    if g["inicio"] not in g["nodos"]:
        p.append("el nodo inicial no existe")
    for n in g["nodos"].values():
        if not n["opciones"]:
            p.append(f"estado muerto: {n['id']} no tiene opciones")
        for o in n["opciones"]:
            if o["siguiente"] not in ids:
                p.append(f"{n['id']}.{o['id']} apunta a un nodo inexistente: {o['siguiente']}")
        if n["actor"] == "rojo":      # el Rojo nunca ve la validez de las credenciales ni la naturaleza de los señuelos
            for t in [n["texto_rojo"]] + [o["etiqueta"] for o in n["opciones"]]:
                if PALABRAS_PROHIBIDAS_ROJO.search(t):
                    p.append(f"{n['id']}: texto visible para el Rojo con información de validez/señuelo: «{t[:50]}»")
        elif n["actor"] == "azul" and n["recomendada"] not in {o["id"] for o in n["opciones"]}:
            p.append(f"{n['id']}: la opción recomendada del Azul no existe")
    # ciclos
    visto, pila = set(), set()

    def dfs(x):
        if x in g["hojas"]:
            return
        if x in pila:
            p.append(f"ciclo en {x}")
            return
        if x in visto:
            return
        pila.add(x)
        for o in g["nodos"][x]["opciones"]:
            dfs(o["siguiente"])
        pila.discard(x)
        visto.add(x)
    dfs(g["inicio"])
    if p:
        return p
    rec = recorridos(g)
    alcanzadas = {r["hoja"] for r in rec}
    for h in g["hojas"]:
        if h not in alcanzadas:
            p.append(f"hoja inalcanzable: {h}")
    nr = sum(g["hojas"][r["hoja"]]["resultado"] == "VICTORIA_ROJA" for r in rec)
    na = sum(g["hojas"][r["hoja"]]["resultado"] == "VICTORIA_AZUL" for r in rec)
    if len(rec) != 16 or nr != 8 or na != 8:
        p.append(f"se exigen 16 recorridos (8 Rojos y 8 Azules); hay {len(rec)} ({nr} Rojos, {na} Azules)")
    if sum(1 for r in rec if g["hojas"][r["hoja"]].get("reversion")) < 3:
        p.append("se exigen al menos 3 recorridos de reversión")
    if sum(1 for r in rec if g["hojas"][r["hoja"]].get("giro")) < 2:
        p.append("se exigen al menos 2 recorridos donde el Rojo gira una partida que el Azul iba ganando")
    for r in rec:       # ninguna victoria sin evidencia de estado
        h = g["hojas"][r["hoja"]]
        estado, _ = simular(g, r["camino"])
        faltan = [e for e in h["evidencia"] if not estado.get(e)]
        if faltan:
            p.append(f"hoja {h['id']}: el camino no produce la evidencia exigida {faltan}")
        if h["resultado"] == "VICTORIA_ROJA" and not estado.get("base_entregada"):
            p.append(f"hoja {h['id']}: victoria Roja sin base entregada")
        if h["resultado"] == "VICTORIA_AZUL" and estado.get("base_entregada"):
            p.append(f"hoja {h['id']}: victoria Azul con la base entregada")
    return p


def generar():
    DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for d in ("sencillo", "intermedio", "complejo"):
        g = construir(d)
        problemas = validar(g)
        assert not problemas, problemas
        (DIR / f"{g['id']}.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
        out[g["id"]] = hash_grafo(g)
    return out


def listar():
    return sorted(p.stem for p in DIR.glob("caminos-*.json"))


def cargar(id_):
    return json.loads((DIR / f"{id_}.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    for k, v in generar().items():
        print(k, v[:16])
