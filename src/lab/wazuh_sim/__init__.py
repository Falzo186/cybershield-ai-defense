"""WAZUH SIMULADO — alertas con esquema compatible con Wazuh, generadas por el motor de combate.

TODO lo que sale de aquí es una SIMULACIÓN del laboratorio. No es Wazuh. Cada alerta lleva `lab.simulado=true`
y el proveedor declara su modo (`simulado`). Si algún día hay una instancia real, se usa `RealProvider`, que
aquí es solo contrato + stub: no inventa respuestas.

Piezas:
  * `WazuhProvider`  — interfaz: listar_agentes / consultar_alertas / estado.
  * `SimProvider`    — implementación local alimentada por los eventos del motor (reglas ids 100000+).
  * `RealProvider`   — contrato y stub; lee WAZUH_URL / credenciales de variables de entorno.

Honestidad de la medición: cada alerta tiene una verdad de fondo `relevante` (viene de una solicitud maliciosa o
no) que se guarda en un canal OCULTO (`verdad_de_fondo`) y que `consultar_alertas` nunca devuelve.
"""
from .proveedor import (AGENTES, MODOS, RealProvider, SimProvider, WazuhProvider, ETIQUETA)  # noqa: F401
from .reglas import REGLAS  # noqa: F401
