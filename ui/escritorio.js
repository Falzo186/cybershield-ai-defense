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
      { id: "auditoria", titulo: "Auditoría", icono: "📜", sel: "section.panel.aud", abierta: ["rojo", "azul", "general", "espectador", ""] },
      // Buzón: la MISMA tarjeta del modal (render.js delega abrir/cerrar en esta ventana con R.alojarBuzon).
      // Se abre desde el acceso «Correo/Buzón» (que carga los datos), nunca sola al recargar, y flota fuera del mosaico.
      { id: "buzon", titulo: rol === "azul" ? "Buzón" : "Correo", icono: "📬", sel: "#buzon-modal .buzon-card",
        abierta: [], roles: ["rojo", "azul"], sinIcono: true, efimera: true, flotante: true, tam: [680, 560] },
    ].filter((d) => !d.roles || d.roles.includes(rol));
    // Accesos directos: reutilizan los botones y modales que ya existen (mismo código, mismos permisos).
    const ACCESOS = [
      { id: "correo", titulo: rol === "azul" ? "Buzón" : "Correo", icono: "📬", roles: ["rojo", "azul"],
        accion: () => pulsar("btn-buzon", "Tu vista aún no tiene token de equipo.") },
      { id: "misiones", titulo: "Misiones", icono: "🎯", roles: ["azul"],
        accion: () => { if (pulsar("btn-buzon", "Tu vista aún no tiene token de equipo.")) clicEn('[data-azul="misiones"]'); } },
      { id: "finalizar", titulo: "Finalizar partida", icono: "🏁", roles: ["general"],
        accion: () => pulsar("btn-finalizar", "Necesitas el token de la vista general.") },
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
      ventanas.map((v) => [v.def.id, { abierta: v.abierta, x: v.x, y: v.y, w: v.w, h: v.h }]))));

    // ---------- ventanas ----------
    const ventanas = [];
    let orden = []; // ids de abajo a arriba (z-order)

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
      const cerrar = document.createElement("button");
      cerrar.type = "button";
      cerrar.className = "ventana-cerrar";
      cerrar.textContent = "✕";
      cerrar.setAttribute("aria-label", "Cerrar " + def.titulo);
      cab.append(titulo, cerrar);
      const cuerpo = document.createElement("div");
      cuerpo.className = "ventana-cuerpo";
      cuerpo.append(seccion); // la MISMA sección: ids, listeners y estado intactos
      marco.append(cab, cuerpo);
      capa.append(marco);

      const [w0, h0] = def.tam || [420, 320];
      const v = { def, marco, abierta: false, x: 0, y: 0, w: w0, h: h0, nueva: true };
      cerrar.addEventListener("click", () => cerrarVentana(v));
      marco.addEventListener("pointerdown", () => alFrente(v), true);
      arrastrable(v, cab);
      // Redimensionar con el control nativo (CSS resize): se guarda el tamaño al terminar.
      if ("ResizeObserver" in window) {
        let t = null;
        new ResizeObserver(() => {
          if (!v.abierta) return;
          clearTimeout(t);
          t = setTimeout(() => { v.w = marco.offsetWidth; v.h = marco.offsetHeight; guardar(); }, 250);
        }).observe(marco);
      }
      return v;
    }

    function aplicar(v) {
      const m = v.marco;
      m.style.left = v.x + "px";
      m.style.top = v.y + "px";
      m.style.width = v.w + "px";
      m.style.height = v.h + "px";
      m.hidden = !v.abierta;
    }

    function limites() { return { w: capa.clientWidth, h: capa.clientHeight }; }

    function encajar(v) {
      const L = limites();
      v.w = Math.max(280, Math.min(v.w, L.w - 2 * MARGEN));
      v.h = Math.max(160, Math.min(v.h, L.h - 2 * MARGEN));
      v.x = Math.max(0, Math.min(v.x, L.w - 120));
      v.y = Math.max(0, Math.min(v.y, L.h - 40));
    }

    function alFrente(v) {
      orden = orden.filter((id) => id !== v.def.id).concat(v.def.id);
      orden.forEach((id, i) => {
        const w = ventanas.find((x) => x.def.id === id);
        if (w) { w.marco.style.zIndex = String(Z_BASE + i); w.marco.classList.toggle("activa", i === orden.length - 1); }
      });
      pintarTareas();
    }

    function abrirVentana(v) {
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
      alFrente(v);
      guardar();
    }

    function cerrarVentana(v) {
      v.abierta = false;
      aplicar(v);
      orden = orden.filter((id) => id !== v.def.id);
      pintarTareas();
      guardar();
    }

    function arrastrable(v, asa) {
      let ini = null;
      asa.addEventListener("pointerdown", (ev) => {
        if (ev.button !== 0 || ev.target.closest("button")) return;
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
        guardar();
      };
      asa.addEventListener("pointerup", soltar);
      asa.addEventListener("pointercancel", soltar);
      // Teclado: con la barra enfocada, las flechas mueven la ventana (accesible sin ratón).
      asa.tabIndex = 0;
      asa.addEventListener("keydown", (ev) => {
        const paso = ev.shiftKey ? 40 : 10;
        const d = { ArrowLeft: [-paso, 0], ArrowRight: [paso, 0], ArrowUp: [0, -paso], ArrowDown: [0, paso] }[ev.key];
        if (!d) return;
        ev.preventDefault();
        v.x += d[0];
        v.y += d[1];
        encajar(v);
        aplicar(v);
        guardar();
      });
    }

    // Mosaico por defecto según la vista: paneles principales arriba, auditoría abajo a lo ancho.
    function mosaico() {
      const L = limites();
      ventanas.filter((v) => !v.abierta).forEach(aplicar); // las cerradas, ocultas (si no, quedan sin tamaño)
      const abiertas = ventanas.filter((v) => v.abierta && !v.def.flotante); // el buzón no entra en el mosaico
      const abajo = abiertas.filter((v) => v.def.id === "auditoria");
      const arriba = abiertas.filter((v) => v.def.id !== "auditoria");
      const altoAbajo = abajo.length ? Math.round(L.h * 0.3) : 0;
      const altoArriba = L.h - altoAbajo - MARGEN * (abajo.length ? 3 : 2);
      // Peso de cada panel en el ancho: el panel "propio" del equipo, más ancho.
      const peso = (id) => (id === "atacante" && rol === "rojo") || (id === "defensor" && rol === "azul") ? 1.4
        : id === "control" ? 1.2 : 1;
      const total = arriba.reduce((s, v) => s + peso(v.def.id), 0) || 1;
      let x = MARGEN;
      const anchoUtil = L.w - MARGEN * (arriba.length + 1);
      arriba.forEach((v) => {
        v.x = x; v.y = MARGEN;
        v.w = Math.round(anchoUtil * peso(v.def.id) / total);
        v.h = altoArriba;
        x += v.w + MARGEN;
        aplicar(v);
      });
      abajo.forEach((v) => {
        v.x = MARGEN; v.y = L.h - altoAbajo - MARGEN; v.w = L.w - 2 * MARGEN; v.h = altoAbajo;
        aplicar(v);
      });
      guardar();
    }

    // ---------- iconos y barra de tareas ----------
    function icono(titulo, emoji, alAbrir, id) {
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
      b.title = "Abrir " + titulo;
      b.addEventListener("click", alAbrir);
      iconos.append(b);
    }

    function pintarTareas() {
      tareas.replaceChildren();
      ventanas.filter((v) => v.abierta).forEach((v) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "esc-tarea" + (orden[orden.length - 1] === v.def.id ? " activa" : "");
        b.textContent = v.def.icono + " " + v.def.titulo;
        b.addEventListener("click", () => abrirVentana(v));
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

    ventanas.filter((v) => !v.def.sinIcono).forEach((v) => icono(v.def.titulo, v.def.icono, () => abrirVentana(v), v.def.id));
    ACCESOS.filter((a) => a.roles.includes(rol)).forEach((a) => icono(a.titulo, a.icono, a.accion, a.id));

    const buzon = ventanas.find((v) => v.def.id === "buzon");
    if (buzon && typeof R !== "undefined" && R.alojarBuzon) {
      R.alojarBuzon({ abrir: () => abrirVentana(buzon), cerrar: () => cerrarVentana(buzon), abierta: () => buzon.abierta });
    }

    const hayGuardado = ventanas.some((v) => guardado[v.def.id] && !v.def.efimera);
    ventanas.forEach((v) => {
      const g = guardado[v.def.id];
      if (g) {
        Object.assign(v, { abierta: !!g.abierta, x: +g.x || 0, y: +g.y || 0, w: +g.w || v.w, h: +g.h || v.h, nueva: false });
      } else v.abierta = v.def.abierta.includes(rol);
      if (v.def.efimera) v.abierta = false; // el buzón solo se abre con su acceso (que carga los datos)
    });
    if (hayGuardado) ventanas.forEach((v) => { if (v.abierta) encajar(v); aplicar(v); });
    else mosaico();
    ventanas.filter((v) => v.abierta).forEach(alFrente);

    organizar.addEventListener("click", mosaico);
    window.addEventListener("resize", () => {
      if (window.innerWidth < ANCHO_MINIMO) return; // se respeta al recargar
      ventanas.forEach((v) => { if (v.abierta) { encajar(v); aplicar(v); } });
    });
    tic();
    setInterval(tic, 15000);
  }
})();
