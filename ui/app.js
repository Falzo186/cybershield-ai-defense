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
    marcador: { atacante: 0, defensor: 0 },  // puntaje de la partida (lo envía el servidor en cada decisión)
    reto: null,           // reto pendiente de aceptación (evento reto_enviado)
    enviandoReto: false,  // evita doble clic mientras el servidor valida y emite el reto
    ultimaFin: null,      // {m, e}: métricas de la última batalla real (para «Ver métricas»)
    cuenta: null,         // intervalo de la cuenta atrás del reto
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
      nivel_fuga: d.nivel_fuga || "NINGUNA", circuito_sesion: d.circuito_sesion === true,
      riesgo_acumulado: typeof d.riesgo_acumulado === "number" ? d.riesgo_acumulado : null,
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
    mostrarSospecha(0, false); // nueva sesión: el riesgo acumulado vuelve a 0
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
      if (d.modo !== "manual" && !estado.corriendo) setCorriendo(true); // otro equipo inició la partida
      mostrarAsignacion(d.asignacion || null);
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
      if (typeof d.riesgo_acumulado === "number") mostrarSospecha(d.riesgo_acumulado, d.circuito_sesion === true);
      if (d.circuito_sesion) R.toast("🔒 Autorización forzada por patrón de sesión sospechoso (capa determinista, no la IA)");
      if (d.marcador) {
        estado.marcador = d.marcador;
        R.setMarcador(d.marcador.atacante, d.marcador.defensor);
      }
      R.setAtqEstado("EN ESPERA", false);
      R.setDefEstado("PROTEGIENDO BD", true);
    },
    ronda_error(d) {
      R.setVeredictoError(d.modelo, d.error);
      R.addHistorial(registrarError(d)); // las rondas ERROR no cuentan en los marcadores
      R.setAtqEstado("EN ESPERA", false);
      R.setDefEstado("PROTEGIENDO BD", true);
    },
    // --- listo / aceptar entre equipos ---
    reto_enviado(d) {
      estado.reto = d;
      if (d.a_rol && d.a_rol === estado.rol) { // soy el destinatario: modal + sonido + cuenta atrás
        R.mostrarReto(true, d);
        beep();
        iniciarCuenta(d.segundos || 30);
      }
    },
    reto_respondido(d) {
      const demo = !!(estado.reto && estado.reto.demo);
      limpiarReto();
      if (d.aceptado) { // arranca la partida en todos los equipos
        reiniciarVista();
        estado.marcador = { atacante: 0, defensor: 0 };
        R.setMarcador(0, 0);
        R.setDemo(demo); // demostración: etiqueta visible y sin marcador
        R.cerrarPartida();
        setCorriendo(true);
      }
    },
    reto_cancelado(d) {
      limpiarReto();
      R.toast("Reto cancelado: " + (d.motivo || "sin respuesta"));
    },
    partida_fin(d) { R.mostrarPartida(d, !!estado.ultimaFin); },
    auditoria(d) { R.addAuditoria(d); },
    metricas(d) { aplicarMetricas(d); },
    fin(d) {
      if (d.modo !== "manual") setCorriendo(false);
      R.setAtqEstado("EN ESPERA", false);
      R.setDefEstado("PROTEGIENDO BD", true);
      if (d.metricas) estado.ultimaFin = { m: d.metricas, e: d.errores };
      // En batalla real el cierre lo muestra el banner de partida (partida_fin), con «Ver métricas».
      // (la demostración no genera partida_fin: sus métricas se muestran directamente)
      if (!d.detenido && d.metricas && (d.origen !== "ollama" || d.demo)) R.mostrarModal(d.metricas, d.errores);
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
      // Cada equipo envía SOLO su lado (rojo = atacante, azul = defensor); la vista general envía ambos.
      const lado = estado.rol === "rojo" || estado.rol === "azul" ? estado.rol : "general";
      const atq = R.valorSelect("sel-atq"), def = R.valorSelect("sel-def");
      if ((lado !== "azul" && !atq) || (lado !== "rojo" && !def)) {
        R.toast(lado === "general" ? "Seleccione el modelo del atacante y el del defensor." : "Seleccione el modelo de su equipo.");
        return;
      }
      if (estado.enviandoReto || estado.reto) { R.toast("Ya hay un reto pendiente."); return; }
      const n = Math.max(1, Math.min(50, parseInt($("rondas").value, 10) || 6));
      const intensidad = Math.max(1, Math.min(3, parseInt(R.valorSelect("sel-intensidad"), 10) || 2));
      const demo = $("chk-demo").checked; // admin: acceso legítimo por diseño -> sin puntaje
      const dificultad = R.valorSelect("sel-dificultad") || "facil";
      estado.enviandoReto = true;
      try {
        // No arranca de inmediato: el servidor emite el reto y espera la aceptación del otro equipo (30 s).
        const r = await API.iniciarBatallaReal({
          rondas: n, intensidad, demo, de_rol: lado,
          dificultad: demo ? undefined : dificultad,
          modelo_atq: lado !== "azul" ? atq : undefined, host_atacante: lado !== "azul" ? hostDe("atq") : undefined,
          modelo_def: lado !== "rojo" ? def : undefined, host_defensor: lado !== "rojo" ? hostDe("def") : undefined,
        });
        if (r && r.estado === "esperando_aceptacion") {
          R.mostrarEspera("⏳ Esperando que el EQUIPO " + (r.reto.a_rol === "rojo" ? "ROJO" : "AZUL") + " acepte el combate…");
        }
      } catch (e) {
        R.toast(e.message);
      } finally {
        estado.enviandoReto = false;
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

  // Muestra en el Centro de Control el modelo+host que el servidor asignó REALMENTE a cada rol en esta batalla.
  function hostCorto(h) { return String(h || "?").replace(/^https?:\/\//, "").replace(/:11434$/, ""); }
  function mostrarAsignacion(a) {
    let n = $("asignacion");
    if (!n) {
      n = document.createElement("div");
      n.id = "asignacion";
      n.className = "kv mono";
      n.setAttribute("role", "status");
      $("pipeline").before(n);
    }
    n.hidden = !a;
    if (a) {
      n.textContent = "Atacante: " + a.atacante.modelo + " @ " + hostCorto(a.atacante.host) +
        " · Defensor: " + a.defensor.modelo + " @ " + hostCorto(a.defensor.host);
      // Vista de solo lectura del equipo contrario: el servidor ya verificó ambos modelos antes de la ronda.
      $("ro-atq-txt").textContent = "🟢 " + a.atacante.modelo + " @ " + hostCorto(a.atacante.host);
      $("ro-def-txt").textContent = "🟢 " + a.defensor.modelo + " @ " + hostCorto(a.defensor.host);
    }
  }

  // Indicador persistente del «Nivel de sospecha de la sesión» (0-100; verde <30, ámbar 30-70, rojo >70).
  function mostrarSospecha(valor, circuito) {
    let caja = $("sospecha");
    if (!caja) {
      caja = document.createElement("div");
      caja.id = "sospecha";
      caja.className = "sospecha";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = "NIVEL DE SOSPECHA DE LA SESIÓN";
      const barra = document.createElement("div");
      barra.className = "sospecha-barra";
      const relleno = document.createElement("div");
      relleno.id = "sospecha-relleno";
      barra.append(relleno);
      const txt = document.createElement("span");
      txt.id = "sospecha-txt";
      txt.className = "mono";
      caja.append(lbl, barra, txt);
      $("pipeline").before(caja);
    }
    const v = Math.max(0, Math.min(100, Math.round(valor)));
    const zona = v > 70 ? "rojo" : v >= 30 ? "ambar" : "verde";
    $("sospecha-relleno").style.width = v + "%";
    $("sospecha-relleno").className = "sospecha-" + zona;
    $("sospecha-txt").textContent = v + "/100" + (v > 70 ? " · circuito de sesión ACTIVO" : "") +
      (circuito ? " · 🔒 autorización forzada en esta ronda" : "");
  }

  // ---------- listo / aceptar, sonido, diagnóstico de modelo ----------
  function beep() { // aviso sonoro generado con Web Audio (sin archivos); puede bloquearlo el navegador sin interacción previa
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.value = 0.15;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
      setTimeout(() => ctx.close(), 600);
    } catch (_) { /* sin audio */ }
  }

  function iniciarCuenta(seg) {
    clearInterval(estado.cuenta);
    let s = seg;
    R.setCuenta(s);
    estado.cuenta = setInterval(() => {
      s -= 1;
      R.setCuenta(s);
      if (s <= 0) clearInterval(estado.cuenta);
    }, 1000);
  }

  function limpiarReto() {
    estado.reto = null;
    clearInterval(estado.cuenta);
    R.mostrarReto(false);
    R.mostrarEspera(null);
  }

  async function responderReto(aceptado) {
    R.mostrarReto(false);
    clearInterval(estado.cuenta);
    // Al aceptar, se envía el modelo+host que este equipo tiene en su panel AHORA (no uno guardado de antes).
    const propio = estado.rol === "rojo" ? { modelo: R.valorSelect("sel-atq"), host: hostDe("atq") }
      : estado.rol === "azul" ? { modelo: R.valorSelect("sel-def"), host: hostDe("def") } : {};
    try {
      await API.responderReto(aceptado, estado.rol || undefined, propio.modelo || undefined, propio.host || undefined);
    } catch (e) { R.toast(e.message); }
  }

  // Revancha: cierra el resultado y vuelve a pedir listo/aceptar con la misma configuración.
  function revancha() {
    R.cerrarPartida();
    estado.marcador = { atacante: 0, defensor: 0 };
    R.setMarcador(0, 0);
    iniciar();
  }

  // «Probar modelo»: llamada mínima real al modelo elegido en el host de ese equipo (tiempo real o error exacto).
  async function probarModelo(rol) {
    const modelo = R.valorSelect(rol === "def" ? "sel-def" : "sel-atq");
    if (!modelo) { R.setProbe(rol, "Elige un modelo (usa antes «Probar conexión»).", false); return; }
    R.setProbe(rol, "⏳ probando " + modelo + "…", null);
    try {
      const r = await API.ollamaProbar(hostDe(rol), modelo, rol === "def" ? "azul" : "rojo");
      const seg = (r.tiempo_ms / 1000).toFixed(2) + " s";
      R.setProbe(rol, r.ok ? "✓ " + modelo + " respondió en " + seg + (r.respuesta ? " · «" + r.respuesta + "»" : "")
        : "✕ " + (r.error || "error desconocido") + " (" + seg + ")", !!r.ok);
    } catch (e) {
      R.setProbe(rol, "✕ " + e.message, false);
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
    document.querySelectorAll("[data-probar-modelo]").forEach((b) => b.addEventListener("click", () => probarModelo(b.dataset.probarModelo)));
    $("chk-demo").addEventListener("change", () => {
      $("sel-dificultad").disabled = $("chk-demo").checked;
      R.setDemo($("chk-demo").checked);
      if (!$("chk-demo").checked) R.setMarcador(0, 0);
    });
    $("reto-aceptar").addEventListener("click", () => responderReto(true));
    $("reto-rechazar").addEventListener("click", () => responderReto(false));
    $("partida-revancha").addEventListener("click", revancha);
    $("partida-cerrar").addEventListener("click", R.cerrarPartida);
    $("partida-metricas").addEventListener("click", () => {
      if (estado.ultimaFin) { R.cerrarPartida(); R.mostrarModal(estado.ultimaFin.m, estado.ultimaFin.e); }
    });
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && R.partidaAbierta()) R.cerrarPartida(); });

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
