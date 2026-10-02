"""Pruebas offline de las capas del laboratorio (BD en memoria). Ejecutar: python -m src.lab.test_lab"""
from . import herramientas as H
from . import repositorio
from .repositorio import PermisoDenegado

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repo = repositorio.abrir(":memory:")
    visita, ana, luis, marta, root = (repo.identidad(u) for u in
                                      ("visita.demo", "ana.perez", "luis.gomez", "marta.ruiz", "root.lab"))
    run = lambda n, p, i: H.ejecutar_herramienta(n, p, i, repo)  # noqa: E731

    r = run("consultar_inventario", {}, visita)
    chk("invitado lee inventario PUBLICO", r["ok"] and len(r["datos"]) >= 3)
    r = run("consultar_clientes", {}, visita)
    chk("invitado NO lee clientes (permisos)", not r["ok"] and r["capa_bloqueo"] == "permisos")

    r = run("consultar_incidentes", {}, ana)
    chk("empleado sin autorizacion -> capa autorizacion", r["capa_bloqueo"] == "autorizacion" and r["requiere_autorizacion"])
    r = run("consultar_configuracion_admin", {}, ana)
    chk("empleado NO lee config admin (permisos)", not r["ok"] and r["capa_bloqueo"] == "permisos")

    chk("empleado con autorizacion previa lee incidentes", run("consultar_incidentes", {}, luis)["ok"])
    chk("analista lee incidentes", run("consultar_incidentes", {"severidad": "ALTA"}, marta)["ok"])
    chk("analista NO lee config admin", run("consultar_configuracion_admin", {}, marta)["capa_bloqueo"] == "permisos")
    r = run("consultar_configuracion_admin", {}, root)
    chk("admin lee config admin", r["ok"] and len(r["datos"]) == 2)

    chk("inyeccion SQL en parametro -> validacion",
        run("consultar_inventario", {"sku": "' OR 1=1 --"}, root)["capa_bloqueo"] == "validacion")
    chk("parametro 'rol' inyectado -> validacion",
        run("consultar_inventario", {"rol": "admin"}, visita)["capa_bloqueo"] == "validacion")
    chk("herramienta inexistente -> catalogo",
        run("ejecutar_sql", {"q": "DROP TABLE usuarios"}, root)["capa_bloqueo"] == "catalogo")

    try:
        repo.consultar(ana, "configuracion_admin")
        capa = None
    except PermisoDenegado as exc:
        capa = exc.capa
    chk("repositorio bloquea por si solo (ultima capa)", capa == "repositorio")
    try:
        repo.consultar(root, "usuarios")
        ok_tabla = False
    except ValueError:
        ok_tabla = True
    chk("repositorio rechaza tablas fuera de la especificacion", ok_tabla)

    try:
        repo.autorizador.otorgar(ana, "ana.perez", "incidentes")
        otorgo = True
    except PermisoDenegado:
        otorgo = False
    chk("un empleado no puede otorgarse autorizaciones", not otorgo)
    repo.autorizador.otorgar(marta, "ana.perez", "incidentes")
    chk("analista otorga y el empleado ya lee incidentes", run("consultar_incidentes", {}, ana)["ok"])
    try:
        repo.autorizador.otorgar(root, "ana.perez", "configuracion_admin")
        delego = True
    except PermisoDenegado:
        delego = False
    chk("recursos CRITICOS nunca se delegan", not delego)
    repo.autorizador.revocar(marta, "ana.perez", "incidentes")
    chk("revocar autorizacion cierra el acceso", run("consultar_incidentes", {}, ana)["capa_bloqueo"] == "autorizacion")

    try:
        repo.conn.execute("DELETE FROM auditoria")
        borro = True
    except Exception:  # noqa: BLE001
        borro = False
    chk("auditoria es append-only y tiene registros", not borro and len(repo.auditoria()) > 0)

    r = H.ejecutar_herramienta("consultar_inventario", {}, None, repo)
    chk("fallo interno -> error explicito, no se disfraza de bloqueo",
        (not r["ok"]) and r["error"] is not None and r["capa_bloqueo"] is None)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
