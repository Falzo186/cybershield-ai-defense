# Guía de ejecución

## 1. Una partida desde la terminal
```powershell
# modelos falsos determinísticos (sin Ollama): demuestra el motor
python -m src.lab.combate.jugar --escenario verificacion_falsa-intermedio --rojo falso:objetivos --azul falso:aprobar
# modelos 8B reales (la primera llamada carga el modelo: 10–30 s)
python -m src.lab.combate.jugar --escenario verificacion_falsa-sencillo --rojo qwen3:8b --azul llama3.1:8b --semilla 1 --verbose
```
Escenarios: `python -c "from src.lab.combate import escenarios as e; print(e.listar())"`. Rojo falso: `falso:objetivos|fijo|denegado|aleatorio`. Azul falso:
`falso:registro|rechazar|aprobar|solicitar|aleatorio|credulo`.

## 2. Desde la interfaz
```powershell
$env:CS_CODIGO_ARBITRO="123456"; python server/app.py      # PUERTO=8000 por defecto
```
Abre `http://localhost:8000/combate/`, entra como **árbitro** (nombre + código), elige escenario y modelos y pulsa «Iniciar combate». Cualquiera puede observar en
solo lectura. Historial, Wazuh (simulado) y Campañas están en el menú lateral.

## 3. Campañas (segundo plano, reanudables)
```powershell
python experimentos/campana_combate.py --campana combate-v1 --fases espejo,cruzada --reps-llm 4 --prueba-corta      # 2–3 partidas, revisa el log
python experimentos/campana_combate.py --campana combate-v1 --fases espejo,cruzada --reps-llm 4 --lanzar           # desacoplada
python experimentos/campana_combate.py --campana combate-v1 --fases espejo,cruzada --reps-llm 4 --estado           # PID, progreso, latido
python experimentos/resumir_combate.py --campana combate-v1                                                       # métricas, IC, gráficas
```
Se puede cortar y relanzar el mismo comando: no repite celdas ya observadas. `--reintentar-invalidas` repite UNA vez las inconclusas.

## 4. Pruebas
```powershell
python ejecutar_pruebas.py            # batería completa (abre navegadores)
python ejecutar_pruebas.py --rapido   # sin navegador
python -m src.lab.test_combate        # solo el motor de combate
python e2e/test_combate_ui.py         # E2E de /combate/ con capturas en docs/capturas_final/
```
