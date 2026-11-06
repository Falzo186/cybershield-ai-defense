# Arquitectura actualizada — CyberShield AI Defense

Estado al 06/11/2026, tras la evolución técnica. Sustituye a la §1 de [`DIAGNOSTICO.md`](DIAGNOSTICO.md),
que sigue valiendo como foto del 26/10/2026.

## Mapa

```
┌──────────────────────── ui/ ────────────────────────┐   ┌──────────── ui/panel/ ────────────┐
│ Partida Rojo/Azul (escritorio con ventanas)         │   │ Panel de operaciones y análisis   │
│ index.html · app.js · render.js · escritorio.js     │   │ 11 pantallas · sistema de diseño  │
└──────────────────────┬──────────────────────────────┘   └──────────────┬────────────────────┘
                       │  REST + SSE                                     │  REST (GET públicos)
┌──────────────────────▼─────────────────────────────────────────────────▼────────────────────┐
│ server/app.py (FastAPI: partida, batalla, buzón, misiones, incidentes)                       │
│ server/panel.py (NUEVO: /api/panel/… estado, resumen, experimentos, RAG, SOC, campañas)      │
│ server/partida.py · server/mock_server.py                                                    │
└──────────────────────┬───────────────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────────────────────────────┐
│ MOTOR                                                                                         │
│  harness.py (NUEVO: presupuestos, bucles, cancelación)                                        │
│    └─ motor.py → filtro_rapido → defensor.py ──(tecnica)──→ rag/ (NUEVO)                      │
│                       │                                      corpus · indice (BM25)           │
│                       ├─ atacante.py · ataque_ia.py · sesion.py                               │
│                       └─ diagnostico.py (NUEVO: 12 clases, evidencia, confianza)              │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ CAPAS DETERMINISTAS   herramientas.py (catálogo + validación) → permisos.py → repositorio.py  │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ EVALUACIÓN            evaluacion/ (NUEVO: escenarios · metricas · campana · correr)           │
│                       experimentos.py (NUEVO: registro y comparador)                          │
│                       adversarial.py (NUEVO, aislado del camino de producción)                │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ OBSERVABILIDAD        wazuh/ (NUEVO: 3 modos · cliente de solo lectura · reglas compartidas)  │
│                       correlacion.py (NUEVO: cronología unificada y correlación)              │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ DATOS                 SQLite data/lab.db · data/eventos.jsonl · data/experimentos.jsonl       │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                   Ollama (localhost, urllib de la stdlib)
```

## Qué cambió y qué no

### Lo que no se tocó

El catálogo cerrado de 4 herramientas, la validación por lista blanca, los permisos rol × sensibilidad, el
autorizador, el repositorio sin SQL libre, la auditoría *append-only*, el circuito de seguridad por sesión,
la partida Rojo/Azul completa (buzón, misiones, incidentes, credenciales, marcador, cierre), el cliente de
Ollama y la interfaz de la partida (salvo una línea: el enlace al panel).

**Ninguna funcionalidad se eliminó.**

### Módulos nuevos

| Módulo | Líneas | Qué resuelve |
|---|---|---|
| `src/lab/diagnostico.py` | 215 | Por qué falló cada ronda, en 12 clases, separando infraestructura de modelo |
| `src/lab/harness.py` | 288 | Presupuestos, detección de bucles, cancelación, estado serializable |
| `src/lab/rag/` | 486 | Corpus, troceado, índice BM25 (+embeddings opcionales), saneado anti-inyección |
| `src/lab/evaluacion/` | 724 | Escenarios con referencia determinista, métricas con IC, campañas, lanzador |
| `src/lab/experimentos.py` | 192 | Registro reproducible y comparador que avisa cuando no es comparable |
| `src/lab/adversarial.py` | 219 | Laboratorio de prompt injection, aislado, con controles benignos |
| `src/lab/wazuh/` | 341 | Tres modos, cliente de solo lectura, reglas compartidas con la prueba |
| `src/lab/correlacion.py` | 221 | Cronología unificada y correlación de incidentes |
| `server/panel.py` | 237 | Rutas del panel, en su módulo para no engordar `app.py` |
| `ui/panel/` | 1 733 | Sistema de diseño y 11 pantallas |

### Cambios en módulos existentes

| Archivo | Cambio | Compatibilidad |
|---|---|---|
| `motor.py` | Añade `diagnostico` a cada ronda; acepta `tecnica`, `rag_host`, `rag_k`, `rag_umbral`, `temperatura` | Todos los parámetros nuevos tienen valor por defecto; el comportamiento sin ellos es idéntico |
| `defensor.py` | `_system` acepta técnica y bloque RAG; `analizar` acepta técnica y temperatura; devuelve `tecnica` y `rag` | Por defecto `tecnica="fewshot"`, que es el comportamiento histórico |
| `server/app.py` | Importa el panel, lo registra y abre `/api/panel/` a los GET públicos; emite el diagnóstico por SSE | 3 bloques tocados, ninguna ruta existente modificada |
| `integraciones/wazuh/test_reglas.py` | Usa el módulo de reglas compartido en vez de su propia copia | Las 14 comprobaciones siguen pasando |
| `ui/index.html`, `ui/styles.css` | Una línea: el enlace al panel | La E2E de navegador sigue en 106/106 |

### Decisiones de arquitectura, con su razón

| Decisión | Por qué | ¿Reversible? |
|---|---|---|
| **Sin dependencias nuevas** (BM25 en Python puro en vez de ChromaDB/FAISS) | 17 fragmentos no justifican cientos de MB y un proceso más. `requirements.txt` sigue en 3 líneas | Sí: la interfaz de `Indice` está aislada en un archivo |
| **Sin SQL generado por un modelo**, en contra de lo que pedía el encargo | Añadirlo habría destruido la capa 6, que es la propiedad de seguridad central del proyecto | — |
| **Panel nuevo en vez de rediseñar la partida** | Rehacer una interfaz de 3 800 líneas que funciona, para una funcionalidad que no tenía interfaz, era el cambio de mayor riesgo y menor valor | Sí: el sistema de diseño está en tokens y se puede aplicar a la otra interfaz |
| **Rutas del panel en su propio módulo** | `app.py` ya tenía 1 821 líneas y la auditoría lo marcó como problema | — |
| **Tipografía del sistema, no Google Fonts** | El proyecto funciona sin red; traer una fuente externa lo rompería | Sí |
| **El harness no se conectó a la partida** | Cambia el coste por ronda y hay que medirlo antes de imponerlo a una partida en vivo | Sí |

## Flujo de una ronda, hoy

1. `atacante.generar_ataque` (Ollama) o una solicitud del conjunto de evaluación.
2. **[harness]** comprobar presupuesto, repeticiones y cancelación.
3. `filtro_rapido.clasificar_rapido`: los casos obvios se bloquean sin inferencia.
4. **[RAG]** si la técnica lo pide: recuperar → **sanear** → insertar como material de consulta.
5. `defensor.analizar` (Ollama): propone decisión, herramienta y parámetros.
6. Circuito de seguridad por sesión.
7. `herramientas.ejecutar_herramienta`: catálogo → validación → permisos/autorización → repositorio.
8. `motor.evaluar_veredicto`.
9. **`diagnostico.diagnosticar`**: por qué salió ese veredicto, y si cuenta para el modelo.
10. **[harness]** ¿corrección técnica legítima? Si no, salir.
11. Auditoría SQLite + `eventos.jsonl` + SSE + (en campaña) ronda registrada en el experimento.

## Pruebas

| Bloque | Suites | Comprobaciones |
|---|---|---|
| Unitarias (`src/lab/test_*.py`) | 21 | 782 |
| Servidor (`server/test_*.py`) | 6 | 343 |
| Integración (`e2e/`, `integraciones/`) | 2 | 38 |
| Navegador (Playwright) | 1 | 106 |
| **Total** | **30** | **1 187** |

`python ejecutar_pruebas.py` las corre todas; `--rapido` omite el navegador. Ninguna necesita Ollama
encendido ni red: las que requieren un modelo usan el Ollama falso o un doble inyectado. Las campañas con
Ollama real son una herramienta aparte (`src.lab.evaluacion.correr`), nunca parte de la batería.
