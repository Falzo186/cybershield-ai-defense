# Para Jesús — checklist antes de dejar la PC (mañana 3 pm)

Este archivo es para ti, no para Claude Code.

## 1. Preparar el entorno (30–40 min antes)
- [ ] Copia esta carpeta dentro del proyecto como `MISION_23H/` (en la raíz del repo `cybershield-ai-defense`).
- [ ] **Copia de seguridad manual**: duplica TODA la carpeta del proyecto (p. ej. `cybershield-ai-defense_RESPALDO_18nov`). Es tu red de seguridad real.
- [ ] `git status` limpio: haz commit de lo pendiente en tu rama actual antes de arrancar.
- [ ] Ollama instalado y corriendo (`ollama list`). Deja ≥ 40 GB libres en disco (los modelos de 8B pesan ~5 GB cada uno). Si ya tienes qwen3:8b o llama3.1:8b, mejor.
- [ ] Cierra juegos, navegadores pesados y cualquier cosa que use la GPU.

## 2. Que la PC no se duerma ni se reinicie (Windows)
- [ ] Conectada al cargador. Plan de energía: **nunca suspender / nunca apagar pantalla si te da seguridad**, y "Suspender: Nunca" en batería y conectado.
- [ ] Pausa las actualizaciones de Windows por 7 días (Configuración → Windows Update → Pausar).
- [ ] Desactiva protectores de pantalla con bloqueo.
- [ ] Internet estable (la sesión de Claude Code necesita conexión las 23 h).

## 3. Créditos y permisos
- [ ] Verifica que tengas el 100 % de créditos semanales al arrancar. 23 h continuas pueden gastar mucho; no puedo ver tu saldo, revísalo tú.
- [ ] Para que trabaje sin pedirte permisos necesitas un modo de permisos amplio en Claude Code (p. ej. aceptar ediciones y comandos automáticamente). Eso es decisión tuya: si lo activas, el respaldo del punto 1 es indispensable. Las reglas de la misión prohíben push y borrar históricos, pero **son reglas del prompt, no un candado técnico**. Si quieres un candado real, desconecta temporalmente el remoto (`git remote -v` y anota la URL antes) o cierra sesión de GitHub en la PC.

## 4. Arranque
En la terminal, dentro de la carpeta del proyecto, abre Claude Code y pega el contenido de `MISION_23H/PROMPT_DE_ARRANQUE.txt`. Revisa los primeros 10–15 minutos: que haya leído la carpeta, creado la rama `mision-23h` y escrito `ESTADO_MISION.md`. Después puedes irte.

## 5. Al volver
- Lee `docs/INFORME_EJECUTIVO_FINAL.md` y `ESTADO_MISION.md`.
- Revisa `BLOQUEOS.md` y `git log` en la rama `mision-23h`.
- Nada se fusionó a `main` ni se subió a GitHub: decides tú tras revisar.

## Expectativas realistas
23 h de IA autónoma pueden producir mucho, pero también pueden quedarse atoradas o gastar créditos en bucles. El plan tiene reglas anti-bucle (3 intentos), puntos de control y recorte de alcance. Aun así, algunos resultados pueden salir "malos" con modelos de 8B (por ejemplo, que el Rojo casi nunca gane): eso es un resultado válido y está contemplado en el plan.
