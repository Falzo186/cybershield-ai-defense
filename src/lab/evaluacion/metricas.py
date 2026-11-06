"""Estadística de las campañas. Solo stdlib, determinista y sin inventar nada.

Dos ideas que atraviesan el módulo:
  - **Una proporción sin tamaño de muestra no es un resultado.** Todas las funciones devuelven `n` junto al
    valor, y los intervalos de confianza son obligatorios, no un adorno.
  - **Con pocos datos, se dice que son pocos.** `comparar` responde «muestra insuficiente» en vez de declarar
    una mejora que el ruido explicaría igual de bien.
"""
import math
import random

Z95 = 1.959963984540054   # normal estándar, dos colas, 95 %


def proporcion(exitos, total):
    """-> {exitos, n, valor} ; `valor` es None si n == 0 (nunca 0.0, que significaría «falló todo»)."""
    exitos, total = int(exitos), int(total)
    return {"exitos": exitos, "n": total, "valor": (exitos / total) if total else None}


def wilson(exitos, total, z=Z95):
    """Intervalo de confianza de Wilson para una proporción. Es el adecuado con muestras pequeñas y con
    proporciones pegadas a 0 o a 1, donde el intervalo normal da límites imposibles (<0 o >1).

    -> {exitos, n, valor, bajo, alto, amplitud} ; todo None salvo n si no hay muestra."""
    p = proporcion(exitos, total)
    if not p["n"]:
        return {**p, "bajo": None, "alto": None, "amplitud": None}
    n, ph = p["n"], p["valor"]
    denom = 1 + z * z / n
    centro = (ph + z * z / (2 * n)) / denom
    margen = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / denom
    # El redondeo a 12 decimales evita que, con p = 1, el límite superior salga 0.9999999999999999 por error
    # de coma flotante: el intervalo de Wilson en ese caso es exactamente 1.
    bajo = round(max(0.0, centro - margen), 12)
    alto = round(min(1.0, centro + margen), 12)
    return {**p, "bajo": bajo, "alto": alto, "amplitud": alto - bajo}


def resumen_numerico(valores):
    """Media, mediana, p95, mínimo y máximo de una lista de números. Ignora None.
    -> {n, media, mediana, p95, min, max} ; los estadísticos son None si no hay datos."""
    xs = sorted(v for v in (valores or []) if isinstance(v, (int, float)) and not isinstance(v, bool))
    if not xs:
        return {"n": 0, "media": None, "mediana": None, "p95": None, "min": None, "max": None}
    return {"n": len(xs), "media": sum(xs) / len(xs), "mediana": percentil(xs, 50),
            "p95": percentil(xs, 95), "min": xs[0], "max": xs[-1]}


def percentil(ordenados, p):
    """Percentil por interpolación lineal sobre una lista YA ordenada."""
    if not ordenados:
        return None
    if len(ordenados) == 1:
        return ordenados[0]
    pos = (len(ordenados) - 1) * (p / 100)
    bajo, alto = math.floor(pos), math.ceil(pos)
    if bajo == alto:
        return ordenados[int(pos)]
    return ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * (pos - bajo)


def bootstrap_diferencia(exitos_a, n_a, exitos_b, n_b, repeticiones=2000, semilla=0, z=Z95):
    """Intervalo bootstrap de la diferencia de proporciones (B − A), remuestreando cada grupo.

    -> {diferencia, bajo, alto, repeticiones, n_a, n_b} ; None si falta muestra en algún lado.
    La semilla hace el resultado reproducible: con la misma entrada sale el mismo intervalo."""
    if not n_a or not n_b:
        return {"diferencia": None, "bajo": None, "alto": None, "repeticiones": 0, "n_a": n_a, "n_b": n_b}
    pa, pb = exitos_a / n_a, exitos_b / n_b
    rnd = random.Random(semilla)
    difs = []
    for _ in range(repeticiones):
        ma = sum(1 for _ in range(n_a) if rnd.random() < pa) / n_a
        mb = sum(1 for _ in range(n_b) if rnd.random() < pb) / n_b
        difs.append(mb - ma)
    difs.sort()
    return {"diferencia": pb - pa, "bajo": percentil(difs, 2.5), "alto": percentil(difs, 97.5),
            "repeticiones": repeticiones, "n_a": n_a, "n_b": n_b}


# Por debajo de esta muestra por grupo, una diferencia de proporciones no se interpreta.
MUESTRA_MINIMA = 20


def comparar(nombre_a, exitos_a, n_a, nombre_b, exitos_b, n_b, repeticiones=2000, semilla=0):
    """Compara dos grupos y dice qué se puede concluir y qué no.

    -> {a, b, diferencia, intervalo, veredicto, explicacion}
    veredicto: «muestra_insuficiente» | «sin_diferencia_concluyente» | «mejora» | «empeora»."""
    wa, wb = wilson(exitos_a, n_a), wilson(exitos_b, n_b)
    boot = bootstrap_diferencia(exitos_a, n_a, exitos_b, n_b, repeticiones, semilla)
    base = {"a": {"nombre": nombre_a, **wa}, "b": {"nombre": nombre_b, **wb},
            "diferencia": boot["diferencia"], "intervalo": {"bajo": boot["bajo"], "alto": boot["alto"]}}
    if not n_a or not n_b:
        return {**base, "veredicto": "muestra_insuficiente",
                "explicacion": "Uno de los dos grupos no tiene ninguna observación."}
    if min(n_a, n_b) < MUESTRA_MINIMA:
        return {**base, "veredicto": "muestra_insuficiente",
                "explicacion": (f"Con {min(n_a, n_b)} observaciones en el grupo menor (mínimo "
                                f"{MUESTRA_MINIMA}) la diferencia no se interpreta.")}
    if boot["bajo"] is not None and boot["bajo"] > 0:
        return {**base, "veredicto": "mejora",
                "explicacion": (f"{nombre_b} supera a {nombre_a}: el intervalo del 95 % de la diferencia "
                                f"({boot['bajo']:.3f}, {boot['alto']:.3f}) no incluye el 0.")}
    if boot["alto"] is not None and boot["alto"] < 0:
        return {**base, "veredicto": "empeora",
                "explicacion": (f"{nombre_b} queda por debajo de {nombre_a}: el intervalo del 95 % "
                                f"({boot['bajo']:.3f}, {boot['alto']:.3f}) no incluye el 0.")}
    return {**base, "veredicto": "sin_diferencia_concluyente",
            "explicacion": (f"El intervalo del 95 % de la diferencia ({boot['bajo']:.3f}, {boot['alto']:.3f}) "
                            "incluye el 0: con esta muestra no se puede afirmar que haya diferencia.")}


def clasificacion(vp, fp, fn, vn):
    """Métricas de un clasificador binario, con intervalo de confianza y denominador siempre visible.

    Cada tasa dice sobre cuántos casos se calculó. Una tasa sin denominador es `None`, no 0: con 0 casos
    maliciosos no hay recall del 0 %, no hay recall.

    F1 no lleva intervalo de confianza: es una media armónica de dos proporciones correlacionadas y un
    Wilson sobre ella no significaría nada. Se publica el valor y, al lado, los IC de precisión y recall,
    que sí son interpretables."""
    vp, fp, fn, vn = (int(x or 0) for x in (vp, fp, fn, vn))
    prec = wilson(vp, vp + fp)
    rec = wilson(vp, vp + fn)
    p, r = prec["valor"], rec["valor"]
    f1 = (2 * p * r / (p + r)) if (p is not None and r is not None and (p + r) > 0) else None
    return {
        "VP": vp, "FP": fp, "FN": fn, "VN": vn,
        "n": vp + fp + fn + vn, "positivos_reales": vp + fn, "negativos_reales": fp + vn,
        "precision": prec,                       # de lo marcado como malicioso, cuánto lo era
        "recall": rec,                           # de lo malicioso, cuánto se marcó (= sensibilidad)
        "especificidad": wilson(vn, fp + vn),
        "exactitud": wilson(vp + vn, vp + fp + fn + vn),
        "f1": None if f1 is None else round(f1, 6),
        "nota_f1": ("F1 sin intervalo de confianza a propósito: es una media de dos proporciones "
                    "correlacionadas. Use los IC de precisión y recall."),
    }
