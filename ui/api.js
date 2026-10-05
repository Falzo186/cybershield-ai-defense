"use strict";
// Capa de acceso al contrato (docs/CONTRATO_API.md): REST + SSE con reconexión automática.
const API = (() => {
  async function req(method, url, body) {
    const opts = { method, headers: {} };
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
    "ollama_estado", "ronda_error"];

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
    conectar,
  };
})();
