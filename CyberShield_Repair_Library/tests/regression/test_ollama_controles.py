"""Controles de la integración con Ollama (CyberShield Repair §9), contra el servidor real y un Ollama FALSO lento/caído.
 A. una respuesta TARDÍA no modifica una partida ya finalizada (el ataque a medias no cuenta);
 B. una inferencia en curso no se duplica y cada ataque queda asociado a una ronda con identificador;
 C. si Ollama se cae, el servidor responde con un error claro y la partida sigue utilizable (sin respuestas inventadas);
 D. no se inician inferencias al entrar/consultar pantallas (ya cubierto por la regresión 2).
Ejecutar: python CyberShield_Repair_Library/tests/regression/test_ollama_controles.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arnes import Entorno  # noqa: E402

R = []


def chk(n, c, d=""):
    R.append(bool(c))
    print(("OK    " if c else "FALLO ") + n + (f"  [{d}]" if d and not c else ""), flush=True)


def main():
    with Entorno(retardo_ollama=3.0) as E:
        adm, rojo, azul = E.unirse("Admin", "general"), E.unirse("Rojo1", "rojo"), E.unirse("Azul1", "azul")
        adm.post("/api/partida/iniciar", {"duracion_min": 5})
        d = azul.post("/api/ia/defensor", {"modelo": "falso-defensor", "host": E.url_ollama})
        chk("Azul fija su defensor contra el Ollama real (falso) del laboratorio", d.status == 200, f"{d.status} {d.datos}")
        # B · una inferencia en curso no se duplica y queda asociada a un ataque numerado
        a1 = rojo.post("/api/ia/ataque", {"modelo": "falso-atacante", "host": E.url_ollama})
        a2 = rojo.post("/api/ia/ataque", {"modelo": "falso-atacante", "host": E.url_ollama})
        est = adm.get("/api/ia/estado")
        chk("el ataque IA se acepta y el segundo, simultáneo, se rechaza (409)", a1.status == 200 and a2.status == 409, f"{a1.status},{a2.status}")
        chk("la inferencia en curso queda identificada (ataque número y fase)", bool(est.get("en_curso")), str(est.get("en_curso"))[:120])
        # A · respuesta tardía tras finalizar: no cuenta
        antes = adm.get("/api/ia/estado")
        fin = adm.post("/api/partida/finalizar")
        time.sleep(5)       # el Ollama falso tarda 3 s por llamada: la respuesta llega con la partida ya finalizada
        despues = adm.get("/api/ia/estado")
        puntos_antes, puntos_desp = antes.get("puntos"), despues.get("puntos")
        terminados = [x for x in despues.get("ataques", []) if x.get("resultado") not in (None, "cancelado")]
        chk("finalizar cancela la inferencia en curso y su respuesta tardía NO modifica el resultado ni los puntos",
            fin.status == 200 and puntos_antes == puntos_desp and not terminados and not despues.get("en_curso"), f"fin={fin.status}, puntos={puntos_antes}->{puntos_desp}, terminados={len(terminados)}")
        # C · Ollama caído: error claro, partida utilizable
        adm.post("/api/partida/nueva")
        adm.post("/api/partida/iniciar", {"duracion_min": 5})
        E.srv_ollama.shutdown()
        E.srv_ollama.server_close()
        caido = rojo.post("/api/ia/ataque", {"modelo": "falso-atacante", "host": E.url_ollama})
        chk("con Ollama caído el ataque se rechaza con un mensaje claro (sin simular una respuesta)", caido.status in (409, 503) and "disponible" in str(caido.datos).lower(), f"{caido.status} {caido.datos}")
        c = rojo.post("/api/correo", {"plantilla": "soporte_tecnico"})
        p = adm.get("/api/partida")
        chk("y la partida sigue en curso y utilizable (correo de Rojo funciona)", p["fase"] == "en_curso" and c.status == 200, f"{p['fase']},{c.status}")
        chk("tras el fallo no queda ninguna inferencia colgada", not adm.get("/api/ia/estado").get("en_curso"))
    print(f"\nTotal {sum(R)}/{len(R)}")
    return all(R)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(0 if main() else 1)
