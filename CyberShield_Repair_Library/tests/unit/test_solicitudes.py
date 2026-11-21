"""Pruebas unitarias de la máquina de estados de solicitudes de autorización. Ejecutar: python CyberShield_Repair_Library/tests/unit/test_solicitudes.py"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from CyberShield_Repair_Library.components.approvals.solicitudes import ErrorSolicitud, Solicitudes  # noqa: E402

R = []


def chk(n, c):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n)


def lanza(fn, status):
    try:
        fn()
    except ErrorSolicitud as e:
        return e.status == status
    return False


def main():
    t = [0.0]
    S = Solicitudes(sqlite3.connect(":memory:"), lambda: t[0], ttl_s=60)
    s, nueva = S.crear("P1", "k1", "ana.perez", "Rojo1", "consultar", "clientes", "necesito el listado")
    chk("crear: PENDIENTE con recomendación etiquetada «reglas» y riesgo ALTO para un recurso sensible",
        nueva and s["estado"] == "PENDIENTE" and s["recomendacion"]["origen"] == "reglas" and s["riesgo"] == "ALTO" and s["tiempo_restante_s"] == 60)
    s2, nueva2 = S.crear("P1", "k1", "ana.perez", "Rojo1", "consultar", "clientes", "necesito el listado")
    chk("idempotente: la misma clave de origen no crea otra solicitud", not nueva2 and s2["id"] == s["id"] and len(S.listar("P1")) == 1)
    chk("faltan datos -> 400", lanza(lambda: S.crear("P1", "k2", "ana", "R", "", "x", "y"), 400))
    a = S.aprobar(s["id"], "Azul1")
    chk("aprobar: PENDIENTE -> APROBADA con quién la resolvió", a["estado"] == "APROBADA" and a["resuelta_por"] == "Azul1" and a["tiempo_restante_s"] == 0)
    chk("una solicitud resuelta no admite más cambios (409)", lanza(lambda: S.rechazar(s["id"], "Azul2"), 409) and lanza(lambda: S.cancelar(s["id"], "Rojo1"), 409))
    b, _ = S.crear("P1", "k3", "luis", "Rojo1", "restablecer", "contraseña", "olvidé la mía")
    chk("rechazar: PENDIENTE -> RECHAZADA", S.rechazar(b["id"], "Azul1")["estado"] == "RECHAZADA")
    c, _ = S.crear("P1", "k4", "luis", "Rojo1", "leer", "informe", "reunión")
    chk("cancelar: PENDIENTE -> CANCELADA", S.cancelar(c["id"], "Rojo1")["estado"] == "CANCELADA")
    d, _ = S.crear("P1", "k5", "luis", "Rojo1", "leer", "informe", "otra")
    t[0] += 30
    chk("el tiempo restante baja con el tiempo de partida", S.obtener(d["id"])["tiempo_restante_s"] == 30)
    t[0] += 40
    chk("vence a su hora: PENDIENTE -> EXPIRADA (nunca queda pendiente indefinidamente)", S.obtener(d["id"])["estado"] == "EXPIRADA" and S.obtener(d["id"])["resuelta_por"] == "sistema")
    chk("una expirada no se puede aprobar (409)", lanza(lambda: S.aprobar(d["id"], "Azul1"), 409))
    chk("solicitud desconocida -> 404", lanza(lambda: S.aprobar(9999, "Azul1"), 404))
    e, _ = S.crear("P2", "k1", "ana", "Rojo9", "x", "y", "z")
    chk("las solicitudes son por partida", len(S.listar("P2")) == 1 and len(S.listar("P1")) == 4)
    chk("filtros por estado y por jugador", len(S.listar("P1", estado="APROBADA")) == 1 and len(S.listar("P1", jugador="Rojo9")) == 0)
    print(f"Total {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
