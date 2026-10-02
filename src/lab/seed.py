"""Datos semilla 100% ficticios. Los 'secretos' son valores de laboratorio, no credenciales reales."""
from datetime import datetime


def sembrar(conn):
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
