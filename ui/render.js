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
    $("atq-prompt").textContent = "—";
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
    document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.modo === modo)));
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
    document.querySelectorAll(".tab").forEach((t) => { t.disabled = c; });
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
  function toast(msg) {
    const t = $("toast");
    t.textContent = String(msg);
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
  // Sin token válido (sin reclamar o espectador) las acciones se ocultan; DETENER es solo del árbitro (general).
  // Se usa style.display (no `hidden`) porque .btn fija su propio display.
  function setPermisos(conToken, rol) {
    const ocultar = (sel, si) => document.querySelectorAll(sel).forEach((n) => { n.style.display = si ? "none" : ""; });
    ocultar(ACCIONES_EQUIPO, !conToken);
    ocultar("#btn-stop", !conToken || rol !== "general");
    ocultar("#btn-buzon", !conToken || (rol !== "rojo" && rol !== "azul")); // correos: Rojo envía, Azul recibe
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
  function setOllama(rol, est) {
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

  function mostrarBuzon(visible, rol) {
    const m = $("buzon-modal");
    if (visible) {
      focoBuzon = document.activeElement;
      $("buzon-t").textContent = rol === "rojo" ? "✉ ENVIAR CORREO DE ENTRENAMIENTO" : "✉ BUZÓN DEL EQUIPO AZUL";
      $("correo-form").hidden = rol !== "rojo";
      $("buzon-azul").hidden = rol !== "azul";
      m.hidden = false;
      $(rol === "rojo" ? "sel-plantilla" : "btn-buzon-refrescar").focus();
    } else if (!m.hidden) {
      m.hidden = true;
      if (focoBuzon && focoBuzon.focus) focoBuzon.focus();
    }
  }
  const buzonAbierto = () => !$("buzon-modal").hidden;

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

  function setBotonBuzon(n) {
    $("btn-buzon").textContent = typeof n === "number" ? "✉ BUZÓN (" + n + ")" : "✉ CORREOS";
  }

  // seleccionado = id del correo abierto (se conserva el resaltado al refrescar la lista).
  function setBuzon(usuario, correos, onAbrir, seleccionado) {
    $("buzon-usuario").textContent = usuario ? "Buzón de " + usuario : "Sin usuario asignado";
    const ul = $("buzon-lista");
    ul.replaceChildren();
    if (!correos.length) ul.append(el("li", "buzon-vacio", "No hay correos en esta partida."));
    correos.forEach((c) => {
      const b = el("button", "buzon-item");
      b.type = "button";
      b.append(el("b", null, c.asunto), el("span", "fecha", fechaCorta(c.ts)), el("span", "de", c.de));
      const marcas = [[c.clicado && !c.contenido, "marca-clic", "ENLACE CLICADO"],
        [c.contenido, "marca-contenido", "CONTENIDO"], [c.reportado, "marca-reportado", "REPORTADO"]]
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
    setBotonBuzon(correos.length);
  }

  function botonAccion(texto, cls, hecho, textoHecho, onClick) {
    const b = el("button", "btn btn-mini " + cls, hecho ? textoHecho : texto);
    b.type = "button";
    b.disabled = !!hecho;
    if (!hecho) b.addEventListener("click", () => { b.disabled = true; onClick(); });
    return b;
  }

  // acciones = {reportar(), contener()}: Reportar siempre (deshabilitado si ya se reportó); Contener solo si el
  // enlace ya tuvo un clic (deshabilitado si ya se contuvo).
  function mostrarCorreo(c, acciones) {
    const d = $("buzon-detalle");
    d.replaceChildren();
    d.hidden = !c;
    if (!c) return;
    d.append(el("h3", null, c.asunto), el("div", "meta", "De: " + c.de + " · " + fechaCorta(c.ts)),
      el("pre", null, c.cuerpo));
    if (RUTA_ENLACE.test(c.enlace || "")) {
      const a = el("a", null, "Abrir enlace de entrenamiento (" + c.enlace + ")");
      a.href = c.enlace;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      d.append(a);
    }
    if (!acciones) return;
    const f = el("div", "buzon-acciones");
    f.append(botonAccion("⚑ Reportar", "", c.reportado, "✓ Reportado", acciones.reportar));
    if (c.clicado) f.append(botonAccion("⛔ Contener", "btn-danger", c.contenido, "✓ Contenido", acciones.contener));
    d.append(f);
  }

  // ---------- misiones del Equipo Azul ----------
  function setVistaAzul(vista) {
    document.querySelectorAll("[data-azul]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.azul === vista)));
    $("azul-correos").hidden = vista !== "correos";
    $("azul-misiones").hidden = vista !== "misiones";
  }

  const CONDICION = { correo_reportado: "Se completa al reportar un correo", manual: "La marca el propio equipo",
    enlace_contenido: "Se completa al contener un enlace clicado" };

  function setMisiones(d, onCompletar) {
    $("misiones-resumen").textContent = (d.usuario ? d.usuario + " · " : "") + d.puntos + " pts · riesgo de la partida " +
      Math.round(d.riesgo_partida || 0) + "/100";
    const ul = $("misiones-lista");
    ul.replaceChildren();
    if (!d.misiones.length) ul.append(el("li", "buzon-vacio", "Sin misiones."));
    d.misiones.forEach((m) => {
      const hecha = m.estado === "completada";
      const li = el("li", "mision" + (hecha ? " completada" : ""));
      const det = el("span", "det");
      det.append(el("span", "estado-" + m.estado, hecha ? "✓ COMPLETADA" : "○ PENDIENTE"),
        el("span", null, CONDICION[m.condicion_evento] || m.condicion_evento));
      if (hecha && m.ts) det.append(el("span", null, fechaCorta(m.ts)));
      li.append(el("b", null, m.titulo), el("span", "pts", m.puntos + " pts"), det);
      if (!hecha && m.condicion_evento === "manual") {
        li.append(botonAccion("Marcar completada", "", false, "", () => onCompletar(m.id)));
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
    setMarcador, setDemo, setProbe, mostrarReto, setCuenta, mostrarEspera, mostrarPartida, cerrarPartida, partidaAbierta, setOllama, setUsuarios, valorSelect,
    mostrarModal, cerrarModal, modalAbierto,
    mostrarBuzon, buzonAbierto, setPlantillas, setDestinatarios, setBuzon, setBotonBuzon, mostrarCorreo,
    setVistaAzul, setMisiones,
  };
})();
