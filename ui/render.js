"use strict";
// Solo pinta. Todo texto dinámico entra por textContent / createElement (nunca innerHTML).
const R = (() => {
  const $ = (id) => document.getElementById(id);
  const reduce = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function el(tag, cls, texto) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (texto !== undefined && texto !== null) n.textContent = String(texto);
    return n;
  }

  const ETAPAS = [
    ["atacante", "Atacante"], ["prompt", "Prompt"], ["analisis", "Análisis"], ["defensor", "Defensor"],
    ["politicas", "Políticas"], ["autorizacion", "Autorización"], ["herramienta", "Herramienta"], ["bd", "Base de datos"],
  ];
  const ESTADO_NODO = {
    pendiente: ["○", "PENDIENTE"], activo: ["◉", "ACTIVO"], ok: ["✓", "OK"],
    bloqueado: ["✕", "BLOQUEADO"], omitido: ["–", "OMITIDO"],
    ejecucion_real: ["✓", "EJECUCIÓN REAL"], error: ["⚠", "ERROR"],
  };
  const VEREDICTO = {
    PERMITIR: ["v-ok", "●", "PERMITIDA"],
    SOLICITAR_AUTORIZACION: ["v-warn", "◆", "REQUIERE AUTORIZACIÓN"],
    MARCAR_COMO_RIESGO: ["v-warn", "◆", "MARCADA COMO RIESGO"],
    RECHAZAR: ["v-bad", "■", "BLOQUEADA"],
    AISLAR: ["v-bad", "■", "AISLADA"],
  };
  const RESULTADO = {
    DEFENSA_EXITOSA: ["r-ok", "✓", "DEFENSA EXITOSA"],
    PERMITIDO_CORRECTO: ["r-ok", "●", "PERMITIDO CORRECTO"],
    FALSO_POSITIVO: ["r-warn", "◆", "FALSO POSITIVO"],
    FALLA_DEFENSA: ["r-bad", "✕", "VICTORIA DEL ATACANTE"],
    DEFENSA_EN_PROFUNDIDAD: ["r-depth", "◈", "IA ENGAÑADA · CAPAS CONTUVIERON"],
  };
  const SENS_ICONO = { PUBLICA: "○", INTERNA: "◐", CONFIDENCIAL: "◆", CRITICA: "▲" };

  // ---------- pipeline ----------
  function initPipeline() {
    const ol = $("pipeline");
    ol.replaceChildren();
    ETAPAS.forEach(([id, nombre]) => {
      const li = el("li", "nodo");
      li.dataset.etapa = id;
      li.append(el("span", "nodo-ico"), el("span", "nodo-nombre", nombre), el("span", "nodo-estado"), el("span", "nodo-det"));
      ol.append(li);
      pintarNodo(li, "pendiente");
    });
  }
  // extra (opcional): {detalle, modelo, tiempo_ms} -> línea "detalle · modelo · 1.82 s" bajo el nodo.
  function pintarNodo(li, estado, extra) {
    const [ico, txt] = ESTADO_NODO[estado] || ESTADO_NODO.pendiente;
    li.dataset.estado = estado;
    li.children[0].textContent = ico;
    li.children[2].textContent = txt;
    const partes = [];
    if (extra) {
      if (extra.detalle) partes.push(extra.detalle);
      if (extra.modelo) partes.push(extra.modelo);
      if (typeof extra.tiempo_ms === "number") partes.push((extra.tiempo_ms / 1000).toFixed(2) + " s");
    }
    li.children[3].textContent = partes.join(" · ");
  }
  function resetPipeline() { $("pipeline").querySelectorAll(".nodo").forEach((li) => pintarNodo(li, "pendiente")); }
  function setEtapa(etapa, estado, extra) {
    const li = $("pipeline").querySelector('.nodo[data-etapa="' + CSS.escape(String(etapa)) + '"]');
    if (li) pintarNodo(li, estado, extra);
  }

  // ---------- ronda / veredicto ----------
  function setRonda(num, nombre, modo, origen) {
    $("ronda-num").textContent = num === null ? "00" : String(num).padStart(2, "0");
    $("ronda-esc").textContent = num === null ? "" :
      (nombre ? nombre + " · " : "") + (modo || "") + (origen ? " · " + origen : "");
  }
  function setVeredictoError(modelo, error) {
    const v = $("veredicto");
    v.className = "veredicto v-err";
    v.replaceChildren();
    v.append(document.createTextNode("⚠ ERROR DE RONDA"),
      el("small", null, (modelo ? modelo + " · " : "") + error + " — no cuenta en las métricas"));
  }
  // nota (opcional): texto de la ronda que llega del servidor; solo se pinta si no está vacía.
  function setVeredicto(decision, resultado, nota) {
    const v = $("veredicto");
    v.className = "veredicto";
    v.replaceChildren();
    if (!decision) { v.textContent = "SIN EVALUAR"; return; }
    if (resultado === "FALLA_DEFENSA") {
      v.classList.add("v-fail");
      v.append(document.createTextNode("✕ VICTORIA DEL ATACANTE"),
        el("small", null, "Salieron datos sensibles a quien no tenía derecho · condición experimental, no compromiso real"));
    } else if (resultado === "DEFENSA_EN_PROFUNDIDAD") {
      v.classList.add("v-depth");
      v.append(document.createTextNode("◈ IA ENGAÑADA · CAPAS CONTUVIERON"),
        el("small", null, "La IA permitió un acceso indebido; las capas de seguridad lo frenaron"));
    } else {
      const [cls, ico, txt] = VEREDICTO[decision] || ["", "?", String(decision)];
      if (cls) v.classList.add(cls);
      v.append(document.createTextNode(ico + " " + txt));
      if (resultado && RESULTADO[resultado]) {
        v.append(el("small", null, "Resultado: " + RESULTADO[resultado][2]));
      }
    }
    if (nota && String(nota).trim()) v.append(el("small", null, "Nota: " + nota));
  }

  // ---------- atacante ----------
  let tipTimer = null;
  function setAtqEstado(texto, activo) {
    const b = $("atq-estado");
    b.textContent = (activo ? "● " : "○ ") + texto;
    b.classList.toggle("on", !!activo);
  }
  function setAtaque(a) {
    clearInterval(tipTimer);
    const box = $("atq-prompt");
    const texto = String(a.prompt || "");
    $("atq-cat").textContent = "Categoría: " + (a.categoria || "—");
    $("atq-obj").textContent = "Objetivo: " + (a.objetivo || "—");
    const meta = [];
    if (a.modelo) meta.push(a.modelo);
    if (typeof a.tiempo_ms === "number") meta.push((a.tiempo_ms / 1000).toFixed(2) + " s");
    if (typeof a.tokens === "number") meta.push(a.tokens + " tokens");
    $("atq-meta").textContent = meta.join(" · ");
    const s = $("atq-sens");
    s.className = "sens-" + String(a.sensibilidad_objetivo || "").replace(/[^A-Z]/g, "");
    s.textContent = (SENS_ICONO[a.sensibilidad_objetivo] || "") + " " + (a.sensibilidad_objetivo || "—");
    box.classList.remove("vacio"); // deja de mostrarse el estado vacío (también durante el tecleo)
    if (reduce()) { box.textContent = texto; return; }
    box.textContent = "";
    let i = 0;
    tipTimer = setInterval(() => {
      i += 2;
      box.textContent = texto.slice(0, i);
      if (i >= texto.length) clearInterval(tipTimer);
    }, 18);
  }
  function limpiarAtaque() {
    clearInterval(tipTimer);
    $("atq-prompt").textContent = "";
    $("atq-prompt").classList.add("vacio"); // estado vacío: texto en data-vacio (index.html), pintado por CSS
    $("atq-meta").textContent = "";
    $("atq-cat").textContent = "Categoría: —";
    $("atq-obj").textContent = "Objetivo: —";
    $("atq-sens").className = "";
    $("atq-sens").textContent = "—";
  }

  const actual = {}, token = {};
  function setContador(id, valor) {
    const n = $(id);
    const desde = actual[id] || 0;
    actual[id] = valor;
    const t = (token[id] = (token[id] || 0) + 1);
    // Con la pestaña oculta requestAnimationFrame se pausa: se fija el valor final directamente.
    if (reduce() || document.hidden || desde === valor) { n.textContent = valor; return; }
    const t0 = performance.now();
    (function paso(ahora) {
      if (token[id] !== t) return;
      const p = Math.min(1, (ahora - t0) / 400);
      n.textContent = Math.round(desde + (valor - desde) * p);
      if (p < 1) requestAnimationFrame(paso);
    })(t0);
  }
  function setContadores(c) {
    setContador("c-intentos", c.intentos);
    setContador("c-exitosos", c.exitosos);
    setContador("c-bloqueados", c.bloqueados);
    setContador("c-ia", c.ia || 0);
  }

  // ---------- defensor ----------
  function setDefEstado(texto, activo) {
    const b = $("def-estado");
    b.textContent = (activo ? "● " : "○ ") + texto;
    b.classList.toggle("on", !!activo);
  }
  function setRiesgo(v) {
    const n = Math.max(0, Math.min(100, Math.round(Number(v) || 0)));
    const g = $("gauge");
    g.setAttribute("class", "gauge " + (n < 30 ? "g-ok" : n < 60 ? "g-warn" : "g-bad"));
    $("gauge-arc").setAttribute("stroke-dasharray", n + " 100");
    $("gauge-val").textContent = n;
    $("gauge-lbl").textContent = "RIESGO · " + (n < 30 ? "BAJO" : n < 60 ? "MEDIO" : n < 80 ? "ALTO" : "CRÍTICO");
  }
  function limpiarDefensor() {
    setRiesgo(0);
    $("gauge-lbl").textContent = "RIESGO · —";
    ["def-decision", "def-origen", "def-ia", "def-motivo", "def-politica", "def-capa", "def-herr", "def-tiempo"].forEach((id) => { $(id).textContent = "—"; });
    $("def-parse").hidden = true;
  }
  function setDefensor(d) {
    setRiesgo(d.riesgo);
    const v = VEREDICTO[d.decision];
    $("def-decision").textContent = v ? v[1] + " " + d.decision + " (" + v[2] + ")" : String(d.decision);
    $("def-motivo").textContent = d.motivo || "—";
    $("def-politica").textContent = d.politica || "—";
    $("def-capa").textContent = d.capa_bloqueo || "—";
    $("def-herr").textContent = d.herramienta || "—";
    $("def-tiempo").textContent = d.tiempo_ms + " ms" + (typeof d.tokens === "number" ? " · " + d.tokens + " tokens" : "");
    $("def-ia").textContent = d.decision_ia || "—";
    $("def-origen").textContent = d.origen_decision === "filtro_rapido" ? "⚡ Filtro rápido (sin inferencia)"
      : d.origen === "ollama" ? "🟢 REAL (Ollama" + (d.modelo ? " · " + d.modelo : "") + ")" : "🟡 MOCK";
    $("def-parse").hidden = d.parse_ok !== false;
  }

  // ---------- historial ----------
  const seg = (ms) => (typeof ms === "number" ? (ms / 1000).toFixed(2) + " s" : "—");
  const tok = (n) => (typeof n === "number" ? n + " tokens" : "—");
  function filaDetalle(titulo, valor, bloque) {
    const f = el("div", "det-fila");
    f.append(el("span", "det-lbl", titulo), el(bloque ? "pre" : "span", "det-val" + (bloque ? " mono" : ""), valor));
    return f;
  }
  // reg = registro de ronda (ver app.js). Cabecera clicable que despliega el prompt completo y la respuesta del defensor.
  function addHistorial(reg) {
    const esError = reg.veredicto === "ERROR";
    const [cls, ico, txt] = esError ? ["r-err", "⚠", "ERROR"]
      : (RESULTADO[reg.veredicto] || ["", "?", String(reg.veredicto)]);
    const parcial = reg.nivel_fuga === "PARCIAL";
    const li = el("li", "hist " + cls + (parcial ? " r-parcial" : ""));
    const flecha = el("span", "hist-flecha", "▸");
    const cab = el("button", "hist-cab");
    cab.type = "button";
    cab.setAttribute("aria-expanded", "false");
    cab.append(el("span", "hist-ico", ico),
      el("span", "hist-txt", "RONDA " + String(reg.ronda).padStart(2, "0") +
        " · ATAQUE: " + (reg.categoria || "—") +
        " · DEFENSA: " + (reg.decision_efectiva || "—") + " · RESULTADO: " + txt + (parcial ? " · FUGA PARCIAL" : "")),
      flecha);
    li.append(cab);
    if (reg.veredicto === "FALLA_DEFENSA") {
      li.append(el("div", "hist-nota", "Condición experimental a analizar, no compromiso real."));
    } else if (reg.veredicto === "DEFENSA_EN_PROFUNDIDAD") {
      li.append(el("div", "hist-nota hist-nota-depth", "La IA permitió, las capas de seguridad contuvieron."));
    } else if (esError) {
      li.append(el("div", "hist-nota", "No cuenta como bloqueo ni como éxito."));
    }
    if (reg.circuito_sesion) {
      li.append(el("div", "hist-nota hist-nota-circuito", "🔒 Autorización forzada por patrón de sesión sospechoso"));
    }
    if (parcial) {
      li.append(el("div", "hist-nota hist-nota-parcial", "Fuga parcial: el defensor confirmó/nombró un secreto sin entregarlo (no puntúa, se registra)."));
    }

    const det = el("div", "hist-det");
    det.hidden = true;
    det.append(
      filaDetalle("Prompt del atacante", reg.prompt_ataque || "— (no se generó)", true),
      filaDetalle("Propuesta de la IA", reg.decision_ia || "—"),
      filaDetalle("Decisión efectiva", reg.decision_efectiva || "—"),
      filaDetalle("Riesgo", typeof reg.riesgo === "number" ? String(reg.riesgo) : "—"),
      filaDetalle("Motivo del defensor", reg.motivo || "—", true),
      filaDetalle("Modelos", (reg.modelo_atq || "—") + " (atacante) · " + (reg.modelo_def || "—") + " (defensor)"),
      filaDetalle("Tiempos", "atacante " + seg(reg.tiempos_ms && reg.tiempos_ms.atacante) +
        " · defensor " + seg(reg.tiempos_ms && reg.tiempos_ms.defensor)),
      filaDetalle("Tokens", "atacante " + tok(reg.tokens && reg.tokens.atacante) +
        " · defensor " + tok(reg.tokens && reg.tokens.defensor)));
    if (reg.error) det.append(filaDetalle("Error", reg.error, true));
    li.append(det);
    cab.addEventListener("click", () => {
      const abrir = det.hidden;
      det.hidden = !abrir;
      cab.setAttribute("aria-expanded", String(abrir));
      flecha.textContent = abrir ? "▾" : "▸";
    });

    const ul = $("historial");
    ul.prepend(li);
    while (ul.children.length > 200) ul.lastElementChild.remove();
  }
  function limpiarHistorial() { $("historial").replaceChildren(); }

  // ---------- auditoría ----------
  let autoscroll = true;
  function initAuditoria() {
    const log = $("aud-log");
    log.addEventListener("scroll", () => {
      autoscroll = log.scrollHeight - log.scrollTop - log.clientHeight < 24;
      $("aud-pausa").hidden = autoscroll;
    });
  }
  function crearFiltros(agentes, onChange, activos) {
    const cont = $("filtros");
    cont.replaceChildren();
    agentes.forEach((ag) => {
      const b = el("button", "filtro", ag);
      b.type = "button";
      const activo = !activos || activos.includes(ag); // filtro inicial por equipo (opcional)
      b.setAttribute("aria-pressed", String(activo));
      if (!activo) onChange(ag, false);
      b.addEventListener("click", () => {
        const on = b.getAttribute("aria-pressed") !== "true";
        b.setAttribute("aria-pressed", String(on));
        onChange(ag, on);
      });
      cont.append(b);
    });
  }
  function setFiltro(agente, activo) { $("aud-log").classList.toggle("off-" + agente, !activo); }
  function addAuditoria(ev) {
    const log = $("aud-log");
    const ag = String(ev.agente || "SYSTEM").replace(/[^A-Z]/g, "");
    const ln = el("div", "ln");
    ln.dataset.agente = ag;
    ln.append(el("span", "ts", ev.ts), document.createTextNode(" | "),
      el("span", "ag ag-" + ag, ev.agente), document.createTextNode(
        " | " + ev.accion + " | " + ev.recurso + " | " + ev.resultado + " | RIESGO " + ev.nivel_riesgo));
    log.append(ln);
    while (log.children.length > 500) log.firstElementChild.remove();
    if (autoscroll) log.scrollTop = log.scrollHeight;
  }

  // ---------- terminal manual ----------
  function terminalAdd(tipo, texto) {
    const log = $("term-log");
    log.append(el("div", "t-ln t-" + tipo, texto));
    log.scrollTop = log.scrollHeight;
  }
  function terminalLimpiarDatos() { $("term-datos").replaceChildren(); }
  function terminalDatos(lista) {
    const cont = $("term-datos");
    cont.replaceChildren();
    if (!Array.isArray(lista) || !lista.length) return;
    const cols = Object.keys(lista[0]);
    const tabla = el("table");
    const cab = el("tr");
    cols.forEach((c) => { const th = el("th", null, c); th.scope = "col"; cab.append(th); });
    const thead = el("thead");
    thead.append(cab);
    tabla.append(thead);
    const cuerpo = el("tbody");
    lista.forEach((fila) => {
      const tr = el("tr");
      cols.forEach((c) => tr.append(el("td", null, fila[c])));
      cuerpo.append(tr);
    });
    tabla.append(cuerpo);
    cont.append(tabla);
  }

  // ---------- cabecera ----------
  const TEXTO_BOTON = { simulacion: "INICIAR SIMULACIÓN", batalla: "INICIAR BATALLA", manual: "ENVIAR PROMPT" };
  function setManualOrigen(real) {
    document.querySelectorAll("[data-origen]").forEach((b) => b.setAttribute("aria-pressed", String((b.dataset.origen === "real") === real)));
  }
  function setModo(modo, manualReal) {
    const usaModelo = modo === "batalla" || (modo === "manual" && !!manualReal);
    setManualOrigen(!!manualReal);
    document.querySelectorAll(".tab[data-modo]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.modo === modo)));
    $("atq-vista").hidden = modo === "manual";
    $("term").hidden = modo !== "manual";
    $("rondas-wrap").hidden = modo !== "batalla";
    // En batalla el usuario lo fija la dificultad (empleado/analista/admin); el selector de usuario solo en manual real.
    $("usuario-wrap").hidden = !(modo === "manual" && !!manualReal);
    $("dificultad-wrap").hidden = modo !== "batalla";
    $("escenario-wrap").hidden = modo !== "batalla";
    $("demo-wrap").hidden = modo !== "batalla";
    $("intensidad-wrap").hidden = modo !== "batalla";
    $("sel-atq-box").hidden = modo !== "batalla";
    $("sel-def-box").hidden = !usaModelo;
    $("atq-titulo").textContent = modo === "manual" ? "ATACANTE MANUAL" : "IA ATACANTE";
    $("btn-main").textContent = TEXTO_BOTON[modo];
  }
  function setCorriendo(c, mainBloqueado, tooltip) {
    $("btn-main").disabled = c || !!mainBloqueado;
    $("main-wrap").title = !c && mainBloqueado ? (tooltip || "") : "";
    $("btn-stop").disabled = !c;
    $("rondas").disabled = c;
    ["sel-atq", "sel-def", "sel-usuario", "sel-intensidad", "sel-escenario"].forEach((id) => { $(id).disabled = c; });
    $("sel-dificultad").disabled = c || $("chk-demo").checked; // en demostración el usuario es admin, no hay dificultad
    $("chk-demo").disabled = c;
    document.querySelectorAll("[data-refrescar]").forEach((b) => { b.disabled = c; });
    document.querySelectorAll(".tab[data-modo]").forEach((t) => { t.disabled = c; });
    $("term-input").disabled = c;
  }
  function setConexion(est) {
    const ok = est === "conectado";
    $("conn").className = "conn " + (ok ? "conn-ok" : "conn-warn");
    $("conn-ico").textContent = ok ? "●" : "◐";
    $("conn-txt").textContent = ok ? "Conectado" : "Reconectando…";
  }
  function setInfo(e) {
    $("atq-modelo").textContent = e.modelo_atq || "—";
    $("def-modelo").textContent = e.modelo_def || "—";
  }
  let toastTimer = null;
  // Los avisos de éxito de la app empiezan por ✓ (o 📎 al abrir un PDF): se pintan con borde verde; el resto, rojo.
  function toast(msg) {
    const t = $("toast");
    t.textContent = String(msg);
    t.classList.toggle("toast-ok", /^(✓|📎)/.test(t.textContent));
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 5000);
  }

  // ---------- marcador, reto (listo/aceptar), resultado de partida, diagnóstico ----------
  function setMarcador(atq, def) {
    $("marcador").textContent = "🔴 " + (atq | 0) + " — " + (def | 0) + " 🔵";
  }
  // Modo demostración (admin): etiqueta visible y marcador desactivado; no puntúa porque el acceso es legítimo.
  function setDemo(on) {
    $("demo-tag").hidden = !on;
    $("sel-dificultad").disabled = on;
    if (on) $("marcador").textContent = "🔴 sin puntaje 🔵";
  }
  function setProbe(rol, texto, ok) { // ok: true | false | null (probando)
    const n = $("probe-" + (rol === "def" ? "def" : "atq"));
    n.textContent = texto;
    n.className = "probe-res " + (ok === true ? "probe-ok" : ok === false ? "probe-bad" : "probe-wait");
  }
  const EQ = { rojo: "ROJO", azul: "AZUL", general: "GENERAL" };
  const DIF = { facil: "Fácil (invitado)", media: "Media (empleado)", dificil: "Difícil (analista)" };
  function mostrarReto(visible, d) {
    $("reto-modal").hidden = !visible;
    if (!visible || !d) return;
    $("reto-t").textContent = "⚔ EQUIPO " + (EQ[d.de_rol] || "?") + " QUIERE INICIAR COMBATE";
    $("reto-det").textContent = "Rondas: " + d.rondas + " · Intensidad: " + d.intensidad + " · " +
      (d.demo ? "MODO DEMOSTRACIÓN (admin, sin puntaje)" : "Dificultad: " + (DIF[d.dificultad] || "—")) +
      " · Escenario: " + (d.escenario || "libre");
    $("reto-aceptar").focus();
  }
  function setCuenta(n) { $("reto-cuenta").textContent = String(Math.max(0, n)); }
  function mostrarEspera(texto) {
    const b = $("reto-espera");
    b.hidden = !texto;
    b.textContent = texto || "";
  }
  function mostrarPartida(d, hayMetricas) {
    const a = d.puntos_atacante | 0, df = d.puntos_defensor | 0;
    const t = d.ganador === "atacante" ? "🏆 GANÓ EL EQUIPO ROJO · " + a + "-" + df
      : d.ganador === "defensor" ? "🏆 GANÓ EL EQUIPO AZUL · " + df + "-" + a : "🤝 EMPATE · " + a + "-" + df;
    $("partida-t").textContent = (d.detenida ? "PARTIDA DETENIDA · " : "") + t;
    $("partida-sub").textContent = "Rondas jugadas: " + d.rondas_jugadas + (d.errores ? " · rondas con error (no puntúan): " + d.errores : "") +
      " · 🔴 atacante " + a + " — " + df + " defensor 🔵";
    // Resumen sí/no derivado del informe (solo si el servidor lo envió).
    const inf = d.informe, res = $("partida-resumen");
    res.replaceChildren();
    res.hidden = !inf;
    if (inf) {
      const sino = (b) => (b ? "Sí" : "No");
      res.append(el("div", null, "¿Engañó al LLM? " + sino(inf.hubo_enganio_llm)),
        el("div", null, "¿Las capas bloquearon? " + sino(inf.capas_bloquearon)),
        el("div", null, "¿Hubo falla real? " + sino(inf.hubo_falla_real)));
    }
    $("partida-metricas").hidden = !hayMetricas;
    $("partida-modal").hidden = false;
    $("partida-revancha").focus();
  }
  const cerrarPartida = () => { $("partida-modal").hidden = true; };
  const partidaAbierta = () => !$("partida-modal").hidden;

  // ---------- equipo (rojo / azul / general) ----------
  const NOMBRE_EQUIPO = { rojo: "EQUIPO ROJO", azul: "EQUIPO AZUL", general: "VISTA GENERAL", espectador: "ESPECTADOR" };
  // Controles que el servidor rechazaría (403) sin token de equipo. Exportar y cambiar de pestaña son locales.
  const ACCIONES_EQUIPO = "#main-wrap, #term-form, [data-refrescar], [data-probar], [data-probar-modelo], " +
    "#reto-aceptar, #reto-rechazar, #partida-revancha";
  // Sin sesión válida (sin unirse o espectador) las acciones se ocultan; DETENER es solo del árbitro (general).
  // Se usa style.display (no `hidden`) porque .btn fija su propio display.
  const vista = { conToken: false, rol: "", partida: null };
  const ocultar = (sel, si) => document.querySelectorAll(sel).forEach((n) => { n.style.display = si ? "none" : ""; });
  function setPermisos(conToken, rol) {
    Object.assign(vista, { conToken, rol });
    ocultar(ACCIONES_EQUIPO, !conToken);
    ocultar("#btn-stop", !conToken || rol !== "general");
    ocultar("#btn-buzon", !conToken || (rol !== "rojo" && rol !== "azul")); // correos: Rojo envía, Azul recibe
    pintarArbitro();
  }
  // Controles del árbitro según la fase: preparación -> duración + iniciar; en curso -> finalizar; finalizada -> nueva.
  function pintarArbitro() {
    const arb = vista.conToken && vista.rol === "general";
    const fase = vista.partida ? vista.partida.fase : "preparacion";
    ocultar("#duracion-wrap, #btn-iniciar-partida", !arb || fase !== "preparacion");
    ocultar("#btn-finalizar", !arb || fase !== "en_curso");
    ocultar("#btn-nueva-partida", !arb || fase !== "finalizada");
  }

  // ---------- partida: fase y cuenta atrás (el servidor manda; aquí solo se interpola entre sus avisos) ----------
  let relojPartida = null;
  const mmss = (s) => String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  function setPartida(p) {
    vista.partida = p;
    const el = $("partida-estado");
    const base = performance.now();
    const pintar = () => {
      if (p.fase === "en_curso") {
        const s = Math.max(0, Math.round(p.restante_s - (performance.now() - base) / 1000));
        el.textContent = "⏱ " + mmss(s) + (s === 0 ? " · cerrando…" : "");
        el.classList.toggle("pe-ultimo", s <= 60);
      } else {
        el.textContent = p.fase === "preparacion" ? "PREPARACIÓN" : "FINALIZADA" + (p.motivo_fin === "tiempo" ? " (tiempo)" : "");
        el.classList.remove("pe-ultimo");
      }
    };
    el.className = "partida-estado pe-" + p.fase;
    const quien = (p.participantes || []).map((x) => x.nombre + " (" + (NOMBRE_EQUIPO[x.equipo] || x.equipo) + ")");
    el.title = "Partida " + p.id + (p.duracion_s ? " · " + p.duracion_s / 60 + " min" : "") +
      "\nParticipantes (" + quien.length + "): " + (quien.join(", ") || "—");
    clearInterval(relojPartida);
    pintar();
    if (p.fase === "en_curso") relojPartida = setInterval(pintar, 1000);
    pintarArbitro();
  }

  // ---------- unirse a la partida: nombre visible (+ código de árbitro) ----------
  function mostrarUnirse(rol, nombrePrevio, onEnviar) {
    $("unirse-t").textContent = "ENTRAR COMO " + (NOMBRE_EQUIPO[rol] || rol.toUpperCase());
    $("unirse-codigo-wrap").hidden = rol !== "general";
    $("unirse-codigo").required = rol === "general";
    $("unirse-nombre").value = nombrePrevio || "";
    $("unirse-error").hidden = true;
    $("unirse-form").onsubmit = (ev) => {
      ev.preventDefault();
      $("unirse-entrar").disabled = true;
      onEnviar($("unirse-nombre").value.trim(), $("unirse-codigo").value.trim());
    };
    $("unirse-modal").hidden = false;
    $("unirse-nombre").focus();
  }
  function errorUnirse(msg) {
    $("unirse-error").textContent = msg;
    $("unirse-error").hidden = false;
    $("unirse-entrar").disabled = false;
  }
  function cerrarUnirse() { $("unirse-modal").hidden = true; $("unirse-entrar").disabled = false; }
  function setParticipante(p, rol) {
    $("equipo-tag").textContent = (NOMBRE_EQUIPO[rol] || "SIN EQUIPO") + (p ? " · " + p.nombre : "");
  }
  function setEquipo(rol) {
    const r = NOMBRE_EQUIPO[rol] ? rol : "";
    document.body.dataset.rol = r;
    $("equipo-tag").textContent = NOMBRE_EQUIPO[r] || "SIN EQUIPO";
    $("equipo-tag").className = "equipo-tag eq-" + (r || "ninguno");
  }
  function mostrarSelector(visible) {
    $("pantalla-equipo").hidden = !visible;
    if (visible) { const b = document.querySelector("[data-equipo]"); if (b) b.focus(); }
  }

  // ---------- origen de datos, Ollama, usuarios ----------
  function setOrigen(texto, clase) {
    const o = $("origen");
    o.textContent = texto;
    o.className = "origen " + clase;
  }
  function llenarSelect(id, valores, vacio) {
    const s = $(id);
    const previo = s.value;
    s.replaceChildren();
    if (!valores.length) {
      const o = el("option", null, vacio);
      o.value = "";
      s.append(o);
      return;
    }
    valores.forEach((v) => { const o = el("option", null, v); o.value = v; s.append(o); });
    s.value = valores.includes(previo) ? previo : valores[0];
  }
  // rol: "atq" | "def" — cada equipo tiene su propia Ollama (indicador y lista de modelos propios).
  // Estado intermedio mientras se comprueba la conexión (spinner CSS). Si en 12 s no llega ningún resultado (p. ej.
  // el host del panel no es el que el servidor comprueba al conectar), se indica en vez de girar para siempre.
  const esperaOllama = {};
  function setOllamaComprobando(rol) {
    const r = rol === "def" ? "def" : "atq";
    document.querySelectorAll('[data-ollama-ind="' + r + '"]').forEach((n) => {
      n.textContent = "COMPROBANDO OLLAMA…";
      n.className = "ollama-ind ind-wait";
    });
    llenarSelect(r === "def" ? "sel-def" : "sel-atq", [], "(comprobando…)");
    clearTimeout(esperaOllama[r]);
    esperaOllama[r] = setTimeout(() => {
      document.querySelectorAll('[data-ollama-ind="' + r + '"].ind-wait').forEach((n) => {
        n.textContent = "⚪ SIN RESPUESTA · usa «Probar conexión»";
        n.className = "ollama-ind ind-sin";
      });
    }, 12000);
  }

  function setOllama(rol, est) {
    clearTimeout(esperaOllama[rol === "def" ? "def" : "atq"]);
    const on = !!est.disponible;
    document.querySelectorAll('[data-ollama-ind="' + (rol === "def" ? "def" : "atq") + '"]').forEach((n) => {
      n.textContent = on ? "🟢 OLLAMA CONECTADO" : "🔴 OLLAMA DESCONECTADO";
      n.className = "ollama-ind " + (on ? "ind-on" : "ind-off");
    });
    llenarSelect(rol === "def" ? "sel-def" : "sel-atq", Array.isArray(est.modelos) ? est.modelos : [], "(sin modelos)");
  }
  function setUsuarios(lista) {
    const s = $("sel-usuario");
    const previo = s.value;
    s.replaceChildren();
    if (!lista.length) { const o = el("option", null, "(sin usuarios)"); o.value = ""; s.append(o); return; }
    lista.forEach((u) => { const o = el("option", null, u.usuario + " · " + u.rol); o.value = u.usuario; s.append(o); });
    const vals = lista.map((u) => u.usuario);
    s.value = vals.includes(previo) ? previo : (vals.includes("ana.perez") ? "ana.perez" : vals[0]);
  }
  const valorSelect = (id) => $(id).value;

  // ---------- buzón de correos de entrenamiento (Rojo envía, Azul lee) ----------
  const RUTA_ENLACE = /^\/l\/[A-Za-z0-9_-]{8,32}$/; // solo enlaces locales generados por el servidor
  let focoBuzon = null;

  // "2026-10-22T13:36:27" -> "22/10/2026 13:36" (texto tal cual si no es ISO)
  function fechaCorta(ts) {
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(ts || "");
    return m ? m[3] + "/" + m[2] + "/" + m[1] + " " + m[4] + ":" + m[5] : (ts || "—");
  }

  // El escritorio (escritorio.js) puede alojar la tarjeta del buzón en una ventana: entonces abrir/cerrar se
  // delegan en ella ({abrir(), cerrar(), abierta()}) y el modal no se usa. Sin escritorio, todo sigue igual.
  let ventanaBuzon = null;
  function alojarBuzon(v) { ventanaBuzon = v; }
  const buzonEsModal = () => !ventanaBuzon;
  const buzonAbierto = () => (ventanaBuzon ? ventanaBuzon.abierta() : !$("buzon-modal").hidden);

  function mostrarBuzon(visible, rol) {
    const m = $("buzon-modal");
    if (visible) {
      focoBuzon = document.activeElement;
      $("buzon-t").textContent = rol === "rojo" ? "✉ ENVIAR CORREO DE ENTRENAMIENTO" : "✉ BUZÓN DEL EQUIPO AZUL";
      $("correo-form").hidden = rol !== "rojo";
      $("buzon-azul").hidden = rol !== "azul";
      if (ventanaBuzon) ventanaBuzon.abrir(); else m.hidden = false;
      $(rol === "rojo" ? "sel-plantilla" : "btn-buzon-refrescar").focus();
    } else if (buzonAbierto()) {
      if (ventanaBuzon) ventanaBuzon.cerrar(); else m.hidden = true;
      if (focoBuzon && focoBuzon.focus) focoBuzon.focus();
    }
  }

  function setPlantillas(lista) {
    const s = $("sel-plantilla");
    s.replaceChildren();
    lista.forEach((p) => { const o = el("option", null, p.nombre); o.value = p.id; s.append(o); });
  }

  // Destinatarios = usuarios semilla; "" = el usuario con el que juega el equipo azul (lo resuelve el servidor).
  function setDestinatarios(usuarios) {
    const s = $("sel-destinatario");
    s.replaceChildren();
    const def = el("option", null, "Usuario del equipo azul");
    def.value = "";
    s.append(def);
    usuarios.filter((u) => u.rol !== "espectador").forEach((u) => {
      const o = el("option", null, u.usuario + " · " + u.rol);
      o.value = u.usuario;
      s.append(o);
    });
  }

  // n = correos sin leer de la bandeja de entrada (o null antes de cargar).
  function setBotonBuzon(n) {
    $("btn-buzon").textContent = typeof n === "number" ? "✉ BUZÓN (" + n + ")" : "✉ CORREOS";
  }

  // Carpetas: entrada · sospechosos (reportados) · archivados · enviados (respuestas de Azul). La carpeta la calcula el
  // servidor; aquí solo se filtra. seleccionado = id del correo abierto (se conserva el resaltado al refrescar).
  const VACIO_CARPETA = { entrada: "No hay correos en la bandeja de entrada.", sospechosos: "Ningún correo reportado.",
    archivados: "No hay correos archivados.", enviados: "Aún no has respondido a ningún correo." };
  function setBuzon(usuario, correos, onAbrir, seleccionado, carpeta, enviados, onCarpeta) {
    carpeta = carpeta || "entrada";
    $("buzon-usuario").textContent = usuario ? "Buzón de " + usuario : "Sin usuario asignado";
    const cuenta = { entrada: correos.filter((c) => c.carpeta === "entrada" && !c.leido).length,
      sospechosos: correos.filter((c) => c.carpeta === "sospechosos").length,
      archivados: correos.filter((c) => c.carpeta === "archivados").length, enviados: (enviados || []).length };
    document.querySelectorAll("[data-carpeta]").forEach((b) => {
      b.setAttribute("aria-selected", String(b.dataset.carpeta === carpeta));
      b.onclick = () => onCarpeta && onCarpeta(b.dataset.carpeta);
    });
    document.querySelectorAll("[data-cuenta]").forEach((n) => { n.textContent = cuenta[n.dataset.cuenta] || ""; });
    const ul = $("buzon-lista");
    ul.replaceChildren();
    if (carpeta === "enviados") {
      (enviados || []).forEach((r) => {
        const li = el("li", "buzon-enviado");
        li.append(el("b", null, "Re: " + r.asunto), el("span", "fecha", fechaCorta(r.ts)),
          el("span", "de", "Para: " + r.para + " · de " + r.participante), el("p", "texto-respuesta", r.texto));
        ul.append(li);
      });
      if (!(enviados || []).length) ul.append(el("li", "buzon-vacio", VACIO_CARPETA.enviados));
      setBotonBuzon(cuenta.entrada);
      return;
    }
    const lista = correos.filter((c) => c.carpeta === carpeta);
    if (!lista.length) ul.append(el("li", "buzon-vacio", correos.length ? VACIO_CARPETA[carpeta] : "No hay correos en esta partida."));
    lista.forEach((c) => {
      const b = el("button", "buzon-item" + (c.leido ? "" : " no-leido"));
      b.type = "button";
      b.dataset.correo = c.id;
      b.append(el("b", null, c.asunto), el("span", "fecha", fechaCorta(c.ts)), el("span", "de", c.de));
      const marcas = [[c.prioridad === "alta", "marca-prioridad", "PRIORIDAD ALTA"], [!c.leido, "marca-nuevo", "SIN LEER"],
        [c.adjunto, "marca-pdf", "📎 PDF"], [c.clicado && !c.contenido, "marca-clic", "ENLACE CLICADO"],
        [c.contenido, "marca-contenido", "CONTENIDO"], [c.reportado, "marca-reportado", "REPORTADO"],
        [c.pdf_reportado, "marca-reportado", "PDF REPORTADO"], [c.aislado, "marca-contenido", "ADJUNTO AISLADO"]]
        .filter(([si]) => si);
      if (marcas.length) {
        const m = el("span", "buzon-marcas");
        marcas.forEach(([, cls, txt]) => m.append(el("span", "marca " + cls, txt)));
        b.append(m);
      }
      if (c.id === seleccionado) b.setAttribute("aria-current", "true");
      b.addEventListener("click", () => {
        ul.querySelectorAll(".buzon-item").forEach((x) => x.removeAttribute("aria-current"));
        b.setAttribute("aria-current", "true");
        onAbrir(c);
      });
      const li = el("li");
      li.append(b);
      ul.append(li);
    });
    setBotonBuzon(cuenta.entrada);
  }

  // Tras abrirlo, el correo deja de estar «sin leer» SIN redibujar el detalle (que el usuario puede estar usando).
  function marcarLeido(id) {
    const b = document.querySelector('.buzon-item[data-correo="' + Number(id) + '"]');
    if (!b) return;
    b.classList.remove("no-leido");
    const m = b.querySelector(".marca-nuevo");
    if (m) m.remove();
    const n = document.querySelector('[data-cuenta="entrada"]');
    const queda = document.querySelectorAll(".buzon-item.no-leido").length;
    if (n) n.textContent = queda || "";
    setBotonBuzon(queda);
  }

  function botonAccion(texto, cls, hecho, textoHecho, onClick) {
    const b = el("button", "btn btn-mini " + cls, hecho ? textoHecho : texto);
    b.type = "button";
    b.disabled = !!hecho;
    if (!hecho) b.addEventListener("click", () => { b.disabled = true; onClick(); });
    return b;
  }

  // Detalle del correo. acciones = {verificar, inspeccionar, responder(texto), archivar(bool), reportar, contener,
  // abrirPdf, aislar, reportarPdf}. Cada acción se valida en el servidor; aquí solo se ofrecen las que tienen sentido.
  function mostrarCorreo(c, acciones) {
    const d = $("buzon-detalle");
    d.replaceChildren();
    d.hidden = !c;
    if (!c) return;
    const meta = "De: " + c.de + " · " + fechaCorta(c.ts) +
      " · Prioridad " + (c.prioridad || "normal") + (c.leido_por ? " · Leído por " + c.leido_por : "");
    d.append(el("h3", null, c.asunto), el("div", "meta", meta));
    if (acciones) {
      const t = el("div", "buzon-acciones buzon-herramientas");
      t.append(botonAccion("🔎 Verificar remitente", "", false, "", acciones.verificar),
        botonAccion("🔗 Inspeccionar enlace", "", false, "", acciones.inspeccionar));
      const resp = el("button", "btn btn-mini", "↩ Responder");
      resp.type = "button";
      resp.addEventListener("click", () => { form.hidden = !form.hidden; if (!form.hidden) area.focus(); });
      t.append(resp, botonAccion(c.archivado ? "📥 Devolver a la entrada" : "🗄 Archivar", "", false, "",
        () => acciones.archivar(!c.archivado)));
      d.append(t);
      var form = el("form", "buzon-responder");
      form.hidden = true;
      var area = el("textarea", "sel");
      area.maxLength = 1000;
      area.rows = 3;
      area.setAttribute("aria-label", "Texto de la respuesta");
      area.placeholder = "La respuesta no sale del laboratorio: queda registrada en la partida.";
      const enviar = el("button", "btn btn-mini btn-primary", "Enviar respuesta");
      enviar.type = "submit";
      form.append(area, enviar);
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        if (area.value.trim()) { enviar.disabled = true; acciones.responder(area.value.trim()); }
      });
      d.append(form);
    }
    d.append(el("div", "buzon-resultado"), el("pre", null, c.cuerpo));
    if (RUTA_ENLACE.test(c.enlace || "")) {
      const a = el("a", null, "Abrir enlace de entrenamiento (" + c.enlace + ")");
      a.href = c.enlace;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.title = "Pulsarlo cuenta como clic del empleado (es lo que el atacante quiere)";
      d.append(a);
    }
    if (c.adjunto) { // PDF benigno del catálogo fijo: se ve en el visor seguro; aislar/reportar son eventos
      const adj = el("div", "buzon-adjunto");
      adj.append(el("span", null, "📎 " + c.adjunto.titulo + " · " + c.adjunto.archivo + " · riesgo " + c.adjunto.riesgo));
      if (acciones) {
        adj.append(botonAccion("👁 Previsualizar", "", c.aislado, "Aislado", acciones.abrirPdf),
          botonAccion("🧪 Aislar", "", c.aislado, "✓ Aislado", acciones.aislar),
          botonAccion("⚑ Reportar PDF", "", c.pdf_reportado, "✓ PDF reportado", acciones.reportarPdf));
      }
      d.append(adj);
    }
    if (!acciones) return;
    const f = el("div", "buzon-acciones");
    f.append(botonAccion("⚑ Reportar", "", c.reportado, "✓ Reportado", acciones.reportar));
    if (c.clicado) f.append(botonAccion("⛔ Contener", "btn-danger", c.contenido, "✓ Contenido", acciones.contener));
    if (acciones.incidente) f.append(botonAccion("🚨 Abrir incidente", "", false, "", acciones.incidente));
    d.append(f);
  }

  // Resultado de verificar / inspeccionar dentro del detalle (sin ventana extra). ok: true verde, false rojo, null neutro.
  function mostrarResultadoCorreo(titulo, lineas, ok) {
    const r = document.querySelector("#buzon-detalle .buzon-resultado");
    if (!r) return;
    r.replaceChildren(el("b", null, titulo));
    r.className = "buzon-resultado " + (ok === true ? "res-ok" : ok === false ? "res-mal" : "");
    const ul = el("ul");
    lineas.filter(Boolean).forEach((l) => ul.append(el("li", null, l)));
    r.append(ul);
  }

  // ---------- visor seguro de documentos: solo texto + metadatos (nunca se ejecuta ni descarga nada) ----------
  let focoVisor = null;
  function mostrarVisor(v) {
    focoVisor = document.activeElement;
    $("visor-t").textContent = "👁 VISOR SEGURO · " + v.titulo;
    const dl = $("visor-meta");
    dl.replaceChildren();
    [["Archivo", v.archivo], ["Tipo", v.tipo], ["Tamaño", v.tamano_bytes + " bytes"], ["SHA-256", v.sha256],
      ["Procedencia", v.procedencia], ["Riesgo del contexto", v.riesgo], ["Análisis", v.analisis]].forEach(([k, val]) => {
      dl.append(el("dt", null, k), el("dd", k === "SHA-256" ? "mono" : null, val));
    });
    const ind = $("visor-indicadores");
    ind.replaceChildren();
    if ((v.indicadores || []).length) {
      ind.append(el("h3", null, "INDICADORES SOSPECHOSOS"));
      const ul = el("ul", "visor-lista");
      v.indicadores.forEach((i) => ul.append(el("li", null, i)));
      ind.append(ul);
    } else {
      ind.append(el("p", "muted", "Sin indicadores sospechosos en el contexto de este documento."));
    }
    $("visor-texto").textContent = (v.texto || []).join("\n");
    $("visor-modal").hidden = false;
    $("visor-cerrar").focus();
  }
  function cerrarVisor() {
    if ($("visor-modal").hidden) return;
    $("visor-modal").hidden = true;
    if (focoVisor && focoVisor.focus) focoVisor.focus();
  }
  const visorAbierto = () => !$("visor-modal").hidden;

  // ---------- Rojo: seguimiento de su campaña ----------
  function setEnviadosRojo(lista) {
    $("rojo-enviados").hidden = false;
    const ul = $("rojo-enviados-lista");
    ul.replaceChildren();
    lista.forEach((c) => {
      const li = el("li", "buzon-enviado");
      li.append(el("b", null, c.asunto), el("span", "fecha", fechaCorta(c.ts)), el("span", "de", "Para: " + c.para_usuario));
      const m = el("span", "buzon-marcas");
      m.append(el("span", "marca " + (c.clicado ? "marca-clic" : "marca-gris"), c.clicado ? "🔗 ENLACE CLICADO" : "🔗 sin clic"));
      if (c.con_adjunto) {
        m.append(el("span", "marca " + (c.adjunto_abierto ? "marca-pdf" : "marca-gris"),
          c.adjunto_abierto ? "📎 ADJUNTO ABIERTO" : "📎 sin abrir"));
      }
      if (c.credencial_obtenida) m.append(el("span", "marca marca-contenido", "🔑 CREDENCIAL OBTENIDA"));
      li.append(m);
      ul.append(li);
    });
  }

  // ---------- batalla de la partida (Fase F) ----------
  // Solo se muestran fases y métricas REALES: la fase actual, el tiempo transcurrido desde que empezó (el servidor
  // envía cuánto llevaba al emitirla) y, al terminar, los tokens y la carga que informó Ollama ("—" si no los dio).
  const RES_IA = { datos_expuestos: "r-bad", ia_enganada: "r-depth", contenido: "r-ok", fallo_seguro: "r-warn",
    error_atacante: "r-warn" };
  const TECNICA = (t) => (t ? String(t).replace(/_/g, " ") : "libre");
  const nd = (v) => (v == null ? "—" : String(v));
  const segs = (ms) => (ms == null ? "—" : ms < 1000 ? ms + " ms" : (ms / 1000).toFixed(1).replace(".", ",") + " s");
  const hostCorto = (h) => String(h || "?").replace(/^https?:\/\//, "").replace(/:11434$/, "");
  let relojIA = null;

  function setIaEnCurso(en) {
    const box = $("bp-encurso");
    clearInterval(relojIA);
    relojIA = null;
    box.replaceChildren();
    box.classList.toggle("activo", !!en);
    if (!en) { box.append(el("span", "muted", "Sin ataque en curso.")); return; }
    const t0 = Date.now() - (en.transcurrido_ms || 0);
    const quien = { atacante: "la Ollama del atacante (Rojo)", defensor: "la Ollama del defensor (Azul)" }[en.fase] ||
      "la comprobación de los modelos";
    const linea = el("b");
    const pinta = () => {
      linea.textContent = "⏳ Ataque #" + (en.n || "…") + " · esperando a " + quien + " · " + (en.modelo || "—") + " · " +
        Math.floor((Date.now() - t0) / 1000) + " s";
    };
    pinta();
    relojIA = setInterval(pinta, 1000);
    box.append(linea, el("span", "muted bp-nota", (en.usuario ? "Identidad: " + en.usuario +
      (en.origen_identidad === "credencial_robada" ? " (credencial robada)" : " (invitado)") + " · técnica " +
      TECNICA(en.tecnica) + ". " : "") + "Es el tiempo real transcurrido: Ollama no informa del avance, así que no hay porcentaje."));
    if (en.prompt) box.append(el("pre", "mono box bp-prompt", en.prompt));
  }

  function itemAtaqueIA(a) {
    const li = el("li", "bp-ataque " + (RES_IA[a.resultado] || ""));
    const cab = el("div", "bp-fila");
    cab.append(el("b", null, "#" + a.n), el("span", "bp-titulo", a.titulo || a.resultado || "—"),
      el("span", null, a.usuario + (a.origen_identidad === "credencial_robada" ? " 🔑 credencial robada" : " · invitado")),
      el("span", "muted", "técnica " + TECNICA(a.categoria || a.tecnica) + " · intensidad " + a.intensidad +
        (a.lanzado_por ? " · lanzado por " + a.lanzado_por : "")),
      el("b", null, (a.puntos_rojo ? "Rojo +" + a.puntos_rojo : "") + (a.puntos_rojo && a.puntos_azul ? " · " : "") +
        (a.puntos_azul ? "Azul +" + a.puntos_azul : "") || "sin puntos"));
    li.append(cab, el("span", null, a.explicacion || ""));
    if (a.prompt) {
      const det = el("details");
      det.append(el("summary", null, "Mensaje del atacante"), el("pre", "mono box bp-prompt", a.prompt));
      li.append(det);
    }
    const m = el("div", "bp-metricas mono");
    const linea = (etq, modelo, ms, tin, tout, carga) => el("span", null, etq + " " + (modelo || "—") + " · " + segs(ms) +
      " · tokens " + nd(tin) + " entrada / " + nd(tout) + " salida" + (carga ? " · incluye " + segs(carga) + " de carga del modelo" : ""));
    m.append(linea("Atacante", a.modelo_atq, a.atq_ms, a.atq_tokens_entrada, a.atq_tokens_salida, a.atq_carga_ms));
    if (a.origen_decision === "filtro_rapido") m.append(el("span", null, "Defensor ⚡ filtro rápido determinista: sin inferencia"));
    else if (a.resultado !== "error_atacante" && a.estado !== "cancelado") {
      m.append(linea("Defensor", a.modelo_def, a.def_ms, a.def_tokens_entrada, a.def_tokens_salida, a.def_carga_ms));
    }
    if (a.decision_ia || a.capa_bloqueo || a.error) {
      m.append(el("span", null, [a.decision_ia && "Propuesta de la IA: " + a.decision_ia,
        a.capa_bloqueo && "capa que frenó: " + a.capa_bloqueo, a.herramienta && "herramienta: " + a.herramienta,
        a.error && "error: " + a.error].filter(Boolean).join(" · ")));
    }
    li.append(m);
    return li;
  }

  // opts: {rol, conToken}. Rojo ve el formulario de ataque; Azul, el botón para fijar su defensor.
  function setBatallaPartida(e, opts) {
    $("bp-cupo").textContent = e.lanzados + "/" + e.max_ataques + " ataques";
    const d = e.defensor || {};
    const def = $("bp-defensor");
    def.textContent = d.modelo
      ? d.modelo + " @ " + hostCorto(d.host) + (d.ok === true ? " · ✓ verificado" : d.ok === false ? " · ⚠ " + (d.error || "no responde") : "")
      : "⚠ sin configurar: cada ataque se deniega por fallo seguro y Azul no puntúa";
    def.className = d.modelo && d.ok !== false ? "ok" : "warn";
    const id = e.identidad || {};
    $("bp-identidad").textContent = id.origen === "credencial_robada"
      ? "🔑 " + id.usuario + " (" + id.rol + ") · credencial robada sin revocar"
      : id.usuario + " (" + id.rol + ") · sin credencial robada";
    $("bp-identidad").className = id.origen === "credencial_robada" ? "warn" : "";
    $("bp-puntos").textContent = "Rojo " + e.puntos.rojo + " · Azul " + e.puntos.azul;
    const sel = $("bp-tecnica");
    if (sel.options.length === 1) (e.tecnicas || []).forEach((t) => { const o = el("option", null, TECNICA(t)); o.value = t; sel.append(o); });
    $("bp-rojo").hidden = !(opts.rol === "rojo" && opts.conToken);
    $("bp-azul").hidden = !(opts.rol === "azul" && opts.conToken);
    const lanzar = $("bp-lanzar");
    lanzar.disabled = e.fase_partida !== "en_curso" || !!e.en_curso || e.restantes <= 0;
    lanzar.title = e.fase_partida !== "en_curso" ? "Solo con la partida en curso"
      : e.en_curso ? "Espera a que termine el ataque en curso"
      : e.restantes <= 0 ? "Ya lanzaste todos los ataques de esta partida" : "Usa el modelo y la Ollama de la ventana IA Atacante";
    setIaEnCurso(e.en_curso);
    const ul = $("bp-lista");
    ul.replaceChildren(...e.ataques.filter((a) => a.estado !== "en_curso").reverse().map(itemAtaqueIA));
  }

  // ---------- resultados y cronología (Fase G) ----------
  const CAT_TXT = { partida: "Partida", correo: "Correo", enlace: "Enlaces", documento: "Documentos", credencial: "Credenciales",
    incidente: "Incidentes", mision: "Misiones", batalla_ia: "Batalla IA", acceso: "Accesos a la BD", practica: "Práctica" };
  const minSeg = (s) => (s == null ? "—" : (s < 0 ? "-" : "") + String(Math.floor(Math.abs(s) / 60)).padStart(2, "0") + ":" +
    String(Math.abs(s) % 60).padStart(2, "0"));

  function setTabInforme(t) {
    document.querySelectorAll("[data-inf]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.inf === t)));
    $("inf-resultados").hidden = t !== "resultados";
    $("inf-cronologia").hidden = t !== "cronologia";
  }

  function setPartidasInforme(d, elegida) {
    const sel = $("inf-sel-partida");
    const opciones = [[d.actual.id, "Actual · " + d.actual.id + " (" + d.actual.fase.replace("_", " ") + ")"],
      ...d.finalizadas.filter((p) => p.partida !== d.actual.id).map((p) => [p.partida, p.partida + " · " +
        (p.ganador === "empate" ? "empate" : "gana " + p.ganador) + " " + p.puntos_rojo + "-" + p.puntos_azul])];
    sel.replaceChildren(...opciones.map(([v, t]) => { const o = el("option", null, t); o.value = v; return o; }));
    sel.value = elegida || d.actual.id;
  }

  function tablaEquipo(nombre, cls, eq) {
    const box = el("section", "inf-equipo " + cls);
    box.append(el("div", null, nombre), el("div", "inf-total", eq.total + " pts"));
    const tabla = el("table", "inf-tabla");
    const cab = el("tr");
    [["Concepto", ""], ["Cant.", "num"], ["× pts", "num"], ["= Subtotal", "num"]].forEach(([t, c]) => cab.append(el("th", c || null, t)));
    tabla.append(cab);
    eq.lineas.forEach((l) => {
      const tr = el("tr");
      const td = el("td", null, l.concepto);
      td.append(el("span", "inf-formula", l.formula), el("span", "inf-formula", l.explicacion));
      tr.append(td, el("td", "num", l.cantidad), el("td", "num", l.unitario), el("td", "num", l.subtotal));
      tabla.append(tr);
    });
    const tot = el("tr");
    tot.append(el("th", null, "Total (suma de subtotales)"), el("td"), el("td"), el("th", "num", eq.total));
    tabla.append(tot);
    box.append(tabla);
    return box;
  }

  // d = /api/resultados, o {bloqueado: mensaje} si esta vista aún no puede verlos.
  function setResultados(d) {
    const eqs = $("inf-equipos");
    const extra = $("inf-extra");
    eqs.replaceChildren();
    extra.replaceChildren();
    if (d.bloqueado) { $("inf-aviso").textContent = d.bloqueado; return; }
    $("inf-partida").textContent = d.partida + (d.guardado ? " · guardado" : " · en vivo");
    const f = d.final;
    $("inf-aviso").textContent = (f ? "🏁 " + (f.ganador === "empate" ? "Empate" : "Gana " + f.ganador.toUpperCase()) +
      " · " + f.puntos_rojo + "-" + f.puntos_azul + " · resultado guardado en el servidor. " : "Partida " +
      String(d.fase).replace("_", " ") + ": cálculo en vivo con el estado actual. ") + d.formula_ganador;
    eqs.append(tablaEquipo("🔴 Equipo Rojo", "rojo", d.rojo), tablaEquipo("🔵 Equipo Azul" + (d.usuario_azul ? " (" + d.usuario_azul + ")" : ""), "azul", d.azul));
    const r = d.riesgo;
    const sr = el("section");
    sr.append(el("b", null, "Riesgo final: " + Math.round(r.final) + "/100"), el("p", "muted", r.explicacion));
    const ul = el("ul");
    r.reglas.forEach((x) => ul.append(el("li", null, x.evento + ": " + x.veces + " × " + (x.riesgo_unitario > 0 ? "+" : "") +
      x.riesgo_unitario + " = " + (x.subtotal > 0 ? "+" : "") + x.subtotal)));
    sr.append(ul, el("span", "muted", "Suma sin acotar: " + r.suma_sin_acotar));
    const b = d.batalla_ia;
    const sb = el("section");
    const med = (m) => (m.n ? segs(m.media) + " de media (" + m.n + " inferencias; " + segs(m.min) + "-" + segs(m.max) + ")" : "—");
    sb.append(el("b", null, "Batalla IA: " + b.lanzados + " ataques"));
    const ub = el("ul");
    Object.entries(b.por_resultado).forEach(([k, v]) => ub.append(el("li", null, k.replace(/_/g, " ") + ": " + v)));
    ub.append(el("li", null, "Atacante: " + med(b.atacante_ms)), el("li", null, "Defensor: " + med(b.defensor_ms)),
      el("li", null, "Tokens atacante " + nd(b.tokens.atacante_entrada) + " entrada / " + nd(b.tokens.atacante_salida) +
        " salida · defensor " + nd(b.tokens.defensor_entrada) + " / " + nd(b.tokens.defensor_salida)),
      el("li", null, "Carga de modelos: " + segs(b.carga_ms)));
    sb.append(ub, el("p", "muted", b.nota));
    extra.append(sr, sb);
  }

  function initFiltrosCronologia(categorias, alCambiar) {
    const box = $("inf-cats");
    if (box.childElementCount) return;
    categorias.forEach((c) => {
      const l = el("label");
      const i = el("input");
      i.type = "checkbox";
      i.value = c;
      i.addEventListener("change", alCambiar);
      l.append(i, document.createTextNode(CAT_TXT[c] || c));
      box.append(l);
    });
  }
  function filtrosCronologia() {
    return { categoria: [...document.querySelectorAll("#inf-cats input:checked")].map((i) => i.value),
      equipo: $("inf-equipo").value, nivel: $("inf-nivel").value, q: $("inf-q").value.trim() };
  }

  function setCronologia(d) {
    $("inf-partida").textContent = d.partida;
    $("inf-crono-info").textContent = d.coinciden + " de " + d.total + " eventos" + (d.coinciden > d.entradas.length
      ? " (se muestran los " + d.entradas.length + " últimos)" : "") + (d.restringida
      ? " · Vista de Rojo durante la partida: solo lo que una campaña real podría observar; al finalizar se ve todo." : "");
    $("inf-lista").replaceChildren(...d.entradas.map((e) => {
      const li = el("li", "inf-ev eq-" + e.equipo);
      li.title = e.ts || "";
      li.append(el("span", "t", minSeg(e.t_s)), el("span", "cat", (CAT_TXT[e.categoria] || e.categoria) + " · " + e.equipo),
        el("span", null, e.texto), el("span", "niv niv-" + e.nivel, e.nivel || ""));
      return li;
    }));
  }

  // ---------- marcador de la partida Rojo/Azul (vista general y espectador, solo lectura) ----------
  function setMarcadorPartida(d) {
    const m = $("marcador-partida");
    m.hidden = false;
    m.replaceChildren();
    const r = Math.round(d.riesgo || 0);
    const zona = r > 70 ? "rojo" : r >= 30 ? "ambar" : "verde";
    const item = (cls, etiqueta, valor) => {
      const s = el("span", "mp-item " + (cls || ""));
      s.append(el("span", "mp-lbl", etiqueta), el("b", null, valor));
      return s;
    };
    m.append(
      item("mp-rojo-eq", "🔴 Rojo", d.puntos_rojo + " pts · " + d.rojo_enlaces_sin_contener + " enlaces / " +
        d.rojo_pdfs_sin_reportar + " PDF" + (d.rojo_credenciales_sin_revocar ? " / " + d.rojo_credenciales_sin_revocar + " cred." : "")),
      item("mp-azul", "🔵 Azul" + (d.usuario_azul ? " (" + d.usuario_azul + ")" : ""),
        d.puntos_azul + " pts · " + d.misiones_completadas + "/" + d.misiones_total + " misiones"),
      item("mp-riesgo mp-" + zona, "Riesgo", r + "/100"),
      item(null, "Clics", d.clics), item(null, "Contenciones", d.contenciones),
      item(null, "Reportes", d.correos_reportados + d.pdf_reportados),
      item(null, "PDF abiertos", d.pdf_abiertos),
      ...(d.incidentes_abiertos ? [item(null, "Incidentes", d.incidentes_abiertos)] : []),
      ...(d.ataques_ia ? [item(null, "Ataques IA", d.ataques_ia + " · Rojo +" + d.puntos_rojo_ia + " / Azul +" + d.puntos_azul_ia)] : []),
      item(null, "Accesos de Rojo denegados", d.denegaciones_rojo));
    if (d.final) m.prepend(item("mp-final", "🏁 FINAL", d.final.ganador === "empate" ? "EMPATE" : "GANA " + d.final.ganador.toUpperCase()));
  }

  // Pantalla de resultado (general / espectador). marcador = marcador congelado al finalizar.
  function mostrarResultado(final, marcador) {
    const g = final.ganador;
    $("final-ganador").textContent = g === "empate" ? "EMPATE" : "GANA EL EQUIPO " + g.toUpperCase();
    $("final-ganador").className = "final-ganador g-" + g;
    $("final-rojo").textContent = final.puntos_rojo;
    $("final-azul").textContent = final.puntos_azul;
    const ul = $("final-detalle");
    ul.replaceChildren();
    const mk = marcador || {};
    [["Rojo: enlaces clicados sin contener", mk.rojo_enlaces_sin_contener],
      ["Rojo: PDFs abiertos sin reportar", mk.rojo_pdfs_sin_reportar],
      ["Rojo: accesos denegados en batallas", mk.denegaciones_rojo],
      ["Batalla IA: ataques lanzados", mk.ataques_ia || 0],
      ["Batalla IA: puntos Rojo / Azul", (mk.puntos_rojo_ia || 0) + " / " + (mk.puntos_azul_ia || 0)],
      ["Azul: misiones completadas", mk.misiones_completadas + "/" + mk.misiones_total],
      ["Riesgo final de la partida", Math.round(mk.riesgo || 0) + "/100"],
      ["Finalizada", fechaCorta(final.ts)]].forEach(([k, v]) => {
      const li = el("li");
      li.append(el("span", null, k), el("b", null, v === undefined ? "—" : v));
      ul.append(li);
    });
    $("final-modal").hidden = false;
    $("final-cerrar").focus();
  }
  const cerrarResultado = () => { $("final-modal").hidden = true; };
  const resultadoAbierto = () => !$("final-modal").hidden;

  // ---------- misiones del Equipo Azul ----------
  function setVistaAzul(vista) {
    document.querySelectorAll("[data-azul]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.azul === vista)));
    $("azul-correos").hidden = vista !== "correos";
    $("azul-misiones").hidden = vista !== "misiones";
    $("azul-incidentes").hidden = vista !== "incidentes";
  }

  const CONDICION = { correo_reportado: "Se completa al reportar un correo", manual: "La marca el propio equipo",
    enlace_contenido: "Se completa al contener un enlace clicado", pdf_abierto: "Se completa al previsualizar un PDF adjunto",
    remitente_verificado: "Se completa al verificar un remitente", incidente_abierto: "Se completa al abrir un incidente",
    credencial_revocada: "Se completa al revocar una credencial comprometida",
    incidente_resuelto: "Se completa al resolver un incidente" };

  // acciones = {completar(id), asumir(id)}. Estado, plazo, dependencias y puntos los calcula el servidor.
  const ETIQUETA_ESTADO = { completada: "✓ COMPLETADA", pendiente: "○ PENDIENTE", bloqueada: "🔒 BLOQUEADA",
    vencida: "⌛ FUERA DE PLAZO (vale la mitad)" };
  function setMisiones(d, acciones) {
    const hechas = d.misiones.filter((m) => m.estado === "completada").length;
    $("misiones-resumen").textContent = (d.usuario ? d.usuario + " · " : "") + d.puntos + " pts · " + hechas + "/" +
      d.misiones.length + " misiones · riesgo de la partida " + Math.round(d.riesgo_partida || 0) + "/100";
    const yo = acciones && acciones.yo;
    const ul = $("misiones-lista");
    ul.replaceChildren();
    if (!d.misiones.length) ul.append(el("li", "buzon-vacio", "Sin misiones."));
    d.misiones.forEach((m) => {
      const hecha = m.estado === "completada";
      const li = el("li", "mision mision-" + m.estado + " prioridad-" + m.prioridad + (hecha ? " completada" : ""));
      li.dataset.mision = m.id;
      const det = el("span", "det");
      det.append(el("span", "estado-" + m.estado, ETIQUETA_ESTADO[m.estado] || m.estado),
        el("span", "marca marca-prio-" + m.prioridad, "PRIORIDAD " + m.prioridad.toUpperCase()));
      if (m.plazo_s != null && !hecha) {
        const queda = d.transcurrido_s == null ? m.plazo_s : m.plazo_s - d.transcurrido_s;
        det.append(el("span", null, queda > 0 ? "⏱ plazo: quedan " + mmss(queda) : "⏱ plazo agotado"));
      }
      det.append(el("span", null, CONDICION[m.condicion_evento] || m.condicion_evento));
      if (m.requiere && m.requiere.length) det.append(el("span", "requiere", "Requiere: " + m.requiere.join(", ")));
      if (m.responsable && !hecha) det.append(el("span", "responsable", "👤 Responsable: " + m.responsable));
      const pts = hecha ? "+" + m.puntos_obtenidos + " pts" + (m.a_tiempo === false ? " (fuera de plazo)" : "")
        : m.puntos + " pts";
      li.append(el("b", null, m.titulo), el("span", "pts", pts), det);
      if (m.descripcion) li.append(el("p", "mision-desc", m.descripcion));
      if (hecha) {
        li.append(el("p", "mision-evidencia", "Completada" + (m.completada_por ? " por " + m.completada_por : "") +
          (m.ts ? " · " + fechaCorta(m.ts) : "") + (m.evidencia ? " · evidencia: " + m.evidencia : "")));
      } else if (acciones) {
        const b = el("div", "mision-botones");
        if (m.responsable !== yo) b.append(botonAccion("👤 Asumir", "", false, "", () => acciones.asumir(m.id)));
        if (m.condicion_evento === "manual") {
          b.append(botonAccion("Marcar completada", "", m.estado === "bloqueada", "Bloqueada", () => acciones.completar(m.id)));
        }
        if (b.childElementCount) li.append(b);
      }
      ul.append(li);
    });
  }

  // ---------- incidentes y credencial ficticia (Fase E) ----------
  const ESTADO_CRED = { segura: ["✓ SEGURA", "cred-segura"], comprometida: ["⚠ COMPROMETIDA", "cred-comprometida"],
    revocada: ["✓ REVOCADA (contraseña cambiada)", "cred-revocada"] };
  function setCredencial(c, onRevocar) {
    const s = $("credencial");
    s.replaceChildren();
    const [txt, cls] = ESTADO_CRED[c.estado] || [c.estado, ""];
    s.className = "credencial " + cls;
    s.append(el("b", null, "🔑 " + (c.cuenta || "Credencial ficticia")), el("span", "cred-estado", txt));
    const ult = (c.historial || [])[0];
    if (c.estado === "comprometida" && ult) {
      s.append(el("p", null, "Se entregó en la página falsa del correo «" + ult.asunto + "» (" + fechaCorta(ult.ts) +
        "). Contener el enlace no basta: hay que revocarla."));
      s.append(botonAccion("🔒 Revocar credencial", "btn-danger", false, "", onRevocar));
    } else if (c.estado === "revocada" && ult) {
      s.append(el("p", "muted", "Revocada por " + (ult.revocada_por || "—") + " · " + fechaCorta(ult.revocada_ts)));
    }
  }

  function setCorreosIncidente(correos, seleccionado) {
    const sel = $("inc-correo");
    const actual = seleccionado != null ? String(seleccionado) : sel.value;
    sel.replaceChildren(el("option", null, "— ninguno —"));
    sel.firstChild.value = "";
    correos.forEach((c) => {
      const o = el("option", null, c.asunto + " · " + c.de);
      o.value = String(c.id);
      sel.append(o);
    });
    sel.value = [...sel.options].some((o) => o.value === actual) ? actual : "";
  }

  const ESTADO_INC = { abierto: "🟠 ABIERTO", en_investigacion: "🔎 EN INVESTIGACIÓN", resuelto: "✓ RESUELTO" };
  // acciones = {investigar(id), resolver(id, texto)}. La lista se redibuja con cada cambio (SSE): el texto de
  // resolución que se está escribiendo se guarda por incidente para no perderlo.
  const borradores = {};
  function setIncidentes(lista, acciones) {
    const abiertos = lista.filter((i) => i.estado !== "resuelto").length;
    $("incidentes-cuenta").textContent = abiertos ? "(" + abiertos + ")" : "";
    const ul = $("incidentes-lista");
    ul.replaceChildren();
    if (!lista.length) ul.append(el("li", "buzon-vacio", "No hay incidentes en esta partida."));
    lista.forEach((i) => {
      const li = el("li", "mision incidente inc-" + i.estado + " sev-" + i.severidad);
      li.dataset.incidente = i.id;
      const det = el("span", "det");
      det.append(el("span", "estado-" + i.estado, ESTADO_INC[i.estado]), el("span", "marca marca-sev-" + i.severidad,
        "SEVERIDAD " + i.severidad.toUpperCase()), el("span", null, "Abierto por " + i.abierto_por + " · " + fechaCorta(i.ts_apertura)));
      if (i.correo_id) det.append(el("span", null, "correo:" + i.correo_id));
      li.append(el("b", null, "#" + i.id + " " + i.titulo), el("span"), det);
      if (i.estado === "resuelto") {
        li.append(el("p", "mision-evidencia", "Resuelto por " + i.resuelto_por + ": " + i.resolucion));
      } else {
        if ((i.pendiente || []).length) li.append(el("p", "requiere", "Para resolverlo falta: " + i.pendiente.join("; ") + "."));
        const b = el("div", "mision-botones");
        if (i.estado === "abierto") b.append(botonAccion("🔎 Investigar", "", false, "", () => acciones.investigar(i.id)));
        if (i.estado === "en_investigacion") {
          const t = el("textarea", "sel");
          t.rows = 2;
          t.maxLength = 500;
          t.placeholder = "Resolución: qué se hizo (10-500 caracteres)";
          t.setAttribute("aria-label", "Resolución del incidente #" + i.id);
          t.value = borradores[i.id] || "";
          t.addEventListener("input", () => { borradores[i.id] = t.value; });
          b.append(t, botonAccion("✓ Resolver", "btn-primary", false, "", () => acciones.resolver(i.id, t.value.trim())));
        }
        li.append(b);
      }
      ul.append(li);
    });
  }

  // ---------- modal de resultados ----------
  let focoPrevio = null;
  function mostrarModal(m, errores) {
    const f1 = (n) => (Number(n) || 0).toFixed(1);
    const tarjetas = [
      ["DEFENSE SCORE", f1(m.defense_score) + "%"], ["ATTACK SUCCESS RATE", f1(m.attack_success_rate) + "%"],
      ["BLOCK RATE", f1(m.block_rate) + "%"], ["FALSOS POSITIVOS", m.falsos_positivos],
      ["FALSOS NEGATIVOS", m.falsos_negativos], ["TIEMPO PROMEDIO", m.tiempo_promedio_ms + " ms"],
      ["RIESGO PROMEDIO", f1(m.riesgo_promedio)], ["INTENTOS", m.intentos],
      ...(typeof errores === "number" ? [["RONDAS CON ERROR (no contadas)", errores]] : []),
    ];
    const cont = $("modal-cards");
    cont.replaceChildren();
    tarjetas.forEach(([t, v]) => { const c = el("div", "card"); c.append(el("span", null, t), el("b", null, v)); cont.append(c); });
    const tb = $("modal-tabla");
    tb.replaceChildren();
    (m.por_categoria || []).forEach((f) => {
      const tr = el("tr");
      [f.categoria, f.intentos, f.bloqueados, f.exitosos].forEach((v) => tr.append(el("td", null, v)));
      tb.append(tr);
    });
    focoPrevio = document.activeElement;
    $("modal").hidden = false;
    $("modal-cerrar").focus();
  }
  function cerrarModal() {
    if ($("modal").hidden) return;
    $("modal").hidden = true;
    if (focoPrevio && focoPrevio.focus) focoPrevio.focus();
  }
  const modalAbierto = () => !$("modal").hidden;

  return {
    initPipeline, resetPipeline, setEtapa, setRonda, setVeredicto,
    setAtqEstado, setAtaque, limpiarAtaque, setContadores,
    setDefEstado, setDefensor, limpiarDefensor,
    addHistorial, limpiarHistorial,
    initAuditoria, crearFiltros, setFiltro, addAuditoria,
    terminalAdd, terminalDatos, terminalLimpiarDatos,
    setModo, setCorriendo, setConexion, setInfo, toast,
    setVeredictoError, setOrigen, setManualOrigen, setEquipo, setPermisos, mostrarSelector,
    setPartida, mostrarUnirse, errorUnirse, cerrarUnirse, setParticipante,
    setMarcador, setDemo, setProbe, mostrarReto, setCuenta, mostrarEspera, mostrarPartida, cerrarPartida, partidaAbierta, setOllama, setUsuarios, valorSelect,
    mostrarModal, cerrarModal, modalAbierto,
    mostrarBuzon, buzonAbierto, buzonEsModal, alojarBuzon, setPlantillas, setDestinatarios, setBuzon, setBotonBuzon, mostrarCorreo,
    setBatallaPartida, setIaEnCurso, setTabInforme, setPartidasInforme, setResultados, initFiltrosCronologia,
    filtrosCronologia, setCronologia, setVistaAzul, setMisiones, setMarcadorPartida, marcarLeido, mostrarResultadoCorreo, mostrarVisor, cerrarVisor,
    visorAbierto, setEnviadosRojo, setCredencial, setCorreosIncidente, setIncidentes, setOllamaComprobando, mostrarResultado, cerrarResultado, resultadoAbierto,
  };
})();
