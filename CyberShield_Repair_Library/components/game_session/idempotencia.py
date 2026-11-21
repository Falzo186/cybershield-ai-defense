"""Idempotencia de acciones (CyberShield Repair §12). Una misma acción repetida (doble clic, reintento del cliente, reinicio de la
interfaz) con la MISMA clave `Idempotency-Key` no se ejecuta dos veces: devuelve la respuesta de la primera.

La clave se ámbita por participante (token) + método + ruta, así que un participante no puede reutilizar la clave de otro ni
colisionar entre acciones distintas. Las respuestas se guardan un tiempo limitado (TTL) y el almacén tiene un tope de tamaño.
Solo se memorizan respuestas que NO son errores del servidor (5xx): un fallo transitorio sí se puede reintentar.
"""
import threading
import time


class AlmacenIdempotencia:
    def __init__(self, ttl_s=600, maximo=2000, reloj=time.monotonic):
        self.ttl_s, self.maximo, self._reloj = ttl_s, maximo, reloj
        self._d = {}
        self._c = threading.Lock()

    @staticmethod
    def clave(token, metodo, ruta, clave_cliente):
        return (token or "", metodo.upper(), ruta, str(clave_cliente))

    def obtener(self, k):
        """-> (status, cuerpo_bytes, tipo) o None."""
        with self._c:
            self._purgar()
            e = self._d.get(k)
            return e[1] if e else None

    def guardar(self, k, status, cuerpo, tipo="application/json"):
        if status >= 500:
            return False
        with self._c:
            self._purgar()
            if len(self._d) >= self.maximo:
                self._d.pop(next(iter(self._d)))
            self._d[k] = (self._reloj() + self.ttl_s, (status, cuerpo, tipo))
            return True

    def _purgar(self):
        ahora = self._reloj()
        for k in [k for k, (t, _) in self._d.items() if t < ahora]:
            self._d.pop(k, None)

    def __len__(self):
        return len(self._d)
