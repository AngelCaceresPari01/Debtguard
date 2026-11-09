"use strict";
// Todo texto que viene de la carpeta (rutas, mensajes de commit, autores) se inserta como texto, nunca como HTML.
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const estado = { info: null, resultado: null, trabajo: null, etiquetas: {}, abierto: null, filtros: { fuente: null, familia: "", severidad: "", texto: "" } };
const FAMILIAS = { complejidad: ["Complejidad", "c-s1"], regla: ["Reglas", "c-s2"], clon: ["Clones", "c-s3"], satd: ["SATD", "c-s4"] };
const fmt = (x, d = 2) => (x === null || x === undefined ? "—" : Number(x).toLocaleString("es", { maximumFractionDigits: d }));

function el(tag, attrs = {}, ...hijos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "on") Object.entries(v).forEach(([ev, fn]) => e.addEventListener(ev, fn));
    else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v === true ? "" : v);
  }
  for (const h of hijos.flat()) if (h !== null && h !== undefined && h !== false) e.append(h.nodeType ? h : String(h));
  return e;
}
function svg(tag, attrs = {}, ...hijos) {
  const e = document.createElementNS(NS, tag);
  Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
  hijos.forEach((h) => e.append(h));
  return e;
}
async function api(url, cuerpo) {
  const r = await fetch(url, cuerpo === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `Error ${r.status}`);
  return d;
}
function mostrarError(m) { $("error").textContent = m || ""; $("error").hidden = !m; }

// ---------- Elegir carpeta ----------
async function elegirCarpeta(ruta) {
  $("ruta").value = ruta;
  mostrarError("");
  try {
    estado.info = await api(`/api/inspeccionar?ruta=${encodeURIComponent(ruta)}`);
    pintarInfo();
  } catch (e) {
    estado.info = null; $("info").hidden = true; $("opciones").hidden = true;
    mostrarError(e.message);
  }
}
function pintarInfo() {
  const i = estado.info, c = $("info");
  c.replaceChildren();
  const partes = [];
  if (i.es_git) {
    partes.push(`Repositorio git en ${i.raiz}, rama ${i.rama}, ${fmt(i.commits, 0)} commits sin contar merges.`);
    if (i.sin_confirmar) partes.push("Hay cambios de Python sin confirmar.");
  } else partes.push("Esta carpeta no es un repositorio git, así que solo se puede medir el código actual.");
  partes.push(`${fmt(i.python_produccion, 0)} archivos Python de producción de ${fmt(i.archivos, 0)} archivos.`);
  c.append(el("p", {}, partes.join(" ")));
  if (!i.python) c.append(el("p", {}, "No hay archivos Python: por ahora las métricas solo cubren Python."));
  if (i.repos_internos?.length) {
    c.append(el("p", {}, "Repositorios git encontrados dentro:"),
      el("ul", {}, i.repos_internos.map((r) => el("li", {}, el("button", { type: "button", on: { click: () => elegirCarpeta(r) } }, r)))));
  }
  c.hidden = false;
  $("opciones").hidden = false;
  $("op-historial").disabled = !i.es_git; $("op-historial").checked = i.es_git; $("op-n").disabled = !i.es_git;
  $("op-sucio").disabled = !i.es_git; $("op-sucio").checked = Boolean(i.sin_confirmar);
}
async function abrirNavegador() {
  const raices = await api("/api/raices");
  const a = $("dlg-accesos");
  a.replaceChildren(...[...raices.accesos.map((x) => [x.nombre, x.ruta]), ...raices.unidades.map((u) => [u, u])]
    .map(([n, r]) => el("button", { type: "button", on: { click: () => navegar(r) } }, n)));
  $("dlg-carpeta").showModal();
  await navegar($("ruta").value || raices.accesos[0]?.ruta || raices.unidades[0]);
}
let rutaDialogo = null, padreDialogo = null;
async function navegar(ruta) {
  try {
    const d = await api(`/api/explorar?ruta=${encodeURIComponent(ruta)}`);
    rutaDialogo = d.ruta; padreDialogo = d.padre;
    $("dlg-ruta").textContent = d.ruta + (d.git ? "  (repositorio git)" : "");
    $("dlg-subir").disabled = !d.padre;
    const lista = $("dlg-lista");
    lista.replaceChildren(...(d.carpetas.length ? d.carpetas.map((c) => el("li", {}, el("button", { type: "button", on: { click: () => navegar(c.ruta) } },
      el("span", {}, c.nombre), c.git ? el("span", { class: "insignia e-neutro" }, "git") : null))) : [el("li", { class: "nota" }, el("button", { type: "button", disabled: true }, "Sin subcarpetas"))]));
    lista.scrollTop = 0;
  } catch (e) { $("dlg-ruta").textContent = e.message; }
}

// ---------- Ejecutar ----------
async function analizar() {
  mostrarError("");
  const cuerpo = { ruta: estado.info.carpeta, codigo: $("op-codigo").checked, commits: $("op-historial").checked ? Number($("op-n").value) : 0, sin_confirmar: $("op-sucio").checked };
  try {
    const { id } = await api("/api/analizar", cuerpo);
    estado.trabajo = id; estado.etiquetas = {}; estado.abierto = null; estado.filtros.fuente = null;
    $("btn-analizar").disabled = true; $("progreso").hidden = false; $("btn-cancelar").disabled = false;
    seguir(id);
  } catch (e) { mostrarError(e.message); }
}
async function seguir(id) {
  let t;
  try { t = await api(`/api/trabajos/${id}`); } catch (e) { fin(); mostrarError(e.message); return; }
  const barra = document.querySelector(".barra");
  barra.classList.toggle("indeterminada", !t.total);
  $("barra-valor").style.width = t.total ? `${(100 * t.hecho) / t.total}%` : "";
  $("progreso-texto").textContent = t.total ? `${t.hecho} de ${t.total}. ${t.mensaje}` : t.mensaje;
  if (t.estado === "en_curso") { setTimeout(() => seguir(id), 500); return; }
  fin();
  if (t.estado === "error") mostrarError(`El análisis falló. ${t.mensaje}`);
  if (t.estado === "listo") { estado.resultado = t.resultado; pintarTodo(); }
}
function fin() { $("btn-analizar").disabled = false; $("progreso").hidden = true; }

// ---------- Componentes ----------
function tile(nombre, valor, ayuda, grande, explicar) {
  const clase = `tile${grande ? " grande" : ""}`;
  const partes = [el("span", { class: "nombre" }, nombre), el("span", { class: "valor" }, valor), ayuda ? el("span", { class: "ayuda" }, ayuda) : null];
  if (!explicar) return el("div", { class: clase }, partes);
  return el("button", { type: "button", class: clase, "aria-haspopup": "dialog", "aria-label": `${nombre}: ${valor}. Ver explicación`, on: { click: explicar } }, partes);
}
function insigniaVeredicto(v) {
  const m = { ACEPTAR: ["e-bien", "Aceptar"], ADVERTIR: ["e-aviso", "Advertir"], BLOQUEAR: ["e-critico", "Bloquear"], SIN_CALIBRAR: ["e-neutro", "Sin calibrar"] }[v] || ["e-neutro", v];
  return el("span", { class: `insignia ${m[0]}` }, el("i"), m[1]);
}
function tabla(cabeceras, filas) {
  return el("div", { class: "tabla-marco" }, el("table", {},
    el("thead", {}, el("tr", {}, cabeceras.map((c) => el("th", { scope: "col", class: c.num ? "num" : "" }, c.t || c)))),
    el("tbody", {}, filas)));
}
function td(v, clase) { return el("td", clase ? { class: clase } : {}, v); }
function verTooltip(ev, titulo, lineas) {
  const t = $("tooltip");
  t.replaceChildren(el("strong", {}, titulo), ...lineas.map((l) => el("div", {}, l)));
  t.hidden = false;
  const r = t.getBoundingClientRect();
  const x = ev.clientX ?? ev.target.getBoundingClientRect().left, y = ev.clientY ?? ev.target.getBoundingClientRect().top;
  t.style.left = `${Math.min(x + 14, innerWidth - r.width - 8)}px`;
  t.style.top = `${Math.max(8, y - r.height - 10)}px`;
}
const ocultarTooltip = () => { $("tooltip").hidden = true; };
const etiqueta = (c) => estado.etiquetas[c.sha] ?? c.origen;

function graficoCommits(commits) {
  const orden = [...commits].reverse();
  const A = 900, H = 240, izq = 44, abajo = 22, arriba = 10, ancho = A - izq - 6, alto = H - abajo - arriba;
  const max = Math.max(...orden.map((c) => c.deuda_horas), 0.25);
  const paso = [0.25, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000].find((p) => max / p <= 5) || Math.ceil(max / 5);
  const s = svg("svg", { class: "grafico", viewBox: `0 0 ${A} ${H}`, role: "img", "aria-label": "Horas de deuda introducidas por cada commit, del más antiguo al más reciente" });
  const y = (v) => arriba + alto - (v / (paso * Math.ceil(max / paso))) * alto;
  for (let v = 0; v <= paso * Math.ceil(max / paso) + 1e-9; v += paso) {
    s.append(svg("line", { x1: izq, x2: A - 6, y1: y(v), y2: y(v), class: "rejilla" }));
    const tx = svg("text", { x: izq - 6, y: y(v) + 4, "text-anchor": "end" }); tx.textContent = fmt(v); s.append(tx);
  }
  const celda = ancho / orden.length, b = Math.max(2, Math.min(celda - 2, 22));
  orden.forEach((c, i) => {
    const x = izq + i * celda + (celda - b) / 2, yy = y(c.deuda_horas), h = Math.max(c.deuda_horas > 0 ? 2 : 0, arriba + alto - yy);
    const r = Math.min(4, b / 2, h);
    const forma = `M${x},${arriba + alto} V${arriba + alto - h + r} Q${x},${arriba + alto - h} ${x + r},${arriba + alto - h} H${x + b - r} Q${x + b},${arriba + alto - h} ${x + b},${arriba + alto - h + r} V${arriba + alto} Z`;
    const zona = svg("rect", { x: izq + i * celda, y: arriba, width: celda, height: alto, class: "zona", tabindex: 0, "aria-label": `${c.corto}: ${fmt(c.deuda_horas)} horas` });
    const lineas = [`${fmt(c.deuda_horas)} h de deuda (${fmt(c.horas_kloc, 1)} h/KLOC)`, `${c.metricas.lineas_anadidas} líneas añadidas, ${c.hallazgos.length} hallazgos`, c.asunto];
    const titulo = `${c.corto} · ${c.fecha.slice(0, 10)}`;
    zona.addEventListener("mousemove", (e) => verTooltip(e, titulo, lineas));
    zona.addEventListener("focus", (e) => verTooltip(e, titulo, lineas));
    ["mouseleave", "blur"].forEach((ev) => zona.addEventListener(ev, ocultarTooltip));
    zona.addEventListener("click", () => { estado.abierto = c.sha; abrirPestana("commits"); pintarCommits(); });
    s.append(zona, svg("path", { d: forma, class: etiqueta(c) === "ia" ? "barra-s2" : "barra-s1", "pointer-events": "none" }));
  });
  [[0, orden[0]], [orden.length - 1, orden[orden.length - 1]]].forEach(([i, c], k) => {
    if (!c || (k && orden.length < 2)) return;
    const t = svg("text", { x: k ? A - 6 : izq, y: H - 6, "text-anchor": k ? "end" : "start" }); t.textContent = c.fecha.slice(0, 10); s.append(t);
  });
  return s;
}
function composicion(minutos) {
  const total = Object.values(minutos).reduce((a, b) => a + b, 0);
  if (!total) return el("p", { class: "nota" }, "No se estimó deuda.");
  const seg = el("div", { class: "segmentos", role: "img", "aria-label": "Minutos de deuda por familia" });
  Object.entries(FAMILIAS).forEach(([f, [n, c]]) => {
    if (!minutos[f]) return;
    const d = el("div", { class: c, on: { mousemove: (e) => verTooltip(e, n, [`${fmt(minutos[f] / 60)} h, ${fmt((100 * minutos[f]) / total, 0)} %`]), mouseleave: ocultarTooltip } });
    d.style.flexGrow = String(minutos[f]);
    seg.append(d);
  });
  return el("div", {}, seg, el("ul", { class: "leyenda" }, Object.entries(FAMILIAS).map(([f, [n, c]]) =>
    el("li", {}, el("i", { class: c }), `${n}: ${fmt((minutos[f] || 0) / 60)} h`))));
}
function tilesMetricas(d, ctx) {
  const h = d.metricas, abrir = (clave) => () => abrirExplicacion(clave, d, ctx);
  return el("div", { class: "tiles" },
    tile("Deuda estimada", `${fmt(d.deuda_horas)} h`, `${fmt(d.horas_kloc, 1)} h/KLOC`, true, abrir("deuda")),
    tile("Nota SQALE", d.nota_sqale, `Razón de deuda: ${fmt(100 * d.debt_ratio, 1)} %`, true, abrir("sqale")),
    tile("Cognitiva máx.", fmt(h.cognitiva_max, 0), "Umbral: 15", false, abrir("cognitiva")),
    tile("Ciclomática máx.", fmt(h.ciclomatica_max, 0), "Umbral: 10", false, abrir("ciclomatica")),
    tile("Clones", fmt(h.clones, 0), "Fragmentos duplicados", false, abrir("clones")),
    tile("Advertencias", fmt(h.advertencias, 0), `${fmt(h.advertencias_kloc, 1)} por KLOC`, false, abrir("advertencias")),
    tile("Mantenibilidad mín.", fmt(h.mi_min, 1), "Radon: de 0 a 100", false, abrir("mantenibilidad")),
    tile("SATD", fmt(h.satd, 0), "TODO, FIXME, HACK, XXX", false, abrir("satd")));
}

// ---------- Paginas ----------
function pintarResumen() {
  const r = estado.resultado, p = $("p-resumen");
  p.replaceChildren();
  const errores = [...(r.codigo?.errores || []), ...(r.historial?.errores || []), ...(r.sin_confirmar?.errores || [])];
  const avisos = r.codigo?.avisos || [];
  p.append(el("div", { class: "aviso" }, "Estas cifras estiman qué tan costoso es mantener el código. No indican si el código funciona: en el experimento, DeepSeek resolvió solo 9 de 30 problemas sin mostrar más deuda que las personas."));
  if (r.raiz && r.carpeta.replaceAll("\\", "/").toLowerCase() !== r.raiz.replaceAll("\\", "/").toLowerCase()) p.append(el("p", { class: "nota seccion" }, `La carpeta está dentro del repositorio ${r.raiz}, así que se analizó el repositorio completo.`));
  if (r.codigo) {
    const c = r.codigo;
    p.append(el("section", { class: "seccion" }, el("h2", {}, "Código actual"),
      el("p", { class: "nota" }, `${fmt(c.metricas.archivos, 0)} archivos Python, ${fmt(c.metricas.lineas, 0)} líneas y ${fmt(c.metricas.funciones, 0)} funciones. ${c.excluidos ? `Se excluyeron ${fmt(c.excluidos, 0)} archivos de pruebas o migraciones.` : ""}`),
      el("p", { class: "nota seccion-ayuda" }, "Selecciona una tarjeta para ver qué significa su resultado."),
      tilesMetricas(c, "codigo"),
      el("div", { class: "tarjeta" }, el("h3", {}, "De dónde viene la deuda"), composicion(c.minutos_familia))));
    p.lastChild.lastChild.style.marginTop = "10px";
  }
  if (r.sin_confirmar) {
    const s = r.sin_confirmar;
    p.append(el("section", { class: "seccion" }, el("h2", {}, "Cambios sin confirmar"),
      s.metricas.archivos ? el("div", {}, el("p", { class: "nota" }, "Veredicto: ", insigniaVeredicto(s.veredicto), ` IRD ${fmt(s.ird, 1)}, ${s.metricas.lineas_anadidas} líneas añadidas.`), tilesMetricas(s, "cambio")) : el("p", { class: "nota" }, "No hay cambios de Python sin confirmar.")));
  }
  const h = r.historial;
  if (h) {
    const cs = h.commits;
    const total = cs.reduce((a, c) => a + c.deuda_horas, 0), lineas = cs.reduce((a, c) => a + c.metricas.lineas_anadidas, 0);
    const bloque = el("section", { class: "seccion" }, el("h2", {}, "Historial de git"),
      el("p", { class: "nota" }, `${h.revisados} commits revisados; ${cs.length} cambian Python de producción${h.sin_python ? ` y ${h.sin_python} no` : ""}.`));
    if (cs.length) {
      const ia = cs.filter((c) => etiqueta(c) === "ia").length;
      const bloqueados = cs.filter((c) => c.veredicto === "BLOQUEAR").length;
      const kloc = lineas ? total / (lineas / 1000) : 0;
      const datos = { commits: cs, total, lineas, kloc, bloqueados, ia, total_commits: cs.length };
      const abrir = (clave) => () => abrirExplicacion(clave, datos, "historial");
      bloque.append(el("div", { class: "tiles" },
        tile("Deuda introducida", `${fmt(total)} h`, `${fmt(kloc, 1)} h/KLOC`, true, abrir("historial_deuda")),
        tile("Líneas añadidas", fmt(lineas, 0), "En código de producción", false, abrir("historial_lineas")),
        tile("Bloqueados", fmt(bloqueados, 0), "Según el IRD", false, abrir("historial_bloqueados")),
        tile("Con IA declarada", fmt(ia, 0), `De ${cs.length} commits`, false, abrir("historial_ia"))));
      const tar = el("div", { class: "tarjeta" }, el("h3", {}, "Deuda introducida por commit, en horas"), graficoCommits(cs));
      if (ia) tar.append(el("ul", { class: "leyenda" }, el("li", {}, el("i", { class: "c-s1" }), "Sin declarar"), el("li", {}, el("i", { class: "c-s2" }), "IA declarada")));
      tar.append(el("p", { class: "nota" }, "Selecciona una barra para ver el commit."));
      tar.style.marginTop = "10px";
      bloque.append(tar);
    }
    p.append(bloque);
  }
  if (errores.length || avisos.length) {
    p.append(el("section", { class: "seccion" }, el("h2", {}, "Avisos del análisis"),
      el("ul", { class: "lista-simple nota" }, [...avisos, ...errores].slice(0, 30).map((x) => el("li", {}, x)))));
  }
}
function filaHallazgo(h, conArchivo = true) {
  return el("tr", {}, conArchivo ? td(`${h.archivo}:${h.linea}`, "mono ruta") : null, td(FAMILIAS[h.familia]?.[0] || h.familia), td(h.regla, "mono"),
    td(h.severidad), td(h.funcion || h.detalle || ""), td(fmt(h.costo_min, 1), "num"));
}
function pintarCommits() {
  const p = $("p-commits"), h = estado.resultado.historial;
  p.replaceChildren();
  if (!h) { p.append(el("p", { class: "nota" }, "No se analizó el historial de git.")); return; }
  if (!h.commits.length) { p.append(el("p", { class: "nota" }, "Ningún commit revisado cambia Python de producción.")); return; }
  const filas = [];
  for (const c of h.commits) {
    const abierto = estado.abierto === c.sha, m = c.metricas;
    const sel = el("select", { "aria-label": `Origen de ${c.corto}`, on: { click: (e) => e.stopPropagation(), change: (e) => { estado.etiquetas[c.sha] = e.target.value; pintarComparar(); pintarResumen(); } } },
      el("option", { value: "sin_declarar" }, "Sin declarar"), el("option", { value: "ia" }, "IA"));
    sel.value = etiqueta(c);
    filas.push(el("tr", { class: "clic", tabindex: 0, "aria-expanded": abierto, on: { click: () => alternar(c.sha), keydown: (e) => { if (e.key === "Enter") alternar(c.sha); } } },
      td(c.corto, "mono"), td(c.fecha.slice(0, 10)), td(c.autor), td(c.asunto, "asunto"), td(sel),
      td(`+${m.lineas_anadidas} −${m.lineas_eliminadas}`, "num"), td(fmt(c.deuda_horas), "num"), td(fmt(c.horas_kloc, 1), "num"),
      td(fmt(m.cognitiva_max, 0), "num"), td(fmt(m.ciclomatica_max, 0), "num"), td(fmt(m.clones, 0), "num"), td(fmt(m.advertencias, 0), "num"),
      td(fmt(m.mi_min, 1), "num"), td(fmt(m.satd, 0), "num"), td(insigniaVeredicto(c.veredicto))));
    if (abierto) {
      filas.push(el("tr", { class: "detalle" }, el("td", { colspan: 15 },
        c.hallazgos.length ? tabla(["Ubicación", "Familia", "Regla", "Severidad", "Función o detalle", { t: "Min", num: true }], c.hallazgos.map((x) => filaHallazgo(x))) : el("p", { class: "nota" }, "Sin hallazgos en este commit."),
        c.errores?.length ? el("p", { class: "nota" }, c.errores.join(" ")) : null)));
    }
  }
  p.append(el("p", { class: "nota seccion" }, "Selecciona un commit para ver sus hallazgos. Puedes corregir su origen si sabes que se usó IA."),
    tabla(["Commit", "Fecha", "Autor", "Asunto", "Origen", { t: "Líneas", num: true }, { t: "Horas", num: true }, { t: "h/KLOC", num: true }, { t: "Cogn.", num: true }, { t: "Cicl.", num: true },
      { t: "Clones", num: true }, { t: "Adv.", num: true }, { t: "MI", num: true }, { t: "SATD", num: true }, "Veredicto"], filas));
}
function alternar(sha) { estado.abierto = estado.abierto === sha ? null : sha; pintarCommits(); }
function pintarArchivos() {
  const p = $("p-archivos"), c = estado.resultado.codigo;
  p.replaceChildren();
  if (!c) { p.append(el("p", { class: "nota" }, "Activa «Código actual» para ver esta sección.")); return; }
  p.append(el("section", { class: "seccion" }, el("h2", {}, "Funciones más complejas"),
    c.funciones.length ? tabla(["Función", "Ubicación", { t: "Cognitiva", num: true }, { t: "Ciclomática", num: true }, { t: "Líneas", num: true }],
      c.funciones.map((f) => el("tr", {}, td(f.funcion, "mono ruta"), td(`${f.archivo}:${f.linea}`, "mono ruta"), td(fmt(f.cognitiva, 0), "num"), td(fmt(f.ciclomatica, 0), "num"), td(fmt(f.loc, 0), "num")))) : el("p", { class: "nota" }, "No hay funciones.")));
  p.append(el("section", { class: "seccion" }, el("h2", {}, "Archivos, de más a menos deuda"),
    tabla(["Archivo", { t: "Líneas", num: true }, { t: "Funciones", num: true }, { t: "Cognitiva", num: true }, { t: "Ciclomática", num: true }, { t: "MI", num: true }, { t: "Hallazgos", num: true }, { t: "Horas", num: true }],
      c.archivos.slice(0, 500).map((f) => el("tr", {}, td(f.archivo, "mono ruta"), td(fmt(f.loc, 0), "num"), td(fmt(f.funciones, 0), "num"), td(fmt(f.cognitiva_max, 0), "num"), td(fmt(f.ciclomatica_max, 0), "num"), td(fmt(f.mi, 1), "num"), td(fmt(f.hallazgos, 0), "num"), td(fmt(f.horas), "num"))))));
}
function fuentesHallazgos() {
  const r = estado.resultado, f = [];
  if (r.codigo) f.push(["codigo", "Código actual", r.codigo.hallazgos]);
  if (r.sin_confirmar) f.push(["sucio", "Cambios sin confirmar", r.sin_confirmar.hallazgos]);
  if (r.historial?.commits.length) f.push(["historial", "Todos los commits", r.historial.commits.flatMap((c) => c.hallazgos.map((h) => ({ ...h, commit: c.corto })))]);
  return f;
}
function pintarHallazgos() {
  const p = $("p-hallazgos"), F = estado.filtros, fuentes = fuentesHallazgos();
  p.replaceChildren();
  if (!fuentes.length) { p.append(el("p", { class: "nota" }, "Sin datos.")); return; }
  if (!fuentes.some((x) => x[0] === F.fuente)) F.fuente = fuentes[0][0];
  const opcion = (v, t, actual) => el("option", { value: v, selected: v === actual }, t);
  const cambiar = (k) => (e) => { F[k] = e.target.value; pintarHallazgos(); };
  const lista = fuentes.find((x) => x[0] === F.fuente)[2];
  const q = F.texto.toLowerCase();
  const vis = lista.filter((h) => (!F.familia || h.familia === F.familia) && (!F.severidad || h.severidad === F.severidad)
    && (!q || `${h.archivo} ${h.regla} ${h.funcion || ""} ${h.detalle || ""}`.toLowerCase().includes(q)));
  const buscador = el("input", { type: "search", placeholder: "Archivo, regla o texto", "aria-label": "Buscar hallazgos", value: F.texto, on: { change: cambiar("texto") } });
  p.append(el("div", { class: "filtros" },
    el("label", {}, "Fuente ", el("select", { on: { change: cambiar("fuente") } }, fuentes.map((x) => opcion(x[0], x[1], F.fuente)))),
    el("label", {}, "Familia ", el("select", { on: { change: cambiar("familia") } }, opcion("", "Todas", F.familia), Object.entries(FAMILIAS).map(([k, v]) => opcion(k, v[0], F.familia)))),
    el("label", {}, "Severidad ", el("select", { on: { change: cambiar("severidad") } }, opcion("", "Todas", F.severidad), ["baja", "media", "alta", "critica"].map((s) => opcion(s, s === "critica" ? "crítica" : s, F.severidad)))),
    buscador, el("span", { class: "nota" }, `${fmt(vis.length, 0)} de ${fmt(lista.length, 0)}${vis.length > 400 ? "; se muestran los primeros 400" : ""}`)));
  p.append(vis.length ? tabla(["Ubicación", "Familia", "Regla", "Severidad", "Función o detalle", { t: "Min", num: true }], vis.slice(0, 400).map((h) => filaHallazgo(h))) : el("p", { class: "nota" }, "Ningún hallazgo coincide con los filtros."));
}
async function pintarComparar() {
  const p = $("p-comparar"), h = estado.resultado?.historial;
  p.replaceChildren();
  if (!h?.commits.length) { p.append(el("p", { class: "nota" }, "Hace falta analizar el historial de git para comparar.")); return; }
  let d;
  try { d = await api("/api/comparar", { id: estado.trabajo, etiquetas: estado.etiquetas }); } catch (e) { p.append(el("p", { class: "error" }, e.message)); return; }
  p.replaceChildren(
    el("div", { class: "aviso" }, "«Sin declarar» no significa escrito por una persona: solo indica que el commit no menciona una herramienta de IA. Además, esta comparación no empareja commits del mismo problema como el experimento, así que muestra asociación, no causa."),
    el("div", { class: "tiles seccion" }, tile("IA declarada", fmt(d.n_ia, 0), "commits"), tile("Sin declarar", fmt(d.n_resto, 0), "commits")),
    d.suficiente ? el("p", { class: "nota seccion" }, "Mann-Whitney U bilateral, delta de Cliff y corrección de Holm. Se considera diferencia si p Holm < 0,05 y |δ| ≥ 0,147.")
      : el("p", { class: "nota seccion" }, `Se necesitan al menos ${d.min_por_grupo} commits en cada grupo para hacer pruebas estadísticas. Puedes corregir el origen en la pestaña Commits.`),
    tabla(["H", "Métrica", { t: "Mediana IA", num: true }, { t: "Mediana resto", num: true }, { t: "p", num: true }, { t: "p Holm", num: true }, { t: "δ Cliff", num: true }, "Efecto", "Resultado"],
      d.metricas.map((m) => el("tr", {}, td(m.hipotesis), td(m.nombre), td(fmt(m.med_ia), "num"), td(fmt(m.med_resto), "num"), td(fmt(m.p, 3), "num"), td(fmt(m.p_holm, 3), "num"), td(fmt(m.cliff, 3), "num"), td(m.magnitud || "—"),
        td(m.p_holm === null ? "—" : m.significativo ? "Hay diferencia" : "Sin diferencia")))));
}
function pintarMetodo() {
  const filas = [["Complejidad cognitiva", "Qué tan difícil de entender es la función más enredada. Umbral: 15; cuesta 3 min por punto de aumento.", "complexipy"],
    ["Complejidad ciclomática", "Cuántos caminos de ejecución tiene la función. Umbral: 10; cuesta 2 min por punto de aumento.", "Radon"],
    ["Clones", "Fragmentos duplicados contra el resto del proyecto. Cuesta 20 min.", "jscpd"],
    ["Advertencias", "Malas prácticas e importaciones cíclicas. De 2,5 a 120 min, según categoría y severidad.", "Ruff y Pylint"],
    ["Mantenibilidad (MI)", "Puntaje del archivo menos mantenible. Más alto es mejor.", "Radon"],
    ["SATD", "Comentarios TODO, FIXME, HACK o XXX. Cuesta 10 min.", "tokenize"],
    ["Horas de deuda", "Suma de los costos, según el modelo tipo SQALE de la guía.", "debtguard"],
    ["IRD y veredicto", "Índice de 0 a 100 calibrado con 20 parches humanos. Solo se aplica a cambios, no al código completo.", "debtguard"]];
  $("p-metodo").replaceChildren(
    el("section", { class: "seccion" }, el("h2", {}, "Las mismas métricas del experimento"), tabla(["Métrica", "Qué mide", "Herramienta"], filas.map((f) => el("tr", {}, td(f[0]), td(f[1]), td(f[2]))))),
    el("section", { class: "seccion" }, el("h2", {}, "Qué se analiza en cada caso"), el("ul", { class: "lista-simple" },
      el("li", {}, "Commits y cambios sin confirmar: solo lo que introduce el cambio, igual que en el experimento."),
      el("li", {}, "Código actual: todo el código de producción, tratado como nuevo. Sus horas no son comparables con las de un commit."),
      el("li", {}, "Se excluyen pruebas, migraciones y archivos generados, y se respeta .gitignore."))),
    el("section", { class: "seccion" }, el("h2", {}, "Límites"), el("ul", { class: "lista-simple" },
      el("li", {}, "Solo mide Python."),
      el("li", {}, "No comprueba si el código funciona: para eso están las pruebas del proyecto."),
      el("li", {}, "Las horas son una estimación con costos definidos por el equipo; todavía no se han validado con correcciones cronometradas."),
      el("li", {}, "La precisión de las alertas sigue pendiente de la revisión manual del Hito 2."),
      el("li", {}, "No detecta clones semánticos ni mide acoplamiento."),
      el("li", {}, "El veredicto es muy estricto en cambios diminutos: un solo TODO puede bloquear un cambio de una línea."))));
}
function pintarTodo() {
  $("vacio").hidden = true; $("resultados").hidden = false;
  pintarResumen(); pintarCommits(); pintarArchivos(); pintarHallazgos(); pintarComparar(); pintarMetodo();
  abrirPestana("resumen");
}
function abrirPestana(n) {
  document.querySelectorAll("[role=tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.p === n)));
  document.querySelectorAll(".pagina").forEach((d) => { d.hidden = d.id !== `p-${n}`; });
}
function descargar(nombre, tipo, texto) {
  const a = el("a", { href: URL.createObjectURL(new Blob([texto], { type: tipo })), download: nombre });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function csvHallazgos() {
  const esc = (v) => {
    let s = String(v ?? "");
    if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`; // evita que una hoja de calculo ejecute texto del repositorio como formula
    return `"${s.replaceAll('"', '""')}"`;
  };
  const cols = ["fuente", "commit", "archivo", "linea", "funcion", "familia", "regla", "severidad", "categoria", "valor", "costo_min", "detalle"];
  const lineas = [cols.join(",")];
  fuentesHallazgos().forEach(([k, , lista]) => lista.forEach((h) => lineas.push(cols.map((c) => esc(c === "fuente" ? k : h[c])).join(","))));
  return `﻿${lineas.join("\r\n")}`;
}

// ---------- Eventos ----------
$("btn-examinar").addEventListener("click", () => abrirNavegador().catch((e) => mostrarError(e.message)));
$("btn-nativo").addEventListener("click", async () => {
  try {
    const d = await api("/api/elegir", {});
    if (d.error) mostrarError(d.error);
    if (d.ruta) elegirCarpeta(d.ruta);
  } catch (e) { mostrarError(e.message); }
});
$("ruta").addEventListener("change", (e) => { if (e.target.value.trim()) elegirCarpeta(e.target.value.trim()); });
$("btn-analizar").addEventListener("click", analizar);
$("btn-cancelar").addEventListener("click", async () => {
  $("btn-cancelar").disabled = true;
  $("progreso-texto").textContent = "Cancelando al terminar el paso actual";
  await api(`/api/trabajos/${estado.trabajo}/cancelar`, {}).catch(() => {});
});
document.querySelectorAll("[role=tab]").forEach((b) => b.addEventListener("click", () => abrirPestana(b.dataset.p)));
$("exp-cerrar").addEventListener("click", () => $("dlg-metrica").close());
$("dlg-metrica").addEventListener("click", (e) => { if (e.target === $("dlg-metrica")) $("dlg-metrica").close(); });
$("dlg-subir").addEventListener("click", () => padreDialogo && navegar(padreDialogo));
$("dlg-cerrar").addEventListener("click", () => $("dlg-carpeta").close());
$("dlg-usar").addEventListener("click", () => { $("dlg-carpeta").close(); if (rutaDialogo) elegirCarpeta(rutaDialogo); });
$("btn-json").addEventListener("click", () => descargar("debtguard.json", "application/json", JSON.stringify(estado.resultado, null, 2)));
$("btn-csv").addEventListener("click", () => descargar("debtguard_hallazgos.csv", "text/csv;charset=utf-8", csvHallazgos()));
