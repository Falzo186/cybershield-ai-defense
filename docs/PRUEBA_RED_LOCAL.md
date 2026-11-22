# Prueba en red local con un compañero (Nova)

Verificado en esta máquina el 2026-11-22: el servidor responde por la IP de red (`http://192.168.100.10:PUERTO/nova/` → 200) y existen reglas de firewall de entrada para `python.exe` en el perfil Privado. **NO verificado:** que otro equipo llegue a esa IP (por eso esta prueba).

## Quién hace qué
| Quién | Qué hace | Dirección |
|---|---|---|
| **Tú (host)** | Lanza el servidor y entra como Administrador | `http://localhost:8000/nova/` |
| **Tu compañero** | Solo abre el navegador; no instala nada | `http://192.168.100.10:8000/nova/` (la IP del host) |

> Ambos equipos deben estar en la **misma red** (misma Wi-Fi o mismo router). Si la IP de tu máquina cambió, ejecuta `ipconfig` y usa la dirección IPv4 del adaptador que está en la red de tu compañero (la `192.168.56.1` es de VirtualBox y no sirve).

## Pasos
1. Tú: en la carpeta del proyecto, ejecuta (deja la ventana abierta; anota el **Código de árbitro** que imprime):
```powershell
python server/app.py
```
2. Tu compañero: abre `http://192.168.100.10:8000/nova/`. Si no carga: ver «Si no conecta».
3. Tú: entra como **Administrador (General)** con tu nombre y el código de árbitro. Crea la partida (modo de autorizaciones «Votación»), abre la sala de espera.
4. Tu compañero: entra con su nombre y el equipo (Rojo o Azul) y pulsa «Unirme». Tú puedes unirte desde otra pestaña como el otro equipo.
5. Prueba sugerida (5 min): el Rojo envía un correo a una identidad Azul; el Azul revisa su bandeja; el Rojo intenta una credencial parecida (aviso «solicitud misteriosa» al Azul); el Azul vota; el administrador inicia, pausa y detiene. Abre el panel «Jugadores» en ambos.
6. Para probar la IA: el administrador pone la IA de un equipo en `assist`; el jugador arma el prompt con los combos.

## Si no conecta
- Misma red y misma subred (`192.168.100.x`). Prueba `ping 192.168.100.10` desde el equipo de tu compañero.
- Firewall (PowerShell **como administrador** en tu máquina), solo si no abre:
```powershell
New-NetFirewallRule -DisplayName "CyberShield 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```
- Otro puerto: `$env:PUERTO = "8010"; python server/app.py` (y usa ese puerto en las dos direcciones).

## Qué anotar (para cerrar los criterios 14 y 33)
Si el compañero entra, ve la lista de jugadores, juega su equipo y los dos ven los mismos cambios, el criterio 33 pasa a APROBADO con evidencia. El criterio 14 (modelos en dos PCs) exige además que él ejecute Ollama y configures su endpoint (`http://IP:11434`, con `OLLAMA_HOST=0.0.0.0`).
