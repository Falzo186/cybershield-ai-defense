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
    rol: null,            // "rojo" | "azul" | "general" | null (pantalla de selección de equipo)
    ollama: { atq: { disponible: false, modelos: [] }, def: { disponible: false, modelos: [] } }, // una Ollama por equipo
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
    } else r = ollamaListo() ? ["🟢 OLLAMA", "origen-real"] : ["🔴 SIN OLLAMA", "origen-off"];
    R.setOrigen(r[0], r[1]);
  }

  // El origen REAL aplica a la batalla y al manual con el interruptor en REAL.
  function usaOllama() { return estado.modo === "batalla" || (estado.modo === "manual" && estado.manualReal); }

  // La batalla necesita la Ollama del atacante Y la del defensor; el manual real solo la del defensor.
  function ollamaListo() {
    const o = estado.ollama;
    return estado.modo === "batalla" ? o.atq.disponible && o.def.disponible : o.def.disponible;
  }

  // IP/host de la Ollama de cada equipo ("atq" | "def"), guardada solo en ESTE navegador.
  function hostDe(rol) {
    return $("host-" + (rol === "def" ? "def" : "atq")).value.trim() || HOST_DEFECTO;
  }

  function aplicarControles() {
    const sinOllama = usaOllama() && !ollamaListo();
    R.setCorriendo(estado.corriendo, sinOllama, "Inicie Ollama");
  }

  function setCorriendo(c) {
    estado.corriendo = c;
    aplicarControles();
    actualizarOrigen();
  }

  function aplicarOllama(rol, d) {
    estado.ollama[rol] = { disponible: !!d.disponible, modelos: Array.isArray(d.modelos) ? d.modelos : [] };
    R.setOllama(rol, estado.ollama[rol]);
    aplicarControles();
    actualizarOrigen();
  }

  // Consulta la Ollama del equipo (atq|def) en SU host; avisar=true muestra el resultado (botón "Probar conexión").
  async function consultarHost(rol, avisar) {
    const host = hostDe(rol);
    LS.set(rol === "def" ? "cs_host_def" : "cs_host_atq", host);
    try {
      const e = await API.ollamaEstado(host);
      const m = e.disponible ? await API.ollamaModelos(host) : { modelos: [] };
      aplicarOllama(rol, { disponible: e.disponible, modelos: m.modelos });
      if (avisar) {
        R.toast(e.disponible ? "Conexión OK con " + host + " · " + m.modelos.length + " modelo(s)"
          : "Sin conexión con " + host + ". ¿Ollama abierto y expuesto en la red (OLLAMA_HOST=0.0.0.0)?");
      }
    } catch (err) {
      aplicarOllama(rol, { disponible: false, modelos: [] }); // p. ej. servidor mock sin endpoints de Ollama
      if (avisar) R.toast(err.message);
    }
  }

  function refrescarModelos() {
    return Promise.all([consultarHost("atq"), consultarHost("def")]);
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
    // El estado difundido es el de la Ollama por defecto del servidor: solo se aplica si coincide con el host de este equipo.
    ollama_estado(d) {
      if (d.host && d.host === hostDe("atq")) aplicarOllama("atq", d);
      if (d.host && d.host === hostDe("def")) aplicarOllama("def", d);
    },
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
        await API.iniciarBatallaReal({
          modelo_atq: atq, modelo_def: def, rondas: n, usuario, intensidad,
          host_atacante: hostDe("atq"), host_defensor: hostDe("def"),
        });
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
      if (!ollamaListo()) { R.toast("Inicie Ollama"); return; }
      if (!modelo || !usuario) { R.toast("Seleccione el modelo del defensor y el usuario."); return; }
      cuerpoReal = { prompt: texto, modelo_def: modelo, usuario, host_atacante: hostDe("atq"), host_defensor: hostDe("def") };
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

  // ---------- equipo (rol) y persistencia local ----------
  const ROLES = ["rojo", "azul", "general"];
  const HOST_DEFECTO = "http://localhost:11434";
  // Auditoría inicial por equipo (los toggles siguen siendo editables).
  const FILTROS_POR_ROL = { rojo: ["ATTACKER", "SYSTEM"], azul: ["DEFENDER", "POLICY", "SYSTEM"] };
  const LS = {
    get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* almacenamiento bloqueado */ } },
  };

  // ?rol=rojo|azul|general (o el último elegido en este navegador). ?cambiar=1 fuerza la pantalla de selección.
  function resolverRol() {
    const p = new URLSearchParams(location.search);
    if (p.has("cambiar")) return null;
    let rol = p.get("rol");
    if (!ROLES.includes(rol)) {
      rol = LS.get("cs_rol");
      if (!ROLES.includes(rol)) return null;
      try { history.replaceState(null, "", "?rol=" + rol); } catch (_) { /* sin history */ }
    }
    return rol;
  }

  function elegirEquipo(rol) {
    if (!ROLES.includes(rol)) return;
    LS.set("cs_rol", rol);
    location.href = location.pathname + "?rol=" + rol; // recarga con la vista elegida
  }

  // ---------- arranque ----------
  function init() {
    estado.rol = resolverRol();
    R.setEquipo(estado.rol);
    R.mostrarSelector(!estado.rol);
    document.querySelectorAll("[data-equipo]").forEach((b) => b.addEventListener("click", () => elegirEquipo(b.dataset.equipo)));
    $("host-atq").value = LS.get("cs_host_atq") || HOST_DEFECTO;
    $("host-def").value = LS.get("cs_host_def") || HOST_DEFECTO;
    ["atq", "def"].forEach((rol) => $("host-" + rol).addEventListener("change",
      () => LS.set(rol === "def" ? "cs_host_def" : "cs_host_atq", hostDe(rol))));
    document.querySelectorAll("[data-probar]").forEach((b) => b.addEventListener("click", () => consultarHost(b.dataset.probar, true)));

    R.initPipeline();
    R.initAuditoria();
    R.limpiarDefensor();
    R.crearFiltros(AGENTES, (ag, on) => R.setFiltro(ag, on), FILTROS_POR_ROL[estado.rol]);
    R.setModo(estado.modo);
    R.setAtqEstado("EN ESPERA", false);
    R.setDefEstado("PROTEGIENDO BD", true);
    R.setOllama("atq", estado.ollama.atq);
    R.setOllama("def", estado.ollama.def);
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
