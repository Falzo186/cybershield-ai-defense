"use strict";
// Escritorio "CyberShield OS": iconos + ventanas arrastrables que ENVUELVEN los paneles existentes.
// No duplica ni reescribe lógica: mueve las mismas <section> (render.js las busca por id, así que siguen
// funcionando) a marcos de ventana. Sin escritorio (?vista=clasica, preferencia guardada o pantalla estrecha)
// la página queda exactamente como antes.
(() => {
  const ANCHO_MINIMO = 760; // por debajo, vista clásica apilada (el escritorio no tiene sentido en un teléfono)
  const MARGEN = 8;
  const Z_BASE = 1;         // las ventanas quedan por debajo de los modales (z-index 10+)

  const LS = {
    get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* almacenamiento bloqueado */ } },
  };

  const rol = document.body.dataset.rol || "";
  const params = new URLSearchParams(location.search);
  if (params.get("vista") === "clasica") LS.set("cs_vista", "clasica");
  if (params.get("vista") === "escritorio") LS.set("cs_vista", "escritorio");
  const quiereEscritorio = LS.get("cs_vista") !== "clasica";

  // Enlace de la cabecera para cambiar de vista (siempre visible, también en la clásica).
  const lnk = document.createElement("a");
  lnk.className = "lnk";
  lnk.id = "lnk-vista";
  lnk.href = "#";
  lnk.textContent = quiereEscritorio ? "☰ Vista clásica" : "🖥 Vista escritorio";
  lnk.addEventListener("click", (ev) => {
    ev.preventDefault();
    LS.set("cs_vista", quiereEscritorio ? "clasica" : "escritorio");
    const p = new URLSearchParams(location.search);
    p.delete("vista");
    location.search = p.toString();
  });
  const cambiar = document.getElementById("lnk-equipo");
  if (cambiar) cambiar.after(lnk);

  if (!quiereEscritorio) return;
  // Si la página carga estrecha (teléfono, o una pestaña oculta con ancho 0), el escritorio se activa la primera vez
  // que la ventana llegue al ancho mínimo; nunca se desactiva sin recargar.
  if (window.innerWidth >= ANCHO_MINIMO) iniciar();
  else {
    const esperar = () => {
      if (window.innerWidth < ANCHO_MINIMO) return;
      window.removeEventListener("resize", esperar);
      iniciar();
    };
    window.addEventListener("resize", esperar);
  }

  function iniciar() {

    // ---------- catálogo de ventanas (paneles existentes) y de accesos directos ----------
    // abierta: en qué vistas arranca abierta la ventana (el resto queda como icono).
    const VENTANAS = [
      { id: "atacante", titulo: "IA Atacante", icono: "🗡️", sel: "section.panel.atq", abierta: ["rojo", "general", "espectador", ""] },
      { id: "control", titulo: "Centro de control", icono: "🎛️", sel: "section.panel.ctr", abierta: ["rojo", "azul", "general", "espectador", ""] },
      { id: "defensor", titulo: "IA Defensora", icono: "🛡️", sel: "section.panel.def", abierta: ["azul", "general", "espectador", ""] },
      { id: "batalla", titulo: "Batalla de la partida", icono: "⚔️", sel: "section.panel.bpartida", abierta: ["rojo", "azul", "general", "espectador", ""] },
      { id: "auditoria", titulo: "Auditoría", icono: "📜", sel: "section.panel.aud", abierta: ["rojo", "azul", "general", "espectador", ""], minH: 100 },
      // Buzón: la MISMA tarjeta del modal (render.js delega abrir/cerrar en esta ventana con R.alojarBuzon).
      // Se abre desde el acceso «Correo/Buzón» (que carga los datos), nunca sola al recargar, y flota fuera del mosaico.
      { id: "buzon", titulo: rol === "azul" ? "Buzón" : "Correo", icono: "📬", sel: "#buzon-modal .buzon-card",
        abierta: [], roles: ["rojo", "azul"], sinIcono: true, efimera: true, flotante: true, tam: [680, 560] },
    ].filter((d) => !d.roles || d.roles.includes(rol));
    // Accesos directos: reutilizan los botones y modales que ya existen (mismo código, mismos permisos).
    const ACCESOS = [
      { id: "correo", titulo: rol === "azul" ? "Buzón" : "Correo", icono: "📬", roles: ["rojo", "azul"],
        ayuda: rol === "azul" ? "Abrir el buzón de correos de entrenamiento" : "Enviar un correo de entrenamiento al Equipo Azul",
        accion: () => pulsar("btn-buzon", "Tu vista aún no tiene token de equipo.") },
      { id: "misiones", titulo: "Misiones", icono: "🎯", roles: ["azul"],
        ayuda: "Ver el progreso de las misiones del Equipo Azul",
        accion: () => { if (pulsar("btn-buzon", "Tu vista aún no tiene token de equipo.")) clicEn('[data-azul="misiones"]'); } },
      { id: "finalizar", titulo: "Finalizar partida", icono: "🏁", roles: ["general"],
        ayuda: "Finalizar la partida: congela los puntajes y muestra el resultado",
        accion: () => pulsar("btn-finalizar", "Solo el árbitro puede finalizar, y solo con la partida en curso.") },
    ];

    function visible(n) { return !!n && getComputedStyle(n).display !== "none" && !n.disabled; }
    function pulsar(id, aviso) {
      const b = document.getElementById(id);
      if (visible(b)) { b.click(); return true; }
      if (typeof R !== "undefined") R.toast(aviso);
      return false;
    }
    function clicEn(sel) { const n = document.querySelector(sel); if (n) n.click(); }

    // ---------- estructura del escritorio ----------
    const app = document.querySelector(".app");
    const mid = document.querySelector("main.mid");
    document.body.classList.add("escritorio");

    const escritorio = document.createElement("div");
    escritorio.id = "escritorio";
    escritorio.className = "escritorio-area";
    escritorio.setAttribute("aria-label", "Escritorio CyberShield");
    const iconos = document.createElement("nav");
    iconos.className = "esc-iconos";
    iconos.setAttribute("aria-label", "Iconos del escritorio");
    const capa = document.createElement("div");
    capa.className = "esc-capa";
    escritorio.append(iconos, capa);

    const barra = document.createElement("div");
    barra.className = "esc-barra";
    barra.setAttribute("role", "toolbar");
    barra.setAttribute("aria-label", "Barra de tareas");
    const tareas = document.createElement("div");
    tareas.className = "esc-tareas";
    const organizar = document.createElement("button");
    organizar.type = "button";
    organizar.className = "esc-organizar";
    organizar.textContent = "▦ Organizar";
    organizar.title = "Vuelve a colocar las ventanas abiertas en mosaico";
    const reloj = document.createElement("span");
    reloj.className = "esc-reloj mono";
    barra.append(tareas, organizar, reloj);

    app.insertBefore(escritorio, mid);
    app.insertBefore(barra, mid.nextSibling);

    // ---------- estado guardado por vista ----------
    const CLAVE = "cs_escritorio_" + (rol || "sinrol");
    let guardado = {};
    try { guardado = JSON.parse(LS.get(CLAVE) || "{}") || {}; } catch (_) { guardado = {}; }
    const guardar = () => LS.set(CLAVE, JSON.stringify(Object.fromEntries(
      ventanas.map((v) => [v.def.id, { abierta: v.abierta, minimizada: v.minimizada, maximizada: v.maximizada,
        x: v.x, y: v.y, w: v.w, h: v.h }]))));

    // ---------- ventanas ----------
    const ventanas = [];
    let orden = []; // ids de abajo a arriba (z-order)
    let mosaicoAuto = false; // true mientras la disposición sea la del mosaico y el usuario no la haya tocado

    function crearVentana(def) {
      const seccion = document.querySelector(def.sel);
      if (!seccion) return null;
      const marco = document.createElement("div");
      marco.className = "ventana";
      marco.dataset.ventana = def.id;
      marco.setAttribute("role", "region");
      marco.setAttribute("aria-label", def.titulo);
      const cab = document.createElement("div");
      cab.className = "ventana-barra";
      const titulo = document.createElement("span");
      titulo.className = "ventana-titulo";
      titulo.textContent = def.icono + " " + def.titulo;
      const boton = (cls, texto, etiqueta) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "ventana-btn " + cls;
        b.textContent = texto;
        b.setAttribute("aria-label", etiqueta + " " + def.titulo);
        b.title = etiqueta;
        return b;
      };
      const minimizar = boton("ventana-minimizar", "–", "Minimizar");
      const maximizar = boton("ventana-maximizar", "□", "Maximizar");
      const cerrar = boton("ventana-cerrar", "✕", "Cerrar");
      const botones = document.createElement("span");
      botones.className = "ventana-botones";
      botones.append(minimizar, maximizar, cerrar);
      cab.append(titulo, botones);
      const cuerpo = document.createElement("div");
      cuerpo.className = "ventana-cuerpo";
      cuerpo.append(seccion); // la MISMA sección: ids, listeners y estado intactos
      marco.append(cab, cuerpo);
      capa.append(marco);

      const [w0, h0] = def.tam || [420, 320];
      // x/y/w/h = posición y tamaño "normales"; maximizada solo cambia cómo se pinta (al restaurar vuelve a ellos).
      const v = { def, marco, btnMax: maximizar, abierta: false, minimizada: false, maximizada: false,
        x: 0, y: 0, w: w0, h: h0, nueva: true };
      cerrar.addEventListener("click", () => cerrarVentana(v));
      minimizar.addEventListener("click", () => minimizarVentana(v));
      maximizar.addEventListener("click", () => alternarMaximizar(v));
      cab.addEventListener("dblclick", (ev) => { if (!ev.target.closest("button")) alternarMaximizar(v); });
      marco.addEventListener("pointerdown", () => alFrente(v), true);
      arrastrable(v, cab);
      // Redimensionar con el control nativo (CSS resize): se guarda el tamaño al terminar.
      if ("ResizeObserver" in window) {
        let t = null;
        new ResizeObserver(() => {
          if (!v.abierta || v.minimizada || v.maximizada) return; // maximizada: no pisar el tamaño normal
          clearTimeout(t);
          t = setTimeout(() => {
            if (marco.offsetWidth !== v.w || marco.offsetHeight !== v.h) mosaicoAuto = false; // lo cambió el usuario
            v.w = marco.offsetWidth; v.h = marco.offsetHeight; guardar();
          }, 250);
        }).observe(marco);
      }
      return v;
    }

    function aplicar(v) {
      const m = v.marco;
      const L = v.maximizada ? limites() : null;
      m.style.left = (L ? 0 : v.x) + "px";
      m.style.top = (L ? 0 : v.y) + "px";
      m.style.width = (L ? L.w : v.w) + "px";
      m.style.height = (L ? L.h : v.h) + "px";
      m.classList.toggle("maximizada", v.maximizada);
      v.btnMax.textContent = v.maximizada ? "❐" : "□";
      v.btnMax.title = v.maximizada ? "Restaurar" : "Maximizar";
      v.btnMax.setAttribute("aria-label", (v.maximizada ? "Restaurar " : "Maximizar ") + v.def.titulo);
      m.hidden = !v.abierta || v.minimizada;
    }

    function limites() { return { w: capa.clientWidth, h: capa.clientHeight }; }

    function encajar(v) {
      const L = limites();
      v.w = Math.max(280, Math.min(v.w, L.w - 2 * MARGEN));
      v.h = Math.max(v.def.minH || 160, Math.min(v.h, L.h - 2 * MARGEN)); // mismo mínimo que el CSS
      v.x = Math.max(0, Math.min(v.x, L.w - 120));
      v.y = Math.max(0, Math.min(v.y, L.h - 40));
    }

    // ---------- microinteracciones (solo presentación) ----------
    // El estado (abierta/minimizada, barra de tareas) cambia al instante; la animación es solo visual: al entrar,
    // fundido + escala; al salir, se oculta al terminar la transición. Con «reducir movimiento», sin animación.
    const DURACION = 170;
    const sinMovimiento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function animarEntrada(v) {
      const m = v.marco;
      clearTimeout(v.tSalida);
      v.tSalida = null;
      m.classList.remove("sale", "sale-min");
      if (sinMovimiento()) return;
      m.classList.add("entra");
      void m.offsetWidth; // fija el estado inicial antes de quitar la clase y disparar la transición
      m.classList.remove("entra");
    }

    function ocultarAnimado(v, clase) {
      clearTimeout(v.tSalida);
      if (sinMovimiento()) { aplicar(v); return; }
      v.marco.classList.add(clase);
      v.tSalida = setTimeout(() => { v.tSalida = null; v.marco.classList.remove(clase); aplicar(v); }, DURACION);
    }

    function animarGeometria(v) {
      if (sinMovimiento()) return;
      clearTimeout(v.tGeom);
      v.marco.classList.add("geom");
      v.tGeom = setTimeout(() => v.marco.classList.remove("geom"), DURACION + 60);
    }

    // Ventana activa = la de más arriba que no esté minimizada.
    const activa = () => [...orden].reverse().map((id) => ventanas.find((x) => x.def.id === id))
      .find((w) => w && w.abierta && !w.minimizada);

    function reordenar() {
      const top = activa();
      orden.forEach((id, i) => {
        const w = ventanas.find((x) => x.def.id === id);
        if (w) { w.marco.style.zIndex = String(Z_BASE + i); w.marco.classList.toggle("activa", w === top); }
      });
      pintarTareas();
    }

    function alFrente(v) {
      orden = orden.filter((id) => id !== v.def.id).concat(v.def.id);
      reordenar();
    }

    function minimizarVentana(v) {
      v.minimizada = true; // sigue abierta: baja a la barra de tareas con su posición, tamaño y contenido
      ocultarAnimado(v, "sale-min");
      reordenar();
      guardar();
    }

    function alternarMaximizar(v) {
      v.maximizada = !v.maximizada; // restaurar = volver a x/y/w/h, que no se tocaron al maximizar
      animarGeometria(v);
      aplicar(v);
      alFrente(v);
      guardar();
    }

    // Botón de la barra de tareas: restaura si está minimizada; si ya es la activa, la minimiza; si no, al frente.
    function alternarDesdeBarra(v) {
      if (v.minimizada) { v.minimizada = false; aplicar(v); animarEntrada(v); alFrente(v); guardar(); }
      else if (activa() === v) minimizarVentana(v);
      else alFrente(v);
    }

    function abrirVentana(v) {
      const estabaOculta = !v.abierta || v.minimizada || v.marco.hidden;
      if (v.minimizada) { v.minimizada = false; aplicar(v); }
      if (!v.abierta) {
        v.abierta = true;
        if (v.nueva) { // primera vez sin posición guardada: centrada
          const L = limites();
          v.x = Math.round((L.w - v.w) / 2);
          v.y = Math.round((L.h - v.h) / 2);
        }
        v.nueva = false;
        encajar(v);
        aplicar(v);
      }
      if (v.tSalida) aplicar(v); // se reabre mientras se cerraba: que no la oculte el temporizador pendiente
      if (estabaOculta || v.tSalida) animarEntrada(v); // ya visible: la transición arranca desde aquí
      v.tSalida = null;
      alFrente(v);
      guardar();
    }

    function cerrarVentana(v) {
      v.abierta = false;
      v.minimizada = false;
      v.maximizada = false;
      ocultarAnimado(v, "sale");
      orden = orden.filter((id) => id !== v.def.id);
      pintarTareas();
      guardar();
    }

    function arrastrable(v, asa) {
      let ini = null;
      asa.addEventListener("pointerdown", (ev) => {
        if (ev.button !== 0 || ev.target.closest("button") || v.maximizada) return; // maximizada: no se arrastra
        ini = { px: ev.clientX, py: ev.clientY, x: v.x, y: v.y };
        asa.setPointerCapture(ev.pointerId);
        v.marco.classList.add("arrastrando");
        ev.preventDefault();
      });
      asa.addEventListener("pointermove", (ev) => {
        if (!ini) return;
        v.x = ini.x + ev.clientX - ini.px;
        v.y = ini.y + ev.clientY - ini.py;
        encajar(v);
        v.marco.style.left = v.x + "px";
        v.marco.style.top = v.y + "px";
      });
      const soltar = () => {
        if (!ini) return;
        ini = null;
        v.marco.classList.remove("arrastrando");
        mosaicoAuto = false;
        guardar();
      };
      asa.addEventListener("pointerup", soltar);
      asa.addEventListener("pointercancel", soltar);
      // Teclado: con la barra enfocada, las flechas mueven la ventana (accesible sin ratón).
      asa.tabIndex = 0;
      asa.addEventListener("keydown", (ev) => {
        const paso = ev.shiftKey ? 40 : 10;
        const d = { ArrowLeft: [-paso, 0], ArrowRight: [paso, 0], ArrowUp: [0, -paso], ArrowDown: [0, paso] }[ev.key];
        if (!d || v.maximizada) return;
        ev.preventDefault();
        mosaicoAuto = false;
        v.x += d[0];
        v.y += d[1];
        encajar(v);
        aplicar(v);
        guardar();
      });
    }

    // Alto que necesita el contenido de una ventana con el ancho que tiene ahora (sin scroll interno).
    function altoNatural(v) {
      const m = v.marco;
      const previo = m.style.height;
      m.style.height = "auto";
      const h = m.offsetHeight;
      m.style.height = previo;
      return h;
    }

    // Mosaico por defecto según la vista y el CONTENIDO real de cada panel (medido, no proporciones fijas):
    // - paneles principales en fila y auditoría debajo, si caben enteros dejando a la auditoría su mínimo;
    // - si no caben (pantallas bajas), la auditoría se apila bajo el panel que menos alto necesita y los demás
    //   usan todo el alto; si ni así, fila con el alto disponible (el scroll interno es entonces inevitable).
    const AUDITORIA_MIN = 100;
    function mosaico() {
      const L = limites();
      ventanas.filter((v) => !v.abierta).forEach(aplicar); // las cerradas, ocultas (si no, quedan sin tamaño)
      mosaicoAuto = true;
      const abiertas = ventanas.filter((v) => v.abierta && !v.def.flotante); // el buzón no entra en el mosaico
      abiertas.forEach((v) => { v.minimizada = false; v.maximizada = false; }); // organizar = todas a la vista
      const aud = abiertas.find((v) => v.def.id === "auditoria");
      const arriba = abiertas.filter((v) => v !== aud);
      const util = L.h - 2 * MARGEN;
      // Peso de cada panel en el ancho: el panel "propio" del equipo, más ancho.
      const peso = (id) => (id === "atacante" && rol === "rojo") || (id === "defensor" && rol === "azul") ? 1.4
        : id === "control" ? 1.2 : 1;
      const total = arriba.reduce((s, v) => s + peso(v.def.id), 0) || 1;
      const anchoUtil = (arriba.length ? L.w : 0) - MARGEN * (arriba.length + 1);
      let x = MARGEN;
      arriba.forEach((v) => {
        v.x = x; v.y = MARGEN; v.w = Math.round(anchoUtil * peso(v.def.id) / total); v.h = util;
        x += v.w + MARGEN;
        aplicar(v);
      });
      abiertas.forEach((v) => { v.nueva = false; }); // ya tienen sitio: al reabrirlas no se centran
      const nat = new Map(arriba.map((v) => [v, altoNatural(v)])); // con el ancho ya asignado
      const maxNat = Math.max(0, ...nat.values());
      if (!aud) { guardar(); return; }
      if (!arriba.length || maxNat + MARGEN + AUDITORIA_MIN <= util) {
        const alto = arriba.length ? maxNat : 0;
        arriba.forEach((v) => { v.h = alto; aplicar(v); });
        Object.assign(aud, { x: MARGEN, y: MARGEN + (alto ? alto + MARGEN : 0), w: L.w - 2 * MARGEN,
          h: util - (alto ? alto + MARGEN : 0) });
      } else {
        const bajo = arriba.reduce((a, b) => (nat.get(b) < nat.get(a) ? b : a));
        if (nat.get(bajo) + MARGEN + AUDITORIA_MIN <= util) {
          bajo.h = nat.get(bajo);
          aplicar(bajo);
          Object.assign(aud, { x: bajo.x, y: MARGEN + bajo.h + MARGEN, w: bajo.w, h: util - bajo.h - MARGEN });
        } else {
          const alto = util - MARGEN - AUDITORIA_MIN;
          arriba.forEach((v) => { v.h = alto; aplicar(v); });
          Object.assign(aud, { x: MARGEN, y: MARGEN + alto + MARGEN, w: L.w - 2 * MARGEN, h: AUDITORIA_MIN });
        }
      }
      aplicar(aud);
      guardar();
    }

    // ---------- iconos y barra de tareas ----------
    // Grupos de iconos por función, de arriba abajo, separados por una línea sutil.
    const GRUPOS_ICONOS = [
      ["Herramientas del equipo", ["atacante", "control", "defensor"]],
      ["Comunicación", ["correo"]],
      ["Registro y seguimiento", ["auditoria", "misiones", "finalizar"]],
    ];
    const botonesIcono = new Map();

    function icono(titulo, emoji, alAbrir, id, ayuda) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "esc-icono";
      b.dataset.icono = id;
      const e = document.createElement("span");
      e.className = "esc-icono-img";
      e.setAttribute("aria-hidden", "true");
      e.textContent = emoji;
      const t = document.createElement("span");
      t.className = "esc-icono-txt";
      t.textContent = titulo;
      b.append(e, t);
      b.title = ayuda || "Abrir " + titulo; // tooltip con el nombre (y qué hace) al pasar el cursor
      b.addEventListener("click", alAbrir);
      botonesIcono.set(id, b);
    }

    function pintarIconos() {
      const grupos = GRUPOS_ICONOS.map(([nombre, ids]) => [nombre, ids.map((id) => botonesIcono.get(id)).filter(Boolean)])
        .filter(([, botones]) => botones.length);
      grupos.forEach(([nombre, botones], i) => {
        if (i) {
          const sep = document.createElement("div");
          sep.className = "esc-sep";
          sep.setAttribute("role", "separator");
          iconos.append(sep);
        }
        const g = document.createElement("div");
        g.className = "esc-grupo";
        g.setAttribute("role", "group");
        g.setAttribute("aria-label", nombre);
        g.append(...botones);
        iconos.append(g);
      });
    }

    function pintarTareas() {
      tareas.replaceChildren();
      const top = activa();
      ventanas.filter((v) => v.abierta).forEach((v) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "esc-tarea" + (v === top ? " activa" : "") + (v.minimizada ? " minimizada" : "");
        b.dataset.tarea = v.def.id;
        b.textContent = v.def.icono + " " + v.def.titulo;
        b.title = v.minimizada ? "Restaurar" : v === top ? "Minimizar" : "Traer al frente";
        b.setAttribute("aria-pressed", String(!v.minimizada));
        b.addEventListener("click", () => alternarDesdeBarra(v));
        tareas.append(b);
      });
    }

    function tic() {
      const d = new Date();
      reloj.textContent = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
    }

    // ---------- arranque ----------
    VENTANAS.forEach((def) => { const v = crearVentana(def); if (v) ventanas.push(v); });
    mid.hidden = true; // ya no contiene nada: sus secciones viven en ventanas

    ventanas.filter((v) => !v.def.sinIcono).forEach((v) => icono(v.def.titulo, v.def.icono, () => abrirVentana(v), v.def.id,
      "Abrir la ventana " + v.def.titulo));
    ACCESOS.filter((a) => a.roles.includes(rol)).forEach((a) => icono(a.titulo, a.icono, a.accion, a.id, a.ayuda));
    pintarIconos();

    const buzon = ventanas.find((v) => v.def.id === "buzon");
    if (buzon && typeof R !== "undefined" && R.alojarBuzon) {
      R.alojarBuzon({ abrir: () => abrirVentana(buzon), cerrar: () => cerrarVentana(buzon), abierta: () => buzon.abierta });
    }

    const hayGuardado = ventanas.some((v) => guardado[v.def.id] && !v.def.efimera);
    ventanas.forEach((v) => {
      const g = guardado[v.def.id];
      if (g) {
        Object.assign(v, { abierta: !!g.abierta, minimizada: !!g.minimizada, maximizada: !!g.maximizada,
          x: +g.x || 0, y: +g.y || 0, w: +g.w || v.w, h: +g.h || v.h, nueva: false });
      } else v.abierta = v.def.abierta.includes(rol);
      if (v.def.efimera) Object.assign(v, { abierta: false, minimizada: false, maximizada: false }); // solo con su acceso
    });
    if (hayGuardado) ventanas.forEach((v) => { if (v.abierta) encajar(v); aplicar(v); });
    else mosaico();
    ventanas.filter((v) => v.abierta).forEach(alFrente);

    organizar.addEventListener("click", mosaico);
    // El área del escritorio cambia de alto sin que cambie la ventana del navegador (p. ej. aparece la fila del
    // marcador de la partida tras el primer SSE): si el mosaico no se ha tocado, se recalcula; si no, solo se
    // ajusta lo que quedaría fuera por abajo.
    if ("ResizeObserver" in window) {
      let previo = limites().h;
      new ResizeObserver(() => {
        const L = limites();
        if (Math.abs(L.h - previo) < 2) return;
        previo = L.h;
        if (mosaicoAuto) { mosaico(); return; }
        ventanas.filter((v) => v.abierta).forEach((v) => {
          if (v.y + v.h > L.h - MARGEN) v.h = Math.max(v.def.minH || 160, L.h - MARGEN - v.y);
          if (v.y + v.h > L.h - MARGEN) v.y = Math.max(0, L.h - MARGEN - v.h);
          encajar(v);
          aplicar(v);
        });
        guardar();
      }).observe(capa);
    }
    window.addEventListener("resize", () => {
      if (window.innerWidth < ANCHO_MINIMO) return; // se respeta al recargar
      ventanas.forEach((v) => { if (v.abierta) { encajar(v); aplicar(v); } }); // las maximizadas se reajustan
    });
    tic();
    setInterval(tic, 15000);
  }
})();
