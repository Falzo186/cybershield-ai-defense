"""Escenario «Distribuidora Nova» (paquete del profesor, decisiones D2–D7): 6 identidades FIJAS, recursos, base ficticia NovaStore_Lab (8 tablas)
y reglas de victoria. Todo es ficticio y local: dominio `.test`, enlaces `lab://`, sin datos reales.

Las identidades y las credenciales son ESTABLES: se generan una sola vez con una semilla fija y reiniciar el escenario no las duplica ni las cambia.
Excepción deliberada (D4): EMP-04 tiene el valor predecible `12345A` (`weak=true`), lo que da a la adivinación una probabilidad real de acierto.
"""
import random
import re

EMPRESA = "Distribuidora Nova"
DOMINIO = "nova-lab.test"
PATRON_CREDENCIAL = r"^[0-9]{5}[A-Z]$"
SEMILLA_CREDENCIALES = 20261121
SEMILLA_DATOS = 4242

# D3 · catálogo fijo de 6 identidades
IDENTIDADES = [
    {"id": "EMP-01", "nombre": "Laura Méndez", "depto": "Ventas", "puesto": "Ejecutiva de ventas", "permiso": "consultar_ventas", "recurso": "R-VENTAS", "weak": False},
    {"id": "EMP-02", "nombre": "Carlos Rivas", "depto": "Compras", "puesto": "Comprador", "permiso": "consultar_compras", "recurso": "R-COMPRAS", "weak": False},
    {"id": "EMP-03", "nombre": "Sofía Torres", "depto": "Administración", "puesto": "Coordinadora administrativa", "permiso": "consultar_reportes", "recurso": "R-REPORTES", "weak": False},
    {"id": "EMP-04", "nombre": "Diego Herrera", "depto": "Almacén", "puesto": "Encargado de almacén", "permiso": "consultar_inventario", "recurso": "R-INVENTARIO", "weak": True},
    {"id": "EMP-05", "nombre": "Andrea Salas", "depto": "Finanzas", "puesto": "Analista financiera", "permiso": "consultar_movimientos", "recurso": "R-FINANZAS", "weak": False},
    {"id": "EMP-06", "nombre": "Miguel Ortega", "depto": "Dirección", "puesto": "Director general", "permiso": "consultar_indicadores", "recurso": "R-INDICADORES", "weak": False},
]
ORDEN_AZUL = ["EMP-01", "EMP-02", "EMP-03", "EMP-04"]      # asignación por defecto (máx. 4 jugadores Azul)
MAX_AZUL, MAX_ROJO = 4, 4

TABLAS = ["empleados", "productos", "clientes", "ventas", "detalle_venta", "compras", "inventario", "reportes_financieros"]
PROTEGIDAS = ["reportes_financieros", "empleados"]
# recurso -> (tablas que permite leer completas, ¿protegido?)
RECURSOS = {
    "R-VENTAS": {"nombre": "Ventas y clientes", "tablas": ["ventas", "detalle_venta", "clientes"], "protegido": False},
    "R-COMPRAS": {"nombre": "Compras", "tablas": ["compras"], "protegido": False},
    "R-REPORTES": {"nombre": "Reportes operativos y empleados (directorio)", "tablas": ["empleados"], "protegido": True},
    "R-INVENTARIO": {"nombre": "Productos e inventario", "tablas": ["productos", "inventario"], "protegido": False},
    "R-FINANZAS": {"nombre": "Reportes financieros", "tablas": ["reportes_financieros"], "protegido": True},
    "R-INDICADORES": {"nombre": "Indicadores agregados (KPIs)", "tablas": [], "protegido": False},
}
# D7 · condiciones de victoria del Rojo (configurables por el administrador antes de iniciar)
WIN_POR_DEFECTO = {"modo": "any_of", "reglas": ["W1", "W2"], "w1_tabla": "reportes_financieros", "w1_identidades": ["EMP-05"], "w3_umbral_registros": 50}

_NOMBRES = ["Ana", "Luis", "Marta", "Jorge", "Elena", "Pablo", "Rosa", "Iván", "Julia", "Hugo", "Nora", "Tomás", "Lidia", "Raúl", "Clara", "Mario"]
_APELLIDOS = ["Gómez", "Vega", "Ríos", "Soto", "Mora", "Cruz", "Peña", "Lara", "Núñez", "Paz", "Rey", "Salas"]
_PRODUCTOS = ["Arroz 1kg", "Aceite 1L", "Azúcar 2kg", "Leche 1L", "Café 500g", "Harina 1kg", "Frijol 1kg", "Atún lata", "Jabón barra", "Papel higiénico x4"]


def generar_credenciales(semilla=SEMILLA_CREDENCIALES):
    """Valores de laboratorio con el patrón `^[0-9]{5}[A-Z]$`, únicos y fijos por semilla. EMP-04 es débil por diseño (`12345A`)."""
    rng = random.Random(f"cred|{semilla}")
    usados, out = {"12345A"}, {}
    for i in IDENTIDADES:
        if i["weak"]:
            out[i["id"]] = "12345A"
            continue
        while True:
            v = f"{rng.randrange(10000, 100000)}{chr(rng.randrange(65, 91))}"
            if v not in usados and v != "12345A" and re.match(PATRON_CREDENCIAL, v):
                usados.add(v)
                out[i["id"]] = v
                break
    return out


def generar_base(credenciales, semilla=SEMILLA_DATOS):
    """NovaStore_Lab: 8 tablas con datos ficticios deterministas. `empleados.credencial_ficticia` guarda el valor de laboratorio."""
    rng = random.Random(f"base|{semilla}")
    emp = [{"id": i["id"], "nombre": i["nombre"], "depto": i["depto"], "puesto": i["puesto"], "correo": f"{i['nombre'].split()[0].lower()}@{DOMINIO}",
            "credencial_ficticia": credenciales[i["id"]]} for i in IDENTIDADES]
    prod = [{"id": n + 1, "nombre": p, "precio": round(rng.uniform(12, 95), 2)} for n, p in enumerate(_PRODUCTOS)]
    cli = [{"id": n + 1, "nombre": f"{rng.choice(_NOMBRES)} {rng.choice(_APELLIDOS)}", "correo": f"cliente{n + 1}@clientes.test", "ciudad": rng.choice(["Mérida", "Monterrey", "Puebla", "León"])} for n in range(24)]
    ven = [{"id": n + 1, "cliente_id": rng.randint(1, len(cli)), "fecha": f"2026-10-{rng.randint(1, 28):02d}", "total": round(rng.uniform(80, 2400), 2)} for n in range(30)]
    det = [{"id": n + 1, "venta_id": rng.randint(1, len(ven)), "producto_id": rng.randint(1, len(prod)), "cantidad": rng.randint(1, 12)} for n in range(60)]
    com = [{"id": n + 1, "proveedor": f"Proveedor {rng.randint(1, 9)}", "fecha": f"2026-09-{rng.randint(1, 28):02d}", "total": round(rng.uniform(500, 9000), 2)} for n in range(18)]
    inv = [{"producto_id": p["id"], "existencias": rng.randint(0, 400), "bodega": rng.choice(["A", "B", "C"])} for p in prod]
    fin = [{"id": n + 1, "periodo": f"2026-{m:02d}", "concepto": c, "monto": round(rng.uniform(5000, 90000), 2)} for n, (m, c) in enumerate((m, c) for m in range(1, 10) for c in ("ingresos", "egresos", "utilidad"))]
    return {"empleados": emp, "productos": prod, "clientes": cli, "ventas": ven, "detalle_venta": det, "compras": com, "inventario": inv, "reportes_financieros": fin}


def kpis(base):
    """Indicadores agregados (R-INDICADORES): solo números, nunca filas."""
    return {"ventas_totales": round(sum(v["total"] for v in base["ventas"]), 2), "clientes": len(base["clientes"]), "productos": len(base["productos"]),
            "compras_totales": round(sum(c["total"] for c in base["compras"]), 2)}


# Plantillas de correo del Rojo (D6): el texto lo puede escribir un humano o la IA; el servidor solo fija el enlace `lab://`.
PLANTILLAS_ROJO = {
    "aviso_soporte": {"asunto": "Soporte TI: verifica tu identidad de laboratorio", "malicioso": True},
    "reporte_urgente": {"asunto": "Reporte financiero pendiente de revisión", "malicioso": True},
    "consulta_cordial": {"asunto": "Consulta sobre el calendario de entregas", "malicioso": False},
}

# Correos PROGRAMADOS del escenario (independientes del Rojo). `at_s` = segundos de tiempo de partida.
CORREOS_PROGRAMADOS = [
    {"id": "SC-01", "at_s": 10, "de": "rrhh@" + DOMINIO, "asunto": "Recordatorio: actualización de datos de contacto", "cuerpo": "Revisa tus datos de contacto en el portal interno.", "legitimo": True},
    {"id": "SC-02", "at_s": 40, "de": "finanzas@" + DOMINIO, "asunto": "Cierre de mes: fecha límite de gastos", "cuerpo": "La fecha límite es el viernes.", "legitimo": True},
    {"id": "SC-03", "at_s": 75, "de": "direccion@" + DOMINIO, "asunto": "Reunión general del lunes", "cuerpo": "A las 10:00 en la sala principal.", "legitimo": True},
    {"id": "SC-04", "at_s": 110, "de": "soporte@" + DOMINIO, "asunto": "Mantenimiento del correo el sábado", "cuerpo": "No se pedirá ninguna contraseña por este motivo.", "legitimo": True},
    {"id": "SC-05", "at_s": 150, "de": "ventas@" + DOMINIO, "asunto": "Solicitud: consulta del reporte de ventas", "cuerpo": "Un compañero pide autorización para consultar el reporte de ventas.", "legitimo": True, "requiere_aprobacion": True},
    {"id": "SC-06", "at_s": 200, "de": "compras@" + DOMINIO, "asunto": "Solicitud: consulta de inventario", "cuerpo": "Compras pide autorización para consultar el inventario.", "legitimo": True, "requiere_aprobacion": True},
]


# Modalidades (D13): cada una MODIFICA parámetros reales del motor, se cuantifica y se congela al iniciar la partida.
MODALIDADES = {
    "BALANCED": {},
    "RED_ADVANTAGE": {"guess_attempts_per_round": 5, "guess_cooldown_s": 10, "guess_lockout_after_fails": 4, "detect_prob_fail": 0.3, "click_delay_s": 12, "scans_per_round": 3, "approval_ttl_s": 60,
                      "revela_permisos_al_identificar": True},
    "BLUE_ADVANTAGE": {"guess_attempts_per_round": 2, "guess_cooldown_s": 30, "guess_lockout_after_fails": 2, "detect_prob_fail": 0.9, "click_delay_s": 45, "scans_per_round": 1, "approval_ttl_s": 150,
                       "alertas_con_detalle": True},
}
