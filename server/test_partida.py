"""Pruebas de la lógica de sesiones y partida (sin HTTP), con un reloj simulado. Ejecutar: python server/test_partida.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import partida as pt  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def lanza(fn, status):
    try:
        fn()
    except pt.ErrorSesion as e:
        return e.status == status
    return False


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def main():
    reloj = Reloj()
    sala = pt.Sala("123456", reloj=reloj)

    # --- unirse ---
    ana = sala.unirse("Ana", "azul")
    chk("unirse da un token propio y el rol del equipo", ana.token and ana.rol == "jugador" and ana.equipo == "azul")
    beto = sala.unirse("Beto", "azul")
    chk("varios participantes por equipo, cada uno con su token", beto.token != ana.token
        and len(sala.participantes("azul")) == 2)
    chk("nombre repetido (sin distinguir mayúsculas) -> 409", lanza(lambda: sala.unirse("ana", "rojo"), 409))
    chk("los espacios sobrantes no evitan la repetición", lanza(lambda: sala.unirse("  Ana  ", "rojo"), 409))
    chk("nombre demasiado corto -> 400", lanza(lambda: sala.unirse("A", "rojo"), 400))
    chk("nombre con caracteres raros -> 400", lanza(lambda: sala.unirse("<script>", "rojo"), 400))
    chk("equipo inventado -> 400", lanza(lambda: sala.unirse("Carla", "morado"), 400))
    chk("el público no incluye el token", "token" not in ana.publico())
    chk("por_token encuentra al participante", sala.por_token(beto.token) is beto)
    chk("token falso o vacío -> None", sala.por_token("falso") is None and sala.por_token(None) is None)
    esp = sala.unirse("Público 1", "espectador")
    chk("espectador con rol espectador", esp.rol == "espectador")

    # --- árbitro ---
    chk("árbitro sin código -> 403", lanza(lambda: sala.unirse("Juez", "general"), 403))
    chk("árbitro con código erróneo -> 403", lanza(lambda: sala.unirse("Juez", "general", "000000", "pc1"), 403))
    arb = sala.unirse("Juez", "general", " 123456 ", "pc1")
    chk("árbitro con el código correcto", arb.rol == "arbitro")
    for _ in range(pt.INTENTOS_ARBITRO):
        lanza(lambda: sala.unirse("Intruso", "general", "999999", "pc2"), 403)
    chk(f"tras {pt.INTENTOS_ARBITRO} códigos erróneos el cliente queda bloqueado (429), aun con el correcto",
        lanza(lambda: sala.unirse("Intruso", "general", "123456", "pc2"), 429))
    chk("el bloqueo es por cliente", sala.unirse("Juez 2", "general", "123456", "pc3").rol == "arbitro")
    reloj.t += pt.BLOQUEO_ARBITRO_S + 1
    chk("el bloqueo caduca", sala.unirse("Intruso", "general", "123456", "pc2").rol == "arbitro")

    # --- partida ---
    p = pt.Partida(reloj=reloj)
    chk("empieza en preparación", p.fase == "preparacion" and p.restante_s() is None)
    chk("finalizar antes de iniciar -> 409", lanza(lambda: p.finalizar("arbitro"), 409))
    chk("duración no permitida -> 400", lanza(lambda: p.iniciar(7), 400))
    p.iniciar(5)
    chk("iniciar: en curso con 300 s", p.fase == "en_curso" and p.restante_s() == 300 and p.inicio)
    chk("iniciar dos veces -> 409", lanza(lambda: p.iniciar(5), 409))
    reloj.t += 120
    chk("el restante lo cuenta el reloj del servidor", p.restante_s() == 180 and not p.vencida())
    chk("transcurrido para los plazos de las misiones", p.transcurrido_s() == 120
        and pt.Partida(reloj=reloj).transcurrido_s() is None)
    reloj.t += 181
    chk("vence al agotarse el tiempo", p.vencida() and p.restante_s() == 0)
    p.finalizar("tiempo")
    chk("finalizada por tiempo", p.fase == "finalizada" and p.motivo_fin == "tiempo" and p.fin and p.restante_s() == 0)
    chk("finalizar dos veces -> 409", lanza(lambda: p.finalizar("arbitro"), 409))
    chk("ya no está vencida (no se vuelve a cerrar)", not p.vencida())
    chk("cada partida tiene su propio id", len({pt.Partida(reloj=reloj).id for _ in range(20)}) == 20)
    pub = p.publico()
    chk("el estado público tiene fase, duración y restante", {"id", "fase", "duracion_s", "restante_s", "inicio", "fin",
                                                             "motivo_fin"} <= set(pub))

    # ══ Autenticación por persona y protección de sesiones (Fase H) ═══════════════════════════════════════
    reloj = {"t": 1000.0}
    s = pt.Sala("CODIGO-ARBITRO", reloj=lambda: reloj["t"])

    a = s.unirse("Ana", "azul", clave="clave-personal-1")
    chk("quien entra con clave queda autenticado", a.autenticado is True)
    chk("y se dice en su ficha pública", a.publico()["autenticado"] is True)
    chk("la ficha pública nunca trae el token, la sal ni el derivado",
        not ({"token", "sal", "derivado"} & set(a.publico())))
    chk("la clave no se guarda en claro",
        a.derivado is not None and b"clave-personal-1" not in (a.derivado or b""))
    chk("cada persona tiene su propia sal",
        s.unirse("Bea", "azul", clave="clave-personal-2").sal != a.sal)

    # Reautenticación: mismo nombre, otra sesión.
    t_viejo = a.token
    a2 = s.unirse("Ana", "azul", clave="clave-personal-1")
    chk("con la clave correcta se puede volver a entrar con el mismo nombre", a2.id == a.id)
    chk("el token se rota al volver a entrar", a2.token != t_viejo)
    chk("y el token anterior deja de valer inmediatamente", s.por_token(t_viejo) is None)
    chk("el nuevo sí vale", s.por_token(a2.token) is a2)
    chk("se cuenta cuántas veces ha entrado", a2.sesiones == 2)
    chk("no se duplica el participante", len([p for p in s.participantes() if p.nombre == "Ana"]) == 1)

    chk("con la clave equivocada no se entra", lanza(lambda: s.unirse("Ana", "azul", clave="otra-clave-xx"), 403))
    chk("y el token bueno sigue valiendo", s.por_token(a2.token) is a2)
    chk("sin clave tampoco se entra a un nombre con clave",
        lanza(lambda: s.unirse("Ana", "azul"), 403))
    chk("ni cambiando de equipo",
        lanza(lambda: s.unirse("Ana", "rojo", clave="clave-personal-1"), 409))

    # Sin clave: el comportamiento anterior no cambia.
    c = s.unirse("Caro", "rojo")
    chk("sin clave se sigue pudiendo entrar", c.token and c.autenticado is False)
    chk("pero el nombre no queda reservado: se rechaza el duplicado",
        lanza(lambda: s.unirse("Caro", "rojo"), 409))
    chk("y tampoco se puede reclamar con una clave inventada",
        lanza(lambda: s.unirse("caro", "rojo", clave="clave-inventada"), 409))

    # Longitud de la clave
    chk("una clave demasiado corta se rechaza",
        lanza(lambda: s.unirse("Dani", "azul", clave="x" * (pt.CLAVE_MINIMA - 1)), 400))
    chk("una clave absurdamente larga también",
        lanza(lambda: s.unirse("Dani", "azul", clave="x" * (pt.CLAVE_MAXIMA + 1)), 400))
    chk("una clave justo en el mínimo vale",
        s.unirse("Dani", "azul", clave="x" * pt.CLAVE_MINIMA).autenticado is True)

    # Límite de intentos: una clave no se puede probar a fuerza bruta.
    s2 = pt.Sala("CODIGO", reloj=lambda: reloj["t"])
    s2.unirse("Eva", "azul", clave="clave-de-eva-1")
    for _ in range(pt.INTENTOS_CLAVE):
        lanza(lambda: s2.unirse("Eva", "azul", clave="mal-mal-mal"), 403)
    chk("tras varios fallos, el cliente queda bloqueado un rato",
        lanza(lambda: s2.unirse("Eva", "azul", clave="clave-de-eva-1"), 429))
    reloj["t"] += pt.BLOQUEO_CLAVE_S + 1
    chk("pasado el bloqueo, la clave correcta vuelve a funcionar",
        s2.unirse("Eva", "azul", clave="clave-de-eva-1").autenticado is True)

    # Caducidad por inactividad
    reloj["t"] = 5000.0
    s3 = pt.Sala("CODIGO", reloj=lambda: reloj["t"])
    viva = s3.unirse("Viva", "azul", clave="clave-de-viva")
    quieta = s3.unirse("Quieta", "rojo")
    chk("nada caduca recién entrado", s3.caducar() == [])
    reloj["t"] += pt.INACTIVIDAD_S - 10
    s3.por_token(viva.token)                     # actividad: esta sesión se refresca
    reloj["t"] += 20
    caducados = s3.caducar()
    chk("la sesión sin actividad caduca", caducados == ["Quieta"])
    chk("y la que se usó, no", s3.por_token(viva.token) is viva)
    chk("una sesión caducada ya no vale", s3.por_token(quieta.token) is None)
    chk("su nombre queda libre", s3.unirse("Quieta", "rojo").token != quieta.token)
    chk("quien tenía clave puede volver tras caducar",
        s3.caducar(0) is not None and s3.unirse("Viva", "azul", clave="clave-de-viva").autenticado)
    chk("por_token(tocar=False) no refresca la actividad",
        (lambda p: (s3.por_token(p.token, tocar=False), p.ultima_actividad)[1])(
            s3.unirse("Fugaz", "rojo")) > 0)

    # Cerrar sesión
    s4 = pt.Sala("CODIGO", reloj=lambda: reloj["t"])
    g = s4.unirse("Gus", "rojo")
    chk("cerrar la sesión devuelve el nombre", s4.cerrar_sesion(g.token) == "Gus")
    chk("y el token deja de valer al instante", s4.por_token(g.token) is None)
    chk("cerrar con un token que no vale no hace nada", s4.cerrar_sesion("inventado") is None)
    chk("cerrar sin token tampoco", s4.cerrar_sesion(None) is None)
    h = s4.unirse("Hugo", "azul", clave="clave-de-hugo")
    s4.cerrar_sesion(h.token)
    chk("quien tenía clave puede volver a entrar tras cerrar sesión",
        s4.unirse("Hugo", "azul", clave="clave-de-hugo").autenticado is True)

    # El código de árbitro sigue siendo obligatorio y limitado
    s5 = pt.Sala("SECRETO-ARBITRO", reloj=lambda: reloj["t"])
    chk("sin código no se entra como árbitro", lanza(lambda: s5.unirse("Juez", "general"), 403))
    chk("con el código correcto sí",
        s5.unirse("Juez", "general", codigo="SECRETO-ARBITRO").rol == "arbitro")
    chk("el árbitro también puede tener clave personal",
        s5.unirse("Juez2", "general", codigo="SECRETO-ARBITRO", clave="clave-del-juez").autenticado)

    # derivar() es determinista y depende de la sal
    sal = b"0123456789abcdef"
    chk("el derivado es determinista", pt.derivar("x" * 10, sal) == pt.derivar("x" * 10, sal))
    chk("y cambia con la sal", pt.derivar("x" * 10, sal) != pt.derivar("x" * 10, b"otra-sal-distint"))
    chk("y con la clave", pt.derivar("x" * 10, sal) != pt.derivar("y" * 10, sal))
    chk("comprueba() es False sin clave configurada",
        pt.Participante(id="1", nombre="n", equipo="rojo", token="t").comprueba("lo que sea") is False)
    chk("comprueba() es False con clave vacía", a2.comprueba("") is False and a2.comprueba(None) is False)

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
