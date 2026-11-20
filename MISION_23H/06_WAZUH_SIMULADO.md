# 06 — WAZUH SIMULADO

## Principio de honestidad
Todo lo de este archivo es **simulación**. En código, UI, logs, informes y capturas debe aparecer siempre la etiqueta **"WAZUH SIMULADO"**. Jamás se presenta como Wazuh real. Si en la máquina existiera una instancia real, se distingue como modo distinto (`real` / `simulado` / `desconectado` / `con_errores`); este último estado debe ser visible en la UI.

## Arquitectura
Módulo `src/lab/wazuh_sim/` (o equivalente al estilo del repo):
- `WazuhProvider` (interfaz): `listar_agentes()`, `consultar_alertas(partida_id, desde, nivel_min, grupos)`, `estado()`.
- `SimProvider`: implementación local alimentada por los eventos del motor.
- `RealProvider`: **solo contrato + stub** que lee `WAZUH_URL`/credenciales de variables de entorno; sus pruebas se **omiten** (`skip`) si no hay instancia. No inventes respuestas reales.

## Modelo de datos
- **Agentes ficticios** (p. ej. `srv-correo`, `srv-rrhh`, `ws-contabilidad-01`, `srv-bd`) con id, nombre, IP privada ficticia, SO, grupo.
- **Alertas** con esquema compatible con Wazuh: `id` único, `timestamp` ISO 8601 con zona, `rule{id,level,description,groups,mitre{id,tactic,technique}}`, `agent{id,name,ip}`, `manager{name}`, `decoder{name}`, `location`, `full_log`, `data{...}` y un campo propio `lab{partida_id,turno,simulado:true}`.
- Persistencia: `data/wazuh_sim/alerts.ndjson` (append-only) + tabla indexada por `partida_id`. Sin duplicados (idempotencia por `id` determinista = hash de partida+turno+regla+evento).

## Reglas simuladas (conjunto propio, ids 100000+)
Mapea eventos del motor a alertas con niveles 0–15, p. ej.: intento de solicitud con identidad inconsistente, acceso denegado por permisos, aprobación en zona delegada, patrón repetido de intentos, clic en enlace de entrenamiento, PDF abierto, escalada de privilegios intentada, cambio de campo protegido, contención ejecutada. Incluye **MITRE ATT&CK de referencia** (p. ej. T1566 phishing, T1078 cuentas válidas, T1548 abuso de mecanismos de elevación) solo como etiqueta educativa.

## Ruido y señal (importante para métricas honestas)
El generador añade **alertas de fondo benignas y de bajo nivel** con semilla (≈ 3–6 por cada alerta relevante) para que detectar no sea trivial. Cada alerta guarda `relevante: true|false` en un canal oculto del motor (verdad de fondo), nunca visible para el modelo.

## Integración
- **Azul** recibe un resumen de alertas recientes de su partida como parte del contexto de cada turno (herramienta `consultar_alertas` limitada por presupuesto) y puede usarlas para decidir/contener. La alerta nunca prueba por sí sola que una solicitud sea maliciosa.
- **Rojo no ve Wazuh.**
- **Espectador/General** ven el panel Wazuh en solo lectura.
- Eventos de Harness, misiones, contención y resultado se correlacionan por `partida_id` y marca temporal.
- Métricas: tasa de detección (alertas relevantes atendidas), falsos positivos (contenciones sobre ruido), latencia de reacción en turnos.

## UI
Ventana "Wazuh (simulado)": estado del proveedor, agentes, línea de tiempo de alertas, filtros por nivel/grupo/agente, detalle JSON de una alerta, badge permanente "SIMULADO". Cargando / vacío / error resueltos (archivo 07).

## Pruebas
Esquema válido; idempotencia (reinyectar el mismo evento no duplica); correlación por partida; ruido presente y reproducible con semilla; `RealProvider` omitido sin instancia; UI muestra "SIMULADO"; el Rojo no recibe alertas en su contexto.
