"""Informe final en formato APA 7 con la estructura pedida por el curso. Las cifras se leen de los datos del repositorio."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
DATA, FIG, CAP = RAIZ / "data", RAIZ / "docs" / "figuras", RAIZ / "estudio_caso" / "capturas"
SALIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "entregables" / "Informe_Final_Debtguard_APA.docx"
TMP = Path(__file__).parent / "_tmp"
ANCHO = 16.0
REPO = "https://github.com/AngelCaceresPari01/Debtguard"

# ================= Datos =================
res = pd.read_csv(DATA / "resultados.csv")
t = pd.read_csv(DATA / "tabla_hipotesis.csv")
ex = pd.read_csv(DATA / "tabla_exploratoria.csv").set_index("metrica")
sens = pd.read_csv(DATA / "sensibilidad_costos.csv")
comp = pd.read_csv(DATA / "composicion_deuda.csv").set_index("origen")
ver = pd.read_csv(DATA / "veredictos.csv").set_index("origen")
sq = pd.read_csv(DATA / "notas_sqale.csv").set_index("origen")
gen = pd.read_csv(DATA / "generacion_llm.csv")
eje = pd.read_csv(DATA / "ejecucion_comparacion.csv").set_index("instance_id")
cor = pd.read_csv(DATA / "correccion" / "correccion.csv").set_index("instance_id")
tc = pd.read_csv(DATA / "correccion" / "tabla_solo_correctos.csv")
fechas = pd.read_csv(DATA / "fechas_base.csv").set_index("instance_id")
t22 = pd.read_csv(DATA / "tabla_antes_2022.csv")
v11 = pd.read_csv(DATA / "v11" / "tabla_v11.csv")
v11tot = pd.read_csv(DATA / "v11" / "totales_v11.csv").set_index("origen")
v10v11 = pd.read_csv(DATA / "v11" / "v10_vs_v11.csv")
casos = pd.read_csv(DATA / "casos.csv").set_index("instance_id")
th = yaml.safe_load((RAIZ / "config" / "thresholds.yaml").read_text(encoding="utf-8"))
ec = json.loads((RAIZ / "estudio_caso" / "datos" / "resultado_completo.json").read_text(encoding="utf-8"))
ec_cmp = json.loads((RAIZ / "estudio_caso" / "datos" / "comparacion_ia.json").read_text(encoding="utf-8"))
ejemplo = json.loads((RAIZ / "reports" / "pytest-dev__pytest-7373_llm.json").read_text(encoding="utf-8"))

sel = gen[gen.elegido]
n_ok = int(cor.llm_resuelto.eq(True).sum())
n_no_corre = int((cor.llm_aplica != True).sum())  # noqa: E712
n_prev = int((cor.llm_p2p_mal > 0).sum())
por = res.set_index(["origen", "instance_id"])
ids = sorted(res.instance_id.unique())
w = res.pivot(index="instance_id", columns="origen", values="lineas_anadidas")
ceros = int(((res[res.origen == "humano"].set_index("instance_id").deuda_horas == 0)
             & (res[res.origen == "LLM"].set_index("instance_id").deuda_horas == 0)).sum())
sub_ok = res[res.instance_id.isin(cor.index[cor.llm_resuelto.eq(True)])]
tot_ok = sub_ok.groupby("origen")[["deuda_horas", "lineas_anadidas"]].sum()
llm_cor = res[res.origen == "LLM"].set_index("instance_id").join(cor.llm_resuelto)
med_ok = llm_cor[llm_cor.llm_resuelto.eq(True)].lineas_anadidas.median()
med_mal = llm_cor[~llm_cor.llm_resuelto.eq(True)].lineas_anadidas.median()
n_2022 = int((fechas.fecha_base >= "2022").sum())
n_2023 = int((fechas.fecha_base >= "2023").sum())
codigo, hist = ec["codigo"], ec["historial"]
cm = codigo["metricas"]
NOMBRES = {"cognitiva_max": "Complejidad cognitiva máxima", "ciclomatica_max": "Complejidad ciclomática máxima",
           "clones": "Clones nuevos", "advertencias_kloc": "Advertencias por KLOC", "mi_min": "Índice de mantenibilidad",
           "horas_kloc": "Horas por KLOC", "satd_kloc": "SATD por KLOC"}
PROBLEMAS = {
    "astropy__astropy-14182": "Filas de encabezado al exportar tablas en formato RST",
    "django__django-12983": "slugify() debe quitar guiones y guiones bajos de los extremos",
    "django__django-13315": "limit_choices_to puede mostrar opciones duplicadas",
    "django__django-14752": "Campos adicionales en el autocompletado del admin",
    "django__django-16229": "Valores por defecto calculados que no se propagan en formularios",
    "matplotlib__matplotlib-24265": "Error al pedir el estilo seaborn-colorblind en la versión 3.6.1",
    "matplotlib__matplotlib-24970": "Avisos de funciones obsoletas con NumPy 1.24",
    "matplotlib__matplotlib-25332": "No se puede serializar una figura tras align_labels()",
    "matplotlib__matplotlib-26011": "xlim_changed no se emite en ejes compartidos",
    "pallets__flask-4045": "Error si el nombre de un blueprint contiene un punto",
    "pallets__flask-4992": "Parámetro de modo de archivo en Config.from_file()",
    "pallets__flask-5063": "Mostrar el subdominio de cada ruta en flask routes",
    "psf__requests-3362": "iter_content(decode_unicode=True) devuelve bytes",
    "pydata__xarray-4493": "Dataset.update pierde la división en bloques de dask",
    "pylint-dev__pylint-7114": "Falla si un paquete contiene un módulo con su mismo nombre",
    "pylint-dev__pylint-7228": "Error con \\p{Han} en una expresión regular de configuración",
    "pytest-dev__pytest-5221": "Mostrar el alcance de los fixtures con --fixtures",
    "pytest-dev__pytest-5495": "Mensaje confuso al comparar cadenas de bytes",
    "pytest-dev__pytest-7220": "Ruta incorrecta si un fixture cambia de directorio",
    "pytest-dev__pytest-7373": "Caché incorrecta al evaluar skipif y xfail",
    "scikit-learn__scikit-learn-10297": "store_cv_values en RidgeClassifierCV",
    "scikit-learn__scikit-learn-11040": "Falta validar n_neighbors decimal",
    "scikit-learn__scikit-learn-13497": "Comparación de texto con un array en _estimate_mi",
    "scikit-learn__scikit-learn-14092": "NCA falla en GridSearch por validación estricta",
    "sphinx-doc__sphinx-8282": "autodoc_typehints no afecta a funciones sobrecargadas",
    "sphinx-doc__sphinx-8801": "Atributo anotado en una superclase tratado como no documentado",
    "sympy__sympy-12419": "La suma de los elementos de una matriz identidad da cero",
    "sympy__sympy-13031": "Cambio de comportamiento de hstack y vstack en la versión 1.1",
    "sympy__sympy-14308": "Los vectores se imprimen mal en modo pretty",
    "sympy__sympy-18835": "uniq no avisa si la lista se modifica al recorrerla",
}


def n(x, d=2) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def nc(x) -> str:
    s = n(x, 2)
    return s.rstrip("0").rstrip(",") if "," in s else s


def rbc(df: pd.DataFrame, m: str) -> tuple[float, int]:
    """Correlacion biserial por rangos para pares (Kerby, 2014): (T+ - T-) / (T+ + T-) sobre las diferencias no nulas."""
    from scipy.stats import rankdata
    wv = df.pivot(index="instance_id", columns="origen", values=m).dropna()
    d = (wv["LLM"] - wv["humano"]).to_numpy(float)
    d = d[d != 0]
    if not len(d):
        return 0.0, 0
    r = rankdata(abs(d))
    tp, tn = r[d > 0].sum(), r[d < 0].sum()
    return (tp - tn) / (tp + tn), len(d)


def p0(x, d=3) -> str:
    """Valores acotados por 1 (p, delta, similitud) sin cero inicial, como pide APA."""
    if x is None or pd.isna(x):
        return "—"
    if 0 < x < 0.001:
        return "< ,001"
    s = n(x, d)
    return s.replace("0,", ",", 1) if s.startswith(("0,", "-0,")) else s


# ================= Formato APA =================
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
for lado in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, lado, Cm(2.54))
normal = doc.styles["Normal"]
normal.font.name, normal.font.size = "Times New Roman", Pt(12)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
normal.paragraph_format.line_spacing = 2.0
normal.paragraph_format.space_after = Pt(0)
normal.paragraph_format.space_before = Pt(0)
for nivel, (centrado, cursiva) in {1: (True, False), 2: (False, False), 3: (False, True)}.items():
    s = doc.styles[f"Heading {nivel}"]
    s.font.name, s.font.size, s.font.bold, s.font.italic = "Times New Roman", Pt(12), True, cursiva
    s.font.color.rgb = None
    rf = s.element.rPr.rFonts
    for atr in list(rf.attrib):
        del rf.attrib[atr]
    rf.set(qn("w:ascii"), "Times New Roman")
    rf.set(qn("w:hAnsi"), "Times New Roman")
    pf = s.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER if centrado else WD_ALIGN_PARAGRAPH.LEFT
    pf.space_before, pf.space_after, pf.line_spacing, pf.keep_with_next = Pt(0), Pt(0), 2.0, True
lista = doc.styles["List Bullet"]
lista.font.name, lista.font.size = "Times New Roman", Pt(12)
lista.paragraph_format.line_spacing = 2.0
cont = {"Tabla": 0, "Figura": 0}


def campo(p, instruccion, texto="1"):
    for tipo in ("begin", "instr", "separate", "texto", "end"):
        r = p.add_run()
        if tipo == "instr":
            i = OxmlElement("w:instrText")
            i.set(qn("xml:space"), "preserve")
            i.text = instruccion
            r._r.append(i)
        elif tipo == "texto":
            r.text = texto
        else:
            f = OxmlElement("w:fldChar")
            f.set(qn("w:fldCharType"), tipo)
            r._r.append(f)


def _runs(p, texto, tam=None):
    """**negrita** y _cursiva_ dentro del texto."""
    negrita = cursiva = False
    trozo = ""
    i = 0
    while i < len(texto):
        if texto.startswith("**", i) or texto[i] == "_" and (i == 0 or not texto[i - 1].isalnum()) or texto[i] == "_" and (i + 1 == len(texto) or not texto[i + 1].isalnum()):
            if trozo:
                r = p.add_run(trozo)
                r.bold, r.italic = negrita, cursiva
                if tam:
                    r.font.size = Pt(tam)
                trozo = ""
            if texto.startswith("**", i):
                negrita = not negrita
                i += 2
            else:
                cursiva = not cursiva
                i += 1
            continue
        trozo += texto[i]
        i += 1
    if trozo:
        r = p.add_run(trozo)
        r.bold, r.italic = negrita, cursiva
        if tam:
            r.font.size = Pt(tam)


def P(texto, sangria=True, centro=False):
    p = doc.add_paragraph()
    if centro:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif sangria:
        p.paragraph_format.first_line_indent = Cm(1.27)
    _runs(p, texto)
    return p


def B(texto):
    p = doc.add_paragraph(style="List Bullet")
    _runs(p, texto)
    return p


def H(nivel, texto, nueva=False):
    h = doc.add_heading(texto, nivel)
    h.paragraph_format.page_break_before = nueva
    return h


def rotulo(tipo, titulo):
    cont[tipo] += 1
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.add_run(f"{tipo} {cont[tipo]}").bold = True
    q = doc.add_paragraph()
    q.paragraph_format.keep_with_next = True
    q.add_run(titulo).italic = True
    return cont[tipo]


def nota(texto):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_after = Pt(12)
    r = p.add_run("Nota. ")
    r.italic, r.font.size = True, Pt(10)
    _runs(p, texto, 10)


def T(cab, filas, anchos, titulo, fuente_nota, tam=9.5):
    num = rotulo("Tabla", titulo)
    total = sum(anchos)
    anchos = [a * ANCHO / total for a in anchos]
    tb = doc.add_table(rows=1, cols=len(cab))
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    tb.autofit = False

    def borde(celda, lados):
        tcpr = celda._tc.get_or_add_tcPr()
        b = OxmlElement("w:tcBorders")
        for lado in ("top", "bottom", "left", "right"):
            e = OxmlElement(f"w:{lado}")
            e.set(qn("w:val"), "single" if lado in lados else "nil")
            e.set(qn("w:sz"), "6")
            e.set(qn("w:color"), "000000")
            b.append(e)
        tcpr.append(b)

    def celda(c, x, cab_=False):
        c.text = ""
        p = c.paragraphs[0]
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.first_line_indent = Cm(0)
        txt = str(x)
        r = p.add_run(txt.strip("*"))
        r.font.size, r.bold = Pt(tam), cab_ or txt.startswith("**")

    for i, x in enumerate(cab):
        celda(tb.rows[0].cells[i], x, True)
    tb.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for f in filas:
        cs = tb.add_row().cells
        for i, x in enumerate(f):
            celda(cs[i], x)
    ultima = len(tb.rows) - 1
    for k, fila in enumerate(tb.rows):
        fila._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for i, a in enumerate(anchos):
            fila.cells[i].width = Cm(a)
            lados = (["top", "bottom"] if k == 0 else []) + (["bottom"] if k == ultima else [])
            borde(fila.cells[i], lados)
    nota(fuente_nota)
    return num


def F(ruta, titulo, nota_texto, ancho=ANCHO, recorte=None):
    origen = Path(ruta)
    if recorte:
        TMP.mkdir(exist_ok=True)
        im = Image.open(origen)
        destino = TMP / f"{origen.stem}_{recorte}.png"
        im.crop((0, 0, im.width, min(im.height, recorte))).save(destino)
        origen = destino
    num = rotulo("Figura", titulo)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.line_spacing = 1.0
    p.add_run().add_picture(str(origen), width=Cm(ancho))
    nota(nota_texto)
    return num


def codigo_bloque(texto, tam=8.5):
    for linea in texto.splitlines():
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(linea)
        r.font.name, r.font.size = "Consolas", Pt(tam)
    doc.add_paragraph().paragraph_format.line_spacing = 1.0


# Numero de pagina arriba a la derecha (APA)
cab = sec.header.paragraphs[0]
cab.alignment = WD_ALIGN_PARAGRAPH.RIGHT
campo(cab, "PAGE")

# ================= 1. Caratula =================
for _ in range(3):
    doc.add_paragraph()
p = P("**Debtguard: Detección y Estimación en Horas de la Deuda Técnica en Código Generado por Modelos de Lenguaje Grandes**", centro=True)
P("Prototipo y experimento pareado con SWE-bench Lite", centro=True)
doc.add_paragraph()
for a in ("Arles Melvin Carrasco Choque", "Angel Raul Caceres Pari", "Klismann Chancuaña Alvis", "Luis Efrain Yana Agramonte"):
    P(a, centro=True)
doc.add_paragraph()
P("Universidad Nacional de San Agustín de Arequipa", centro=True)
P("Tópicos Avanzados de Ingeniería de Sistemas", centro=True)
P("Docente: Robert Edison Arisaca Mamani", centro=True)
P("10 de noviembre de 2026", centro=True)

# ================= 2. Tabla de contenido =================
H(1, "Tabla de Contenido", nueva=True)
campo(doc.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u', "(actualizar)")

# ================= 3. Introduccion =================
H(1, "Introducción", nueva=True)
P("La deuda técnica es el trabajo futuro que deja un código difícil de mantener: funciones demasiado enredadas, fragmentos "
  "copiados, malas prácticas o tareas marcadas como pendientes. Cunningham (1992) la describió con una metáfora financiera: "
  "entregar código imperfecto para avanzar rápido equivale a pedir un préstamo cuyo interés se paga como esfuerzo adicional "
  "en cada cambio posterior. La Guía del Cuerpo de Conocimiento de la Ingeniería de Software (SWEBOK) la ubica en el área de "
  "mantenimiento y propone estimarla a partir del tamaño, la complejidad y las violaciones de buenas prácticas (Washizaki, 2026).")
P("En los últimos años, los asistentes basados en modelos de lenguaje grandes (LLMs) y los agentes de programación pasaron a "
  "escribir una parte creciente del código. La revisión sistemática que el equipo realizó en el Hito 1 (Carrasco Choque et al., "
  "2026) reunió diez estudios primarios y encontró que ese código tiende a acumular más complejidad y más problemas de "
  "mantenibilidad (Agarwal et al., 2026; Huang et al., 2026; Sun et al., 2026), que esa deuda es menos visible (Brahmi et al., "
  "2026) y que un LLM sin validación no es fiable para detectarla ni corregirla (Li et al., 2026; Tornhill et al., 2025). La "
  "revisión identificó además un vacío directamente ligado al SWEBOK: casi ningún estudio estima la deuda en tiempo o costo.")
P("Este informe presenta la parte experimental del curso. Se construyó **debtguard**, un prototipo que recibe un cambio de "
  "código Python, detecta la deuda que ese cambio introduce y la expresa en horas de corrección con un modelo de tipo SQALE "
  "(Letouzey, 2012). Con él se realizó un experimento pareado sobre 30 problemas reales de SWE-bench Lite (Jimenez et al., "
  "2024), cada uno resuelto por sus desarrolladores y por el modelo DeepSeek-V4-Pro a partir del mismo código, y se comprobó "
  "con las pruebas oficiales del conjunto de datos qué soluciones resuelven el problema. El prototipo se llevó también a un "
  "dashboard web y se aplicó a un repositorio real.")
P(f"Los resultados principales son medibles y reproducibles desde el repositorio del proyecto ({REPO}): no se encontraron "
  f"diferencias significativas de deuda entre el código humano y el del LLM en ninguna de las siete métricas planificadas, "
  f"pero el LLM resolvió solo {n_ok} de los 30 problemas, frente a 30 de 30 de las soluciones humanas.")
P("El informe sigue esta estructura: trabajos relacionados, planificación metodológica del experimento, conducción del "
  "experimento (herramientas, diseño del prototipo e implementación), resultados, conclusiones, referencias y anexos.")

# ================= 4. Trabajos relacionados =================
H(1, "Trabajos Relacionados", nueva=True)
P("La búsqueda en Scopus y Web of Science del Hito 1 identificó cuatro revisiones de literatura cercanas al tema. Ninguna "
  "aborda de forma central la deuda que introduce el código generado por LLMs ni propone una forma de estimarla en horas. La "
  "Tabla 1 las resume y los apartados siguientes las discuten.")
T(["Revisión", "Tipo y alcance", "Enfoque", "Diferencia con este trabajo"], [
    ["Moreschini et al. (2026)", "Revisión multivocal; 61 fuentes", "Gestión de la deuda técnica en sistemas de IA y en el uso de IA para la ingeniería", "Se centra en la deuda de los sistemas de IA; no mide la deuda del código generado"],
    ["Gosu et al. (2026)", "Revisión sistemática; 29 estudios", "IA generativa como herramienta para gestionar la deuda", "Trata al LLM como instrumento, no como fuente de deuda"],
    ["Abdulaziz et al. (2026)", "Revisión sistemática; 46 estudios de 1 537", "Detección automática de deuda autoadmitida, 2015–2025", "No distingue el código asistido por LLMs; aquí la deuda autoadmitida es una de varias métricas"],
    ["Kosmas et al. (2026)", "Revisión PRISMA", "Ciclo de vida del aprendizaje automático", "La deuda técnica es un tema tangencial"],
], [3.2, 3, 4.6, 5.2], "Revisiones de literatura relacionadas", "Elaborado a partir de la revisión del Hito 1 (Carrasco Choque et al., 2026).")
H(2, "Revisión Multivocal de Moreschini et al. (2026)")
P("Es la revisión más cercana. Analiza 61 fuentes académicas e industriales sobre cómo debe adaptarse la gestión de la deuda "
  "técnica en dos direcciones: la ingeniería de sistemas de inteligencia artificial y el uso de la inteligencia artificial "
  "dentro del proceso de ingeniería. Concluye que los artefactos generados por IA introducen nuevos desafíos de mantenibilidad. "
  "Sin embargo, no sintetiza evidencia sobre cuánta deuda introduce el código generado ni compara métricas para medirla, que "
  "es lo que este trabajo hace de forma experimental.")
H(2, "Revisión Sistemática de Gosu et al. (2026)")
P("Revisa 29 estudios sobre el uso de IA generativa para gestionar la deuda técnica y encuentra que los enfoques actuales "
  "apoyan sobre todo la identificación y el pago de la deuda mediante prompts. Considera al LLM solo como herramienta de "
  "gestión. Este trabajo estudia la otra cara: el LLM como fuente de deuda, que en la revisión del Hito 1 resultó el rol "
  "dominante (siete de los diez estudios primarios).")
H(2, "Revisión Sistemática de Abdulaziz et al. (2026)")
P("Analiza 46 estudios sobre la detección automática de deuda autoadmitida (SATD), es decir, comentarios como TODO o FIXME en "
  "los que el propio desarrollador reconoce algo pendiente (Potdar & Shihab, 2014). Documenta la evolución desde palabras clave "
  "hacia modelos basados en transformers. No distingue si el código fue escrito con asistencia de LLMs. En debtguard, la "
  "deuda autoadmitida se detecta con palabras clave y es una de las métricas, junto con la complejidad, las malas prácticas y "
  "la duplicación.")
H(2, "Revisión de Kosmas et al. (2026)")
P("Revisa el ciclo de vida del aprendizaje automático y trata la deuda técnica de forma tangencial, como un problema de las "
  "canalizaciones de datos y modelos. Su aporte a este trabajo es indirecto.")
H(2, "Discusión")
P("En conjunto, las revisiones dejan un vacío preciso: ninguna mide la deuda que introduce el código generado por LLMs ni la "
  "expresa en tiempo, como propone el SWEBOK. Los estudios primarios del Hito 1 aportan las métricas y los diseños que este "
  "trabajo reutiliza. Agarwal et al. (2026) reportan un aumento de 39 % en la complejidad cognitiva y de 18 % en las "
  "advertencias tras adoptar agentes; Huang et al. (2026) encuentran 1,87 veces más redundancia en el código de agentes; Sun "
  "et al. (2026) usan SWE-bench Lite y encuentran 423 recomendaciones de mantenibilidad en parches de LLM frente a 30 en los "
  "humanos; y Bhutani et al. (2025) son de los pocos que expresan la deuda en días. Este trabajo combina esas métricas en una "
  "herramienta, las traduce a horas y las aplica a un diseño pareado.")

# ================= 5. Planificacion =================
H(1, "Planificación Metodológica del Experimento", nueva=True)
P("El experimento se planificó como un cuasi-experimento pareado, siguiendo a Wohlin et al. (2012): cada problema funciona "
  "como su propio control, porque la solución humana y la del LLM parten del mismo código. Las hipótesis, las métricas, los "
  "costos y los umbrales se fijaron antes de medir las soluciones del LLM y se congelaron en la etiqueta git "
  "v1.0-experimento del repositorio.")
H(2, "Descripción del Problema")
P("El código generado por LLMs se integra cada vez más en proyectos reales, y la evidencia del Hito 1 indica que puede traer "
  "más complejidad, más duplicación y más problemas de mantenibilidad que el código humano. Quien revisa un cambio necesita "
  "saber, antes de integrarlo, cuánta deuda introduce y cuánto costaría corregirla. Las herramientas de análisis estático "
  "entregan listas de advertencias, pero no separan la deuda que introduce un cambio de la que ya existía, y la literatura casi "
  "no la expresa en horas.")
P("**Pregunta de investigación:** ¿el código generado por un LLM introduce más deuda técnica, medida en complejidad, "
  "duplicación, advertencias, mantenibilidad, deuda autoadmitida y horas de corrección, que el código humano que resuelve el "
  "mismo problema?")
H(2, "Objetivos")
P("**Objetivo general.** Construir un prototipo que detecte y estime en horas la deuda técnica que introduce un cambio de "
  "código Python, y usarlo para comparar el código generado por un LLM con el código humano equivalente.")
P("**Objetivos específicos:**", sangria=False)
for x in ("Implementar un analizador determinista que mida complejidad, reglas estáticas, clones, acoplamiento, ciclos de importación y deuda autoadmitida, limitado a lo que introduce cada cambio.",
          "Traducir los hallazgos a horas de corrección con un modelo de costo de tipo SQALE configurable.",
          "Comparar 30 pares de soluciones humanas y de un LLM sobre los mismos problemas, con pruebas estadísticas para datos pareados.",
          "Determinar qué soluciones resuelven el problema, mediante las pruebas oficiales de SWE-bench.",
          "Llevar el prototipo a un dashboard web y aplicarlo a un repositorio real."):
    B(x)
P("Las hipótesis del experimento se resumen en la Tabla 2. En todos los casos, la hipótesis nula es que no hay diferencia "
  "entre ambos orígenes.")
T(["Hipótesis", "Enunciado", "Métricas", "Respaldo"], [
    ["H1", "El código del LLM tiene mayor complejidad", "Complejidad cognitiva y ciclomática máximas", "Agarwal et al. (2026)"],
    ["H2", "El código del LLM introduce más clones", "Clones nuevos", "Huang et al. (2026)"],
    ["H3", "El código del LLM tiene más advertencias y menor mantenibilidad", "Advertencias por KLOC; índice de mantenibilidad", "Sun et al. (2026)"],
    ["H4", "El código del LLM tiene más deuda en horas y menos deuda autoadmitida", "Horas por KLOC; SATD por KLOC", "Brahmi et al. (2026); Bhutani et al. (2025)"],
], [1.8, 5.5, 4.7, 4], "Hipótesis del experimento", "KLOC = mil líneas de código añadidas.")
H(2, "Variables: Dependiente e Independiente")
P("La Tabla 3 define las variables. La variable independiente es el origen del código; las dependientes son las métricas que "
  "calcula debtguard sobre cada solución. Las variables de control aseguran que ambas soluciones de un par se comparen en las "
  "mismas condiciones.")
T(["Tipo", "Variable", "Cómo se mide"], [
    ["Independiente", "Origen del código", "Humano (solución de los desarrolladores en SWE-bench) o LLM (DeepSeek-V4-Pro)"],
    ["Dependiente", "Complejidad cognitiva máxima", "complexipy, en las funciones que contienen líneas añadidas"],
    ["Dependiente", "Complejidad ciclomática máxima", "Radon, en las mismas funciones"],
    ["Dependiente", "Clones nuevos", "jscpd contra el proyecto completo; fragmentos con al menos 50 % de líneas nuevas"],
    ["Dependiente", "Advertencias por KLOC", "Ruff en líneas añadidas y ciclos de importación nuevos, por cada 1 000 líneas añadidas"],
    ["Dependiente", "Índice de mantenibilidad", "Radon; el mínimo entre los archivos tocados"],
    ["Dependiente", "Horas por KLOC", "Suma de los costos SQALE de los hallazgos, en horas, por cada 1 000 líneas añadidas"],
    ["Dependiente", "SATD por KLOC", "Comentarios TODO, FIXME, HACK o XXX en líneas añadidas"],
    ["Control", "Problema y código de partida", "Iguales en cada par"],
    ["Control", "Lenguaje y generación", "Solo Python; un único prompt; temperatura 0"],
    ["Registrada", "Corrección funcional", "Si la solución pasa las pruebas oficiales de SWE-bench"],
    ["Registrada", "Tamaño y similitud", "Líneas añadidas y eliminadas; similitud con la solución humana"],
], [2.6, 4.4, 9], "Variables del experimento", "Se excluyen de la medición las pruebas, las migraciones y los archivos autogenerados.")
H(2, "Cronograma y Recursos")
P("El trabajo se organizó en tres roles (P1: prototipo e implementación; P2: datos y análisis; P3: informe y validación). La "
  "Tabla 4 muestra las actividades realizadas y la Tabla 5 los recursos utilizados.")
T(["Fecha (2026)", "Actividad", "Rol", "Producto"], [
    ["2 de noviembre", "Definición del alcance y del diseño experimental", "Todos", "Guía de desarrollo del Hito 2"],
    ["5 de noviembre", "Construcción del prototipo y sus pruebas", "P1", "Paquete debtguard y pruebas automáticas"],
    ["5 de noviembre", "Muestreo de SWE-bench Lite y generación con DeepSeek", "P2", "data/casos.csv y data/llm/"],
    ["5 de noviembre", "Calibración, congelación de la configuración y lote de 60 mediciones", "P1, P2", "Etiqueta v1.0-experimento y reports/"],
    ["5 de noviembre", "Análisis estadístico, gráficos y sensibilidad", "P2", "data/tabla_hipotesis.csv y figuras"],
    ["5 de noviembre", "Comprobación funcional con las pruebas de SWE-bench", "P1, P2", "data/correccion/"],
    ["5 de noviembre", "Dashboard web", "P1", "dashboard-web/"],
    ["8 de noviembre", "Publicación del repositorio", "P1", "Repositorio en GitHub"],
    ["10 de noviembre", "Versión 1.1 del prototipo y re-medición", "P1, P2", "Rama v1.1-vacios y data/v11/"],
    ["10 de noviembre", "Estudio de caso con sqlite-utils", "P1, P3", "estudio_caso/"],
    ["10 de noviembre", "Redacción del informe", "P3", "Este documento"],
], [2.6, 7, 1.6, 4.8], "Cronograma de actividades", "Fechas de las versiones registradas en el historial de git del repositorio.")
T(["Recurso", "Detalle"], [
    ["Humanos", "Cuatro integrantes organizados en tres roles (P1, P2 y P3)"],
    ["Hardware", "Procesador Intel Core i5-12500H, 16 GB de RAM, Windows 11, sin GPU"],
    ["Software", "Python 3.13, Node.js 22, git 2.50 y Docker 29.8; herramientas de la Tabla 6"],
    ["Datos", "SWE-bench Lite: 300 problemas reales de 12 proyectos de Python"],
    ["Servicio externo", f"API de DeepSeek: {n(gen.tokens_entrada.sum(), 0)} tokens de entrada y {n(gen.tokens_salida.sum(), 0)} de salida en {len(gen)} problemas"],
    ["Costo monetario", "0,28 USD (saldo de la cuenta de 3,57 a 3,29 USD)"],
    ["Tiempo de cómputo", "Lote de 60 mediciones: 7 min 41 s. Comprobación funcional: cerca de 1 h 30 min. Estudio de caso: 2 min 40 s"],
], [3.5, 12.5], "Recursos utilizados", "Todas las herramientas de software son de código abierto, salvo la API del modelo.")

# ================= 6. Conduccion =================
H(1, "Conducción del Experimento", nueva=True)
H(2, "Herramientas y Stack Tecnológico")
P("La Tabla 6 lista las herramientas con su versión exacta, que está fijada en los archivos requirements.txt y "
  "package-lock.json del repositorio. Las de medición son complexipy (complexipy contributors, s.f.), Radon (Lacchia, s.f.), "
  "Ruff (Astral, s.f.) y jscpd (Kucherenko, s.f.); la comprobación funcional usa el arnés de SWE-bench (SWE-bench, s.f.) y la "
  "generación, la API de DeepSeek (DeepSeek, s.f.). Todas las herramientas de medición analizan el código sin ejecutarlo.")
T(["Herramienta", "Versión", "Licencia", "Uso"], [
    ["Python", "3.13.5", "PSF", "Lenguaje del prototipo y del análisis"],
    ["complexipy", "8.3.0", "MIT", "Complejidad cognitiva"],
    ["Radon", "6.0.1", "MIT", "Complejidad ciclomática e índice de mantenibilidad"],
    ["Ruff", "0.17.3", "MIT", "Reglas de buenas prácticas, errores probables y seguridad"],
    ["Pylint", "4.1.3", "GPL-2.0", "Ciclos de importación en la versión 1.0"],
    ["ast (biblioteca estándar)", "3.13", "PSF", "Grafo de imports: acoplamiento y ciclos en la versión 1.1"],
    ["jscpd", "5.4.2", "MIT", "Clones exactos y, desde la versión 1.1, parecidos"],
    ["unidiff", "1.0.1", "MIT", "Lectura de diffs"],
    ["datasets", "5.1.0", "Apache-2.0", "Descarga de SWE-bench Lite"],
    ["pandas", "3.1.1", "BSD", "Consolidación de resultados"],
    ["SciPy", "1.18.1", "BSD", "Pruebas de Wilcoxon y Mann-Whitney"],
    ["statsmodels", "0.15.0", "BSD", "Corrección de Holm"],
    ["matplotlib", "3.11.2", "PSF", "Gráficos"],
    ["swebench", "5.0.2", "MIT", "Comprobación funcional de las soluciones"],
    ["Docker", "29.8.0", "Apache-2.0", "Entorno de pruebas de cada problema"],
    ["Flask", "3.1.2", "BSD", "Servidor local del dashboard"],
    ["DeepSeek API (deepseek-v4-pro)", "—", "Servicio comercial", "Generación de las soluciones del LLM"],
], [4.8, 2.2, 2.6, 6.4], "Herramientas y stack tecnológico", "Versiones registradas en requirements.txt, package-lock.json y en el campo «versiones» de cada reporte JSON.")
H(2, "Diseño del Prototipo")
H(3, "Funcionamiento General")
P("debtguard recibe un diff, que contiene las líneas que añade, elimina o modifica un cambio, y el proyecto con ese cambio "
  "aplicado. Analiza solo las líneas añadidas en código Python de producción. Para cada problema genera un hallazgo con su "
  "archivo, línea, familia, regla, severidad y costo. Después suma la deuda, calcula un índice de riesgo y entrega un "
  "veredicto. La Figura 1 muestra el flujo.")
P("La decisión de diseño más importante es **cobrar solo lo que el cambio introduce**. Si una función ya superaba el umbral de "
  "complejidad antes del cambio, solo se cobra el aumento; un ciclo de importación que ya existía no se atribuye al cambio; y "
  "un clon se atribuye solo si al menos la mitad de sus líneas son nuevas. Así, cada cambio responde por su propia deuda.")
F(FIG / "flujo_prototipo_v11.png", "Flujo de Análisis de debtguard", "Elaboración propia.", 12)
H(3, "Arquitectura")
P("El núcleo está en el paquete src/debtguard y tiene cuatro módulos (Figura 2): ingest lee el diff y el repositorio git; "
  "metrics contiene un medidor por familia de deuda; estimator calcula costos, índice de riesgo y veredicto; y report escribe "
  "los resultados en JSON y Markdown. El mismo núcleo se usa desde la consola, desde el dashboard y desde los scripts del "
  "experimento. Los costos y umbrales están en archivos de configuración, no en el código.")
F(FIG / "arquitectura_v11.png", "Arquitectura del Prototipo", "Elaboración propia.", 13)
H(3, "Métricas")
P("La Tabla 7 resume las métricas y cómo interpretar sus valores. Las secciones que siguen las explican.")
T(["Métrica", "Qué mide", "Valor deseable", "Herramienta"], [
    ["Complejidad cognitiva", "Esfuerzo para entender una función", "15 o menos", "complexipy"],
    ["Complejidad ciclomática", "Caminos de ejecución de una función", "10 o menos", "Radon"],
    ["Clones exactos", "Código copiado casi literalmente", "0", "jscpd"],
    ["Clones parecidos", "Funciones con la misma estructura y otros nombres", "0", "jscpd --similarity"],
    ["Advertencias", "Malas prácticas, errores probables y riesgos de seguridad", "Pocas", "Ruff"],
    ["Acoplamiento", "Dependencias de salida y de entrada entre módulos", "Moderado", "Grafo de imports"],
    ["Ciclos de importación", "Módulos que se importan entre sí", "0", "Grafo de imports"],
    ["Índice de mantenibilidad", "Facilidad de mantener un archivo, de 0 a 100", "20 o más", "Radon"],
    ["SATD", "Deuda declarada en comentarios", "Pocos", "tokenize"],
    ["Horas de deuda", "Tiempo estimado para corregir lo detectado", "Pocas", "Modelo SQALE"],
], [3.6, 6.4, 2.6, 3.4], "Métricas de debtguard", "Umbrales tomados de config/remediation_costs.yaml y de los rangos que documenta Radon.")
P("**Complejidad cognitiva.** Mide el esfuerzo mental para entender una función (Campbell, 2018). Suma un punto por cada "
  "condición o bucle, más puntos cuanto más anidado está. Se mide en las funciones que contienen líneas añadidas, antes y "
  "después del cambio. Genera un hallazgo solo si el valor final supera el umbral de 15 **y** es mayor que el previo; la "
  "severidad es media, o alta si supera el doble del umbral (30). El costo se calcula sobre el aumento: 3 min × (valor final − "
  "máximo entre el valor previo y 15). Así no se cobra la complejidad que la función ya tenía.")
P("**Complejidad ciclomática.** Cuenta los caminos independientes de una función (McCabe, 1976). Cada if, for, while o "
  "condición lógica abre un camino nuevo y un caso más que probar. Sigue la misma regla que la complejidad cognitiva, con umbral "
  "10, severidad alta por encima de 20 y un costo de 2 min por punto de aumento.")
P("**Clones.** Un clon exacto es un fragmento de al menos 50 tokens copiado casi literalmente. Un clon parecido, o Tipo 3, es "
  "una función con la misma estructura que otra aunque cambien los nombres o los valores; jscpd los detecta comparando el "
  "árbol sintáctico normalizado, con una similitud mínima de 0,8.")
P("**Advertencias.** Son reglas de Ruff agrupadas en tres categorías (estilo, mantenibilidad y seguridad) y cuatro "
  "severidades (baja, media, alta y crítica). Por ejemplo, el uso de eval es una advertencia de seguridad crítica y una "
  "consulta SQL armada con texto es de seguridad alta.")
P("**Acoplamiento y ciclos.** A partir de los import de cada archivo se construye un grafo de dependencias entre los módulos "
  "del proyecto. Para cada módulo se calcula el acoplamiento eferente (cuántos módulos importa), el aferente (cuántos lo "
  "importan) y la inestabilidad, igual a eferente ÷ (eferente + aferente) (Martin, 1994). Un ciclo de importación es un "
  "grupo de módulos que se importan entre sí y puede impedir que el programa cargue. debtguard marca un ciclo solo cuando un "
  "import añadido une módulos que **antes no estaban** en un mismo ciclo; si ya lo estaban, el cambio no crea un ciclo nuevo y "
  "no se le atribuye. Esta regla evita culpar a un cambio de enredos previos, pero tiene un costo, que se analiza en los "
  "resultados: un import nuevo dentro de un ciclo existente puede alterar el orden de carga y no se marca.")
P("**Índice de mantenibilidad.** Combina tamaño, complejidad y comentarios de un archivo en un puntaje de 0 a 100 (Oman & "
  "Hagemeister, 1992). En Radon, de 20 a 100 es alto, de 10 a 19 medio y de 0 a 9 bajo. En archivos muy grandes el índice "
  "llega a 0 y deja de distinguir cambios.")
P("**SATD.** Son comentarios en los que el desarrollador admite algo pendiente: TODO, FIXME, HACK o XXX (Potdar & Shihab, "
  "2014).")
H(3, "Modelo de Costo")
P("Cada hallazgo recibe un costo en minutos según la Tabla 8, y la deuda es la suma (Letouzey, 2012). La nota SQALE compara "
  "esa deuda con el costo de escribir el código, estimado en 30 minutos por línea: hasta 5 % es A; hasta 10 %, B; hasta "
  "20 %, C; hasta 50 %, D; y más, E. El valor de 30 minutos es el costo de desarrollo por línea que SonarQube usa por defecto "
  "(SonarSource, s.f.); se adoptó para que la nota sea comparable con esa herramienta, y es configurable. Como define el "
  "denominador de la razón, un valor mayor mejora la nota y uno menor la empeora; las horas no dependen de él.")
P("El acoplamiento y el índice de mantenibilidad **se miden y se reportan, pero no suman horas ni entran al IRD**: no hay un "
  "costo de corrección de referencia validado para ellos. Solo los ciclos de importación nuevos, que sí son un defecto "
  "concreto, tienen costo.")
T(["Hallazgo", "Costo de corrección"], [
    ["Advertencia", "Base × factor. Base: estilo 5, mantenibilidad 15, seguridad 30 min. Factor: baja 0,5; media 1; alta 2; crítica 4"],
    ["Complejidad cognitiva", "3 min por punto de aumento sobre el umbral de 15"],
    ["Complejidad ciclomática", "2 min por punto de aumento sobre el umbral de 10"],
    ["Función larga", "15 min si el cambio la lleva a más de 70 líneas"],
    ["Clon exacto o parecido", "20 min"],
    ["Ciclo de importación nuevo", "30 min (mantenibilidad, severidad alta)"],
    ["Comentario SATD", "10 min"],
], [4.5, 11.5], "Modelo de Costo de Corrección", "Valores de config/remediation_costs.yaml.")
H(3, "Índice de Riesgo y Veredicto")
P(f"El índice de riesgo de deuda (IRD) va de 0 a 100. Se calcula con cinco componentes: horas por KLOC, complejidad cognitiva "
  f"máxima, clones exactos, advertencias altas o críticas por KLOC y SATD por KLOC. Cada componente c se normaliza con su "
  f"percentil 95 (p95) en {th['n_calibracion']} soluciones humanas de SWE-bench que no participan en la comparación (rol "
  f"«calibracion» en data/casos.csv):")
codigo_bloque("norm(c) = min(1, valor(c) / p95(c))            si p95(c) > 0\n"
              "norm(c) = 1 si valor(c) > 0; 0 en otro caso    si p95(c) = 0\n"
              "IRD     = 100 × Σ 0,2 × norm(c)                (cinco componentes con el mismo peso)", 9)
P(f"Los valores por encima del p95 cuentan como 1, de modo que ningún componente pesa más del 20 %. Con la calibración, los p95 "
  f"son {n(th['p95']['horas_kloc'], 1)} h/KLOC, cognitiva {n(th['p95']['cognitiva_max'], 1)}, {n(th['p95']['clones'], 0)} clones y 0 "
  f"en advertencias graves y en SATD; por eso, en estos dos últimos, un solo hallazgo aporta el componente completo. Un cambio se "
  f"advierte desde un IRD de {n(th['ird']['advertir'], 1)} (percentil 75 de la calibración) y se bloquea desde "
  f"{n(th['ird']['bloquear'], 1)} (percentil 90), o si contiene un hallazgo de seguridad crítico.")
_m = ejemplo["metricas"]
_c = [min(1, ejemplo["horas_kloc"] / th["p95"]["horas_kloc"]), min(1, _m["cognitiva_max"] / th["p95"]["cognitiva_max"]),
      min(1, _m["clones"] / th["p95"]["clones"]), 1.0 if _m["adv_altas_kloc"] > 0 else 0.0, 1.0 if _m["satd_kloc"] > 0 else 0.0]
P(f"**Ejemplo.** La solución del LLM para pytest-7373 tiene {n(ejemplo['horas_kloc'], 1)} h/KLOC (componente 1, porque supera el "
  f"p95), complejidad cognitiva {_m['cognitiva_max']} ({n(_c[1], 3)}), 0 clones (0), una advertencia crítica (1) y 0 SATD (0). "
  f"IRD = 100 × 0,2 × ({' + '.join(n(x, 3) for x in _c)}) = {n(100 * 0.2 * sum(_c), 2)}, igual al {n(ejemplo['ird'], 2)} del "
  f"reporte. El veredicto es bloquear por partida doble: supera {n(th['ird']['bloquear'], 1)} y tiene un hallazgo crítico.")
H(3, "Versión 1.1")
P("Después del experimento se publicó la versión 1.1, que añade los clones parecidos, el grafo de imports propio para "
  "acoplamiento y ciclos, y el cambio del índice de mantenibilidad que produce cada cambio. El grafo propio reemplaza a "
  "Pylint para los ciclos: en el proyecto Django (815 módulos) tardó 17 s frente a 33 s de Pylint, y agrupa los ciclos en "
  "7 grupos de módulos donde Pylint enumeraba 341 ciclos. Con la versión 1.1 se midieron de nuevo los 60 parches.")
H(3, "Interfaces de Uso")
P("**Consola.** El comando python -m debtguard analyze imprime el veredicto, las horas, la nota y el número de hallazgos, y "
  "guarda el reporte. Devuelve el código de salida 1 cuando el veredicto es bloquear, para poder usarlo en procesos "
  "automáticos. La Figura 3 muestra una ejecución real.")
F(FIG / "consola_analisis.png", "Salida de la Consola para un Parche Aceptado y Otro Bloqueado", "Ejecución real sobre los parches de DeepSeek para django-14752 y pytest-7373.", 15)
P("**Dashboard web.** Es una aplicación local que permite elegir una carpeta, encontrar su repositorio git y analizar el "
  "código actual, los últimos commits o los cambios sin confirmar. Muestra las métricas en tarjetas que explican su "
  "resultado, el historial de deuda por commit, las funciones y módulos más problemáticos, la lista de hallazgos y una "
  "comparación estadística entre los commits que declaran el uso de IA y el resto (Mann-Whitney U, delta de Cliff y Holm). "
  "Trabaja en modo de solo lectura: analiza una copia temporal y nunca ejecuta el código analizado.")
H(2, "Implementación del Experimento")
P("La Figura 4 resume el procedimiento. Los apartados siguientes describen cada paso.")
F(FIG / "flujo_experimento.png", "Flujo del Experimento", "Elaboración propia.", 7.5)
H(3, "Selección de los Casos")
P(f"De los 300 problemas de SWE-bench Lite se conservaron los 86 cuya solución humana cambia entre 10 y 300 líneas de "
  f"código de producción. Se barajaron con la semilla 42 y se asignaron 30 a la comparación y 20 a la calibración del IRD, "
  f"con un máximo de cuatro por proyecto. El resto quedó como reserva. Los 30 casos cubren 11 proyectos y se listan en el "
  f"Anexo A. {n_2022} de sus commits de partida son de 2022 en adelante y {n_2023} de 2023 en adelante.")
H(3, "Generación con el LLM")
P(f"Se usó el modelo deepseek-v4-pro con temperatura 0, razonamiento desactivado y el mismo prompt para todos los casos "
  f"(Anexo B). El prompt incluye el texto del problema y los archivos que modifica la solución humana. Cada respuesta se "
  f"guardó con el prompt, el modelo, la fecha y los tokens. Si un parche no se podía aplicar, se permitió un reintento con el "
  f"mensaje de error. Los problemas sin un parche utilizable se reemplazaron por los siguientes de la reserva, en el orden del "
  f"sorteo y respetando el máximo de cuatro por proyecto, hasta completar 30. Un parche que no se aplicaba con git apply "
  f"estándar se intentaba con git apply --recount --ignore-whitespace, que recalcula los conteos de líneas de cada bloque e "
  f"ignora diferencias de espacios; el contenido de los cambios no se modifica. La Tabla 9 resume el proceso.")
T(["Indicador", "Valor"], [
    ["Problemas enviados al modelo", f"{len(gen)} ({int((gen.rol == 'comparacion').sum())} de la muestra y {int((gen.rol == 'reserva').sum())} de la reserva)"],
    ["Llamadas a la API", f"{int(gen.n_intentos.sum())} (incluidos {int(gen.n_intentos.sum()) - len(gen)} reintentos)"],
    ["Parches no utilizables", f"{int((gen.estado != 'ok').sum())}: {int(gen.estado.str.contains('corrupt').sum())} con formato corrupto, {int(gen.estado.str.contains('does not apply').sum())} que no encajaban con el código y 1 sin cambios en código de producción"],
    ["Parches utilizados", f"30 ({int((sel.rol == 'comparacion').sum())} de la muestra y {int((sel.rol == 'reserva').sum())} de la reserva)"],
    ["Aplicados en modo estricto / flexible", f"{int((sel.modo == 'estricto').sum())} / {int((sel.modo == 'laxo').sum())}"],
    ["Tokens de entrada / salida", f"{n(gen.tokens_entrada.sum(), 0)} / {n(gen.tokens_salida.sum(), 0)}"],
    ["Costo", "0,28 USD"],
], [6, 10], "Generación de Soluciones con DeepSeek-V4-Pro", "Fuente: data/generacion_llm.csv. El modo flexible usa git apply --recount --ignore-whitespace.")
H(3, "Medición")
P("Para cada caso se tomó el código del commit de partida, se aplicó la solución humana, se ejecutó debtguard, se restauró el "
  "código y se repitió con la solución del LLM. Las líneas añadidas se cuentan solo en código Python de producción y sin "
  "líneas en blanco; una línea modificada cuenta como eliminada y añadida, como en cualquier diff. El lote de 60 mediciones tardó 7 min 41 s y produjo 60 reportes JSON sin "
  "errores de herramientas (carpeta reports/). La configuración se congeló antes en la etiqueta v1.0-experimento; desde "
  "entonces, src/ y config/ no cambiaron en esa versión.")
H(3, "Comprobación Funcional")
P("Las 60 soluciones se evaluaron con el arnés oficial de SWE-bench, en contenedores Docker con el entorno de cada problema. "
  "Una solución se considera correcta si pasan las pruebas que el problema debía arreglar y siguen pasando las que ya "
  "funcionaban. Las soluciones humanas sirven como control del entorno.")
H(3, "Análisis Estadístico")
P("Como cada problema tiene dos soluciones, se usaron pruebas para datos pareados. La **prueba de Wilcoxon de rangos con "
  "signo** (Wilcoxon, 1945) indica si, par por par, un grupo tiende a tener valores mayores; no supone normalidad. El **delta "
  "de Cliff** (Cliff, 1993) mide el tamaño del efecto entre −1 y 1: por debajo de ,147 en valor absoluto es despreciable; "
  "hasta ,33, pequeño; hasta ,474, mediano; y por encima, grande. La **corrección de Holm** (Holm, 1979) ajusta los valores p "
  "por probar siete métricas a la vez. Se rechaza H0, y la hipótesis queda respaldada, solo si el p ajustado es menor que ,05, "
  "el efecto no es despreciable y va en el sentido esperado; se usó α = ,05. Si H0 no se rechaza, el resultado indica que no se "
  "detectó una diferencia con esta muestra, no que ambos grupos sean iguales.")
P("La prueba de Wilcoxon descarta los pares con diferencia cero, por lo que el número efectivo de pares de cada métrica se "
  "informa junto a los resultados. Como el delta de Cliff está pensado para grupos independientes, se informa además la "
  "correlación biserial por rangos pareados (Kerby, 2014), que corresponde a la prueba de Wilcoxon: (T+ − T−) ÷ (T+ + T−), "
  "donde T+ y T− son las sumas de rangos de las diferencias positivas y negativas. Se interpreta como una correlación: "
  "alrededor de ,1 es pequeña; ,3, moderada; y ,5, grande.")
H(3, "Verificación del Prototipo")
P("El prototipo tiene 43 pruebas automáticas y el dashboard 13 (Tabla 10). Incluyen archivos con deuda conocida y costos "
  "calculados a mano: por ejemplo, la función con anidamiento profundo de la carpeta tests/fixtures tiene complejidad "
  "cognitiva 37 y debe costar (37 − 15) × 3 = 66 minutos, que es lo que entrega debtguard. También hay pruebas de regresión "
  "para errores encontrados durante el desarrollo.")
T(["Grupo de pruebas", "Cantidad", "Qué verifican"], [
    ["Prototipo, v1.0 (tests/test_prototipo.py)", "23", "Lectura del diff, cada métrica, costos calculados a mano, IRD, veredicto, consola y nota SQALE"],
    ["Archivos con deuda conocida (tests/test_fixtures.py)", "7", "Anidamiento, except genérico, función duplicada, TODO, ciclo entre dos módulos, archivo limpio y diff real de un pull request"],
    ["Regresiones (tests/test_regresiones.py)", "4", "Atribución de ciclos y saltos de línea en Windows"],
    ["Versión 1.1 (tests/test_v11.py)", "9", "Clones parecidos, acoplamiento, ciclos y cambio del índice de mantenibilidad"],
    ["Dashboard (dashboard-web/tests)", "13", "Que la carpeta analizada no cambie, commits, cambios sin confirmar, código actual, estadística y seguridad del servidor"],
], [6, 1.8, 8.2], "Pruebas Automáticas", "Resultado de la ejecución: 43 pruebas del prototipo y 13 del dashboard, todas aprobadas.")
F(FIG / "consola_pruebas.png", "Ejecución de las Pruebas del Prototipo", "Captura de la ejecución de las pruebas de la versión 1.0.", 13)

# ================= 7. Resultados =================
H(1, "Resultados", nueva=True)
H(2, "Contraste de Hipótesis")
P(f"En ninguna de las cuatro hipótesis se rechazó H0 (Tabla 11): todos los valores p ajustados son {p0(t.p_holm.min())} o "
  f"mayores. La columna «LLM > / = / <» indica en cuántos pares el LLM tuvo un valor mayor, igual o menor que el humano, y "
  f"«n ef.» cuántos pares tuvieron una diferencia distinta de cero.")
P(f"Las dos medidas de tamaño del efecto se leen distinto. El delta de Cliff compara todas las soluciones como dos grupos y da "
  f"efectos despreciables en las siete métricas. La correlación biserial pareada usa solo los pares con diferencia y aprovecha "
  f"el emparejamiento: en complejidad ciclomática es {p0(rbc(res, 'ciclomatica_max')[0], 2)} y en complejidad cognitiva "
  f"{p0(rbc(res, 'cognitiva_max')[0], 2)}, es decir, efectos moderados **en sentido contrario a H1**: cuando las dos "
  f"soluciones difieren, la del LLM suele ser menos compleja. Esos efectos no son significativos tras la corrección de Holm, y "
  f"en SATD el valor de {p0(rbc(res, 'satd_kloc')[0], 2)} se basa en un solo par, por lo que no es informativo.")
T(["H", "Métrica", "Mdn humano", "Mdn LLM", "LLM > / = / <", "n ef.", "W", "p", "p Holm", "r rb", "δ"],
  [[f.hipotesis, NOMBRES[f.metrica], n(f.med_humano), n(f.med_llm), f"{f.llm_mayor} / {f.empates} / {f.llm_menor}", rbc(res, f.metrica)[1], n(f.W, 1),
    p0(f.p), p0(f.p_holm), p0(rbc(res, f.metrica)[0], 2), p0(f.cliff, 2)] for f in t.itertuples()],
  [0.75, 3.6, 1.4, 1.25, 1.9, 0.85, 1.05, 1.05, 1.1, 1.05, 1.0], "Resultados de las Hipótesis H1 a H4",
  "En las siete métricas no se rechaza H0. 30 pares. Prueba de Wilcoxon de rangos con signo; n ef. = pares con diferencia distinta de cero, los únicos que usa la prueba. "
  "r rb = correlación biserial por rangos pareados (Kerby, 2014); δ = delta de Cliff. En ambos, un valor negativo indica que el LLM tuvo valores menores. "
  "Fuente: data/tabla_hipotesis.csv y data/resultados.csv.", tam=8)
F(FIG / "boxplots.png", "Distribución de las Métricas por Origen", "Cada punto es una solución. Las escalas difieren entre paneles. Fuente: data/resultados.csv.")
P("Los diagramas de caja de la Figura 6 muestran distribuciones muy parecidas. En varias métricas la mayoría de los valores "
  "es 0: muchas soluciones pequeñas no generan clones, advertencias ni comentarios de deuda.")
H(2, "Tamaño de las Soluciones")
P(f"La diferencia más clara está en el tamaño (Tabla 12). El LLM añadió menos líneas que el humano en "
  f"{int((w.LLM < w.humano).sum())} de los 30 pares: mediana de {n(ex.loc['lineas_anadidas', 'med_llm'], 0)} frente a "
  f"{n(ex.loc['lineas_anadidas', 'med_humano'], 0)} (p = {p0(ex.loc['lineas_anadidas', 'p'])}; δ = "
  f"{p0(ex.loc['lineas_anadidas', 'cliff'])}, grande). También eliminó menos líneas (mediana de "
  f"{n(ex.loc['lineas_eliminadas', 'med_llm'], 0)} frente a {n(ex.loc['lineas_eliminadas', 'med_humano'], 0)}). Este análisis "
  f"es exploratorio y no estaba entre las hipótesis.")
EXPL = {"delta_cognitiva": "Aumento de complejidad cognitiva", "delta_ciclomatica": "Aumento de complejidad ciclomática",
        "deuda_horas": "Deuda por solución (horas)", "lineas_anadidas": "Líneas añadidas", "lineas_eliminadas": "Líneas eliminadas"}
T(["Métrica", "M humano", "M LLM", "Mdn humano", "Mdn LLM", "p", "δ"],
  [[EXPL[m], n(ex.loc[m, "media_humano"]), n(ex.loc[m, "media_llm"]), n(ex.loc[m, "med_humano"]), n(ex.loc[m, "med_llm"]), p0(ex.loc[m, "p"]), p0(ex.loc[m, "cliff"])]
   for m in EXPL], [5.4, 1.8, 1.8, 2, 1.8, 1.6, 1.6], "Análisis Exploratorio", "M = media; Mdn = mediana. Valores p sin corrección por comparaciones múltiples. Fuente: data/tabla_exploratoria.csv.")
H(2, "Deuda Total y su Composición")
h_t, l_t = comp.loc["humano", "deuda_horas"], comp.loc["LLM", "deuda_horas"]
h_l, l_l = comp.loc["humano", "lineas_anadidas"], comp.loc["LLM", "lineas_anadidas"]
P(f"Sumando las 30 soluciones, el código humano acumula {n(h_t, 2)} h de deuda y el del LLM {n(l_t, 2)} h. Por tamaño, en "
  f"cambio, la relación se invierte: {n(h_t / h_l * 1000, 1)} h/KLOC frente a {n(l_t / l_l * 1000, 1)} h/KLOC, porque el LLM "
  f"escribió casi la mitad de líneas. En {ceros} de los 30 pares ambas soluciones tienen 0 horas de deuda (Tabla 13).")
T(["Origen", "Complejidad", "Reglas", "Clones", "SATD", "Total", "Líneas añadidas", "Hallazgos"],
  [[{"humano": "Humano", "LLM": "LLM"}[o], f"{n(comp.loc[o, 'min_complejidad'] / 60)} h", f"{n(comp.loc[o, 'min_regla'] / 60)} h",
    f"{n(comp.loc[o, 'min_clon'] / 60)} h", f"{n(comp.loc[o, 'min_satd'] / 60)} h", f"{n(comp.loc[o, 'deuda_horas'])} h",
    int(comp.loc[o, "lineas_anadidas"]), int(comp.loc[o, "n_hallazgos"])] for o in ("humano", "LLM")],
  [2, 2.2, 2, 2, 1.6, 1.8, 2.4, 2], "Composición de la Deuda en los 30 Pares", "Fuente: data/composicion_deuda.csv.")
P("Como los costos son parámetros del modelo, se varió ±25 % el costo de cada familia por separado (Tabla 14). La conclusión "
  "sobre horas por KLOC no cambió en ningún escenario: todos los valores p son mayores que ,47.")
T(["Familia variada", "Factor", "Mdn humano (h/KLOC)", "Mdn LLM (h/KLOC)", "p", "δ"],
  [[{"complejidad": "Complejidad", "regla": "Reglas", "clon": "Clones", "satd": "SATD"}[f.familia], n(f.factor), n(f.med_humano), n(f.med_llm), p0(f.p), p0(f.cliff)]
   for f in sens.itertuples()], [3, 1.5, 3.5, 3.5, 1.5, 1.5], "Sensibilidad de Horas por KLOC a los Costos",
  "Medianas por solución. La mediana del LLM es 0 porque más de la mitad de sus soluciones no tiene ningún hallazgo; la Tabla 13, "
  "en cambio, muestra sumas de los 30 pares. Fuente: data/sensibilidad_costos.csv.")
P(f"En cuanto a los veredictos, las soluciones humanas recibieron {ver.loc['humano', 'ACEPTAR']} aceptar, "
  f"{ver.loc['humano', 'ADVERTIR']} advertir y {ver.loc['humano', 'BLOQUEAR']} bloquear; las del LLM, "
  f"{ver.loc['LLM', 'ACEPTAR']}, {ver.loc['LLM', 'ADVERTIR']} y {ver.loc['LLM', 'BLOQUEAR']}. En notas SQALE, ambos grupos "
  f"tuvieron {sq.loc['humano', 'A']} soluciones con nota A.")
H(2, "Corrección Funcional")
P(f"Las pruebas oficiales de SWE-bench muestran la diferencia más grande del experimento (Tabla 15): **las 30 soluciones "
  f"humanas resuelven su problema y solo {n_ok} de las 30 del LLM lo hacen** ({n(n_ok / 30 * 100, 0)} %). De las {30 - n_ok} "
  f"restantes, {n_no_corre} impidieron que las pruebas llegaran a ejecutarse (por ejemplo, por un import circular o un import "
  f"de un nombre inexistente) y {30 - n_ok - n_no_corre} se ejecutaron sin pasarlas; {n_prev} de estas últimas además "
  f"rompieron pruebas que antes funcionaban.")
T(["Resultado", "Humano", "LLM"], [
    ["Resuelve el problema", "30", str(n_ok)],
    ["Las pruebas se ejecutan pero fallan", "0", str(30 - n_ok - n_no_corre)],
    ["Las pruebas no llegan a ejecutarse", "0", str(n_no_corre)],
    ["Rompe pruebas que antes pasaban", "0", str(n_prev)],
], [8, 4, 4], "Corrección Funcional de las Soluciones", "Arnés oficial de SWE-bench 5.0.2 en Docker. La última fila es un subconjunto de la segunda. Fuente: data/correccion/correccion.csv.")
P("Uno de los parches que impidió ejecutar las pruebas, el de sympy-12419, añade en sympy/matrices/expressions/matexpr.py la "
  "línea from sympy import Piecewise, que provoca un import circular al cargar el paquete. debtguard no lo marcó. La versión "
  "1.1 sí registró la dependencia nueva (dependencias_nuevas = 1 en reports_v11/), pero el módulo y el paquete sympy ya "
  "formaban parte de un mismo ciclo antes del cambio, y la regla solo marca ciclos nuevos. El error real fue de orden de "
  "carga dentro de un ciclo existente, algo que un análisis estático del grafo no puede ver sin ejecutar el código. Es un "
  "falso negativo documentado del detector de ciclos.")
P(f"La brevedad de las soluciones del LLM no se explica por sus errores: la mediana de líneas añadidas es {n(med_ok, 0)} tanto "
  f"en las correctas como en las incorrectas ({n(med_mal, 0)}). Con solo los {n_ok} pares en que el LLM acertó tampoco aparecen "
  f"diferencias de deuda (Tabla 16): la deuda total es de {n(tot_ok.loc['humano', 'deuda_horas'])} h para el código humano y "
  f"{n(tot_ok.loc['LLM', 'deuda_horas'])} h para el del LLM, con "
  f"{n(tot_ok.loc['humano', 'deuda_horas'] / tot_ok.loc['humano', 'lineas_anadidas'] * 1000, 1)} y "
  f"{n(tot_ok.loc['LLM', 'deuda_horas'] / tot_ok.loc['LLM', 'lineas_anadidas'] * 1000, 1)} h/KLOC.")
T(["H", "Métrica", "Mdn humano", "Mdn LLM", "LLM > / = / <", "p", "p Holm", "r rb", "δ"],
  [[f.hipotesis, NOMBRES[f.metrica], n(f.med_humano), n(f.med_llm), f"{f.llm_mayor} / {f.empates} / {f.llm_menor}", p0(f.p), p0(f.p_holm),
    p0(rbc(sub_ok, f.metrica)[0], 2), p0(f.cliff, 2)]
   for f in tc.itertuples()], [0.8, 3.8, 1.7, 1.6, 2.1, 1.3, 1.3, 1.2, 1.2], f"Hipótesis con los {n_ok} Pares en que el LLM Resolvió el Problema",
  "Wilcoxon de rangos con signo y corrección de Holm sobre las siete métricas. Fuente: data/correccion/tabla_solo_correctos.csv.", tam=9)
H(2, "Comprobaciones Adicionales")
P(f"**Memorización.** Para detectar si el modelo copió la solución humana, se midió la similitud entre las líneas añadidas de "
  f"cada par con difflib. La mediana fue {p0(eje.similitud.median(), 2)} y el máximo {p0(eje.similitud.max(), 2)}; ningún caso "
  f"superó el criterio de ,90 (fuente: data/ejecucion_comparacion.csv). No se observó evidencia de copia con ese criterio, "
  f"aunque eso no descarta otras formas de memorización.")
P(f"**Fecha de las soluciones humanas.** Como {n_2022} commits de partida son de 2022 en adelante, cuando ya existían "
  f"asistentes de programación, se repitió el análisis con los {30 - n_2022} pares anteriores a 2022. El resultado fue el "
  f"mismo: ningún p ajustado bajó de {p0(t22.p_holm.min())} (fuente: data/tabla_antes_2022.csv).")
H(2, "Resultados con la Versión 1.1")
cambios = v10v11[v10v11.cambio_horas.abs() > 1e-9]
P(f"La re-medición de los 60 parches con la versión 1.1 coincide con la versión 1.0 en {len(v10v11) - len(cambios)} de 60 "
  f"reportes; en el único restante, un parche del LLM, aparece un clon parecido nuevo. Ninguna versión encontró ciclos de "
  f"importación nuevos. Las métricas nuevas se analizaron igual que las hipótesis, con Wilcoxon de rangos con signo y corrección "
  f"de Holm sobre las siete métricas de la Tabla 17, como análisis exploratorio: ninguna muestra diferencias entre orígenes.")
T(["Métrica (versión 1.1)", "Mdn humano", "Mdn LLM", "M humano", "M LLM", "p Holm", "δ"],
  [[f.nombre, n(f.med_humano), n(f.med_llm), n(f.media_humano), n(f.media_llm), p0(f.p_holm), p0(f.cliff)] for f in v11.itertuples()],
  [5.4, 1.9, 1.9, 1.9, 1.9, 1.5, 1.5], "Métricas de la Versión 1.1 sobre los Mismos 30 Pares", "Fuente: data/v11/tabla_v11.csv y data/v11/v10_vs_v11.csv.")
H(2, "Resultados por Caso")
P("La Tabla 18 presenta los valores de cada par, en la forma humano / LLM. Muchos coinciden porque ambas soluciones modifican "
  "la misma función, y la complejidad máxima incluye la que esa función ya tenía.")


def par(i, m):
    return f"{nc(por.loc[('humano', i), m])} / {nc(por.loc[('LLM', i), m])}"


T(["Caso", "Cogn.", "Cicl.", "Clones", "Adv.", "MI", "Horas", "Líneas", "LLM resuelve"],
  [[i.split("__")[1], par(i, "cognitiva_max"), par(i, "ciclomatica_max"), par(i, "clones"), par(i, "advertencias"), par(i, "mi_min"),
    par(i, "deuda_horas"), par(i, "lineas_anadidas"), "Sí" if cor.loc[i, "llm_resuelto"] == True else "No"] for i in ids],  # noqa: E712
  [3.2, 1.3, 1.3, 1.25, 1.1, 2.4, 2.1, 1.6, 1.6], "Resultados por Caso", "Valores en la forma humano / LLM. Cogn. y Cicl.: complejidad máxima; Adv.: advertencias; MI: índice de mantenibilidad; Líneas: añadidas. Fuente: data/resultados.csv.", tam=8)

H(2, "Aplicación a un Repositorio Real: sqlite-utils")
P("Para verificar el prototipo fuera del experimento se analizó sqlite-utils, una librería de Python de código abierto "
  "(licencia Apache 2.0) para trabajar con bases de datos SQLite, en su commit 9c66baf del 10 de octubre de 2026. Se eligió "
  "porque sus commits recientes combinan algunos que declaran el uso de IA y otros que no. Se analizaron el código actual y "
  "los últimos 100 commits con el dashboard de la versión 1.1; la primera ejecución tardó unos 2 min 40 s. Los archivos se "
  "obtienen con git ls-files, que respeta .gitignore; se excluyen pruebas, migraciones y archivos generados, y las líneas son "
  "las no vacías de cada archivo. Los resultados se reproducen con estudio_caso/capturar.py sobre ese commit.")
fam = codigo["minutos_familia"]
T(["Métrica", "Valor"], [
    ["Archivos, líneas y funciones de producción", f"{cm['archivos']} archivos, {n(cm['lineas'], 0)} líneas y {cm['funciones']} funciones ({codigo['excluidos']} archivos de pruebas excluidos)"],
    ["Deuda estimada", f"{n(codigo['deuda_horas'], 1)} h ({n(codigo['horas_kloc'], 1)} h/KLOC); nota SQALE {codigo['nota_sqale']} (razón de deuda {n(codigo['debt_ratio'] * 100, 1)} %)"],
    ["Composición", f"Complejidad {n(fam['complejidad'] / 60, 1)} h; reglas {n(fam['regla'] / 60, 1)} h; clones {n(fam['clon'] / 60, 1)} h; SATD {n(fam['satd'] / 60, 1)} h"],
    ["Complejidad cognitiva máxima", f"{cm['cognitiva_max']} ({codigo['funciones'][0]['funcion']})"],
    ["Complejidad ciclomática máxima", f"{cm['ciclomatica_max']}"],
    ["Clones exactos / parecidos", f"{cm['clones']} / {cm['clones_similares']}"],
    ["Advertencias", f"{cm['advertencias']} ({n(cm['advertencias_kloc'], 1)} por KLOC): 2 críticas, 29 altas, 66 medias y 196 bajas"],
    ["Acoplamiento máximo (eferente / aferente)", f"{cm['acoplamiento_eferente_max']} / {cm['acoplamiento_aferente_max']}"],
    ["Ciclos de importación", f"{cm['ciclos']}"],
    ["Índice de mantenibilidad", f"Mínimo {n(cm['mi_min'], 1)}; promedio por líneas {n(cm['mi_promedio'], 1)}; {cm['mi_en_cero']} archivos en 0"],
    ["SATD", f"{cm['satd']} comentarios"],
], [6, 10], "Código Actual de sqlite-utils", "Fuente: estudio_caso/datos/resultado_completo.json.")
F(CAP / "01_resumen.png", "Resumen del Análisis de sqlite-utils en el Dashboard", "Captura del dashboard de la versión 1.1.", ANCHO, recorte=1630)
P("La nota A convive con funciones muy complejas: la razón de deuda se diluye en más de 10 000 líneas, mientras que la deuda "
  "se concentra en unas pocas funciones de los archivos db.py y cli.py (Figura 8).")
F(CAP / "03_archivos_y_modulos.png", "Funciones Más Complejas, Módulos Más Acoplados y Archivos con Más Deuda", "Captura del dashboard.", 14.5, recorte=2861)
cs = hist["commits"]
grupos = {o: [c for c in cs if c["origen"] == o] for o in ("ia", "sin_declarar")}


def med(xs):
    xs = sorted(xs)
    k = len(xs)
    return (xs[k // 2] if k % 2 else (xs[k // 2 - 1] + xs[k // 2]) / 2) if k else 0


P("Un commit se clasifica como **IA declarada** si su autor o su mensaje contiene una línea Co-Authored-By que nombra una "
  "herramienta de IA (Claude, Copilot, Cursor, Codex, Devin, Aider, Gemini, ChatGPT, OpenAI, Anthropic o Windsurf), o un texto "
  "del tipo «Generated with Claude». El resto se clasifica como **sin declarar**, lo que no garantiza que no se haya usado IA.")
P(f"De los 100 commits revisados, {len(cs)} cambian código Python de producción: {len(grupos['ia'])} declaran el uso de IA "
  f"y {len(grupos['sin_declarar'])} no lo declaran (Tabla 20). La comparación entre ambos grupos no muestra diferencias "
  f"significativas en ninguna de las {len(ec_cmp['metricas'])} métricas: todos los p ajustados son "
  f"{p0(min(m['p_holm'] for m in ec_cmp['metricas'] if m['p_holm'] is not None))} o mayores (Figura 9). Es el mismo resultado "
  f"que el experimento, en otro proyecto y con otro tipo de uso de la IA, aunque aquí los grupos no resuelven las mismas tareas.")
T(["Grupo", "Commits", "Deuda introducida", "Líneas añadidas", "Mdn h/KLOC", "Bloqueados"],
  [[{"ia": "IA declarada", "sin_declarar": "Sin declarar"}[o], len(g), f"{n(sum(c['deuda_horas'] for c in g), 1)} h",
    n(sum(c["metricas"]["lineas_anadidas"] for c in g), 0), n(med([c["horas_kloc"] for c in g]), 1),
    sum(c["veredicto"] == "BLOQUEAR" for c in g)] for o, g in grupos.items()],
  [3, 2, 3, 3, 3, 2], "Historial de sqlite-utils por Grupo", "Fuente: estudio_caso/datos/commits.csv y comparacion_ia.json.")
F(CAP / "05_ia_y_resto.png", "Comparación entre Commits con IA Declarada y el Resto", "Mann-Whitney U, delta de Cliff y corrección de Holm, calculados por el dashboard.", 14.5)
F(CAP / "07_modal_advertencias.png", "Explicación de una Métrica en el Dashboard", "Cada tarjeta abre una explicación con el valor, su lectura, la herramienta y el cálculo.", 14)

H(2, "Amenazas a la Validez y Alcance")
P(f"Siguiendo a Wohlin et al. (2012), la Tabla {cont['Tabla'] + 1} resume los factores que delimitan el alcance de los resultados y cómo se "
  f"trataron.")
T(["Tipo", "Factor", "Tratamiento"], [
    ["Interna", f"{int((gen.estado != 'ok').sum())} de {len(gen)} problemas no dieron un parche utilizable y se reemplazaron desde la reserva", "Reemplazo en el orden del sorteo; si fallaron los problemas más difíciles, la muestra podría favorecer al LLM"],
    ["Interna", f"{int((sel.modo == 'laxo').sum())} de 30 parches se aplicaron en modo flexible", "Solo recalcula conteos y espacios; se mide el diff resultante"],
    ["Interna", f"{n_2022} de 30 soluciones humanas son de 2022 en adelante", f"Mismo resultado con los {30 - n_2022} pares anteriores"],
    ["Interna", "Posible memorización del conjunto de datos", "Similitud máxima ,68; ningún caso sobre ,90"],
    ["Constructo", "El prompt entrega los archivos que modifica la solución humana", "Acota la tarea y difiere de un agente que explora el repositorio"],
    ["Constructo", "Las horas dependen de costos de referencia", "Sensibilidad ±25 % sin cambio en las conclusiones"],
    ["Constructo", "El detector de ciclos no ve errores de orden de carga dentro de ciclos existentes", "Caso sympy-12419 documentado"],
    ["Constructo", "Los clones semánticos (Tipo 4) no se detectan", "Se cubren los clones exactos y los parecidos (Tipo 3)"],
    ["Conclusión", "30 pares y muchos empates en cero", "Pruebas no paramétricas, n efectivo y dos medidas de efecto"],
    ["Externa", "Un modelo, un prompt, temperatura 0 y solo Python", "Los resultados se limitan a ese modo de uso"],
], [2.3, 7, 6.7], "Amenazas a la Validez", "Clasificación según Wohlin et al. (2012).")

# ================= 8. Conclusiones =================
H(1, "Conclusiones", nueva=True)
P("Este trabajo construyó debtguard, un prototipo que detecta la deuda técnica que introduce un cambio de código Python y la "
  "estima en horas de corrección, y lo usó para comparar soluciones humanas y de un LLM sobre los mismos problemas. Las "
  "conclusiones, todas verificables con los datos del repositorio, son las siguientes:")
B("**El prototipo cubre el vacío identificado en el Hito 1.** Traduce la complejidad, las malas prácticas, los clones, el "
  "acoplamiento, los ciclos de importación y la deuda autoadmitida a horas de corrección, como propone el SWEBOK, y atribuye "
  "a cada cambio solo la deuda que introduce. Sus 56 pruebas automáticas, con costos calculados a mano, verifican ese "
  "comportamiento.")
B("**No se detectó que el código del LLM introdujera más deuda que el humano.** En ninguna de las cuatro hipótesis se rechazó "
  "H0: en las siete métricas, los p ajustados fueron ,494 o mayores. Las diferencias que sí aparecen, en complejidad, van en "
  "sentido contrario al esperado y no son significativas. El resultado se mantiene al variar los costos ±25 %, con las métricas "
  "de la versión 1.1, con solo los pares correctos y con solo los casos anteriores a 2022. No demuestra que ambos códigos sean "
  "equivalentes: con 30 pares, diferencias pequeñas podrían pasar inadvertidas.")
B(f"**El LLM fue mucho menos eficaz para resolver los problemas.** Resolvió {n_ok} de 30, frente a 30 de 30 de las "
  f"soluciones humanas, y escribió parches más cortos (mediana de {n(ex.loc['lineas_anadidas', 'med_llm'], 0)} líneas "
  f"añadidas frente a {n(ex.loc['lineas_anadidas', 'med_humano'], 0)}).")
B("**Medir la deuda y probar el código son complementarios.** Una deuda baja no garantiza que el cambio funcione, y un cambio "
  "que funciona puede dejar deuda. debtguard responde cuánto costará mantener un cambio; las pruebas, si hace lo que debe.")
B("**Los resultados difieren de los estudios con agentes por el contexto.** Agarwal et al. (2026) y Sun et al. (2026) "
  "observaron más deuda en agentes que recorren el repositorio; aquí el LLM recibió los archivos exactos y produjo cambios "
  "pequeños, que apenas pueden añadir complejidad o duplicación. El resultado es válido para ese modo de uso: un modelo, un "
  "prompt y código Python.")
B("**La herramienta es aplicable a proyectos reales.** El dashboard analizó sqlite-utils en minutos, señaló las funciones que "
  "concentran la deuda y reprodujo el resultado del experimento al comparar los commits que declaran IA con el resto.")
P("En síntesis, en las condiciones evaluadas (un modelo, un prompt acotado y 30 problemas de Python) no se encontró evidencia "
  "de que el LLM introdujera más deuda técnica que las personas en las métricas consideradas, pero sí una eficacia mucho menor "
  "para resolver el problema. debtguard permite observar ambas dimensiones de forma reproducible y explicar cada resultado.")

# ================= 9. Referencias =================
H(1, "Referencias", nueva=True)
REFS = [
    "Abdulaziz, A., Sonbol, R., & Alnoukari, M. (2026). Automated detection of self-admitted technical debt: A systematic literature review. _IEEE Access, 14_, 20803–20825. https://doi.org/10.1109/ACCESS.2026.3661069",
    "Agarwal, S., He, H., & Vasilescu, B. (2026). AI IDEs or autonomous agents? Measuring the impact of coding agents on software development. En _Proceedings of the 23rd International Conference on Mining Software Repositories (MSR '26)_. ACM. https://doi.org/10.1145/3793302.3793589",
    "Astral. (s.f.). _Ruff_ (Versión 0.17.3) [Software]. https://github.com/astral-sh/ruff",
    "Bhutani, V., Toosi, F. G., & Buckley, J. (2025). Analysing software quality of AI-translated code: A comparative study of large language models using static analysis. _Applied Computer Systems, 30_(1), 105–121. https://doi.org/10.2478/acss-2025-0013",
    "Brahmi, Z., Ouni, A., Sayagh, M., & Saied, M. A. (2026). Characterizing self-admitted technical debt generated by AI coding agents. En _Proceedings of the 23rd International Conference on Mining Software Repositories (MSR '26)_ (pp. 852–856). ACM. https://doi.org/10.1145/3793302.3793588",
    "Campbell, G. A. (2018). Cognitive complexity: An overview and evaluation. En _Proceedings of the 2018 International Conference on Technical Debt_ (pp. 57–58). ACM.",
    "Carrasco Choque, A. M., Caceres Pari, A. R., Chancuaña Alvis, K., & Yana Agramonte, L. E. (2026). _Deuda técnica en el desarrollo de software asistido por LLMs: Un estudio de mapeo sistemático_ [Informe del Hito 1]. Universidad Nacional de San Agustín de Arequipa.",
    "Cliff, N. (1993). Dominance statistics: Ordinal analyses to answer ordinal questions. _Psychological Bulletin, 114_(3), 494–509. https://doi.org/10.1037/0033-2909.114.3.494",
    "complexipy contributors. (s.f.). _complexipy_ (Versión 8.3.0) [Software]. https://github.com/rohaquinlop/complexipy",
    "Cunningham, W. (1992). The WyCash portfolio management system. En _Addendum to the Proceedings on Object-Oriented Programming Systems, Languages, and Applications (OOPSLA '92)_ (pp. 29–30). ACM. https://doi.org/10.1145/157709.157715",
    "DeepSeek. (s.f.). _DeepSeek API documentation_. https://api-docs.deepseek.com",
    "Gosu, S., Feitosa, D., & Avgeriou, P. (2026). The use of generative AI in technical debt management: A systematic literature review. _Information and Software Technology, 199_, Artículo 108257. https://doi.org/10.1016/j.infsof.2026.108257",
    "Holm, S. (1979). A simple sequentially rejective multiple test procedure. _Scandinavian Journal of Statistics, 6_(2), 65–70.",
    "Huang, H., Jaisri, P., Shimizu, S., Chen, L., Nakashima, S., & Rodríguez-Pérez, G. (2026). More code, less reuse: Investigation on code quality and reviewer sentiment towards AI-generated pull requests. En _Proceedings of the 23rd International Conference on Mining Software Repositories (MSR '26)_ (pp. 1024–1028). ACM. https://doi.org/10.1145/3793302.3793622",
    "Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2024). SWE-bench: Can language models resolve real-world GitHub issues? En _The Twelfth International Conference on Learning Representations (ICLR 2024)_.",
    "Kerby, D. S. (2014). The simple difference formula: An approach to teaching nonparametric correlation. _Comprehensive Psychology, 3_, Artículo 11.IT.3.1. https://doi.org/10.2466/11.IT.3.1",
    "Kosmas, I., Papadopoulos, T., & Michalakelis, C. (2026). Machine learning lifecycle: A survey. _AppliedMath, 6_(7), Artículo 113. https://doi.org/10.3390/appliedmath6070113",
    "Kucherenko, A. (s.f.). _jscpd_ (Versión 5.4.2) [Software]. https://github.com/kucherenko/jscpd",
    "Lacchia, M. (s.f.). _Radon_ (Versión 6.0.1) [Software]. https://github.com/rubik/radon",
    "Letouzey, J.-L. (2012). The SQALE method for evaluating technical debt. En _2012 Third International Workshop on Managing Technical Debt_ (pp. 31–36). IEEE.",
    "Li, Q., Yin, Z., Yang, Y., Li, C., Shen, Z., Ge, J., Zhong, W., Luo, B., & Ng, V. (2026). IMPACT: Identifying and classifying multiple sourced and categorized self-admitted technical debts. _ACM Transactions on Software Engineering and Methodology, 35_(4), Artículo 102. https://doi.org/10.1145/3747180",
    "Martin, R. C. (1994). _OO design quality metrics: An analysis of dependencies_ [Manuscrito no publicado].",
    "McCabe, T. J. (1976). A complexity measure. _IEEE Transactions on Software Engineering, SE-2_(4), 308–320. https://doi.org/10.1109/TSE.1976.233837",
    "Moreschini, S., Arvanitou, E., Kanidou, E.-P., Nikolaidis, N., Su, R., Ampatzoglou, A., Chatzigeorgiou, A., & Lenarduzzi, V. (2026). The evolution of technical debt from DevOps to generative AI: A multivocal literature review. _Journal of Systems and Software, 231_, Artículo 112599. https://doi.org/10.1016/j.jss.2025.112599",
    "Oman, P., & Hagemeister, J. (1992). Metrics for assessing a software system's maintainability. En _Proceedings Conference on Software Maintenance 1992_ (pp. 337–344). IEEE.",
    "Potdar, A., & Shihab, E. (2014). An exploratory study on self-admitted technical debt. En _2014 IEEE International Conference on Software Maintenance and Evolution_ (pp. 91–100). IEEE. https://doi.org/10.1109/ICSME.2014.31",
    "SonarSource. (s.f.). _SonarQube documentation: Metric definitions_. https://docs.sonarsource.com",
    "Sun, X., Ståhl, D., Sandahl, K., & Kessler, C. (2026). Quality assurance of LLM-generated code: Addressing non-functional quality characteristics. _Journal of Systems and Software, 238_, Artículo 112885. https://doi.org/10.1016/j.jss.2026.112885",
    "SWE-bench. (s.f.). _SWE-bench_ (Versión 5.0.2) [Software]. https://github.com/SWE-bench/SWE-bench",
    "Tornhill, A., Borg, M., Hagatulah, N., & Söderberg, E. (2025). ACE: Automated technical debt remediation with validated large language model refactorings. En _Companion Proceedings of the 33rd ACM International Conference on the Foundations of Software Engineering (FSE Companion '25)_ (pp. 1318–1324). ACM. https://doi.org/10.1145/3696630.3730565",
    "Washizaki, H. (Ed.). (2026). _Guide to the software engineering body of knowledge (SWEBOK Guide), version 4.0a_. IEEE Computer Society. https://computer.org/swebok",
    "Wilcoxon, F. (1945). Individual comparisons by ranking methods. _Biometrics Bulletin, 1_(6), 80–83. https://doi.org/10.2307/3001968",
    "Wohlin, C., Runeson, P., Höst, M., Ohlsson, M. C., Regnell, B., & Wesslén, A. (2012). _Experimentation in software engineering_. Springer. https://doi.org/10.1007/978-3-642-29044-2",
]
for r in sorted(REFS, key=lambda x: x.lower()):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(1.27)
    p.paragraph_format.first_line_indent = Cm(-1.27)
    _runs(p, r)

# ================= 10. Anexos =================
H(1, "Anexos", nueva=True)
H(2, "Anexo A. Casos del Experimento")
T(["Caso", "Proyecto", "Año", "Problema", "Origen", "LLM resuelve"],
  [[i.split("__")[1], casos.loc[i, "repo"].split("/")[1], fechas.loc[i, "fecha_base"][:4], PROBLEMAS[i],
    "Reserva" if casos.loc[i, "rol"] == "reserva" else "Muestra", "Sí" if cor.loc[i, "llm_resuelto"] == True else "No"] for i in ids],  # noqa: E712
  [3.2, 2.2, 1, 6.6, 1.6, 1.6], "Los 30 Casos del Experimento", "El año es el del commit de partida. Fuente: data/casos.csv, data/fechas_base.csv y data/correccion/correccion.csv.", tam=8.5)
H(2, "Anexo B. Prompt Utilizado")
P("Este fue el prompt enviado al modelo para cada caso. Los textos entre llaves se reemplazan por los datos del problema. "
  "Parámetros de la llamada: modelo deepseek-v4-pro, temperature = 0, max_tokens = 16 000, razonamiento desactivado "
  "(thinking: disabled) y huella del sistema a307abda487cd1b463329ccb945ce396, la misma en las 44 llamadas.")
codigo_bloque("Eres un desarrollador. Repositorio: {repo}. Resuelve el siguiente issue.\n"
              "Devuelve SOLO un parche en formato unified diff aplicable con `git apply`.\n\n"
              "Issue:\n{texto del problema}\n\n"
              "Archivos relevantes:\n{contenido de los archivos que modifica la solución humana}", 9)
H(2, "Anexo C. Formato del Reporte de debtguard")
P("Cada análisis produce un archivo JSON con este formato. El ejemplo es el reporte real de la solución del LLM para "
  "pytest-7373, abreviado: tiene un único hallazgo, una llamada a eval que Ruff marca como riesgo de seguridad crítico, y por "
  "eso el veredicto es bloquear aunque la deuda sea de 2 horas.")
h0 = ejemplo["hallazgos"][0]
codigo_bloque(json.dumps({"caso_id": ejemplo["caso_id"], "origen": ejemplo["origen"], "modelo": ejemplo["modelo"],
                          "metricas": {k: ejemplo["metricas"][k] for k in ("cognitiva_max", "ciclomatica_max", "clones", "advertencias", "satd", "lineas_anadidas")},
                          "hallazgos": [{k: h0[k] for k in ("archivo", "linea", "familia", "regla", "severidad", "categoria", "costo_min", "detalle")}],
                          "deuda_min": ejemplo["deuda_min"], "deuda_horas": ejemplo["deuda_horas"], "nota_sqale": ejemplo["nota_sqale"],
                          "ird": ejemplo["ird"], "veredicto": ejemplo["veredicto"], "versiones": ejemplo["versiones"]}, ensure_ascii=False, indent=2))
H(2, "Anexo D. Formato de Configuración")
P("Los costos, umbrales y opciones de medición están en config/remediation_costs.yaml. Este es un extracto:")
codigo_bloque("severidad_factor: {baja: 0.5, media: 1, alta: 2, critica: 4}\n"
              "regla_base_min: {estilo: 5, mantenibilidad: 15, seguridad: 30}\n"
              "complejidad:\n  cognitiva: {umbral: 15, min_por_punto: 3}\n  ciclomatica: {umbral: 10, min_por_punto: 2}\n"
              "  funcion_larga: {umbral_loc: 70, min: 15}\n"
              "clon_min: 20\nsatd_min: 10\n"
              "clones: {min_tokens: 50, min_solapamiento: 0.5, similitud: 0.8}\n"
              "ciclos: {motor: ast}")
H(2, "Anexo E. Código Fuente en GitHub")
P(f"Todo el código, los datos y los resultados están en el repositorio {REPO}. La Tabla {cont['Tabla'] + 1} indica dónde está cada elemento.")
T(["Elemento", "Ubicación"], [
    ["Prototipo, versión del experimento", "Etiqueta v1.0-experimento (rama main)"],
    ["Prototipo, versión 1.1, re-medición y estudio de caso", "Rama v1.1-vacios"],
    ["Código del prototipo", "src/debtguard/"],
    ["Configuración de costos y umbrales", "config/"],
    ["Pruebas automáticas", "tests/ y dashboard-web/tests/"],
    ["Scripts del experimento", "experiments/ (muestreo, generación, lote, análisis, corrección y re-medición)"],
    ["Respuestas crudas del LLM", "data/llm/"],
    ["Soluciones humanas y del LLM", "casos/"],
    ["Reportes de cada solución", "reports/ (v1.0) y reports_v11/ (v1.1)"],
    ["Tablas de resultados", "data/ (por ejemplo, tabla_hipotesis.csv y correccion/correccion.csv)"],
    ["Dashboard", "dashboard-web/"],
    ["Estudio de caso", "estudio_caso/ (datos, capturas y script)"],
    ["Generador de este informe", "docs/build_informe_apa.py"],
], [6.5, 9.5], "Ubicación de los Elementos en el Repositorio", "Las instrucciones de instalación y reproducción están en el archivo README.md de la raíz.")
P("Para instalar el prototipo y repetir las pruebas en Windows:", sangria=False)
codigo_bloque("git clone https://github.com/AngelCaceresPari01/Debtguard.git\ncd Debtguard\npy -3.13 -m venv .venv\n"
              ".venv\\Scripts\\python.exe -m pip install -r requirements.txt\n.venv\\Scripts\\python.exe -m pip install -e .\n"
              "npm ci\n.venv\\Scripts\\python.exe -m pytest", 9)
P("Para repetir las mediciones y el análisis del experimento sin llamar a la API (las respuestas del modelo ya están en "
  "data/llm/; la descarga de los proyectos ocupa varios GB):", sangria=False)
codigo_bloque(".venv\\Scripts\\python.exe experiments\\prepare_repos.py\n"
              ".venv\\Scripts\\python.exe experiments\\run_batch.py --rol calibracion\n"
              ".venv\\Scripts\\python.exe experiments\\calibrate.py\n"
              ".venv\\Scripts\\python.exe experiments\\run_batch.py --rol comparacion\n"
              ".venv\\Scripts\\python.exe experiments\\analysis.py", 9)
P("run_batch.py no vuelve a medir los casos que ya tienen reporte en reports/; para repetirlos, mueva esos archivos a otra "
  "carpeta. El resultado esperado son los 60 reportes de reports/ y las tablas de data/, como data/tabla_hipotesis.csv. La "
  "comprobación funcional requiere Docker (experiments/swe_eval.py), y la versión 1.1 se mide con experiments/remedir_v11.py.",
  sangria=False)
H(2, "Anexo F. Uso de Asistentes de Inteligencia Artificial")
P("El desarrollo del prototipo, el análisis de datos y la redacción se apoyaron en Claude Code. Las soluciones evaluadas en "
  "el experimento las generó únicamente DeepSeek-V4-Pro.")

SALIDA.parent.mkdir(parents=True, exist_ok=True)
doc.save(SALIDA)
print(SALIDA)
