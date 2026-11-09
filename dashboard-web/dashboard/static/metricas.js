"use strict";
// Explicacion de cada tarjeta. Los limites son los de debtguard (remediation_costs.yaml, costs.py y complexity.py)
// y, para el indice de mantenibilidad, los rangos que documenta Radon.
const ESTADOS = {
  bien: ["e-bien", "Bueno"], aceptable: ["e-bien", "Aceptable"], aviso: ["e-aviso", "Conviene revisar"],
  alto: ["e-critico", "Alto"], info: ["e-neutro", "Informativo"],
};
const SEVERIDADES = { critica: "críticas", alta: "altas", media: "medias", baja: "bajas" };
const familiaMinutos = (d) => d.minutos_familia || d.hallazgos.reduce((m, h) => ({ ...m, [h.familia]: (m[h.familia] || 0) + h.costo_min }), {});
const alcance = (ctx) => (ctx === "codigo" ? "todo el código de producción" : ctx === "cambio" ? "lo que introduce este cambio" : "los commits revisados");
const donde = (h) => `${h.archivo}:${h.linea}${h.funcion ? ` (${h.funcion})` : ""}`;

function peoresHallazgos(d, filtro, n = 5) {
  return d.hallazgos.filter(filtro).sort((a, b) => b.costo_min - a.costo_min).slice(0, n).map((h) => `${donde(h)}: ${fmt(h.costo_min, 1)} min`);
}
function complejidad(d, ctx, cfg) {
  const v = d.metricas[cfg.clave];
  const aumento = d.metricas[cfg.delta];
  const peores = d.hallazgos.filter((h) => h.regla === cfg.regla).sort((a, b) => b.valor - a.valor).slice(0, 5).map((h) => `${donde(h)}: ${fmt(h.valor, 0)}`);
  const estado = v <= cfg.umbral ? "bien" : v <= 2 * cfg.umbral ? "aviso" : "alto";
  const veces = fmt(v / cfg.umbral, 1);
  let lectura = estado === "bien"
    ? `${fmt(v, 0)} no supera el umbral de ${cfg.umbral}. Ninguna función medida pasa ese límite, así que esta métrica no genera deuda.`
    : `${fmt(v, 0)} supera el umbral de ${cfg.umbral} (${veces} veces). ${estado === "alto" ? "Está por encima del doble del umbral, por lo que se considera severidad alta." : "Está sobre el umbral, pero sin llegar al doble."}`;
  if (ctx === "cambio" && aumento !== undefined) lectura += ` Esta cifra incluye la complejidad que la función ya tenía. El cambio la modificó en ${aumento >= 0 ? "+" : ""}${fmt(aumento, 0)} puntos en total.`;
  return {
    titulo: cfg.titulo, valor: fmt(v, 0), estado, que: cfg.que, herramienta: cfg.herramienta,
    calculo: `Es el valor más alto entre las funciones de ${alcance(ctx)}. Umbral: ${cfg.umbral}. Cada punto que supera el umbral cuesta ${cfg.minutos} min; en un cambio solo se cobra el aumento.`,
    lectura, lista: peores.length ? ["Funciones sobre el umbral", peores] : null,
  };
}

const EXPLICACIONES = {
  deuda(d, ctx) {
    const ratio = d.debt_ratio * 100, f = familiaMinutos(d);
    const orden = Object.entries(f).filter(([, m]) => m > 0).sort((a, b) => b[1] - a[1]);
    const principal = orden[0] ? `La mayor parte viene de ${FAMILIAS[orden[0][0]][0].toLowerCase()}: ${fmt(orden[0][1] / 60)} h.` : "No se detectó ningún hallazgo con costo.";
    return {
      titulo: "Deuda estimada", valor: `${fmt(d.deuda_horas)} h`, estado: { A: "bien", B: "aceptable", C: "aviso", D: "alto", E: "alto" }[d.nota_sqale],
      que: "Estima cuánto tiempo tomaría corregir los problemas detectados. No es tiempo ya perdido, sino trabajo pendiente.",
      herramienta: "Modelo de costo tipo SQALE de debtguard, con los hallazgos de complexipy, Radon, Ruff, Pylint, jscpd y tokenize.",
      calculo: `Suma los minutos de cada hallazgo en ${alcance(ctx)} y los pasa a horas. Por tamaño: ${fmt(d.horas_kloc, 1)} h por cada 1000 líneas.`,
      lectura: `${fmt(d.deuda_horas)} h equivalen a unos ${fmt(d.deuda_horas / 8, 1)} días de trabajo de 8 horas, y a un ${fmt(ratio, 1)} % del tiempo estimado para desarrollar este código. ${principal} Para juzgarlo, mira la proporción más que las horas: el mismo número pesa distinto según el tamaño del código.`,
      lista: orden.length ? ["De dónde viene", orden.map(([k, m]) => `${FAMILIAS[k][0]}: ${fmt(m / 60)} h`)] : null,
      nota: "Es una estimación: los costos los definió el equipo y aún no se han validado con correcciones cronometradas.",
    };
  },
  sqale(d) {
    const ratio = d.debt_ratio * 100, nota = d.nota_sqale;
    const limites = { A: 5, B: 10, C: 20, D: 50 };
    const siguiente = limites[nota];
    return {
      titulo: "Nota SQALE", valor: nota, estado: { A: "bien", B: "aceptable", C: "aviso", D: "alto", E: "alto" }[nota],
      que: "Resume la deuda en una letra, de la A (mejor) a la E (peor), comparándola con lo que costaría escribir el código.",
      herramienta: "Modelo SQALE, con la misma escala de letras que usa SonarQube.",
      calculo: "Razón de deuda = minutos de deuda ÷ (líneas × 30 min). A: hasta 5 %. B: hasta 10 %. C: hasta 20 %. D: hasta 50 %. E: más de 50 %.",
      lectura: `Su razón de deuda es ${fmt(ratio, 1)} %, y por eso obtiene ${nota}. ${siguiente ? `El límite de esta letra es ${siguiente} %${siguiente - ratio < 1 ? ", y está muy cerca de superarlo" : ""}.` : "Supera el último límite de la escala."} ${nota <= "B" ? "Una buena nota no significa que no haya problemas: conviene mirar también las advertencias y la complejidad." : "Conviene empezar por los hallazgos de mayor costo."}`,
      nota: "En un cambio muy pequeño, un solo hallazgo puede bajar mucho la nota.",
    };
  },
  cognitiva: (d, ctx) => complejidad(d, ctx, {
    titulo: "Complejidad cognitiva máxima", clave: "cognitiva_max", delta: "delta_cognitiva", regla: "cognitive>15", umbral: 15, minutos: 3, herramienta: "complexipy.",
    que: "Mide qué tan difícil es entender una función al leerla. Penaliza sobre todo las condiciones y los bucles anidados.",
  }),
  ciclomatica: (d, ctx) => complejidad(d, ctx, {
    titulo: "Complejidad ciclomática máxima", clave: "ciclomatica_max", delta: "delta_ciclomatica", regla: "cyclomatic>10", umbral: 10, minutos: 2, herramienta: "Radon.",
    que: "Cuenta los caminos de ejecución de una función. Cuantos más caminos, más casos hay que probar.",
  }),
  clones(d, ctx) {
    const n = d.metricas.clones;
    return {
      titulo: "Clones", valor: fmt(n, 0), estado: n ? "aviso" : "bien",
      que: "Cuenta fragmentos de código copiados. Si un duplicado tiene un error, hay que corregirlo en cada copia.",
      herramienta: "jscpd, con un mínimo de 50 tokens por fragmento.",
      calculo: `Compara el código con el resto del proyecto, sin contar pruebas ni documentación. Para ${alcance(ctx)}, un fragmento cuenta si al menos la mitad de sus líneas son nuevas. Cada uno cuesta 20 min.`,
      lectura: n ? `Hay ${fmt(n, 0)} ${n === 1 ? "fragmento duplicado" : "fragmentos duplicados"}, unos ${fmt((n * 20) / 60)} h estimadas. Revisa si se pueden unir en una función común.` : "No se encontraron fragmentos duplicados de este tipo.",
      lista: n ? ["Dónde mirar", d.hallazgos.filter((h) => h.familia === "clon").slice(0, 5).map((h) => `${h.archivo}: ${h.detalle}`)] : null,
      nota: "jscpd detecta copias textuales. No ve código que hace lo mismo escrito de otra forma, que es la redundancia que S03 asocia a los LLMs.",
    };
  },
  advertencias(d, ctx) {
    const reglas = d.hallazgos.filter((h) => h.familia === "regla"), n = reglas.length;
    const sev = reglas.reduce((m, h) => ({ ...m, [h.severidad]: (m[h.severidad] || 0) + 1 }), {});
    const cat = reglas.reduce((m, h) => ({ ...m, [h.categoria]: (m[h.categoria] || 0) + 1 }), {});
    const min = reglas.reduce((a, h) => a + h.costo_min, 0);
    const cuenta = reglas.reduce((m, h) => ({ ...m, [h.regla]: (m[h.regla] || 0) + 1 }), {});
    const top = Object.entries(cuenta).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([r, c]) => {
      const ej = reglas.find((h) => h.regla === r);
      return `${r} (${c}): ${ej.detalle}`;
    });
    const estado = !n ? "bien" : sev.critica ? "alto" : "aviso";
    const partes = Object.keys(SEVERIDADES).filter((s) => sev[s]).map((s) => `${sev[s]} ${SEVERIDADES[s]}`).join(", ");
    const lectura = !n ? "No se encontró ninguna mala práctica con las reglas activas."
      : `Hay ${fmt(n, 0)} advertencias: ${partes}. Equivalen a ${fmt(min / 60)} h de deuda. ${sev.critica ? "Empieza por las críticas: son riesgos de seguridad o errores de sintaxis." : sev.alta ? "Empieza por las de severidad alta." : "No hay críticas ni altas, así que no parecen urgentes, pero se acumulan."} No existe un umbral único de cuántas son demasiadas, porque depende de las reglas activas.`;
    return {
      titulo: "Advertencias", valor: fmt(n, 0), estado,
      que: "Cuenta malas prácticas: errores probables, código innecesario, riesgos de seguridad, problemas de estilo e importaciones cíclicas.",
      herramienta: "Ruff, con un conjunto amplio de reglas, y Pylint solo para importaciones cíclicas (R0401).",
      calculo: `Revisa ${alcance(ctx)}. Son ${fmt(d.metricas.advertencias_kloc, 1)} por cada 1000 líneas. Costo = base × severidad. Base: estilo 5, mantenibilidad 15, seguridad 30 min. Factor: baja 0,5; media 1; alta 2; crítica 4.`,
      lectura, lista: top.length ? ["Las reglas más frecuentes", top] : null,
      lista2: Object.keys(cat).length ? ["Por categoría", Object.entries(cat).map(([c, k]) => `${c}: ${k}`)] : null,
      nota: "Son alertas automáticas y pueden incluir falsos positivos. Por ejemplo, un assert o un subprocess no siempre son un problema real.",
    };
  },
  mantenibilidad(d, ctx) {
    const v = d.metricas.mi_min;
    const estado = v === null || v === undefined ? "info" : v >= 20 ? "bien" : v >= 10 ? "aviso" : "alto";
    const lecturas = {
      info: "No se pudo calcular, porque ningún archivo se pudo medir.",
      bien: `${fmt(v, 1)} está en el rango alto de Radon (20 o más), incluso en el archivo peor valorado.`,
      aviso: `${fmt(v, 1)} está en el rango medio de Radon (de 10 a 19). Ese archivo merece revisión.`,
      alto: `${fmt(v, 1)} está en el rango bajo de Radon (menos de 10). Es típico de archivos muy grandes, y conviene dividirlo si se modifica a menudo.`,
    };
    const peor = (d.archivos || []).filter((f) => f.mi !== null).sort((a, b) => a.mi - b.mi).slice(0, 5).map((f) => `${f.archivo}: ${fmt(f.mi, 1)}`);
    return {
      titulo: "Mantenibilidad mínima", valor: fmt(v, 1), estado,
      que: "Es un puntaje de 0 a 100 sobre qué tan fácil es mantener un archivo. Aquí, más alto es mejor.",
      herramienta: "Radon (índice de mantenibilidad).",
      calculo: `Combina tamaño, complejidad y comentarios del archivo. Se muestra el peor puntaje entre los archivos de ${alcance(ctx)}. Rangos de Radon: 20 a 100 alto, 10 a 19 medio, 0 a 9 bajo.`,
      lectura: lecturas[estado], lista: peor.length ? ["Archivos con menor puntaje", peor] : null,
      nota: "No suma horas de deuda. Depende mucho del tamaño del archivo, y un cambio pequeño apenas lo mueve.",
    };
  },
  satd(d, ctx) {
    const n = d.metricas.satd;
    return {
      titulo: "SATD (deuda autoadmitida)", valor: fmt(n, 0), estado: n ? "aviso" : "info",
      que: "Cuenta comentarios en los que quien programó admite algo pendiente o mal resuelto: TODO, FIXME, HACK o XXX.",
      herramienta: "tokenize de Python con una expresión regular.",
      calculo: `Busca esas palabras en los comentarios de ${alcance(ctx)}. Cada uno cuesta 10 min.`,
      lectura: n ? `Hay ${fmt(n, 0)} ${n === 1 ? "comentario" : "comentarios"} que declaran deuda, unos ${fmt((n * 10) / 60)} h estimadas. Revisa si siguen vigentes.` : "No hay deuda declarada. Esto no significa que no exista deuda: solo que nadie la dejó escrita en un comentario.",
      lista: n ? ["Dónde mirar", d.hallazgos.filter((h) => h.familia === "satd").slice(0, 5).map((h) => `${h.archivo}:${h.linea}: ${h.detalle}`)] : null,
      nota: "En la literatura del Hito 1 (S02), los agentes de IA declaran menos deuda, así que un valor bajo no basta para concluir que el código está limpio.",
    };
  },
  historial_deuda(h) {
    const orden = [...h.commits].sort((a, b) => b.deuda_horas - a.deuda_horas).slice(0, 5).filter((c) => c.deuda_horas > 0);
    return {
      titulo: "Deuda introducida", valor: `${fmt(h.total)} h`, estado: "info",
      que: "Suma la deuda que añadió cada commit revisado, sin contar la que ya existía antes de cada uno.",
      herramienta: "debtguard, con el mismo procedimiento del experimento.",
      calculo: `Mide cada commit frente al anterior. Por tamaño: ${fmt(h.kloc, 1)} h por cada 1000 líneas añadidas.`,
      lectura: "Sirve para ver qué cambios concentran la deuda. No es la deuda actual: parte pudo corregirse después. Para eso está la sección «Código actual».",
      lista: orden.length ? ["Commits con más deuda", orden.map((c) => `${c.corto}: ${fmt(c.deuda_horas)} h. ${c.asunto}`)] : null,
    };
  },
  historial_lineas(h) {
    return {
      titulo: "Líneas añadidas", valor: fmt(h.lineas, 0), estado: "info",
      que: "Cuenta las líneas nuevas no vacías en código Python de producción.", herramienta: "unidiff, sobre el diff de cada commit.",
      calculo: "No cuenta pruebas, migraciones ni archivos generados.",
      lectura: "No es buena ni mala por sí sola. Da contexto: más código suele traer más deuda, y por eso las horas también se muestran por KLOC.",
    };
  },
  historial_bloqueados(h) {
    return {
      titulo: "Commits bloqueados", valor: fmt(h.bloqueados, 0), estado: h.bloqueados ? "aviso" : "bien",
      que: "Cuenta los commits a los que el prototipo les daría el veredicto BLOQUEAR.",
      herramienta: "Índice de riesgo de deuda (IRD) de debtguard, calibrado con 20 parches humanos de SWE-bench.",
      calculo: "Se bloquea si el IRD llega a 35,5 o si hay un hallazgo crítico de seguridad. Desde 28,6 se advierte.",
      lectura: h.bloqueados ? "Revisa estos commits en la pestaña Commits. Un bloqueo es una señal para revisar, no un error confirmado." : "Ningún commit revisado llegó al límite de bloqueo.",
      nota: "El veredicto es muy estricto en cambios diminutos: un solo TODO puede bloquear un cambio de una línea.",
    };
  },
  historial_ia(h) {
    return {
      titulo: "Con IA declarada", valor: fmt(h.ia, 0), estado: "info",
      que: "Cuenta los commits que mencionan una herramienta de IA, por ejemplo en una línea Co-Authored-By.", herramienta: "Búsqueda de texto en el autor y el mensaje del commit.",
      calculo: `${fmt(h.ia, 0)} de ${fmt(h.total_commits, 0)} commits con Python de producción. Puedes corregir el origen en la pestaña Commits.`,
      lectura: "No mide calidad. Sirve para separar grupos en la pestaña «IA y resto». Un commit sin esa mención pudo escribirse igualmente con IA.",
    };
  },
};

function abrirExplicacion(clave, datos, ctx) {
  const x = EXPLICACIONES[clave](datos, ctx);
  const [clase, etiquetaEstado] = ESTADOS[x.estado];
  const bloque = (t, texto) => el("div", { class: "exp-bloque" }, el("h3", {}, t), el("p", {}, texto));
  const listado = (par) => (par ? el("div", { class: "exp-bloque" }, el("h3", {}, par[0]), el("ul", { class: "lista-simple exp-lista" }, par[1].map((i) => el("li", {}, i)))) : null);
  $("exp-titulo").textContent = x.titulo;
  $("exp-cuerpo").replaceChildren(
    el("div", { class: "exp-resultado" }, el("span", { class: "exp-valor" }, x.valor), el("span", { class: `insignia ${clase}` }, el("i"), etiquetaEstado)),
    bloque("Qué significa este resultado", x.lectura), bloque("Qué mide", x.que), bloque("Herramienta", x.herramienta), bloque("Cómo se calcula", x.calculo),
    ...[listado(x.lista), listado(x.lista2)].filter(Boolean), ...(x.nota ? [el("p", { class: "nota exp-nota" }, x.nota)] : []));
  $("dlg-metrica").showModal();
  $("exp-cuerpo").scrollTop = 0;
}
