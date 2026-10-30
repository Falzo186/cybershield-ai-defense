# Adaptador de Wazuh para CyberShield

> **Estado: documentado y comprobado sin conexión. NO probado contra un Wazuh real.** En este laboratorio no hay
> ningún Wazuh instalado ni conectado. Lo que sigue es lo necesario para conectarlo y lo que ya está verificado
> sin él.

## Qué emite el laboratorio

`Repositorio.registrar` escribe cada evento relevante como **una línea JSON** en `data/eventos.jsonl`, desde el mismo
punto que la auditoría SQLite (que sigue siendo la fuente de verdad). Cada línea tiene 11 campos:

```json
{"timestamp": "2026-10-30T10:26:23-06:00", "partida": "20261030-102619-840c", "equipo": "rojo",
 "usuario": "ana.perez", "rol": "empleado", "tipo": "ataque_ia_resultado", "accion": "ATAQUE_IA_RESULTADO",
 "recurso": "ataque_ia:1", "resultado": "DATOS_EXPUESTOS", "riesgo": "CRITICO", "origen": "cybershield-lab"}
```

Hay 26 tipos: los de `repositorio.EVENTOS_SIEM` y `autorizacion_denegada`. `eventos_ejemplo.jsonl` son
eventos **reales** de una partida jugada por `e2e/test_reinicio.py`, con el Ollama falso para la IA.

## Archivos

| Archivo | Para qué |
|---|---|
| `ossec_localfile.xml` | Bloque `<localfile>` con `log_format json` para que el agente lea `data/eventos.jsonl`. |
| `local_rules.xml` | 18 reglas (ids 100100-100140) del grupo `cybershield`: una base y una por familia de eventos, con nivel, descripción con los campos y técnicas MITRE. |
| `eventos_ejemplo.jsonl` | Muestra real para probar las reglas. |
| `test_reglas.py` | Comprobación sin conexión (abajo). |

| Nivel | Eventos |
|---|---|
| 12 | `credencial_comprometida` (T1566.002, T1078) · `ataque_ia_resultado` = `DATOS_EXPUESTOS` (T1078, T1213) |
| 10 | Correlación: 3 `autorizacion_denegada` de la misma partida en 120 s |
| 7-8 | `clic_enlace` (T1566.002) 8 · `IA_ENGANADA` 8 · `incidente_abierto` 7 · `FALLO_SEGURO` 7 |
| 5-6 | `pdf_abierto` (T1566.001) 6 · `autorizacion_denegada` 6 · `ataque_ia_lanzado` 5 · `clic_bloqueado` 5 |
| 3-4 | Acciones defensivas de Azul (4), actividad de correo, misiones, práctica y fin de partida (3) |

## Cómo conectarlo (cuando haya un Wazuh)

1. En la máquina del laboratorio, con el agente de Wazuh instalado, añade el contenido de `ossec_localfile.xml` a
   `ossec.conf` y corrige la ruta a `data/eventos.jsonl`. Reinicia el agente.
2. En el manager, añade el contenido de `local_rules.xml` a `/var/ossec/etc/rules/local_rules.xml`. Reinicia el
   manager (`systemctl restart wazuh-manager`).
3. Prueba con `/var/ossec/bin/wazuh-logtest`: pega una línea de `eventos_ejemplo.jsonl` y comprueba la regla y el
   nivel. Deberían coincidir con lo que imprime `test_reglas.py`.
4. Juega una partida y busca `rule.groups: cybershield` en el panel.

**Requisitos supuestos (sin verificar):** Wazuh 4.x, porque `same_field` en la regla de correlación necesita una
versión reciente. Las reglas usan `<field>` con OS_Regex y solo `^`, `$` y `|`. Si el agente está en otra máquina,
el archivo debe ser legible por él (el laboratorio solo escribe en local).

## Qué está comprobado y qué no

`python integraciones/wazuh/test_reglas.py` (también lo ejecuta `python ejecutar_pruebas.py`):

- **Comprobado:**
  - los XML son válidos, los ids son únicos y del rango local, y todas las referencias existen;
  - cada uno de los 26 tipos tiene regla propia: si alguien añade un tipo a `EVENTOS_SIEM` sin regla, la prueba
    falla;
  - las descripciones solo usan campos del contrato;
  - en una **simulación aproximada** (decodificador JSON, expresiones regulares y descenso por `if_sid`), cada
    evento real de la muestra cae en su regla con el nivel esperado.
- **No comprobado:**
  - el comportamiento real de Wazuh (orden exacto de evaluación de las reglas hijas, OS_Regex frente a las
    expresiones regulares de Python, decodificación de los `null`);
  - la regla de correlación 100136;
  - el envío del agente al manager y los paneles.

  Todo eso requiere un Wazuh real y `wazuh-logtest`.
- **Seguridad:** el JSONL contiene datos ficticios del laboratorio (usuarios semilla, ids de correos, resultados);
  ninguna contraseña ni secreto real.
