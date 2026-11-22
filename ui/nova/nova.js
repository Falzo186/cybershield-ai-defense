/* Nova · interfaz por rol. Sin dependencias ni build. TODO texto dinámico entra por textContent. El estado real lo manda el servidor
   (SSE + sondeo de respaldo): aquí no se calcula ni se inventa nada, y cada botón llama a una operación real del motor. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, cls, texto) => { const e = document.createElement(tag); if (cls) e.className = cls; if (texto != null) e.textContent = texto; return e; };
  const LS = { get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* bloqueado */ } } };
  const S = { token: null, rol: null, nombre: null, est: null, ultimoSeq: 0, eventos: [], clave: 0 };
  const ROLES = { general: "ADMIN", rojo: "RED", azul: "BLUE", espectador: "SPECTATOR" };
  const NOMBRE_ROL = { ADMIN: "Administrador", RED: "Equipo Rojo", BLUE: "Equipo Azul", SPECTATOR: "Espectador" };
  const mmss = (s) => String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(Math.floor(s % 60)).padStart(2, "0");

  async function api(metodo, ruta, cuerpo, crudo) {
    const h = { Accept: "application/json" }; if (S.token) h["X-Equipo-Token"] = S.token; if (cuerpo !== undefined) h["Content-Type"] = "application/json";
    let r; try { r = await fetch(ruta, { method: metodo, headers: h, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) }); } catch (_) { const x = new Error("Sin conexión con el servidor"); x.red = true; throw x; }
    if (crudo) return r;
    let d = null; try { d = await r.json(); } catch (_) { /* sin cuerpo */ }
    if (!r.ok) { const x = new Error((d && (d.mensaje || d.error || d.detail)) || "Error " + r.status); x.status = r.status; x.datos = d; throw x; }
    return d;
  }
  function toast(msg, tipo = "") { const t = el("div", "toast " + tipo, msg); $("#toasts").append(t); setTimeout(() => t.remove(), 4500); }
  const intentar = async (fn, ok) => { try { const r = await fn(); if (ok) toast(ok, "ok"); await refrescar(); return r; } catch (e) { toast(e.message, "error"); await refrescar(); return null; } };

  // ── Sesión ──────────────────────────────────────────────────────────────────────────────────────
  async function recuperar() {
    for (const rol of ["general", "rojo", "azul"]) {
      const t = LS.get("cs_sesion_" + rol); if (!t) continue; S.token = t;
      try { const s = await api("GET", "/api/sesion"); S.rol = ROLES[s.participante.equipo]; S.nombre = s.participante.nombre; return true; } catch (e) { S.token = null; if (e.status === 403) LS.set("cs_sesion_" + rol, ""); }
    }
    return false;
  }
  $("#e-rol").addEventListener("change", () => { $("#e-codigo-wrap").hidden = $("#e-rol").value !== "general"; $("#e-nombre").required = $("#e-rol").value !== "espectador"; });
  $("#form-entrar").addEventListener("submit", async (ev) => {
    ev.preventDefault(); $("#e-error").textContent = ""; const rol = $("#e-rol").value;
    try {
      if (rol === "espectador") { S.token = null; S.rol = "SPECTATOR"; S.nombre = null; arrancar(); return; }
      const r = await api("POST", "/api/sesion", { nombre: $("#e-nombre").value.trim(), equipo: rol, codigo: rol === "general" ? $("#e-codigo").value.trim() : undefined });
      S.token = r.token; S.rol = ROLES[r.participante.equipo]; S.nombre = r.participante.nombre; LS.set("cs_sesion_" + rol, r.token); LS.set("cs_nombre", S.nombre); arrancar();
    } catch (e) { $("#e-error").textContent = e.message; }
  });

  // ── Estado ──────────────────────────────────────────────────────────────────────────────────────
  async function refrescar() {
    try { S.est = await api("GET", "/api/nova/estado"); } catch (_) { return; }
    pintar(); cargarEventos();
  }
  const visible = (id, v) => { $(id).hidden = !v; };
  function pintar() {
    const e = S.est; if (!e) return;
    const sin = e.estado == null;
    $("#chip-estado").textContent = sin ? "SIN PARTIDA" : e.estado.replace(/_/g, " "); $("#chip-yo").textContent = NOMBRE_ROL[S.rol] + (S.nombre ? " · " + S.nombre : "");
    $("#chip-reloj").textContent = sin ? "—" : `${mmss(e.t_s)} / ${mmss(e.duracion_s)}`;
    const b = $("#banner-estado"); b.className = "banner-estado" + (e.estado === "EN_CURSO" ? " en-curso" : e.estado === "PAUSADA" ? " pausada" : ["FINALIZADA", "CANCELADA"].includes(e.estado) ? " fin" : "");
    b.textContent = sin ? (S.rol === "ADMIN" ? "No hay partida. Crea una: nada empieza hasta que tú la inicies." : "Esperando a que el administrador cree la partida.") :
      e.estado === "CONFIGURACION" ? "La partida está en configuración: el administrador debe abrir la sala de espera." : e.estado === "SALA_DE_ESPERA" ? "Sala de espera: los jugadores entran y se marcan listos. La partida NO empieza sola."
      : e.estado === "LISTA" ? "Todo listo. Solo el administrador puede iniciar la partida." : e.estado === "EN_CURSO" ? "Partida EN CURSO." : e.estado === "PAUSADA" ? "⏸ PARTIDA PAUSADA: el reloj está detenido y las acciones están bloqueadas." : "Partida terminada: " + e.estado;
    visible("#p-admin", S.rol === "ADMIN");
    if (S.rol === "ADMIN") pintarAdmin(e);
    pintarSala(e); pintarVictoria(e); pintarCatalogo(e); pintarEquipo(e);
    visible("#p-rojo-cred", ["RED", "ADMIN"].includes(S.rol) && !!e.rojo); visible("#p-rojo-op", S.rol === "RED" && !!e.rojo);
    if (e.rojo) pintarRojo(e);
    pintarConstructor(e);
    pintarJugadores(e);
    pintarEstadoIA(e);
    const az = S.rol === "BLUE" && e.azul; for (const id of ["#p-azul-id", "#p-azul-bandeja", "#p-azul-aprob", "#p-azul-alertas"]) visible(id, !!az);
    if (az) pintarAzul(e); else if (S.rol === "ADMIN" && e.azul_todos) pintarAdminAzul(e);
    pintarPub(e);
  }

  // ── Administrador ───────────────────────────────────────────────────────────────────────────────
  function pintarAdmin(e) {
    const st = e.estado; const hab = (id, ok) => { $(id).disabled = !ok; };
    hab("#btn-crear", st == null || ["FINALIZADA", "CANCELADA"].includes(st)); hab("#b-sala", st === "CONFIGURACION"); hab("#b-lista", st === "SALA_DE_ESPERA");
    hab("#b-iniciar", st === "LISTA"); hab("#b-pausar", st === "EN_CURSO"); hab("#b-reanudar", st === "PAUSADA"); hab("#b-detener", ["EN_CURSO", "PAUSADA"].includes(st)); hab("#b-cancelar", ["EN_CURSO", "PAUSADA"].includes(st));
    hab("#b-ia", st != null && !["FINALIZADA", "CANCELADA"].includes(st));
    if (e.ia) { $("#ia-estado").textContent = `IA Roja: ${e.ia.modos.RED} · ${e.ia.proveedores.RED.etiqueta} — IA Azul: ${e.ia.modos.BLUE} · ${e.ia.proveedores.BLUE.etiqueta} — corridas registradas: ${e.ia.corridas}`; }
  }
  $("#form-crear").addEventListener("submit", (ev) => { ev.preventDefault();
    intentar(() => api("POST", "/api/nova/partida", { duration_s: parseInt($("#c-dur").value, 10), time_scale: parseFloat($("#c-esc").value), modalidad: $("#c-mod").value, ai_prompt_mode: $("#c-pmodo").value, approval_mode: $("#c-amodo").value, ai_prompt_budget: parseInt($("#c-pres").value, 10) || 10, win: { reglas: $("#c-win").value.split(",") } }), "Partida creada (en configuración)"); });
  $("#b-sala").addEventListener("click", () => intentar(() => api("POST", "/api/nova/sala"), "Sala de espera abierta"));
  $("#b-lista").addEventListener("click", () => intentar(() => api("POST", "/api/nova/lista"), "Partida marcada LISTA"));
  $("#b-iniciar").addEventListener("click", () => { if (window.confirm("¿Iniciar la partida? Esta acción la inicia de verdad.")) intentar(() => api("POST", "/api/nova/iniciar", { confirm: true, idempotency_key: "ui-" + Date.now() + "-" + Math.random().toString(36).slice(2) }), "Partida iniciada"); });
  $("#b-pausar").addEventListener("click", () => intentar(() => api("POST", "/api/nova/pausar"), "Partida en pausa"));
  $("#b-reanudar").addEventListener("click", () => intentar(() => api("POST", "/api/nova/reanudar"), "Partida reanudada"));
  $("#b-detener").addEventListener("click", () => { if (window.confirm("¿Detener y finalizar la partida?")) intentar(() => api("POST", "/api/nova/detener", {}), "Partida detenida"); });
  $("#b-cancelar").addEventListener("click", () => { if (window.confirm("¿Cancelar la partida sin resultado?")) intentar(() => api("POST", "/api/nova/detener", { cancelar: true }), "Partida cancelada"); });
  $("#ia-prov").addEventListener("change", () => { $("#ia-ollama").hidden = $("#ia-prov").value !== "ollama"; });
  $("#b-ia").addEventListener("click", () => { const tipo = $("#ia-prov").value; const prov = tipo === "ollama" ? { tipo, endpoint: $("#ia-endpoint").value.trim(), modelo: $("#ia-modelo").value.trim() } : { tipo };
    intentar(() => api("POST", "/api/nova/ia/config", { RED: { modo: $("#ia-rojo-modo").value, proveedor: prov }, BLUE: { modo: $("#ia-azul-modo").value, proveedor: prov } }), "IA configurada"); });

  // ── Catálogo (admin), misiones y mensajes ───────────────────────────────────────────────────────
  let mostrar = false;
  function pintarCatalogo(e) {
    visible("#p-catalogo", S.rol === "ADMIN" && !!e.catalogo); if (!(S.rol === "ADMIN" && e.catalogo)) return;
    const c = $("#catalogo"); c.textContent = ""; e.catalogo.forEach((x) => { const f = el("div", "cat"); f.append(el("span", "", `${x.id} · ${x.nombre} (${x.depto})`), el("span", "", `${x.estado}${x.debil ? " · débil" : ""}`), el("b", "", mostrar ? x.credencial : x.credencial.slice(0, 2) + "***" + x.credencial.slice(-1))); c.append(f); });
    $("#b-mostrar").textContent = mostrar ? "Ocultar valores" : "Mostrar valores";
  }
  $("#b-mostrar").addEventListener("click", () => { mostrar = !mostrar; pintarCatalogo(S.est); });
  function pintarEquipo(e) {
    const datos = S.rol === "RED" ? e.rojo : S.rol === "BLUE" ? e.azul : null; visible("#p-misiones", !!datos); visible("#p-msg", !!datos); if (!datos) return;
    const m = $("#misiones"); m.textContent = ""; (datos.misiones || []).forEach((x) => { const f = el("div", "mis"); f.append(el("span", "", x.titulo), el("span", "chip sin-punto " + (x.estado === "COMPLETADA" ? "chip-ok" : x.estado === "EN_PROGRESO" ? "chip-aviso" : "chip-neutro"), x.estado)); m.append(f); });
    const ms = $("#msgs"); ms.textContent = ""; (datos.mensajes || []).forEach((x) => ms.append(el("div", "", `${x.autor}: ${x.texto}`))); if (!(datos.mensajes || []).length) ms.append(el("div", "vacio-eq", "Sin mensajes todavía."));
    visible("#form-tarea", S.rol === "BLUE"); const t = $("#tareas"); t.textContent = "";
    (datos.tareas || []).forEach((x) => { const d = el("div", "ap"); d.append(el("b", "", `${x.id} · ${x.titulo} · ${x.estado}`), el("small", "", "Asignada a " + x.asignado));
      const sig = { PENDIENTE: "EN_PROGRESO", EN_PROGRESO: "ESPERANDO_APROBACION", ESPERANDO_APROBACION: "COMPLETADA" }[x.estado]; if (sig) { const b = el("button", "boton", "Pasar a " + sig.replace("_", " ")); b.addEventListener("click", () => acc("set_task_status", { task_id: x.id, estado: sig })); d.append(b); } t.append(d); });
  }
  $("#form-msg").addEventListener("submit", async (ev) => { ev.preventDefault(); const t = $("#m-texto").value.trim(); if (!t) return; $("#m-texto").value = ""; await acc("message_team", { texto: t }); });
  $("#form-tarea").addEventListener("submit", async (ev) => { ev.preventDefault(); const t = $("#t-titulo").value.trim(); if (!t) return; $("#t-titulo").value = ""; await acc("assign_task", { titulo: t }, "Tarea creada"); });

  // ── Sala / participantes ────────────────────────────────────────────────────────────────────────
  function pintarSala(e) {
    const c = $("#lista-part"); c.textContent = ""; $("#n-part").textContent = String((e.participantes || []).length);
    (e.participantes || []).forEach((p) => { const f = el("div", "part " + (p.equipo === "RED" ? "rojo" : p.equipo === "BLUE" ? "azul" : "")); f.append(el("b", "", p.nombre), el("span", "chip chip-neutro sin-punto", NOMBRE_ROL[p.equipo] || p.equipo));
      if (p.identidad) f.append(el("span", "chip chip-info sin-punto", p.identidad));
      if (S.rol === "ADMIN" && p.equipo === "BLUE" && ["SALA_DE_ESPERA", "LISTA"].includes(e.estado)) { const sel = el("select"); sel.setAttribute("aria-label", "Reasignar identidad de " + p.nombre); ["EMP-01", "EMP-02", "EMP-03", "EMP-04", "EMP-05", "EMP-06"].forEach((i) => { const o = el("option", "", i); o.value = i; sel.append(o); }); sel.value = p.identidad; sel.addEventListener("change", () => intentar(() => api("POST", "/api/nova/reasignar", { jugador: p.nombre, identidad: sel.value }), "Identidad reasignada")); f.append(sel); } f.append(el("small", "", (p.listo ? "listo" : "no listo") + " · " + (p.conectado ? "conectado" : "desconectado"))); c.append(f); });
    if (!e.participantes || !e.participantes.length) c.append(el("div", "vacio-eq", "Todavía no hay participantes."));
    const yo = (e.participantes || []).find((p) => p.nombre === S.nombre);
    visible("#b-unirse", !!S.token && ["RED", "BLUE"].includes(S.rol) && !yo && ["SALA_DE_ESPERA", "LISTA", "EN_CURSO", "PAUSADA"].includes(e.estado));
    visible("#b-listo", !!yo && ["SALA_DE_ESPERA", "LISTA"].includes(e.estado)); if (yo) $("#b-listo").textContent = yo.listo ? "Ya no estoy listo" : "Estoy listo";
  }
  $("#b-unirse").addEventListener("click", () => intentar(() => api("POST", "/api/nova/unirse", {}), "Te uniste a la partida"));
  $("#b-listo").addEventListener("click", () => { const yo = (S.est.participantes || []).find((p) => p.nombre === S.nombre); intentar(() => api("POST", "/api/nova/listo", { listo: !(yo && yo.listo) })); });

  // ── Rojo ────────────────────────────────────────────────────────────────────────────────────────
  const ETQ = { DESCONOCIDA: "Desconocida", IDENTIFICADA: "Identificada (sin credencial)", CANDIDATA: "Candidata (pendiente de validar)", VALIDA_DESCUBIERTA: "Credencial válida descubierta", COMPROMETIDA: "Comprometida", BLOQUEADA: "Bloqueada / revocada" };
  function pintarRojo(e) {
    const r = e.rojo; const c = $("#creds"); c.textContent = "";
    const desc = r.credenciales.filter((x) => x.estado === "VALIDA_DESCUBIERTA").length; $("#n-desc").textContent = `${desc} de ${r.credenciales.length}`;
    r.credenciales.forEach((x) => { const t = el("div", "cred " + x.estado); t.append(el("h4", "", x.nombre ? x.nombre : "Identidad " + x.id), el("small", "", x.id + (x.depto ? " · " + x.depto : "")), el("span", "chip sin-punto chip-neutro", ETQ[x.estado] || x.estado));
      if (x.credencial) t.append(el("b", "", "Credencial: " + x.credencial)); if (x.origen) t.append(el("small", "", "Origen: " + x.origen)); c.append(t); });
    if (S.rol !== "RED") return;
    const sel = $("#op-ident"); const previo = sel.value; if (sel.options.length === 0) r.credenciales.forEach((x) => { const o = el("option", "", x.id + (x.nombre ? " · " + x.nombre : "")); o.value = x.id; sel.append(o); }); if (previo) sel.value = previo;
    if ($("#op-plant").options.length === 0) r.plantillas.forEach((p) => { const o = el("option", "", p.replace(/_/g, " ")); o.value = p; $("#op-plant").append(o); });
    if ($("#op-tabla").options.length === 0) r.tablas.forEach((t) => { const o = el("option", "", t); o.value = t; $("#op-tabla").append(o); });
    ajustarOp();
    const ia = e.ia && e.ia.modos.RED !== "off"; visible("#ia-rojo", !!ia);
    const el2 = $("#elev-rojo"); el2.textContent = ""; (r.aprobaciones || []).forEach((a) => { const d = el("div", "ap"); d.append(el("b", "", `Solicitud ${a.id}: ${a.operacion} → ${a.estado}`), el("small", "", a.motivo)); el2.append(d); });
  }
  function ajustarOp() { const a = $("#op-accion").value;
    visible("#op-id-w", !["scan_directory", "request_elevation", "export_database"].includes(a)); visible("#op-pl-w", a === "send_email"); visible("#op-cuerpo-w", ["send_email", "request_elevation"].includes(a));
    visible("#op-cand-w", a === "guess_credential"); visible("#op-tab-w", a === "extract_table"); }
  $("#op-accion").addEventListener("change", ajustarOp);
  $("#form-op").addEventListener("submit", async (ev) => {
    ev.preventDefault(); const a = $("#op-accion").value; const p = {};
    if (!["scan_directory", "request_elevation", "export_database"].includes(a)) p.identidad_id = $("#op-ident").value;
    if (a === "send_email") { p.plantilla = $("#op-plant").value; p.cuerpo = $("#op-cuerpo").value; }
    const obj = $("#op-obj").value, est = $("#op-estr").value; if (obj || est) p.meta = { objetivo: obj, estrategia: est };
    if (a === "request_elevation") p.motivo = $("#op-cuerpo").value; if (a === "guess_credential") p.candidate_value = $("#op-cand").value.trim().toUpperCase(); if (a === "extract_table") p.tabla = $("#op-tabla").value;
    const r = await api("POST", "/api/nova/accion", { action_type: a, params: p, idempotency_key: "op-" + Date.now() + Math.random().toString(36).slice(2) }, true); const d = await r.json();
    $("#op-resultado").textContent = r.ok ? "Operación aceptada por el motor." + (d.data && d.data.acierto != null ? (d.data.acierto ? " ¡Credencial válida!" : " Credencial incorrecta.") : "") : "Rechazada por el motor: " + d.mensaje + " (" + d.reject_reason + ")";
    if (!r.ok) toast(d.mensaje, "error"); await refrescar();
  });
  async function propuesta(eq, cont, directiva) {
    try { const r = await api("POST", "/api/nova/ia/proponer", { equipo: eq, directiva }); const c = $(cont); c.textContent = "";
      const d = el("div", "prop"); const o = r.salida_estructurada || {};
      d.append(el("b", "", `${r.provider_kind === "scripted" ? "SIMULADO – no es una IA" : "Ollama " + (r.modelo || "")} · corrida ${r.run_id} · ${r.estado}`));
      if (r.propuesta && r.propuesta.estado === "INVALIDA") d.append(el("span", "", "La IA respondió algo que no cumple el esquema: no se ejecuta nada.")); else if (r.estado === "FALLIDA") d.append(el("span", "", "La IA falló: " + (r.error || "sin detalle")));
      else { d.append(el("span", "", (o.operation_name || o.verdict || "propuesta") + " — " + (o.justification || o.reasoning || "")));
        const pa = o.proposed_action || o.recommended_action; if (pa) d.append(el("small", "", "Acción: " + pa.action_type));
        if (r.propuesta && r.propuesta.estado === "PROPUESTA") { const a = el("div", "acciones-form"); const ok = el("button", "boton boton-primario", "Confirmar y ejecutar"), no = el("button", "boton", "Descartar");
          ok.addEventListener("click", () => intentar(() => api("POST", "/api/nova/ia/confirmar", { run_id: r.run_id }), "Propuesta ejecutada por el motor")); no.addEventListener("click", () => intentar(() => api("POST", "/api/nova/ia/confirmar", { run_id: r.run_id, descartar: true }), "Propuesta descartada")); a.append(ok, no); d.append(a); }
        else if (r.propuesta) d.append(el("small", "", "Estado de la propuesta: " + r.propuesta.estado + (r.propuesta.reject_reason ? " (" + r.propuesta.reject_reason + ")" : ""))); }
      c.append(d); await refrescar();
    } catch (e) { toast(e.message, "error"); }
  }
  // ── Constructor de prompts: el jugador elige PARTES de catálogo; la IA solo se lanza al pulsar y cada lanzamiento gasta una oportunidad ──
  function llena(sel, vals, vacio) { const s = $(sel); const sig = JSON.stringify([vals, vacio]); if (s.dataset.sig === sig) return; s.dataset.sig = sig; const previo = s.value; s.textContent = ""; if (vacio != null) { const o = el("option", "", vacio); o.value = ""; s.append(o); }
    vals.forEach((v) => { const o = el("option", "", v.t || String(v).replace(/_/g, " ")); o.value = v.v || v; s.append(o); }); if ([...s.options].some((o) => o.value === previo)) s.value = previo; }
  function pintarConstructor(e) {
    const c = e.ia && e.ia.catalogo_directiva; if (!c) return; const op = e.ia.oportunidades || {};
    const txt = (o) => o ? (o.modo === "controlado" ? `Oportunidades: ${o.restantes} de ${o.total}` : "Prompts libres (ensayo)") : "";
    $("#op-restantes-rojo").textContent = txt(op.RED); $("#op-restantes-azul").textContent = txt(op.BLUE);
    $("#b-prop-rojo").disabled = !!(op.RED && op.RED.modo === "controlado" && op.RED.restantes === 0); $("#b-prop-azul").disabled = !!(op.BLUE && op.BLUE.modo === "controlado" && op.BLUE.restantes === 0);
    if (e.rojo) { llena("#d-accion", c.acciones_rojo); llena("#d-obj", c.objetivos); llena("#d-estr", c.estrategias, "(sin estrategia)"); llena("#d-ident", c.identidades, "(ninguna)"); llena("#d-tabla", c.tablas, "(ninguna)"); llena("#d-plant", c.plantillas, "(ninguna)");
      const desbloq = (e.rojo.credenciales || []).filter((x) => x.credencial).map((x) => ({ v: "conocida:" + x.id, t: `Usar la credencial obtenida de ${x.id} (${x.credencial})` }));
      llena("#d-cred", [{ v: "ninguna", t: "Sin credencial" }, { v: "aleatoria", t: "Inventar una credencial aleatoria con esta estructura" }, ...desbloq]); $("#d-estruct").hidden = $("#d-cred").value !== "aleatoria"; }
    if (e.azul || e.rol === "ADMIN") { llena("#e-foco", c.focos_azul); llena("#e-acc", c.acciones_azul, "(la IA decide)");
      const a = e.azul || {}; const sujetos = [...(a.alertas || []).map((x) => x.id), ...(a.aprobaciones || []).filter((x) => ["PENDIENTE", "INFO_SOLICITADA", "ESCALADA"].includes(x.estado)).map((x) => x.id), ...c.identidades, ...(a.correos || []).map((x) => x.id)];
      llena("#e-suj", sujetos, "(ninguno)"); }
  }
  $("#d-cred").addEventListener("change", () => { $("#d-estruct").hidden = $("#d-cred").value !== "aleatoria"; });
  $("#form-dir-rojo").addEventListener("submit", (ev) => { ev.preventDefault(); const cr = $("#d-cred").value; const credencial = cr.startsWith("conocida:") ? { modo: "conocida" } : cr === "aleatoria" ? { modo: "aleatoria", digitos_iniciales: $("#d-dig").value.trim(), letra: $("#d-letra").value.trim().toUpperCase() } : { modo: "ninguna" };
    const ident = cr.startsWith("conocida:") ? cr.split(":")[1] : $("#d-ident").value;
    propuesta("RED", "#prop-rojo", { accion: $("#d-accion").value, objetivo: $("#d-obj").value, estrategia: $("#d-estr").value, identidad_id: ident, tabla: $("#d-tabla").value, plantilla: $("#d-plant").value, credencial }); });
  $("#form-dir-azul").addEventListener("submit", (ev) => { ev.preventDefault(); propuesta("BLUE", "#prop-azul", { foco: $("#e-foco").value, sujeto_id: $("#e-suj").value, accion_preferida: $("#e-acc").value }); });

  // ── Azul ────────────────────────────────────────────────────────────────────────────────────────
  const acc = (tipo, p, ok) => intentar(async () => { const r = await api("POST", "/api/nova/accion", { action_type: tipo, params: p, idempotency_key: "az-" + Date.now() + Math.random().toString(36).slice(2) }, true); const d = await r.json(); if (!r.ok) throw new Error(d.mensaje); return d; }, ok);
  function pintarAzul(e) {
    const a = e.azul; const id = a.identidad; const c = $("#az-ident"); c.textContent = "";
    if (id) { $("#az-estado").textContent = "Credencial " + id.estado_credencial; c.append(el("b", "", `${id.nombre} · ${id.id}`), el("div", "", `${id.puesto} · ${id.depto}`), el("div", "", `Permiso base: ${id.permiso} · recurso ${id.recurso}`)); }
    const bz = $("#az-correos"); bz.textContent = ""; const sin = a.correos.filter((m) => !m.leido).length; $("#n-nl").hidden = !sin; $("#n-nl").textContent = sin + " sin leer";
    if (!a.correos.length) bz.append(el("div", "vacio-eq", "La bandeja está vacía. Los correos del escenario llegan según avanza la partida."));
    a.correos.slice().reverse().forEach((m) => { const f = el("div", "corr" + (m.leido ? "" : " nuevo")); f.append(el("b", "", m.asunto), el("small", "", `${m.de} · ${m.origen === "RED" ? "recibido" : "escenario"}${m.leido ? " · leído" : ""}${m.reportado ? " · reportado" : ""}`));
      const bt = el("div", "acciones-form"); const B = (t, fn, cls) => { const b = el("button", "boton" + (cls ? " " + cls : ""), t); b.addEventListener("click", fn); bt.append(b); };
      if (!m.leido) B("Abrir", () => acc("open_email", { email_id: m.id }));
      if (m.link_id) { B("Ver enlace", () => acc("view_link", { link_id: m.link_id }, "Enlace visualizado (lab://)")); B("Pulsar enlace", async () => { const d = await acc("click_link", { link_id: m.link_id }); if (d && d.data) { const ok = window.confirm("Página interna del laboratorio: " + d.data.aviso + "\n\n¿Pulsar «" + d.data.boton + "»?"); if (ok) acc("risk_action", { link_id: m.link_id }, "Acción de riesgo completada"); } }); B("Neutralizar enlace", () => acc("block_link", { link_id: m.link_id }, "Enlace neutralizado")); }
      B("Reportar", () => acc("report_email", { email_id: m.id }, "Correo reportado")); f.append(bt); bz.append(f); });
    const ap = $("#az-aprob"); ap.textContent = ""; const pend = a.aprobaciones.filter((x) => ["PENDIENTE", "INFO_SOLICITADA", "ESCALADA"].includes(x.estado)); $("#n-aprob").hidden = !pend.length; $("#n-aprob").textContent = pend.length + " pendiente(s)";
    if (!a.aprobaciones.length) ap.append(el("div", "vacio-eq", "No hay solicitudes."));
    a.aprobaciones.forEach((x) => { const d = el("div", "ap"); d.append(el("b", "", `${x.id} · ${x.operacion} → ${x.recurso} · ${x.estado}`), el("small", "", `Solicitante: ${x.solicitante} · riesgo ${x.riesgo} · ${x.motivo}`), ...(x.detalle ? [el("b", "", `⚠ SOLICITUD MISTERIOSA: alguien presentó una credencial parecida (${x.detalle.candidato}, ${x.detalle.coincidencias} de ${x.detalle.de} posiciones) para ${x.detalle.identidad} · ${x.detalle.nombre}. Posible jugador: ${x.detalle.jugador_posible || "sin asignar"}. ¿Fue él?`)] : []), el("small", "", `Recomendación (${x.recomendacion.origen === "ia" ? "IA" : x.recomendacion.origen === "humano" ? "humano" : "reglas, no IA"}): ${x.recomendacion.decision} — ${x.recomendacion.motivo}`), el("small", "", resumenVotos(x)));
      if (["PENDIENTE", "INFO_SOLICITADA", "ESCALADA"].includes(x.estado)) { const bt = el("div", "acciones-form"); const B = (t, tipo, cls) => { const b = el("button", "boton" + (cls ? " " + cls : ""), t); b.addEventListener("click", () => acc(tipo, { approval_id: x.id }, t)); bt.append(b); };
        B(x.detalle ? "Aceptar (fui yo / lo permito)" : "Aprobar", "approve_request", "boton-primario"); B(x.detalle ? "Denegar y bloquear identidad" : "Rechazar", "reject_request", "boton-peligro"); B("Pedir más información", "request_more_info"); B("Escalar", "escalate"); d.append(bt); } ap.append(d); });
    const al = $("#az-alertas"); al.textContent = ""; a.alertas.slice(-6).reverse().forEach((x) => { const d = el("div", "al"); d.append(el("b", "", `${x.id} · ${x.severidad} · ${x.estado}`), el("span", "", x.titulo));
      const sig = { NUEVA: "EN_ANALISIS", EN_ANALISIS: "ASIGNADA", ASIGNADA: "CONTENIDA", CONTENIDA: "RESUELTA", RESUELTA: "CERRADA" }[x.estado]; if (sig) { const b = el("button", "boton", "Pasar a " + sig.replace("_", " ")); b.addEventListener("click", () => acc("set_alert_status", { alert_id: x.id, estado: sig })); d.append(b); } al.append(d); });
    if (!a.alertas.length) al.append(el("div", "vacio-eq", "Sin alertas."));
    const inc = $("#az-inc"); inc.textContent = ""; a.incidentes.forEach((x) => { const d = el("div", "al"); d.append(el("b", "", `${x.id} · ${x.estado}`), el("span", "", x.titulo + " · identidades: " + x.identidades.join(", "))); if (x.estado === "ABIERTO") { const b = el("button", "boton boton-primario", "Contener incidente"); b.addEventListener("click", () => acc("contain_incident", { incident_id: x.id }, "Incidente contenido")); d.append(b); } inc.append(d); });
    const ia = $("#az-ident-acc"); ia.textContent = ""; ["EMP-01", "EMP-02", "EMP-03", "EMP-04", "EMP-05", "EMP-06"].forEach((i) => { const b = el("button", "boton", "Revocar " + i); b.addEventListener("click", () => { if (window.confirm("Revocar la credencial de " + i + "? Si no estaba comprometida, penaliza (falso positivo).")) acc("revoke_credential", { identidad_id: i }, "Credencial revocada"); }); ia.append(b); });
    visible("#ia-azul", !!(e.ia && e.ia.modos.BLUE !== "off"));
    dialogoSolicitudes(a);
  }
  function pintarAdminAzul(e) { /* el administrador ve el panel Rojo y el estado general en «Marcador y estado público» */ }

  // ── Estado REAL de la IA por equipo: proveedor etiquetado, endpoint, modelo y si Ollama responde de verdad ───────────
  const SONDEO = {};
  function sondearOllama(endpoint) {
    const s = SONDEO[endpoint] || (SONDEO[endpoint] = { t: 0, r: null, vivo: false }); if (Date.now() - s.t < 8000 || s.vivo) return s; s.t = Date.now(); s.vivo = true;
    api("GET", "/api/nova/ollama/estado?endpoint=" + encodeURIComponent(endpoint)).then((r) => { s.r = r; }).catch((er) => { s.r = { conectado: false, error: er.message, modelos: [] }; }).finally(() => { s.vivo = false; }); return s;
  }
  function lineaIA(eq, e) {
    const pr = e.ia.proveedores[eq]; if (!pr) return null; const nombre = eq === "RED" ? "IA Roja" : "IA Azul"; const modo = e.ia.modos[eq];
    if (pr.kind === "ollama") { const s = sondearOllama(pr.endpoint); const r = s.r; const est = !r ? "comprobando…" : r.conectado ? (r.modelos.includes(pr.modelo) ? "CONECTADO · modelo disponible" : "CONECTADO · el modelo NO está instalado") : "SIN CONEXIÓN (" + (r.error || "no responde") + ")";
      return `${nombre} · modo ${modo} · Ollama · ${pr.endpoint} · ${pr.modelo} · ${est}`; }
    return `${nombre} · modo ${modo} · ${pr.etiqueta}${pr.kind === "offline" ? "" : " (no hay modelo real conectado)"}`;
  }
  function pintarEstadoIA(e) {
    if (!e.ia) return; const r = lineaIA("RED", e), b = lineaIA("BLUE", e);
    if (S.rol === "ADMIN" || S.rol === "SPECTATOR") { const c = $("#ia-detalle"); if (c) { c.textContent = ""; [r, b].forEach((x) => { if (x) c.append(el("div", "ia-linea", x)); }); } }
    if ($("#ia-linea-rojo") && r) $("#ia-linea-rojo").textContent = r; if ($("#ia-linea-azul") && b) $("#ia-linea-azul").textContent = b;
  }

  // ── Presencia automática: latido cada 5 s mientras la pestaña esté abierta ─────────────────────────────────────
  setInterval(() => { if (S.token && (S.rol === "RED" || S.rol === "BLUE")) fetch("/api/nova/latido", { method: "POST", headers: { "X-Equipo-Token": S.token } }).catch(() => {}); }, 5000);

  // ── Lista de jugadores (panel lateral, solo nombres) ────────────────────────────────────────────
  function pintarJugadores(e) {
    visible("#b-jug", !!S.token && S.rol !== null); const ps = e.participantes || [];
    for (const [eq, cont, n] of [["RED", "#jug-rojo", "#jug-n-rojo"], ["BLUE", "#jug-azul", "#jug-n-azul"]]) {
      const c = $(cont); c.textContent = ""; const lista = ps.filter((p) => p.equipo === eq); $(n).textContent = String(lista.length);
      lista.forEach((p) => { const f = el("div", "jug " + (eq === "RED" ? "rojo" : "azul") + (p.nombre === S.nombre ? " yo" : "")); f.append(el("span", "punto" + (p.conectado ? " on" : "")), el("b", "", p.nombre)); f.title = p.conectado ? "conectado" : "desconectado"; c.append(f); });
      if (!lista.length) c.append(el("div", "vacio-eq", "Nadie todavía."));
    }
  }
  $("#b-jug").addEventListener("click", () => { const p = $("#panel-jug"); p.hidden = !p.hidden; $("#b-jug").setAttribute("aria-expanded", String(!p.hidden)); });
  $("#b-jug-cerrar").addEventListener("click", () => { $("#panel-jug").hidden = true; $("#b-jug").setAttribute("aria-expanded", "false"); });

  // ── Solicitudes del Azul: diálogo para TODOS, opiniones visibles y decisor (el primero que interviene) ─────────
  const ABIERTA = ["PENDIENTE", "INFO_SOLICITADA", "ESCALADA"]; const OCULTAS = new Set(); let dlgId = null;
  function resumenVotos(x) {
    const v = Object.entries(x.votos || {}); if (!v.length && !x.decisor) return "Sin votos todavía";
    const a = v.filter(([, q]) => q.voto === "APROBAR").length; return `Decisor: ${x.decisor || "—"} · votos: ${a} a favor, ${v.length - a} en contra`;
  }
  function filasDetalle(x) {
    const d = x.detalle || {};
    const f = [["Solicitud", `${x.id} · ${x.operacion}`], ["Qué pide", d.que_pide || x.motivo], ["Quién lo pide", d.solicitante ? `${d.solicitante} (${d.origen === "ai" ? "IA Azul" : "jugador"})` : x.solicitante],
      ["Identidad", d.sujeto || d.identidad ? `${d.sujeto || d.identidad} · ${d.nombre || ""}` : "—"], ["Credencial", d.credencial || d.candidato || "—"], ["Jugador posible", d.jugador_posible || "—"], ["Riesgo", x.riesgo],
      ["Hora de la partida", d.hora_partida_s != null ? `${d.hora_partida_s} s` : `${Math.round(x.ts_s)} s`], ["Hora real", d.hora_real || "—"]];
    if (d.coincidencias != null) f.push(["Parecido", `${d.coincidencias} de ${d.de} posiciones`]);
    if (d.ia) {
      f.push(["Corrida de IA", `${d.ia.run_id} · ${d.ia.proveedor === "scripted" ? "SIMULADO – no es una IA" : "Ollama " + (d.ia.modelo || "")}`]);
      f.push(["Prompt (directiva)", d.ia.directiva ? Object.entries(d.ia.directiva).filter(([, v]) => v).map(([k, v]) => k + ": " + (typeof v === "object" ? JSON.stringify(v) : v)).join(" · ") : "sin directiva (modo libre)"]);
    }
    f.push(["Motivo", x.motivo]); return f;
  }
  function pintarDialogo(x) {
    const d = $("#dlg-detalle"); d.textContent = ""; filasDetalle(x).forEach(([k, v]) => { const f = el("div", "dlg-fila"); f.append(el("span", "", k), el("span", "", String(v))); d.append(f); });
    $("#dlg-titulo").textContent = x.operacion === "acceso_sospechoso" ? "⚠ Solicitud misteriosa de acceso" : x.operacion === "autorizacion_ia" ? "La IA Azul pide autorización" : "Solicitud pendiente";
  }
  function pintarVotos(x) {
    const c = $("#dlg-votos"); c.textContent = ""; $("#dlg-decisor").textContent = x.decisor ? `· decide ${x.decisor}` : "· aún sin decisor: el primero en responder decide";
    Object.entries(x.votos || {}).forEach(([n, q]) => { const f = el("div", "voto " + q.voto); f.append(el("b", "", n + ": " + (q.voto === "APROBAR" ? "a favor" : "en contra")), el("span", "", q.comentario || "")); c.append(f); });
    if (!Object.keys(x.votos || {}).length) c.append(el("div", "vacio-eq", "Nadie ha opinado todavía."));
    const soyDecisor = !x.decisor || x.decisor === S.nombre;
    $("#dlg-nota").textContent = soyDecisor ? "Tu decisión cierra la solicitud." : `Decide ${x.decisor}. Tu respuesta cuenta como opinión; también se cierra si la mayoría del equipo coincide.`;
  }
  function dialogoSolicitudes(a) {
    const dlg = $("#dlg-sol"); if (!dlg || typeof dlg.showModal !== "function") return;
    const abiertas = (a.aprobaciones || []).filter((x) => ABIERTA.includes(x.estado));
    if (dlgId) {
      const x = (a.aprobaciones || []).find((q) => q.id === dlgId);
      if (!x || !ABIERTA.includes(x.estado)) { if (dlg.open) dlg.close(); if (x) toast(`Solicitud ${x.id}: ${x.estado.toLowerCase()}`, "ok"); dlgId = null; } else { pintarVotos(x); return; }
    }
    const nueva = abiertas.find((x) => !OCULTAS.has(x.id) && !(x.votos || {})[S.nombre]); if (!nueva || dlg.open) return;
    dlgId = nueva.id; $("#dlg-coment").value = ""; pintarDialogo(nueva); pintarVotos(nueva); dlg.showModal();
  }
  function responder(tipo) {
    if (!dlgId) return; const id = dlgId; const c = $("#dlg-coment").value.trim(); OCULTAS.add(id);
    intentar(async () => {
      const r = await api("POST", "/api/nova/accion", { action_type: tipo, params: { approval_id: id, comentario: c }, idempotency_key: "dlg-" + Date.now() + Math.random().toString(36).slice(2) }, true); const d = await r.json();
      if (!r.ok) throw new Error(d.mensaje || "rechazada");
      toast(d.data && d.data.voto_registrado ? "Tu opinión quedó registrada" : "Decisión aplicada", "ok"); return d;
    }, null);
  }
  $("#dlg-ok").addEventListener("click", () => responder("approve_request")); $("#dlg-no").addEventListener("click", () => responder("reject_request"));
  $("#dlg-luego").addEventListener("click", () => { if (dlgId) OCULTAS.add(dlgId); $("#dlg-sol").close(); dlgId = null; });

  // ── Público, victoria, eventos ──────────────────────────────────────────────────────────────────
  function pintarPub(e) {
    const c = $("#pub"); c.textContent = "";
    if (e.puntos) c.append(el("div", "", `Puntos — Rojo ${e.puntos.RED} · Azul ${e.puntos.BLUE}`)); if (e.continuidad != null) c.append(el("div", "", `Continuidad legítima: ${Math.round(e.continuidad * 100)} %`));
    const ex = (e.publico && e.publico.extraido) || (e.rojo && e.rojo.extraido) || {}; c.append(el("div", "", "Tablas extraídas: " + (Object.keys(ex).length ? Object.entries(ex).map(([t, n]) => `${t} (${n})`).join(", ") : "ninguna")));
    if (e.publico) c.append(el("div", "", `Alertas: ${e.publico.alertas} · incidentes: ${e.publico.incidentes}`));
    if (e.metricas) c.append(el("div", "", `Eventos: ${e.metricas.eventos} · acciones: ${e.metricas.acciones} (rechazadas: ${e.metricas.rechazadas})`));
  }
  function pintarVictoria(e) {
    const v = $("#victoria"); const r = e.resultado; v.hidden = !r; if (!r) return;
    v.className = "tarjeta victoria " + (r.resultado === "VICTORIA_ROJA" ? "roja" : r.resultado === "VICTORIA_AZUL" ? "azul" : "empate");
    $("#v-titulo").textContent = r.resultado === "VICTORIA_ROJA" ? "Victoria del Equipo Rojo" : r.resultado === "VICTORIA_AZUL" ? "Victoria del Equipo Azul" : r.resultado.replace(/_/g, " ");
    $("#v-chip").textContent = r.resultado; $("#v-motivo").textContent = r.motivo; const d = $("#v-datos"); d.textContent = "";
    [`Puntos Rojo ${r.puntos.RED} · Azul ${r.puntos.BLUE}`, `Continuidad ${Math.round(r.continuidad * 100)} %`, `Duración ${r.duracion_s} s`, `Tablas extraídas: ${r.tablas_extraidas.length}`].forEach((t) => d.append(el("span", "chip chip-neutro sin-punto", t)));
    const dl = $("#v-descargas"); dl.textContent = ""; if (r.tablas_extraidas.length && S.rol !== "BLUE") ["csv", "json", "sql"].forEach((f) => { const b = el("button", "boton", "Descargar " + f.toUpperCase()); b.addEventListener("click", async () => { const x = await api("GET", "/api/nova/descarga?formato=" + f, undefined, true); if (!x.ok) { toast("No disponible", "error"); return; } const blob = await x.blob(); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "nova." + f; a.click(); }); dl.append(b); });
  }
  async function cargarEventos() {
    let r; try { r = await api("GET", "/api/nova/eventos?after_seq=" + S.ultimoSeq); } catch (_) { return; }
    if (S.est && S.est.id !== S.clave) { S.clave = S.est.id; S.ultimoSeq = 0; S.eventos = []; r = await api("GET", "/api/nova/eventos?after_seq=0"); }
    S.eventos.push(...r.eventos); S.ultimoSeq = r.ultimo; const c = $("#lista-ev"); c.textContent = ""; $("#n-ev").textContent = String(S.eventos.length);
    S.eventos.slice(-60).reverse().forEach((e) => { const f = el("div", "log"); f.append(el("span", "t", mmss(e.ts_match_ms / 1000)), el("span", "", e.type), el("span", "", resumen(e))); c.append(f); });
    if (!S.eventos.length) c.append(el("div", "vacio-eq", "Sin eventos todavía."));
  }
  const resumen = (e) => { const d = e.data || {}; return [e.actor && e.actor.label, d.asunto, d.titulo, d.tabla, d.identidad, d.estado, d.reject_reason, d.clasificacion].filter(Boolean).join(" · "); };

  // ── Tiempo real ─────────────────────────────────────────────────────────────────────────────────
  function conectar() {
    const es = new EventSource("/api/eventos"); const chip = $("#chip-conexion");
    es.onopen = () => { chip.textContent = "Conectado en vivo"; chip.className = "chip chip-ok"; }; es.onerror = () => { chip.textContent = "Reconectando…"; chip.className = "chip chip-aviso"; };
    es.addEventListener("nova_estado", () => refrescar()); es.addEventListener("nova_evento", () => refrescar());
  }
  function arrancar() { $("#entrar").hidden = true; $("#principal").hidden = false; conectar(); refrescar(); setInterval(refrescar, 2000); if (S.token) setInterval(() => api("POST", "/api/presencia", {}).catch(() => {}), 20000); }
  (async function iniciar() { if (await recuperar()) arrancar(); else { $("#entrar").hidden = false; $("#e-nombre").value = LS.get("cs_nombre") || ""; } })();
})();
