"""Ensayo de demostración REPRODUCIBLE de Nova (criterio 35). Reloj virtual, sin IA ni red: recorre el ciclo completo y
verifica cada hito contra el estado del motor. `python -m src.lab.demo_nova` -> sale con código 1 si algún hito falla."""
import sys

from cryptography.fernet import Fernet

from .nova.ia import ControlIA
from .nova.motor import ErrorNova, NovaPartida, Secretos

SEC = Secretos(pepper="demo", clave_fernet=Fernet.generate_key())
R = []


def hito(n, c):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n)


def acc(m, eq, user, tipo, **p):
    return m.ejecutar({"action_type": tipo, "actor": {"kind": "human", "team": eq, "user": user}, "params": p})


def main():
    m = NovaPartida(secretos=SEC)
    hito("1. partida creada en CONFIGURACION; nada corre solo", m.estado == "CONFIGURACION" and m.reloj.ahora_ms() == 0)
    m.abrir_sala()
    m.unirse("Rojo1", "RED")
    for i in range(2):
        m.unirse(f"Azul{i + 1}", "BLUE")
    hito("2. sala de espera con jugadores", m.estado == "SALA_DE_ESPERA")
    m.marcar_lista()
    try:
        m.iniciar("ADMIN", False, "x")
        sin_confirmar = False
    except ErrorNova:
        sin_confirmar = True
    hito("3. iniciar sin confirmación se rechaza", sin_confirmar and m.estado == "LISTA")
    m.iniciar("ADMIN", True, "demo-" + m.id)
    hito("4. el admin inicia: EN_CURSO", m.estado == "EN_CURSO")
    r = acc(m, "RED", "Rojo1", "send_email", identidad_id="EMP-05", plantilla="aviso_soporte")
    m.avanzar(m.config["click_delay_s"] + 2)
    hito("5. correo del Rojo; el empleado no conectado pulsa y la credencial queda COMPROMETIDA", r["ok"] and m.creds["EMP-05"]["estado"] == "COMPROMETIDA")
    q = acc(m, "RED", "Rojo1", "query_resource", identidad_id="EMP-05")
    hito("6. consultar un recurso protegido genera una alerta real para el Azul", q["ok"] and any("recurso protegido" in al["titulo"] for al in m.alertas.values()))
    ia = ControlIA(m)
    ia.configurar("RED", "assist")
    try:
        ia.proponer("RED")
        espera = False
    except ErrorNova as e:
        espera = e.motivo == "DIRECTIVA_REQUIRED"
    run = ia.proponer("RED", {"accion": "extract_table", "objetivo": "extraer_tabla", "identidad_id": "EMP-05", "tabla": "reportes_financieros", "credencial": {"modo": "conocida"}})
    hito("6b. la IA espera: sin directiva no se lanza; con la credencial obtenida elegida en el combo propone y gasta 1 de 10 oportunidades", espera and run["propuesta"]["estado"] == "PROPUESTA"
         and ia.oportunidades("RED")["restantes"] == 9)
    x = acc(m, "RED", "Rojo1", "extract_table", identidad_id="EMP-05", tabla="reportes_financieros")
    hito("7. extracción W1 completada por el motor", x["ok"])
    hito("8. resultado VICTORIA_ROJA y partida FINALIZADA", m.estado == "FINALIZADA" and m.resultado["resultado"] == "VICTORIA_ROJA")
    hito("9. resultado persistido y descarga solo con lo extraído", m.db.execute("SELECT COUNT(*) FROM nova_results WHERE match_id=?", (m.id,)).fetchone()[0] == 1
         and "INSERT INTO reportes_financieros" in m.descarga("sql")[1])
    print(f"\n{sum(R)}/{len(R)} hitos")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
