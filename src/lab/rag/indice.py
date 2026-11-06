"""Índice y recuperación. Solo stdlib.

Por qué no hay ChromaDB ni FAISS: el corpus son decenas de fragmentos cortos. Una base vectorial añadiría
cientos de MB de dependencias, un proceso más y un formato binario que mantener, a cambio de nada medible a
esta escala. El índice es BM25 (léxico, determinista, sin red) con **embeddings opcionales** servidos por
Ollama. La interfaz es la misma en los dos casos, así que cambiar de motor más adelante es sustituir este
archivo, no tocar quien lo use.

Si se piden embeddings y Ollama no responde, **se dice** (`modo: "bm25 (embeddings no disponibles)"`) y se
recupera igual con BM25. Nunca se simula un vector ni se inventa una similitud.
"""
import json
import math
import re
import time
import unicodedata
from pathlib import Path

from .. import cliente_ollama
from . import corpus

RUTA_INDICE = Path(__file__).resolve().parents[3] / "data" / "rag_indice.json"
MODELO_EMBEDDINGS = "nomic-embed-text"
MAX_CARACTERES = 700        # tamaño objetivo de un fragmento
K_POR_DEFECTO = 3
UMBRAL_POR_DEFECTO = 0.12   # similitud mínima normalizada (0-1) para que un fragmento entre en el prompt

# Palabras vacías del español que no aportan a la recuperación.
VACIAS = frozenset("""a al algo alguna algunas alguno algunos ante antes aquel aquella aquellas aquello aquellos
aqui asi aun aunque bajo bien cada como con contra cual cuales cuando de del desde donde dos e el ella ellas
ello ellos en entre era eran es esa esas ese eso esos esta estan estas este esto estos fue fueron ha hace hacia
han hasta hay la las le les lo los mas me mi mientras mucho muy nada ni no nos nuestra nuestro o os otra otras
otro otros para pero poco por porque que quien quienes se sea segun ser si sin sobre son su sus tal tambien
tan tanto te tiene tienen toda todas todo todos tu tus un una unas uno unos y ya""".split())


def normalizar(texto):
    """Minúsculas sin tildes: «AUTORIZACIÓN» y «autorizacion» deben casar."""
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def tokenizar(texto):
    return [p for p in re.findall(r"[a-z0-9_]+", normalizar(texto)) if len(p) > 2 and p not in VACIAS]


def trocear(documento, max_caracteres=MAX_CARACTERES):
    """Trocea por párrafos, uniendo los cortos hasta `max_caracteres`. Conserva siempre el origen.

    Nunca parte una palabra ni mezcla dos documentos: un fragmento pertenece a un único documento."""
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", documento["texto"]) if p.strip()]
    if not parrafos:
        return []
    trozos, actual = [], ""
    for p in parrafos:
        while len(p) > max_caracteres:   # un párrafo enorme se parte por el último punto que quepa
            corte = p.rfind(". ", 0, max_caracteres)
            corte = corte + 1 if corte > max_caracteres // 3 else max_caracteres
            trozos.append(p[:corte].strip())
            p = p[corte:].strip()
        if actual and len(actual) + len(p) + 1 > max_caracteres:
            trozos.append(actual)
            actual = p
        else:
            actual = f"{actual}\n{p}" if actual else p
    if actual:
        trozos.append(actual)
    return [{"id": f"{documento['id']}#{i}", "doc": documento["id"], "titulo": documento["titulo"],
             "fuente": documento["fuente"], "etiquetas": list(documento["etiquetas"]), "texto": t}
            for i, t in enumerate(trozos)]


def _coseno(a, b):
    if not a or not b or len(a) != len(b):
        return None
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return None
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def embeber(host, textos, modelo=MODELO_EMBEDDINGS, timeout=30):
    """Pide embeddings a Ollama. -> (lista de vectores | None, error). Nunca lanza, nunca inventa un vector."""
    vectores = []
    for t in textos:
        try:
            cuerpo = json.dumps({"model": modelo, "prompt": t}).encode("utf-8")
            with cliente_ollama._abrir(host.rstrip("/") + "/api/embeddings", timeout, data=cuerpo) as r:
                if r.status != 200:
                    return None, f"HTTP {r.status}"
                v = json.loads(r.read().decode("utf-8")).get("embedding")
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"
        if not isinstance(v, list) or not v:
            return None, "respuesta sin embedding"
        vectores.append([float(x) for x in v])
    return vectores, None


class Indice:
    """Índice BM25 sobre los fragmentos del corpus, con embeddings opcionales."""

    K1, B = 1.5, 0.75

    def __init__(self, fragmentos, vectores=None, modelo_embeddings=None, construido=None):
        self.fragmentos = list(fragmentos)
        self.vectores = vectores
        self.modelo_embeddings = modelo_embeddings
        self.construido = construido or time.strftime("%Y-%m-%dT%H:%M:%S")
        self._tokens = [tokenizar(f["texto"] + " " + f["titulo"]) for f in self.fragmentos]
        self._largo = [len(t) for t in self._tokens]
        self._medio = (sum(self._largo) / len(self._largo)) if self._largo else 0.0
        self._frec = [{} for _ in self._tokens]
        docf = {}
        for i, toks in enumerate(self._tokens):
            for t in toks:
                self._frec[i][t] = self._frec[i].get(t, 0) + 1
            for t in set(toks):
                docf[t] = docf.get(t, 0) + 1
        n = max(1, len(self._tokens))
        self._idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in docf.items()}

    # ── BM25 ───────────────────────────────────────────────────────────────────────────────────────────────
    def _bm25(self, consulta):
        q = tokenizar(consulta)
        if not q or not self._tokens:
            return [0.0] * len(self._tokens)
        out = []
        for i, frec in enumerate(self._frec):
            s = 0.0
            for t in q:
                f = frec.get(t)
                if not f:
                    continue
                denom = f + self.K1 * (1 - self.B + self.B * (self._largo[i] / (self._medio or 1)))
                s += self._idf.get(t, 0.0) * (f * (self.K1 + 1)) / denom
            out.append(s)
        return out

    def recuperar(self, consulta, k=K_POR_DEFECTO, umbral=UMBRAL_POR_DEFECTO, host=None):
        """-> {fragmentos, modo, ms, consultados, descartados_por_umbral, error}.

        La puntuación se normaliza a 0-1 dividiendo por la mejor de la consulta, de modo que el umbral es
        «cómo de bueno es este fragmento comparado con el mejor», no un valor absoluto que dependa del corpus.
        Con embeddings disponibles la puntuación es el coseno (ya en 0-1 para vectores no negativos)."""
        t0 = time.perf_counter()
        modo, error = "bm25", None
        puntos = self._bm25(consulta)
        if host and self.vectores:
            vs, err = embeber(host, [consulta], self.modelo_embeddings or MODELO_EMBEDDINGS)
            if vs:
                cos = [_coseno(vs[0], v) for v in self.vectores]
                if all(c is not None for c in cos):
                    puntos, modo = [max(0.0, c) for c in cos], f"embeddings:{self.modelo_embeddings}"
                else:
                    modo, error = "bm25 (dimensión de vectores incompatible)", "dimension"
            else:
                modo, error = "bm25 (embeddings no disponibles)", err
        mejor = max(puntos, default=0.0)
        orden = sorted(range(len(puntos)), key=lambda i: -puntos[i])
        elegidos, descartados = [], 0
        for i in orden:
            rel = (puntos[i] / mejor) if mejor > 0 else 0.0
            if rel < umbral or puntos[i] <= 0:
                descartados += 1
                continue
            if len(elegidos) >= k:
                break
            elegidos.append({**self.fragmentos[i], "similitud": round(rel, 4),
                             "puntuacion": round(puntos[i], 4)})
        return {"fragmentos": elegidos, "modo": modo, "ms": int((time.perf_counter() - t0) * 1000),
                "consultados": len(self.fragmentos), "descartados_por_umbral": descartados, "error": error}

    # ── Persistencia ───────────────────────────────────────────────────────────────────────────────────────
    def a_json(self):
        return {"construido": self.construido, "modelo_embeddings": self.modelo_embeddings,
                "huella_corpus": huella_corpus(), "fragmentos": self.fragmentos, "vectores": self.vectores}

    @classmethod
    def desde_json(cls, datos):
        return cls(datos.get("fragmentos") or [], datos.get("vectores"),
                   datos.get("modelo_embeddings"), datos.get("construido"))


def huella_corpus():
    """Huella del corpus: si cambia, el índice guardado está obsoleto y hay que reconstruirlo."""
    import hashlib
    crudo = "\u0000".join(f"{d['id']}|{d['texto']}" for d in corpus.DOCUMENTOS)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:16]


def construir(host=None, modelo_embeddings=MODELO_EMBEDDINGS, max_caracteres=MAX_CARACTERES):
    """Trocea el corpus y, si se da `host`, intenta calcular embeddings. -> (Indice, error_embeddings|None)."""
    fragmentos = [t for d in corpus.documentos() for t in trocear(d, max_caracteres)]
    vectores, err = (None, None)
    if host:
        vectores, err = embeber(host, [f["texto"] for f in fragmentos], modelo_embeddings)
    return Indice(fragmentos, vectores, modelo_embeddings if vectores else None), err


def guardar(indice, ruta=RUTA_INDICE):
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(indice.a_json(), ensure_ascii=False), encoding="utf-8")
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def cargar(ruta=RUTA_INDICE):
    """-> (Indice | None, motivo). Un índice de un corpus distinto se descarta: nunca se usa desactualizado."""
    try:
        if not ruta.exists():
            return None, "no hay índice guardado"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    if datos.get("huella_corpus") != huella_corpus():
        return None, "el corpus cambió desde que se construyó el índice"
    return Indice.desde_json(datos), None
