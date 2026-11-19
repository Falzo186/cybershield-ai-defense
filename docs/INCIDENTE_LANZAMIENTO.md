# Incidente del 07/11/2026 · `exit code 4` en la campaña del atacante

Se registra porque es un fallo de infraestructura que interrumpió una medición, y porque el encargo prohíbe
ocultarlos. No afectó a ningún resultado publicado.

## Qué pasó

El primer lanzamiento de `experimentos/campana_atacante.py` en segundo plano terminó con **código 4** a los
~25 minutos, con 11 de 20 sesiones cerradas.

## Diagnóstico

La orden lanzada era `python … > log 2>&1; echo "=== fin, codigo $? ==="; tail -40 log`.

| Evidencia | Qué implica |
|---|---|
| La salida de la tarea son **22 bytes**: solo `[exited with code 4]` | Ni el `echo` ni el `tail` se ejecutaron |
| La tanda anterior, que sí terminó, acaba con `=== fin, codigo 0 ===` y una línea de cierre del shell | El envoltorio normalmente sí imprime esas líneas |
| El log **no tiene ninguna traza de excepción**, y acaba limpio en la sesión 11 | `stderr` iba al log; Python no lanzó nada |
| Las únicas salidas del programa son 0, 1, 2 y 130 | **El 4 no puede venir del programa** |
| Ollama responde `200` con los modelos cargados | No fue una caída del servicio |
| 144 líneas escritas sin un solo error de E/S | No fue disco, permisos ni ruta |
| La tanda anterior corrió **207 min** en segundo plano y terminó en 0 | No es un tope de duración |

**Conclusión:** el envoltorio del shell fue **terminado desde fuera** antes de que Python devolviera el
control. No fue un fallo del experimento.

**Causa más probable, no demostrada:** el directorio de trabajo de la sesión cambió por debajo
(`…\llm-redteam` → `…\Cyberseguridad con IA` → y vuelta), y el aviso de ese cambio coincide con el fallo;
eso derriba el grupo de procesos en segundo plano. **No se puede demostrar el disparador exacto desde
dentro de un proceso que ya murió**, y no se afirma como hecho. Lo que sí está demostrado es todo lo de la
tabla.

## Integridad de los datos: intacta

1 cabecera + 132 rondas + 11 marcas de sesión = 144 líneas. Doce rondas en cada una de las 11 sesiones:
**ninguna sesión partida**. Cero líneas ilegibles. 130 imputables y 2 errores de infraestructura,
correctamente fuera del denominador. No se borró ni se sobrescribió nada, y se hizo copia antes de tocar.

## El defecto propio que el incidente destapó, y su arreglo

Las rondas se escribían **al cerrar la sesión**, no al terminar cada una, así que el corte se llevó minutos
de inferencia ya calculada.

Arreglado: cada ronda se guarda en cuanto termina, mediante el observador `al_avanzar`. Una sesión que no
llega a cerrarse deja sus rondas en el archivo marcadas como **huérfanas**: se conservan, quedan fuera de
las métricas, la sesión se repite entera y nada se cuenta dos veces. Verificado sobre una copia: 3 rondas
huérfanas quedan en 0 de 154, y pasan a 3 de 157 solo al cerrarse la sesión.

Además, `adversarial.campana_atacante` se traga a propósito las excepciones del observador para que un
observador roto no tumbe una campaña. Eso no vale para el que escribe en disco: ahora apunta sus propios
fallos y, si no pudo escribir, **la sesión no se cierra** y se dice por qué.

## Lo que se cambió en el relanzamiento

- La orden es un único comando, sin la cadena `python … ; echo … ; tail …`, así que la salida cae directa en
  el archivo de la tarea y no depende de que el shell sobreviva al programa.
- Prueba corta antes del lanzamiento largo. Cazó una referencia obsoleta (`KeyError: 'objetivo'`) que habría
  reventado la tanda completa a la primera sesión.

El relanzamiento completó las 40 sesiones en 102,6 min con **0 rondas huérfanas**.

---
## Adenda 2026-11-19 · Intento de demostrar la causa (misión extra, fase A.3)

Se probaron tres enfoques controlados en Windows 11 con un hijo de Python de 10 s (scripts efímeros, no versionados). Códigos de salida y estado medidos, no supuestos.

| # | Enfoque | Resultado medido |
|---|---|---|
| 1 | Envoltorio original (`cmd /c "python hijo & echo fin"`) y `taskkill /F /T` sobre el envoltorio | Código del envoltorio **1**; el hijo **murió** (no escribió su marca) |
| 2 | Lanzador desacoplado (`DETACHED_PROCESS\|CREATE_NEW_PROCESS_GROUP`) y `taskkill /F /T` sobre el padre | Código del padre **1**; el hijo **murió también** |
| 2b | Control: los mismos dos lanzamientos con `taskkill /F` **sin** `/T` (solo el padre) | Hijo **sobrevivió y terminó** en ambos casos |
| 3 | Borrar el directorio de trabajo del hijo mientras corre | Windows lo **deniega** (`PermissionError`); el hijo termina con código 0 |

Qué se descarta: el cambio o borrado del directorio de trabajo no mata al hijo (enfoque 3), así que la hipótesis del cwd del incidente original **queda descartada como causa directa**.

Qué se aprende: un corte del árbol (`/T`) mata también al proceso desacoplado, porque Windows conserva la relación padre-hijo. Mi mitigación anterior («lanzador desacoplado») protege solo cuando se mata al padre sin el árbol; **no protege contra un corte de árbol**. Esto corrige la afirmación previa de que la mitigación era suficiente. La protección real que sí funciona es la reanudación (ids deterministas, candado PID, huérfanas).

Qué NO se demostró: el código **4** no se reprodujo (se obtuvo 1). Sigue sin conocerse qué proceso externo terminó el envoltorio original ni por qué devolvió 4. Causa raíz: **no demostrada**.
