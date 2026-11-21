"""Reglas simuladas (ids 100000+) y generador de ruido benigno. MITRE ATT&CK solo como etiqueta educativa."""

M = lambda i, tac, tec: {"id": i, "tactic": tac, "technique": tec}  # noqa: E731

REGLAS = {
    # Señales observables de una solicitud (nunca la verdad de fondo)
    "solicitud.referencia_invalida": (100010, 8, "Solicitud con referencia de autorización no registrada",
                                      ["cybershield_lab", "ingenieria_social"], M("T1566", "Initial Access", "Phishing")),
    "solicitud.identidad_inconsistente": (100011, 9, "Identidad declarada inconsistente con el registro",
                                          ["cybershield_lab", "identidad"], M("T1078", "Defense Evasion", "Valid Accounts")),
    "solicitud.fuera_alcance": (100012, 7, "Solicitud sobre un recurso fuera del alcance del rol",
                                ["cybershield_lab", "permisos"], M("T1548", "Privilege Escalation", "Abuse Elevation Control Mechanism")),
    "solicitud.urgencia": (100013, 4, "Solicitud marcada como urgente",
                           ["cybershield_lab", "ingenieria_social"], M("T1566", "Initial Access", "Phishing")),
    "solicitud.patron_repetido": (100014, 10, "Patrón repetido de intentos del mismo solicitante",
                                  ["cybershield_lab", "ingenieria_social"], M("T1078", "Defense Evasion", "Valid Accounts")),
    # Consecuencias en el estado
    "accion.bloqueada_politica": (100020, 10, "Acceso denegado por política determinista tras una aprobación",
                                  ["cybershield_lab", "permisos"], M("T1548", "Privilege Escalation", "Abuse Elevation Control Mechanism")),
    "accion.aprobada_delegada": (100021, 9, "Aprobación en zona delegada al defensor",
                                 ["cybershield_lab", "aprobacion"], M("T1078", "Defense Evasion", "Valid Accounts")),
    "campo.protegido_modificado": (100022, 12, "Cambio de campo protegido de prueba",
                                   ["cybershield_lab", "integridad"], M("T1565", "Impact", "Data Manipulation")),
    "acceso.restablecido": (100023, 10, "Restablecimiento de acceso a una identidad",
                            ["cybershield_lab", "identidad"], M("T1098", "Persistence", "Account Manipulation")),
    "documento.liberado": (100024, 8, "Liberación de documento interno",
                           ["cybershield_lab", "confidencialidad"], M("T1213", "Collection", "Data from Information Repositories")),
    "excepcion.aprobada": (100025, 8, "Excepción de política aprobada",
                           ["cybershield_lab", "aprobacion"], M("T1548", "Privilege Escalation", "Abuse Elevation Control Mechanism")),
    "contencion.ejecutada": (100030, 6, "Contención ejecutada por el equipo azul",
                             ["cybershield_lab", "respuesta"], M("T1562", "Defense Evasion", "Impair Defenses")),
    "escalada.solicitada": (100031, 5, "Solicitud escalada a un responsable humano",
                            ["cybershield_lab", "respuesta"], None),
    # Modo Caminos / credenciales (misión Caminos): señales de acceso y respuesta. Todo SIMULADO.
    "caminos.acceso_inusual": (100050, 7, "Inicio de sesión desde un canal externo inusual para la identidad",
                               ["cybershield_lab", "identidad", "caminos"], M("T1078", "Initial Access", "Valid Accounts")),
    "caminos.correo_clic": (100051, 6, "Un empleado abrió el enlace de un correo señuelo",
                            ["cybershield_lab", "ingenieria_social", "caminos"], M("T1566", "Initial Access", "Phishing")),
    "caminos.correo_reportado": (100052, 5, "Correo señuelo reportado por el equipo azul",
                                 ["cybershield_lab", "respuesta", "caminos"], None),
    "caminos.honeytoken": (100053, 13, "Uso de una credencial señuelo (honeytoken)",
                           ["cybershield_lab", "identidad", "caminos"], M("T1078", "Defense Evasion", "Valid Accounts")),
    "caminos.intentos_repetidos": (100054, 9, "Intentos de autenticación repetidos contra la misma identidad",
                                   ["cybershield_lab", "identidad", "caminos"], M("T1110", "Credential Access", "Brute Force")),
    "caminos.cuenta_bloqueada": (100055, 8, "Cuenta bloqueada tras intentos fallidos",
                                 ["cybershield_lab", "identidad", "caminos"], None),
    "caminos.credencial_rotada": (100056, 6, "Credencial rotada por el equipo azul",
                                  ["cybershield_lab", "respuesta", "caminos"], M("T1098", "Persistence", "Account Manipulation")),
    "caminos.base_entregada": (100057, 12, "Entrega de la base de datos sintética a un solicitante",
                               ["cybershield_lab", "confidencialidad", "caminos"], M("T1213", "Collection", "Data from Information Repositories")),
    "caminos.documento_instruccion": (100058, 5, "Documento procesado con texto que simula instrucciones",
                                      ["cybershield_lab", "ingenieria_social", "caminos"], M("T1566", "Initial Access", "Phishing")),
    "solicitud.legitima_atendida": (100040, 3, "Solicitud de empleado atendida",
                                    ["cybershield_lab", "rutina"], None),
}

# Ruido de fondo (nivel 1-4): benigno, sin relación con ninguna solicitud.
RUIDO = [
    (100900, 2, "Inicio de sesión correcto de usuario de servicio", ["syslog", "authentication_success"], "sshd: Accepted publickey for svc-backup"),
    (100901, 3, "Cambio de hora del sistema", ["ossec", "time_change"], "systemd-timesyncd: Synchronized to time server"),
    (100902, 2, "Paquete actualizado", ["syslog", "package_update"], "apt: upgraded libssl3 (rutina)"),
    (100903, 3, "Proceso programado ejecutado", ["syslog", "cron"], "CRON: (root) CMD (/usr/local/bin/rotar-logs)"),
    (100904, 4, "Intento de inicio de sesión fallido aislado", ["syslog", "authentication_failed"], "sshd: Failed password for invalid user test"),
    (100905, 1, "Servicio reiniciado", ["syslog", "service"], "systemd: Started Daily apt download activities"),
    (100906, 3, "Comprobación de integridad completada", ["ossec", "syscheck"], "syscheck: integrity check finished (0 changes)"),
    (100907, 2, "Conexión a la base de datos establecida", ["syslog", "database"], "postgres: connection authorized: user=app"),
    (100908, 4, "Aviso de disco al 80 %", ["syslog", "disk"], "df: /var al 80 % de uso"),
]
