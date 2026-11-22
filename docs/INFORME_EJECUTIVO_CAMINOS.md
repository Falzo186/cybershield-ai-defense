# Informe ejecutivo — misión Caminos

Fecha: 2026-11-21 · Rama `mision-caminos` (desde `mision-extra`, etiqueta `pre-mision-caminos`) · Proyecto: CyberShield AI Defense (laboratorio académico, 100 % local y ficticio). No reescribe los informes anteriores.

## 1. Qué se hizo
- **Modo Caminos:** grafo de decisión fijo con **16 recorridos (8 victorias Rojas y 8 Azules)**, 3 reversiones («parece ganar el Rojo y gana el Azul») y 3 giros del Rojo, en 3 dificultades, con validador automático (sin estados muertos ni ciclos, evidencia de estado exigida para toda victoria, el Rojo no ve la validez de las credenciales). Sin autoaprendizaje ni memoria entre partidas.
- **Motor** con auditoría de hashes, resultado inmutable, grafo congelado por hash, y tres tipos de procedencia visibles: `LIBRE_IA`, `CAMINOS_IA`, `CAMINOS_GUION`.
- **Modo automático de credenciales:** Rojo 8B contra Azul 8B con 8 credenciales ficticias fijas (3 válidas, 3 inválidas, 2 señuelo), bloqueo a los 3 fallos, alertas Wazuh **simuladas**, tráfico legítimo intercalado; lanzable por CLI y desde la interfaz (solo árbitro).
- **Ventana Simulación (`/simulacion/`):** reproductor narrado de ≈ 10 min con paneles sincronizados y grafo; 9 grabaciones (6 de guion y 3 victorias Rojas **reales de 8B** de la campaña).
- **Campaña `caminos-v1`:** 2 062 partidas (2 052 válidas) con `qwen3:8b` y `llama3.1:8b`.

## 2. Resultados (con IC de Wilson al 95 %; detalle en `docs/evaluacion/INFORME_CAMINOS.md`)
- **Un 8B sí puede ganar como Rojo en este modo.** Grafo, cruzada: **Rojo `qwen3:8b` contra Azul `llama3.1:8b`: 97,7 % de victorias Rojas (43/44; IC 88–99,6 %)**, todas por la misma hoja (`H_R_giro_2f`: segundo factor obtenido por un correo que nadie reportó). Causa observable: el Azul `llama3.1:8b` **aprobó el segundo factor 88 de 88 veces** (nodo N1i4) sin cuestionar su procedencia.
- **El mismo grafo no es una puerta abierta:** `llama3.1:8b` como Rojo contra `qwen3:8b` como Azul: **0/42**; espejo en el grafo: **0/120 y 0/120**. El Azul `qwen3:8b` rechazó o pidió verificación en todos los nodos críticos (0 aprobaciones indebidas).
- **Contra Azules triviales:** «aprobar siempre» pierde ante cualquier Rojo (100 % de victorias Rojas, n = 36 por celda); «rechazar siempre» y el registro nunca entregan la base en el grafo.
- **Modo automático (espejo):** el Rojo 8B ganó **7,3 % (3/41) con qwen y 6,7 % (3/45) con llama** contra su propio modelo como Azul; el Rojo tiende a probar primero la credencial del administrador de respaldos (un señuelo) y pierde de inmediato. Con `qwen3:8b` como Azul frente a Rojos guionados el resultado fue **empate degradado 13/13**: sobre-rechaza al tráfico legítimo, igual que en el combate libre.
- **Honestidad de procedencia:** las 6 victorias Rojas de guion se muestran como «recorrido posible del grafo, NO victoria de un modelo»; solo las de `CAMINOS_IA` son victorias de un modelo, **y solo en este modo** (en el combate libre el Rojo 8B siguió en 0/540).

## 3. Defectos encontrados y corregidos
Un contrato de prueba mal planteado (contexto del Azul sin registro), un modo mal normalizado entre servidor e interfaz (`automatico`/`auto`), una carrera en la prueba E2E (resultado vs «qué enseña»), el inventario de credenciales de la interfaz que inventaba validez en la ruta de documento, y un 404 al sondear una partida lanzada aún en curso (ahora 202). Tres iteraciones visuales con capturas a 1366×768 y 1920×1080.

## 4. Pruebas
Batería completa: **42/42 suites · 1 953/1 953 comprobaciones** (línea base 37/39 · 1 885/1 887; +66 nuevas: motor 25, modo automático 17, interfaz E2E 24). Un guion por cada una de las 16 hojas (×3 variantes). Estas pruebas verifican el motor y la interfaz, **no** la calidad de ningún modelo.

## 5. Limitaciones y pendientes
- **Cruzada incompleta:** 86 de 204 planificadas; el modo automático cruzado casi no se jugó (la GPU se cedió al usuario). La campaña es reanudable.
- El resultado «97,7 % del Rojo qwen» es **específico de este grafo, estos prompts y este par de modelos**: es una vulnerabilidad medida del Azul `llama3.1:8b`, no una propiedad general de los 8B.
- Cinco nodos del Rojo tienen una única opción (el peso de la decisión está en el primer movimiento y en el Azul).
- Wazuh simulado; prompts `c1` sin calibrar; los contrastes tratan las muestras como independientes.
- Pendiente de decisión del usuario: alinear el proyecto con el paquete del profesor o retomar `Rebuilt` (ver `docs/ESTUDIO_PAQUETE_PROFESOR.md`).

## 6. Veredicto técnico honesto
**Funcional.** El modo Caminos cumple lo que se pidió: el Rojo tiene un camino genuino a la victoria, el Azul tiene contrajugadas genuinas, el motor decide y la procedencia siempre está a la vista. La evidencia empírica es mixta y se reporta tal cual: **sí hay victorias reales de un 8B**, pero dependen casi por completo de que el Azul sea `llama3.1:8b`; contra `qwen3:8b` el Rojo no gana. Sigue sin demostrarse que un 8B engañe a un defensor que verifica con texto libre.
