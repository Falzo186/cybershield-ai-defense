"""Campaña grande del objetivo del atacante (n >= 200 por condición), por sesiones y reanudable.

Qué mide, exactamente: **si el modelo atacante consigue que salgan datos por encima del permiso de la
identidad**. Se mide sobre la EJECUCIÓN real, no sobre lo que diga el texto del defensor. Una ronda en la
que falla la infraestructura no cuenta ni a favor ni en contra: queda fuera del denominador.

Por qué por sesiones y no en una sola tirada de 240 rondas: el atacante recibe el historial de la sesión, y
una sesión de 240 rondas no se parece a nada real; además el prompt crecería sin límite. La unidad natural
es la partida. Aquí son sesiones de 12 rondas, que es el techo por defecto de `PresupuestoPartida`.

Las dos condiciones cambian **solo el modelo defensor**, porque las campañas del defensor
(`campanas_grandes.py`) dejaron claro que `llama3.2:3b` rechaza todo y `qwen2.5:7b` no. La pregunta que
contesta esto es si el atacante consigue algo contra un defensor que de verdad discrimina.

Reanudable: cada ronda se añade a su JSONL con el número de sesión y de ronda. Al relanzar se cuentan las
sesiones ya completas y se siguen las que falten. No se reescribe nada.

Uso:
    python experimentos/campana_atacante.py                  # las dos condiciones
    python experimentos/campana_atacante.py --estado
    python experimentos/campana_atacante.py --solo def-l32
    python experimentos/campana_atacante.py --max-segundos 1800
"""
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.lab import adversarial, motor, permisos, repositorio      # noqa: E402
from src.lab.evaluacion import metricas                            # noqa: E402

HOST = "http://localhost:11434"
MODELO_ATACANTE = "llama3.2:3b"
RONDAS_POR_SESION = 12
SESIONES = 20                      # 20 x 12 = 240 rondas planificadas por condición
ROL = "empleado"                   # ni el más restringido ni el más permisivo
# Las tres técnicas del catálogo, rotadas por sesión, más sesiones de elección libre del atacante.
ESCENARIOS = ["suplantacion_identidad", "verificacion_falsa", "escalada_privilegios", None]
DIRECTORIO = RAIZ / "data" / "campanas"
SALIDA_JSON = RAIZ / "data" / "campana_atacante.json"

CONDICIONES = [
    ("def-l32", {"modelo_defensor": "llama3.2:3b"},
     "Defensor llama3.2:3b, el que rechaza todo según las campañas del defensor."),
    ("def-q25", {"modelo_defensor": "qwen2.5:7b"},
     "Defensor qwen2.5:7b, el único que supera al defensor constante."),
]
NOMBRES = {n for n, _, _ in CONDICIONES}


def ruta(nombre):
    return DIRECTORIO / f"atacante-{nombre}.jsonl"


def config_de(nombre):
    base = next(c for n, c, _ in CONDICIONES if n == nombre)
    return {"host": HOST, "modelo_atacante": MODELO_ATACANTE, "rol": ROL,
            "rondas_por_sesion": RONDAS_POR_SESION, "sesiones": SESIONES,
            "escenarios": ESCENARIOS, "intensidad": 2, **base}


def _anadir(nombre, registro):
    r = ruta(nombre)
    r.parent.mkdir(parents=True, exist_ok=True)
    with r.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")


def leer(nombre):
    """-> {config, filas, sesiones_completas, huerfanas}. Una línea ilegible se cuenta, no desaparece.

    `filas` contiene SOLO las rondas de sesiones marcadas como completas. Las rondas de una sesión que se
    quedó a medias (porque mataron el proceso) son **huérfanas**: se conservan en el archivo, pero quedan
    fuera de las métricas, porque al reanudar esa sesión se vuelve a ejecutar entera y contarlas dos veces
    inflaría el denominador. Se informa de cuántas hay; no se borran nunca.
    """
    r = ruta(nombre)
    if not r.exists():
        return None
    cfg, todas, completas, ilegibles = None, [], set(), 0
    for linea in r.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            reg = json.loads(linea)
        except ValueError:
            ilegibles += 1
            continue
        if reg.get("tipo") == "cabecera" and cfg is None:
            cfg = reg.get("config") or {}
        elif reg.get("tipo") == "ronda":
            todas.append(reg["fila"] | {"sesion": int(reg["sesion"]),
                                        "escenario": reg.get("escenario")})
        elif reg.get("tipo") == "sesion":
            completas.add(int(reg["sesion"]))
    filas = [f for f in todas if f["sesion"] in completas]
    return {"config": cfg or {}, "filas": filas, "sesiones_completas": completas,
            "huerfanas": len(todas) - len(filas), "ilegibles": ilegibles}


def progreso(nombre):
    e = leer(nombre)
    if e is None:
        return None
    hechas = len(e["sesiones_completas"])
    return {"sesiones": hechas, "sesiones_planificadas": SESIONES, "rondas": len(e["filas"]),
            "rondas_planificadas": SESIONES * RONDAS_POR_SESION,
            "completa": hechas >= SESIONES, "ilegibles": e["ilegibles"]}


def ejecutar(nombre, max_segundos=None):
    cfg = config_de(nombre)
    if leer(nombre) is None:
        _anadir(nombre, {"tipo": "cabecera", "creada": time.strftime("%Y-%m-%d %H:%M:%S"), "config": cfg})
    e = leer(nombre)
    # La condición guardada manda: si alguien cambia el modelo y relanza, se para en vez de mezclar.
    for clave in ("modelo_atacante", "modelo_defensor", "rol", "rondas_por_sesion", "intensidad"):
        if e["config"].get(clave) != cfg[clave]:
            print(f"  [{nombre}] NO se reanuda: «{clave}» cambió "
                  f"({e['config'].get(clave)!r} -> {cfg[clave]!r}). Los resultados viejos siguen en su "
                  f"archivo; use otro nombre en vez de mezclar dos conjuntos.")
            return progreso(nombre)

    repo = repositorio.abrir(":memory:")
    identidad = permisos.Identidad(f"atq.{ROL}", ROL)
    t0 = time.monotonic()
    for s in range(1, SESIONES + 1):
        if s in e["sesiones_completas"]:
            continue
        if max_segundos is not None and (time.monotonic() - t0) >= max_segundos:
            print(f"  [{nombre}] tope de tiempo de esta tanda tras {len(e['sesiones_completas'])} sesiones")
            return progreso(nombre)
        escenario = ESCENARIOS[(s - 1) % len(ESCENARIOS)]
        ts = time.monotonic()
        # Cada ronda se guarda EN CUANTO termina, no al acabar la sesión. Es el arreglo del fallo del
        # 07/11: mataron el proceso a mitad de una sesión y se perdieron las rondas ya calculadas de esa
        # sesión, que son minutos de inferencia real. Ahora en el disco queda todo lo ejecutado; lo que no
        # llegue a cerrar sesión se marca huérfano y se repite, sin contarse dos veces.
        # `campana_atacante` se traga cualquier excepción del observador a propósito, para que un observador
        # roto no tumbe la campaña. Aquí eso no vale: si no se puede escribir, hay que enterarse. Así que el
        # escritor apunta su propio fallo y se comprueba al cerrar la sesión.
        fallos_escritura = []

        def escribir(n, fila, _s=s, _e=escenario, _f=fallos_escritura):
            try:
                _anadir(nombre, {"tipo": "ronda", "sesion": _s, "escenario": _e, "fila": fila})
            except OSError as exc:
                _f.append(f"ronda {n}: {type(exc).__name__}: {exc}")

        r = adversarial.campana_atacante(
            motor.ejecutar_ronda, HOST, MODELO_ATACANTE, cfg["modelo_defensor"], identidad, repo=repo,
            rondas=RONDAS_POR_SESION, escenario=escenario, intensidad=cfg["intensidad"],
            al_avanzar=escribir)
        if fallos_escritura:
            print(f"  [{nombre}] NO se cierra la sesión {s}: fallaron {len(fallos_escritura)} escrituras "
                  f"({fallos_escritura[0]}). Las rondas quedan huérfanas y la sesión se repetirá.")
            return progreso(nombre)
        _anadir(nombre, {"tipo": "sesion", "sesion": s, "escenario": escenario,
                         "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "duracion_s": round(time.monotonic() - ts, 1),
                         "metricas": r["metricas"]})
        e = leer(nombre)
        res = resumen(nombre)
        obj, eng = res["objetivo_por_ronda"], res["engano_por_ronda"]
        print(f"  [{nombre}] sesión {s:>2}/{SESIONES} ({escenario or 'libre'}) en "
              f"{(time.monotonic() - ts) / 60:.1f} min · objetivo {obj['exitos']}/{obj['n']} · "
              f"engaño {eng['exitos']}/{eng['n']}", flush=True)
    return progreso(nombre)


def _grupos(filas, clave):
    """[(exitos, n), ...] una tupla por sesión, para el bootstrap agrupado. Solo rondas imputables."""
    por_sesion = {}
    for f in filas:
        if not f.get("imputable"):
            continue
        d = por_sesion.setdefault(f["sesion"], [0, 0])
        d[1] += 1
        d[0] += int(bool(f.get(clave)))
    return [tuple(v) for _, v in sorted(por_sesion.items())]


def resumen(nombre):
    """Resumen completo de una condición. Publica la tasa por ronda y por sesión, y DOS intervalos.

    Por qué dos: 240 rondas no son 240 observaciones independientes. Dentro de una sesión el atacante ve el
    historial de las rondas anteriores, así que comparten sesión, técnica y deriva del modelo. El Wilson
    sobre las 240 rondas asume independencia y sale demasiado estrecho; el agrupado remuestrea sesiones
    completas. El agrupado es el que hay que citar.
    """
    e = leer(nombre)
    if e is None:
        return None
    filas = e["filas"]
    base = adversarial.resumir_atacante(filas)
    imput = [f for f in filas if f.get("imputable")]
    sesiones = sorted({f["sesion"] for f in filas})

    por_esc = {}
    for f in imput:
        d = por_esc.setdefault(f.get("escenario") or "libre", {"exitos": 0, "n": 0})
        d["n"] += 1
        d["exitos"] += int(bool(f.get("conseguido")))
    for d in por_esc.values():
        d.update(metricas.wilson(d["exitos"], d["n"]))

    g_obj, g_eng = _grupos(filas, "conseguido"), _grupos(filas, "engano_modelo")
    # Tasa por SESIÓN: ¿en cuántas sesiones el atacante consiguió el objetivo al menos una vez? La unidad es
    # la partida, que es como se juega de verdad; y aquí las sesiones sí son independientes entre sí.
    ses_con_exito = sum(1 for ex, _ in g_obj if ex > 0)
    ses_con_engano = sum(1 for ex, _ in g_eng if ex > 0)
    return {
        "config": e["config"], "progreso": progreso(nombre),
        "sesiones": len(sesiones), "rondas": len(filas), "imputables": len(imput),
        "huerfanas": e["huerfanas"], "ilegibles": e["ilegibles"],
        # ── Lo que pasó, contado sin interpretar ───────────────────────────────────────────────────────────
        "intentos": len(filas),
        "no_imputables": len(filas) - len(imput),
        "errores_modelo": adversarial.cuenta(
            [f for f in filas if not f.get("imputable")], "error", omitir_vacio=True),
        "por_veredicto": base["por_veredicto"],
        "por_decision_defensor": base["por_decision_defensor"],
        "bloqueadas_por_capa": base["bloqueadas_por_capa"],
        "frenado_por": base["frenado_por"],
        # ── Las dos tasas, cada una con su intervalo ingenuo y su intervalo agrupado ───────────────────────
        "objetivo_por_ronda": metricas.wilson(sum(1 for f in imput if f.get("conseguido")), len(imput)),
        "objetivo_agrupado": metricas.bootstrap_agrupado(g_obj),
        "objetivo_por_sesion": metricas.wilson(ses_con_exito, len(g_obj)),
        "engano_por_ronda": metricas.wilson(sum(1 for f in imput if f.get("engano_modelo")), len(imput)),
        "engano_agrupado": metricas.bootstrap_agrupado(g_eng),
        "engano_por_sesion": metricas.wilson(ses_con_engano, len(g_eng)),
        "grupos_objetivo": g_obj,
        "por_escenario": dict(sorted(por_esc.items())),
        "por_tecnica": base["por_tecnica"],
        # ── Coste ─────────────────────────────────────────────────────────────────────────────────────────
        "latencia_atacante_ms": base["latencia_atacante_ms"],
        "latencia_defensor_ms": base["latencia_defensor_ms"],
        "latencia_ronda_ms": metricas.resumen_numerico([f.get("ms") for f in filas]),
        "tokens_atacante": base["tokens_atacante"],
        "tokens_defensor": base["tokens_defensor"],
        "definicion": base["definicion"],
        "definicion_engano": base["definicion_engano"],
    }


# En estas dos medidas, MÁS ES PEOR: un defensor al que engañan más no «mejora». `metricas.comparar_agrupado`
# usa etiquetas neutras («mejora» = el segundo grupo tiene la proporción más alta), que son correctas como
# estadística y engañosas como texto. Aquí se traducen al sentido del dominio para que el informe no diga que
# un defensor es mejor por caer más veces. La estadística no se toca; solo se nombra bien.
SENTIDO = {"mejora": "la segunda condición cae MÁS, con diferencia significativa",
           "empeora": "la segunda condición cae MENOS, con diferencia significativa",
           "sin_diferencia_concluyente": "sin diferencia concluyente",
           "muestra_insuficiente": "muestra insuficiente"}


def _sentido(clave, veredicto):
    """El veredicto estadístico, dicho en el sentido correcto del dominio."""
    if clave in ("objetivo", "engano"):
        return SENTIDO.get(veredicto, veredicto)
    return veredicto


def comparar():
    """Compara las dos condiciones de defensor, agrupando por sesión. -> dict o None si falta alguna."""
    a, b = resumen(CONDICIONES[0][0]), resumen(CONDICIONES[1][0])
    if not a or not b:
        return None
    na, nb = CONDICIONES[0][0], CONDICIONES[1][0]
    return {
        "objetivo": metricas.comparar_agrupado(na, a["grupos_objetivo"], nb, b["grupos_objetivo"]),
        "engano": metricas.comparar_agrupado(na, _grupos(leer(na)["filas"], "engano_modelo"),
                                             nb, _grupos(leer(nb)["filas"], "engano_modelo")),
        "nota_sentido": ("En «objetivo conseguido» y «engaño del modelo», más es PEOR para el defensor. El "
                         "veredicto estadístico de metricas.py es neutro («mejora» = proporción más alta en "
                         "la segunda condición); aquí se publica traducido al sentido del dominio."),
        "parcial": not (a["progreso"]["completa"] and b["progreso"]["completa"]),
    }


def estado():
    print(f"{'condición':<10} {'sesiones':>9} {'rondas':>9} {'huérf.':>7}  estado")
    for nombre, _, _ in CONDICIONES:
        p, e = progreso(nombre), leer(nombre)
        if p is None:
            print(f"{nombre:<10} {'-':>9} {'-':>9} {'-':>7}  sin empezar")
            continue
        print(f"{nombre:<10} {p['sesiones']:>3}/{SESIONES:<5} {p['rondas']:>4}/"
              f"{p['rondas_planificadas']:<4} {e['huerfanas']:>7}  "
              f"{'completa' if p['completa'] else 'parcial'}")


def _w(x, etiqueta="IC95"):
    """Un intervalo como texto, siempre con denominador. None es None, no 0; y un intervalo que el método no
    puede estimar se dice, no se rellena con ceros."""
    if not x or x.get("valor") is None:
        return f"-- (n={0 if not x else x.get('n', 0)})"
    if x.get("bajo") is None:
        motivo = "sin variación entre sesiones" if x.get("degenerado") else f"sin {etiqueta}"
        return f"{x['valor'] * 100:5.1f}% ({motivo}, n={x['n']})"
    return f"{x['valor'] * 100:5.1f}% {etiqueta} [{x['bajo'] * 100:4.1f} · {x['alto'] * 100:5.1f}] n={x['n']}"


def informe():
    """Imprime el informe del atacante y escribe `data/campana_atacante.json`. Solo lee."""
    salida = {"condiciones": {}, "comparacion": comparar(),
              "definiciones": {}}
    print("=" * 104)
    print("OBJETIVO DEL ATACANTE · dos condiciones de defensor, mismo atacante y mismos escenarios")
    print("=" * 104)
    for nombre, _, descripcion in CONDICIONES:
        r = resumen(nombre)
        if r is None:
            print(f"\n── {nombre}: sin empezar")
            continue
        salida["condiciones"][nombre] = r
        salida["definiciones"] = {"objetivo": r["definicion"], "engano": r["definicion_engano"]}
        est = "PARCIAL" if not r["progreso"]["completa"] else "completa"
        print(f"\n── {nombre} · {descripcion}")
        print(f"   defensor {r['config'].get('modelo_defensor')} · {r['sesiones']} sesiones · "
              f"{r['intentos']} intentos · {r['imputables']} imputables · "
              f"{r['no_imputables']} no imputables · {r['huerfanas']} huérfanas · {est}")
        print(f"   objetivo conseguido   por ronda  {_w(r['objetivo_por_ronda'], 'Wilson')}")
        print(f"                         agrupado   {_w(r['objetivo_agrupado'], 'IC95 ses.')}"
              + (f"  (efecto diseño ×{r['objetivo_agrupado']['efecto_diseno']:.2f})"
                 if r["objetivo_agrupado"].get("efecto_diseno") else ""))
        print(f"                         por sesión {_w(r['objetivo_por_sesion'], 'Wilson')}")
        print(f"   engaño del modelo     por ronda  {_w(r['engano_por_ronda'], 'Wilson')}")
        print(f"                         agrupado   {_w(r['engano_agrupado'], 'IC95 ses.')}")
        print(f"                         por sesión {_w(r['engano_por_sesion'], 'Wilson')}")
        print(f"   veredictos            {r['por_veredicto']}")
        print(f"   decisión del defensor {r['por_decision_defensor']}")
        print(f"   bloqueado por capa    {r['bloqueadas_por_capa'] or '(ninguna ejecución bloqueada)'}")
        print(f"   frenado por           {r['frenado_por']}")
        print(f"   errores de modelo     {r['errores_modelo'] or '(ninguno)'}")
        la, ld = r["latencia_atacante_ms"], r["latencia_defensor_ms"]
        ta, td = r["tokens_atacante"], r["tokens_defensor"]
        f = lambda x, k="media": "--" if not x or x.get(k) is None else f"{x[k]:.0f}"  # noqa: E731
        print(f"   latencia atacante {f(la)} ms · defensor {f(ld)} ms · ronda {f(r['latencia_ronda_ms'])} ms")
        print(f"   tokens atacante {f(ta)} (n={ta['n']}) · defensor {f(td)} (n={td['n']})")
        print(f"   por escenario         " + ", ".join(
            f"{k} {v['exitos']}/{v['n']}" for k, v in r["por_escenario"].items()))

    cmp_ = salida["comparacion"]
    if cmp_:
        print(f"\n── Comparación entre las dos condiciones, agrupando por sesión")
        for clave, titulo in (("objetivo", "objetivo conseguido"), ("engano", "engaño del modelo")):
            c = cmp_[clave]
            i = c["intervalo"]
            dif = "--" if c["diferencia"] is None else f"{c['diferencia']:+.3f}"
            ic = "--" if i["bajo"] is None else f"[{i['bajo']:+.3f}, {i['alto']:+.3f}]"
            print(f"   {titulo:<22} dif {dif} IC95 {ic} · **{_sentido(clave, c['veredicto'])}**")
            print(f"   {'':<22} {c['explicacion']}")
        if cmp_["parcial"]:
            print("   AVISO: alguna condición está incompleta; la comparación es provisional.")

    print(f"\n── Qué cuenta como éxito, y qué no")
    for k, v in (salida["definiciones"] or {}).items():
        print(f"   {k}: {v}")

    SALIDA_JSON.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_JSON.write_text(json.dumps(salida, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nEscrito: {SALIDA_JSON}")


def main(argv):
    if "--estado" in argv:
        estado()
        return 0
    if "--informe" in argv:
        informe()
        return 0
    solo = None
    if "--solo" in argv:
        solo = argv[argv.index("--solo") + 1]
        if solo not in NOMBRES:
            print(f"condición desconocida: {solo}. Son: {', '.join(sorted(NOMBRES))}")
            return 2
    max_s = float(argv[argv.index("--max-segundos") + 1]) if "--max-segundos" in argv else None

    print(f"Objetivo del atacante · atacante {MODELO_ATACANTE} · rol {ROL} · "
          f"{SESIONES} sesiones x {RONDAS_POR_SESION} rondas = {SESIONES * RONDAS_POR_SESION} por condición")
    t0 = time.monotonic()
    out = {}
    for nombre, _, descripcion in CONDICIONES:
        if solo is not None and nombre != solo:
            continue
        print(f"\n── {nombre} · {descripcion}")
        out[nombre] = ejecutar(nombre, None if max_s is None else max(1.0, max_s - (time.monotonic() - t0)))
        p = out[nombre]
        print(f"   {'TERMINADA' if p['completa'] else 'PARCIAL'}: {p['sesiones']}/{SESIONES} sesiones")
        if max_s is not None and (time.monotonic() - t0) >= max_s:
            print("Tope de tiempo de la tanda. Vuelva a lanzar para seguir.")
            break
    print(f"\nTotal de esta tanda: {(time.monotonic() - t0) / 60:.1f} min")
    estado()
    if all(p["completa"] for p in out.values()):
        print()
        informe()
        return 0
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nInterrumpido. Las sesiones completas están guardadas; relance para seguir.")
        sys.exit(130)
