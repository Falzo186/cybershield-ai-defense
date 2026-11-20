# 00 — LEER PRIMERO (protocolo de arranque y reanudación)

Eres el responsable técnico autónomo de **CyberShield AI Defense** durante una misión de **23 horas sin supervisión humana**. Esta carpeta (`MISION_23H/`) contiene TODO lo que necesitas saber. Léela completa antes de tocar código.

## Orden de lectura obligatorio
1. `00_LEEME_PRIMERO.md` (este archivo)
2. `01_MISION_Y_ALCANCE.md`
3. `02_REGLAS_INQUEBRANTABLES.md`
4. `03_DIAGNOSTICO_INICIAL.md`
5. `04_VICTORIA_Y_DERROTA.md`
6. `05_MODELOS_8B.md`
7. `06_WAZUH_SIMULADO.md`
8. `07_INTERFAZ_IMPECABLE.md`
9. `08_EVALUACION_Y_METRICAS.md`
10. `09_PRUEBAS_Y_CALIDAD.md`
11. `10_DOCUMENTACION_Y_ENTREGA.md`
12. `11_PLAN_DE_TIEMPO_23H.md`
13. `12_PROMPT_ORIGINAL_DEL_USUARIO.md` (referencia histórica; si contradice a los archivos 01–11, mandan 01–11)

## Arranque (primeros 10 minutos)
1. Ejecuta `date` y guarda la hora en `MISION_23H/ESTADO_MISION.md` como **T0**. Calcula y escribe **T_FIN = T0 + 23 h** y **T_CIERRE = T0 + 21 h 30 min** (a partir de T_CIERRE solo se hace cierre, documentación y regresión; nada nuevo).
2. Crea la rama `mision-23h` desde la rama actual y la etiqueta de respaldo `pre-mision-23h`. Copia de seguridad de la base de datos y de `data/` a `respaldo_pre_mision/` (si no existe ya).
3. Crea `ESTADO_MISION.md` con: T0, T_FIN, fase actual, tareas hechas, tareas pendientes, bloqueos, último commit, resultado de la última batería de pruebas.
4. Crea una tarea (TaskCreate) por fase del archivo 11.

## Protocolo de reanudación (si se compacta o pierdes contexto)
Si no recuerdas qué estabas haciendo: lee `ESTADO_MISION.md`, `PROGRESO.md`, `git log --oneline -30`, `git status` y vuelve a leer `00`, `02` y `11`. Continúa desde la fase registrada. **Nunca reinicies trabajo ya commiteado.** Actualiza `ESTADO_MISION.md` al terminar CADA tarea, no solo cada fase.

## Reloj
Ejecuta `date` al inicio y al final de cada fase y regístralo. Si vas atrasado respecto al archivo 11, aplica la regla de recorte de alcance allí descrita. Nunca dejes que el cierre (docs, regresión, informe) se quede sin tiempo.

## Cómo terminar
La misión termina cuando cumples la "Definición de terminado" de `01_MISION_Y_ALCANCE.md` o llegas a T_FIN. Entrega siempre `docs/INFORME_EJECUTIVO_FINAL.md` (formato en archivo 10), aunque la misión quede incompleta; en ese caso, con la lista honesta de lo que falta y por qué.
