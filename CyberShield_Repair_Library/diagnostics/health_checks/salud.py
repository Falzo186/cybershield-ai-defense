"""Comprobaciones de salud (CyberShield Repair §13). Cada una devuelve {estado: ok|degradado|caido, detalle}; el estado global es el peor.
Solo diagnostica: no arregla ni reinicia nada, y no incluye secretos (ni tokens, ni códigos, ni contraseñas)."""
ORDEN = {"ok": 0, "degradado": 1, "caido": 2}


def comprobar(nombre, fn):
    try:
        estado, detalle = fn()
    except Exception as exc:  # noqa: BLE001 - una comprobación rota se informa, no tumba el diagnóstico
        estado, detalle = "caido", f"{type(exc).__name__}: {str(exc)[:120]}"
    return {"nombre": nombre, "estado": estado, "detalle": detalle}


def informe(comprobaciones):
    """comprobaciones = [(nombre, fn)] -> {estado, comprobaciones}."""
    res = [comprobar(n, f) for n, f in comprobaciones]
    peor = max((ORDEN[r["estado"]] for r in res), default=0)
    return {"estado": [k for k, v in ORDEN.items() if v == peor][0], "comprobaciones": res}
