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

    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
