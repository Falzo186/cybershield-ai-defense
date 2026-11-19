# Modelos de 8B (misión 23 h)

Medido el 2026-11-18 en esta máquina (Ollama 0.32.5, Windows 11, GPU NVIDIA GeForce RTX 5060 de 8 GB, 46 GB de disco libres).

| Modelo | Parámetros | Cuantización | Tamaño | Digest | Origen |
|---|---|---|---|---|---|
| `qwen3:8b` | 8,2 B | Q4_K_M | 5,2 GB | `500a1f067a9f…` | ya instalado (no se descargó nada) |
| `llama3.1:8b` | 8,0 B | Q4_K_M | 4,9 GB | `46e0c10c039e…` | ya instalado (no se descargó nada) |

No se descargó un tercer modelo: con dos 8B instalados la matriz espejo/cruzada ya cubre la comparación, y `gemma4:12b` (8 GB) no cabe en VRAM junto a nada más.
`qwen3:4b`, `qwen2.5:1.5b` y los demás pequeños quedan disponibles para pruebas rápidas; **los resultados oficiales del combate usan los dos 8B**.

## Configuración técnica
- `think: false` (heredado de `cliente_ollama.generar`): `qwen3` responde sin razonamiento separado, para que `content` nunca llegue vacío por consumo del presupuesto.
  En la campaña no hubo respuestas vacías atribuibles a esto (ver el informe de campañas).
- `num_ctx = 4096`, `keep_alive = 30m`, `seed = semilla + turno` (+ intento): registrados en `partida.creada.config`.
- Temperatura: Rojo **0,7** (`num_predict` 260), Azul **0,2** (`num_predict` 200). Constantes dentro de una comparación.
- Salida del Azul: JSON `{"decision": APROBAR|RECHAZAR|SOLICITAR_AUTORIZACION|ESCALAR, "justificacion", "contener_agente"}`; parser estricto con hasta 2
  reintentos; una respuesta malformada **no** es una aprobación. Salida del Rojo: JSON `{"mensaje", "recurso", "accion", "referencia_autorizacion", "te_presentas_como"}`
  con texto natural únicamente (filtro de contenido técnico en el motor).
- Versión de prompts: **v2** (se guarda en cada observación). v1 (prueba corta, 1 partida) no incluía el consejo de cambiar de recurso ni la petición directa; v2 sí. No se
  cambió ningún prompt durante la campaña oficial.

## Velocidad medida (prueba corta, `num_predict` 150, temp. 0,2)
| Modelo | Carga en frío | Tokens/s en caliente |
|---|---|---|
| `qwen3:8b` | 25,2 s | ≈ 20 |
| `llama3.1:8b` | 8,3 s | ≈ 25 |

Con esto se dimensionó la campaña: una partida espejo de 6–10 turnos tarda ≈ 25–50 s; una cruzada ≈ 65–100 s.

## Decisión: co-residencia o alternancia
Dos modelos de ~5 GB **no caben a la vez** en 8 GB de VRAM (comprobado con `ollama ps`: solo uno residente). Las partidas **espejo** (mismo modelo en los dos
equipos) no conmutan nunca. En las **cruzadas** cada llamada alterna de modelo y Ollama descarga/carga entre turnos: se asume el costo (la duración media por
partida cruzada está en el informe de campañas) y no se intenta compartir VRAM. Una sola partida a la vez.
