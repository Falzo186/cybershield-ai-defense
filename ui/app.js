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
    informe: null,        // informe agregado de la última partida (exportable)
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

  // Descarga un objeto como archivo .json desde el navegador (Blob + enlace), sin backend.
  function descargarJSON(prefijo, datos) {
    const blob = new Blob([JSON.stringify(datos, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = prefijo + new Date().toISOString().replace(/[:.]/g, "-") + ".json";
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportarHistorial() {
    if (!estado.rondas.length) { R.toast("Aún no hay rondas que exportar."); return; }
    descargarJSON("historial-", estado.rondas);
  }

  // Informe agregado de la última partida (llega en partida_fin.informe).
  function exportarInforme() {
    if (!estado.informe) { R.toast("El informe estará disponible al terminar una partida."); return; }
    descargarJSON("informe_sesion_", estado.informe);
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

  // Durante una partida en curso la práctica (simulación, manual, batalla «mejor de N») queda en pausa: el servidor
  // la rechaza con 409 y aquí el botón lo explica. La batalla de la partida está en su propia ventana.
  function aplicarControles() {
    const enPartida = !!(estado.partida && estado.partida.fase === "en_curso");
    const sinOllama = usaOllama() && !ollamaListo();
    R.setCorriendo(estado.corriendo, sinOllama || enPartida,
      enPartida ? "Práctica en pausa durante la partida: usa «Batalla de la partida»" : "Inicie Ollama");
    $("marcador").hidden = enPartida; // el marcador «BATALLA IA vs IA» es de la práctica: en la partida confundía
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
    R.setOllamaComprobando(rol);
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

  // ---------- buzón de correos de entrenamiento ----------
  async function abrirBuzon() {
    R.mostrarBuzon(true, estado.rol);
    if (estado.rol === "azul") { cargarBuzon(); cargarMisiones(); cargarIncidentes(); return; }
    try {
      const [p, u] = await Promise.all([API.plantillasCorreo(), API.usuarios()]);
      R.setPlantillas(p.plantillas || []);
      R.setDestinatarios(u.usuarios || []);
    } catch (e) { R.toast(e.message); }
    cargarEnviadosRojo();
  }

  async function cargarEnviadosRojo() {
    try { R.setEnviadosRojo((await API.enviadosRojo()).enviados || []); } catch (e) { /* p. ej. partida sin iniciar */ }
  }

  async function enviarCorreo() {
    const plantilla = R.valorSelect("sel-plantilla");
    if (!plantilla) { R.toast("Elige una plantilla."); return; }
    $("btn-correo").disabled = true;
    try {
      const c = await API.enviarCorreo(plantilla, R.valorSelect("sel-destinatario"));
      R.toast("✓ Correo enviado a " + c.para_usuario + ": «" + c.asunto + "»");
    } catch (e) { R.toast(e.message); }
    $("btn-correo").disabled = false;
    cargarEnviadosRojo();
  }

  // Tras refrescar, el correo abierto sigue abierto (con sus botones al día).
  async function cargarBuzon() {
    try {
      const b = await API.buzon();
      const correos = b.correos || [];
      estado.correos = correos;
      estado.enviados = b.enviados || [];
      const abierto = correos.find((c) => c.id === estado.correoAbierto);
      pintarBuzon(b.usuario, abierto && abierto.id);
      if (abierto) abrirCorreo(abierto, false); else { estado.correoAbierto = null; R.mostrarCorreo(null); }
    } catch (e) { if (R.buzonAbierto()) R.toast(e.message); }
  }

  function pintarBuzon(usuario, seleccionado) {
    estado.usuarioBuzon = usuario || estado.usuarioBuzon;
    R.setBuzon(estado.usuarioBuzon, estado.correos || [], abrirCorreo, seleccionado, estado.carpeta, estado.enviados,
      (carpeta) => { estado.carpeta = carpeta; pintarBuzon(null, estado.correoAbierto); });
  }

  // leer=true: al abrirlo por primera vez ESTE participante, se marca como leído (evento correo_abierto, riesgo 0).
  function abrirCorreo(c, leer = true) {
    estado.correoAbierto = c.id;
    R.mostrarCorreo(c, {
      reportar: () => accionCorreo("reportar", c.id), contener: () => accionCorreo("contener", c.id),
      incidente: () => incidenteDesdeCorreo(c),
      abrirPdf: () => accionPdf("pdf_abierto", c.id), reportarPdf: () => accionPdf("pdf_reportado", c.id),
      aislar: () => accionSimple(() => API.aislarAdjunto(c.id), "🧪 Adjunto aislado"),
      archivar: (si) => accionSimple(() => API.archivarCorreo(c.id, si), si ? "🗄 Correo archivado" : "📥 De vuelta en la entrada"),
      responder: (texto) => accionSimple(() => API.responderCorreo(c.id, texto), "↩ Respuesta registrada (no sale del laboratorio)"),
      verificar: async () => {
        try {
          const v = await API.verificarRemitente(c.id);
          R.mostrarResultadoCorreo(v.oficial ? "✓ Remitente de la organización" : v.parecido ? "⚠ El remitente IMITA al dominio oficial"
            : "⚠ Remitente externo", [v.detalle].concat(v.indicadores.length ? ["Indicadores: " + v.indicadores.join(" · ")] : []), v.oficial);
        } catch (e) { R.toast(e.message); }
      },
      inspeccionar: async () => {
        try {
          const i = await API.inspeccionarEnlace(c.id);
          R.mostrarResultadoCorreo(i.coincide ? "✓ El enlace va a donde dice" : "⚠ El enlace NO va a donde dice",
            ["Texto visible: " + i.texto_mostrado, "Destino real: " + i.destino_real, i.explicacion], i.coincide);
        } catch (e) { R.toast(e.message); }
      },
    });
    const yo = estado.participante && estado.participante.nombre;
    const yaLeido = (c.leido_por || "").split(", ").includes(yo);
    if (leer && !yaLeido && API.tieneToken()) {
      API.leerCorreo(c.id).then(() => {
        c.leido = true;
        c.leido_por = c.leido_por ? c.leido_por + ", " + yo : yo;
        R.marcarLeido(c.id);
      }).catch(() => { /* p. ej. partida no iniciada: el servidor lo rechaza y se ve al actuar */ });
    }
  }

  // Acción con aviso + regla explicada y recarga del buzón (el estado lo calcula el servidor).
  async function accionSimple(llamada, aviso) {
    try {
      const r = await llamada();
      const g = r.regla || {};  // una consecuencia negativa explica qué control falló
      R.toast((g.riesgo > 0 ? "⚠ " : "✓ ") + aviso + textoRegla(g) + (g.riesgo > 0 && g.explicacion ? " — " + g.explicacion : ""));
    } catch (e) { R.toast(e.message); }
    cargarBuzon();
    cargarMisiones();
  }

  // Texto del aviso tras una regla: el cambio de la regla Y el riesgo resultante de la partida (que no baja de 0,
  // así que "−10" con la partida ya en 0 no se lee como una bajada que no ocurrió) + misiones completadas.
  function textoRegla(g) {
    const riesgo = g.riesgo ? " · regla " + (g.riesgo > 0 ? "+" : "") + g.riesgo +
      (typeof g.riesgo_acumulado === "number" ? " → riesgo de la partida " + Math.round(g.riesgo_acumulado) + "/100" : "") : "";
    const misiones = (g.misiones_completadas || []).map((m) => "«" + m.titulo + "» +" + m.puntos + " pts" +
      (m.a_tiempo === false ? " (fuera de plazo)" : ""));
    const bloqueadas = (g.misiones_bloqueadas || []).map((m) => "«" + m.titulo + "» (requiere " + m.requiere.join(", ") + ")");
    return riesgo + (misiones.length ? " · misión completada: " + misiones.join(", ") : "") +
      (bloqueadas.length ? " · misión bloqueada: " + bloqueadas.join(", ") : "");
  }

  // Reportar / contener: el servidor aplica la regla fija y avisa qué cambió (riesgo y misiones completadas).
  async function accionCorreo(tipo, id) {
    try {
      const r = await (tipo === "reportar" ? API.reportarCorreo(id) : API.contenerCorreo(id));
      R.toast((tipo === "reportar" ? "✓ Correo reportado" : "✓ Enlace contenido") + textoRegla(r.regla || {}));
    } catch (e) { R.toast(e.message); }
    cargarBuzon();
    cargarMisiones();
  }

  // Previsualizar/reportar el PDF adjunto: el evento (auditoría + regla) y, si es previsualizar, el VISOR SEGURO con el
  // texto del propio archivo y su análisis. Ya no se descarga nada al equipo del participante.
  async function accionPdf(tipo, id) {
    try {
      const r = await API.eventoPdf(tipo, id);
      R.toast((tipo === "pdf_abierto" ? "📎 PDF previsualizado (evento registrado)" : "✓ PDF reportado") + textoRegla(r.regla || {}));
      if (r.vista) R.mostrarVisor(r.vista);
    } catch (e) { R.toast(e.message); }
    cargarBuzon();
    cargarMisiones();
  }

  async function cargarMisiones() {
    try {
      R.setMisiones(await API.misiones(), { completar: completarMision, asumir: asumirMision,
        yo: estado.participante && estado.participante.nombre });
    } catch (e) { if (R.buzonAbierto()) R.toast(e.message); }
  }

  async function asumirMision(id) {
    try { await API.asumirMision(id); R.toast("✓ Ahora eres responsable de esa misión"); } catch (e) { R.toast(e.message); }
    cargarMisiones();
  }

  // ---------- incidentes y credencial ficticia (Fase E) ----------
  async function cargarIncidentes() {
    try {
      const [i, c] = await Promise.all([API.incidentes(), API.credenciales()]);
      R.setIncidentes(i.incidentes || [], {
        investigar: (id) => accionIncidente(() => API.estadoIncidente(id, "en_investigacion"), "🔎 Incidente en investigación"),
        resolver: (id, texto) => accionIncidente(() => API.estadoIncidente(id, "resuelto", texto), "✓ Incidente resuelto"),
      });
      R.setCredencial(c, () => accionIncidente(() => API.revocarCredencial(), "✓ Credencial revocada"));
      R.setCorreosIncidente(estado.correos || []);
    } catch (e) { /* p. ej. sin sesión azul */ }
  }

  async function accionIncidente(llamada, aviso) {
    try {
      const r = await llamada();
      R.toast(aviso + textoRegla(r.regla || {}));
    } catch (e) { R.toast(e.message); }
    cargarIncidentes();
    cargarMisiones();
  }

  async function abrirIncidente() {
    const titulo = $("inc-titulo").value.trim();
    const correo = $("inc-correo").value;
    try {
      const r = await API.abrirIncidente(titulo, $("inc-severidad").value, correo ? Number(correo) : null);
      $("inc-titulo").value = "";
      R.toast("🚨 Incidente #" + r.incidente.id + " abierto" + textoRegla(r.regla || {}));
    } catch (e) { R.toast(e.message); }
    cargarIncidentes();
    cargarMisiones();
  }

  // Desde un correo: pestaña de incidentes con ese correo ya elegido y un título propuesto.
  function incidenteDesdeCorreo(c) {
    R.setVistaAzul("incidentes");
    cargarIncidentes().then(() => {
      R.setCorreosIncidente(estado.correos || [], c.id);
      if (!$("inc-titulo").value) $("inc-titulo").value = ("Correo sospechoso: " + c.asunto).slice(0, 80);
      $("inc-titulo").focus();
    });
  }

  async function completarMision(id) {
    try { await API.completarMision(id); R.toast("✓ Misión completada"); } catch (e) { R.toast(e.message); }
    cargarMisiones();
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
      R.setVeredicto(d.decision, d.resultado, d.nota);
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
    partida_fin(d) {
      estado.informe = d.informe || null;
      $("btn-informe").disabled = !estado.informe;
      $("partida-informe").hidden = !estado.informe;
      R.mostrarPartida(d, !!estado.ultimaFin);
    },
    partida_estado(d) { aplicarPartida(d); },
    // Marcador de la partida Rojo/Azul: solo lo muestran el árbitro (general) y los espectadores.
    marcador_partida(d) {
      refrescarInforme();
      refrescarApps();
      if (estado.rol !== "general" && estado.rol !== "espectador") return;
      R.setMarcadorPartida(d);
      $("btn-finalizar").disabled = !!d.final; // ya no hay nada que cerrar
      if (d.final && !estado.finalMostrado) { estado.finalMostrado = true; R.mostrarResultado(d.final, d); }
    },
    partida_finalizada(d) {
      if ((estado.rol === "general" || estado.rol === "espectador") && !estado.finalMostrado) {
        estado.finalMostrado = true;
        R.mostrarResultado(d, d.marcador);
      }
    },
    auditoria(d) {
      R.addAuditoria(d);
      const n = (NOTIF_AUDITORIA[d.accion] || {})[estado.rol];
      if (n) notificar(n[0] + (d.recurso ? " · " + d.recurso : ""), n[1]);
      // Correo nuevo o clic en un enlace: el equipo azul refresca su buzón (contador y botón «Contener» al día);
      // Rojo, el seguimiento de su campaña (clics y adjuntos abiertos).
      if ((d.accion === "CORREO_ENVIADO" || d.accion === "CLIC_ENLACE") && estado.rol === "azul" && API.tieneToken()) {
        cargarBuzon();
      }
      if (["CLIC_ENLACE", "PDF_ABIERTO", "CORREO_ENVIADO", "CREDENCIAL_COMPROMETIDA"].includes(d.accion) &&
          estado.rol === "rojo" && API.tieneToken()) {
        cargarEnviadosRojo();
      }
    },
    // Fase E: cambios que afectan a todo el equipo azul (otro participante asumió, abrió o revocó algo).
    misiones_cambio() { if (estado.rol === "azul" && API.tieneToken()) cargarMisiones(); },
    incidentes_cambio() { if (estado.rol === "azul" && API.tieneToken()) { cargarIncidentes(); cargarMisiones(); } },
    credenciales_cambio(d) {
      if (estado.rol !== "azul" || !API.tieneToken()) return;
      if (d.estado === "comprometida") {
        R.toast("⚠ La credencial de " + d.usuario + " está COMPROMETIDA: revócala en Incidentes");
        notificar("⚠ Credencial de " + d.usuario + " COMPROMETIDA: revócala", "alerta");
      }
      cargarIncidentes();
    },
    // Fase F: batalla de la partida
    ia_estado(d) { pintarBatalla(d); },
    ia_ataque(d) {
      R.setIaEnCurso(d.en_curso);
      const a = d.terminado;
      if (a) {
        const pts = [a.puntos_rojo && "Rojo +" + a.puntos_rojo, a.puntos_azul && "Azul +" + a.puntos_azul].filter(Boolean).join(" · ");
        R.toast("⚔ Ataque IA #" + a.n + ": " + a.titulo + (pts ? " (" + pts + ")" : "") + " — " + a.explicacion);
        notificar("⚔ Ataque IA #" + a.n + ": " + a.titulo + (pts ? " (" + pts + ")" : ""),
          a.resultado === "datos_expuestos" || a.resultado === "fallo_seguro" ? "alerta" : "info");
      }
    },
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
      // /api/metricas exige token: el espectador no lo pide (antes producía un 403 en consola en cada conexión)
      if (API.tieneToken()) aplicarMetricas(await API.metricas());
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
      const escenario = R.valorSelect("sel-escenario") || undefined; // vacío = atacante libre
      estado.enviandoReto = true;
      try {
        // No arranca de inmediato: el servidor emite el reto y espera la aceptación del otro equipo (30 s).
        const r = await API.iniciarBatallaReal({
          rondas: n, intensidad, demo, de_rol: lado,
          dificultad: demo ? undefined : dificultad, escenario,
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
  const ROLES = ["rojo", "azul", "general", "espectador"];
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

  // Sesión del participante: se guarda en este navegador (localStorage) para reconectar al recargar o reabrir la
  // pestaña; si el servidor ya no la reconoce (reinicio), se vuelve a pedir el nombre. -> true si hay sesión.
  // El espectador no necesita sesión: solo observa.
  async function prepararToken(rol) {
    if (!rol || rol === "espectador") return false;
    const clave = "cs_sesion_" + rol;
    const token = LS.get(clave);
    if (token) {
      API.setToken(token);
      try {
        const s = await API.miSesion();
        aplicarSesion(s.participante, s.partida);
        return true;
      } catch (e) {
        API.setToken(null);
        if (e.status !== 403) { R.toast("No se pudo comprobar la sesión: " + e.message); return false; }
        LS.set(clave, ""); // el servidor no la reconoce: hay que volver a unirse
      }
    }
    return new Promise((resolve) => {
      R.mostrarUnirse(rol, LS.get("cs_nombre"), async (nombre, codigo) => {
        try {
          const r = await API.unirse(nombre, rol, codigo);
          LS.set(clave, r.token);
          LS.set("cs_nombre", r.participante.nombre);
          API.setToken(r.token);
          aplicarSesion(r.participante, r.partida);
          R.cerrarUnirse();
          resolve(true);
        } catch (e) { R.errorUnirse(e.message); }
      });
    });
  }

  function aplicarSesion(participante, partida) {
    estado.participante = participante;
    R.setParticipante(participante, estado.rol);
    if (partida) aplicarPartida(partida);
  }

  // Estado de la partida (SSE al conectar, cada cambio y cada 15 s). Una partida nueva (otro id) limpia la vista.
  function aplicarPartida(p) {
    const nueva = estado.partida && estado.partida.id !== p.id;
    const cambioFase = !estado.partida || estado.partida.fase !== p.fase;
    estado.partida = p;
    R.setPartida(p);
    if (cambioFase) {
      aplicarControles();
      refrescarInforme();
      refrescarApps();
      if (nueva || notif.clave !== claveNotif()) cargarNotif(); // cada partida tiene sus notificaciones
      if (p.fase === "en_curso") notificar("▶ La partida ha empezado", "info");
      if (p.fase === "finalizada") notificar("🏁 La partida ha terminado: mira Resultados", "info");
    }
    if (estado.batalla && estado.batalla.fase_partida !== p.fase && !nueva) pintarBatalla({ ...estado.batalla, fase_partida: p.fase });
    if (nueva) {
      estado.finalMostrado = false;
      R.cerrarResultado();
      if (estado.rol === "azul" && API.tieneToken()) { cargarBuzon(); cargarMisiones(); }
    }
  }

  // ---------- batalla de la partida (Fase F) ----------
  function pintarBatalla(e) {
    estado.batalla = e;
    R.setBatallaPartida(e, { rol: estado.rol, conToken: API.tieneToken() });
  }

  async function lanzarAtaqueIA() {
    const modelo = R.valorSelect("sel-atq");
    if (!modelo) { R.toast("Elige primero el modelo del atacante en la ventana IA Atacante."); return; }
    try {
      await API.lanzarAtaqueIA(modelo, hostDe("atq"), R.valorSelect("bp-tecnica"), Number(R.valorSelect("bp-intensidad")));
    } catch (e) { R.toast(e.message); } // el progreso y el resultado llegan por SSE
  }

  async function usarDefensorIA() {
    const modelo = R.valorSelect("sel-def");
    if (!modelo) { R.toast("Elige primero el modelo del defensor en la ventana IA Defensora."); return; }
    try {
      await API.configurarDefensorIA(modelo, hostDe("def"));
      R.toast("🛡 Defensor IA activo y verificado: " + modelo);
    } catch (e) { R.toast(e.message); }
  }

  // ---------- aplicaciones por permiso (Fase B) ----------
  // Cada ventana se carga al hacerse visible y se refresca (agrupado) con los cambios de la partida mientras se ve.
  const APPS_CARGA = {
    archivos: async () => {
      try {
        R.setArchivos(await API.archivos(), {
          ver: (id) => accionPdf("pdf_abierto", id).then(cargarAppsVisibles),
          reportar: (id) => accionPdf("pdf_reportado", id).then(cargarAppsVisibles),
          aislar: (id) => accionSimple(() => API.aislarAdjunto(id), "🧪 Adjunto aislado").then(cargarAppsVisibles),
        });
      } catch (e) { R.setArchivos({ bloqueado: e.message }); }
    },
    seguridad: async () => {
      try {
        R.setSeguridad(await API.seguridad(), { revocar: async () => {
          try {
            const r = await API.revocarCredencial();
            R.toast("🔒 Credencial revocada" + textoRegla(r.regla || {}));
          } catch (e) { R.toast(e.message); }
          cargarAppsVisibles();
        } });
      } catch (e) { R.setSeguridad({ bloqueado: e.message }); }
    },
    "incidentes-gen": async () => {
      try { R.setIncidentesGen(await API.incidentes()); } catch (e) { R.setIncidentesGen({ bloqueado: e.message }); }
    },
    recursos: async () => { try { R.setRecursos(await API.recursos()); } catch (e) { R.toast(e.message); } },
    ayuda: async () => { try { R.setAyuda(await API.ayuda(estado.rol || "espectador")); } catch (e) { R.toast(e.message); } },
  };
  const appVisible = (clase) => !!(document.querySelector("section.panel." + clase) || {}).offsetParent;
  let temporizadorApps = null;
  function cargarAppsVisibles() {
    Object.entries(APPS_CARGA).forEach(([clase, fn]) => { if (appVisible(clase)) fn(); });
  }
  function refrescarApps() {
    clearTimeout(temporizadorApps);
    temporizadorApps = setTimeout(cargarAppsVisibles, 800);
  }

  // ---------- notificaciones ----------
  // Lo que pasa en la partida y le importa a ESTA vista (sin repetir los avisos de las acciones propias). Se guardan en
  // este navegador (las 50 últimas, por vista y partida): son una comodidad de la vista, no un registro.
  const notif = { lista: [], clave: null };
  function claveNotif() { return "cs_notif_" + (estado.rol || "x") + "_" + ((estado.partida && estado.partida.id) || ""); }
  function cargarNotif() {
    notif.clave = claveNotif();
    try { notif.lista = JSON.parse(LS.get(notif.clave) || "[]") || []; } catch (_) { notif.lista = []; }
    pintarNotif();
  }
  function pintarNotif() {
    R.setNotificaciones(notif.lista, notif.lista.filter((x) => !x.leida).length);
    LS.set(notif.clave || claveNotif(), JSON.stringify(notif.lista));
  }
  function notificar(texto, nivel) {
    const d = new Date();
    const hora = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
    notif.lista = [{ texto, nivel: nivel || "info", hora, leida: R.notificacionesAbiertas() }, ...notif.lista].slice(0, 50);
    pintarNotif();
  }
  // acción de auditoría (SSE) -> {equipo: [texto, nivel]}
  const NOTIF_AUDITORIA = {
    CORREO_ENVIADO: { azul: ["📬 Ha llegado un correo nuevo al buzón", "info"] },
    CLIC_ENLACE: { rojo: ["🔗 Alguien pulsó el enlace de uno de tus correos", "info"], azul: ["⚠ Un empleado pulsó el enlace de un correo: contenlo", "alerta"],
      general: ["🔗 Clic en un enlace de phishing", "alerta"] },
    PDF_ABIERTO: { rojo: ["📎 Abrieron uno de tus adjuntos", "info"] },
    CREDENCIAL_COMPROMETIDA: { rojo: ["🔑 Has obtenido una credencial", "info"], general: ["🔑 Credencial comprometida", "alerta"] },
    CREDENCIAL_REVOCADA: { general: ["🔒 Azul revocó la credencial", "info"] },
    MISION_COMPLETADA: { azul: ["🎯 Misión completada", "info"] },
    INCIDENTE_ABIERTO: { general: ["🚨 Azul abrió un incidente", "info"] },
    INCIDENTE_RESUELTO: { general: ["✓ Azul resolvió un incidente", "info"] },
  };

  // ---------- resultados y cronología (Fase G) ----------
  const informe = { tab: "resultados", partida: null, temporizador: null, carga: 0 };
  const informeVisible = () => !!$("inf-equipos").offsetParent || !!$("inf-lista").offsetParent;

  // Varias cargas pueden solaparse (icono, visibilidad, SSE): solo se pinta la respuesta de la ÚLTIMA.
  async function cargarInforme() {
    const n = ++informe.carga;
    const vigente = () => n === informe.carga;
    try {
      const p = await API.partidas();
      if (!vigente()) return;
      if (!informe.partida || ![p.actual.id, ...p.finalizadas.map((x) => x.partida)].includes(informe.partida)) informe.partida = p.actual.id;
      R.setPartidasInforme(p, informe.partida);
    } catch (e) { R.toast(e.message); return; }
    if (informe.tab === "resultados") {
      try {
        const d = await API.resultados(informe.partida);
        if (vigente()) R.setResultados(d);
      } catch (e) { if (vigente()) R.setResultados({ bloqueado: e.message }); }
    } else {
      try {
        const d = await API.cronologia({ partida: informe.partida, ...R.filtrosCronologia() });
        if (!vigente()) return;
        R.initFiltrosCronologia(d.categorias, cargarInforme);
        R.setCronologia(d);
      } catch (e) { R.toast(e.message); }
    }
  }
  // Con la ventana a la vista, se refresca (agrupado) cuando cambia algo en la partida.
  function refrescarInforme() {
    if (!informeVisible()) return;
    clearTimeout(informe.temporizador);
    informe.temporizador = setTimeout(cargarInforme, 800);
  }
  async function exportarInformeServidor() {
    try {
      const [res, cro] = await Promise.all([API.resultados(informe.partida).catch((e) => ({ bloqueado: e.message })),
        API.cronologia({ partida: informe.partida })]);
      descargarJSON("informe_" + (informe.partida || "partida") + "_", { exportado: new Date().toISOString(), resultados: res, cronologia: cro });
    } catch (e) { R.toast(e.message); }
  }
  function abrirInforme(tab) {
    informe.tab = tab || "resultados";
    R.setTabInforme(informe.tab);
    const icono = document.querySelector('[data-icono="resultados"]');
    if (icono) icono.click(); else $("t-inf").scrollIntoView();
    cargarInforme();
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
    $("partida-informe").addEventListener("click", exportarInforme);
    $("btn-informe").addEventListener("click", exportarInforme);
    $("partida-metricas").addEventListener("click", () => {
      if (estado.ultimaFin) { R.cerrarPartida(); R.mostrarModal(estado.ultimaFin.m, estado.ultimaFin.e); }
    });
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && R.partidaAbierta()) R.cerrarPartida(); });
    $("btn-buzon").addEventListener("click", abrirBuzon);
    $("btn-iniciar-partida").addEventListener("click", async () => {
      const min = Number(R.valorSelect("sel-duracion"));
      if (!window.confirm("¿Iniciar la partida de " + min + " minutos? Desde ahora cuentan correos, clics, reportes y misiones.")) return;
      try { await API.iniciarPartida(min); } catch (e) { R.toast(e.message); } // el estado llega por SSE
    });
    $("btn-nueva-partida").addEventListener("click", async () => {
      if (!window.confirm("¿Preparar una partida nueva? Correos, misiones y marcador empiezan de cero (los participantes se conservan).")) return;
      try { await API.nuevaPartida(); } catch (e) { R.toast(e.message); }
    });
    $("btn-finalizar").addEventListener("click", async () => {
      if (!window.confirm("¿Finalizar la partida? Se congelan los puntajes y Rojo/Azul ya no podrán actuar.")) return;
      try { await API.finalizarPartida(); } catch (e) { R.toast(e.message); } // el resultado llega por SSE
    });
    $("final-cerrar").addEventListener("click", R.cerrarResultado);
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && R.resultadoAbierto()) R.cerrarResultado(); });
    $("buzon-cerrar").addEventListener("click", () => R.mostrarBuzon(false));
    $("buzon-modal").addEventListener("click", (ev) => { if (ev.target === $("buzon-modal")) R.mostrarBuzon(false); });
    $("btn-buzon-refrescar").addEventListener("click", cargarBuzon);
    $("btn-enviados-refrescar").addEventListener("click", cargarEnviadosRojo);
    $("visor-cerrar").addEventListener("click", R.cerrarVisor);
    $("visor-modal").addEventListener("click", (ev) => { if (ev.target === $("visor-modal")) R.cerrarVisor(); });
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && R.visorAbierto()) R.cerrarVisor(); });
    $("btn-misiones-refrescar").addEventListener("click", cargarMisiones);
    document.querySelectorAll("[data-azul]").forEach((t) => t.addEventListener("click", () => {
      R.setVistaAzul(t.dataset.azul);
      if (t.dataset.azul === "misiones") cargarMisiones();
      if (t.dataset.azul === "incidentes") cargarIncidentes();
    }));
    $("incidente-form").addEventListener("submit", (ev) => { ev.preventDefault(); abrirIncidente(); });
    $("correo-form").addEventListener("submit", (ev) => { ev.preventDefault(); enviarCorreo(); });
    $("bp-rojo").addEventListener("submit", (ev) => { ev.preventDefault(); lanzarAtaqueIA(); });
    $("bp-defender").addEventListener("click", usarDefensorIA);
    document.querySelectorAll("[data-inf]").forEach((t) => t.addEventListener("click", () => {
      informe.tab = t.dataset.inf;
      R.setTabInforme(informe.tab);
      cargarInforme();
    }));
    $("inf-sel-partida").addEventListener("change", (ev) => { informe.partida = ev.target.value; cargarInforme(); });
    $("inf-actualizar").addEventListener("click", cargarInforme);
    $("inf-exportar").addEventListener("click", exportarInformeServidor);
    ["inf-equipo", "inf-nivel"].forEach((id) => $(id).addEventListener("change", cargarInforme));
    $("inf-q").addEventListener("input", () => { clearTimeout(informe.temporizador); informe.temporizador = setTimeout(cargarInforme, 400); });
    $("inf-filtros").addEventListener("submit", (ev) => { ev.preventDefault(); cargarInforme(); });
    $("final-desglose").addEventListener("click", () => { R.cerrarResultado(); abrirInforme("resultados"); });
    if ("IntersectionObserver" in window) {
      Object.entries(APPS_CARGA).forEach(([clase, fn]) => {
        const s = document.querySelector("section.panel." + clase);
        if (s) new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) fn(); }).observe(s);
      });
    }
    $("btn-notif").addEventListener("click", () => {
      R.mostrarNotificaciones(!R.notificacionesAbiertas());
    });
    $("notif-leidas").addEventListener("click", () => { notif.lista.forEach((x) => { x.leida = true; }); pintarNotif(); });
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && R.notificacionesAbiertas()) R.mostrarNotificaciones(false); });
    document.addEventListener("click", (ev) => {
      if (R.notificacionesAbiertas() && !ev.target.closest("#notif-panel, #btn-notif")) R.mostrarNotificaciones(false);
    });
    cargarNotif();
    // Se carga al hacerse visible (abrir la ventana desde su icono, restaurarla o, en la vista clásica, al llegar a ella).
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) cargarInforme(); })
        .observe(document.querySelector("section.panel.informe"));
    }
    // Esc cierra el buzón solo cuando es un modal; como ventana del escritorio se cierra con su ✕.
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && R.buzonEsModal() && R.buzonAbierto()) R.mostrarBuzon(false);
    });

    R.initPipeline();
    R.initAuditoria();
    R.limpiarDefensor();
    R.crearFiltros(AGENTES, (ag, on) => R.setFiltro(ag, on), FILTROS_POR_ROL[estado.rol]);
    R.setModo(estado.modo);
    R.setAtqEstado("EN ESPERA", false);
    R.setDefEstado("PROTEGIENDO BD", true);
    // Hasta que llegue el primer estado real (SSE al conectar o «Probar conexión»): «Comprobando…», no «desconectado».
    R.setOllamaComprobando("atq");
    R.setOllamaComprobando("def");
    actualizarOrigen();

    document.querySelectorAll(".tab[data-modo]").forEach((t) => t.addEventListener("click", () => cambiarModo(t.dataset.modo)));
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

    // Primero el token (las rutas /api, salvo eventos y estado, lo exigen); después, datos y SSE.
    R.setPermisos(false, estado.rol); // acciones ocultas hasta tener token
    prepararToken(estado.rol).then((conToken) => {
      R.setPermisos(conToken, estado.rol);
      if (estado.batalla) pintarBatalla(estado.batalla); // ya con token: muestra los controles del equipo
      if (conToken) cargarUsuarios();
      if (conToken && estado.rol === "azul") cargarBuzon(); // contador inicial del botón ✉ BUZÓN (n)
      API.conectar(handlers, (est) => {
        const antes = estado.conexion;
        estado.conexion = est;
        R.setConexion(est);
        if (est === "conectado" && antes !== "conectado") sincronizar();
      });
    });
  }

  init();
})();
