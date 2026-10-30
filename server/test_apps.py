"""Pruebas de la Fase B en el servidor: el catálogo de aplicaciones por permiso coincide con lo que permite cada ruta,
y Archivos, Seguridad, Recursos y Ayuda devuelven lo que deben a cada equipo. BD en memoria, sin Ollama.
Ejecutar: python server/test_apps.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

import app as srv  # noqa: E402
from src.lab import apps, repositorio  # noqa: E402

resultados = []


def chk(nombre, cond):
    resultados.append(bool(cond))
    print(("OK    " if cond else "FALLO ") + nombre)


def main():
    repositorio._DEFECTO = repositorio.abrir(":memory:")
    c = TestClient(srv.app)
    c.__enter__()
    H = lambda t: {"X-Equipo-Token": t} if t else {}  # noqa: E731
    unirse = lambda equipo, nombre, **x: c.post("/api/sesion", json={"nombre": nombre, "equipo": equipo, **x}).json()["token"]  # noqa: E731
    P = lambda ruta, tok, **j: c.post(ruta, json=j, headers=H(tok))  # noqa: E731
    tok = {"rojo": unirse("rojo", "Rita"), "azul": unirse("azul", "Beto", usuario="ana.perez"),
           "general": unirse("general", "Juez", codigo=srv.CODIGO_ARBITRO), "espectador": unirse("espectador", "Público"),
           None: None}

    # --- el catálogo es el que dice el servidor, según la SESIÓN (no lo que pida el cliente) ---
    for eq in ("rojo", "azul", "general", "espectador"):
        d = c.get("/api/apps", headers=H(tok[eq])).json()
        chk(f"/api/apps para {eq} = catálogo de {eq}", d["equipo"] == eq and d["apps"] == apps.catalogo(eq))
    chk("con sesión de Rojo, pedir el catálogo de General devuelve el de Rojo",
        c.get("/api/apps?equipo=general", headers=H(tok["rojo"])).json()["equipo"] == "rojo")
    chk("sin sesión, el catálogo pedido (es público) o el de espectador",
        c.get("/api/apps?equipo=azul").json()["equipo"] == "azul" and c.get("/api/apps").json()["equipo"] == "espectador")

    # --- matriz: cada ruta de lectura de una aplicación responde 200 si y solo si el catálogo da esa aplicación ---
    c.post("/api/partida/iniciar", json={"duracion_min": 10}, headers=H(tok["general"]))
    rutas = {"archivos": ["/api/archivos"], "seguridad": ["/api/seguridad"], "incidentes": ["/api/incidentes"],
             "misiones": ["/api/misiones"], "recursos": ["/api/recursos"], "ayuda": ["/api/ayuda"]}
    for app_id, lista in rutas.items():
        for ruta in lista:
            esperado = {eq: apps.permiso(app_id, eq) is not None for eq in tok}
            observado = {eq: c.get(ruta, headers=H(t)).status_code == 200 for eq, t in tok.items()}
            chk(f"{ruta}: acceso = catálogo de «{app_id}» para cada equipo (y sin sesión)", observado == esperado)
    # Correo: cada equipo con su ruta (Rojo envía y sigue su campaña; Azul tiene el buzón)
    chk("Correo: Rojo ve sus enviados y Azul su buzón; nadie más",
        [c.get("/api/correo/enviados", headers=H(t)).status_code == 200 for t in tok.values()] == [True, False, False, False, False]
        and [c.get("/api/buzon", headers=H(t)).status_code == 200 for t in tok.values()] == [False, True, False, False, False])
    r = c.get("/api/seguridad", headers=H(tok["rojo"]))
    chk("un 403 de aplicación dice cuál falta", r.status_code == 403 and "«Seguridad»" in r.json()["mensaje"])

    # --- Archivos ---
    nom = P("/api/correo", tok["rojo"], plantilla="recursos_humanos").json()  # trae el PDF de nómina
    sop = P("/api/correo", tok["rojo"], plantilla="soporte_tecnico").json()["id"]
    P("/api/evento", tok["azul"], tipo="pdf_abierto", recurso=f"correo:{nom['id']}")
    P("/api/evento", tok["azul"], tipo="pdf_reportado", recurso=f"correo:{nom['id']}")
    a = c.get("/api/archivos", headers=H(tok["azul"])).json()
    chk("Azul ve sus adjuntos recibidos (solo los correos con PDF) con su estado",
        [x["id"] for x in a["adjuntos"]] == [nom["id"]] and a["adjuntos"][0]["pdf_abierto"] and a["adjuntos"][0]["pdf_reportado"]
        and a["puede_actuar"] is True)
    g = c.get("/api/archivos", headers=H(tok["general"])).json()
    chk("General los ve igual, en solo lectura", g["adjuntos"] == a["adjuntos"] and g["puede_actuar"] is False)
    rr = c.get("/api/archivos", headers=H(tok["rojo"])).json()
    chk("Rojo ve el catálogo de adjuntos que puede enviar", rr["vista"] == "rojo"
        and {x["adjunto"]["id"] for x in rr["catalogo"]} >= {"recibo_nomina", "comprobante_envio"})
    chk("y si su adjunto se abrió, pero NUNCA si se reportó", rr["enviados"][0]["adjunto_abierto"] == 1
        and not any("reportado" in k for x in rr["enviados"] for k in x))

    # --- Seguridad: recomendaciones deterministas que cambian con el estado ---
    s = c.get("/api/seguridad", headers=H(tok["azul"])).json()
    chk("sin defensor IA configurado, Seguridad lo avisa", any("defensor IA no está configurado" in x["texto"]
                                                              for x in s["recomendaciones"]))
    enl = [y for y in c.get("/api/buzon", headers=H(tok["azul"])).json()["correos"] if y["id"] == sop][0]["enlace"]
    c.get(enl)
    c.post(enl + "/credenciales")
    s = c.get("/api/seguridad", headers=H(tok["azul"])).json()
    chk("credencial comprometida: primera recomendación, CRÍTICA", s["recomendaciones"][0]["nivel"] == "CRITICO"
        and s["credencial"]["estado"] == "comprometida")
    chk("el enlace clicado sin contener también aparece", any("sin contener" in x["texto"] for x in s["recomendaciones"]))
    chk("los controles cuentan lo aplicado", (s["controles"]["adjuntos_reportados"], s["controles"]["enlaces_clicados"]) == (1, 1))
    P("/api/credenciales/revocar", tok["azul"])
    P(f"/api/correo/{sop}/contener", tok["azul"])
    s = c.get("/api/seguridad", headers=H(tok["azul"])).json()
    chk("al revocar y contener, esas recomendaciones desaparecen",
        not any(x["nivel"] == "CRITICO" or "sin contener" in x["texto"] for x in s["recomendaciones"]))
    chk("General ve la misma Seguridad en solo lectura",
        c.get("/api/seguridad", headers=H(tok["general"])).json()["recomendaciones"] == s["recomendaciones"]
        and c.get("/api/seguridad", headers=H(tok["general"])).json()["puede_actuar"] is False)
    chk("y General no puede revocar (la acción sigue siendo de Azul)",
        P("/api/credenciales/revocar", tok["general"]).status_code == 403)

    # --- Recursos y Ayuda (públicos) ---
    rec = c.get("/api/recursos").json()
    chk("Recursos: matriz de acceso por rol", rec["recursos"] and set(rec["roles"]) == {"invitado", "empleado", "analista", "admin"})
    ay = c.get("/api/ayuda", headers=H(tok["rojo"])).json()
    chk("Ayuda según la sesión (Rojo), con sus aplicaciones", ay["equipo"] == "rojo"
        and [x["id"] for x in ay["apps"]] == [x["id"] for x in apps.catalogo("rojo")])
    c.__exit__(None, None, None)
    print(f"Total {sum(resultados)}/{len(resultados)}")
    return all(resultados)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
