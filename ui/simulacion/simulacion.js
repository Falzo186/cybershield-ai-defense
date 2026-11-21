/* Simulación · CyberShield. Sin dependencias ni build. TODO texto dinámico entra por textContent / createElementNS.
   Reproduce un REGISTRO ya grabado (eventos con hash): no regenera ni calcula nada de la partida. El resultado se pinta solo cuando
   se llega al evento `partida.resultado` del registro. El ritmo es NARRATIVO (pesos por tipo de evento sobre ≈ 10 min). */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, cls, texto) => { const e = document.createElement(tag); if (cls) e.className = cls; if (texto != null) e.textContent = texto; return e; };
  const NS = "http://www.w3.org/2000/svg";
  const sv = (tag, attrs) => { const e = document.createElementNS(NS, tag); Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v)); return e; };
  const DURACION_S = 600;
  const FACTOR = () => (typeof window.__ritmoSim === "number" ? window.__ritmoSim : 1);   // pruebas: 10 min -> unos segundos
  const INSIGNIA = {
    CAMINOS_GUION: ["GUION · recorrido posible del grafo", "guion", "Decisiones prefijadas: demuestra que el motor y el grafo permiten este final. NO es una partida de un modelo."],
    CAMINOS_IA: ["IA 8B · eligió opciones del grafo", "ia", "Un modelo de lenguaje eligió las opciones del menú; el motor decidió el resultado."],
    LIBRE_IA: ["IA · texto libre", "libre", "Combate libre: solo texto contra el defensor."],
  };
  const NARRA = {
    correo_senuelo: "El Equipo Rojo envió un correo a un empleado", reportar_correo: "El Equipo Azul reportó el correo", no_reportar: "Nadie reportó el correo: un empleado abrió el enlace",
    cred_gerente: "El Equipo Rojo presentó la credencial de la gerente de operaciones", cred_respaldos: "El Equipo Rojo presentó la credencial del administrador de respaldos",
    documento_senuelo: "El Equipo Rojo entregó un documento para que el defensor lo procese", aportar_segundo_factor: "El Equipo Rojo aportó un segundo factor",
    insistir_autoridad: "El Equipo Rojo insistió invocando a la dirección", insistir: "El Equipo Rojo insistió con urgencia", solicitar_base: "El Equipo Rojo pidió la base de datos",
    pivotar_documento: "El Equipo Rojo entregó un documento desde la sesión abierta", aprobar: "El Equipo Azul aprobó", rechazar: "El Equipo Azul rechazó y contuvo la cuenta",
    pedir_verificacion: "El Equipo Azul pidió una verificación adicional", rotar_credencial: "El Equipo Azul rotó la credencial y cerró la sesión", contener: "El Equipo Azul contuvo la cuenta",
  };
  const ALERTA = { "caminos.acceso_inusual": "Azul vio una alerta de acceso inusual", "caminos.correo_clic": "Alerta: un empleado abrió el enlace de un correo", "caminos.correo_reportado": "El SIEM registró un correo reportado",
    "caminos.honeytoken": "Alerta crítica: uso de una credencial señuelo", "caminos.intentos_repetidos": "Alerta: intentos repetidos", "caminos.cuenta_bloqueada": "Alerta: cuenta bloqueada",
    "caminos.credencial_rotada": "El SIEM registró una credencial rotada", "caminos.base_entregada": "Alerta: entrega de la base de datos", "caminos.documento_instruccion": "Alerta: documento con texto que da instrucciones" };
  const ESTADO_TXT = { correo_clic: "Un empleado abrió el enlace del correo", sesion_activa: "Credencial comprometida: el Rojo tiene una sesión activa", base_entregada: "La base de datos sintética fue ENTREGADA",
    cred_rotada: "La credencial fue rotada: la sesión del Rojo quedó invalidada", contencion_activa: "Cuenta contenida por el Equipo Azul", honeytoken_usado: "Se usó una credencial señuelo", datos_senuelo_entregados: "Se entregaron datos de prueba (señuelo)" };
  const S = { det: null, items: [], t: 0, vel: 1, jugando: false, timer: null, ult: 0, vistos: 0 };

  async function api(ruta) {
    let r; try { r = await fetch(ruta, { headers: { Accept: "application/json" } }); } catch (_) { throw new Error("Sin conexión con el servidor"); }
    let d = null; try { d = await r.json(); } catch (_) { /* sin cuerpo */ }
    if (!r.ok) throw new Error((d && d.error) || "Error " + r.status);
    return d;
  }
  const mmss = (s) => String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(Math.floor(s % 60)).padStart(2, "0");
  const hhmmss = (s) => { const b = 9 * 3600 + s; return [Math.floor(b / 3600), Math.floor(b % 3600 / 60), b % 60].map((x) => String(Math.floor(x)).padStart(2, "0")).join(":"); };
  const chipResultado = (r) => el("span", "chip sin-punto " + (r === "VICTORIA_ROJA" ? "chip-rojo" : r === "VICTORIA_AZUL" ? "chip-azul" : "chip-aviso"), r === "VICTORIA_ROJA" ? "Victoria del Equipo Rojo" : r === "VICTORIA_AZUL" ? "Victoria del Equipo Azul" : String(r));
  function insignia(tipo) { const i = INSIGNIA[tipo] || [tipo, "libre", ""]; const c = el("span", "chip sin-punto insignia " + i[1], i[0]); c.title = i[2]; return c; }

  // ── Catálogo ──────────────────────────────────────────────────────────────────────────────────
  async function cargarCatalogo() {
    const cont = $("#catalogo"); cont.textContent = "";
    try {
      const r = await api("/api/simulacion/catalogo");
      r.simulaciones.forEach((x) => {
        const c = el("article", "sim-card " + (x.resultado === "VICTORIA_ROJA" ? "roja" : "azul")); c.dataset.id = x.id;
        const d = el("div", "datos"); d.append(insignia(x.tipo), chipResultado(x.resultado));
        if (x.reversion) d.append(el("span", "chip chip-aviso sin-punto", "reversión"));
        if (x.giro) d.append(el("span", "chip chip-aviso sin-punto", "giro del Rojo"));
        const m = el("div", "datos"); [`Rojo: ${x.modelos.rojo}`, `Azul: ${x.modelos.azul}`, `semilla ${x.semilla}`, `grafo ${x.dificultad}`, `hoja ${x.hoja}`, `hash ${x.hash_grafo.slice(0, 10)}…`].forEach((t) => m.append(el("span", "chip chip-neutro sin-punto", t)));
        const b = el("button", "boton boton-primario", "Reproducir simulación"); b.addEventListener("click", () => abrir(x.id));
        c.append(el("h3", "", x.titulo), d, el("p", "", x.procedencia.replace(/^[A-Z_]+:\s*/, "")), m, b); cont.append(c);
      });
      if (!r.simulaciones.length) cont.append(el("p", "", "No hay grabaciones. Genera el catálogo con experimentos/grabar_simulaciones.py."));
    } catch (e) { cont.textContent = "No se pudo cargar el catálogo: " + e.message; }
  }

  // ── Del registro a la narración ─────────────────────────────────────────────────────────────────
  function construirItems(ev, grafo) {
    const it = []; let pend = {};
    const acumular = (c) => { const u = it[it.length - 1]; if (u) u.todos = Object.assign(u.todos || {}, c); else Object.assign(pend, c); };
    ev.forEach((e) => {
      const p = e.payload;
      if (e.tipo === "caminos.estado") acumular(p.cambios);
      if (e.tipo === "caminos.decision") {
        const base = NARRA[p.opcion] || p.etiqueta;
        it.push({ k: "decision", actor: p.actor, titulo: base, detalle: p.etiqueta, mensaje: p.mensaje, peso: 3, hito: true, nodo: p.nodo, opcion: p.opcion, turno: e.turno });
      } else if (e.tipo === "caminos.alerta") {
        it.push({ k: "alerta", actor: "sistema", titulo: ALERTA[p.clave] || p.clave, detalle: "WAZUH SIMULADO · " + p.clave, clave: p.clave, peso: 2, turno: e.turno });
      } else if (e.tipo === "caminos.estado") {
        Object.entries(p.cambios).forEach(([k, v]) => { if (v === true && ESTADO_TXT[k]) it.push({ k: "estado", actor: "sistema", titulo: ESTADO_TXT[k], detalle: "Estado confirmado por el motor", bandera: k, cambios: { [k]: v }, peso: 2, turno: e.turno }); else if (k === "sesion_activa" && v === false) it.push({ k: "estado", actor: "sistema", titulo: "La sesión del Rojo se cerró", detalle: "Estado confirmado por el motor", cambios: { sesion_activa: false }, peso: 1, turno: e.turno }); });
      } else if (e.tipo === "partida.resultado") {
        it.push({ k: "resultado", actor: "sistema", titulo: p.motivo, detalle: "Resultado declarado por el motor (partida.resultado)", resultado: p, peso: 4, hito: true, turno: e.turno });
      }
    });
    if (it.length && Object.keys(pend).length) it[0].todos = Object.assign(pend, it[0].todos || {});
    const W = it.reduce((a, x) => a + x.peso, 0); let acum = 0;
    it.forEach((x) => { acum += x.peso; x.t = acum / W; x.reloj = acum * 18; });       // t en 0..1 (narrativo); reloj simulado en segundos
    return it;
  }

  // ── Grafo SVG ─────────────────────────────────────────────────────────────────────────────────
  function dibujarGrafo(g) {
    const cont = $("#grafo"); cont.textContent = "";
    const prof = {}, orden = []; const hojas = new Set(Object.keys(g.hojas));
    (function dfs(id, d) { if (hojas.has(id)) { if (!(id in prof) || prof[id] < d) prof[id] = d; if (!orden.includes(id)) orden.push(id); return; } if (!(id in prof) || prof[id] < d) prof[id] = d; if (!orden.includes(id)) orden.push(id); g.nodos[id].opciones.forEach((o) => dfs(o.siguiente, d + 1)); })(g.inicio, 0);
    const cols = Math.max(...Object.values(prof)) + 1, porCol = {};
    orden.forEach((id) => { (porCol[prof[id]] = porCol[prof[id]] || []).push(id); });
    const W = 104, H = 32, gx = 22, gy = 10, alto = Math.max(...Object.values(porCol).map((a) => a.length)) * (H + gy) + 20, ancho = cols * (W + gx) + 10, pos = {};
    Object.entries(porCol).forEach(([c, ids]) => { const tot = ids.length * (H + gy); ids.forEach((id, i) => { pos[id] = { x: 6 + c * (W + gx), y: (alto - tot) / 2 + i * (H + gy) + 8 }; }); });
    const svg = sv("svg", { viewBox: `0 0 ${ancho} ${alto}`, preserveAspectRatio: "xMidYMid meet", role: "img", "aria-label": "Grafo de decisiones con el camino recorrido resaltado" });
    const aristas = [];
    Object.values(g.nodos).forEach((n) => n.opciones.forEach((o) => {
      const a = pos[n.id], b = pos[o.siguiente]; const e = sv("path", { class: "e", d: `M${a.x + W},${a.y + H / 2} C${a.x + W + gx / 2},${a.y + H / 2} ${b.x - gx / 2},${b.y + H / 2} ${b.x},${b.y + H / 2}` }); e.dataset.k = n.id + ":" + o.id; svg.append(e); aristas.push(e);
    }));
    Object.values(g.nodos).forEach((n) => { const r = sv("rect", { class: "n " + n.actor, x: pos[n.id].x, y: pos[n.id].y, width: W, height: H, rx: 8 }); r.dataset.id = n.id; const t = sv("text", { x: pos[n.id].x + 8, y: pos[n.id].y + 20 }); t.textContent = n.id + " · " + n.actor.toUpperCase(); const t2 = sv("text", { x: pos[n.id].x + 8, y: pos[n.id].y + 30 }); t2.textContent = ""; svg.append(r, t); });
    Object.values(g.hojas).forEach((h) => { const r = sv("rect", { class: "h " + (h.resultado === "VICTORIA_ROJA" ? "roja" : "azul"), x: pos[h.id].x, y: pos[h.id].y, width: W, height: H, rx: 18 }); r.dataset.id = h.id; const t = sv("text", { x: pos[h.id].x + 9, y: pos[h.id].y + 20 }); t.textContent = (h.resultado === "VICTORIA_ROJA" ? "R " : "A ") + h.id.replace(/^H_[RA]_/, "").slice(0, 14); svg.append(r, t); });
    cont.append(svg);
  }
  function marcarGrafo() {
    const vis = new Set(), arist = new Set(); S.items.slice(0, S.vistos).forEach((x) => { if (x.k === "decision") { arist.add(x.nodo + ":" + x.opcion); vis.add(x.nodo); const o = S.det.grafo.nodos[x.nodo].opciones.find((q) => q.id === x.opcion); if (o) vis.add(o.siguiente); } });
    if (!vis.size) vis.add(S.det.grafo.inicio);
    document.querySelectorAll("#grafo .n, #grafo .h").forEach((n) => n.classList.toggle("vis", vis.has(n.dataset.id)));
    document.querySelectorAll("#grafo .e").forEach((e) => e.classList.toggle("vis", arist.has(e.dataset.k)));
  }

  // ── Paneles sincronizados ─────────────────────────────────────────────────────────────────────
  function pintar() {
    const v = S.items.slice(0, S.vistos);
    const cron = $("#cron"); while (cron.children.length < v.length) { const x = v[cron.children.length]; const li = el("li", x.actor === "rojo" ? "rojo" : x.actor === "azul" ? "azul" : "sistema"); li.append(el("span", "t", hhmmss(x.reloj)), (() => { const d = el("div"); d.append(el("b", "", x.titulo), el("small", "", x.detalle || "")); return d; })()); cron.append(li); cron.scrollTop = cron.scrollHeight; }
    while (cron.children.length > v.length) cron.lastChild.remove();
    $("#hora-sim").textContent = v.length ? hhmmss(v[v.length - 1].reloj) : "09:00:00";
    const men = $("#mensajes"); men.textContent = ""; v.filter((x) => x.k === "decision" && x.mensaje).forEach((x) => { const m = el("div", "m " + x.actor); m.append(el("b", "", x.actor === "rojo" ? "Equipo Rojo" : "Equipo Azul"), document.createTextNode(x.mensaje)); men.append(m); }); men.scrollTop = men.scrollHeight;
    const al = $("#alertas"); al.textContent = ""; v.filter((x) => x.k === "alerta").forEach((x) => { const li = el("li"); li.append(el("span", "chip chip-simulado sin-punto", "SIMULADO"), document.createTextNode(" " + x.titulo)); al.append(li); });
    // estado derivado SOLO de lo ya reproducido
    const fl = {}; v.forEach((x) => { if (x.todos) Object.assign(fl, x.todos); });
    const inv = [["C-01", "gerente de operaciones"], ["C-07", "administrador de respaldos"]];
    const dec = v.filter((x) => x.k === "decision").map((x) => x.opcion);
    const usada01 = fl.cred_gerente_presentada || dec.includes("cred_gerente");
    const estC01 = !usada01 ? ["sin probar", "chip-neutro"] : fl.cred_rotada ? ["ROTADA", "chip-aviso"] : (fl.base_entregada || fl.sesion_activa || fl.alerta_vista || fl.verificacion_exigida) ? ["VÁLIDA (confirmada por el motor)", "chip-error"] : ["presentada", "chip-info"];
    const estC07 = fl.honeytoken_usado ? ["SEÑUELO detectado", "chip-ok"] : (fl.cred_respaldos_presentada || dec.includes("cred_respaldos")) ? ["presentada", "chip-info"] : ["sin probar", "chip-neutro"];
    const ul = $("#inventario"); ul.textContent = ""; [[inv[0], estC01], [inv[1], estC07]].forEach(([c, e]) => { const li = el("li"); li.append(el("span", "", c[0] + " · " + c[1]), el("span", "chip sin-punto " + e[1], e[0])); ul.append(li); });
    const base = $("#base-chip"); let b = ["ÍNTEGRA", "chip-ok"]; if (fl.base_entregada) b = ["COMPROMETIDA", "chip-error"]; else if (fl.cred_rotada || fl.contencion_activa || fl.honeytoken_usado) b = ["CONTENIDA", "chip-info"];
    base.className = "chip sin-punto " + b[1]; base.textContent = b[0];
    const fin = v.find((x) => x.k === "resultado"); const mc = $("#marcador"); mc.textContent = "";
    const dr = v.filter((x) => x.k === "decision" && x.actor === "rojo").length, da = v.filter((x) => x.k === "decision" && x.actor === "azul").length;
    mc.append(el("div", "", `Movimientos del Rojo: ${dr} · decisiones del Azul: ${da}`), el("div", "", fin ? "Resultado: " : "En juego…"));
    if (fin) mc.lastChild.append(chipResultado(fin.resultado.resultado));
    const bn = $("#banner-res"), ens = $("#ensena");
    if (fin) {
      const r = fin.resultado; bn.hidden = false; bn.className = "banner " + (r.resultado === "VICTORIA_ROJA" ? "r-rojo" : "r-azul"); bn.textContent = "";
      const izq = el("div", "banner-texto"); izq.append(el("h2", "", r.resultado === "VICTORIA_ROJA" ? "Victoria del Equipo Rojo" : "Victoria del Equipo Azul"), el("p", "motivo", r.motivo),
        el("p", "explica", S.det.tipo === "CAMINOS_GUION" ? "Recorrido posible del grafo, demostrado por el motor (decisiones prefijadas): NO es una victoria de un modelo de IA." : "El motor declaró este resultado a partir del estado verificable."));
      bn.append(izq); ens.hidden = false; $("#ensena-txt").textContent = r.ensena || "";
    } else { bn.hidden = true; ens.hidden = true; }
    marcarGrafo();
  }

  // ── Reproductor ───────────────────────────────────────────────────────────────────────────────
  const total = () => DURACION_S * FACTOR();
  function aplicarTiempo() {
    const f = S.t / total(); S.vistos = S.items.filter((x) => x.t <= f + 1e-9).length;
    $("#rng").value = String(Math.round(f * 1000)); $("#reloj").textContent = `${mmss(Math.min(S.t / FACTOR(), DURACION_S))} / ${mmss(DURACION_S)}`; pintar();
  }
  function tick() { S.t = Math.min(total(), S.t + 0.1 * S.vel); aplicarTiempo(); if (S.t >= total()) pausar(); }
  function reproducir() { if (S.t >= total()) { S.t = 0; aplicarTiempo(); } S.jugando = true; $("#btn-play").textContent = "⏸ Pausar"; clearInterval(S.timer); S.timer = setInterval(tick, 100); }
  function pausar() { S.jugando = false; $("#btn-play").textContent = "▶ Reproducir"; clearInterval(S.timer); }
  $("#btn-play").addEventListener("click", () => (S.jugando ? pausar() : reproducir()));
  $("#sel-vel").addEventListener("change", (ev) => { S.vel = parseFloat(ev.target.value); });
  $("#rng").addEventListener("input", (ev) => { pausar(); S.t = (parseInt(ev.target.value, 10) / 1000) * total(); aplicarTiempo(); });
  $("#btn-hito").addEventListener("click", () => { const f = S.t / total(); const h = S.items.find((x) => x.hito && x.t > f + 1e-6); S.t = (h ? h.t : 1) * total(); aplicarTiempo(); });
  $("#btn-volver").addEventListener("click", () => { pausar(); $("#vista-reproductor").hidden = true; $("#vista-catalogo").hidden = false; history.replaceState(null, "", "#"); });

  async function abrir(id) {
    let d; try { d = await api("/api/simulacion/" + encodeURIComponent(id)); } catch (e) { $("#catalogo").textContent = e.message; return; }
    pausar(); S.det = d; S.items = construirItems(d.eventos_registro, d.grafo); S.t = 0; S.vistos = 0; S.vel = parseFloat($("#sel-vel").value);
    $("#vista-catalogo").hidden = true; $("#vista-reproductor").hidden = false; history.replaceState(null, "", "#" + id);
    $("#r-titulo").textContent = d.titulo;
    const m = $("#r-meta"); m.textContent = ""; m.append(insignia(d.tipo)); [`Rojo: ${d.modelos.rojo}`, `Azul: ${d.modelos.azul}`, `semilla ${d.semilla}`, `grafo ${d.dificultad}`, `hojas recorridas: ${d.hoja}`, `hash del grafo ${d.hash_grafo.slice(0, 12)}…`, d.cadena_integra ? "cadena de hashes íntegra" : "CADENA ROTA"].forEach((t) => m.append(el("span", "chip sin-punto " + (t === "CADENA ROTA" ? "chip-error" : "chip-neutro"), t)));
    const a = el("a", "chip chip-info sin-punto", "Ver registro (JSON)"); a.href = "/api/simulacion/" + encodeURIComponent(id); a.target = "_blank"; a.rel = "noopener"; m.append(a);
    $("#nota-ritmo").textContent = "Reproducción a ritmo narrativo (≈ 10 min): no es la duración real de la ejecución, que fue de milisegundos. " + (INSIGNIA[d.tipo] ? INSIGNIA[d.tipo][2] : "");
    const hit = $("#hitos"); hit.textContent = ""; S.items.filter((x) => x.hito).forEach((x) => { const i = el("i", x.k === "resultado" ? "fin" : x.actor); i.style.left = (x.t * 100) + "%"; i.title = x.titulo; i.addEventListener("click", () => { pausar(); S.t = x.t * total(); aplicarTiempo(); }); hit.append(i); });
    $("#cron").textContent = ""; dibujarGrafo(d.grafo); aplicarTiempo();
  }

  (async function iniciar() {
    await cargarCatalogo();
    const h = location.hash.replace("#", ""); if (h.startsWith("sim-")) abrir(h);
  })();
})();
