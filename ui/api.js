"use strict";
// Capa de acceso al contrato (docs/CONTRATO_API.md): REST + SSE con reconexión automática.
const API = (() => {
  let token = null; // token de equipo emitido por el servidor (sin token = espectador, solo lectura)

  async function req(method, url, body) {
    const opts = { method, headers: {} };
    if (token) opts.headers["X-Equipo-Token"] = token;
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(url, opts);
    let data = null;
    try { data = await r.json(); } catch (_) { /* cuerpo vacío */ }
    if (!r.ok) {
      const msg = data && (data.mensaje || data.error || data.detail);
      const err = new Error(msg ? (typeof msg === "string" ? msg : JSON.stringify(msg)) : "HTTP " + r.status);
      err.status = r.status;
      throw err;
    }
    return data;
  }

  const TIPOS = ["ronda_inicio", "ataque", "etapa", "decision", "auditoria", "metricas", "fin", "error",
    "ollama_estado", "ronda_error", "reto_enviado", "reto_respondido", "reto_cancelado", "partida_fin", "marcador_partida", "partida_finalizada",
    "partida_estado", "misiones_cambio", "incidentes_cambio", "credenciales_cambio", "ia_estado", "ia_ataque"];

  // handlers: {tipo: fn(data)}; onEstado("conectado"|"reconectando")
  function conectar(handlers, onEstado) {
    let es = null, intento = 0, timer = null, cerrado = false;

    function abrir() {
      es = new EventSource("/api/eventos");
      es.onopen = () => { intento = 0; onEstado("conectado"); };
      es.onerror = () => {
        if (es) { es.close(); es = null; }
        onEstado("reconectando");
        if (cerrado) return;
        const espera = Math.min(10000, 1000 * Math.pow(2, intento));
        intento += 1;
        timer = setTimeout(abrir, espera);
      };
      TIPOS.forEach((tipo) => {
        es.addEventListener(tipo, (ev) => {
          if (typeof ev.data !== "string") return; // el 'error' nativo de conexión no trae datos
          let datos;
          try { datos = JSON.parse(ev.data); } catch (_) { return; }
          if (handlers[tipo]) handlers[tipo](datos);
        });
      });
    }
    abrir();
    return { cerrar() { cerrado = true; clearTimeout(timer); if (es) es.close(); } };
  }

  return {
    setToken: (t) => { token = t || null; },
    // Sesión por participante: nombre visible + equipo (+ código si es el árbitro) -> {token, participante, partida}
    unirse: (nombre, equipo, codigo) => req("POST", "/api/sesion", { nombre, equipo, codigo: codigo || undefined }),
    miSesion: () => req("GET", "/api/sesion"),
    iniciarPartida: (duracion_min) => req("POST", "/api/partida/iniciar", { duracion_min }),
    nuevaPartida: () => req("POST", "/api/partida/nueva", {}),
    tieneToken: () => !!token,
    estado: () => req("GET", "/api/estado"),
    metricas: () => req("GET", "/api/metricas"),
    iniciarSimulacion: () => req("POST", "/api/simulacion/iniciar", {}),
    iniciarBatalla: (rondas) => req("POST", "/api/batalla/iniciar", { rondas }),
    iniciarBatallaReal: (cuerpo) => req("POST", "/api/batalla/real/iniciar", cuerpo),
    detener: () => req("POST", "/api/detener", {}),
    manual: (prompt) => req("POST", "/api/manual", { prompt }),
    manualReal: (cuerpo) => req("POST", "/api/manual/real", cuerpo),
    // host (opcional): Ollama de cualquier IP de la LAN, p. ej. http://192.168.1.50:11434
    ollamaEstado: (host) => req("GET", "/api/ollama/estado" + (host ? "?host=" + encodeURIComponent(host) : "")),
    ollamaModelos: (host) => req("GET", "/api/ollama/modelos" + (host ? "?host=" + encodeURIComponent(host) : "")),
    usuarios: () => req("GET", "/api/usuarios"),
    // Llamada mínima real a host/modelo -> {ok, tiempo_ms, respuesta, error}
    // rol ("rojo"|"azul"): si la prueba sale bien, el servidor guarda ese modelo+host como lo último confirmado del equipo.
    ollamaProbar: (host, modelo, rol) => req("GET", "/api/ollama/probar?modelo=" + encodeURIComponent(modelo) +
      (host ? "&host=" + encodeURIComponent(host) : "") + (rol ? "&rol=" + encodeURIComponent(rol) : "")),
    // modelo/host: lo que el equipo que acepta tiene en SU panel en este instante.
    responderReto: (aceptado, rol, modelo, host) => req("POST", "/api/batalla/responder", { aceptado, rol, modelo, host }),
    // Buzón de entrenamiento: Rojo envía desde una plantilla fija (para_usuario vacío = usuario del equipo azul).
    plantillasCorreo: () => req("GET", "/api/correo/plantillas"),
    enviarCorreo: (plantilla, para_usuario) => req("POST", "/api/correo", { plantilla, para_usuario: para_usuario || undefined }),
    buzon: () => req("GET", "/api/buzon"),
    // Solo Azul: acciones sobre un correo de su buzón y misiones -> {..., regla:{riesgo, misiones_completadas}}
    reportarCorreo: (id) => req("POST", "/api/correo/" + encodeURIComponent(id) + "/reportar", {}),
    contenerCorreo: (id) => req("POST", "/api/correo/" + encodeURIComponent(id) + "/contener", {}),
    misiones: () => req("GET", "/api/misiones"),
    // Fase D: aplicación de correo de Azul y seguimiento de Rojo (todo se valida en el servidor)
    leerCorreo: (id) => req("POST", "/api/correo/" + encodeURIComponent(id) + "/leer", {}),
    archivarCorreo: (id, archivar) => req("POST", "/api/correo/" + encodeURIComponent(id) + "/archivar", { archivar }),
    verificarRemitente: (id) => req("POST", "/api/correo/" + encodeURIComponent(id) + "/verificar", {}),
    inspeccionarEnlace: (id) => req("POST", "/api/correo/" + encodeURIComponent(id) + "/inspeccionar", {}),
    responderCorreo: (id, texto) => req("POST", "/api/correo/" + encodeURIComponent(id) + "/responder", { texto }),
    aislarAdjunto: (id) => req("POST", "/api/correo/" + encodeURIComponent(id) + "/aislar", {}),
    enviadosRojo: () => req("GET", "/api/correo/enviados"),
    // Fase E: misiones con responsable, incidentes y credencial ficticia (Azul)
    asumirMision: (id) => req("POST", "/api/misiones/" + encodeURIComponent(id) + "/asumir", {}),
    incidentes: () => req("GET", "/api/incidentes"),
    abrirIncidente: (titulo, severidad, correoId) => req("POST", "/api/incidentes",
      { titulo, severidad, correo_id: correoId == null ? null : correoId }),
    estadoIncidente: (id, estado, resolucion) => req("POST", "/api/incidentes/" + encodeURIComponent(id) + "/estado",
      { estado, resolucion: resolucion || null }),
    credenciales: () => req("GET", "/api/credenciales"),
    revocarCredencial: () => req("POST", "/api/credenciales/revocar", {}),
    finalizarPartida: () => req("POST", "/api/partida/finalizar", {}), // solo token general
    // Fase F: batalla de la partida. Rojo lanza ataques IA; Azul elige (y el servidor comprueba) su defensor.
    iaEstado: () => req("GET", "/api/ia/estado"),
    lanzarAtaqueIA: (modelo, host, tecnica, intensidad) => req("POST", "/api/ia/ataque",
      { modelo, host, tecnica: tecnica || null, intensidad }),
    configurarDefensorIA: (modelo, host) => req("POST", "/api/ia/defensor", { modelo, host }),
    // Fase B: aplicaciones por permiso (el catálogo y el acceso los decide el servidor)
    apps: (equipo) => req("GET", "/api/apps" + (equipo ? "?equipo=" + encodeURIComponent(equipo) : "")),
    archivos: () => req("GET", "/api/archivos"),
    seguridad: () => req("GET", "/api/seguridad"),
    recursos: () => req("GET", "/api/recursos"),
    ayuda: (equipo) => req("GET", "/api/ayuda" + (equipo ? "?equipo=" + encodeURIComponent(equipo) : "")),
    // Fase G: resultados con fórmulas, cronología filtrable e historial de partidas (lectura)
    partidas: () => req("GET", "/api/partidas"),
    resultados: (partida) => req("GET", "/api/resultados" + (partida ? "?partida=" + encodeURIComponent(partida) : "")),
    cronologia: (f) => req("GET", "/api/cronologia?" + new URLSearchParams(Object.entries(f || {})
      .filter(([, v]) => v !== "" && v != null && !(Array.isArray(v) && !v.length))
      .map(([k, v]) => [k, Array.isArray(v) ? v.join(",") : v])).toString()),
    // tipo "pdf_abierto" | "pdf_reportado" sobre el PDF adjunto del correo id -> {documento, regla, descarga|null}
    eventoPdf: (tipo, correoId) => req("POST", "/api/evento", { tipo, recurso: "correo:" + correoId }),
    completarMision: (id) => req("POST", "/api/misiones/" + encodeURIComponent(id) + "/completar", {}),
    conectar,
  };
})();
