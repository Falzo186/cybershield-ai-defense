# Nova: IA Roja vs IA Azul con Ollama REAL

Generado por `experimentos/prueba_ollama_ia_vs_ia.py`: 48 partidas, ambos equipos con un 8B en modo libre y `auto` (sin guion humano), 2 Azules en la sala, duración 600 s de partida. Datos: `data/nova_ollama_ia_vs_ia.json`.

| Rojo | Azul | Modalidad | Partidas | Rojo gana | Azul gana | Empate | Error | % Rojo |
|---|---|---|---|---|---|---|---|---|
| qwen3:8b | qwen3:8b | BALANCED | 4 | 0 | 0 | 4 | 0 | 0 % |
| qwen3:8b | qwen3:8b | RED_ADVANTAGE | 4 | 0 | 0 | 4 | 0 | 0 % |
| qwen3:8b | qwen3:8b | BLUE_ADVANTAGE | 4 | 0 | 0 | 4 | 0 | 0 % |
| llama3.1:8b | llama3.1:8b | BALANCED | 4 | 0 | 0 | 4 | 0 | 0 % |
| llama3.1:8b | llama3.1:8b | RED_ADVANTAGE | 4 | 0 | 0 | 4 | 0 | 0 % |
| llama3.1:8b | llama3.1:8b | BLUE_ADVANTAGE | 4 | 0 | 0 | 4 | 0 | 0 % |
| qwen3:8b | llama3.1:8b | BALANCED | 4 | 0 | 0 | 4 | 0 | 0 % |
| qwen3:8b | llama3.1:8b | RED_ADVANTAGE | 4 | 0 | 0 | 4 | 0 | 0 % |
| qwen3:8b | llama3.1:8b | BLUE_ADVANTAGE | 4 | 0 | 0 | 4 | 0 | 0 % |
| llama3.1:8b | qwen3:8b | BALANCED | 4 | 0 | 0 | 4 | 0 | 0 % |
| llama3.1:8b | qwen3:8b | RED_ADVANTAGE | 4 | 0 | 0 | 4 | 0 | 0 % |
| llama3.1:8b | qwen3:8b | BLUE_ADVANTAGE | 4 | 0 | 0 | 4 | 0 | 0 % |

**Total:** 48 partidas · Rojo 0 · Azul 0 · Empate 48 · Error técnico 0.

## Límites
- Muestras pequeñas (n por celda en la tabla), exploratorio: no es una probabilidad estable.
- Los dos equipos son modelos 8B sin calibrar, con prompts v1; no refleja a jugadores humanos.
- El Azul de IA decide solo (auto); en una partida real los humanos votan las autorizaciones.

## Resultado y cómo leerlo
- **48 de 48 partidas terminaron en EMPATE**: el Rojo no extrajo ninguna tabla (0 de 48) y el Azul no logró una victoria por contención (0 de 48). Las tres modalidades dan el mismo resultado: con estos dos 8B en modo libre **no se puede estimar una probabilidad de victoria del Rojo; el dato es «0 victorias de cualquiera»**.
- Propuestas válidas: Rojo 1344 de 1344; Azul 1344 de 1344. Ejecutadas por el motor: Rojo 258 de 1344 (19 %); Azul 450 de 1344 (33 %). Los modelos hacen propuestas válidas pero casi nunca encadenan la ruta que gana (correo → credencial → extracción) por sí solos.
- **Limitación importante:** cada partida corrió 14 turnos de 20 s (≈ 280 s de partida) y se detuvo con `detener()`, por lo que el EMPATE es por **corte del experimento**, no por fin natural de los 600 s. Una corrida más larga podría cambiar el resultado. No se repitió por falta de tiempo.
- Coherente con lo medido antes: con un humano que arma las directivas (combos) el Rojo sí gana por el camino que el motor permite (`docs/evaluacion/NOVA_OLLAMA_DIRECTIVAS.md`); la IA sola, no.
