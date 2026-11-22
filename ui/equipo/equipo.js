/* Sala de equipo · CyberShield Repair. Sin dependencias ni build. TODO texto dinámico entra por textContent.
   El estado real lo manda el servidor (SSE + sondeo de respaldo); aquí no se inventa nada: si el servidor no responde se dice. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, cls, texto) => { const e = document.createElement(tag); if (cls) e.className = cls; if (texto != null) e.textContent = texto; return e; };
  const LS = { get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* bloqueado */ } } };
  const S = { token: null, rol: null, nombre: null, partida: null, base: 0, relojT: null, ultimoChat: 0, sse: null };
  const NOMBRE_EQ = { rojo: "Equipo Rojo", azul: "Equipo Azul", general: "Árbitro", espectador: "Espectadores" };

  async function api(metodo, ruta, cuerpo) {
    const h = { Accept: "application/json" };
    if (S.token) h["X-Equipo-Token"] = S.token;
    if (cuerpo !== undefined) h["Content-Type"] = "application/json";
    let r;
    try { r = await fetch(ruta, { method: metodo, headers: h, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) }); }
    catch (_) { const x = new Error("Sin conexión con el servidor"); x.red = true; throw x; }
    let d = null; try { d = await r.json(); } catch (_) { /* sin cuerpo */ }
    if (!r.ok) { const x = new Error((d && (d.error || d.mensaje || d.detail)) || "Error " + r.status); x.status = r.status; throw x; }
    return d;
  }
  function toast(msg, tipo = "") { const t = el("div", "toast " + tipo, msg); $("#toasts").append(t); setTimeout(() => t.remove(), 4000); }
  const mmss = (s) => String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  const hora = (iso) => { try { return new Date(iso).toLocaleTimeString("es-MX", { hour12: false }); } catch (_) { return "—"; } };

  // ── Sesión ──────────────────────────────────────────────────────────────────────────────────────
  async function recuperar() {
    const pedido = new URLSearchParams(location.search).get("rol");
    const orden = pedido ? [pedido] : ["general", "rojo", "azul"];
    for (const rol of orden) {
      const t = LS.get("cs_sesion_" + rol);
      if (!t) continue;
      S.token = t;
      try { const s = await api("GET", "/api/sesion"); S.rol = s.participante.equipo; S.nombre = s.participante.nombre; return s; }
      catch (e) { S.token = null; if (e.status === 403) LS.set("cs_sesion_" + rol, ""); }
    }
    return null;
  }
  $("#e-rol").addEventListener("change", () => { $("#e-codigo-wrap").hidden = $("#e-rol").value !== "general"; });
  $("#form-entrar").addEventListener("submit", async (ev) => {
    ev.preventDefault(); $("#e-error").textContent = "";
    const rol = $("#e-rol").value;
    try {
      const r = await api("POST", "/api/sesion", { nombre: $("#e-nombre").value.trim(), equipo: rol, codigo: rol === "general" ? $("#e-codigo").value.trim() : undefined });
      S.token = r.token; S.rol = r.participante.equipo; S.nombre = r.participante.nombre;
      LS.set("cs_sesion_" + rol, r.token); LS.set("cs_nombre", S.nombre);
      arrancar(r.partida);
    } catch (e) { $("#e-error").textContent = e.message; }
  });

  // ── Partida: estado, reloj y controles del árbitro ──────────────────────────────────────────────
  function pintarPartida(p) {
    S.partida = p; S.base = performance.now();
    const chip = $("#chip-partida"); clearInterval(S.relojT);
    const pintar = () => {
      if (p.fase === "en_curso") { const s = Math.max(0, Math.round(p.restante_s - (performance.now() - S.base) / 1000)); chip.textContent = "EN CURSO · " + mmss(s); chip.className = "chip chip-ok sin-punto"; }
      else if (p.fase === "pausada") { chip.textContent = "PAUSADA · " + mmss(p.restante_s); chip.className = "chip chip-pausada sin-punto"; }
      else if (p.fase === "finalizada") { chip.textContent = "FINALIZADA"; chip.className = "chip chip-neutro sin-punto"; }
      else { chip.textContent = "PREPARACIÓN · esperando al árbitro"; chip.className = "chip chip-neutro sin-punto"; }
    };
    pintar(); if (p.fase === "en_curso") S.relojT = setInterval(pintar, 1000);
    const arb = S.rol === "general";
    $("#controles-arbitro").hidden = !arb;
    if (arb) {
      $("#sel-dur").hidden = $("#sel-dur").parentElement.hidden = p.fase !== "preparacion";
      $("#btn-iniciar").hidden = p.fase !== "preparacion"; $("#btn-pausar").hidden = p.fase !== "en_curso";
      $("#btn-reanudar").hidden = p.fase !== "pausada"; $("#btn-finalizar").hidden = !["en_curso", "pausada"].includes(p.fase); $("#btn-nueva").hidden = p.fase !== "finalizada";
    }
    pintarParticipantes(p.participantes || []);
  }
  function pintarParticipantes(lista) {
    const cont = $("#lista-part"); cont.textContent = "";
    $("#n-conectados").textContent = lista.filter((x) => x.conectado !== false).length + " conectados";
    ["rojo", "azul", "general", "espectador"].forEach((eq) => {
      const g = lista.filter((x) => x.equipo === eq); if (!g.length) return;
      const caja = el("div", "grupo-eq " + eq); caja.append(el("h4", "", NOMBRE_EQ[eq] + " (" + g.length + ")"));
      g.forEach((x) => {
        const f = el("div", "part" + (x.conectado === false ? " fuera" : "")); const pt = el("span", "punto"); pt.setAttribute("role", "img");
        pt.setAttribute("aria-label", x.conectado === false ? "desconectado" : "conectado");
        f.append(pt, el("b", "", x.nombre), el("span", "chip chip-neutro sin-punto", x.rol), el("span", "meta", (x.conectado === false ? "desconectado " + hora(x.desconectado) : "conectado desde " + hora(x.unido))));
        caja.append(f);
      });
      cont.append(caja);
    });
    if (!lista.length) cont.append(el("div", "vacio-eq", "Todavía no hay participantes."));
  }
  async function accion(ruta, cuerpo, ok) {
    try { const r = await api("POST", ruta, cuerpo || {}); if (ok) toast(ok, "ok"); if (r && r.fase) pintarPartida(r); } catch (e) { toast(e.message, "error"); }
  }
  $("#btn-iniciar").addEventListener("click", () => accion("/api/partida/iniciar", { duracion_min: parseInt($("#sel-dur").value, 10) }, "Partida iniciada"));
  $("#btn-pausar").addEventListener("click", () => accion("/api/partida/pausar", {}, "Partida en pausa"));
  $("#btn-reanudar").addEventListener("click", () => accion("/api/partida/reanudar", {}, "Partida reanudada"));
  $("#btn-finalizar").addEventListener("click", () => { if (window.confirm("¿Finalizar la partida? Los puntajes se congelan.")) accion("/api/partida/finalizar", {}, "Partida finalizada").then(refrescarPartida); });
  $("#btn-nueva").addEventListener("click", () => accion("/api/partida/nueva", {}, "Partida nueva en preparación"));
  async function refrescarPartida() { try { pintarPartida(await api("GET", "/api/partida")); } catch (_) { /* lo cubre el chip de conexión */ } }

  // ── Solicitudes de autorización ─────────────────────────────────────────────────────────────────
  const CHIP_EST = { PENDIENTE: "chip-aviso", APROBADA: "chip-ok", RECHAZADA: "chip-error", EXPIRADA: "chip-neutro", CANCELADA: "chip-neutro" };
  async function cargarAut() {
    let r; try { r = await api("GET", "/api/autorizaciones"); } catch (_) { return; }
    const cont = $("#lista-aut"); cont.textContent = "";
    const pend = r.autorizaciones.filter((x) => x.estado === "PENDIENTE").length;
    $("#n-pend").hidden = !pend; $("#n-pend").textContent = pend + " pendiente" + (pend === 1 ? "" : "s");
    if (!r.autorizaciones.length) cont.append(el("div", "vacio-eq", S.rol === "azul" ? "No hay solicitudes pendientes." : "Sin solicitudes en esta partida."));
    r.autorizaciones.forEach((x) => {
      const c = el("div", "sol"); const l1 = el("div", "sol-linea");
      l1.append(el("span", "chip sin-punto " + (CHIP_EST[x.estado] || "chip-neutro"), x.estado), el("b", "", x.operacion + " → " + x.recurso), el("span", "chip chip-neutro sin-punto", "riesgo " + x.riesgo));
      if (x.estado === "PENDIENTE") l1.append(el("span", "chip chip-neutro sin-punto", "vence en " + mmss(x.tiempo_restante_s)));
      c.append(l1, el("small", "", "Identidad: " + x.identidad + " · jugador: " + x.jugador + " · motivo: " + x.motivo));
      if (x.recomendacion) c.append(el("small", "", "Recomendación (" + (x.recomendacion.origen === "ia" ? "IA" : "reglas, no IA") + "): " + x.recomendacion.decision + " — " + x.recomendacion.motivo));
      if (x.resuelta_por) c.append(el("small", "", "Resuelta por " + x.resuelta_por + " a las " + hora(x.resuelta)));
      if (S.rol === "azul" && x.estado === "PENDIENTE") {
        const a = el("div", "acciones"); const ap = el("button", "boton boton-primario", "Aprobar"), re = el("button", "boton boton-peligro", "Rechazar");
        ap.addEventListener("click", () => resolver(x.id, "aprobar")); re.addEventListener("click", () => resolver(x.id, "rechazar")); a.append(ap, re); c.append(a);
      }
      if ((S.rol === "rojo" || S.rol === "general") && x.estado === "PENDIENTE") { const b = el("button", "boton", "Cancelar"); b.addEventListener("click", () => resolver(x.id, "cancelar")); c.append(b); }
      cont.append(c);
    });
  }
  async function resolver(id, acc) { try { await api("POST", `/api/autorizaciones/${id}/${acc}`, {}); toast("Solicitud " + acc, "ok"); } catch (e) { toast(e.message, "error"); } cargarAut(); }
  $("#form-sol").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await api("POST", "/api/autorizaciones", { identidad: $("#s-ident").value.trim(), operacion: $("#s-op").value.trim(), recurso: $("#s-rec").value.trim(), motivo: $("#s-mot").value.trim() }); toast("Solicitud enviada al equipo Azul", "ok"); $("#form-sol").reset(); $("#s-ident").value = "ana.perez"; }
    catch (e) { toast(e.message, "error"); }
    cargarAut();
  });

  // ── Buzón (Azul) ────────────────────────────────────────────────────────────────────────────────
  async function cargarBuzon() {
    const panel = $("#panel-buzon");
    if (S.rol !== "azul") { panel.hidden = true; return; }
    let r; try { r = await api("GET", "/api/buzon"); } catch (_) { return; }
    const cont = $("#lista-buzon"); cont.textContent = "";
    $("#n-nl").hidden = !r.no_leidos; $("#n-nl").textContent = r.no_leidos + " sin leer";
    if (!r.correos.length) cont.append(el("div", "vacio-eq", "El buzón está vacío. Los correos del escenario llegan según avanza la partida."));
    r.correos.filter((c) => c.carpeta === "entrada").forEach((c) => {
      const leido = (c.leido_por || "").split(", ").includes(S.nombre);
      const f = el("div", "correo" + (leido ? "" : " nuevo"));
      f.append(el("b", "", c.asunto), el("span", "de", c.de + (c.origen === "escenario" ? " · escenario" : "") + " · " + hora(c.ts)));
      if (!leido) { const b = el("button", "boton", "Marcar leído"); b.addEventListener("click", async () => { try { await api("POST", `/api/correo/${c.id}/leer`, {}); } catch (e) { toast(e.message, "error"); } cargarBuzon(); }); f.append(b); }
      cont.append(f);
    });
  }

  // ── Chat ────────────────────────────────────────────────────────────────────────────────────────
  const idsChat = new Set(); let chatOcupado = false, chatOtraVez = false;
  async function cargarChat(completo) {
    if (chatOcupado) { chatOtraVez = true; return; }   // una sola carga a la vez: dos avisos seguidos no duplican mensajes
    chatOcupado = true;
    try {
      if (completo) { S.ultimoChat = 0; idsChat.clear(); $("#chat").textContent = ""; }
      let r; try { r = await api("GET", "/api/chat?desde=" + S.ultimoChat); } catch (_) { return; }
      $("#chat-eq").textContent = NOMBRE_EQ[r.equipo] || r.equipo;
      const c = $("#chat"); const pegado = c.scrollTop + c.clientHeight >= c.scrollHeight - 30;
      const vacio = c.querySelector(".vacio-eq"); if (vacio && r.mensajes.length) vacio.remove();
      r.mensajes.forEach((m) => {
        S.ultimoChat = Math.max(S.ultimoChat, m.id); if (idsChat.has(m.id)) return; idsChat.add(m.id);
        const f = el("div", "m"); f.append(el("b", "", m.autor + (r.equipo === "general" ? " (" + m.equipo + ")" : "")), el("time", "", hora(m.ts)), document.createElement("br"), document.createTextNode(m.texto)); c.append(f);
      });
      if (pegado) c.scrollTop = c.scrollHeight;
      if (!idsChat.size && !c.children.length) c.append(el("div", "vacio-eq", S.rol === "espectador" ? "Los espectadores no ven el chat de los equipos." : "Todavía no hay mensajes."));
    } finally { chatOcupado = false; if (chatOtraVez) { chatOtraVez = false; cargarChat(); } }
  }
  $("#form-chat").addEventListener("submit", async (ev) => {
    ev.preventDefault(); const t = $("#c-texto").value.trim(); if (!t) return;
    try { await api("POST", "/api/chat", { texto: t }); $("#c-texto").value = ""; cargarChat(); } catch (e) { toast(e.message, "error"); }
  });

  // ── Registro de eventos ─────────────────────────────────────────────────────────────────────────
  let primeraCat = true;
  async function cargarLog() {
    const q = new URLSearchParams(); if ($("#f-cat").value) q.set("categoria", $("#f-cat").value); if ($("#f-eq").value) q.set("equipo", $("#f-eq").value); if ($("#f-q").value.trim()) q.set("q", $("#f-q").value.trim());
    let r; try { r = await api("GET", "/api/cronologia?" + q); } catch (_) { return; }
    if (primeraCat) { primeraCat = false; r.categorias.forEach((c) => { const o = el("option", "", c); o.value = c; $("#f-cat").append(o); }); }
    const cont = $("#lista-log"); cont.textContent = "";
    if (!r.entradas.length) cont.append(el("div", "vacio-eq", "Sin eventos con este filtro."));
    r.entradas.slice().reverse().forEach((e) => { const f = el("div", "log-fila"); f.append(el("span", "t", e.t_s == null ? "—" : mmss(e.t_s)), el("span", "", e.categoria), el("span", "", e.equipo), el("span", "", e.texto)); cont.append(f); });
  }
  ["#f-cat", "#f-eq"].forEach((s) => $(s).addEventListener("change", cargarLog)); $("#f-q").addEventListener("input", () => { clearTimeout(cargarLog.t); cargarLog.t = setTimeout(cargarLog, 300); });

  // ── Tiempo real: SSE + sondeo de respaldo + latido de presencia ────────────────────────────────
  function conectarSse() {
    if (S.sse) S.sse.close();
    const es = new EventSource("/api/eventos"); S.sse = es;
    const chip = $("#chip-conexion");
    es.onopen = () => { chip.textContent = "Conectado en vivo"; chip.className = "chip chip-ok"; };
    es.onerror = () => { chip.textContent = "Reconectando…"; chip.className = "chip chip-aviso"; };
    es.addEventListener("partida_estado", (ev) => pintarPartida(JSON.parse(ev.data)));
    es.addEventListener("autorizacion", (ev) => { const d = JSON.parse(ev.data); cargarAut(); if (d.estado === "PENDIENTE" && S.rol === "azul") toast("Nueva solicitud de autorización: " + d.operacion, "ok"); cargarLog(); });
    es.addEventListener("correo_nuevo", () => { cargarBuzon(); if (S.rol === "azul") toast("Llegó un correo nuevo", "ok"); cargarLog(); });
    es.addEventListener("buzon_estado", () => cargarBuzon());
    es.addEventListener("chat", () => cargarChat());
    es.addEventListener("auditoria", () => { clearTimeout(cargarLog.s); cargarLog.s = setTimeout(cargarLog, 600); });
  }
  function arrancar(partida) {
    $("#entrar").hidden = true; $("#principal").hidden = false;
    $("#chip-yo").textContent = (NOMBRE_EQ[S.rol] || S.rol) + " · " + S.nombre;
    $("#form-sol").hidden = S.rol !== "rojo"; $("#t-aut").textContent = S.rol === "rojo" ? "Mis solicitudes de autorización" : "Solicitudes de autorización";
    if (partida) pintarPartida(partida); else refrescarPartida();
    conectarSse(); cargarAut(); cargarBuzon(); cargarChat(true); cargarLog();
    if (S.token) setInterval(() => api("POST", "/api/presencia", {}).catch(() => {}), 20000);
    setInterval(() => { refrescarPartida(); cargarAut(); cargarBuzon(); }, 15000);   // respaldo: el SSE manda, esto solo cubre cortes
  }

  (async function iniciar() {
    const s = await recuperar();
    if (s) arrancar(s.partida);
    else { $("#entrar").hidden = false; $("#e-nombre").value = LS.get("cs_nombre") || ""; try { const p = await api("GET", "/api/ia/estado"); void p; } catch (_) { toast("El servidor no responde", "error"); } }
  })();
})();
