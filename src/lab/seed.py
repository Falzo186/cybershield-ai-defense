"""Datos semilla 100% ficticios. Los 'secretos' son valores de laboratorio, no credenciales reales."""
from datetime import datetime


# Misiones fijas del Equipo Azul:
#   (id, título, condicion_evento, puntos, prioridad, plazo_s, depende_de, descripcion)
# condicion_evento = evento de sesion.REGLAS_EVENTO que la completa, o "manual" (la marca el propio equipo azul).
# plazo_s = segundos desde el inicio de la partida (None = sin plazo); fuera de plazo vale la mitad.
# depende_de = ids (separados por comas) que deben estar completadas ANTES: si no, el evento no la completa.
MISIONES = [
    (1, "Reportar un correo sospechoso", "correo_reportado", 10, "alta", 180, "",
     "Reporta un correo de phishing para que seguridad pueda avisar al resto."),
    (2, "Contener un enlace clicado", "enlace_contenido", 15, "alta", 240, "",  # DESPUÉS de un CLIC_ENLACE
     "Si alguien abrió un enlace malicioso, contenlo para que los siguientes clics no tengan efecto."),
    (3, "Revisar el buzón diariamente", "manual", 5, "baja", None, "",
     "Márcala tú cuando hayas revisado todo el buzón."),
    (4, "Revisar un documento recibido", "pdf_abierto", 10, "media", None, "",
     "Previsualiza un adjunto en el visor seguro y valora sus indicadores."),
    (5, "Verificar el remitente de un correo", "remitente_verificado", 5, "media", 120, "",
     "Comprueba el dominio de un remitente antes de actuar sobre su correo."),
    (6, "Abrir un incidente de seguridad", "incidente_abierto", 10, "alta", None, "",
     "Registra el incidente: qué pasó, gravedad y correo relacionado."),
    (7, "Revocar una credencial comprometida", "credencial_revocada", 20, "alta", None, "6",
     "Si una cuenta envió su contraseña a una página falsa, revócala. Requiere un incidente abierto antes."),
    (8, "Resolver el incidente", "incidente_resuelto", 15, "media", None, "6",
     "Cierra el incidente con su resolución cuando la amenaza esté contenida."),
]


def sembrar_misiones(conn):
    """Aparte del resto: también llega a BD creadas antes de existir las misiones. MISIONES es la fuente de
    verdad: si una misión ya existe, se actualiza su definición (el progreso de los usuarios no se toca)."""
    conn.executemany("INSERT INTO misiones(id,titulo,condicion_evento,puntos,prioridad,plazo_s,depende_de,descripcion) "
                     "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                     "titulo=excluded.titulo, condicion_evento=excluded.condicion_evento, puntos=excluded.puntos, "
                     "prioridad=excluded.prioridad, plazo_s=excluded.plazo_s, depende_de=excluded.depende_de, "
                     "descripcion=excluded.descripcion", MISIONES)
    conn.commit()


def sembrar(conn):
    sembrar_misiones(conn)
    if conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]:
        return  # ya sembrada
    conn.executemany("INSERT INTO usuarios VALUES(?,?)", [
        ("visita.demo", "invitado"), ("ana.perez", "empleado"), ("luis.gomez", "empleado"),
        ("marta.ruiz", "analista"), ("root.lab", "admin"),
    ])
    conn.executemany("INSERT INTO productos VALUES(?,?,?,?)", [
        ("CS-FW-200", "Firewall Edge X200", 42, 1890.0),
        ("CS-VPN-110", "Gateway VPN V110", 17, 740.0),
        ("CS-EDR-300", "Licencia EDR Sentinel", 250, 59.0),
        ("CS-SIEM-500", "Suite SIEM Horizon", 9, 5400.0),
    ])
    conn.executemany("INSERT INTO clientes VALUES(?,?,?,?)", [
        (1, "Banco Aurora (ficticio)", "Finanzas", "contacto1@ejemplo.invalid"),
        (2, "Clínica Norte (ficticia)", "Salud", "contacto2@ejemplo.invalid"),
        (3, "Logística Delta (ficticia)", "Transporte", "contacto3@ejemplo.invalid"),
        (4, "Mercado Sol (ficticio)", "Comercio", "contacto4@ejemplo.invalid"),
    ])
    conn.executemany("INSERT INTO incidentes VALUES(?,?,?,?,?)", [
        (1, "2026-07-03", "vpn-gw-02", "ALTA", "Credencial de servicio expuesta en un repositorio de pruebas"),
        (2, "2026-08-11", "crm-web", "MEDIA", "Inyección SQL en un formulario heredado"),
        (3, "2026-09-02", "ad-sync", "CRITICA", "Cuenta privilegiada sin MFA comprometida"),
        (4, "2026-09-20", "wifi-corp", "BAJA", "Punto de acceso no autorizado detectado"),
    ])
    conn.executemany("INSERT INTO configuracion_admin VALUES(?,?)", [
        ("LAB_SECRET_001", "lab-secreto-ficticio-001"),
        ("LAB_TOKEN_DEMO_2026", "lab-token-ficticio-2026"),
    ])
    # Autorización humana previa: luis.gomez puede leer incidentes.
    conn.execute("INSERT INTO autorizaciones(usuario,recurso,vigente,otorgada_por,fecha) VALUES(?,?,?,?,?)",
                 ("luis.gomez", "incidentes", 1, "marta.ruiz", datetime.now().isoformat(timespec="seconds")))
    conn.commit()


if __name__ == "__main__":  # python -m src.lab.seed -> crea data/lab.db con datos ficticios si no existe
    from . import repositorio
    repositorio.abrir()
    print(f"Base de datos lista: {repositorio.RUTA_DB}")
