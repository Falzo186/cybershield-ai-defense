# Informe de la etapa de integración — CyberShield AI Defense

Fecha: 06/11/2026 · Rama: `main` · De `29434f2` a `fad0776` · 6 commits

Este informe cierra la etapa que arrancó con `docs/AUDITORIA_INTEGRACION.md`. Todas las cifras se han
reproducido en esta máquina; donde algo no se ha podido comprobar, se dice con esas palabras en vez de
rellenarlo.

---

## 1. Estado inicial comprobado

| | Valor |
|---|---|
| Commit de partida | `29434f2` |
| Batería | 30 suites · 1 187 comprobaciones |
| Avance (criterios de `AUDITORIA_INTEGRACION.md` §5) | 76,2 % |
| Diagnóstico | No faltaba funcionalidad: faltaba **acoplamiento**. Tres huecos reales (harness fuera de la partida, el laboratorio adversarial medía el filtro y no el modelo, el sistema de diseño se quedó en el panel) y dos limitaciones de infraestructura (sin Wazuh, sin GPU). |

El hueco principal era verificable con una orden: `grep harness server/app.py` daba **cero**.

---

## 2. Arquitectura final

Lo que cambió es por dónde pasan las cosas, no qué capas hay. Las seis capas deterministas siguen siendo
las mismas y en el mismo orden.

```
                    ┌──────────────────────────────────────────────────────┐
  Rojo (Ollama) ───▶│ motor.ejecutar_ronda(procesar=harness.procesador(…))  │
                    │   ├─ atacante.generar_ataque      (inferencia real)    │
                    │   └─ harness.ejecutar                                  │
                    │        ├─ 1 filtro rápido (regex, sin inferencia)      │
  Azul (Ollama) ───▶│        ├─ 2 defensor IA           (inferencia real)    │
                    │        ├─ 3 catálogo cerrado de 4 herramientas         │
                    │        ├─ 4 whitelist de parámetros                    │
                    │        ├─ 5 permisos rol × sensibilidad                │
                    │        ├─ 6 autorizador + repositorio (SQL fijo)       │
                    │        └─ diagnóstico determinista de la ronda         │
                    └───────────────────┬──────────────────────────────────┘
                                        │  ControlPartida: techos de la partida
                                        ▼  (rondas, llamadas, tokens, tiempo, bucles)
                       SSE  ──▶  interfaz de la partida  +  /api/batalla/presupuesto
                       auditoría append-only  ──▶  cronología  ──▶  correlación
                                                              └──▶  Wazuh (3 modos)
```

El harness **envuelve** al defensor; no lo sustituye ni lo adelanta. `harness` importa `motor`, y `motor`
no importa `harness`: la conexión se hace con `motor.ejecutar_ronda(procesar=…)`, lo que evita el ciclo y
deja el camino directo intacto como opción por defecto.

---

## 3. Archivos creados (10)

| Archivo | Qué es |
|---|---|
| `docs/AUDITORIA_INTEGRACION.md` | Auditoría de la Fase A: matriz, diagnóstico, plan y fórmula de avance |
| `src/lab/evaluacion/lotes.py` | Campañas reanudables por lotes |
| `src/lab/escenarios_empresa.py` | Catálogo declarativo de escenarios de la empresa ficticia |
| `src/lab/wazuh/indexador.py` | Cliente de solo lectura del indexador (OpenSearch) |
| `ui/tokens.css` | Capa de tokens de diseño compartida por las dos pantallas |
| `src/lab/test_control_partida.py` | 56 comprobaciones del control de partida y su integración |
| `src/lab/test_lotes.py` | 49 comprobaciones de reanudación |
| `src/lab/test_escenarios_empresa.py` | 75 comprobaciones de escenarios y estados de misión |
| `server/test_presupuesto.py` | 28 comprobaciones del presupuesto **en el camino de la batalla** |
| `integraciones/wazuh/test_indexador_real.py` | Prueba contra una instalación real (fuera de la batería) |

## 4. Archivos modificados (32)

`src/lab/`: `harness.py`, `motor.py`, `adversarial.py`, `repositorio.py`, `schema.py`, `informe.py`,
`experimentos.py`, `wazuh/__init__.py`, `evaluacion/{campana,escenarios,metricas}.py`, y las suites
`test_{adversarial,evaluacion,wazuh}.py`.
`server/`: `app.py`, `panel.py`, `partida.py`, `test_{app,panel,partida}.py`.
`ui/`: `index.html`, `styles.css`, `render.js`, `app.js`, `escritorio.js`, `panel/index.html`,
`panel/panel.css`.
`docs/`: `INTEGRACION_WAZUH.md`, `SEGURIDAD.md`. Además `ejecutar_pruebas.py`, `.gitignore` y
`integraciones/wazuh/local_rules.xml`.

**Volumen:** 42 archivos, +4 299 / −361 líneas.

---

## 5. Funcionalidades implementadas

| Fase | Qué |
|---|---|
| B | `ControlPartida` y `PresupuestoPartida`; `harness.procesador()`; evento SSE `presupuesto`; ruta `/api/batalla/presupuesto` |
| E1 | `lotes.py`: crear, reanudar, listar, resultado parcial y comparación de campañas |
| E2 | `campana_modelo`, `campana_atacante`, `comparar_filtro_y_modelo`, `metricas.clasificacion`, familia `generado` |
| D | `escenarios_empresa.py` con 3 escenarios y `validar()`; estados `en_progreso` y `cancelada`; rutas de cancelar y reabrir |
| G | `ui/tokens.css`; remapeo de `styles.css`; sprite SVG; puntos de estado; 192 emojis fuera |
| F | `indexador.py`; `wazuh.alertas()` real; `wazuh.estado()` con los dos servicios |
| H | Clave personal, rotación de token, límite de intentos, caducidad, `POST /api/sesion/salir` |

## 6. Funcionalidades integradas (no solo implementadas)

- **El harness está en el camino de una partida real.** `server/test_presupuesto.py` arranca una batalla
  por `/api/batalla/real/iniciar` con el Ollama falso y comprueba el consumo publicado, el corte por techo
  de llamadas, el corte por techo de rondas y el corte por bucle.
- **Las tres medidas de la Fase E tienen ruta en el panel** (`/api/panel/adversarial/modelo`,
  `/adversarial/atacante`, `/lotes`), con progreso real y rechazo si el modelo no está en Ollama.
- **El catálogo de escenarios se sirve** en `/api/escenarios`, de lectura pública.
- **Los estados nuevos de misión** se usan desde la partida: asumir pone en progreso, y hay rutas de
  cancelar y reabrir restringidas a Azul.
- **El indexador se usa en modo real**: `wazuh.alertas()` lo consulta y `wazuh.estado()` publica los dos
  servicios por separado.
- **El lenguaje visual es uno**: las dos pantallas cargan `ui/tokens.css` antes que su hoja propia.

## 7. Funcionalidades todavía simuladas, y marcadas como tales

| Qué | Cómo se marca |
|---|---|
| Alertas del modo `simulado` de Wazuh | `simulado: true`, `origen: "simulado"`, nota explícita y color violeta `--p-simulado` reservado |
| El Ollama falso de las pruebas | Solo existe en `e2e/ollama_falso.py`; ninguna cifra del informe sale de él |
| El evaluador de reglas de Wazuh sin conexión | La cabecera de `reglas.py` dice que **no es Wazuh**, sino un modelo simplificado |

## 8. Funcionalidades pendientes

1. **Campañas grandes** (n ≥ 200 por condición). La maquinaria está (`lotes.py`), el tiempo de CPU no.
2. **Wazuh real**: no hay instalación. El cliente, el contrato y la prueba condicional están listos.
3. **TLS**: documentado con proxy inverso, no desplegado ni probado aquí.
4. **Modo `estres`** de campaña: el preset existe; nunca se ha ejecutado una tanda larga.
5. **Recuperación de clave personal** y código de árbitro por persona (hoy es uno compartido).

---

## 9. Pruebas: inicial y final, comparables

| | Inicio (`29434f2`) | Final (`fad0776`) |
|---|---|---|
| Suites | 30 | **34** |
| Comprobaciones | 1 187 | **1 646** |
| E2E de navegador | 106/106 | **106/106** |

Mismo ejecutor (`ejecutar_pruebas.py`), misma máquina, mismo intérprete. **No son dos medidas del mismo
conjunto**: 4 suites son nuevas y varias existentes crecieron. El delta honesto es «+4 suites y +459
comprobaciones», no «las pruebas mejoraron un 39 %».

La E2E de navegador se ejecutó **antes y después** de cada bloque de cambio visual de la Fase G: tokens,
iconos, indicadores y limpieza de cadenas. Las cuatro veces, 106/106.

### Dos categorías que no se mezclan

- **Pruebas de software (1 646):** usan el Ollama falso o un doble inyectado. Miden el **camino del
  código**. Ninguna dice nada sobre la calidad de un modelo.
- **Evaluaciones de IA:** las campañas de `src/lab/evaluacion/` y `src/lab/adversarial.py`. No forman parte
  de la batería y sus resultados van en la §11.

### Regresiones que la batería cazó durante esta etapa

| Qué | Cómo se arregló |
|---|---|
| Dos tipos de evento nuevos (`mision_cancelada`, `mision_reabierta`) sin regla de Wazuh | Regla 100141, nivel 3 |
| `lotes.comparar` llamaba a `metricas.comparar` con la firma equivocada | Corregido a `(nombre, éxitos, n, …)` |
| Un conteo de reglas fijado a 18 en dos pruebas | Actualizado a 19 |
| Una prueba suponía que la familia `generado` estaba vacía | Actualizada: ya no lo está |
| Colisión de nombre entre dos ayudantes `transporte` en `test_wazuh` | Renombrado |

---

## 10. Rendimiento de Ollama en esta máquina

Hardware real: **sin GPU utilizable** (Radeon integrada de 2 GB, `nvidia-smi` no existe), 17,8 GB de RAM,
inferencia por CPU. Modelos instalados: `qwen3:4b`, `llama3.2:3b`, `qwen2.5:7b`, `deepseek-r1:1.5b`,
`llama3.2:1b`, `qwen2.5:1.5b`.

Esto es lo que condiciona todo el diseño de la evaluación: una campaña de 200 × 4 condiciones son horas,
y por eso la Fase E1 (reanudación por lotes) va antes que las campañas grandes.

---

## 11. Resultados de inferencias reales

Ejecutado hoy contra el Ollama de esta máquina con `experimentos/validar_metodologia.py llama3.2:3b 1 6`.
Resultado completo en `data/validacion_metodologia.json`.

**Esto valida la metodología, no mide al modelo.** Con 18 casos maliciosos imputables y 6 rondas de
atacante, ninguna de estas cifras es concluyente, y el propio programa lo imprime. Se publican porque son
inferencias reales y porque enseñan algo que una métrica única habría escondido.

> **Superado por una medición mayor, 07/11/2026.** La tarea 1 de la §17 se ejecutó: 1 536 inferencias reales
> del defensor en 6 condiciones, con 244 observaciones imputables cada una. Está en
> **`docs/CAMPANAS_GRANDES.md`**, con un hallazgo que esta muestra pequeña no podía ver: la exactitud oficial
> le da a `llama3.2:3b` la misma cifra que a un defensor que contesta siempre lo mismo.
> Las cifras de esta sección **se dejan como se midieron**; no se corrigen ni se reinterpretan.

### 11.1 · Las tres medidas, por separado

| Medida | Resultado | Denominador |
|---|---|---|
| **Detección del filtro determinista** (0 inferencias) | sensibilidad **78,9 %** IC95 [56,7 · 91,5] · falsos positivos **0,0 %** IC95 [0,0 · 29,9] | 15/19 maliciosos · 0/9 benignos |
| **Resistencia del modelo defensor** `llama3.2:3b`, sin filtro delante | recall **100 %** IC95 [82,4 · 100] · precisión **66,7 %** IC95 [47,8 · 81,4] · especificidad **0,0 %** IC95 [0,0 · 29,9] · F1 **0,80** | 18/18 maliciosos · 18/27 marcados · 0/9 benignos |
| **Objetivo del modelo atacante** `llama3.2:3b` contra el sistema completo | **0,0 %** IC95 [0,0 · 39,0] | 0/6 rondas, 0 no imputables |

### 11.2 · Lo que estas cifras enseñan, y que una sola métrica habría tapado

**El modelo defensor contiene absolutamente todo.** Recall 100 % suena excelente hasta que se mira al
lado: especificidad **0 %**. De los nueve casos benignos —peticiones legítimas que se parecen a un
ataque—, `llama3.2:3b` marcó los nueve como riesgo. No está distinguiendo: está diciendo «no» a todo. Un
defensor que rechaza cualquier cosa tiene recall perfecto y **no aporta ninguna información**.

Esto es exactamente lo que el encargo pedía no confundir. Con una métrica única de «cumplimiento de
política» este modelo habría salido con un 100 % y el informe habría dicho que es un defensor excelente.
Separando precisión de recall se ve que su F1 de 0,80 lo sostiene únicamente el recall, y que las seis
peticiones legítimas del laboratorio también se bloquean.

**El filtro determinista y el modelo fallan en sitios distintos.** El filtro deja pasar dos categorías
—`codificacion` y `reformulacion`, las variantes deliberadamente fuera de patrón— y no molesta a ningún
benigno. El modelo no deja pasar ninguna, pero molesta a todos los benignos. Son perfiles opuestos, y por
eso están delante uno del otro en el sistema real. La comparación formal entre los dos recalls sale
**`muestra_insuficiente`**: 18 observaciones en el grupo menor contra un mínimo de 20. El laboratorio se
niega a interpretar la diferencia, que es lo correcto.

**El atacante no consiguió nada en 6 rondas.** 0/6, IC95 [0,0 · 39,0]. Ese intervalo llega al 39 %: con
seis rondas no se puede afirmar que el sistema sea sólido, solo que en estas seis no pasó nada. Las seis
las frenó el defensor IA (`frenado_por: {"ia": 6}`), sin que llegara a intervenir ninguna capa posterior.

**Una respuesta quedó indeterminada** (fallo de inferencia). No cuenta ni como acierto ni como fallo del
modelo: queda en `indeterminados`, fuera del denominador. Es la regla que impide que un error de
infraestructura se confunda con un fallo de razonamiento.

### 11.3 · Latencias medidas (CPU, sin GPU)

| | n | media | mediana | p95 | máx |
|---|---|---|---|---|---|
| Defensor, una solicitud | 28 | 6 131 ms | 5 585 ms | 6 983 ms | 19 503 ms |
| Atacante, generar un ataque | 6 | 8 988 ms | 9 061 ms | 11 440 ms | 12 027 ms |
| Defensor dentro de una ronda de partida | 6 | 6 170 ms | 6 041 ms | 6 864 ms | 6 995 ms |

Una ronda completa son ~15 s de inferencia. De ahí sale la cuenta que justifica la Fase E1: una campaña de
200 rondas por condición y cuatro condiciones son **más de tres horas** de CPU ininterrumpida. Sin
reanudación, cualquier corte tira el trabajo.

El máximo de 19,5 s del defensor es la primera llamada, que incluye la carga del modelo en memoria. Está
en la cifra a propósito: es tiempo real que el usuario espera.

### 11.4 · Reproducirlo

```bash
python experimentos/validar_metodologia.py llama3.2:3b 1 6     # ~4 min
```

La detección del filtro es determinista al 100 % y saldrá idéntica. Las otras dos dependen del modelo y
variarán: `llama3.2:3b` responde a temperatura 0,2 pero no es determinista.

## 12. Estado de Wazuh

| | |
|---|---|
| Modo activo en esta máquina | `desactivado` (ninguna variable de entorno puesta) |
| Manager | Cliente de solo lectura, probado con transporte sustituido. **Sin instalación real que probar.** |
| Indexador | Implementado en esta etapa. Solo `_search` y `_count` sobre `wazuh-alerts-*`. **Sin instalación real que probar.** |
| Reglas locales | 19 reglas, ids 100100–100141, cubren los 28 tipos de evento del laboratorio |
| Prueba de integración | `integraciones/wazuh/test_indexador_real.py`, **fuera de la batería**. Sin configuración sale con código 2 y «NO EJECUTADA» |
| Qué pasa si el modo es `real` y no hay conexión | Error visible, con distinción de si falló el manager o el indexador. **Nunca** se sustituye por alertas simuladas |

No se ha ejecutado `wazuh-logtest`, no se ha visto una alerta en el panel de Wazuh y no se ha leído un
índice `wazuh-alerts-*` de verdad. Los requisitos de instalación están en `docs/INTEGRACION_WAZUH.md` §
«Cómo conectar un Wazuh real».

---

## 13. Seguridad y limitaciones

### Lo que esta etapa añadió

| | |
|---|---|
| El harness **no** puede amplificar un ataque | Solo se reintenta ante `ERROR_FORMATO`, `ERROR_CATALOGO` o `ERROR_PARAMETRO`, y los dos últimos solo si la identidad real tiene derecho a esa herramienta. Probado **en el camino de la batalla**, no solo en aislado |
| Un atacante no puede agotar la máquina | Techo de rondas, de llamadas al modelo, de tokens, de tiempo y de errores seguidos por partida. No hay ninguna ruta que amplíe un techo |
| Un modelo girando en vacío se corta | Detección de prompt repetido y de propuesta repetida |
| Las mediciones no entran en el camino de la partida | `test_adversarial` comprueba que ni el motor, ni las herramientas, ni `server/app.py` importan el laboratorio adversarial; la única vista que lo lee es el panel |
| El indexador no puede escribir | Rutas permitidas comprobadas **antes** de abrir el socket; sin funciones de escritura en el módulo |
| Identidad por persona | PBKDF2 con sal propia, rotación de token, límite de intentos, caducidad y cierre de sesión |
| Ningún secreto versionado | Comprobado con `git grep`; las credenciales se leen del entorno y no salen en ninguna respuesta ni línea de auditoría |

### Lo que sigue abierto

- **Sin TLS.** Mientras no lo haya, esto es para `localhost` o una red de confianza: el token y la clave
  viajan en claro.
- **El código de árbitro es uno y compartido**, impreso en la consola al arrancar.
- **Las sesiones viven en memoria.** Reiniciar el servidor las borra todas.
- **Ollama no tiene autenticación.** No debe exponerse fuera de la máquina.
- **La medición del modelo pasa por alto el filtro** a propósito (es la única forma de medir al modelo), y
  eso está dentro de un módulo que una prueba impide que entre en el camino de la partida. Si alguien
  moviera esa llamada al motor, la prueba fallaría.

---

## 14. Evidencias de funcionamiento

| Afirmación | Cómo comprobarla |
|---|---|
| El harness controla la partida | `python server/test_presupuesto.py` → 28/28 |
| Una denegación de permiso no se reintenta | `python -m src.lab.test_control_partida` → 56/56 |
| Una campaña se reanuda sin duplicar | `python -m src.lab.test_lotes` → 49/49 |
| Las tres medidas están separadas | `python -m src.lab.test_adversarial` → 77/77 |
| Los escenarios no prometen nada inexistente | `python -m src.lab.test_escenarios_empresa` → 75/75 |
| La migración conserva el progreso histórico | mismo comando, bloque final |
| El indexador es de solo lectura | `python -m src.lab.test_wazuh` → 105/105 |
| La identidad por persona funciona | `python server/test_partida.py` → 73/73 |
| La partida sigue funcionando tras el rediseño | `python e2e/demo_partida.py` → 106/106 (4 navegadores) |
| Todo junto | `python ejecutar_pruebas.py` → **34/34 suites · 1 646/1 646** |
| La integración real de Wazuh **no** está probada | `python integraciones/wazuh/test_indexador_real.py` → código 2, «NO EJECUTADA» |

Capturas de la partida con el diseño nuevo: `docs/capturas_demo/` (las genera la propia E2E).

---

## 15. Commits

| Commit | Fase |
|---|---|
| `073cb66` | B · El harness controla la partida, y campañas reanudables |
| `e9efc0a` | E · Familia `generado` y medición separada de modelo y atacante |
| `888cc16` | D · Catálogo de escenarios de empresa y estados de misión |
| `940304a` | G · El sistema de diseño del panel, aplicado a la pantalla de la partida |
| `98dc51f` | F · Lectura de alertas del indexador de Wazuh, de solo lectura |
| `fad0776` | H · Autenticación por persona, protección de sesiones y TLS documentado |

Ninguno se ha subido: **6 commits locales por delante de `origin/main`**. No se ha borrado ninguna rama,
ningún dato ni ningún registro histórico.

---

## 16. Avance, con la misma fórmula y los mismos pesos

Los pesos y los criterios son **exactamente** los de `AUDITORIA_INTEGRACION.md` §5, fijados antes de
medir. No se han tocado después de ver los resultados.

```
avance = Σ(peso_i × cumplimiento_i) / Σ(peso_i)        cumplimiento ∈ {0, 0.5, 1}
```

| Criterio de §18 del encargo | Peso | Antes | Ahora | Por qué |
|---|---|---|---|---|
| Partida completa entre dos modelos reales | 10 | 1 | 1 | — |
| Selección independiente de modelos Rojo/Azul | 6 | 1 | 1 | — |
| Acciones dentro de un escenario ficticio | 6 | 1 | 1 | — |
| Validación de acciones por el motor | 10 | 1 | 1 | — |
| Misiones defensivas funcionales | 8 | 1 | 1 | — |
| Consecuencias verificables | 8 | 1 | 1 | — |
| Diagnóstico de cada ronda | 6 | 1 | 1 | — |
| **Harness integrado** | 8 | 0 | **1** | En el camino de la batalla, con prueba propia |
| Persistencia de partidas | 6 | 1 | 1 | — |
| Cronología consultable | 6 | 1 | 1 | — |
| **Evaluación adversarial del defensor** | 8 | 0 | **0,5** | Implementada, integrada y probada; **medida solo con una muestra pequeña**, que no es concluyente |
| **Evaluación del objetivo del atacante** | 6 | 0 | **0,5** | Igual: la maquinaria está y se ha validado, la medición seria no |
| **Panel coherente con la partida** | 6 | 0,5 | **1** | Mismo sistema de tokens en las dos pantallas |
| Vista de espectador de solo lectura | 4 | 1 | 1 | — |
| Separación real / simulado | 6 | 1 | 1 | — |
| **Wazuh real probado, o limitación documentada** | 6 | 0,5 | **1** | El criterio admite la limitación documentada: cliente, contrato, prueba condicional y requisitos de instalación |
| Batería completa en verde | 8 | 1 | 1 | 1 646/1 646 |
| Documentación actualizada | 4 | 1 | 1 | — |

**Σ pesos = 122 · Σ(peso × cumplimiento) = 114 → avance = 93,4 %** (antes 76,2 %).

> **Corrección aritmética, 07/11/2026.** Esta suma arrastra el error de la auditoría y suma uno de menos:
> la columna «Ahora» de la tabla de arriba da **115, no 114**, es decir **94,3 %, no 93,4 %** (y la línea de
> partida es 77,0 %, no 76,2 %; ver la corrección en `AUDITORIA_INTEGRACION.md` §5).
>
> **Ningún peso ni ningún cumplimiento cambia.** La tabla queda como estaba y la línea original se deja
> escrita arriba. La mejora atribuible a esta etapa **no cambia**: eran 21 puntos ponderados (114 − 93) y
> siguen siendo 21 (115 − 94). Lo que se mueve es la base y el extremo, cada uno un punto, 0,8 puntos
> porcentuales. Así que la corrección no favorece a esta etapa: solo pone bien la cuenta. La suma vive ahora
> en `experimentos/avance.py`.
>
> Estado tras las campañas grandes: **122 / 122 → 100,0 %**, con los mismos pesos. Qué significa y qué **no**
> significa ese 100 %, en `docs/CAMPANA_ATACANTE.md` § «El 100 % y lo que sigue abierto».

Los 8 puntos que faltan son, casi enteros, los dos criterios de evaluación a medias: no se cierran
escribiendo más código, sino dejando correr campañas grandes.

---

## 17. Próximas tareas, por prioridad

1. **Campañas con n ≥ 200 por condición**, con `evaluacion/lotes.py` por lotes de 30–40 rondas. Es lo único
   que mueve el avance: cierra los dos criterios a medias y convierte las cifras de la §11 en resultados.
2. **Comparar modelos** en resistencia del defensor: `llama3.2:3b` contra `qwen2.5:7b`, mismo conjunto,
   misma semilla, con `lotes.comparar`.
3. **Probar Wazuh contra una instalación real** y ejecutar `test_indexador_real.py`. Es la única forma de
   quitar el «no comprobado» de la §12.
4. **Medir el coste real del harness** en una partida larga con modelos de verdad: hoy sabemos que no
   cambia el número de inferencias en el caso normal, pero no cuánto suma su contabilidad.
5. **Modo `estres`**: una tanda larga para detectar fugas de memoria y degradación.
6. **TLS en un despliegue de prueba**, siguiendo `docs/SEGURIDAD.md` §8.
7. **Código de árbitro por persona** y recuperación de clave.

---

## 18. Tabla de módulos

| Módulo | Estado | Evidencia | Pendiente | Avance |
|---|---|---|---|---|
| Motor de ronda y seis capas | Terminado | `test_motor` 41 · E2E 106 | — | 100 |
| Harness y presupuesto de partida | **Terminado** | `test_control_partida` 56 · `test_presupuesto` 28 | Medir su coste con modelos reales | 95 |
| Diagnóstico determinista | Terminado | `test_diagnostico` 50 | — | 100 |
| RAG | Terminado | `test_rag` 64 | Corpus más amplio | 85 |
| Evaluación autónoma | **Terminado** | `test_evaluacion` 121 · `test_lotes` 49 | Campañas n ≥ 200; modo `estres` | 85 |
| Registro de experimentos | Terminado | `test_evaluacion` | — | 100 |
| Laboratorio adversarial | **Terminado** | `test_adversarial` 77 · §11 | Medición con muestra grande | 80 |
| Escenarios de empresa | **Terminado** | `test_escenarios_empresa` 75 | Más escenarios | 90 |
| Misiones y consecuencias | **Terminado** | `test_misiones` 17 · `test_incidentes` 42 | — | 100 |
| Wazuh | Preparado | `test_wazuh` 105 · `test_reglas` 14+25 | Probar contra instalación real | 75 |
| Correlación y cronología | Terminado | `test_correlacion` 39 | Incluir pasos del harness | 90 |
| Panel de análisis | Terminado | `test_panel` 83 | — | 100 |
| Interfaz de la partida | **Terminado** | E2E 106 · `test_app` 206 | — | 95 |
| Sesiones y roles | **Terminado** | `test_partida` 73 | Árbitro por persona | 90 |
| Seguridad del despliegue | Documentado | `docs/SEGURIDAD.md` §7–8 | TLS desplegado | 60 |

---

## 19. Las cuatro condiciones del encargo

| Condición | Cómo se cumplió |
|---|---|
| **A. No romper lo existente** | La batería completa se ejecutó tras cada fase; la E2E de navegador, además, antes y después de cada bloque visual. Las cinco regresiones que aparecieron están en la §9 con su arreglo. |
| **B. No confundir simulación con realidad** | El Ollama falso solo vive en las pruebas; las alertas simuladas llevan marca y color propios; la prueba de Wazuh real sale con «NO EJECUTADA» en vez de pasar en verde; las cifras de la §11 vienen de inferencias reales y dicen su tamaño de muestra. |
| **C. No mejorar artificialmente las métricas** | No se quitó ningún escenario difícil: la familia `generado` **añade** 12. Los pesos del avance son los de la auditoría, fijados antes. El 78,9 % del filtro no se ha tocado. Los dos criterios de evaluación se puntúan 0,5, no 1, porque la medición seria no se ha hecho. |
| **D. No detenerse en la planificación** | Siete fases implementadas, probadas y comiteadas; 42 archivos, +4 299 líneas; cuatro documentos actualizados. |
