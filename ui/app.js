"use strict";
// Estado global, modos y enlace evento -> render.
(() => {
  const $ = (id) => document.getElementById(id);
  const AGENTES = ["ATTACKER", "DEFENDER", "POLICY", "DATABASE", "SYSTEM"];
  const CLASE_TERM = { PERMITIR: "ok", SOLICITAR_AUTORIZACION: "warn", MARCAR_COMO_RIESGO: "warn", RECHAZAR: "bad", AISLAR: "bad" };

  const estado = {
    modo: "simulacion",
    corriendo: false,
    conexion: "reconectando",
    ataques: {},          // ronda -> evento ataque (para el historial)
    historialTerm: [],
    idxTerm: 0,
    metricas: null,
    ollama: { disponible: false, modelos: [] },
    origen: null,         // origen de los eventos de la ejecución en curso: "ollama" | "mock" | null
    manualReal: false,    // modo manual: false = MOCK, true = Ollama real
    contadores: { intentos: 0, exitosos: 0, bloqueados: 0, ia: 0 }, // se acumulan ronda a ronda (ERROR no cuenta)
    rondas: [],           // historial en memoria (se exporta a JSON)
  };

  // intentos +1 por ronda no-ERROR; exitosos solo en FALLA_DEFENSA; bloqueados en DEFENSA_EXITOSA / EN_PROFUNDIDAD.
  // ia (IA engañada) suma ia_fallo==true: incluye DEFENSA_EN_PROFUNDIDAD y FALLA_DEFENSA.
  function contarRonda(veredicto, iaFallo) {
    const c = estado.contadores;
    c.intentos += 1;
    if (iaFallo === true) c.ia += 1;
    if (veredicto === "FALLA_DEFENSA") c.exitosos += 1;
    if (veredicto === "DEFENSA_EXITOSA" || veredicto === "DEFENSA_EN_PROFUNDIDAD") c.bloqueados += 1;
    R.setContadores(c);
  }

  function registroBase(ronda) {
    const a = estado.ataques[ronda] || {};
    return {
      ronda, prompt_ataque: a.prompt || null, categoria: a.categoria || null,
      modelo_atq: a.modelo || null, origen: estado.origen || "mock",
      tiempos_ms: { atacante: typeof a.tiempo_ms === "number" ? a.tiempo_ms : null, defensor: null },
      tokens: { atacante: typeof a.tokens === "number" ? a.tokens : null, defensor: null },
    };
  }
  function registrarRonda(d) {
    const reg = Object.assign(registroBase(d.ronda), {
      decision_ia: d.decision_ia || d.decision, decision_efectiva: d.decision, riesgo: d.riesgo,
      veredicto: d.resultado, motivo: d.motivo || null, modelo_def: d.modelo || null, error: null,
      origen: d.origen || "mock", ia_fallo: d.ia_fallo === true,
    });
    reg.tiempos_ms.defensor = typeof d.tiempo_ms === "number" ? d.tiempo_ms : null;
    reg.tokens.defensor = typeof d.tokens === "number" ? d.tokens : null;
    estado.rondas.push(reg);
    return reg;
  }
  function registrarError(d) {
    const reg = Object.assign(registroBase(d.ronda), {
      decision_ia: null, decision_efectiva: null, riesgo: null, veredicto: "ERROR", motivo: null,
      modelo_def: null, modelo_error: d.modelo || null, error: d.error,
    });
    estado.rondas.push(reg);
    return reg;
  }

  function exportarHistorial() {
    if (!estado.rondas.length) { R.toast("Aún no hay rondas que exportar."); return; }
    const blob = new Blob([JSON.stringify(estado.rondas, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "historial-" + new Date().toISOString().replace(/[:.]/g, "-") + ".json";
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // Etiqueta de origen: solo dice OLLAMA en batalla y, mientras corre, únicamente si llegan eventos reales.
  function actualizarOrigen() {
    let r;
    if (!usaOllama()) r = ["🟡 MOCK", "origen-mock"];
    else if (estado.corriendo) {
      r = estado.origen === "ollama" ? ["🟢 OLLAMA", "origen-real"]
        : estado.origen === "mock" ? ["🟡 MOCK", "origen-mock"] : ["⏳ INICIANDO…", "origen-wait"];
    } else r = estado.ollama.disponible ? ["🟢 OLLAMA", "origen-real"] : ["🔴 SIN OLLAMA", "origen-off"];
    R.setOrigen(r[0], r[1]);
  }

  // El origen REAL aplica a la batalla y al manual con el interruptor en REAL.
  function usaOllama() { return estado.modo === "batalla" || (estado.modo === "manual" && estado.manualReal); }

  function aplicarControles() {
    const sinOllama = usaOllama() && !estado.ollama.disponible;
    R.setCorriendo(estado.corriendo, sinOllama, "Inicie Ollama");
  }

  function setCorriendo(c) {
    estado.corriendo = c;
    aplicarControles();
    actualizarOrigen();
  }

  function aplicarOllama(d) {
    estado.ollama = { disponible: !!d.disponible, modelos: Array.isArray(d.modelos) ? d.modelos : [] };
    R.setOllama(estado.ollama);
    aplicarControles();
    actualizarOrigen();
  }

  async function refrescarModelos() {
    try {
      const [e, m] = await Promise.all([API.ollamaEstado(), API.ollamaModelos()]);
      aplicarOllama({ disponible: e.disponible, modelos: m.modelos });
    } catch (_) {
      aplicarOllama({ disponible: false, modelos: [] }); // p. ej. servidor mock sin endpoints de Ollama
    }
  }

  async function cargarUsuarios() {
    try { R.setUsuarios((await API.usuarios()).usuarios || []); } catch (_) { R.setUsuarios([]); }
  }

  function aplicarMetricas(m) {
    estado.metricas = m; // los marcadores los acumula contarRonda(), no se pisan con la métrica del servidor
  }

  function reiniciarVista() {
    estado.ataques = {};
    estado.origen = null;
    R.resetPipeline();
    R.setVeredicto(null);
    R.setRonda(null);
    R.limpiarAtaque();
    R.limpiarDefensor();
    R.limpiarHistorial();
    estado.contadores = { intentos: 0, exitosos: 0, bloqueados: 0, ia: 0 };
    estado.rondas = [];
    R.setContadores(estado.contadores);
    R.setAtqEstado("EN ESPERA", false);
    R.setDefEstado("PROTEGIENDO BD", true);
  }

  function cambiarModo(modo) {
    if (estado.corriendo) return;
    estado.modo = modo;
    aplicarModo();
  }

  function aplicarModo() {
    R.setModo(estado.modo, estado.manualReal);
    aplicarControles();
    actualizarOrigen();
    if (usaOllama()) refrescarModelos();
  }

  function cambiarOrigenManual(real) {
    if (estado.corriendo) return;
    estado.manualReal = real;
    aplicarModo();
  }

  // ---------- eventos SSE ----------
  const handlers = {
    ollama_estado(d) { aplicarOllama(d); },
    ronda_inicio(d) {
      estado.origen = d.origen || "mock";
      actualizarOrigen();
      R.resetPipeline();
      R.setVeredicto(null);
      R.limpiarDefensor();
      R.setRonda(d.ronda, d.escenario_nombre, d.modo, estado.origen === "ollama" ? "OLLAMA" : "MOCK");
      R.setAtqEstado("ACTIVA", true);
      R.setDefEstado("ANALIZANDO", true);
    },
    ataque(d) {
      estado.ataques[d.ronda] = d;
      R.setAtaque(d);
    },
    etapa(d) { R.setEtapa(d.etapa, d.estado, d); },
    decision(d) {
      R.setVeredicto(d.decision, d.resultado);
      R.setDefensor(d);
      R.addHistorial(registrarRonda(d));
      contarRonda(d.resultado, d.ia_fallo);
      R.setAtqEstado("EN ESPERA", false);
      R.setDefEstado("PROTEGIENDO BD", true);
    },
    ronda_error(d) {
      R.setVeredictoError(d.modelo, d.error);
      R.addHistorial(registrarError(d)); // las rondas ERROR no cuentan en los marcadores
      R.setAtqEstado("EN ESPERA", false);
      R.setDefEstado("PROTEGIENDO BD", true);
    },
    auditoria(d) { R.addAuditoria(d); },
    metricas(d) { aplicarMetricas(d); },
    fin(d) {
      if (d.modo !== "manual") setCorriendo(false);
      R.setAtqEstado("EN ESPERA", false);
      R.setDefEstado("PROTEGIENDO BD", true);
      if (!d.detenido && d.metricas) R.mostrarModal(d.metricas, d.errores);
    },
    error(d) { R.toast(d.mensaje || "Error desconocido"); },
  };

  async function sincronizar() {
    try {
      const e = await API.estado();
      R.setInfo(e);
      if (e.corriendo !== estado.corriendo && e.modo !== "manual") setCorriendo(!!e.corriendo);
      aplicarMetricas(await API.metricas());
    } catch (_) { /* el indicador de conexión ya informa */ }
  }

  // ---------- acciones ----------
  async function iniciar() {
    if (estado.corriendo) return;
    if (estado.modo === "manual") { enviarManual(); return; }

    if (estado.modo === "batalla") {
      const atq = R.valorSelect("sel-atq"), def = R.valorSelect("sel-def"), usuario = R.valorSelect("sel-usuario");
      if (!atq || !def) { R.toast("Seleccione el modelo del atacante y el del defensor."); return; }
      if (!usuario) { R.toast("Seleccione el usuario de la sesión."); return; }
      const n = Math.max(1, Math.min(50, parseInt($("rondas").value, 10) || 6));
      const intensidad = Math.max(1, Math.min(3, parseInt(R.valorSelect("sel-intensidad"), 10) || 2));
      reiniciarVista();
      setCorriendo(true);
      try {
        await API.iniciarBatallaReal({ modelo_atq: atq, modelo_def: def, rondas: n, usuario, intensidad });
      } catch (e) {
        setCorriendo(false);
        R.toast(e.message);
      }
      return;
    }

    reiniciarVista();
    setCorriendo(true);
    try {
      await API.iniciarSimulacion();
    } catch (e) {
      setCorriendo(false);
      R.toast(e.message);
    }
  }

  async function detener() {
    try { await API.detener(); } catch (e) { R.toast(e.message); }
    setCorriendo(false);
    R.setAtqEstado("EN ESPERA", false);
    R.setDefEstado("PROTEGIENDO BD", true);
  }

  async function enviarManual() {
    const inp = $("term-input");
    const texto = inp.value.trim();
    if (!texto || estado.corriendo) return;
    const real = estado.manualReal;
    let cuerpoReal = null;
    if (real) {
      const modelo = R.valorSelect("sel-def"), usuario = R.valorSelect("sel-usuario");
      if (!estado.ollama.disponible) { R.toast("Inicie Ollama"); return; }
      if (!modelo || !usuario) { R.toast("Seleccione el modelo del defensor y el usuario."); return; }
      cuerpoReal = { prompt: texto, modelo_def: modelo, usuario };
    }
    estado.historialTerm.push(texto);
    estado.idxTerm = estado.historialTerm.length;
    inp.value = "";
    R.terminalAdd("usr", "> " + texto);
    R.terminalDatos(null);
    estado.ataques = {};
    estado.origen = null; // el origen lo fijan los eventos de ESTA petición
    setCorriendo(true);
    try {
      const d = real ? await API.manualReal(cuerpoReal) : await API.manual(texto);
      R.terminalAdd(CLASE_TERM[d.decision] || "ok",
        "[" + (real ? "REAL" : "MOCK") + "] [" + d.decision + "] riesgo " + d.riesgo + " — " + d.motivo +
        (real && d.resultado ? " → " + d.resultado : ""));
      if (Array.isArray(d.datos_devueltos)) R.terminalDatos(d.datos_devueltos);
    } catch (e) {
      R.terminalAdd("err", "Error: " + e.message);
    } finally {
      setCorriendo(false);
      inp.focus();
    }
  }

  // ---------- arranque ----------
  function init() {
    R.initPipeline();
    R.initAuditoria();
    R.limpiarDefensor();
    R.crearFiltros(AGENTES, (ag, on) => R.setFiltro(ag, on));
    R.setModo(estado.modo);
    R.setAtqEstado("EN ESPERA", false);
    R.setDefEstado("PROTEGIENDO BD", true);
    R.setOllama(estado.ollama);
    actualizarOrigen();

    document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => cambiarModo(t.dataset.modo)));
    document.querySelectorAll("[data-refrescar]").forEach((b) => b.addEventListener("click", refrescarModelos));
    $("btn-main").addEventListener("click", iniciar);
    $("btn-stop").addEventListener("click", detener);
    $("btn-export").addEventListener("click", exportarHistorial);
    document.querySelectorAll("[data-origen]").forEach((b) =>
      b.addEventListener("click", () => cambiarOrigenManual(b.dataset.origen === "real")));
    $("modal-cerrar").addEventListener("click", R.cerrarModal);
    $("modal").addEventListener("click", (ev) => { if (ev.target === $("modal")) R.cerrarModal(); });

    $("term-form").addEventListener("submit", (ev) => { ev.preventDefault(); enviarManual(); });
    $("term-input").addEventListener("keydown", (ev) => {
      const h = estado.historialTerm;
      if (ev.key === "ArrowUp" && h.length) {
        ev.preventDefault();
        estado.idxTerm = Math.max(0, estado.idxTerm - 1);
        ev.target.value = h[estado.idxTerm];
      } else if (ev.key === "ArrowDown" && h.length) {
        ev.preventDefault();
        estado.idxTerm = Math.min(h.length, estado.idxTerm + 1);
        ev.target.value = h[estado.idxTerm] || "";
      }
    });
    document.addEventListener("keydown", (ev) => {
      if (!R.modalAbierto()) return;
      if (ev.key === "Escape") R.cerrarModal();
      else if (ev.key === "Tab") { ev.preventDefault(); $("modal-cerrar").focus(); }
    });

    cargarUsuarios();
    API.conectar(handlers, (est) => {
      const antes = estado.conexion;
      estado.conexion = est;
      R.setConexion(est);
      if (est === "conectado" && antes !== "conectado") sincronizar();
    });
  }

  init();
})();
