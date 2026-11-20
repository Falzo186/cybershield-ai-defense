# 01 — MISIÓN Y ALCANCE

## Qué es el proyecto
CyberShield AI Defense es un laboratorio académico, **100 % local y ficticio**, donde una IA Atacante (Equipo Rojo) y una IA Defensora (Equipo Azul), ambas modelos locales de ~8B parámetros vía Ollama, se enfrentan en escenarios empresariales simulados. Principio rector (no negociable):

> **La IA propone → el motor valida → los permisos autorizan → el repositorio ejecuta → la auditoría registra.**
> Ningún modelo se declara ganador por lo que dice. Gana quien alcanza sus objetivos en el **estado verificable** del escenario.

Ya existe en el repo (no reimplementar lo que funciona): capas deterministas (permisos/herramientas/repositorio con `set_authorizer`), equipos con tokens verificados, buzón/PDFs/misiones/marcador, motor de reglas evento→consecuencia, interfaz tipo escritorio con ventanas, E2E con Playwright, y — según el usuario — Harness, campañas del atacante (`campana_atacante.py`) y matrices de evaluación. **Audita primero qué hay realmente** (archivo 03).

## Lo que el usuario exige al terminar las 23 h
1. **Combate IA vs IA completo con modelos de 8B** reales (Rojo y Azul), ciclo de partida completo y reproducible.
2. **Ambos equipos pueden ganar** de forma legítima y verificable (archivo 04). Además hay empates y partidas inconclusas bien definidas.
3. **Simulación de Wazuh** integrada, claramente etiquetada como SIMULADA (archivo 06).
4. **Interfaz de usuario impecable** (archivo 07).
5. **Lo más completo posible**: campañas de evaluación reales, métricas honestas, pruebas, documentación y guion de demo.

## Definición de terminado (checklist verificable)
- [ ] Una partida completa (crear → elegir modelos 8B → ejecutar → ganador → historial) se puede lanzar desde la UI y desde CLI.
- [ ] Existen y pasan pruebas que demuestran: victoria Roja, victoria Azul, empate, partida interrumpida, presupuesto agotado, modelo sin respuesta.
- [ ] Victoria determinada solo por el motor; ninguna pantalla muestra "victoria" antes del evento `partida.resultado` persistido.
- [ ] Wazuh simulado emite alertas con esquema compatible, correlacionadas por `partida_id`, visibles en UI y consumibles por el Azul; interfaz `WazuhProvider` lista para una instancia real (prueba condicional).
- [ ] Campañas reales con modelos 8B ejecutadas y guardadas, con métricas, IC y líneas base triviales.
- [ ] Defecto "campaña del atacante exit code 4" diagnosticado con causa verificada y corregido.
- [ ] UI revisada con capturas reales en 2 resoluciones, sin errores de consola, con estados de carga/vacío/error.
- [ ] Batería de pruebas completa en verde (o fallos documentados con causa).
- [ ] Documentación y `docs/INFORME_EJECUTIVO_FINAL.md` entregados.
- [ ] Todo commiteado localmente en `mision-23h`. Sin push.

## Fuera de alcance
Integración con una instancia Wazuh real (solo contrato + prueba condicional), despliegue en nube, pruebas contra sistemas reales, entrenamiento/fine-tuning de modelos, memoria persistente del atacante entre partidas (ver archivo 02).
