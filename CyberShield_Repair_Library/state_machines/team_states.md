# Equipos y permisos (backend, `server/app.py::_verificar_sesion` + `SOLO_EQUIPO`)
Roles: `general` (administrador/árbitro), `rojo`, `azul`, `espectador`. El equipo sale del **token** emitido por el servidor, nunca del cliente.
- Sin sesión: solo GET públicos. Espectador: solo GET.
- Reservado al árbitro: iniciar, pausar, reanudar, finalizar, nueva, detener práctica.
- Reservado a Rojo: correos (plantilla y libre), ataque IA, crear solicitudes de autorización.
- Reservado a Azul: buzón, misiones, eventos de PDF, defensor IA, aprobar/rechazar solicitudes.
- Chat: cada equipo solo lee el suyo; el árbitro lee ambos; el espectador, ninguno.
Verificado: regresión 4, 7, 26, 27, 13–14 (403 al actuar fuera del propio equipo).
