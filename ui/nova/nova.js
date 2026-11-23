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
  // Traduce códigos y errores técnicos a frases que entienda cualquier jugador.
  const MOTIVOS = { COOLDOWN: null, PROMPT_BUDGET_EXCEEDED: "Tu equipo ya gastó todas sus oportunidades de prompt.", NOT_A_PLAYER: "Primero pulsa «Unirme a la partida».", WRONG_TEAM: "Esa acción no es de tu equipo.", MODEL_TOO_BIG: "Ese modelo es demasiado grande para esta máquina; elige uno de 4B.",
    CREDENTIAL_NOT_KNOWN: "Todavía no tienes la credencial de esa identidad. Consíguela primero (correo o intento de acceso).", PERMISSION_DENIED: "Esa identidad no tiene permiso para eso. Prueba con otra identidad o pide una elevación.", IDENTITY_LOCKED: "Esa identidad está bloqueada temporalmente por intentos fallidos.",
    CREDENTIAL_UNUSABLE: "El equipo Azul revocó esa credencial: ya no sirve.", MATCH_NOT_RUNNING: "La partida no está en curso (¿pausada o terminada?).", UNKNOWN_TARGET: "No se encontró ese elemento.", DIRECTIVA_REQUIRED: "Elige primero qué quieres pedirle a la IA.", AI_OFF: "La IA está apagada: el administrador debe encenderla.", NOT_YOUR_INBOX: "Ese correo no está en tu bandeja." };
  function humano(msg, motivo) {
    const m = String(msg || ""); const pre = S.est && S.est.rojo && S.est.rojo.presupuesto;
    const sig = pre ? ` Podrás volver a intentarlo cuando comience la siguiente ronda (en ${Math.ceil(pre.segundos_para_siguiente_ronda)} s).` : " Podrás volver a intentarlo en la siguiente ronda.";
    if (motivo === "BUDGET_EXCEEDED") { if (/correo/i.test(m)) return "Has alcanzado el límite de correos de esta ronda." + sig; if (/reconocimiento/i.test(m)) return "Has alcanzado el límite de reconocimientos de esta ronda." + sig; if (/partida/i.test(m)) return "Agotaste todos los intentos de credencial de la partida."; return "Has alcanzado el límite de intentos de esta ronda." + sig; }
    if (motivo === "COOLDOWN") return m || "Espera unos segundos antes de repetir esa acción.";
    if (motivo && MOTIVOS[motivo]) return MOTIVOS[motivo];
    if (/10061|denegó|refused|urlopen|no responde|Connection/i.test(m)) return "Ollama no está encendido en el computador anfitrión. El administrador debe pulsar «Encender Ollama» en el panel de IA (o usar el modo SIMULADO).";
    if (/timed out|timeout|tiempo/i.test(m) && /IA|Ollama|modelo/i.test(m)) return "Ollama no respondió dentro del tiempo permitido. Prueba un modelo más pequeño (4B).";
    return m;
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
    const sin = e.estado == null; $("#chip-practica").hidden = !e.practica;
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
    visible("#p-ia-rojo", S.rol === "RED" && !!e.rojo); pintarMision(e);
    pintarConstructor(e);
    pintarJugadores(e);
    pintarEstadoIA(e); pintarRapido(e); pintarOllamaAdmin(); pintarGuia(e);
    const az = S.rol === "BLUE" && e.azul; for (const id of ["#p-azul-id", "#p-azul-bandeja", "#p-azul-aprob", "#p-azul-alertas", "#p-azul-kpi", "#p-azul-monitor", "#p-ia-azul"]) visible(id, !!az);
    if (az) pintarAzul(e); else if (S.rol === "ADMIN" && e.azul_todos) pintarAdminAzul(e);
    pintarPub(e); pintarResumen(e); pintarEspectador(e); ajustarColumnas();
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
    const prac = $("#c-prac").checked; const cuerpo = { time_scale: parseFloat($("#c-esc").value), modalidad: $("#c-mod").value, ai_prompt_mode: $("#c-pmodo").value, approval_mode: $("#c-amodo").value, ai_prompt_budget: parseInt($("#c-pres").value, 10) || 10, npc_dificultad: $("#c-npc").value, win: { reglas: $("#c-win").value.split(",") } };
    if (prac) { cuerpo.practica = true; if ($("#c-npc").value === "normal") delete cuerpo.npc_dificultad; } else cuerpo.duration_s = parseInt($("#c-dur").value, 10);
    intentar(() => api("POST", "/api/nova/partida", cuerpo), prac ? "Partida de práctica creada (5 minutos)" : "Partida creada (en configuración)"); });
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
  const ETQ = { DESCONOCIDA: "Desconocida", IDENTIFICADA: "Identificada", CANDIDATA: "Candidata", VALIDA_DESCUBIERTA: "Validada", COMPROMETIDA: "Comprometida", BLOQUEADA: "Revocada" };
  const ACC = {
    scan_directory: { n: "Reconocer directorio", ayuda: "Descubre hasta 3 personas de la empresa. Es silencioso y suma puntos, pero tiene un límite por ronda.", costo: "reconocimientos", tec: "scan_directory" },
    send_email: { n: "Enviar correo de soporte", ayuda: "Envía un correo con un enlace engañoso. Solo entrega una credencial si el empleado lo pulsa; si el Azul lo reporta, pierdes la oportunidad.", costo: "correos", tec: "send_email" },
    guess_credential: { n: "Probar credencial candidata", ayuda: "Prueba una credencial de 5 dígitos y una letra. Varios fallos bloquean la identidad y avisan al Azul.", costo: "intentos_ronda", tec: "guess_credential" },
    query_resource: { n: "Consultar un recurso", ayuda: "Mira qué contiene el recurso de una identidad cuya credencial ya tienes. Puede levantar alertas.", tec: "query_resource" },
    extract_table: { n: "Extraer información", ayuda: "Descarga una tabla completa con una credencial válida. Las tablas protegidas generan una alerta crítica.", tec: "extract_table" },
    request_elevation: { n: "Solicitar elevación de permisos", ayuda: "Pide al equipo Azul permiso para exportar toda la base. Si lo aprueba, tendrás un tiempo limitado para exportar.", tec: "request_elevation" },
    export_database: { n: "Exportar la base completa", ayuda: "Copia las 8 tablas. Solo funciona mientras una elevación aprobada siga activa.", tec: "export_database" } };
  const SIN_ID = ["scan_directory", "request_elevation", "export_database"];
  const ESPERADO = { scan_directory: "Se identifican hasta 3 empleados nuevos.", send_email: "El empleado puede pulsar el enlace y exponer su credencial; el Azul puede reportarlo.", guess_credential: "Si acierta, la credencial queda validada; si falla, cuenta como intento fallido.",
    query_resource: "Se listan las tablas del recurso de esa identidad.", extract_table: "Se extrae la tabla si la identidad tiene permiso sobre ella.", request_elevation: "Llega una solicitud al Azul; si la aprueba podrás exportar la base.", export_database: "Se copian las 8 tablas si hay una elevación aprobada." };
  function pintarRojo(e) {
    const r = e.rojo; const c = $("#creds"); c.textContent = "";
    const ident = r.credenciales.filter((x) => x.estado !== "DESCONOCIDA").length; const desc = r.credenciales.filter((x) => x.estado === "VALIDA_DESCUBIERTA").length;
    $("#n-desc").textContent = `${desc} de ${r.credenciales.length}`; $("#cred-resumen").textContent = `${ident} de ${r.credenciales.length} identidades descubiertas · ${desc} con credencial válida`;
    r.credenciales.forEach((x) => { const t = el("div", "cred " + x.estado); t.append(el("h4", "", x.nombre ? x.nombre : "Identidad " + x.id), el("small", "", x.id + (x.depto ? " · " + x.depto : "")), el("span", "chip sin-punto " + (x.estado === "VALIDA_DESCUBIERTA" ? "chip-ok" : x.estado === "COMPROMETIDA" ? "chip-aviso" : "chip-neutro"), ETQ[x.estado] || x.estado));
      if (x.credencial) t.append(el("b", "", "Credencial: " + x.credencial)); t.append(el("small", "", x.origen ? "Origen: " + x.origen : "Todavía sin información")); c.append(t); });
    if (S.rol !== "RED") return;
    llena("#op-ident", r.credenciales.map((x) => ({ v: x.id, t: x.id + (x.nombre ? " · " + x.nombre + " (" + x.depto + ")" : " · sin identificar") })));
    llena("#q-ident", r.credenciales.map((x) => ({ v: x.id, t: x.id + (x.nombre ? " · " + x.nombre + " (" + x.depto + ")" : " · sin identificar") })));
    llena("#op-plant", r.plantillas.map((p) => ({ v: p, t: { aviso_soporte: "Aviso de soporte técnico", reporte_urgente: "Reporte financiero urgente", consulta_cordial: "Consulta cordial (sin engaño)" }[p] || p.replace(/_/g, " ") })));
    llena("#op-tabla", r.tablas);
    ajustarOp();
    const ia = e.ia && e.ia.modos.RED !== "off"; visible("#ia-rojo", !!ia); visible("#ia-rojo-off", !ia);
    const el2 = $("#elev-rojo"); el2.textContent = ""; (r.aprobaciones || []).forEach((a) => { const d = el("div", "ap"); d.append(el("b", "", `Solicitud al Azul ${a.id}: ${a.estado === "PENDIENTE" ? "ESPERANDO RESPUESTA" : a.estado.replace(/_/g, " ")}`), el("small", "", a.motivo)); el2.append(d); });
  }
  function ajustarOp() { const a = $("#op-accion").value;
    visible("#op-id-w", !SIN_ID.includes(a)); visible("#op-pl-w", a === "send_email"); visible("#op-cuerpo-w", ["send_email", "request_elevation"].includes(a));
    visible("#op-cand-w", a === "guess_credential"); visible("#op-tab-w", a === "extract_table"); $("#op-ayuda").textContent = ACC[a].ayuda; resumenOp(); }
  function resumenOp() {
    const a = $("#op-accion").value; const i = ACC[a]; const e = S.est; const r = e && e.rojo; const pre = (r && r.presupuesto) || {}; const box = $("#op-resumen"); if (!i || !r) return; box.textContent = "";
    box.append(el("b", "", i.n)); const l = [];
    if (!SIN_ID.includes(a)) { const q = r.credenciales.find((x) => x.id === $("#op-ident").value) || {}; l.push("Identidad: " + (q.nombre ? `${q.nombre} (${q.id})` : $("#op-ident").value || "—")); }
    if (a === "send_email") { const o = $("#op-plant").selectedOptions[0]; l.push("Plantilla: " + (o ? o.textContent : "—")); }
    if (a === "guess_credential") l.push("Candidata: " + ($("#op-cand").value || "—")); if (a === "extract_table") l.push("Tabla: " + $("#op-tabla").value);
    l.push("Esperado: " + ESPERADO[a]); l.forEach((x) => box.append(el("div", "", x)));
    const u = i.costo && pre[i.costo]; if (u) box.append(el("small", "", `Te quedan ${Math.max(0, u.max - u.usados)} de ${u.max} en esta ronda · nombre técnico: ${i.tec}`)); else box.append(el("small", "", "Nombre técnico: " + i.tec));
  }
  ["#op-accion", "#op-ident", "#op-plant", "#op-tabla"].forEach((s) => $(s).addEventListener("change", () => { if (s === "#op-accion") ajustarOp(); else resumenOp(); }));
  ["#op-cand", "#op-cuerpo"].forEach((s) => $(s).addEventListener("input", resumenOp));
  const MSG_OK = { scan_directory: (d) => `Reconocimiento completado: ${(d.data && d.data.identificadas || []).length} empleados identificados.`, send_email: () => "Correo enviado correctamente. Espera a ver si el empleado cae.", request_elevation: () => "Solicitud enviada al equipo Azul. La operación está esperando autorización.",
    export_database: () => "Copia completa realizada.", extract_table: (d) => "Información extraída" + (d.data && d.data.tabla ? `: ${d.data.tabla} (${d.data.filas} filas).` : "."), query_resource: () => "Consulta realizada: mira el resultado en el registro.", guess_credential: (d) => d.data && d.data.acierto ? "¡Credencial válida!" : "La credencial no es válida." };
  $("#form-op").addEventListener("submit", async (ev) => {
    ev.preventDefault(); const a = $("#op-accion").value; const p = {}; const b = $("#b-ejecutar"); b.disabled = true; b.textContent = "Ejecutando…";
    if (!SIN_ID.includes(a)) p.identidad_id = $("#op-ident").value;
    if (a === "send_email") { p.plantilla = $("#op-plant").value; p.cuerpo = $("#op-cuerpo").value; }
    const obj = $("#op-obj").value, est = $("#op-estr").value; if (obj || est) p.meta = { objetivo: obj, estrategia: est };
    if (a === "request_elevation") p.motivo = $("#op-cuerpo").value; if (a === "guess_credential") p.candidate_value = $("#op-cand").value.trim().toUpperCase(); if (a === "extract_table") p.tabla = $("#op-tabla").value;
    try {
      const r = await api("POST", "/api/nova/accion", { action_type: a, params: p, idempotency_key: "op-" + Date.now() + Math.random().toString(36).slice(2) }, true); const d = await r.json();
      const hum = r.ok ? "" : humano(d.mensaje, d.reject_reason);
      $("#op-resultado").textContent = r.ok ? "Operación aceptada por el motor. " + (MSG_OK[a] ? MSG_OK[a](d) : "") : "Rechazada por el motor: " + hum + (d.reject_reason ? " (" + d.reject_reason + ")" : "");
      $("#op-resultado").className = "nota-tarjeta " + (r.ok ? "ok" : "mal"); if (!r.ok) toast(hum, "error"); else toast(MSG_OK[a] ? MSG_OK[a](d) : "Operación aceptada", "ok");
    } catch (er) { $("#op-resultado").textContent = "Error: " + er.message; $("#op-resultado").className = "nota-tarjeta mal"; }
    b.disabled = false; b.textContent = "Ejecutar operación"; await refrescar();
  });
  // ── Misión guiada: fases derivadas del estado REAL; «siguiente paso» solo PREPARA la acción, nunca la ejecuta ──
  const FASES = ["Reconocimiento", "Credenciales", "Objetivo", "Preparación", "Ejecución", "Resultado"];
  const rutaDe = (e) => LS.get("cs_ruta_" + e.id);
  function estadoMision(e) {
    const r = e.rojo, cr = r.credenciales, pre = r.presupuesto || {}, ext = r.extraido || {}, ruta = rutaDe(e);
    const ident = cr.filter((x) => x.estado !== "DESCONOCIDA"), conoce = cr.filter((x) => x.credencial), fin = conoce.find((x) => x.id === "EMP-05");
    const elev = (r.aprobaciones || []).filter((a) => a.operacion === "db_export").slice(-1)[0], listoW2 = (pre.elevacion_activa_s || 0) > 0, listoW1 = !!fin;
    const h = [ident.length > 0, conoce.length > 0, !!ruta, ruta === "W1" ? listoW1 : ruta === "W2" ? listoW2 : false, ruta === "W1" ? "reportes_financieros" in ext : ruta === "W2" ? Object.keys(ext).length >= 8 : false, !!e.resultado];
    return { h, actual: h.indexOf(false) === -1 ? 5 : h.indexOf(false), ident, conoce, fin, elev, pre, ruta, ext };
  }
  function siguientePaso(e) {
    const m = estadoMision(e), r = e.rojo, pre = m.pre; const sin = (k) => pre[k] && pre[k].usados >= pre[k].max; const espera = Math.ceil(pre.segundos_para_siguiente_ronda || 0);
    if (e.resultado) return { t: "Partida terminada", x: "Revisa el resumen final arriba.", n: 6 };
    if (e.estado !== "EN_CURSO") return { t: "Espera a que empiece la partida", x: e.estado === "PAUSADA" ? "La partida está en pausa." : "El administrador debe iniciarla.", n: 1, bloq: true };
    if (!m.ident.length) return sin("reconocimientos") ? { t: "Reconocer el directorio", x: `Alcanzaste el límite de reconocimientos de esta ronda. Podrás volver a hacerlo en ${espera} s.`, n: 1, bloq: true } : { t: "Reconocer el directorio", x: "Todavía no conoces a nadie en la empresa. Reconocer el directorio identifica hasta 3 empleados.", n: 1, prep: () => preparar("scan_directory") };
    if (!m.conoce.length || (m.ruta === "W1" && !m.fin && m.actual <= 3)) {
      const objetivo = m.ident.find((x) => x.id === "EMP-05") || m.ident.find((x) => x.estado === "IDENTIFICADA") || m.ident[0];
      const plant = objetivo && ["Finanzas", "Administración"].includes(objetivo.depto) ? "reporte_urgente" : "aviso_soporte";
      if (sin("correos")) return { t: "Conseguir una credencial", x: `Alcanzaste el límite de correos de esta ronda. Podrás enviar otro en ${espera} s; mientras tanto puedes probar una credencial candidata.`, n: 2, bloq: true };
      return { t: "Conseguir una credencial", x: `Aún no tienes credencial válida${m.ruta === "W1" ? " de Finanzas" : ""}. Prepara un correo de soporte a ${objetivo.nombre || objetivo.id}: si lo pulsa, su credencial queda expuesta.`, n: 2, prep: () => preparar("send_email", { ident: objetivo.id, plant, cuerpo: "Verifica tu identidad de laboratorio para el mantenimiento." }) };
    }
    if (!m.ruta) return { t: "Elegir objetivo", x: "Elige tu ruta: tabla financiera (ruta rápida pero exige la identidad de Finanzas) o copia completa (exige que el Azul apruebe).", n: 3, ruta: true };
    if (m.ruta === "W1") return { t: "Ejecutar la extracción", x: `Tienes la credencial de ${m.fin.nombre || "Finanzas"}. Extrae la tabla financiera.`, n: 5, prep: () => preparar("extract_table", { ident: "EMP-05", tabla: "reportes_financieros" }) };
    if (!m.elev || ["RECHAZADA", "EXPIRADA"].includes(m.elev.estado) && !m.pre.elevacion_activa_s) return { t: "Preparar la operación", x: "Solicita al Azul una elevación de permisos para exportar la base. Explica un motivo creíble.", n: 4, prep: () => preparar("request_elevation", { cuerpo: "Soy de soporte TI y necesito una copia para el mantenimiento programado." }) };
    if (["PENDIENTE", "INFO_SOLICITADA", "ESCALADA"].includes(m.elev.estado)) return { t: "Esperar la autorización", x: "Tu solicitud está esperando al equipo Azul. Si piden información, respóndela.", n: 4, bloq: true };
    if ((pre.elevacion_activa_s || 0) > 0) return { t: "Ejecutar la exportación", x: `El Azul aprobó. Te quedan ${Math.round(pre.elevacion_activa_s)} s para exportar la base completa.`, n: 5, prep: () => preparar("export_database") };
    return { t: "Preparar la operación", x: "La elevación ya no está activa. Solicita otra.", n: 4, prep: () => preparar("request_elevation", { cuerpo: "Necesito repetir la copia de mantenimiento." }) };
  }
  function preparar(accion, v = {}) {
    $("#op-accion").value = accion; ajustarOp(); if (v.ident) $("#op-ident").value = v.ident; if (v.plant) $("#op-plant").value = v.plant; if (v.tabla) $("#op-tabla").value = v.tabla; if (v.cuerpo != null) $("#op-cuerpo").value = v.cuerpo; resumenOp();
    toast("Acción preparada: " + ACC[accion].n + ". Revísala y pulsa «Ejecutar operación».", "ok"); $("#p-rojo-op").scrollIntoView({ behavior: "smooth", block: "center" });
  }
  function pintarMision(e) {
    const on = S.rol === "RED" && !!e.rojo; visible("#p-mision", on); visible("#p-presu", on); if (!on) return;
    const m = estadoMision(e), s = siguientePaso(e); const ol = $("#fases"); ol.textContent = "";
    FASES.forEach((f, i) => { const gano = e.resultado && e.resultado.resultado === "VICTORIA_ROJA"; const li = el("li", m.h[i] || gano ? "hecha" : i === m.actual && !e.resultado ? "actual" : ""); li.append(el("span", "n", m.h[i] || gano ? "✓" : String(i + 1)), document.createTextNode(f)); if (i === m.actual) li.setAttribute("aria-current", "step"); ol.append(li); });
    $("#mision-paso").textContent = e.resultado ? "Misión terminada" : `Paso ${Math.min(s.n, 5)} de 5`; $("#paso-titulo").textContent = s.t; $("#paso-texto").textContent = s.x;
    const b = $("#b-siguiente-rojo"); b.disabled = !!s.bloq || e.resultado != null; b.textContent = s.ruta ? "Elegir mi objetivo" : s.bloq ? "Esperando…" : "Hacer siguiente paso"; $("#ruta").hidden = !(m.conoce.length > 0 || m.ident.length > 0) || !!e.resultado;
    document.querySelectorAll(".ruta-op").forEach((x) => x.setAttribute("aria-pressed", String(m.ruta === x.dataset.ruta)));
    pintarPresupuesto(e);
  }
  function pintarPresupuesto(e) {
    const p = e.rojo.presupuesto; if (!p) return; const c = $("#presu"); c.textContent = ""; $("#presu-ronda").textContent = `Ronda ${p.ronda + 1}`;
    const fila = (t, u, max, extra) => { const f = el("div", "presu-fila" + (u >= max ? " agotado" : "")); const a = el("div", "t"); a.append(el("span", "", t), el("span", "", extra || `${u} de ${max} usados`)); const m = el("div", "medidor"); const i = el("i"); i.style.width = Math.min(100, max ? (u / max) * 100 : 0) + "%"; m.append(i); f.append(a, m); c.append(f); };
    fila("Correos (esta ronda)", p.correos.usados, p.correos.max); fila("Reconocimientos (esta ronda)", p.reconocimientos.usados, p.reconocimientos.max); fila("Intentos de credencial (ronda)", p.intentos_ronda.usados, p.intentos_ronda.max); fila("Intentos de credencial (partida)", p.intentos_partida.usados, p.intentos_partida.max);
    if (p.espera_intento_s > 0) c.append(el("p", "nota-tarjeta", `Espera ${Math.ceil(p.espera_intento_s)} s antes de otro intento de credencial.`));
    if (p.elevacion_activa_s > 0) c.append(el("p", "nota-tarjeta ok", `Elevación activa: puedes exportar la base durante ${Math.round(p.elevacion_activa_s)} s más.`));
    c.append(el("p", "nota-tarjeta", `La siguiente ronda empieza en ${Math.ceil(p.segundos_para_siguiente_ronda)} s y se renuevan tus límites.`));
    c.append(el("p", "nota-tarjeta", `Tiempo restante de la partida: ${mmss(p.tiempo_restante_s)}`));
  }
  document.querySelectorAll(".ruta-op").forEach((b) => b.addEventListener("click", () => { if (!S.est) return; LS.set("cs_ruta_" + S.est.id, b.dataset.ruta); pintarMision(S.est); toast("Objetivo elegido: " + (b.dataset.ruta === "W1" ? "tabla financiera" : "copia completa"), "ok"); }));
  $("#b-siguiente-rojo").addEventListener("click", () => { const e = S.est; if (!e || !e.rojo) return; const s = siguientePaso(e); if (s.ruta) { $("#ruta").scrollIntoView({ behavior: "smooth", block: "center" }); toast("Elige una de las dos rutas", "ok"); } else if (s.prep) s.prep(); });
  $("#b-que-hago").addEventListener("click", () => {
    const e = S.est; if (!e || !e.rojo) return; const m = estadoMision(e), p = m.pre, s = siguientePaso(e), box = $("#que-hago"); box.hidden = !box.hidden; if (box.hidden) return; box.textContent = "";
    const t = [`Ya identificaste ${m.ident.length} de ${e.rojo.credenciales.length} empleados.`, m.conoce.length ? `Tienes ${m.conoce.length} credencial(es) válida(s): ${m.conoce.map((x) => x.nombre || x.id).join(", ")}.` : "Todavía no tienes una credencial válida."];
    const opts = []; const q = (k) => p[k] ? p[k].max - p[k].usados : 0;
    if (q("reconocimientos") > 0 && m.ident.length < e.rojo.credenciales.length) opts.push(`reconocer el directorio (te quedan ${q("reconocimientos")} esta ronda)`);
    if (q("correos") > 0) opts.push(`preparar un correo de soporte (te quedan ${q("correos")} esta ronda)`);
    if (q("intentos_ronda") > 0 && p.espera_intento_s <= 0 && m.ident.length) opts.push(`probar una credencial candidata (te quedan ${q("intentos_ronda")} intentos esta ronda)`);
    if (m.conoce.length) opts.push("extraer información con la credencial que ya tienes");
    t.push(opts.length ? "Puedes " + opts.join(", ") + "." : `Ahora mismo no tienes acciones disponibles; la siguiente ronda empieza en ${Math.ceil(p.segundos_para_siguiente_ronda)} s.`); t.push("Siguiente paso recomendado: " + s.t + ". " + s.x);
    t.forEach((x) => box.append(el("p", "", x)));
  });
  // ── Propuestas de la IA: tarjeta destacada con Ejecutar / Editar / Descartar. Nunca se ejecuta nada sin confirmar (salvo modo automático explícito) ──
  S.ia = { RED: null, BLUE: null };
  function tarjetaPropuesta(eq, r) {
    const d = el("div", "prop-card"); const sim = r.provider_kind === "scripted"; const o = r.salida_estructurada || {}; const pa = o.proposed_action || o.recommended_action || {}; const pp = pa.params || {};
    d.append(el("h4", "", eq === "RED" ? "La IA Roja propone una operación" : "La IA defensora recomienda una acción"));
    d.append(el("small", "", `${sim ? "SIMULADO – no es una IA" : "Ollama " + (r.modelo || "")} · corrida ${r.run_id} · ${r.estado}`));
    if (r.propuesta && r.propuesta.estado === "INVALIDA") { d.classList.add("error"); d.append(el("p", "", "La IA respondió algo que no cumple las reglas: no se ejecuta nada. Puedes volver a pedirle ayuda.")); return d; }
    if (r.estado === "FALLIDA") { d.classList.add("error"); d.append(el("p", "", "La IA no pudo responder. " + humano(r.error || "sin detalle"))); return d; }
    const dl = el("dl"); const f = (k, v) => { if (v) { dl.append(el("dt", "", k), el("dd", "", String(v))); } };
    f("Objetivo", (o.operation_name || o.verdict || "").replace(/_/g, " ")); f("Motivo", o.justification || o.reasoning); f("Acción", pa.action_type && (ACC[pa.action_type] ? ACC[pa.action_type].n : pa.action_type.replace(/_/g, " ")));
    f("Identidad", pp.identidad_id || pa.target); f("Recurso", pp.tabla || pp.recurso); f("Resultado esperado", ESPERADO[pa.action_type] || "");
    d.append(dl);
    const estP = r.propuesta && r.propuesta.estado;
    if (estP === "PROPUESTA") {
      d.append(el("small", "", "Modo asistido: la IA no actúa hasta que tú confirmes."));
      const a = el("div", "acciones-form"); const ok = el("button", "boton boton-primario", "Ejecutar"), ed = el("button", "boton", "Editar"), no = el("button", "boton", "Descartar");
      ok.addEventListener("click", async () => { ok.disabled = true; ok.textContent = "Ejecutando…"; const x = await intentar(() => api("POST", "/api/nova/ia/confirmar", { run_id: r.run_id }), "Propuesta ejecutada por el motor");
        if (x) { const est = (x.propuesta && x.propuesta.estado) || x.estado || "EJECUTADA"; d.append(el("p", "nota-tarjeta " + (/RECHAZ|INVALID|DENIED/.test(est) ? "mal" : "ok"), "Validación del motor: " + est + (x.propuesta && x.propuesta.reject_reason ? " (" + humano("", x.propuesta.reject_reason) + ")" : ""))); a.remove(); } else { ok.disabled = false; ok.textContent = "Ejecutar"; } });
      ed.addEventListener("click", () => { if (eq === "RED" && pa.action_type && ACC[pa.action_type]) { preparar(pa.action_type, { ident: pp.identidad_id, tabla: pp.tabla, plant: pp.plantilla, cuerpo: pp.cuerpo || pp.motivo }); } else toast("Para editarla usa tus propias acciones", ""); });
      no.addEventListener("click", async () => { const x = await intentar(() => api("POST", "/api/nova/ia/confirmar", { run_id: r.run_id, descartar: true }), "Propuesta descartada"); if (x) d.replaceChildren(el("p", "nota-tarjeta", "Propuesta descartada: no se ejecutó nada.")); });
      a.append(ok, ed, no); d.append(a);
    } else if (r.propuesta) d.append(el("p", "nota-tarjeta", "Resultado de la validación del motor: " + estP + (r.propuesta.reject_reason ? " (" + humano("", r.propuesta.reject_reason) + ")" : "")));
    return d;
  }
  async function propuesta(eq, cont, directiva) {
    const c = $(cont); const boton = eq === "RED" ? ["#b-rapido-rojo", "#b-prop-rojo"] : ["#b-rapido-azul", "#b-prop-azul"]; const bs = boton.map((x) => $(x)).filter(Boolean);
    c.textContent = ""; const pens = el("div", "prop-card pensando"); pens.append(el("div", "estado-carga", "La IA está analizando… puedes seguir jugando mientras responde.")); c.append(pens); bs.forEach((b) => { b.disabled = true; });
    const t0 = Date.now();
    try { const r = await api("POST", "/api/nova/ia/proponer", { equipo: eq, directiva }); S.ia[eq] = { t: Date.now(), ms: Date.now() - t0, run: r }; c.textContent = ""; c.append(tarjetaPropuesta(eq, r)); await refrescar();
    } catch (e) { c.textContent = ""; const er = el("div", "prop-card error"); er.append(el("p", "", humano(e.message, e.datos && e.datos.motivo))); c.append(er); toast(humano(e.message, e.datos && e.datos.motivo), "error"); }
    bs.forEach((b) => { b.disabled = false; });
  }
  // ── Modo rápido: un objetivo en lenguaje simple → el sistema arma la directiva por ti (el motor sigue validando todo) ──
  const TABLA_DE = { "EMP-05": "reportes_financieros", "EMP-03": "empleados", "EMP-01": "ventas", "EMP-02": "compras", "EMP-04": "productos" };
  function metasRapidas(e) {
    const conocidas = ((e.rojo && e.rojo.credenciales) || []).filter((x) => x.credencial); const hay = conocidas.length > 0;
    const fin = conocidas.find((x) => x.id === "EMP-05") || conocidas[0]; const n = (t, ok) => ({ v: t, t: ok ? t : t + " (necesitas una credencial primero)", off: !ok });
    return { fin, lista: [{ v: "reconocer", t: "Reconocer el directorio (ver quién existe)" }, { v: "correo", t: "Engañar a alguien por correo para conseguir su credencial" }, { v: "usar", t: hay ? "Consultar un recurso con una credencial que ya tengo" : "Consultar un recurso (necesitas una credencial primero)", off: !hay },
      { v: "extraer", t: hay ? "Extraer una tabla con una credencial que ya tengo" : "Extraer una tabla (necesitas una credencial primero)", off: !hay }, { v: "copia", t: "Pedir al Azul una copia completa de la base" }] };
  }
  function pintarRapido(e) {
    if (!e.rojo || S.rol !== "RED") return; const m = metasRapidas(e); const s = $("#q-obj"); const sig = JSON.stringify(m.lista); if (s.dataset.sig !== sig) { s.dataset.sig = sig; const p = s.value; s.textContent = ""; m.lista.forEach((o) => { const x = el("option", "", o.t); x.value = o.v; x.disabled = !!o.off; s.append(x); }); if ([...s.options].some((o) => o.value === p && !o.disabled)) s.value = p; }
    const qi = $("#q-ident"); if (qi.options.length === 0) e.rojo.credenciales.forEach((x) => { const o = el("option", "", x.id + (x.nombre ? " · " + x.nombre : "")); o.value = x.id; qi.append(o); });
    $("#q-id-w").hidden = $("#q-obj").value !== "correo";
  }
  $("#q-obj").addEventListener("change", () => { $("#q-id-w").hidden = $("#q-obj").value !== "correo"; });
  $("#b-rapido-rojo").addEventListener("click", () => {
    const e = S.est; if (!e || !e.rojo) return; const m = metasRapidas(e); const meta = $("#q-obj").value; const fin = m.fin; const ninguna = { modo: "ninguna" }; let d;
    if (meta === "reconocer") d = { accion: "scan_directory", objetivo: "info_administrativa", estrategia: "", identidad_id: "", tabla: "", plantilla: "", credencial: ninguna };
    else if (meta === "correo") d = { accion: "send_email", objetivo: "info_administrativa", estrategia: "ingenieria_social", identidad_id: $("#q-ident").value, tabla: "", plantilla: "aviso_soporte", credencial: ninguna };
    else if (meta === "usar" && fin) d = { accion: "query_resource", objetivo: "consultar_reportes_financieros", estrategia: "uso_credencial_expuesta", identidad_id: fin.id, tabla: TABLA_DE[fin.id] || "", plantilla: "", credencial: { modo: "conocida" } };
    else if (meta === "extraer" && fin) d = { accion: "extract_table", objetivo: "extraer_tabla", estrategia: "uso_credencial_expuesta", identidad_id: fin.id, tabla: TABLA_DE[fin.id] || "reportes_financieros", plantilla: "", credencial: { modo: "conocida" } };
    else if (meta === "copia") d = { accion: "request_elevation", objetivo: "copia_bd", estrategia: "solicitud_legitima", identidad_id: "", tabla: "", plantilla: "", credencial: ninguna };
    else { toast("Elige primero qué quieres intentar", "error"); return; }
    propuesta("RED", "#prop-rojo", d);
  });
  // ── Panel de Ollama del administrador: estado real, encender/apagar y modelos instalados con su tamaño ──
  function pintarOllamaAdmin() {
    if (S.rol !== "ADMIN" || $("#ia-ollama").hidden) return; const ep = $("#ia-endpoint").value.trim(); const s = sondearOllama(ep); const r = s.r; const t = $("#ollama-estado");
    if (!r) { t.textContent = "Ollama: comprobando…"; t.className = "nota-tarjeta"; return; }
    if (!r.conectado) { t.textContent = "Ollama está APAGADO. Pulsa «Encender Ollama» antes de usar la IA real."; t.className = "nota-tarjeta mal"; return; }
    const dl = $("#ia-modelos"); const sig = JSON.stringify(r.modelos_info || []); if (dl.dataset.sig !== sig) { dl.dataset.sig = sig; dl.textContent = ""; (r.modelos_info || []).filter((m) => m.permitido).forEach((m) => { const o = el("option"); o.value = m.nombre; o.label = m.nombre + (m.recomendado ? " ✔ recomendado" : ""); dl.append(o); }); }
    const mi = (r.modelos_info || []).find((m) => m.nombre === $("#ia-modelo").value.trim()); let txt = "Ollama ENCENDIDO · " + (r.modelos || []).length + " modelos instalados · máximo permitido " + r.max_b + "B";
    if (!mi) txt += " · ⚠ ese modelo no está instalado"; else if (!mi.permitido) txt += " · ⛔ demasiado grande para esta máquina"; else if (!mi.recomendado) txt += " · aviso: " + (mi.tam_b || "?") + "B funciona pero usa más RAM; para dos IAs a la vez conviene 4B";
    t.textContent = txt; t.className = "nota-tarjeta " + (mi && mi.permitido ? "ok" : "mal");
  }
  const sondeoYa = (ep) => { delete SONDEO[ep]; return sondearOllama(ep); };
  $("#b-ollama-on").addEventListener("click", async () => { const ep = $("#ia-endpoint").value.trim(); $("#ollama-estado").textContent = "Encendiendo Ollama… (puede tardar unos segundos)"; $("#b-ollama-on").disabled = true;
    try { const r = await api("POST", "/api/nova/ollama/iniciar", { endpoint: ep }); toast(r.mensaje, "ok"); } catch (er) { toast(humano(er.message), "error"); } $("#b-ollama-on").disabled = false; sondeoYa(ep); await refrescar(); });
  $("#b-ollama-off").addEventListener("click", async () => { const ep = $("#ia-endpoint").value.trim(); try { const r = await api("POST", "/api/nova/ollama/detener", {}); toast(r.mensaje, "ok"); } catch (er) { toast(humano(er.message), "error"); } sondeoYa(ep); await refrescar(); });
  // ── Guía «qué hacer ahora» y botón de siguiente paso del administrador ──
  function pintarGuia(e) {
    const st = e.estado; const yo = (e.participantes || []).find((p) => p.nombre === S.nombre); let t;
    if (S.rol === "ADMIN") t = { null: "Pulsa «Crear partida». Nada empieza hasta que tú la inicies.", CONFIGURACION: "Abre la sala de espera para que los jugadores entren.", SALA_DE_ESPERA: "Espera a que todos entren y estén listos; luego marca la partida como LISTA.", LISTA: "Pulsa Iniciar cuando todos estén preparados.", EN_CURSO: "Observa la partida. Puedes pausar o detener.", PAUSADA: "La partida está en pausa. Reanúdala cuando quieras." }[st == null ? "null" : st] || "Partida terminada: revisa el resultado arriba.";
    else if (S.rol === "SPECTATOR") t = "Estás mirando. Verás el marcador y los eventos públicos.";
    else if (st == null || st === "CONFIGURACION") t = "Espera a que el administrador abra la sala.";
    else if (!yo && ["SALA_DE_ESPERA", "LISTA", "EN_CURSO", "PAUSADA"].includes(st)) t = "Pulsa «Unirme a la partida».";
    else if (["SALA_DE_ESPERA"].includes(st)) t = "Pulsa «Estoy listo» y espera al administrador.";
    else if (st === "LISTA") t = "Todo listo: esperando a que el administrador inicie.";
    else if (st === "EN_CURSO") t = S.rol === "RED" ? "Reconoce el directorio, consigue una credencial y extrae la tabla protegida. Puedes pedir ayuda a la IA." : "Revisa tu bandeja y las alertas. Si te llega una solicitud, decide con tu equipo.";
    else if (st === "PAUSADA") t = "Partida en pausa: espera."; else t = "La partida terminó.";
    $("#guia-texto").textContent = t; visible("#guia", true);
    if (S.rol === "ADMIN") { const b = $("#b-siguiente"); const m = { null: ["Crear partida", "#btn-crear"], CONFIGURACION: ["1 · Abrir sala de espera", "#b-sala"], SALA_DE_ESPERA: ["2 · Marcar LISTA", "#b-lista"], LISTA: ["3 · Iniciar partida", "#b-iniciar"], EN_CURSO: ["Pausar partida", "#b-pausar"], PAUSADA: ["Reanudar partida", "#b-reanudar"] }[st == null ? "null" : st];
      b.textContent = m ? m[0] : "Partida terminada"; b.disabled = !m; b.dataset.destino = m ? m[1] : ""; }
  }
  $("#b-siguiente").addEventListener("click", () => { const d = $("#b-siguiente").dataset.destino; if (!d) return; if (d === "#btn-crear") $("#form-crear").requestSubmit(); else $(d).click(); });
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
  $("#form-dir-azul").addEventListener("submit", (ev) => { ev.preventDefault(); propuesta("BLUE", "#prop-azul", { foco: $("#e-foco").value, sujeto_id: $("#e-suj").value, accion_preferida: $("#e-acc").value, pedir_autorizacion: $("#e-pedir").checked }); });

  // ── Azul: centro de monitoreo ───────────────────────────────────────────────────────────────────
  const acc = (tipo, p, ok) => intentar(async () => { const r = await api("POST", "/api/nova/accion", { action_type: tipo, params: p, idempotency_key: "az-" + Date.now() + Math.random().toString(36).slice(2) }, true); const d = await r.json(); if (!r.ok) throw new Error(humano(d.mensaje, d.reject_reason || d.motivo)); return d; }, ok);
  const NIV = { NORMAL: ["●", "Normal"], ADVERTENCIA: ["▲", "Advertencia"], SOSPECHOSO: ["◆", "Sospechoso"], CRITICO: ["✖", "Crítico"] };
  const nivelDe = (p) => (p >= 75 ? "CRITICO" : p >= 50 ? "SOSPECHOSO" : p >= 25 ? "ADVERTENCIA" : "NORMAL");
  const insignia = (niv, p) => el("span", "nivel " + niv, `${NIV[niv][0]} ${NIV[niv][1]}${p != null ? " · " + p : ""}`);
  const kpi = (l, v, cls) => { const d = el("div", "kpi" + (cls ? " " + cls : "")); d.append(el("span", "v", String(v)), el("span", "l", l)); return d; };
  const MON_ABIERTOS = new Set(); S.filtroMon = null;
  function pintarKpis(m) {
    const k = $("#az-kpis"); k.textContent = ""; const niv = m.nivel || nivelDe(m.riesgo_general); const g = el("div", "kpi grande " + (niv === "CRITICO" ? "crit" : niv === "SOSPECHOSO" ? "alto" : "")); const fila = el("div"); fila.append(insignia(niv, m.riesgo_general));
    const med = el("div", "medidor " + niv); const i = el("i"); i.style.width = m.riesgo_general + "%"; med.append(i); med.setAttribute("role", "meter"); med.setAttribute("aria-valuenow", String(m.riesgo_general)); med.setAttribute("aria-valuemin", "0"); med.setAttribute("aria-valuemax", "100"); g.append(el("span", "l", "Riesgo general"), fila, med); k.append(g);
    const c = m.contadores; k.append(kpi("Alertas críticas", c.alertas_criticas, c.alertas_criticas ? "crit" : ""), kpi("Incidentes activos", c.incidentes_activos, c.incidentes_activos ? "alto" : ""), kpi("Correos sospechosos", c.correos_sospechosos, c.correos_sospechosos ? "alto" : ""), kpi("Credenciales comprometidas", c.credenciales_comprometidas, c.credenciales_comprometidas ? "crit" : ""), kpi("Solicitudes pendientes", c.solicitudes_pendientes, c.solicitudes_pendientes ? "alto" : ""));
    const ids = el("div", "ancho-kpi"); ids.style.gridColumn = "1 / -1"; ids.append(el("div", "sub-titulo", "Estado de las identidades"));
    m.identidades.forEach((x) => { const f = el("div", "id-fila"); const bad = ["COMPROMETIDA", "EXPUESTA"].includes(x.credencial); f.append(el("b", "", x.nombre), el("span", "", x.depto), el("span", "nivel " + (bad ? "CRITICO" : ["REVOCADA", "SUSPENDIDA"].includes(x.credencial) ? "ADVERTENCIA" : "NORMAL"), (bad ? "✖ " : ["REVOCADA", "SUSPENDIDA"].includes(x.credencial) ? "▲ " : "● ") + ({ PROTEGIDA: "Protegida", COMPROMETIDA: "Comprometida", EXPUESTA: "Expuesta", REVOCADA: "Revocada", SUSPENDIDA: "Suspendida" }[x.credencial] || x.credencial)), el("small", "", x.jugador ? "Jugador: " + x.jugador : "Empleado simulado (NPC)")); ids.append(f); });
    k.append(ids);
  }
  function pintarMonitor(m) {
    const c = $("#az-monitor"); c.textContent = ""; let filas = m.eventos; if (S.filtroMon) filas = filas.filter((x) => x.identidad === S.filtroMon); $("#n-mon").textContent = String(filas.length);
    if (S.filtroMon) { const b = el("button", "boton", "Quitar filtro: " + S.filtroMon + " ✕"); b.style.margin = "8px 20px"; b.addEventListener("click", () => { S.filtroMon = null; pintarMonitor(m); }); c.append(b); }
    if (!filas.length) { c.append(el("div", "estado-vacio", "Sin actividad que vigilar todavía. Cuando ocurra algo aparecerá aquí, ordenado por nivel de sospecha.")); return; }
    filas.forEach((x) => { const b = el("button", "mon-fila"); b.type = "button"; b.setAttribute("aria-expanded", String(MON_ABIERTOS.has(x.seq))); b.append(el("span", "t", mmss(x.t_s)), insignia(x.nivel, x.puntuacion), el("span", "", `${x.etiqueta}${x.identidad ? " · " + x.identidad : ""}`), el("small", "", x.estado)); c.append(b);
      if (MON_ABIERTOS.has(x.seq)) { const d = el("div", "mon-detalle"); d.append(el("p", "", "Por qué: " + x.motivo), el("p", "", `Actor: ${x.actor || "—"} · Estado: ${x.estado}`), el("p", "", "Acción sugerida: " + x.accion));
        if (x.identidad && ["credential.exposed", "credential.validated_by_engine", "credential.used", "risk_action.completed"].includes(x.tipo)) { const r = el("button", "boton boton-peligro", "Revocar credencial de " + x.identidad); r.addEventListener("click", () => { if (window.confirm("Revocar la credencial de " + x.identidad + "? Si no estaba comprometida, penaliza (falso positivo).")) acc("revoke_credential", { identidad_id: x.identidad }, "Credencial revocada"); }); d.append(r); }
        const ex = el("button", "boton", "Pedir explicación a la IA"); const exr = el("p", "nota-tarjeta"); ex.addEventListener("click", async () => { ex.disabled = true; exr.textContent = "La IA está redactando la explicación…"; try { const q = await api("POST", "/api/nova/azul/explicar", { seq: x.seq }); exr.textContent = (q.fuente === "modelo" ? "IA (" + q.modelo + "): " : "Reglas del motor: ") + q.explicacion + (q.aviso ? " — " + q.aviso : ""); } catch (er) { exr.textContent = humano(er.message); } ex.disabled = false; }); d.append(ex, exr);
        if (x.identidad) { const f = el("button", "boton", "Ver solo " + x.identidad); f.addEventListener("click", () => { S.filtroMon = x.identidad; pintarMonitor(m); }); d.append(f); } c.append(d); }
      b.addEventListener("click", () => { if (MON_ABIERTOS.has(x.seq)) MON_ABIERTOS.delete(x.seq); else MON_ABIERTOS.add(x.seq); pintarMonitor(m); }); });
  }
  function consecuencia(x, ok) {
    const op = x.operacion;
    if (op === "db_export") return ok ? "Aprobar: el Rojo podrá exportar toda la base durante un tiempo limitado. Es la vía de victoria del Rojo." : "Rechazar: el Rojo no podrá exportar la base y la solicitud se cierra.";
    if (op === "acceso_sospechoso") return ok ? "Aceptar: se da el acceso por legítimo (−5 puntos para el Azul) y se reinician los fallos de esa identidad." : "Denegar: se bloquea la identidad y el Rojo no podrá usarla por un tiempo.";
    if (op === "autorizacion_ia") return ok ? `Aprobar: se ejecutará la acción que propone la IA${x.accion_propuesta ? " (" + String(x.accion_propuesta.action_type).replace(/_/g, " ") + ")" : ""}.` : "Rechazar: la IA no actuará.";
    return ok ? "Aprobar: se atiende la solicitud y se protege la continuidad del negocio." : "Rechazar: baja la continuidad; si cae bajo el umbral, el Azul pierde.";
  }
  function tarjetaSolicitud(x, e) {
    const d = el("div", "sol-card"); const s = x.sospecha || { puntuacion: 0, motivos: [] }; const niv = nivelDe(s.puntuacion); const abierta = ABIERTA.includes(x.estado);
    const cab = el("div"); cab.append(insignia(niv, s.puntuacion)); d.append(cab, el("h4", "", ({ db_export: "Solicitud de copia completa de la base", acceso_sospechoso: "Solicitud misteriosa de acceso", autorizacion_ia: "La IA defensora pide autorización", consulta_autorizada: "Solicitud de un compañero" }[x.operacion] || x.operacion) + " · " + x.id));
    const meta = el("div", "meta"); [`Quién: ${x.solicitante}`, `Qué: ${(x.detalle && x.detalle.que_pide) || x.motivo}`, `Recurso: ${x.recurso}`, `Riesgo: ${x.riesgo}`, `Operación técnica: ${x.operacion}`, abierta && x.restante_s != null ? `Tiempo restante: ${Math.ceil(x.restante_s)} s` : `Estado: ${x.estado.toLowerCase()}`].forEach((t) => meta.append(el("span", "", t))); d.append(meta);
    if (x.detalle && x.detalle.candidato) d.append(el("div", "ia-nota", `⚠ Alguien presentó una credencial parecida (${x.detalle.candidato}, ${x.detalle.coincidencias} de ${x.detalle.de} posiciones) para ${x.detalle.identidad} · ${x.detalle.nombre}. Posible jugador: ${x.detalle.jugador_posible || "sin asignar"}.`));
    d.append(el("div", "ia-nota", `Análisis de sospecha (${x.sospecha ? "reglas del motor" : "—"}): ${s.motivos.join("; ") || "sin señales"}. Recomendación (${x.recomendacion.origen === "ia" ? "IA" : x.recomendacion.origen === "humano" ? "humano" : "reglas, no IA"}): ${x.recomendacion.decision} — ${x.recomendacion.motivo}`), el("small", "", resumenVotos(x)));
    if (abierta) { d.append(el("div", "cons", consecuencia(x, true)), el("div", "cons", consecuencia(x, false)));
      const bt = el("div", "acciones-form"); const B = (t, tipo, cls) => { const b = el("button", "boton" + (cls ? " " + cls : ""), t); b.addEventListener("click", () => acc(tipo, { approval_id: x.id }, t)); bt.append(b); };
      B(x.detalle && x.detalle.candidato ? "Aceptar (fui yo / lo permito)" : "Aprobar", "approve_request", "boton-primario"); B(x.detalle && x.detalle.candidato ? "Denegar y bloquear identidad" : "Rechazar", "reject_request", "boton-peligro"); B("Solicitar información", "request_more_info");
      const inv = el("button", "boton", "Investigar"); inv.addEventListener("click", () => { S.filtroMon = x.identidad || (x.detalle && x.detalle.identidad) || null; pintarMonitor(e.azul.monitor); $("#p-azul-monitor").scrollIntoView({ behavior: "smooth", block: "start" }); toast(S.filtroMon ? "Mostrando la actividad de " + S.filtroMon : "Revisa el monitor de eventos", "ok"); }); bt.append(inv); d.append(bt); }
    return d;
  }
  function pintarAzul(e) {
    const a = e.azul; const id = a.identidad; const c = $("#az-ident"); c.textContent = ""; const mon = a.monitor;
    if (id) { $("#az-estado").textContent = "Credencial " + id.estado_credencial; c.append(el("b", "", `${id.nombre} · ${id.id}`), el("div", "", `${id.puesto} · ${id.depto}`), el("div", "", `Permiso base: ${id.permiso} · recurso ${id.recurso}`)); }
    if (mon) { pintarKpis(mon); pintarMonitor(mon); $("#az-metodo").textContent = "puntuación por reglas del motor"; }
    const bz = $("#az-correos"); bz.textContent = ""; const sin = a.correos.filter((m) => !m.leido).length; $("#n-nl").hidden = !sin; $("#n-nl").textContent = sin + " sin leer";
    if (!a.correos.length) bz.append(el("div", "vacio-eq", "La bandeja está vacía. Los correos del escenario llegan según avanza la partida."));
    a.correos.slice().reverse().forEach((m) => { const f = el("div", "corr" + (m.leido ? "" : " nuevo")); const sc = mon && mon.correos && mon.correos[m.id]; const cab = el("div"); cab.append(el("b", "", m.asunto)); if (sc) { cab.append(document.createTextNode(" ")); cab.append(insignia(nivelDe(sc.puntuacion), sc.puntuacion)); } f.append(cab, el("small", "", `${m.de} · ${m.origen === "RED" ? "recibido" : "escenario"}${m.leido ? " · leído" : ""}${m.reportado ? " · reportado" : ""}`));
      if (sc && sc.puntuacion >= 50) f.append(el("small", "", "Señales: " + sc.motivos.join("; ")));
      const bt = el("div", "acciones-form"); const B = (t, fn, cls) => { const b = el("button", "boton" + (cls ? " " + cls : ""), t); b.addEventListener("click", fn); bt.append(b); };
      if (!m.leido) B("Abrir", () => acc("open_email", { email_id: m.id }));
      if (m.link_id) { B("Ver enlace", () => acc("view_link", { link_id: m.link_id }, "Enlace visualizado (lab://)")); B("Pulsar enlace", async () => { const d = await acc("click_link", { link_id: m.link_id }); if (d && d.data) { const ok = window.confirm("Página interna del laboratorio: " + d.data.aviso + "\n\n¿Pulsar «" + d.data.boton + "»?"); if (ok) acc("risk_action", { link_id: m.link_id }, "Acción de riesgo completada"); } }); B("Neutralizar enlace", () => acc("block_link", { link_id: m.link_id }, "Enlace neutralizado")); }
      B("Reportar", () => acc("report_email", { email_id: m.id }, "Correo reportado")); f.append(bt); bz.append(f); });
    const ap = $("#az-aprob"); ap.textContent = ""; const pend = a.aprobaciones.filter((x) => ABIERTA.includes(x.estado)); $("#n-aprob").hidden = !pend.length; $("#n-aprob").textContent = pend.length + " pendiente(s)";
    if (!pend.length) ap.append(el("div", "estado-vacio", "No hay solicitudes pendientes. Las que lleguen aparecerán aquí con su nivel de sospecha."));
    pend.forEach((x) => ap.append(tarjetaSolicitud(x, e)));
    const cerradas = a.aprobaciones.filter((x) => !ABIERTA.includes(x.estado)); if (cerradas.length) { const det = el("details", "avanzado"); det.append(el("summary", "", `Solicitudes resueltas (${cerradas.length})`)); cerradas.slice().reverse().forEach((x) => det.append(tarjetaSolicitud(x, e))); ap.append(det); }
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
    for (const [eq, chip, meta] of [["RED", "#ia-chip-rojo", "#ia-meta-rojo"], ["BLUE", "#ia-chip-azul", null]]) {
      const pr = e.ia.proveedores[eq], modo = e.ia.modos[eq]; const c = $(chip); if (!c) continue;
      c.textContent = modo === "off" ? "Apagada" : modo === "assist" ? "Asistida" : "Automática"; c.className = "chip sin-punto " + (modo === "off" ? "chip-neutro" : modo === "auto" ? "chip-aviso" : "chip-info");
      if (meta && pr) { const m = $(meta); m.textContent = ""; const ult = S.ia[eq]; const sond = pr.kind === "ollama" ? sondearOllama(pr.endpoint).r : null;
        [["Proveedor", pr.kind === "ollama" ? "Ollama" : pr.etiqueta], ["Modelo", pr.modelo || "—"], ["Conexión", pr.kind === "ollama" ? (!sond ? "comprobando…" : sond.conectado ? "conectado" : "SIN CONEXIÓN: el administrador debe encender Ollama") : pr.kind === "scripted" ? "simulada, sin modelo real" : "desconectada"],
          ["Modo", modo === "assist" ? "Asistido: tú confirmas cada operación" : modo === "auto" ? "AUTOMÁTICO: ejecuta sin confirmar" : "apagada"], ["Última inferencia", ult ? `hace ${Math.round((Date.now() - ult.t) / 1000)} s · tardó ${(ult.ms / 1000).toFixed(1)} s` : "todavía ninguna"]].forEach(([k, v]) => m.append(el("span", "", k), el("b", "", v))); }
    }
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
      if (!r.ok) throw new Error(humano(d.mensaje, d.reject_reason || d.motivo) || "rechazada");
      toast(d.data && d.data.voto_registrado ? "Tu opinión quedó registrada" : "Decisión aplicada", "ok"); return d;
    }, null);
  }
  $("#dlg-ok").addEventListener("click", () => responder("approve_request")); $("#dlg-no").addEventListener("click", () => responder("reject_request"));
  $("#dlg-luego").addEventListener("click", () => { if (dlgId) OCULTAS.add(dlgId); $("#dlg-sol").close(); dlgId = null; });

  // ── Resumen final, línea de tiempo y vista de espectador ───────────────────────────────────────────────
  const FUENTES = { admin: "Admin", jugador: "Jugador", npc: "Empleado NPC", ia: "IA", motor: "Motor" };
  function listaTiempo(cont, lt, filtro) {
    cont.textContent = ""; const f = lt.filter((x) => !filtro || x.fuente === filtro); if (!f.length) { cont.append(el("div", "estado-vacio", "Sin eventos para mostrar.")); return; }
    f.slice().reverse().forEach((x) => { const r = el("div", "f"); r.append(el("span", "t", mmss(x.t_s)), el("span", "fuente " + x.fuente, FUENTES[x.fuente] || x.fuente), el("span", "", `${x.quien && x.quien !== "SYSTEM" ? x.quien + ": " : ""}${x.texto}`)); cont.append(r); });
  }
  async function pintarResumen(e) {
    const r = e.resultado; if (!r) { S.resumenDe = null; return; } const clave = e.id + r.resultado; if (S.resumenDe === clave) return; S.resumenDe = clave;
    let d; try { d = await api("GET", "/api/nova/resumen"); } catch (_) { S.resumenDe = null; return; } const box = $("#v-resumen"); box.textContent = "";
    const rej = el("div", "rej"); const bloque = (t, items, vacio) => { const b = el("div", "bloque"); b.append(el("h4", "", t)); if (!items.length) b.append(el("span", "vacio-eq", vacio || "Ninguno")); else { const u = el("ul"); items.forEach((x) => u.append(el("li", "", x))); b.append(u); } rej.append(b); };
    bloque("Objetivos del Rojo", d.objetivos.RED.map((m) => `${m.titulo}: ${m.estado.toLowerCase().replace(/_/g, " ")}`)); bloque("Objetivos del Azul", d.objetivos.BLUE.map((m) => `${m.titulo}: ${m.estado.toLowerCase().replace(/_/g, " ")}`));
    bloque("Operaciones", [`Rojo: ${d.operaciones.exitosas.RED} exitosas, ${d.operaciones.fallidas.RED} fallidas`, `Azul: ${d.operaciones.exitosas.BLUE} exitosas, ${d.operaciones.fallidas.BLUE} fallidas`]);
    bloque("Credenciales comprometidas", d.credenciales_comprometidas, "Ninguna"); bloque("Recursos protegidos", d.recursos_protegidos.map((t) => t.replace(/_/g, " ")), "Ninguno: se extrajo todo"); bloque("Errores defensivos", d.errores_defensivos, "Sin errores registrados"); bloque("Decisiones correctas", d.decisiones_correctas, "Ninguna registrada");
    box.append(rej); const bar = el("div", "acciones-form"); const lista = el("div", "linea"); [["", "Todo"], ["admin", "Administrador"], ["jugador", "Jugadores"], ["npc", "Empleados NPC"], ["ia", "Modelos de IA"], ["motor", "Motor"]].forEach(([k, t]) => { const b = el("button", "boton", t); b.addEventListener("click", () => listaTiempo(lista, d.linea_tiempo, k)); bar.append(b); });
    box.append(el("div", "sub-titulo", "Línea de tiempo: quién hizo qué y cuándo" + (d.practica ? " (partida de práctica)" : "")), bar, lista); listaTiempo(lista, d.linea_tiempo, "");
  }
  async function pintarEspectador(e) {
    const on = S.rol === "SPECTATOR"; visible("#p-espectador", on); if (!on || Date.now() - (S.espT || 0) < 4000) return; S.espT = Date.now();
    try { const d = await api("GET", "/api/nova/resumen"); listaTiempo($("#espectador-tiempo"), d.linea_tiempo.filter((x) => ["extraction.completed", "alert.created", "incident.created", "win.condition_met", "match.finished", "match.started", "credential.validated_by_engine", "approval.approved", "approval.rejected", "risk_action.completed"].includes(x.tipo)), ""); } catch (_) { /* sin datos */ }
  }
  function ajustarColumnas() {
    for (const id of ["#col-izq", "#col-centro", "#col-der"]) { const c = $(id); c.hidden = ![...c.children].some((x) => !x.hidden); }
    const t = $("#tablero"); t.classList.toggle("sin-izq", $("#col-izq").hidden); t.classList.toggle("sin-der", $("#col-der").hidden);
  }

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
