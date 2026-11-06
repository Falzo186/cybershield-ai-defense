/* CyberShield · Panel de operaciones y análisis.
   Vanilla, sin dependencias ni build, como el resto del proyecto.

   Regla heredada del proyecto y que aquí se mantiene: **nunca `innerHTML` con datos**. Todo el texto
   dinámico entra por `textContent` y los nodos se crean con `createElement`, así que un dato del
   laboratorio no puede inyectar marcado. Los únicos `innerHTML` que existen son plantillas de SVG fijas
   escritas en este archivo.

   Segunda regla: **nada se pinta como real si no lo es**. Donde el backend dice `simulado`, la interfaz lo
   marca; donde no hay dato, pone «sin datos», no 0. */

(() => {
  "use strict";

  const API = "/api/panel";

  // ── Utilidades de DOM ───────────────────────────────────────────────────────────────────────────
  function el(tag, props, hijos) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v === null || v === undefined) continue;
      if (k === "txt") n.textContent = String(v);
      else if (k === "cls") n.className = v;
      else if (k === "on") for (const [ev, fn] of Object.entries(v)) n.addEventListener(ev, fn);
      else if (k === "datos") for (const [d, dv] of Object.entries(v)) n.dataset[d] = dv;
      else n.setAttribute(k, v);
    }
    for (const h of [].concat(hijos || [])) {
      if (h === null || h === undefined || h === false) continue;
      n.appendChild(typeof h === "string" ? document.createTextNode(h) : h);
    }
    return n;
  }
  const vaciar = (n) => { while (n.firstChild) n.removeChild(n.firstChild); return n; };
  const poner = (id, ...hijos) => { const n = document.getElementById(id); if (n) { vaciar(n); hijos.flat().forEach((h) => h && n.appendChild(h)); } return n; };

  function icono(nombre, clase) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    if (clase) svg.setAttribute("class", clase);
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#i-" + nombre);
    svg.appendChild(use);
    return svg;
  }

  // ── Formato ─────────────────────────────────────────────────────────────────────────────────────
  const SIN = "sin datos";
  const pct = (v, d = 1) => (v === null || v === undefined ? SIN : (v * 100).toFixed(d) + " %");
  const num = (v, d = 0) => (v === null || v === undefined ? SIN : Number(v).toFixed(d));
  const ms = (v) => (v === null || v === undefined ? SIN : Math.round(v) + " ms");
  function fecha(iso) {
    if (!iso) return SIN;
    const d = new Date(iso);
    if (isNaN(d)) return String(iso);
    return d.toLocaleString("es", { day: "2-digit", month: "2-digit", year: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  const hora = (iso) => { const d = new Date(iso); return isNaN(d) ? String(iso || "") : d.toLocaleTimeString("es"); };

  function chip(texto, tipo, conPunto = true) {
    return el("span", { cls: "chip chip-" + (tipo || "neutro") + (conPunto ? "" : " sin-punto"), txt: texto });
  }
  function aviso(texto, tipo = "info", iconoNombre = "info") {
    return el("div", { cls: "aviso aviso-" + tipo }, [icono(iconoNombre), el("div", { txt: texto })]);
  }
  function vacio(titulo, detalle) {
    return el("div", { cls: "vacio" }, [el("strong", { txt: titulo }), detalle ? document.createTextNode(detalle) : null]);
  }
  const cargando = () => el("div", { cls: "cargando", txt: "Cargando" });

  function metrica(etiqueta, valor, detalle, claseValor) {
    const v = (valor === null || valor === undefined || valor === SIN)
      ? el("span", { cls: "sin-dato", txt: SIN })
      : document.createTextNode(String(valor));
    return el("div", { cls: "tarjeta metrica" }, [
      el("div", { cls: "metrica-etiqueta", txt: etiqueta }),
      el("div", { cls: "metrica-valor" + (claseValor ? " " + claseValor : "") }, [v]),
      detalle ? el("div", { cls: "metrica-detalle", txt: detalle }) : null,
    ]);
  }

  function tabla(columnas, filas, opciones) {
    const o = opciones || {};
    if (!filas.length) return vacio(o.tituloVacio || "No hay nada que mostrar", o.detalleVacio || "");
    const thead = el("thead", {}, [el("tr", {}, columnas.map((c) => el("th", { txt: c.titulo })))]);
    const tbody = el("tbody", {}, filas.map((f) => {
      const tr = el("tr", { cls: o.alPulsar ? "clicable" : "" });
      if (o.alPulsar) tr.addEventListener("click", () => o.alPulsar(f));
      columnas.forEach((c) => {
        const contenido = c.render ? c.render(f) : f[c.campo];
        const td = el("td", { cls: c.cls || "" });
        if (contenido instanceof Node) td.appendChild(contenido);
        else td.textContent = contenido === null || contenido === undefined ? "—" : String(contenido);
        tr.appendChild(td);
      });
      return tr;
    }));
    return el("div", { cls: "envoltura-tabla" }, [el("table", { cls: "datos" }, [thead, tbody])]);
  }

  function parejas(pares) {
    const dl = el("dl", { cls: "par" });
    pares.forEach(([k, v]) => {
      if (v === undefined) return;
      dl.appendChild(el("dt", { txt: k }));
      dl.appendChild(el("dd", { txt: v === null || v === "" ? SIN : String(v) }));
    });
    return dl;
  }

  function barraIC(w) {
    // Proporción con su intervalo de confianza dibujado encima: la cifra nunca va sola.
    if (!w || w.valor === null || w.valor === undefined) return el("div", { cls: "metrica-detalle", txt: SIN });
    const caja = el("div", { cls: "barra-ic" });
    caja.appendChild(el("div", { cls: "pista" }));
    caja.appendChild(el("div", { cls: "valor", style: `left:0;width:${(w.valor * 100).toFixed(1)}%` }));
    if (w.bajo !== null && w.alto !== null) {
      caja.appendChild(el("div", { cls: "ic",
        style: `left:${(w.bajo * 100).toFixed(1)}%;width:${((w.alto - w.bajo) * 100).toFixed(1)}%` }));
    }
    return caja;
  }

  function conIC(w) {
    if (!w || w.valor === null) return SIN;
    const ic = (w.bajo === null) ? "" : `  IC95 [${pct(w.bajo, 0)}, ${pct(w.alto, 0)}]`;
    return `${pct(w.valor)}${ic} · n=${w.n}`;
  }

  // ── Gráficas: SVG a mano, sin librerías ─────────────────────────────────────────────────────────
  const NS = "http://www.w3.org/2000/svg";
  const s = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v); return n; };

  function graficaBarras(datos, opciones) {
    // datos: [{etiqueta, valor, bajo?, alto?}] con valor en 0-1 o absoluto
    const o = Object.assign({ alto: 190, max: null, formato: (v) => pct(v, 0), unidad: "" }, opciones);
    const útiles = datos.filter((d) => d.valor !== null && d.valor !== undefined);
    if (!útiles.length) return vacio("Sin datos suficientes", "No hay ningún experimento con este dato.");
    const W = 560, H = o.alto, mIzq = 38, mAb = 42, mArr = 10, mDer = 10;
    const max = o.max !== null ? o.max : Math.max(...útiles.map((d) => (d.alto ?? d.valor))) * 1.1 || 1;
    const svg = s("svg", { class: "grafica", viewBox: `0 0 ${W} ${H}`, role: "img" });
    svg.appendChild(s("title", {})).textContent = o.titulo || "Gráfica de barras";
    const anchoUtil = W - mIzq - mDer, altoUtil = H - mArr - mAb;
    for (let i = 0; i <= 4; i++) {
      const y = mArr + (altoUtil * i) / 4;
      svg.appendChild(s("line", { class: "rejilla-linea", x1: mIzq, y1: y, x2: W - mDer, y2: y }));
      const t = s("text", { x: mIzq - 6, y: y + 3, "text-anchor": "end" });
      t.textContent = o.formato(max * (1 - i / 4));
      svg.appendChild(t);
    }
    svg.appendChild(s("line", { class: "eje", x1: mIzq, y1: H - mAb, x2: W - mDer, y2: H - mAb }));
    const paso = anchoUtil / datos.length, ancho = Math.min(58, paso * 0.56);
    datos.forEach((d, i) => {
      const cx = mIzq + paso * (i + 0.5);
      if (d.valor !== null && d.valor !== undefined) {
        const h = Math.max(1, (d.valor / max) * altoUtil);
        svg.appendChild(s("rect", { class: d.clase || "barra", x: cx - ancho / 2, y: H - mAb - h, width: ancho, height: h, rx: 2 }));
        if (d.bajo !== null && d.bajo !== undefined && d.alto !== null && d.alto !== undefined) {
          const yb = H - mAb - (d.bajo / max) * altoUtil, ya = H - mAb - (d.alto / max) * altoUtil;
          svg.appendChild(s("line", { x1: cx, y1: ya, x2: cx, y2: yb, stroke: "var(--p-texto-2)", "stroke-width": 1.5 }));
          svg.appendChild(s("line", { x1: cx - 5, y1: ya, x2: cx + 5, y2: ya, stroke: "var(--p-texto-2)", "stroke-width": 1.5 }));
          svg.appendChild(s("line", { x1: cx - 5, y1: yb, x2: cx + 5, y2: yb, stroke: "var(--p-texto-2)", "stroke-width": 1.5 }));
        }
        const vt = s("text", { x: cx, y: H - mAb - h - 5, "text-anchor": "middle", class: "etiqueta-eje" });
        vt.textContent = o.formato(d.valor);
        svg.appendChild(vt);
      } else {
        const vt = s("text", { x: cx, y: H - mAb - 6, "text-anchor": "middle" });
        vt.textContent = SIN;
        svg.appendChild(vt);
      }
      const t = s("text", { x: cx, y: H - mAb + 15, "text-anchor": "middle" });
      t.textContent = d.etiqueta;
      svg.appendChild(t);
      if (d.sub) { const t2 = s("text", { x: cx, y: H - mAb + 28, "text-anchor": "middle" }); t2.textContent = d.sub; svg.appendChild(t2); }
    });
    return svg;
  }

  function graficaLinea(puntos, opciones) {
    const o = Object.assign({ alto: 190, formato: (v) => pct(v, 0) }, opciones);
    const útiles = puntos.filter((p) => p.valor !== null && p.valor !== undefined);
    if (útiles.length < 1) return vacio("Sin serie que mostrar", "Hace falta al menos un experimento con exactitud medida.");
    const W = 560, H = o.alto, mIzq = 38, mAb = 34, mArr = 12, mDer = 12;
    const anchoUtil = W - mIzq - mDer, altoUtil = H - mArr - mAb;
    const svg = s("svg", { class: "grafica", viewBox: `0 0 ${W} ${H}`, role: "img" });
    svg.appendChild(s("title", {})).textContent = o.titulo || "Serie temporal";
    for (let i = 0; i <= 4; i++) {
      const y = mArr + (altoUtil * i) / 4;
      svg.appendChild(s("line", { class: "rejilla-linea", x1: mIzq, y1: y, x2: W - mDer, y2: y }));
      const t = s("text", { x: mIzq - 6, y: y + 3, "text-anchor": "end" });
      t.textContent = o.formato(1 - i / 4);
      svg.appendChild(t);
    }
    svg.appendChild(s("line", { class: "eje", x1: mIzq, y1: H - mAb, x2: W - mDer, y2: H - mAb }));
    const x = (i) => mIzq + (útiles.length === 1 ? anchoUtil / 2 : (anchoUtil * i) / (útiles.length - 1));
    const y = (v) => H - mAb - v * altoUtil;
    if (útiles.some((p) => p.bajo !== null && p.bajo !== undefined)) {
      const arriba = útiles.map((p, i) => `${x(i)},${y(p.alto ?? p.valor)}`).join(" ");
      const abajo = útiles.map((p, i) => `${x(i)},${y(p.bajo ?? p.valor)}`).reverse().join(" ");
      svg.appendChild(s("polygon", { class: "banda", points: arriba + " " + abajo }));
    }
    svg.appendChild(s("polyline", { class: "linea", points: útiles.map((p, i) => `${x(i)},${y(p.valor)}`).join(" ") }));
    útiles.forEach((p, i) => {
      svg.appendChild(s("circle", { class: "punto", cx: x(i), cy: y(p.valor), r: 3 }));
      if (i % Math.ceil(útiles.length / 6) === 0 || i === útiles.length - 1) {
        const t = s("text", { x: x(i), y: H - mAb + 14, "text-anchor": "middle" });
        t.textContent = p.etiqueta;
        svg.appendChild(t);
      }
    });
    return svg;
  }

  // ── Acceso a la API ─────────────────────────────────────────────────────────────────────────────
  async function pedir(ruta, opciones) {
    try {
      const r = await fetch(API + ruta, Object.assign({ headers: { "Content-Type": "application/json" } }, opciones || {}));
      const cuerpo = await r.json().catch(() => null);
      if (!r.ok) return { ok: false, error: (cuerpo && cuerpo.error) || `HTTP ${r.status}`, datos: cuerpo };
      return { ok: true, datos: cuerpo, error: null };
    } catch (e) {
      return { ok: false, error: String(e && e.message ? e.message : e), datos: null };
    }
  }

  // ── Estado compartido ───────────────────────────────────────────────────────────────────────────
  const estado = { general: null, experimentos: [], seleccion: [], vista: "dashboard", temporizadorCampana: null };

  // ── Barra superior ──────────────────────────────────────────────────────────────────────────────
  function pintarEstados(g) {
    const hijos = [];
    if (!g) { hijos.push(chip("Sin conexión con el servidor", "error")); poner("estados", hijos); return; }
    const o = g.ollama;
    hijos.push(chip(o.disponible ? `Ollama disponible · ${o.modelos.length} modelos` : "Ollama no responde",
      o.disponible ? "ok" : "error"));
    hijos.push(el("span", { cls: "ocultable" }, [chip("SQLite · solo consultas fijas", "ok")]));
    const w = g.wazuh;
    const tipoW = w.modo === "real" ? (w.conectado ? "ok" : "error") : (w.modo === "simulado" ? "simulado" : "neutro");
    hijos.push(chip("Wazuh: " + w.modo + (w.modo === "real" && !w.conectado ? " (sin conexión)" : ""), tipoW));
    hijos.push(el("span", { cls: "ocultable" }, [
      chip("RAG: " + (g.rag.listo ? g.rag.modo : "sin índice"), g.rag.listo ? "info" : "aviso")]));
    poner("estados", hijos);
  }

  // ── Dashboard ───────────────────────────────────────────────────────────────────────────────────
  async function vistaDashboard() {
    poner("kpis", cargando());
    const [res, adv] = await Promise.all([pedir("/resumen"), pedir("/adversarial")]);
    if (!res.ok) { poner("kpis", aviso("No se pudo leer el resumen: " + res.error, "error", "aviso")); return; }
    const d = res.datos;
    const ex = d.ultima_exactitud;
    poner("kpis",
      metrica("Experimentos registrados", d.experimentos.total,
        `${d.experimentos.oficiales} oficiales · ${d.rondas_evaluadas} rondas evaluadas`),
      metrica("Última exactitud medida", ex && ex.valor !== null ? pct(ex.valor) : null,
        ex && ex.valor !== null ? `IC95 [${pct(ex.bajo, 0)}, ${pct(ex.alto, 0)}] · n=${ex.n}` : "Aún no hay ninguna campaña con rondas imputables"),
      metrica("Latencia mediana del defensor",
        d.latencia_mediana_ms.mediana !== null ? ms(d.latencia_mediana_ms.mediana) : null,
        `mediana entre ${d.latencia_mediana_ms.n} experimentos`),
      metrica("Modelos evaluados", d.modelos_evaluados.length || null,
        d.modelos_evaluados.join(", ") || "Ninguno todavía"));

    const serie = d.serie_exactitud.map((p) => ({ etiqueta: (p.tecnica || "?"), valor: p.valor, bajo: p.bajo, alto: p.alto }));
    poner("grafica-serie", serie.length
      ? [graficaLinea(serie, { titulo: "Exactitud por experimento, con su intervalo de confianza" }),
         el("p", { cls: "nota-tarjeta", txt: "La banda es el intervalo de confianza del 95 %. Un punto sin banda no tiene muestra suficiente." })]
      : vacio("Todavía no hay experimentos con exactitud medida", "Lanza una campaña desde la consola de defensa."));
    const chipSerie = document.getElementById("chip-serie");
    if (chipSerie) chipSerie.textContent = serie.length + " experimentos";

    // Media por técnica a partir de los experimentos registrados.
    const porTec = {};
    d.serie_exactitud.forEach((p) => {
      if (p.valor === null) return;
      (porTec[p.tecnica || "?"] = porTec[p.tecnica || "?"] || []).push(p);
    });
    const barras = Object.entries(porTec).map(([t, ps]) => ({
      etiqueta: t, valor: ps.reduce((a, p) => a + p.valor, 0) / ps.length,
      sub: "n=" + ps.reduce((a, p) => a + (p.n || 0), 0),
    }));
    poner("grafica-tecnicas", barras.length
      ? [graficaBarras(barras, { titulo: "Exactitud media por técnica", max: 1 }),
         el("p", { cls: "nota-tarjeta", txt: "Media simple de los experimentos registrados de cada técnica. Para comparar con rigor, usa el comparador de la sección Experimentos." })]
      : vacio("Sin técnicas comparadas todavía", ""));

    poner("tabla-recientes", tabla([
      { titulo: "Fecha", render: (f) => fecha(f.fecha) },
      { titulo: "Modelo", campo: "modelo", cls: "mono" },
      { titulo: "Técnica", campo: "tecnica" },
      { titulo: "Pipeline", campo: "pipeline" },
      { titulo: "Tipo", render: (f) => chip(f.tipo, f.tipo === "oficial" ? "info" : "neutro", false) },
      { titulo: "Exactitud", cls: "num", render: (f) => {
          const e = (f.metricas || {}).exactitud; return e && e.valor !== null ? pct(e.valor) : SIN; } },
      { titulo: "n", cls: "num", render: (f) => ((f.metricas || {}).exactitud || {}).n ?? "—" },
    ], estado.experimentos.slice(0, 8), { tituloVacio: "Sin experimentos registrados" }));

    poner("servicios", parejas([
      ["Ollama", estado.general ? (estado.general.ollama.disponible ? "disponible en " + estado.general.ollama.host : "no responde") : SIN],
      ["Modelos instalados", estado.general ? estado.general.ollama.modelos.join(", ") : SIN],
      ["Base de datos", "SQLite, solo consultas fijas y parametrizadas"],
      ["Wazuh", estado.general ? estado.general.wazuh.detalle : SIN],
      ["Índice RAG", estado.general && estado.general.rag.listo
        ? `${estado.general.rag.fragmentos} fragmentos de ${estado.general.rag.documentos} documentos (${estado.general.rag.modo})` : "sin construir"],
      ["Conjunto de evaluación", estado.general ? estado.general.conjunto_evaluacion.total + " escenarios" : SIN],
    ]));

    if (adv.ok) {
      const m = adv.datos.metricas;
      poner("resumen-adversarial",
        parejas([
          ["Intentos maliciosos", m.maliciosos],
          ["Detección", conIC(m.deteccion)],
          ["Falsos positivos", `${m.FP} de ${m.benignos} controles benignos`],
          ["No detectados", m.categorias_no_detectadas.join(", ") || "ninguno"],
        ]),
        el("div", { style: "margin-top:12px" }, [barraIC(m.deteccion)]),
        el("p", { cls: "nota-tarjeta", txt: "Solo la capa determinista. Lo que la atraviesa llega al defensor IA y, si este falla, a las capas de permisos." }));
    } else {
      poner("resumen-adversarial", aviso("No se pudo leer el laboratorio adversarial: " + adv.error, "error", "aviso"));
    }
  }

  // ── Consola de defensa ──────────────────────────────────────────────────────────────────────────
  function formularioCampana(g, campana) {
    const modelos = g && g.ollama.disponible ? g.ollama.modelos : [];
    const sel = (id, opciones, valor) => el("select", { id }, opciones.map((o) =>
      el("option", { value: o.v, txt: o.t, selected: o.v === valor ? "selected" : null })));
    const modos = Object.entries((campana && campana.modos) || {}).map(([k, v]) =>
      ({ v: k, t: `${k} · ${v.descripcion}` }));
    const hijos = [];
    if (!modelos.length) {
      hijos.push(aviso("Ollama no responde o no tiene modelos instalados. No se puede lanzar ninguna campaña: el panel no simula resultados.", "aviso", "aviso"));
    }
    hijos.push(
      el("label", { cls: "campo" }, [el("span", { txt: "Modelo" }),
        sel("cfg-modelo", modelos.map((m) => ({ v: m, t: m })))]),
      el("label", { cls: "campo" }, [el("span", { txt: "Modo" }), sel("cfg-modo", modos, "rapido")]),
      el("label", { cls: "campo" }, [el("span", { txt: "Técnica" }),
        sel("cfg-tecnica", ["base", "fewshot", "rag", "fewshot_rag"].map((t) => ({ v: t, t })), "fewshot")]),
      el("label", { cls: "campo" }, [el("span", { txt: "Pipeline" }),
        sel("cfg-pipeline", ((campana && campana.pipelines) || ["directo"]).map((p) => ({ v: p, t: p })), "directo")]),
      el("label", { cls: "campo" }, [el("span", { txt: "Repeticiones (vacío = las del modo)" }),
        el("input", { type: "number", id: "cfg-rep", min: "1", max: "50" })]),
      el("label", { cls: "campo" }, [el("span", { txt: "Semilla" }), el("input", { type: "number", id: "cfg-semilla", value: "0" })]),
      el("label", { cls: "campo" }, [el("span", { txt: "Temperatura (vacío = la del defensor, 0.2)" }),
        el("input", { type: "number", id: "cfg-temp", step: "0.1", min: "0", max: "2" })]),
      el("div", { style: "display:flex;gap:8px" }, [
        el("button", { cls: "boton boton-primario", id: "btn-lanzar", disabled: modelos.length ? null : "disabled",
          on: { click: lanzarCampana } }, [icono("jugar"), "Lanzar campaña"]),
        el("button", { cls: "boton boton-peligro", id: "btn-cancelar", disabled: "disabled",
          on: { click: cancelarCampana } }, [icono("detener"), "Cancelar"]),
      ]),
      el("p", { cls: "nota-tarjeta", txt: "La campaña corre en el servidor y usa Ollama de verdad. En esta máquina, una ronda tarda entre 2 y 7 s." }));
    poner("formulario-campana", hijos);
  }

  async function lanzarCampana() {
    const v = (id) => { const n = document.getElementById(id); return n && n.value !== "" ? n.value : null; };
    const cuerpo = {
      modelo: v("cfg-modelo"), modo: v("cfg-modo"), tecnica: v("cfg-tecnica"), pipeline: v("cfg-pipeline"),
      repeticiones: v("cfg-rep") ? Number(v("cfg-rep")) : null, semilla: Number(v("cfg-semilla") || 0),
      temperatura: v("cfg-temp") ? Number(v("cfg-temp")) : null, tipo: "exploratorio",
    };
    const r = await pedir("/campana", { method: "POST", body: JSON.stringify(cuerpo) });
    if (!r.ok) { poner("campana-estado", aviso("No se lanzó: " + r.error, "error", "aviso")); return; }
    seguirCampana();
  }

  async function cancelarCampana() {
    const r = await pedir("/campana/cancelar", { method: "POST", body: "{}" });
    if (!r.ok) poner("campana-estado", aviso("No se pudo cancelar: " + r.error, "aviso", "aviso"));
  }

  function seguirCampana() {
    if (estado.temporizadorCampana) clearInterval(estado.temporizadorCampana);
    const tic = async () => {
      const r = await pedir("/campana");
      if (!r.ok) return;
      pintarCampana(r.datos);
      if (!r.datos.en_curso) { clearInterval(estado.temporizadorCampana); estado.temporizadorCampana = null; cargarExperimentos(); }
    };
    tic();
    estado.temporizadorCampana = setInterval(tic, 1500);
  }

  function pintarCampana(c) {
    const chipC = document.getElementById("chip-campana");
    const btnL = document.getElementById("btn-lanzar"), btnC = document.getElementById("btn-cancelar");
    if (btnL) btnL.disabled = c.en_curso;
    if (btnC) btnC.disabled = !c.en_curso;
    const p = c.progreso;
    if (chipC) chipC.textContent = c.en_curso ? "en curso" : (p ? p.estado : "en reposo");
    const hijos = [];
    if (c.error) hijos.push(aviso("La campaña terminó con un error: " + c.error, "error", "aviso"));
    if (!p) {
      hijos.push(vacio("No hay ninguna campaña lanzada en esta sesión",
        "Configura una a la derecha y pulsa «Lanzar campaña»."));
    } else {
      const barra = el("div", { cls: "progreso" }, [el("i", { style: `width:${(p.fraccion * 100).toFixed(1)}%` })]);
      hijos.push(barra, parejas([
        ["Estado", p.estado],
        ["Rondas", `${p.hechas} de ${p.planificadas}`],
        ["Transcurrido", Math.round(p.transcurrido_s) + " s"],
        ["Modelo", c.config && c.config.modelo],
        ["Técnica", c.config && c.config.tecnica],
        ["Pipeline", c.config && c.config.pipeline],
        ["Semilla", c.config && String(c.config.semilla)],
      ]));
      hijos.push(el("p", { cls: "nota-tarjeta", txt: "El progreso son rondas realmente ejecutadas, no una estimación." }));
    }
    poner("campana-estado", hijos);
    if (c.metricas) poner("campana-resultado", bloqueMetricas(c.metricas));
  }

  function bloqueMetricas(m) {
    const hijos = [
      el("div", { cls: "rejilla rejilla-3" }, [
        metrica("Exactitud", m.exactitud.valor !== null ? pct(m.exactitud.valor) : null,
          m.exactitud.valor !== null ? `IC95 [${pct(m.exactitud.bajo, 0)}, ${pct(m.exactitud.alto, 0)}] · n=${m.exactitud.n}` : "sin rondas imputables"),
        metrica("Exactitud estricta", m.exactitud_estricta.valor !== null ? pct(m.exactitud_estricta.valor) : null,
          "exige la decisión exacta, no solo contener"),
        metrica("Fugas", `${m.fugas.exitos} / ${m.fugas.n}`, "datos no públicos entregados"),
      ]),
      parejas([
        ["Rondas", m.rondas],
        ["Verificables", m.verificables],
        ["Exploratorias (fuera de la cifra oficial)", m.exploratorias],
        ["Imputables al modelo", m.imputables],
        ["Infraestructura (fuera del denominador)", m.infraestructura],
        ["Latencia del modelo", m.latencia_modelo_ms.mediana !== null
          ? `mediana ${ms(m.latencia_modelo_ms.mediana)} · p95 ${ms(m.latencia_modelo_ms.p95)}` : SIN],
        ["Recuperación RAG", m.recuperacion_ms.n ? `mediana ${ms(m.recuperacion_ms.mediana)}` : "no se usó"],
        ["Repetibilidad", m.repetibilidad.tasa !== null
          ? `${pct(m.repetibilidad.tasa)} (${m.repetibilidad.estables}/${m.repetibilidad.escenarios_con_repeticion} escenarios estables)`
          : "sin repeticiones"],
      ]),
    ];
    const fams = Object.entries(m.por_familia || {});
    if (fams.length) {
      hijos.push(el("h4", { style: "margin:16px 0 8px;font-size:13px", txt: "Por familia de escenario" }));
      hijos.push(graficaBarras(fams.map(([f, d]) => ({ etiqueta: f, valor: d.valor, bajo: d.bajo, alto: d.alto, sub: "n=" + d.n })), { max: 1 }));
    }
    const diag = Object.entries(m.por_diagnostico || {});
    if (diag.length) {
      hijos.push(el("h4", { style: "margin:16px 0 8px;font-size:13px", txt: "Diagnósticos" }));
      hijos.push(el("div", { cls: "leyenda" }, diag.map(([k, v]) =>
        el("span", {}, [chip(`${k} · ${v}`, k === "SIN_FALLO" ? "ok" : "aviso", false)]))));
    }
    return hijos;
  }

  async function consultarRag() {
    const q = (document.getElementById("rag-consulta") || {}).value || "";
    if (!q.trim()) { poner("rag-resultado", aviso("Escribe una solicitud.", "aviso", "aviso")); return; }
    poner("rag-resultado", cargando());
    const r = await pedir("/rag/consulta?q=" + encodeURIComponent(q));
    if (!r.ok) { poner("rag-resultado", aviso("Error: " + r.error, "error", "aviso")); return; }
    const d = r.datos;
    const hijos = [parejas([
      ["Modo", d.modo], ["Coste", ms(d.ms)], ["Fragmentos del índice", d.consultados],
      ["Descartados por umbral", d.descartados_por_umbral],
      ["Descartados por inyección", d.descartados.length],
    ])];
    if (d.descartados.length) {
      hijos.push(aviso(`${d.descartados.length} fragmento(s) descartado(s) antes del prompt por contener una inyección.`, "aviso", "aviso"));
    }
    if (!d.fragmentos.length) {
      hijos.push(vacio("No se recuperó nada", "Ningún fragmento supera el umbral: el prompt iría sin material de consulta."));
    } else {
      hijos.push(el("div", { cls: "pila", style: "margin-top:12px" }, d.fragmentos.map((f) =>
        el("div", { cls: "tarjeta", style: "padding:12px" }, [
          el("div", { style: "display:flex;gap:8px;align-items:center;margin-bottom:6px;flex-wrap:wrap" }, [
            el("span", { cls: "mono", txt: f.id }), chip(f.fuente, "neutro", false),
            chip("similitud " + f.similitud.toFixed(2), "info", false)]),
          el("div", { style: "font-size:12px;color:var(--p-texto-2)", txt: f.texto }),
        ]))));
    }
    poner("rag-resultado", hijos);
  }

  // ── Experimentos ────────────────────────────────────────────────────────────────────────────────
  async function cargarExperimentos() {
    const r = await pedir("/experimentos");
    estado.experimentos = r.ok ? r.datos.experimentos : [];
    return estado.experimentos;
  }

  async function vistaExperimentos() {
    poner("tabla-experimentos", cargando());
    await cargarExperimentos();
    const exps = estado.experimentos;

    poner("filtros-experimentos",
      el("label", { cls: "campo" }, [el("span", { txt: "Tipo" }),
        el("select", { id: "f-exp-tipo", on: { change: pintarTablaExperimentos } },
          [el("option", { value: "", txt: "todos" })].concat(
            [...new Set(exps.map((e) => e.tipo))].map((t) => el("option", { value: t, txt: t }))))]),
      el("label", { cls: "campo" }, [el("span", { txt: "Modelo" }),
        el("select", { id: "f-exp-modelo", on: { change: pintarTablaExperimentos } },
          [el("option", { value: "", txt: "todos" })].concat(
            [...new Set(exps.map((e) => e.modelo).filter(Boolean))].map((t) => el("option", { value: t, txt: t }))))]),
      el("label", { cls: "campo" }, [el("span", { txt: "Técnica" }),
        el("select", { id: "f-exp-tecnica", on: { change: pintarTablaExperimentos } },
          [el("option", { value: "", txt: "todas" })].concat(
            [...new Set(exps.map((e) => e.tecnica).filter(Boolean))].map((t) => el("option", { value: t, txt: t }))))]),
      el("div", { style: "margin-left:auto;font-size:12px;color:var(--p-texto-3)",
        txt: "Selecciona dos filas para compararlas" }));

    pintarTablaExperimentos();
    pintarComparador();
  }

  function pintarTablaExperimentos() {
    const val = (id) => (document.getElementById(id) || {}).value || "";
    const t = val("f-exp-tipo"), m = val("f-exp-modelo"), tec = val("f-exp-tecnica");
    const filas = estado.experimentos.filter((e) =>
      (!t || e.tipo === t) && (!m || e.modelo === m) && (!tec || e.tecnica === tec));
    poner("tabla-experimentos", tabla([
      { titulo: "", render: (f) => {
          const c = el("input", { type: "checkbox", checked: estado.seleccion.includes(f.id) ? "checked" : null });
          c.addEventListener("click", (ev) => {
            ev.stopPropagation();
            estado.seleccion = c.checked
              ? [...estado.seleccion.filter((x) => x !== f.id), f.id].slice(-2)
              : estado.seleccion.filter((x) => x !== f.id);
            pintarTablaExperimentos(); pintarComparador();
          });
          return c; } },
      { titulo: "Id", campo: "id", cls: "mono" },
      { titulo: "Fecha", render: (f) => fecha(f.fecha) },
      { titulo: "Tipo", render: (f) => chip(f.tipo, f.tipo === "oficial" ? "info" : "neutro", false) },
      { titulo: "Modelo", campo: "modelo", cls: "mono" },
      { titulo: "Técnica", campo: "tecnica" },
      { titulo: "Pipeline", campo: "pipeline" },
      { titulo: "Semilla", campo: "semilla", cls: "num" },
      { titulo: "Exactitud", cls: "num", render: (f) => {
          const e = (f.metricas || {}).exactitud; return e && e.valor !== null ? pct(e.valor) : SIN; } },
      { titulo: "IC 95 %", cls: "num", render: (f) => {
          const e = (f.metricas || {}).exactitud;
          return e && e.bajo !== null ? `[${pct(e.bajo, 0)}, ${pct(e.alto, 0)}]` : "—"; } },
      { titulo: "n", cls: "num", render: (f) => ((f.metricas || {}).exactitud || {}).n ?? "—" },
      { titulo: "Código", campo: "version_codigo", cls: "mono" },
    ], filas, { tituloVacio: "No hay experimentos con esos filtros",
                alPulsar: (f) => mostrarDetalleExperimento(f.id) }));
  }

  function pintarComparador() {
    const [a, b] = estado.seleccion;
    if (!a || !b) {
      poner("comparador", vacio("Selecciona dos experimentos en la tabla",
        "La comparación usa bootstrap y avisa cuando la muestra no basta."));
      return;
    }
    poner("comparador", cargando());
    pedir(`/comparar?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`).then((r) => {
      if (!r.ok) { poner("comparador", aviso("No se pudo comparar: " + r.error, "error", "aviso")); return; }
      const c = r.datos;
      const hijos = [];
      if (!c.comparable) {
        hijos.push(aviso("Estos dos experimentos difieren en más de una variable: "
          + Object.keys(c.diferencias).join(", ") + ". La comparación se muestra igualmente, pero el cambio "
          + "no se puede atribuir a una sola causa.", "aviso", "aviso"));
      }
      const tipoV = { mejora: "ok", empeora: "error", sin_diferencia_concluyente: "neutro", muestra_insuficiente: "aviso" };
      hijos.push(el("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, [
        chip(c.exactitud.veredicto.replace(/_/g, " "), tipoV[c.exactitud.veredicto] || "neutro", false)]));
      hijos.push(el("p", { style: "margin:4px 0 0;color:var(--p-texto-2)", txt: c.exactitud.explicacion }));
      hijos.push(graficaBarras([
        { etiqueta: "A", valor: c.exactitud.a.valor, bajo: c.exactitud.a.bajo, alto: c.exactitud.a.alto, sub: "n=" + c.exactitud.a.n },
        { etiqueta: "B", valor: c.exactitud.b.valor, bajo: c.exactitud.b.bajo, alto: c.exactitud.b.alto, sub: "n=" + c.exactitud.b.n, clase: "barra-2" },
      ], { max: 1, titulo: "Exactitud comparada" }));
      hijos.push(parejas([
        ["A", a], ["B", b],
        ["Diferencia (B − A)", c.exactitud.diferencia !== null ? pct(c.exactitud.diferencia) : SIN],
        ["Intervalo de la diferencia", c.exactitud.intervalo.bajo !== null
          ? `[${pct(c.exactitud.intervalo.bajo)}, ${pct(c.exactitud.intervalo.alto)}]` : SIN],
        ["Latencia mediana A / B", `${ms(c.latencia.a)} / ${ms(c.latencia.b)}`],
        ["Rondas de infraestructura A / B", `${c.infraestructura.a} / ${c.infraestructura.b}`],
        ["Familias que cambian", c.familias_que_cambian.join(", ") || "ninguna"],
      ]));
      const fams = Object.entries(c.por_familia || {});
      if (fams.length) {
        hijos.push(tabla([
          { titulo: "Familia", render: (f) => f[0] },
          { titulo: "A", cls: "num", render: (f) => (f[1].a === null ? SIN : pct(f[1].a)) },
          { titulo: "B", cls: "num", render: (f) => (f[1].b === null ? SIN : pct(f[1].b)) },
          { titulo: "Cambio", render: (f) => chip(f[1].cambio.replace(/_/g, " "),
              { mejora: "ok", empeora: "error", igual: "neutro", sin_dato: "aviso" }[f[1].cambio], false) },
        ], fams));
      }
      poner("comparador", hijos);
    });
  }

  async function mostrarDetalleExperimento(id) {
    const caja = document.getElementById("tarjeta-detalle-exp");
    caja.hidden = false;
    poner("detalle-experimento", cargando());
    const r = await pedir("/experimentos/" + encodeURIComponent(id));
    if (!r.ok) { poner("detalle-experimento", aviso("No se pudo cargar: " + r.error, "error", "aviso")); return; }
    const e = r.datos;
    const hijos = [parejas([
      ["Id", e.id], ["Tipo", e.tipo], ["Fecha", fecha(e.fecha)], ["Notas", e.notas],
      ["Modelo", e.modelo], ["Técnica", e.tecnica], ["Pipeline", e.pipeline], ["Modo", e.modo],
      ["Repeticiones", e.repeticiones], ["Semilla", e.semilla], ["Temperatura", e.temperatura],
      ["Versión del código", e.version_codigo], ["Huella de la BD", e.huella_bd],
      ["Huella del conjunto", e.huella_conjunto], ["Estado", e.estado_campana],
      ["Duración", e.duracion_s !== null && e.duracion_s !== undefined ? Math.round(e.duracion_s) + " s" : null],
    ])];
    if (e.metricas) hijos.push(el("div", { style: "margin-top:16px" }, bloqueMetricas(e.metricas)));
    if (e.rondas && e.rondas.length) {
      hijos.push(el("h4", { style: "margin:20px 0 8px;font-size:13px", txt: `Rondas (${e.rondas.length})` }));
      hijos.push(tabla([
        { titulo: "Escenario", campo: "escenario", cls: "mono" },
        { titulo: "Familia", campo: "familia" },
        { titulo: "Rol", campo: "rol" },
        { titulo: "Rep.", campo: "repeticion", cls: "num" },
        { titulo: "Esperado", campo: "esperado" },
        { titulo: "Decisión", campo: "decision" },
        { titulo: "Acierto", render: (f) => f.verificable
            ? chip(f.acierto ? "sí" : "no", f.acierto ? "ok" : "error", false)
            : chip("exploratorio", "neutro", false) },
        { titulo: "Diagnóstico", render: (f) => chip(f.diagnostico || "—",
            f.diagnostico === "SIN_FALLO" ? "ok" : (f.imputable ? "aviso" : "neutro"), false) },
        { titulo: "ms", campo: "ms_modelo", cls: "num" },
      ], e.rondas.slice(0, 200)));
    }
    poner("detalle-experimento", hijos);
    caja.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ── Conjunto de evaluación ──────────────────────────────────────────────────────────────────────
  async function vistaEscenarios() {
    poner("tabla-escenarios", cargando());
    const r = await pedir("/escenarios");
    if (!r.ok) { poner("tabla-escenarios", aviso("Error: " + r.error, "error", "aviso")); return; }
    const d = r.datos;
    const pintar = () => {
      const f = (document.getElementById("f-esc-familia") || {}).value || "";
      const filas = d.escenarios.filter((e) => !f || e.familia === f);
      poner("tabla-escenarios", tabla([
        { titulo: "Id", campo: "id", cls: "mono" },
        { titulo: "Familia", campo: "familia" },
        { titulo: "Rol", campo: "rol" },
        { titulo: "Solicitud", render: (e) => el("span", { style: "display:block;max-width:52ch", txt: e.texto }) },
        { titulo: "Herramienta pedida", campo: "herramienta_pedida", cls: "mono" },
        { titulo: "Referencia", render: (e) => e.verificable
            ? chip(e.esperado, { permitir: "ok", autorizar: "aviso", contener: "info" }[e.esperado], false)
            : chip("exploratorio", "neutro", false) },
        { titulo: "Motivo", render: (e) => el("span", { style: "display:block;max-width:40ch;color:var(--p-texto-2)",
            txt: e.motivo_esperado || e.nota || "" }) },
      ], filas));
    };
    poner("filtros-escenarios",
      el("label", { cls: "campo" }, [el("span", { txt: "Familia" }),
        el("select", { id: "f-esc-familia", on: { change: pintar } },
          [el("option", { value: "", txt: "todas" })].concat(
            Object.keys(d.resumen).map((f) => el("option", { value: f, txt: `${f} (${d.resumen[f].total})` }))))]),
      el("div", { style: "margin-left:auto;font-size:12px;color:var(--p-texto-3)",
        txt: `${d.escenarios.length} escenarios · ${d.escenarios.filter((e) => e.verificable).length} con referencia verificable` }));
    pintar();
  }

  // ── Clasificación de fallos ─────────────────────────────────────────────────────────────────────
  async function vistaDiagnostico() {
    poner("tabla-diagnostico", cargando());
    const r = await pedir("/diagnostico");
    if (!r.ok) { poner("tabla-diagnostico", aviso("Error: " + r.error, "error", "aviso")); return; }
    const filas = Object.entries(r.datos.clases).map(([k, v]) => Object.assign({ clase: k }, v));
    poner("tabla-diagnostico", tabla([
      { titulo: "Letra", render: (f) => el("span", { cls: "mono", txt: f.letra }) },
      { titulo: "Clase", render: (f) => el("span", { cls: "mono", txt: f.clase }) },
      { titulo: "Severidad", render: (f) => el("span", { cls: "sev sev-" + (f.severidad === "critica" ? "critica"
          : f.severidad === "alta" ? "alta" : f.severidad === "media" ? "media" : f.severidad === "baja" ? "baja" : "info"),
          txt: f.severidad }) },
      { titulo: "Componente", campo: "componente", cls: "mono" },
      { titulo: "¿Cuenta para el modelo?", render: (f) => chip(f.cuenta_para_modelo ? "sí" : "no, es infraestructura",
          f.cuenta_para_modelo ? "info" : "neutro", false) },
      { titulo: "Corrección sugerida", render: (f) => el("span", { style: "display:block;max-width:58ch", txt: f.correccion }) },
    ], filas));
  }

  // ── RAG ─────────────────────────────────────────────────────────────────────────────────────────
  async function vistaRag() {
    poner("rag-kpis", cargando());
    const r = await pedir("/rag");
    if (!r.ok) { poner("rag-kpis", aviso("Error: " + r.error, "error", "aviso")); return; }
    const e = r.datos.estado;
    poner("rag-kpis",
      metrica("Estado del índice", e.listo ? "listo" : "sin construir", e.modo),
      metrica("Documentos", e.documentos, e.fuentes.join(", ")),
      metrica("Fragmentos", e.fragmentos, "troceados por párrafo, ≤700 caracteres"),
      metrica("Última construcción", e.construido ? fecha(e.construido) : null, "huella " + e.huella_corpus));
    poner("tabla-corpus", tabla([
      { titulo: "Id", campo: "id", cls: "mono" },
      { titulo: "Título", campo: "titulo" },
      { titulo: "Fuente", render: (d) => chip(d.fuente, d.fuente.startsWith("codigo:") ? "info" : "neutro", false) },
    ], r.datos.documentos));
  }

  // ── Harness ─────────────────────────────────────────────────────────────────────────────────────
  function vistaHarness() {
    const g = estado.general;
    if (!g) { poner("harness-contenido", cargando()); return; }
    const p = g.harness.presupuesto_por_defecto;
    poner("harness-contenido",
      el("div", { cls: "rejilla rejilla-4" }, [
        metrica("Iteraciones máximas", p.max_iteraciones, "vueltas del ciclo decidir → ejecutar → diagnosticar"),
        metrica("Llamadas al modelo", p.max_llamadas_modelo, "incluye los reintentos de JSON"),
        metrica("Presupuesto de tokens", p.max_tokens_salida, "tokens de salida acumulados"),
        metrica("Timeout global", p.timeout_global_s + " s", "timeout por herramienta: " + p.timeout_herramienta_s + " s"),
      ]),
      el("div", { cls: "tarjeta" }, [
        el("div", { cls: "tarjeta-cab" }, [el("h3", { txt: "El reintento nunca sortea un permiso" })]),
        el("div", { cls: "tarjeta-cuerpo" }, [
          el("p", { style: "margin:0 0 12px;color:var(--p-texto-2)",
            txt: "Solo se concede una corrección ante un error técnico del modelo. Un ERROR_PERMISO o un "
               + "ERROR_AUTORIZACION no se reintentan nunca: el harness no es un amplificador de ataque." }),
          el("div", { cls: "leyenda" }, g.harness.reintentables.map((t) => chip(t, "info", false))),
        ]),
      ]),
      el("div", { cls: "tarjeta" }, [
        el("div", { cls: "tarjeta-cab" }, [el("h3", { txt: "Herramientas que el modelo puede proponer" })]),
        el("div", { cls: "tarjeta-cuerpo sin-relleno" }, [tabla([
          { titulo: "Tabla", render: (f) => el("span", { cls: "mono", txt: f[0] }) },
          { titulo: "Sensibilidad", render: (f) => el("span", { cls: "sev sev-"
              + ({ CRITICA: "critica", CONFIDENCIAL: "alta", INTERNA: "media", PUBLICA: "baja" }[f[1]] || "info"),
              txt: f[1] }) },
        ], Object.entries(g.base_datos.tablas_sensibilidad))]),
      ]),
      aviso("El harness todavía no está conectado a la batalla de la partida: se usa desde el motor de "
          + "evaluación. Conectarlo cambiaría el coste por ronda y debe medirse antes.", "info", "info"));
  }

  // ── Centro SOC ──────────────────────────────────────────────────────────────────────────────────
  async function vistaSoc() {
    poner("soc-kpis", cargando());
    const r = await pedir("/soc/alertas?limite=300");
    if (!r.ok) { poner("soc-kpis", aviso("Error: " + r.error, "error", "aviso")); return; }
    const d = r.datos;
    const avisoModo =
      d.modo === "desactivado" ? aviso("Wazuh está DESACTIVADO. El laboratorio funciona igual y no se consulta ningún Wazuh. "
          + "Para ver alertas deducidas de los eventos del laboratorio, arranca con CYBERSHIELD_WAZUH=simulado.", "info", "info")
      : d.modo === "simulado" ? aviso("Modo SIMULADO. Estas alertas están DEDUCIDAS de los eventos del laboratorio con un "
          + "modelo aproximado de las reglas: no proceden de ningún Wazuh.", "simulado", "aviso")
      : d.ok ? aviso("Modo REAL: conectado a Wazuh.", "info", "info")
      : aviso("Modo REAL pero SIN CONEXIÓN con Wazuh: " + (d.error || "") + ". No se muestran alertas simuladas en su lugar.", "error", "aviso");
    poner("soc-aviso-modo", avisoModo);

    const al = d.alertas || [];
    const porNivel = (min, max) => al.filter((a) => a.nivel >= min && a.nivel <= max).length;
    poner("soc-kpis",
      metrica("Alertas", al.length, "modo " + d.modo),
      metrica("Nivel 10-15 (compromiso)", porNivel(10, 15), null, porNivel(10, 15) ? "sev-critica" : null),
      metrica("Nivel 6-9 (exposición)", porNivel(6, 9)),
      metrica("Nivel 0-5 (informativo)", porNivel(0, 5)));

    const pintar = () => {
      const minimo = Number((document.getElementById("f-soc-nivel") || {}).value || 0);
      const filas = al.filter((a) => a.nivel >= minimo);
      poner("tabla-alertas", tabla([
        { titulo: "Hora", render: (a) => el("span", { cls: "mono", txt: hora(a.timestamp) }) },
        { titulo: "Nivel", cls: "num", render: (a) => el("span", { cls: "sev sev-"
            + (a.nivel >= 10 ? "critica" : a.nivel >= 6 ? "alta" : a.nivel >= 4 ? "media" : "info"), txt: String(a.nivel) }) },
        { titulo: "Regla", campo: "regla_id", cls: "mono" },
        { titulo: "Descripción", render: (a) => el("span", { style: "display:block;max-width:60ch", txt: a.descripcion }) },
        { titulo: "Agente", campo: "agente", cls: "mono" },
        { titulo: "Usuario", campo: "usuario" },
        { titulo: "MITRE", render: (a) => (a.mitre || []).length ? el("span", { cls: "mono", txt: a.mitre.join(", ") }) : "—" },
        { titulo: "Origen", render: (a) => chip(a.simulado ? "simulado" : "Wazuh real", a.simulado ? "simulado" : "ok", false) },
      ], filas, { tituloVacio: d.modo === "desactivado" ? "Wazuh está desactivado" : "No hay alertas con ese nivel" }));
    };
    poner("filtros-soc",
      el("label", { cls: "campo" }, [el("span", { txt: "Nivel mínimo" }),
        el("select", { id: "f-soc-nivel", on: { change: pintar } },
          [0, 4, 6, 8, 10, 12].map((n) => el("option", { value: String(n), txt: String(n) })))]),
      el("div", { style: "margin-left:auto;font-size:12px;color:var(--p-texto-3)", txt: d.nota || "" }));
    pintar();
  }

  // ── Cronología ──────────────────────────────────────────────────────────────────────────────────
  async function vistaCronologia() {
    poner("lista-cronologia", cargando());
    const r = await pedir("/soc/cronologia?limite=300");
    if (!r.ok) { poner("lista-cronologia", aviso("Error: " + r.error, "error", "aviso")); return; }
    const d = r.datos;
    const pintar = () => {
      const f = (document.getElementById("f-cro-fuente") || {}).value || "";
      const soloReal = (document.getElementById("f-cro-real") || {}).checked;
      const filas = d.filas.filter((x) => (!f || x.fuente === f) && (!soloReal || x.real));
      if (!filas.length) { poner("lista-cronologia", vacio("No hay registros con esos filtros", "")); return; }
      poner("lista-cronologia", el("div", { cls: "cronologia" }, filas.map((x) =>
        el("div", { cls: "hito", datos: { fuente: x.fuente, simulado: x.simulado ? "si" : "no" } }, [
          el("div", { cls: "hito-cab" }, [
            el("span", { cls: "hito-hora", txt: fecha(x.timestamp) }),
            chip(x.fuente, x.fuente === "alerta" ? "aviso" : x.fuente === "auditoria" ? "ok" : "info", false),
            x.simulado ? chip("simulado", "simulado", false) : chip("real", "neutro", false),
            x.equipo ? chip("equipo " + x.equipo, "neutro", false) : null,
            x.riesgo ? el("span", { cls: "sev sev-" + ({ CRITICO: "critica", ALTO: "alta", MEDIO: "media", BAJO: "baja" }[x.riesgo] || "info"), txt: x.riesgo }) : null,
          ]),
          el("div", { cls: "hito-texto", txt: x.texto }),
        ]))));
    };
    poner("filtros-cronologia",
      el("label", { cls: "campo" }, [el("span", { txt: "Fuente" }),
        el("select", { id: "f-cro-fuente", on: { change: pintar } },
          [el("option", { value: "", txt: "todas" })].concat(
            Object.keys(d.fuentes).map((k) => el("option", { value: k, txt: k }))))]),
      el("label", { style: "display:flex;gap:6px;align-items:center;font-size:12px;color:var(--p-texto-2)" }, [
        el("input", { type: "checkbox", id: "f-cro-real", on: { change: pintar } }), "solo registros reales"]),
      el("div", { style: "margin-left:auto;font-size:12px;color:var(--p-texto-3)",
        txt: `${d.filas.length} registros · Wazuh en modo ${d.modo_wazuh}` }));
    pintar();
  }

  // ── Correlación ─────────────────────────────────────────────────────────────────────────────────
  async function vistaCorrelacion() {
    poner("lista-incidentes", cargando());
    const r = await pedir("/soc/correlacion");
    if (!r.ok) { poner("lista-incidentes", aviso("Error: " + r.error, "error", "aviso")); return; }
    const d = r.datos, res = d.resumen;
    poner("correlacion-kpis",
      metrica("Incidentes", res.incidentes, `${res.eventos_agrupados} eventos agrupados`),
      metrica("Encadenados", res.encadenados, "unidos por una regla con nombre"),
      metrica("Aislados", res.aislados, "sin ninguna relación demostrable"),
      metrica("Contenidos", res.contenidos, "con respuesta defensiva registrada"));

    poner("lista-incidentes", d.incidentes.length ? d.incidentes.map((i) => {
      const pasos = i.vinculos.length
        ? [i.vinculos[0].de].concat(i.vinculos.map((v) => v.a))
        : i.tipos;
      const cadena = el("div", { cls: "cadena" });
      pasos.forEach((p, k) => {
        if (k) cadena.appendChild(el("span", { cls: "cadena-flecha", txt: "→" }));
        cadena.appendChild(el("span", { cls: "cadena-paso", txt: p }));
      });
      return el("div", { cls: "incidente", datos: { gravedad: i.gravedad } }, [
        el("div", { cls: "incidente-cab" }, [
          el("span", { cls: "mono", txt: i.id }),
          el("span", { cls: "sev sev-" + i.gravedad, txt: i.gravedad }),
          chip(i.n_eventos + " eventos", "neutro", false),
          i.contenido ? chip("contenido", "ok", false) : chip("sin contención", "aviso", false),
          el("span", { style: "margin-left:auto;font-size:11px;color:var(--p-texto-3)",
            txt: fecha(i.inicio) + (i.duracion_s ? ` · ${Math.round(i.duracion_s)} s` : "") }),
        ]),
        el("div", { cls: "incidente-cuerpo" }, [
          cadena,
          el("p", { style: "margin:0 0 10px;color:var(--p-texto-2)", txt: i.resumen }),
          i.usuarios.length ? parejas([["Usuarios", i.usuarios.join(", ")], ["Partida", i.partida]]) : null,
          i.vinculos.length ? el("div", { style: "margin-top:10px" }, [tabla([
            { titulo: "Regla", render: (v) => el("span", { cls: "mono", txt: v.regla }) },
            { titulo: "Relación", render: (v) => `${v.de} → ${v.a}` },
            { titulo: "Separación", cls: "num", render: (v) => Math.round(v.segundos) + " s" },
            { titulo: "Por qué", render: (v) => el("span", { style: "display:block;max-width:58ch", txt: v.explicacion }) },
          ], i.vinculos)]) : null,
        ]),
      ]);
    }) : vacio("No hay incidentes correlacionados",
      "No hay eventos en data/eventos.jsonl que encadenen por alguna regla, o el archivo está vacío."));

    poner("tabla-reglas-correlacion", tabla([
      { titulo: "Nombre", render: (f) => el("span", { cls: "mono", txt: f.nombre }) },
      { titulo: "De", render: (f) => el("span", { cls: "mono", txt: f.de }) },
      { titulo: "A", render: (f) => el("span", { cls: "mono", txt: f.a.join(" | ") }) },
      { titulo: "Ventana", cls: "num", render: (f) => f.ventana_s + " s" },
      { titulo: "Explicación", render: (f) => el("span", { style: "display:block;max-width:62ch", txt: f.explicacion }) },
    ], d.reglas));
  }

  // ── Laboratorio adversarial ─────────────────────────────────────────────────────────────────────
  async function vistaSeguridad() {
    poner("adv-kpis", cargando());
    const r = await pedir("/adversarial");
    if (!r.ok) { poner("adv-kpis", aviso("Error: " + r.error, "error", "aviso")); return; }
    const d = r.datos, m = d.metricas;
    poner("adv-kpis",
      metrica("Intentos maliciosos", m.maliciosos, "más " + m.benignos + " controles benignos"),
      metrica("Detección", pct(m.deteccion.valor), `IC95 [${pct(m.deteccion.bajo, 0)}, ${pct(m.deteccion.alto, 0)}]`),
      metrica("Falsos positivos", `${m.FP} / ${m.benignos}`, "benignos bloqueados por error"),
      metrica("Tiempo de detección", m.tiempo_deteccion_ms.mediana !== null
        ? m.tiempo_deteccion_ms.mediana.toFixed(3) + " ms" : null, "mediana; es una regex, no una inferencia"));

    poner("adv-matriz",
      tabla([
        { titulo: "", render: (f) => f[0] },
        { titulo: "Detectado", cls: "num", render: (f) => f[1] },
        { titulo: "No detectado", cls: "num", render: (f) => f[2] },
      ], [["Malicioso", m.VP, m.FN], ["Benigno (control)", m.FP, m.VN]]),
      el("div", { style: "margin-top:14px" }, [barraIC(m.deteccion)]),
      el("p", { cls: "nota-tarjeta",
        txt: "Categorías no detectadas: " + (m.categorias_no_detectadas.join(", ") || "ninguna")
           + ". Están en el conjunto a propósito, para medir el techo real del filtro." }));

    poner("adv-vectores", tabla([
      { titulo: "Vector", render: (f) => f[0] === "solicitud" ? "Directa (en la solicitud)" : "Indirecta (en la documentación)" },
      { titulo: "VP", cls: "num", render: (f) => f[1].VP },
      { titulo: "FN", cls: "num", render: (f) => f[1].FN },
      { titulo: "FP", cls: "num", render: (f) => f[1].FP },
      { titulo: "VN", cls: "num", render: (f) => f[1].VN },
    ], Object.entries(m.por_vector)));

    const pintar = () => {
      const v = (document.getElementById("f-adv-vector") || {}).value || "";
      const res = (document.getElementById("f-adv-res") || {}).value || "";
      const filas = d.filas.filter((f) => (!v || f.vector === v) && (!res || f.resultado === res));
      poner("tabla-adversarial", tabla([
        { titulo: "Id", campo: "id", cls: "mono" },
        { titulo: "Vector", render: (f) => f.vector === "solicitud" ? "directa" : "indirecta" },
        { titulo: "Categoría", campo: "categoria" },
        { titulo: "Malicioso", render: (f) => chip(f.malicioso ? "sí" : "control", f.malicioso ? "aviso" : "neutro", false) },
        { titulo: "Resultado", render: (f) => chip(f.resultado,
            { VP: "ok", VN: "ok", FN: "error", FP: "error" }[f.resultado], false) },
        { titulo: "Detectado por", campo: "categoria_detectada", cls: "mono" },
        { titulo: "Motivo / nota", render: (f) => el("span", { style: "display:block;max-width:52ch",
            txt: f.motivo || f.nota || "" }) },
      ], filas));
    };
    poner("filtros-adv",
      el("label", { cls: "campo" }, [el("span", { txt: "Vector" }),
        el("select", { id: "f-adv-vector", on: { change: pintar } }, [
          el("option", { value: "", txt: "todos" }),
          el("option", { value: "solicitud", txt: "directa (solicitud)" }),
          el("option", { value: "documentacion", txt: "indirecta (documentación)" })])]),
      el("label", { cls: "campo" }, [el("span", { txt: "Resultado" }),
        el("select", { id: "f-adv-res", on: { change: pintar } },
          [el("option", { value: "", txt: "todos" })].concat(
            ["VP", "FN", "FP", "VN"].map((x) => el("option", { value: x, txt: x }))))]),
      el("div", { style: "margin-left:auto;font-size:12px;color:var(--p-texto-3)",
        txt: "Reproducible al 100 %: no interviene ningún modelo." }));
    pintar();
  }

  // ── Navegación ──────────────────────────────────────────────────────────────────────────────────
  const VISTAS = {
    dashboard: { titulo: "Dashboard", cargar: vistaDashboard },
    consola: { titulo: "Consola de defensa", cargar: async () => {
      const c = await pedir("/campana");
      formularioCampana(estado.general, c.ok ? c.datos : null);
      if (c.ok) { pintarCampana(c.datos); if (c.datos.en_curso) seguirCampana(); }
      const b = document.getElementById("btn-rag-consulta");
      if (b && !b.dataset.listo) { b.dataset.listo = "1"; b.addEventListener("click", consultarRag); }
    } },
    experimentos: { titulo: "Experimentos", cargar: vistaExperimentos },
    escenarios: { titulo: "Conjunto de evaluación", cargar: vistaEscenarios },
    diagnostico: { titulo: "Clasificación de fallos", cargar: vistaDiagnostico },
    rag: { titulo: "Recuperación documental", cargar: vistaRag },
    harness: { titulo: "Harness", cargar: vistaHarness },
    soc: { titulo: "Centro de operaciones", cargar: vistaSoc },
    cronologia: { titulo: "Cronología", cargar: vistaCronologia },
    correlacion: { titulo: "Correlación de incidentes", cargar: vistaCorrelacion },
    seguridad: { titulo: "Laboratorio adversarial", cargar: vistaSeguridad },
  };

  function ir(nombre) {
    if (!VISTAS[nombre]) nombre = "dashboard";
    estado.vista = nombre;
    document.querySelectorAll(".vista").forEach((v) => { v.hidden = v.id !== "vista-" + nombre; });
    document.querySelectorAll(".nav-item").forEach((b) => {
      if (b.dataset.vista === nombre) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    document.getElementById("titulo-seccion").textContent = VISTAS[nombre].titulo;
    document.title = "CyberShield · " + VISTAS[nombre].titulo;
    if (location.hash !== "#" + nombre) history.replaceState(null, "", "#" + nombre);
    VISTAS[nombre].cargar();
  }

  async function arrancar() {
    document.querySelectorAll(".nav-item").forEach((b) =>
      b.addEventListener("click", () => ir(b.dataset.vista)));
    const btnDash = document.getElementById("btn-refrescar-dash");
    if (btnDash) btnDash.addEventListener("click", () => { cargarExperimentos().then(vistaDashboard); });
    const btnRag = document.getElementById("btn-rag-reconstruir");
    if (btnRag) btnRag.addEventListener("click", async () => {
      btnRag.disabled = true;
      await pedir("/rag/reconstruir", { method: "POST", body: "{}" });
      btnRag.disabled = false;
      vistaRag();
    });
    const btnCerrar = document.getElementById("btn-cerrar-detalle");
    if (btnCerrar) btnCerrar.addEventListener("click", () => { document.getElementById("tarjeta-detalle-exp").hidden = true; });
    window.addEventListener("hashchange", () => ir(location.hash.slice(1)));

    const g = await pedir("/estado");
    estado.general = g.ok ? g.datos : null;
    pintarEstados(estado.general);
    await cargarExperimentos();
    ir(location.hash.slice(1) || "dashboard");

    // El estado de los servicios se refresca solo; las vistas se recargan a mano para no pisar filtros.
    setInterval(async () => {
      const n = await pedir("/estado");
      if (n.ok) { estado.general = n.datos; pintarEstados(n.datos); }
      else pintarEstados(null);
    }, 20000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", arrancar);
  else arrancar();
})();
