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


def bootstrap_agrupado(grupos, repeticiones=2000, semilla=0):
    """Intervalo de una proporción cuando las observaciones vienen AGRUPADAS y no son independientes.

    Por qué hace falta: en una sesión de 12 rondas, el atacante recibe el historial de las anteriores. Las 12
    rondas no son 12 observaciones independientes; comparten sesión, técnica y deriva del modelo. Un Wilson
    sobre 240 rondas asume independencia y por eso sale **demasiado estrecho**: exagera la precisión.

    Este bootstrap remuestrea **sesiones completas** con reemplazo (cluster bootstrap), que es la forma
    estándar de respetar la agrupación: si una sesión entra, entra con todas sus rondas.

    `grupos` = [(exitos, n), ...], una tupla por sesión.
    -> {valor, bajo, alto, grupos, n, exitos, repeticiones, efecto_diseno}

    `efecto_diseno` es cuánto más ancho sale este intervalo que el de Wilson: por encima de 1, Wilson estaba
    siendo optimista. Es None si no se puede calcular.
    """
    gs = [(int(e), int(n)) for e, n in (grupos or []) if int(n) > 0]
    exitos, n = sum(e for e, _ in gs), sum(n for _, n in gs)
    base = {"grupos": len(gs), "n": n, "exitos": exitos,
            "valor": (exitos / n) if n else None, "repeticiones": 0,
            "bajo": None, "alto": None, "efecto_diseno": None}
    # Con menos de dos sesiones no hay variación entre grupos que remuestrear: no se inventa un intervalo.
    if len(gs) < 2:
        return base
    rnd = random.Random(semilla)
    tasas = []
    for _ in range(repeticiones):
        muestra = [gs[rnd.randrange(len(gs))] for _ in range(len(gs))]
        tn = sum(x[1] for x in muestra)
        if tn:
            tasas.append(sum(x[0] for x in muestra) / tn)
    if not tasas:
        return base
    tasas.sort()
    bajo, alto = percentil(tasas, 2.5), percentil(tasas, 97.5)
    # Si todas las sesiones dieron la misma tasa (p. ej. todas 0 éxitos), cada réplica del bootstrap sale
    # idéntica y el percentil da un intervalo de amplitud CERO. Eso no es «no hay incertidumbre»: es que
    # este método no puede estimarla sin variación entre grupos. Publicar [0,0 · 0,0] como intervalo del
    # 95 % sería afirmar una precisión que no existe, así que se devuelve None y se dice por qué. Para esos
    # casos el intervalo que sí significa algo es el de la tasa POR SESIÓN (Wilson sobre el nº de sesiones).
    if alto - bajo <= 0:
        return {**base, "repeticiones": repeticiones, "bajo": None, "alto": None,
                "degenerado": True,
                "nota": ("Todas las sesiones dieron la misma tasa: el bootstrap de clústeres no puede "
                         "estimar el intervalo. Cite la tasa por sesión, que sí lo tiene.")}
    w = wilson(exitos, n)
    efecto = None
    if w["amplitud"] and w["amplitud"] > 0:
        efecto = (alto - bajo) / w["amplitud"]
    return {**base, "bajo": bajo, "alto": alto, "repeticiones": repeticiones,
            "efecto_diseno": efecto, "degenerado": False, "nota": None}


# Por debajo de esta muestra por grupo, una diferencia de proporciones no se interpreta.
MUESTRA_MINIMA = 20
# Y por debajo de este número de grupos (sesiones), un intervalo agrupado no se interpreta: el bootstrap de
# clústeres necesita bastantes clústeres para que su percentil signifique algo.
GRUPOS_MINIMOS = 10


def comparar_agrupado(nombre_a, grupos_a, nombre_b, grupos_b, repeticiones=2000, semilla=0):
    """Compara dos proporciones agrupadas remuestreando sesiones completas en cada lado.

    Mismo contrato que `comparar`, pero respetando la agrupación: -> {a, b, diferencia, intervalo, veredicto,
    explicacion}. Es más conservador que `comparar` a propósito."""
    ga = [(int(e), int(n)) for e, n in (grupos_a or []) if int(n) > 0]
    gb = [(int(e), int(n)) for e, n in (grupos_b or []) if int(n) > 0]
    ba, bb = bootstrap_agrupado(ga, repeticiones, semilla), bootstrap_agrupado(gb, repeticiones, semilla)
    base = {"a": {"nombre": nombre_a, **ba}, "b": {"nombre": nombre_b, **bb},
            "diferencia": None, "intervalo": {"bajo": None, "alto": None}}
    if not ga or not gb:
        return {**base, "veredicto": "muestra_insuficiente",
                "explicacion": "Uno de los dos grupos no tiene ninguna sesión."}
    if min(len(ga), len(gb)) < GRUPOS_MINIMOS:
        return {**base, "diferencia": (bb["valor"] or 0) - (ba["valor"] or 0),
                "veredicto": "muestra_insuficiente",
                "explicacion": (f"Con {min(len(ga), len(gb))} sesiones en el lado menor (mínimo "
                                f"{GRUPOS_MINIMOS}) la diferencia agrupada no se interpreta.")}
    rnd = random.Random(semilla)
    difs = []
    for _ in range(repeticiones):
        ma = [ga[rnd.randrange(len(ga))] for _ in range(len(ga))]
        mb = [gb[rnd.randrange(len(gb))] for _ in range(len(gb))]
        na, nb = sum(x[1] for x in ma), sum(x[1] for x in mb)
        if na and nb:
            difs.append(sum(x[0] for x in mb) / nb - sum(x[0] for x in ma) / na)
    if not difs:
        return {**base, "veredicto": "muestra_insuficiente", "explicacion": "El remuestreo no dio ninguna "
                "réplica utilizable."}
    difs.sort()
    bajo, alto = percentil(difs, 2.5), percentil(difs, 97.5)
    dif = (bb["valor"] or 0) - (ba["valor"] or 0)
    out = {**base, "diferencia": dif, "intervalo": {"bajo": bajo, "alto": alto}}
    if bajo > 0:
        return {**out, "veredicto": "mejora",
                "explicacion": (f"{nombre_b} supera a {nombre_a} agrupando por sesión: el intervalo "
                                f"({bajo:.3f}, {alto:.3f}) no incluye el 0.")}
    if alto < 0:
        return {**out, "veredicto": "empeora",
                "explicacion": (f"{nombre_b} queda por debajo de {nombre_a} agrupando por sesión: el "
                                f"intervalo ({bajo:.3f}, {alto:.3f}) no incluye el 0.")}
    return {**out, "veredicto": "sin_diferencia_concluyente",
            "explicacion": (f"El intervalo agrupado del 95 % ({bajo:.3f}, {alto:.3f}) incluye el 0: con "
                            "estas sesiones no se puede afirmar que haya diferencia.")}


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
