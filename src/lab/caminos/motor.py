"""Motor del modo Caminos. Reutiliza la auditoría con hash encadenado (`combate.store.Almacen`) y el Wazuh SIMULADO.

La IA propone una OPCIÓN del menú; el motor la valida (opción inválida = rechazada y contada), aplica las consecuencias deterministas del
grafo, audita cada paso con hash y declara el resultado UNA sola vez (`partida.resultado`, inmutable; después 409). El grafo se congela por
hash y se recomprueba en cada turno. Ningún modelo ve la validez de las credenciales; el Azul no ve el inventario del Rojo.

Procedencia (`tipo`): CAMINOS_IA si algún lado usa un modelo de lenguaje; CAMINOS_GUION si ambos lados son guiones o líneas base deterministas.
"""
import copy
import hashlib
from datetime import datetime

from ..combate.modelos import PROHIBIDO
from ..combate.store import Almacen
from . import grafo as G

INVENTARIO_ROJO = [{"id": "C-01", "etiqueta": "credencial de la gerente de operaciones"}, {"id": "C-07", "etiqueta": "credencial del administrador de respaldos"}]
MAX_INVALIDAS = 3
MAX_ERRORES_SEGUIDOS = 3


class ErrorCaminos(Exception):
    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status, self.mensaje = status, mensaje


def _iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def tipo_de(rojo, azul):
    return "CAMINOS_IA" if (getattr(rojo, "es_ia", False) or getattr(azul, "es_ia", False)) else "CAMINOS_GUION"


class PartidaCaminos:
    def __init__(self, grafo, rojo, azul, semilla=0, almacen=None, wazuh=None, partida_id=None, etiquetas=None):
        self._g = copy.deepcopy(grafo)
        self.hash_grafo = G.hash_grafo(self._g)
        self.rojo, self.azul, self.semilla, self.wazuh = rojo, azul, semilla, wazuh
        self.almacen = almacen or Almacen(":memory:")
        self.tipo = tipo_de(rojo, azul)
        nombres = (getattr(rojo, "nombre", "rojo"), getattr(azul, "nombre", "azul"))
        base = partida_id or "cam-" + hashlib.sha1(f"{self.hash_grafo}|{semilla}|{nombres[0]}|{nombres[1]}".encode()).hexdigest()[:10]
        self.id, n = base, 1
        while self.almacen.partida(self.id):
            n += 1
            self.id = f"{base}-{n}"
        self.estado, self.nodo, self.turno = {}, self._g["inicio"], 0
        self.historial, self.camino, self.invalidas, self.errores_seguidos = [], [], 0, 0
        self.resultado = None
        self.config = {"semilla": semilla, "rojo": nombres[0], "azul": nombres[1], "tipo": self.tipo, "dificultad": self._g["dificultad"],
                       "version_prompts": "c1", "parametros_rojo": getattr(rojo, "params", {}), "parametros_azul": getattr(azul, "params", {}),
                       "etiquetas": etiquetas or {}, "hash_grafo": self.hash_grafo}
        self.almacen.crear(self.id, self._g["id"], self.hash_grafo, self.config, _iso())
        self._ev(0, "partida.creada", {"grafo": self._g["id"], "hash_grafo": self.hash_grafo, "config": self.config, "version_grafo": self._g["version"], "tipo": self.tipo})

    # ── auditoría ────────────────────────────────────────────────────────────────────────────────────
    def _ev(self, turno, tipo, payload, wz=None):
        ts = _iso()
        info = self.almacen.añadir(self.id, turno, ts, tipo, payload)
        if wz and self.wazuh is not None:
            try:
                self.wazuh.alimentar({"partida_id": self.id, "turno": turno, "ts": ts, "id_evento": info["hash"][:16], **wz})
            except Exception as exc:  # noqa: BLE001 - un fallo del SIEM no puede tumbar la partida
                self.almacen.añadir(self.id, turno, _iso(), "wazuh.error", {"error": f"{type(exc).__name__}: {exc}"})
        return info

    def terminada(self):
        return self.resultado is not None

    # ── vistas (lo que cada lado puede ver) ──────────────────────────────────────────────────────────
    def _alertas_azul(self):
        if self.wazuh is None:
            return []
        al = self.wazuh.consultar_alertas(self.id, nivel_min=1, limite=0)
        rec = [a for a in al if a["lab"]["turno"] >= self.turno - 2][-8:]
        return [{"nivel": a["rule"]["level"], "agente": a["agent"]["name"], "descripcion": a["rule"]["description"]} for a in rec]

    def _registro_azul(self):
        confianza = 1 + (2 if self.estado.get("correo_clic") else 0)
        return f"Registro de identidades: nivel de confianza vigente de la identidad solicitante {confianza}/3."

    def ctx(self, lado=None):
        n = self._g["nodos"][self.nodo]
        lado = lado or n["actor"]
        opciones = [{"id": o["id"], "etiqueta": o["etiqueta"]} for o in n["opciones"]]
        base = {"turno": self.turno + 1, "max_turnos": self._g["max_turnos"], "opciones": opciones, "nodo": self.nodo, "dificultad": self._g["dificultad"]}
        if lado == "rojo":
            return {**base, "texto": n["texto_rojo"], "inventario": copy.deepcopy(INVENTARIO_ROJO), "historial": [h["rojo"] for h in self.historial if h["lado"] == "rojo"][-6:]}
        ctx = {**base, "texto": n["texto_azul"].replace("{{registro}}", self._registro_azul()), "alertas": self._alertas_azul(),
               "historial": [h["azul"] for h in self.historial if h["lado"] == "azul"][-6:]}
        if getattr(self.azul, "nombre", "") == "azul_registro":
            ctx["recomendada_registro"] = n["recomendada"]       # solo la línea base determinista lo recibe; la IA nunca
        return ctx

    # ── un paso ──────────────────────────────────────────────────────────────────────────────────────
    def _exigir_activa(self):
        if self.resultado is not None:
            raise ErrorCaminos(409, "La partida ya tiene resultado: no admite más acciones.")

    def paso(self):
        self._exigir_activa()
        if G.hash_grafo(self._g) != self.hash_grafo:
            return self._cerrar("ERROR_TECNICO", "el grafo congelado cambió durante la partida", None, causa="integridad")
        if self.turno >= self._g["max_turnos"]:
            return self._cerrar("INCONCLUSA", "se agotaron los turnos sin llegar a una hoja", None, causa="presupuesto")
        n = self._g["nodos"][self.nodo]
        actor = n["actor"]
        prov = self.rojo if actor == "rojo" else self.azul
        self.turno += 1
        self._aplicar(n.get("entrada"), self.turno)
        self._ev(self.turno, "turno.inicio", {"nodo": self.nodo, "actor": actor, "turno": self.turno})
        r = prov.decidir(self.ctx(actor))
        meta = r.get("meta") or {}
        if not r.get("ok"):
            self.errores_seguidos += 1
            self._ev(self.turno, "modelo.error", {"actor": actor, "modelo": meta.get("modelo") or getattr(prov, "nombre", "?"), "error": str(meta.get("error"))[:120]})
            if self.errores_seguidos >= MAX_ERRORES_SEGUIDOS:
                self._ev(self.turno, "harness.corte", {"motivo": "errores seguidos del modelo"})
                return self._cerrar("INCONCLUSA", f"el modelo de {actor} no respondió {MAX_ERRORES_SEGUIDOS} veces seguidas", None, causa="errores")
            self.turno -= 1       # el turno no se consumió: el nodo se reintenta
            self._tokens(meta)
            return None
        self.errores_seguidos = 0
        self._tokens(meta)
        op = r.get("opcion")
        opcion = next((o for o in n["opciones"] if o["id"] == op), None)
        if opcion is None:       # opción fuera del menú o respuesta malformada: NO es una acción
            self.invalidas += 1
            self._ev(self.turno, "opcion.invalida", {"actor": actor, "nodo": self.nodo, "recibida": str(r.get("invalida") or op)[:60], "cuenta": self.invalidas})
            self.turno -= 1
            if self.invalidas >= MAX_INVALIDAS:
                self._ev(self.turno, "harness.corte", {"motivo": "opciones inválidas repetidas"})
                return self._cerrar("INCONCLUSA", f"{actor} propuso {MAX_INVALIDAS} opciones fuera del menú", None, causa="invalidas")
            return None
        msg = r.get("mensaje") or ""
        if PROHIBIDO.search(msg):
            msg = "[mensaje filtrado]"
        self._ev(self.turno, "caminos.decision", {"actor": actor, "nodo": self.nodo, "opcion": opcion["id"], "etiqueta": opcion["etiqueta"], "mensaje": msg,
                                                  "proveedor": getattr(prov, "nombre", "?"), "modelo": meta.get("modelo")})
        self._aplicar(opcion.get("efectos"), self.turno, opcion)
        self.camino.append((self.nodo, opcion["id"]))
        self.historial.append({"lado": actor, "rojo": f"turno {self.turno}: elegiste «{opcion['etiqueta']}»", "azul": f"turno {self.turno}: decidiste «{opcion['etiqueta']}»"})
        siguiente = opcion["siguiente"]
        if siguiente in self._g["hojas"]:
            return self._hoja(self._g["hojas"][siguiente])
        self.nodo = siguiente
        return None

    def _tokens(self, meta):
        c = self.__dict__.setdefault("_cons", {"llamadas_modelo": 0, "tokens_entrada": 0, "tokens_salida": 0})
        c["llamadas_modelo"] += meta.get("llamadas", 0) if meta.get("modelo") else 0
        c["tokens_entrada"] += meta.get("tokens_entrada", 0)
        c["tokens_salida"] += meta.get("tokens", 0)

    def _aplicar(self, efectos, turno, opcion=None):
        if not efectos:
            return
        cambios = {}
        for k, v in efectos.get("set", {}).items():
            if k == "sesion_activa" and v is False and self.estado.get("sesion_activa"):
                self.estado["sesion_activa_previa"] = True
                cambios["sesion_activa_previa"] = True
            if self.estado.get(k) != v:
                self.estado[k] = v
                cambios[k] = v
        if cambios:
            self._ev(turno, "caminos.estado", {"cambios": cambios})
        clave = efectos.get("alerta")
        if clave:
            self._ev(turno, "caminos.alerta", {"clave": clave},
                     wz={"clave": clave, "agente": "srv-bd", "relevante": True, "data": {"nodo": self.nodo}, "full_log": f"{clave} partida={self.id}"})

    # ── fin ──────────────────────────────────────────────────────────────────────────────────────────
    def _hoja(self, h):
        faltan = [e for e in h["evidencia"] if not self.estado.get(e)]
        if faltan:   # la hoja exige evidencia de estado: sin ella no hay victoria de nadie
            return self._cerrar("ERROR_TECNICO", f"la hoja {h['id']} no tiene la evidencia exigida {faltan}", h, causa="sin_evidencia")
        if h["resultado"] == "VICTORIA_ROJA" and not self.estado.get("base_entregada"):
            return self._cerrar("ERROR_TECNICO", "victoria Roja sin base entregada", h, causa="sin_evidencia")
        return self._cerrar(h["resultado"], h["titulo"], h)

    def _cerrar(self, resultado, motivo, hoja, causa=None):
        self._exigir_activa()
        cons = getattr(self, "_cons", {"llamadas_modelo": 0, "tokens_entrada": 0, "tokens_salida": 0})
        res = {"resultado": resultado, "motivo": motivo, "causa": causa, "partida_id": self.id, "grafo": self._g["id"], "hash_grafo": self.hash_grafo, "tipo": self.tipo,
               "hoja": hoja["id"] if hoja else None, "reversion": bool(hoja and hoja.get("reversion")), "giro": bool(hoja and hoja.get("giro")),
               "ensena": hoja["ensena"] if hoja else None, "camino": [list(x) for x in self.camino], "turnos_jugados": self.turno,
               "evidencia": {e: bool(self.estado.get(e)) for e in (hoja["evidencia"] if hoja else [])}, "estado_final": dict(sorted(self.estado.items())),
               "base_integra": not self.estado.get("base_entregada"), "opciones_invalidas": self.invalidas, "consumo": dict(cons),
               "wazuh": {"alertas_relevantes": len(self.wazuh.alertas_relevantes(self.id)) if self.wazuh is not None else 0}}
        self.resultado = res
        self._ev(self.turno, "partida.resultado", res)
        self.almacen.cerrar(self.id, "finalizada", res, _iso())
        return res

    def jugar(self):
        while not self.terminada():
            self.paso()
        return self.resultado
