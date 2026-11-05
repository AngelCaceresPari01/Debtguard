"""Genera el informe del Hito 2 a partir de los resultados, para evitar transcribir cifras a mano."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import yaml
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
DATA, FIG = RAIZ / "data", RAIZ / "docs" / "figuras"
SALIDA = RAIZ.parent / "A.9_HITO2_Carrasco_Caceres_Chancuaña_Yana.docx"
ANCHO = 16.5

t = pd.read_csv(DATA / "tabla_hipotesis.csv")
ex = pd.read_csv(DATA / "tabla_exploratoria.csv").set_index("metrica")
sens = pd.read_csv(DATA / "sensibilidad_costos.csv")
comp = pd.read_csv(DATA / "composicion_deuda.csv").set_index("origen")
ver = pd.read_csv(DATA / "veredictos.csv").set_index("origen")
sq = pd.read_csv(DATA / "notas_sqale.csv").set_index("origen")
gen = pd.read_csv(DATA / "generacion_llm.csv")
eje = pd.read_csv(DATA / "ejecucion_comparacion.csv")
res = pd.read_csv(DATA / "resultados.csv")
th = yaml.safe_load((RAIZ / "config" / "thresholds.yaml").read_text(encoding="utf-8"))
cl = pd.read_csv(DATA / "validacion" / "clave_no_abrir.csv")


def n(x, d=2) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def ps(x) -> str:
    return "< 0,001" if x < 0.001 else n(x, 3)


NOMBRES = {"cognitiva_max": "Cognitiva máxima", "ciclomatica_max": "Ciclomática máxima", "clones": "Clones nuevos",
           "advertencias_kloc": "Advertencias/KLOC", "mi_min": "Índice de mantenibilidad", "horas_kloc": "Horas/KLOC",
           "satd_kloc": "SATD/KLOC"}
h_total, l_total = comp.loc["humano", "deuda_horas"], comp.loc["LLM", "deuda_horas"]
h_lin, l_lin = comp.loc["humano", "lineas_anadidas"], comp.loc["LLM", "lineas_anadidas"]
sel = gen[gen.elegido]
laxos = int((sel.modo == "laxo").sum())
n_reserva = int((sel.rol == "reserva").sum())
n_gen, n_mal = len(gen), int((gen.estado != "ok").sum())
tok_in, tok_out = int(gen.tokens_entrada.sum()), int(gen.tokens_salida.sum())
w = res.pivot(index="instance_id", columns="origen", values="lineas_anadidas")
llm_menos = int((w.LLM < w.humano).sum())

try:
    hw = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "$c=(Get-CimInstance Win32_Processor).Name;"
                         "$r=[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB);"
                         "Write-Output \"$c, $r GB de RAM\""], capture_output=True, text=True, timeout=30).stdout.strip()
except OSError:
    hw = "equipo con Windows 11"

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.25)
sec.top_margin = sec.bottom_margin = Cm(2.5)
est = doc.styles["Normal"]
est.font.name, est.font.size = "Arial", Pt(10.5)
est.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
est.paragraph_format.space_after = Pt(7)
est.paragraph_format.line_spacing = 1.15
for nombre, tam, antes, despues in (("Heading 1", 15, 16, 7), ("Heading 2", 12, 12, 5), ("Title", 22, 0, 12)):
    s = doc.styles[nombre]
    s.font.name, s.font.size, s.font.bold = "Arial", Pt(tam), True
    s.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    s.element.rPr.rFonts.set(qn("w:asciiTheme"), "")
    rf = s.element.rPr.rFonts
    for atr in list(rf.attrib):
        del rf.attrib[atr]
    rf.set(qn("w:ascii"), "Arial")
    rf.set(qn("w:hAnsi"), "Arial")
    s.paragraph_format.space_before, s.paragraph_format.space_after = Pt(antes), Pt(despues)
    s.paragraph_format.keep_with_next = True
num_tabla, num_fig = [0], [0]


def campo(parrafo, instruccion: str) -> None:
    for tipo, texto in (("begin", None), (None, instruccion), ("separate", None), ("t", "(actualizar en Word)"), ("end", None)):
        r = parrafo.add_run()
        if tipo in ("begin", "separate", "end"):
            f = OxmlElement("w:fldChar")
            f.set(qn("w:fldCharType"), tipo)
            r._r.append(f)
        elif tipo == "t":
            r.text = texto
        else:
            i = OxmlElement("w:instrText")
            i.set(qn("xml:space"), "preserve")
            i.text = texto
            r._r.append(i)


def P(texto: str, **kw):
    """Parrafo. **negrita** y [[pendiente]] resaltado."""
    p = doc.add_paragraph(style=kw.get("style"))
    p.alignment = kw.get("align", WD_ALIGN_PARAGRAPH.LEFT)
    trozos = texto.replace("[[", "\0P").replace("]]", "\0").replace("**", "\0B").split("\0")
    negrita = False
    for tr in trozos:
        if tr.startswith("P"):
            r = p.add_run("PENDIENTE: " + tr[1:])
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
        elif tr.startswith("B"):
            negrita = not negrita
            if tr[1:]:
                p.add_run(tr[1:]).bold = negrita
        elif tr:
            p.add_run(tr).bold = negrita
    return p


def B(texto):
    return P(texto, style="List Bullet")


def H1(x):
    doc.add_heading(x, 1)


def H2(x):
    doc.add_heading(x, 2)


def pie(texto, lista, rotulo):
    lista[0] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{rotulo} {lista[0]}. {texto}")
    r.italic, r.font.size = True, Pt(9)
    return p


def T(cab, filas, anchos, titulo):
    pie(titulo, num_tabla, "Tabla").paragraph_format.keep_with_next = True
    total = sum(anchos)
    anchos = [a * ANCHO / total for a in anchos]
    tb = doc.add_table(rows=1, cols=len(cab))
    tb.style = "Table Grid"
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    tb.autofit = False

    def celda(c, x, cabecera=False):
        c.text = ""
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.0
        pend = str(x).startswith("[[")
        r = p.add_run(("PENDIENTE: " + str(x)[2:-2]) if pend else str(x))
        r.font.size = Pt(8.5)
        r.bold = cabecera
        if pend:
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
        if cabecera:
            s = OxmlElement("w:shd")
            s.set(qn("w:val"), "clear")
            s.set(qn("w:color"), "auto")
            s.set(qn("w:fill"), "E8E8E4")
            c._tc.get_or_add_tcPr().append(s)

    for i, x in enumerate(cab):
        celda(tb.rows[0].cells[i], x, True)
    rp = tb.rows[0]._tr.get_or_add_trPr()
    rp.append(OxmlElement("w:tblHeader"))
    for f in filas:
        cs = tb.add_row().cells
        for i, x in enumerate(f):
            celda(cs[i], x)
    for fila in tb.rows:
        fila._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for i, a in enumerate(anchos):
            fila.cells[i].width = Cm(a)
    doc.add_paragraph().paragraph_format.space_after = Pt(3)


def F(nombre, titulo, ancho=ANCHO):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(FIG / nombre), width=Cm(ancho))
    pie(titulo, num_fig, "Figura")


# ---------- Caratula ----------
P("Tópicos Avanzados de Ingeniería de Sistemas", align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph().paragraph_format.space_after = Pt(70)
tit = doc.add_paragraph(style="Title")
tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
tit.add_run("Detección y estimación en horas de la deuda técnica en código generado por LLMs: "
            "prototipo y experimento pareado")
P("Hito 2: parte experimental", align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph().paragraph_format.space_after = Pt(50)
P("**Presentado a:**", align=WD_ALIGN_PARAGRAPH.CENTER)
P("Robert Edison Arisaca Mamani", align=WD_ALIGN_PARAGRAPH.CENTER)
P("**Presentado por:**", align=WD_ALIGN_PARAGRAPH.CENTER)
for a in ("Carrasco Choque Arles Melvin", "Caceres Pari Angel Raul", "Chancuaña Alvis Klismann", "Yana Agramonte Luis Efrain"):
    P(a, align=WD_ALIGN_PARAGRAPH.CENTER)
P("10 de noviembre de 2026", align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

# ---------- Indice ----------
p = doc.add_paragraph()
p.add_run("Índice").bold = True
p = doc.add_paragraph()
campo(p, 'TOC \\o "1-2" \\h \\z \\u')
doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

# ---------- 1 ----------
H1("1. Introducción")
P("El código producido con modelos de lenguaje grandes (LLMs) ya forma parte del trabajo diario de muchos equipos, y "
  "con él aparece una pregunta de mantenimiento: cuánta deuda técnica introduce y cuánto costaría pagarla. El SWEBOK "
  "v4.0a la trata dentro de la estimación de costos del mantenimiento y propone estimarla a partir del tamaño, la "
  "complejidad y las violaciones de buenas prácticas [1].")
P("En el Hito 1, un estudio de mapeo sistemático sobre Scopus y Web of Science seleccionó 10 estudios primarios (S01–S10) "
  "[29]. La evidencia indica que el código generado acumula más complejidad y más problemas de mantenibilidad (S01, S03, "
  "S06), que esa deuda es menos visible (S02, S03) y que el LLM sin validación no es fiable para detectarla o repararla "
  "(S04, S08). La revisión dejó además un vacío directamente ligado al área elegida: casi nadie la estima en tiempo o costo.")
P("Este Hito 2 pasa de la revisión al experimento y aporta tres cosas: **debtguard**, un prototipo determinista que recibe "
  "un diff, detecta la deuda que ese cambio introduce y la expresa en horas de remediación con un modelo de tipo SQALE [20]; "
  "un experimento pareado con 30 issues de SWE-bench Lite [19], cada uno resuelto por una persona y por DeepSeek-V4-Pro; y "
  "un análisis de sensibilidad del modelo de costos.")
P(f"El resultado principal es que **no se encontró una diferencia significativa en ninguna de las siete métricas "
  f"principales**. Este resultado debe leerse junto a otro: los parches del LLM fueron bastante más pequeños "
  f"(mediana de {n(ex.loc['lineas_anadidas', 'med_llm'], 0)} líneas añadidas frente a "
  f"{n(ex.loc['lineas_anadidas', 'med_humano'], 0)}) y no se comprobó si resuelven el issue.")
P("El informe se organiza así: la Sección 2 discute los trabajos relacionados; la 3, la planificación metodológica; la 4, "
  "la conducción del experimento; la 5, los resultados; y la 6, las conclusiones, la discusión frente a S01–S10, las "
  "amenazas a la validez y el trabajo futuro.")

# ---------- 2 ----------
H1("2. Trabajos relacionados")
P("La búsqueda del Hito 1 identificó cuatro estudios secundarios cercanos [29]. Ninguno aborda de forma central la deuda "
  "que introduce el desarrollo asistido por LLMs ni cómo medirla, y ninguno propone una herramienta para estimarla.")
T(["Estudio", "Tipo y alcance", "Enfoque", "Diferencia con este trabajo"], [
    ["Moreschini et al. [15]", "Revisión multivocal, 61 fuentes", "Gestión de deuda en SE4AI y AI4SE",
     "Foco en la deuda de los sistemas de IA; no mide la deuda de código generado"],
    ["Gosu et al. [16]", "RSL, 29 estudios", "IA generativa para gestionar deuda",
     "Trata al LLM como instrumento, no como fuente de deuda"],
    ["Abdulaziz et al. [17]", "RSL, 46 estudios", "Detección automática de SATD, 2015–2025",
     "No distingue código asistido por LLMs; aquí el SATD es solo una de cuatro familias"],
    ["Kosmas et al. [18]", "Revisión PRISMA", "Ciclo de vida de ML", "La deuda es un tema tangencial"],
], [3, 3, 4, 6], "Estudios secundarios relacionados")
P("Entre los estudios primarios hay varios diseños que este experimento reutiliza o amplía:")
B("**Métricas y comparación con parches de referencia.** S06 [10] compara parches de LLM con los de referencia en SWE-bench "
  "Lite usando CodeQL, y encuentra 423, 420 y 414 recomendaciones de mantenibilidad frente a 30. Aquí se usa el mismo "
  "conjunto de datos, pero con emparejamiento explícito, pruebas estadísticas y estimación en horas.")
B("**Sensibilidad de las métricas.** S01 [5] estima +39 % de complejidad cognitiva y +18 % de advertencias tras adoptar "
  "agentes. S03 [7] muestra que las métricas de Radon apenas distinguen el código de agentes y que la redundancia "
  "semántica sí lo hace. De ahí salen la métrica de H1 y las pruebas de Wilcoxon y delta de Cliff.")
B("**Costo.** S07 [11] reporta días de remediación con SonarQube en una tarea de traducción, y S02 [6] mide el tiempo de "
  "remediación del SATD de agentes. Son las únicas referencias del corpus que expresan la deuda como esfuerzo, y ninguna "
  "estima el costo de un cambio antes de integrarlo.")
B("**Validación.** S08 [12] muestra que un LLM sin validar acierta en el 37 % de las refactorizaciones. Por eso el prototipo "
  "es determinista. S09 [13] aporta el procedimiento de etiquetado con Kappa de Cohen.")
P("La aportación frente a estos trabajos es combinar en una sola herramienta las cuatro familias de hallazgos, atribuir "
  "solo la deuda que introduce el cambio y expresarla en horas por cambio.")

# ---------- 3 ----------
H1("3. Planificación metodológica del experimento")
P("El experimento se planificó como un cuasi-experimento pareado siguiendo las pautas de Wohlin et al. [28]: cada issue "
  "actúa como su propio control, porque ambos tratamientos parten del mismo commit base. Antes de ejecutar la comparación "
  "se fijaron las hipótesis, las métricas, los costos y los umbrales en la etiqueta git v1.0-experimento.")
H2("3.1 Descripción del problema")
P("El código generado por LLMs acumula más complejidad y problemas de mantenibilidad: +39 % de complejidad cognitiva y "
  "+18 % de advertencias (S01), 1,87 veces más redundancia semántica (S03) y 423 recomendaciones de mantenibilidad frente a "
  "30 (S06). La deuda también es menos visible: los agentes la declaran menos (S02) y los revisores la notan menos (S03). "
  "Además, el LLM solo no sirve como detector fiable (S04, S08).")
P("El SWEBOK §2.3.1 pide estimar el costo de la deuda, pero la revisión encontró que solo dos estudios la expresan como "
  "esfuerzo (S02, S07). Falta, por tanto, una forma reproducible de responder antes de integrar un cambio: ¿cuánta deuda "
  "introduce y cuántas horas costaría pagarla?")
H2("3.2 Objetivos")
P("**Objetivo general.** Construir y evaluar un prototipo que detecte y estime en horas la deuda técnica que introduce un "
  "cambio de código Python, y usarlo para comparar el código generado por un LLM con el código humano equivalente.")
P("**Objetivos específicos:**")
for x in ("Implementar un analizador determinista de complejidad, reglas estáticas, clones y SATD limitado a lo que introduce el diff.",
          "Traducir los hallazgos a horas de remediación con un modelo de tipo SQALE configurable.",
          "Comparar 30 pares humano/LLM sobre los mismos issues con pruebas no paramétricas y tamaño del efecto.",
          "Evaluar la sensibilidad de la estimación a los costos y la precisión de las alertas mediante revisión manual."):
    B(x)
T(["H", "Enunciado alternativo (H0: no hay diferencia)", "Métricas", "Respaldo"], [
    ["H1", "El código LLM tiene mayor complejidad", "Cognitiva máx., ciclomática máx.", "S01"],
    ["H2", "El código LLM introduce más clones", "Clones nuevos", "S03"],
    ["H3", "El código LLM tiene más advertencias y menor mantenibilidad", "Advertencias/KLOC, índice de mantenibilidad", "S06"],
    ["H4", "El código LLM tiene más deuda en horas y menos SATD", "Horas/KLOC, SATD/KLOC", "S02, S07"],
], [1, 8, 6, 2], "Hipótesis del experimento")
H2("3.3 Variables dependientes e independientes")
T(["Tipo", "Variable", "Cómo se mide"], [
    ["Independiente", "Origen del código", "Humano (parche de referencia de SWE-bench) o LLM (DeepSeek-V4-Pro)"],
    ["Dependiente", "Complejidad cognitiva y ciclomática máximas", "complexipy y Radon, en las funciones que contienen líneas añadidas"],
    ["Dependiente", "Clones nuevos", "jscpd contra el proyecto; fragmentos con al menos 50 % de líneas añadidas"],
    ["Dependiente", "Advertencias/KLOC", "Ruff en líneas añadidas y ciclos nuevos de Pylint R0401, por cada 1000 líneas añadidas"],
    ["Dependiente", "Índice de mantenibilidad", "Radon; el mínimo entre los archivos tocados"],
    ["Dependiente", "Horas/KLOC", "Suma de los costos SQALE, por cada 1000 líneas añadidas"],
    ["Dependiente", "SATD/KLOC", "Comentarios TODO, FIXME, HACK o XXX en líneas añadidas"],
    ["Control", "Issue y commit base", "Iguales en cada par"],
    ["Control", "Lenguaje y prompt", "Solo Python; prompt único; temperatura 0"],
    ["Registrada", "Tamaño y aplicación del parche", "Líneas añadidas y eliminadas; modo de aplicación; similitud con el parche humano"],
], [2.5, 5, 9], "Variables del experimento")
P("Se excluyen de la medición las pruebas, las migraciones y los archivos autogenerados. Los valores absolutos y los deltas "
  "se reportan como análisis exploratorio, sin intervenir en la decisión sobre las hipótesis.")
H2("3.4 Cronograma y recursos")
T(["Fecha", "Actividad", "Responsable", "Estado"], [
    ["2/11", "Guía de desarrollo y definición del alcance", "Todos", "Hecho"],
    ["5/11", "Prototipo, pruebas y muestreo", "P1, P2", "Hecho"],
    ["5/11", "Generación de parches, calibración y lote de 60 casos", "P1, P2", "Hecho"],
    ["5/11", "Estadística, gráficos y sensibilidad", "P2", "Hecho"],
    ["6–7/11", "Etiquetado de 60 alertas por dos revisores", "P2, P3", "[[por hacer]]"],
    ["7–8/11", "Corrección cronometrada de 10–15 hallazgos; Kappa y precisión", "P2, P3", "[[por hacer]]"],
    ["8/11", "Publicación del repositorio en GitHub", "P1", "[[por hacer]]"],
    ["9/11", "Revisión final del informe", "P3", "[[por hacer]]"],
    ["10/11", "Entrega", "Todos", "[[por hacer]]"],
], [2, 9, 2.5, 3], "Cronograma del Hito 2")
T(["Recurso", "Detalle"], [
    ["Humanos", "P1: prototipo e implementación. P2: datos y análisis. P3: informe y validación."],
    ["Datos", "SWE-bench Lite [19]: 300 issues, de los que 86 cumplen el filtro de tamaño"],
    ["Costo de la API", f"DeepSeek: {n(tok_in, 0)} tokens de entrada y {n(tok_out, 0)} de salida en {n_gen} issues; 0,28 USD (saldo de 3,57 a 3,29 USD)"],
    ["Hardware", hw + ". Sin GPU. El lote de 60 casos tardó 7 min 41 s."],
    ["Software", "Herramientas de código abierto; ver la Tabla de herramientas de la Sección 4.1"],
], [3, 13], "Recursos")

# ---------- 4 ----------
H1("4. Conducción del experimento")
H2("4.1 Herramientas y stack tecnológico")
T(["Herramienta", "Versión", "Licencia", "Uso"], [
    ["Python", "3.13.5", "PSF", "Lenguaje del prototipo"],
    ["Radon", "6.0.1", "MIT", "Ciclomática e índice de mantenibilidad"],
    ["complexipy", "8.3.0", "MIT", "Complejidad cognitiva"],
    ["Ruff", "0.17.3", "MIT", "Reglas estáticas"],
    ["Pylint", "4.1.3", "GPL-2.0", "Solo R0401, importación cíclica"],
    ["jscpd", "5.4.2", "MIT", "Clones contra el proyecto completo"],
    ["unidiff", "1.0.1", "MIT", "Lectura de diffs"],
    ["datasets", "5.1.0", "Apache-2.0", "Descarga de SWE-bench Lite"],
    ["pandas / SciPy", "3.1.1 / 1.18.1", "BSD", "Consolidación y prueba de Wilcoxon"],
    ["statsmodels", "0.15.0", "BSD", "Corrección de Holm"],
    ["scikit-learn", "1.9.1", "BSD", "Kappa de Cohen"],
    ["matplotlib", "3.11.2", "PSF", "Gráficos"],
    ["SDK openai / API DeepSeek", "deepseek-v4-pro", "Servicio de pago", "Generación de parches"],
], [5, 3, 2.5, 6], "Herramientas y stack tecnológico")
H2("4.2 Diseño del prototipo")
P("debtguard es una herramienta de consola. Recibe un diff y el proyecto con el parche aplicado, y devuelve un JSON por "
  "caso y un código de salida. No usa un LLM para decidir, porque S04 y S08 muestran que no sería fiable, y por ello el "
  "mismo diff produce siempre el mismo resultado.")
F("flujo_prototipo.png", "Flujo del prototipo", 12.5)
F("arquitectura.png", "Arquitectura del prototipo y de los scripts del experimento", 12.5)
T(["Módulo", "Entrada", "Proceso", "Salida"], [
    ["ingest", "Diff", "Conserva líneas añadidas de Python de producción", "ChangeSet"],
    ["metrics/complexity", "Archivo antes y después", "Mide las funciones tocadas y compara con la versión previa", "Hallazgos y métricas"],
    ["metrics/static", "ChangeSet", "Ruff en líneas añadidas; R0401 si el cambio añade imports", "Hallazgos de regla"],
    ["metrics/clones", "ChangeSet y proyecto", "jscpd con 50 tokens mínimos; atribuye según el solapamiento", "Hallazgos de clon"],
    ["metrics/satd", "Archivo", "tokenize y expresión regular en comentarios nuevos", "Hallazgos SATD"],
    ["estimator", "Hallazgos y YAML", "Costo, índice de riesgo y veredicto", "Horas, IRD y veredicto"],
    ["report", "Assessment", "Serializa el resultado", "JSON y Markdown"],
], [3.5, 3.5, 7, 3], "Módulos del prototipo")
P("**Formato del JSON.** Cada reporte contiene caso_id, origen, modelo, kloc_cambiadas, metricas, hallazgos, deuda_min, "
  "deuda_horas, horas_kloc, debt_ratio, nota_sqale, ird, veredicto, versiones y errores. Cada hallazgo guarda archivo, línea, "
  "función, familia, regla, severidad, categoría, valor, valor previo, umbral, costo y detalle.")
P("**Modelo de costo.** La deuda de un cambio es la suma de los costos de sus hallazgos [20], con estos valores:")
T(["Familia", "Regla de costo"], [
    ["Regla estática", "Base × factor de severidad. Base: estilo 5, mantenibilidad 15, seguridad 30 min. Factor: baja 0,5; media 1; alta 2; crítica 4"],
    ["Complejidad cognitiva", "3 min por punto sobre el mayor valor entre el umbral (15) y la complejidad previa"],
    ["Complejidad ciclomática", "2 min por punto sobre el mayor valor entre el umbral (10) y la complejidad previa"],
    ["Función larga", "15 min, solo si el cambio cruza las 70 líneas"],
    ["Clon", "20 min por fragmento nuevo"],
    ["SATD", "10 min por comentario nuevo"],
], [4, 12], "Modelo de costo tipo SQALE")
P("La decisión principal del diseño es **cobrar solo lo que introduce el cambio**: una función ya compleja no genera deuda "
  "si el parche no aumenta su complejidad. El informe también da la nota SQALE (A–E), según la razón entre la deuda y el "
  "costo de desarrollo a 30 minutos por línea.")
P(f"**Índice de riesgo (IRD).** Promedia cinco componentes normalizados con el percentil 95 de una muestra humana de "
  f"calibración, ajena a la comparación: horas/KLOC, cognitiva máxima, clones, advertencias altas por KLOC y SATD/KLOC. Con "
  f"esa muestra de {th['n_calibracion']} issues, los umbrales quedaron en {n(th['ird']['advertir'], 1)} para ADVERTIR y "
  f"{n(th['ird']['bloquear'], 1)} para BLOQUEAR; un hallazgo de seguridad crítico también bloquea. El IRD no interviene en "
  "las hipótesis.")
H2("4.3 Implementación del experimento")
F("flujo_experimento.png", "Flujo del experimento", 8.5)
P("**Construcción y pruebas.** Las 27 pruebas automáticas pasan. Incluyen casos con deuda conocida y costos calculados a "
  "mano. La primera ejecución de calibración reveló dos defectos: un parche humano pequeño recibía 2 390 horas porque Pylint "
  "enumera de otro modo los ciclos existentes al añadir un import, y los saltos de línea de Windows alteraban los parches "
  "enviados a git. Ambos se corrigieron con pruebas de regresión antes de congelar la configuración y de medir ningún parche "
  "LLM.")
P(f"**Muestreo.** Con semilla 42 se barajaron los 86 issues cuyo parche humano tiene entre 10 y 300 líneas cambiadas de "
  f"código de producción. Se asignaron 30 a la comparación y 20 a la calibración, con un máximo de 4 por proyecto; los "
  f"restantes quedaron como reserva.")
P(f"**Generación con el LLM.** Se usó deepseek-v4-pro con temperatura 0, razonamiento desactivado y el mismo prompt para "
  f"todos los casos (Anexo C). El prompt incluye los archivos que toca el parche humano. Se probaron {n_gen} issues: "
  f"{n_mal} no produjeron un parche utilizable, ni siquiera tras un reintento, y {n_reserva} de los 30 finales salieron de "
  f"la reserva. Además, {laxos} de los 30 parches no se aplicaron en modo estricto y necesitaron "
  f"git apply --recount --ignore-whitespace.")
P("**Procedimiento del lote.** Para cada issue se hace checkout del commit base, se aplica el parche, se obtiene un diff "
  "canónico y se ejecuta el prototipo: primero con el parche humano y después con el del LLM. Se obtuvieron 60 JSON sin "
  "errores de herramienta.")
P("**Análisis.** Se aplicó la prueba de rangos con signo de Wilcoxon [24] bilateral, el delta de Cliff [25] y la "
  "corrección de Holm [26] sobre las siete pruebas principales, con α = 0,05. H0 se rechaza si el p ajustado es menor que "
  "0,05, |δ| ≥ 0,147 y el sentido coincide con la hipótesis.")

# ---------- 5 ----------
H1("5. Resultados")
P(f"Se analizaron 30 pares de 11 proyectos. **Ninguna hipótesis se confirmó:** todos los p ajustados valen al menos "
  f"{n(t.p_holm.min(), 3)} y todos los efectos son despreciables según |δ| < 0,147.")
filas = []
for f in t.itertuples():
    filas.append([f.hipotesis, NOMBRES[f.metrica], n(f.med_humano), n(f.med_llm), f"{f.llm_mayor} / {f.empates} / {f.llm_menor}",
                  n(f.W, 1), ps(f.p), ps(f.p_holm), n(f.cliff, 3), "No se rechaza H0" if f.decision.startswith("No") else f.decision])
T(["H", "Métrica", "Mediana humano", "Mediana LLM", "LLM > / = / <", "W", "p", "p Holm", "δ Cliff", "Decisión"], filas,
  [0.8, 2.8, 1.7, 1.7, 1.7, 1, 1.1, 1.1, 1.2, 2.2], "Resultados de H1–H4 (Wilcoxon, n = 30 pares)")
F("boxplots.png", "Distribución por origen. Cada punto es un parche; las escalas difieren entre paneles")
P(f"**Tamaño de los parches.** Es la diferencia más marcada, aunque se trata de un análisis exploratorio sin corrección "
  f"múltiple. El LLM añadió menos líneas en {llm_menos} de 30 pares (mediana {n(ex.loc['lineas_anadidas', 'med_llm'], 0)} "
  f"frente a {n(ex.loc['lineas_anadidas', 'med_humano'], 0)}; p = {ps(ex.loc['lineas_anadidas', 'p'])}; "
  f"δ = {n(ex.loc['lineas_anadidas', 'cliff'])}) y eliminó menos (mediana {n(ex.loc['lineas_eliminadas', 'med_llm'], 0)} "
  f"frente a {n(ex.loc['lineas_eliminadas', 'med_humano'], 0)}; p = {ps(ex.loc['lineas_eliminadas', 'p'])}).")
T(["Métrica exploratoria", "Media humano", "Media LLM", "p sin ajustar", "δ Cliff"],
  [[{"delta_cognitiva": "Aumento de cognitiva", "delta_ciclomatica": "Aumento de ciclomática", "deuda_horas": "Deuda por parche (horas)",
     "lineas_anadidas": "Líneas añadidas", "lineas_eliminadas": "Líneas eliminadas"}[m],
    n(ex.loc[m, "media_humano"]), n(ex.loc[m, "media_llm"]), ps(ex.loc[m, "p"]), n(ex.loc[m, "cliff"], 3)]
   for m in ("delta_cognitiva", "delta_ciclomatica", "deuda_horas", "lineas_anadidas", "lineas_eliminadas")],
  [6, 2.5, 2.5, 2.5, 2], "Análisis exploratorio, sin corrección múltiple")
P(f"**Deuda total.** Sumando los 30 parches, el código humano acumula {n(h_total, 1)} h y el del LLM {n(l_total, 1)} h. "
  f"Por tamaño ocurre lo contrario: {n(h_total / h_lin * 1000, 1)} h/KLOC frente a {n(l_total / l_lin * 1000, 1)} h/KLOC. "
  f"Ninguna de las dos lecturas es concluyente: con parches de pocas líneas, un solo hallazgo cambia mucho la razón por "
  f"KLOC. Por eso se reportan ambas.")
T(["Origen", "Complejidad (min)", "Reglas (min)", "Clones (min)", "SATD (min)", "Total (h)", "Líneas añadidas", "Hallazgos"],
  [[{"humano": "Humano", "LLM": "LLM"}[o], n(comp.loc[o, "min_complejidad"], 1), n(comp.loc[o, "min_regla"], 1), n(comp.loc[o, "min_clon"], 1),
    n(comp.loc[o, "min_satd"], 1), n(comp.loc[o, "deuda_horas"], 1), int(comp.loc[o, "lineas_anadidas"]), int(comp.loc[o, "n_hallazgos"])]
   for o in ("humano", "LLM")], [2, 2.3, 2, 2, 2, 2, 2.2, 2], "Composición de la deuda estimada en los 30 pares")
P("**Sensibilidad de costos.** Multiplicar todos los costos por un mismo factor no altera los rangos ni, por tanto, la "
  "prueba. Por eso se varió ±25 % cada familia por separado. La conclusión de H4 no cambia en ningún escenario.")
T(["Familia variada", "Factor", "Mediana humano (h/KLOC)", "Mediana LLM (h/KLOC)", "p", "δ Cliff"],
  [[{"complejidad": "Complejidad", "regla": "Reglas", "clon": "Clones", "satd": "SATD"}[f.familia], n(f.factor), n(f.med_humano), n(f.med_llm), ps(f.p), n(f.cliff, 3)]
   for f in sens.itertuples()], [3, 1.5, 3.5, 3.5, 1.5, 1.5], "Sensibilidad de horas/KLOC a los costos (±25 %)")
P(f"**Veredictos del prototipo.** Humano: {ver.loc['humano', 'ACEPTAR']} aceptar, {ver.loc['humano', 'ADVERTIR']} advertir y "
  f"{ver.loc['humano', 'BLOQUEAR']} bloquear. LLM: {ver.loc['LLM', 'ACEPTAR']} aceptar, {ver.loc['LLM', 'ADVERTIR']} advertir y "
  f"{ver.loc['LLM', 'BLOQUEAR']} bloquear. Notas SQALE A/B/C/D/E: humano "
  f"{'/'.join(str(sq.loc['humano', c]) for c in 'ABCDE')}; LLM {'/'.join(str(sq.loc['LLM', c]) for c in 'ABCDE')}.")
sim = eje.similitud
P(f"**Memorización.** La similitud entre las líneas nuevas de cada par tuvo una mediana de {n(sim.median())} y un máximo de "
  f"{n(sim.max())}. Ningún caso superó 0,9, de modo que no hubo que excluir pares ni hay indicios de que el modelo copiara "
  "el parche de referencia.")
fam = cl.familia.value_counts()
P(f"**Validación del prototipo.** Las pruebas automáticas de los detectores pasan (27 de 27). Se seleccionaron 60 de los 64 "
  f"hallazgos para revisión a ciegas: {fam.get('complejidad', 0)} de complejidad, {fam.get('regla', 0)} de reglas, "
  f"{fam.get('clon', 0)} de clones y {fam.get('satd', 0)} de SATD. La muestra no pudo equilibrarse porque hay pocos clones y "
  "casi ningún SATD.")
T(["Medida", "Resultado", "Referencia"], [
    ["Kappa de Cohen entre revisores", "[[P2 y P3 etiquetan; python experiments/validation.py calcular]]", "> 0,6 aceptable; S09: 0,82–0,94"],
    ["Precisión global y por familia", "[[se calcula tras resolver desacuerdos]]", "S08: 98 % con validación"],
    ["Error del costo estimado", "[[corregir y cronometrar 10–15 hallazgos]]", "Error absoluto medio, en minutos"],
], [5, 7, 4], "Validación manual")

# ---------- 6 ----------
H1("6. Conclusiones")
P("Se construyó un prototipo determinista que detecta la deuda introducida por un diff y la expresa en horas, y se usó "
  "para comparar 30 parches humanos con 30 generados por DeepSeek-V4-Pro sobre los mismos issues.")
P("**Respuesta a cada hipótesis:**")
B(f"**H1 (complejidad): no se confirma.** Cognitiva: p Holm = {ps(t.p_holm[0])}, δ = {n(t.cliff[0], 3)}. Ciclomática: p Holm = {ps(t.p_holm[1])}, δ = {n(t.cliff[1], 3)}.")
B(f"**H2 (clones): no se confirma.** Solo 2 de 30 pares difieren; p Holm = {ps(t.p_holm[2])}.")
B(f"**H3 (advertencias y mantenibilidad): no se confirma.** Advertencias: p Holm = {ps(t.p_holm[3])}. Mantenibilidad: p Holm = {ps(t.p_holm[4])}.")
B(f"**H4 (horas y SATD): no se confirma.** Horas/KLOC: p Holm = {ps(t.p_holm[5])}, δ = {n(t.cliff[5], 3)}, resultado estable ante la variación de costos. SATD/KLOC: p Holm = {ps(t.p_holm[6])}; hubo un solo comentario en los 60 parches.")
P("No haber detectado diferencias no prueba que no existan. Con 30 pares solo se pueden detectar efectos medianos o grandes.")
H2("Discusión frente a S01–S10")
T(["Estudio", "Qué reporta", "Qué se observó aquí", "Lectura"], [
    ["S01", "+39 % cognitiva y +18 % advertencias tras adoptar agentes", "Sin diferencia en cognitiva ni advertencias", "No se replica; S01 mide agentes a nivel de repositorio y aquí un chat acotado"],
    ["S02", "Los agentes admiten poca deuda", "Un SATD humano y ninguno del LLM", "Coherente, pero sin datos suficientes"],
    ["S03", "Radon apenas distingue; los humanos eliminan más; redundancia 1,87×", "Ciclomática y mantenibilidad sin diferencia; los humanos eliminan más", "Coincide; la redundancia semántica no se midió"],
    ["S04, S08", "El LLM aislado no es fiable", "Prototipo determinista; 7 de 37 issues sin parche utilizable", "Respalda no delegar en el LLM"],
    ["S05", "Deuda de comprensión, propuesta conceptual", "No medida", "Fuera de alcance"],
    ["S06", "423 frente a 30 recomendaciones; 360–365 por importación cíclica", "Ningún ciclo nuevo en los 60 parches", "No se replica; difieren el modelo, la herramienta y la definición de ciclo nuevo"],
    ["S07", "Menos días de deuda en lo generado (tarea de traducción)", "Menos horas totales en el LLM, sin diferencia por KLOC", "Coincide en lo absoluto; la deuda sigue el tamaño"],
    ["S09, S10", "SATD y TODO en generación con Copilot", "SATD casi ausente", "La muestra no permite evaluarlo"],
], [1.6, 5, 4.6, 5], "Comparación con los estudios primarios")
P("La explicación más plausible de las diferencias con S01 y S06 es el contexto: aquí el LLM recibió los archivos exactos y "
  "produjo cambios muy pequeños, mientras que aquellos estudios observan agentes o parches que recorren el repositorio. Un "
  "parche mínimo apenas puede añadir complejidad. Es una hipótesis para probar, no una conclusión de este experimento.")
H2("Amenazas a la validez")
T(["Tipo", "Amenaza", "Tratamiento"], [
    ["Constructo", "No se comprobó si los parches resuelven el issue; uno incorrecto puede ser más corto y tener menos deuda", "Declarado; es la amenaza principal y el primer trabajo futuro"],
    ["Constructo", "El prompt incluye los archivos del parche humano, lo que facilita la tarea y acota el cambio", "Decisión de diseño declarada"],
    ["Constructo", "Costos definidos por el equipo", "Sensibilidad ±25 % por familia; validación cronometrada pendiente"],
    ["Constructo", "Falsos positivos de las herramientas", "Revisión manual pendiente"],
    ["Constructo", "Clones semánticos no medidos: jscpd no detecta el Tipo 4, justamente el que S03 asocia a los LLMs", "H2 solo cubre clones sintácticos"],
    ["Constructo", "El índice de mantenibilidad vale 0 en archivos muy grandes, y un parche pequeño apenas lo mueve", "Se reporta; se lee con cautela"],
    ["Interna", f"Selección: {n_mal} issues sin parche utilizable reemplazados desde la reserva", "Tasa reportada; podría favorecer al LLM si fallan los issues más difíciles"],
    ["Interna", f"{laxos} de 30 parches requirieron aplicación laxa", "Se aplica el mismo procedimiento y se conserva el diff canónico"],
    ["Interna", "Memorización del conjunto de datos", "Similitud máxima 0,68; ningún caso sobre 0,9"],
    ["Interna", "Umbrales circulares", "Muestra de calibración separada"],
    ["Conclusión", "Muestra pequeña y muchos empates (19 pares en advertencias, 28 en clones)", "Pruebas no paramétricas, efecto y conteos de empates"],
    ["Conclusión", "Razones por KLOC inestables en parches de pocas líneas", "Se reportan también valores absolutos"],
    ["Externa", "Un solo LLM, sin razonamiento, un solo lenguaje y 11 proyectos de código abierto", "No se generaliza a agentes, a otros modelos ni a la industria"],
    ["Fiabilidad", "No determinismo y cambios del servicio del LLM", "Temperatura 0; respuestas crudas, modelo, fecha y huella guardados"],
], [2, 8, 6.5], "Amenazas a la validez [28]")
H2("Limitaciones")
for x in ("El prototipo solo analiza Python y no mide clones semánticos ni acoplamiento.",
          "El IRD normaliza SATD y advertencias altas con un percentil 95 igual a 0, por lo que un único hallazgo aporta todo su componente. Con la calibración actual, un solo TODO en un cambio de una línea basta para BLOQUEAR, de modo que el veredicto necesita más datos de calibración antes de usarse en un flujo real.",
          "Con la validación manual pendiente, todavía no se conoce la precisión de las alertas."):
    B(x)
H2("Trabajo futuro")
for x in ("Ejecutar las pruebas de SWE-bench para repetir el análisis solo con parches correctos.",
          "Controlar el tamaño del cambio, o comparar parches de tamaño similar.",
          "Comparar chat, IDE y agentes sobre los mismos issues, usando predicciones públicas de agentes.",
          "Añadir clones semánticos con embeddings, medición de acoplamiento y otros lenguajes.",
          "Integrar el prototipo como hook de pre-commit o GitHub Action, y calibrar los costos con correcciones reales."):
    B(x)

# ---------- Referencias ----------
H1("Referencias")
REFS = [
    'H. Washizaki, Ed., Guide to the Software Engineering Body of Knowledge (SWEBOK Guide), Version 4.0a. IEEE Computer Society, 2026.',
    'W. Cunningham, "The WyCash portfolio management system," in Addendum to the Proc. OOPSLA \'92, 1992, pp. 29–30, doi: 10.1145/157709.157715.',
    'P. Avgeriou, P. Kruchten, I. Ozkaya, and C. Seaman, "Managing technical debt in software engineering (Dagstuhl Seminar 16162)," Dagstuhl Reports, vol. 6, no. 4, pp. 110–138, 2016, doi: 10.4230/DagRep.6.4.110.',
    'A. Potdar and E. Shihab, "An exploratory study on self-admitted technical debt," in Proc. IEEE ICSME, 2014, pp. 91–100, doi: 10.1109/ICSME.2014.31.',
    '[S01] S. Agarwal, H. He, and B. Vasilescu, "AI IDEs or autonomous agents? Measuring the impact of coding agents on software development," in Proc. MSR \'26, 2026, doi: 10.1145/3793302.3793589.',
    '[S02] Z. Brahmi, A. Ouni, M. Sayagh, and M. A. Saied, "Characterizing self-admitted technical debt generated by AI coding agents," in Proc. MSR \'26, 2026, pp. 852–856, doi: 10.1145/3793302.3793588.',
    '[S03] H. Huang et al., "More code, less reuse: Investigation on code quality and reviewer sentiment towards AI-generated pull requests," in Proc. MSR \'26, 2026, pp. 1024–1028, doi: 10.1145/3793302.3793622.',
    '[S04] Q. Li et al., "IMPACT: Identifying and classifying multiple sourced and categorized self-admitted technical debts," ACM TOSEM, vol. 35, no. 4, Art. no. 102, 2026, doi: 10.1145/3747180.',
    '[S05] M. S. Patel, R. Dhawan, L. Bramhanwade, and D. J. Mishra, "Code comprehension gaps in AI-assisted development," IEEE Access, vol. 14, pp. 66740–66757, 2026, doi: 10.1109/ACCESS.2026.3689574.',
    '[S06] X. Sun, D. Ståhl, K. Sandahl, and C. Kessler, "Quality assurance of LLM-generated code: Addressing non-functional quality characteristics," J. Systems and Software, vol. 238, Art. no. 112885, 2026, doi: 10.1016/j.jss.2026.112885.',
    '[S07] V. Bhutani, F. G. Toosi, and J. Buckley, "Analysing software quality of AI-translated code," Applied Computer Systems, vol. 30, no. 1, pp. 105–121, 2025, doi: 10.2478/acss-2025-0013.',
    '[S08] A. Tornhill, M. Borg, N. Hagatulah, and E. Söderberg, "ACE: Automated technical debt remediation with validated large language model refactorings," in Companion Proc. FSE \'25, 2025, pp. 1318–1324, doi: 10.1145/3696630.3730565.',
    '[S09] D. OBrien et al., "Are prompt engineering and TODO comments friends or foes? An evaluation on GitHub Copilot," in Proc. ICSE \'24, 2024, doi: 10.1145/3597503.3639176.',
    '[S10] H. Wang et al., "Just-in-time TODO-missed commits detection," IEEE Trans. Software Engineering, vol. 50, no. 11, pp. 2732–2752, 2024, doi: 10.1109/TSE.2024.3405005.',
    'S. Moreschini et al., "The evolution of technical debt from DevOps to generative AI," J. Systems and Software, vol. 231, Art. no. 112599, 2026, doi: 10.1016/j.jss.2025.112599.',
    'S. Gosu, D. Feitosa, and P. Avgeriou, "The use of generative AI in technical debt management," Information and Software Technology, vol. 199, Art. no. 108257, 2026, doi: 10.1016/j.infsof.2026.108257.',
    'A. Abdulaziz, R. Sonbol, and M. Alnoukari, "Automated detection of self-admitted technical debt," IEEE Access, vol. 14, pp. 20803–20825, 2026, doi: 10.1109/ACCESS.2026.3661069.',
    'I. Kosmas, T. Papadopoulos, and C. Michalakelis, "Machine learning lifecycle: A survey," AppliedMath, vol. 6, no. 7, Art. no. 113, 2026, doi: 10.3390/appliedmath6070113.',
    'C. E. Jimenez et al., "SWE-bench: Can language models resolve real-world GitHub issues?," in Proc. ICLR, 2024.',
    'J.-L. Letouzey, "The SQALE method for evaluating technical debt," in Proc. 3rd Int. Workshop on Managing Technical Debt, 2012, pp. 31–36.',
    'G. A. Campbell, "Cognitive complexity: An overview and evaluation," in Proc. Int. Conf. Technical Debt, 2018, pp. 57–58.',
    'T. J. McCabe, "A complexity measure," IEEE Trans. Software Engineering, vol. SE-2, no. 4, pp. 308–320, 1976.',
    'P. Oman and J. Hagemeister, "Metrics for assessing a software system\'s maintainability," in Proc. Conf. Software Maintenance, 1992, pp. 337–344.',
    'F. Wilcoxon, "Individual comparisons by ranking methods," Biometrics Bulletin, vol. 1, no. 6, pp. 80–83, 1945.',
    'N. Cliff, "Dominance statistics: Ordinal analyses to answer ordinal questions," Psychological Bulletin, vol. 114, no. 3, pp. 494–509, 1993.',
    'S. Holm, "A simple sequentially rejective multiple test procedure," Scandinavian J. Statistics, vol. 6, no. 2, pp. 65–70, 1979.',
    'J. Cohen, "A coefficient of agreement for nominal scales," Educational and Psychological Measurement, vol. 20, no. 1, pp. 37–46, 1960.',
    'C. Wohlin et al., Experimentation in Software Engineering. Springer, 2012.',
    'A. M. Carrasco Choque, A. R. Caceres Pari, K. Chancuaña Alvis, and L. E. Yana Agramonte, "Deuda técnica en el desarrollo de software asistido por LLMs: un estudio de mapeo sistemático," informe del Hito 1, 2026.',
]
for i, r in enumerate(REFS, 1):
    p = P(f"[{i}] {r}")
    p.paragraph_format.left_indent = Cm(0.9)
    p.paragraph_format.first_line_indent = Cm(-0.9)

# ---------- Anexos ----------
H1("Anexos")
H2("Anexo A. Repositorio")
P("Código, datos, reportes y comandos de reproducción: [[enlace de GitHub, tras publicar el repositorio; etiqueta v1.0-experimento]].")
H2("Anexo B. Plantillas de validación")
P("data/validacion/alertas_P2.csv y alertas_P3.csv contienen las 60 alertas sin indicar el origen. Cada revisor completa "
  "la columna etiqueta_VP_FP respondiendo: ¿un desarrollador razonable cambiaría esto en una revisión de código? Un tercero "
  "resuelve los desacuerdos en desacuerdos_resueltos.csv.")
H2("Anexo C. Prompt fijo")
for lin in ("Eres un desarrollador. Repositorio: {repo}. Resuelve el siguiente issue.",
            "Devuelve SOLO un parche en formato unified diff aplicable con `git apply`.",
            "Issue: {problem_statement}", "Archivos relevantes: {contenido de los archivos que toca el parche humano}"):
    r = doc.add_paragraph().add_run(lin)
    r.font.name, r.font.size = "Consolas", Pt(9)
H2("Anexo D. Casos (casos.csv)")
casos = pd.read_csv(DATA / "casos.csv").set_index("instance_id")
T(["Issue", "Proyecto", "Líneas del parche humano", "Origen en la muestra", "Modo de aplicación LLM", "Similitud"],
  [[f.instance_id, casos.loc[f.instance_id, "repo"], int(casos.loc[f.instance_id, "lineas_humano"]),
    {"comparacion": "Comparación", "reserva": "Reserva"}[f.rol], {"laxo": "Laxo", "estricto": "Estricto"}[f.modo],
    n(eje.set_index("instance_id").loc[f.instance_id, "similitud"])] for f in sel.itertuples()],
  [5, 3.6, 1.8, 2.5, 1.9, 1.7], "Los 30 pares analizados")
H2("Anexo E. Declaración de uso de asistentes de IA")
P("El prototipo, la ejecución del análisis y un primer borrador de este informe se realizaron con ayuda de Claude Code "
  "(Claude Opus 5.5). Los parches del experimento los generó únicamente DeepSeek-V4-Pro. La validación manual corresponde a "
  "los revisores humanos del equipo. [[el equipo confirma aquí que revisó y asume el contenido final]]")

# Pie de pagina con numero y actualizacion del indice al abrir
pp = sec.footer.paragraphs[0]
pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
campo(pp, "PAGE")
doc.save(SALIDA)
print(SALIDA)
