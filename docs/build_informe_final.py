"""Genera el informe final (prototipo y experimento) a partir de los datos del repositorio."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
DATA, FIG, CAP = RAIZ / "data", RAIZ / "docs" / "figuras", RAIZ / "estudio_caso" / "capturas"
SALIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "entregables" / "Informe_Debtguard_Prototipo_y_Experimento.docx"
ANCHO = 16.0

# ---------------- Datos ----------------
res = pd.read_csv(DATA / "resultados.csv")
t = pd.read_csv(DATA / "tabla_hipotesis.csv")
ex = pd.read_csv(DATA / "tabla_exploratoria.csv").set_index("metrica")
sens = pd.read_csv(DATA / "sensibilidad_costos.csv")
comp = pd.read_csv(DATA / "composicion_deuda.csv").set_index("origen")
ver = pd.read_csv(DATA / "veredictos.csv").set_index("origen")
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
n_2022 = int((fechas.fecha_base >= "2022").sum())
codigo, hist = ec["codigo"], ec["historial"]
NOMBRES = {"cognitiva_max": "Cognitiva máxima", "ciclomatica_max": "Ciclomática máxima", "clones": "Clones nuevos",
           "advertencias_kloc": "Advertencias/KLOC", "mi_min": "Índice de mantenibilidad", "horas_kloc": "Horas/KLOC",
           "satd_kloc": "SATD/KLOC"}
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
    "sympy__sympy-13031": "Cambio de comportamiento de hstack y vstack en 1.1",
    "sympy__sympy-14308": "Los vectores se imprimen mal en modo pretty",
    "sympy__sympy-18835": "uniq no avisa si la lista se modifica al recorrerla",
}


def n(x, d=2) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


def nc(x) -> str:
    s = n(x, 2)
    return s.rstrip("0").rstrip(",") if "," in s else s


def ps(x) -> str:
    return "< 0,001" if x < 0.001 else n(x, 3)


# ---------------- Formato ----------------
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.5)
sec.top_margin = sec.bottom_margin = Cm(2.4)
base = doc.styles["Normal"]
base.font.name, base.font.size = "Calibri", Pt(11)
base.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
base.paragraph_format.space_after = Pt(6)
base.paragraph_format.line_spacing = 1.15
for nombre, tam, antes, despues, color in (("Heading 1", 16, 18, 8, "1F3864"), ("Heading 2", 13, 12, 5, "2E5597"),
                                           ("Heading 3", 11.5, 10, 3, "2E5597"), ("Title", 24, 0, 10, "1F3864")):
    s = doc.styles[nombre]
    s.font.name, s.font.size, s.font.bold = "Calibri", Pt(tam), True
    s.font.color.rgb = RGBColor.from_string(color)
    rf = s.element.rPr.rFonts
    for atr in list(rf.attrib):
        del rf.attrib[atr]
    rf.set(qn("w:ascii"), "Calibri")
    rf.set(qn("w:hAnsi"), "Calibri")
    s.paragraph_format.space_before, s.paragraph_format.space_after = Pt(antes), Pt(despues)
    s.paragraph_format.keep_with_next = True
cont = {"tabla": 0, "figura": 0}


def campo(p, instruccion):
    for tipo in ("begin", "instr", "separate", "texto", "end"):
        r = p.add_run()
        if tipo == "instr":
            i = OxmlElement("w:instrText")
            i.set(qn("xml:space"), "preserve")
            i.text = instruccion
            r._r.append(i)
        elif tipo == "texto":
            r.text = "(actualizar con F9)"
        else:
            f = OxmlElement("w:fldChar")
            f.set(qn("w:fldCharType"), tipo)
            r._r.append(f)


def P(texto, estilo=None, centro=False):
    p = doc.add_paragraph(style=estilo)
    if centro:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    partes = texto.split("**")
    for i, trozo in enumerate(partes):
        if trozo:
            p.add_run(trozo).bold = i % 2 == 1
    return p


def B(texto):
    return P(texto, "List Bullet")


def H1(x, nueva_pagina=True):
    h = doc.add_heading(x, 1)
    h.paragraph_format.page_break_before = nueva_pagina


def H2(x):
    doc.add_heading(x, 2)


def H3(x):
    doc.add_heading(x, 3)


def salto():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def leyenda(texto, tipo):
    cont[tipo] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(f"{'Tabla' if tipo == 'tabla' else 'Figura'} {cont[tipo]}. {texto}")
    r.italic, r.font.size = True, Pt(9)
    r.font.color.rgb = RGBColor(0x40, 0x40, 0x40)
    return p


def T(cab, filas, anchos, titulo, fuente=8.5):
    leyenda(titulo, "tabla").paragraph_format.keep_with_next = True
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
        negrita = cabecera or (isinstance(x, str) and x.startswith("**"))
        r = p.add_run(str(x).strip("*"))
        r.font.size, r.bold = Pt(fuente), negrita
        if cabecera:
            s = OxmlElement("w:shd")
            s.set(qn("w:val"), "clear")
            s.set(qn("w:color"), "auto")
            s.set(qn("w:fill"), "DCE6F2")
            c._tc.get_or_add_tcPr().append(s)

    for i, x in enumerate(cab):
        celda(tb.rows[0].cells[i], x, True)
    tb.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for f in filas:
        cs = tb.add_row().cells
        for i, x in enumerate(f):
            celda(cs[i], x)
    for fila in tb.rows:
        fila._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for i, a in enumerate(anchos):
            fila.cells[i].width = Cm(a)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def F(ruta, titulo, ancho=ANCHO, recorte=None):
    from PIL import Image
    origen = Path(ruta)
    if recorte:
        im = Image.open(origen)
        destino = Path(__file__).parent / "_tmp" / f"{origen.stem}_{recorte}.png"
        destino.parent.mkdir(exist_ok=True)
        im.crop((0, 0, im.width, min(im.height, recorte))).save(destino)
        origen = destino
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(origen), width=Cm(ancho))
    leyenda(titulo, "figura")


# ====================== Portada ======================
P("Universidad Nacional de San Agustín de Arequipa", centro=True)
P("Tópicos Avanzados de Ingeniería de Sistemas", centro=True)
doc.add_paragraph().paragraph_format.space_after = Pt(70)
tit = doc.add_paragraph(style="Title")
tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
tit.add_run("Debtguard: detección y estimación en horas de la deuda técnica en código generado por LLMs")
P("Prototipo y experimento", centro=True)
doc.add_paragraph().paragraph_format.space_after = Pt(60)
P("**Presentado a:** Robert Edison Arisaca Mamani", centro=True)
P("**Presentado por:**", centro=True)
for a in ("Carrasco Choque Arles Melvin", "Caceres Pari Angel Raul", "Chancuaña Alvis Klismann", "Yana Agramonte Luis Efrain"):
    P(a, centro=True)
doc.add_paragraph().paragraph_format.space_after = Pt(30)
P("Noviembre de 2026", centro=True)
P("Repositorio: github.com/AngelCaceresPari01/Debtguard", centro=True)
salto()

P("**Índice**")
campo(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u')

# ====================== Resumen ======================
H1("Resumen")
P("Los asistentes de programación basados en modelos de lenguaje grandes (LLMs) escriben cada vez más código, y con él "
  "aparece una pregunta de mantenimiento: ¿cuánta deuda técnica introduce ese código y cuánto costaría corregirla? La "
  "revisión sistemática del Hito 1 mostró que casi ningún estudio responde la segunda parte, es decir, la estimación del "
  "costo, que es justo lo que pide el SWEBOK en el área de mantenimiento.")
P("Este trabajo presenta **debtguard**, un prototipo que recibe un cambio de código Python, detecta la deuda que ese cambio "
  "introduce y la expresa en **horas de corrección** con un modelo de tipo SQALE. Mide la complejidad, las malas prácticas, el "
  "código duplicado, el acoplamiento entre módulos, los ciclos de importación y los comentarios de deuda autoadmitida. Se "
  "puede usar desde la consola o desde un dashboard web local que analiza cualquier carpeta o repositorio git.")
P(f"Con el prototipo se hizo un experimento pareado: 30 problemas reales de SWE-bench Lite resueltos por sus "
  f"desarrolladores y por DeepSeek-V4-Pro, partiendo del mismo código. **No hubo diferencias significativas de deuda** en "
  f"ninguna de las siete métricas principales. Sin embargo, las pruebas oficiales de SWE-bench mostraron que el modelo "
  f"**resolvió solo {n_ok} de los 30 problemas**, frente a 30 de 30 de las soluciones humanas, y que sus parches fueron más "
  f"cortos (mediana de {n(ex.loc['lineas_anadidas', 'med_llm'], 0)} líneas añadidas frente a "
  f"{n(ex.loc['lineas_anadidas', 'med_humano'], 0)}). Por último, un estudio de caso con el repositorio sqlite-utils muestra "
  f"el prototipo aplicado a un proyecto real.")
P("**Conclusión principal:** con un prompt y parches pequeños, el código del LLM no acumuló más deuda medible que el humano, "
  "pero falló mucho más en resolver el problema. Medir la deuda sirve para decidir cuánto costará mantener un cambio, no para "
  "saber si funciona: ambas comprobaciones son complementarias.")
P("**Palabras clave:** deuda técnica, LLM, SQALE, complejidad cognitiva, SWE-bench, mantenimiento de software.")

# ====================== 1 ======================
H1("1. Introducción")
H2("1.1 El problema")
P("La deuda técnica es el trabajo futuro que deja un código difícil de mantener: funciones demasiado enredadas, partes "
  "copiadas, malas prácticas o tareas marcadas como pendientes. No impide que el programa funcione hoy, pero encarece cada "
  "cambio posterior, igual que los intereses de un préstamo.")
P("Con los LLMs, el código se produce más rápido de lo que los equipos alcanzan a revisarlo. La revisión del Hito 1 reunió "
  "evidencia de que ese código acumula más complejidad y más problemas de mantenibilidad, y de que esa deuda es menos "
  "visible. También encontró un vacío claro: casi nadie traduce la deuda a tiempo o costo, aunque es lo que necesita quien "
  "decide si aceptar un cambio.")
H2("1.2 Objetivo")
P("**Objetivo general:** construir un prototipo que detecte la deuda técnica que introduce un cambio de código Python y la "
  "estime en horas, y usarlo para comparar el código generado por un LLM con el código humano equivalente.")
P("**Objetivos específicos:**")
for x in ("Implementar un analizador determinista que mida solo lo que introduce cada cambio.",
          "Expresar los hallazgos en horas con un modelo de costo configurable.",
          "Comparar 30 pares de soluciones humanas y de un LLM sobre los mismos problemas, con pruebas estadísticas.",
          "Comprobar si las soluciones resuelven el problema, para interpretar bien la deuda medida.",
          "Llevar el prototipo a una herramienta usable, un dashboard, y aplicarla a un repositorio real."):
    B(x)
H2("1.3 Organización del informe")
P("La sección 2 resume los antecedentes. La sección 3 describe el prototipo y explica cada métrica. La sección 4 presenta el "
  "diseño del experimento y la sección 5 sus resultados. La sección 6 muestra el estudio de caso, la sección 7 discute los "
  "hallazgos y la sección 8 concluye.")

# ====================== 2 ======================
H1("2. Antecedentes")
H2("2.1 Deuda técnica y su costo")
P("Cunningham introdujo la metáfora de la deuda técnica en 1992 [2]: entregar código imperfecto para avanzar rápido equivale "
  "a pedir un préstamo cuyo interés se paga con esfuerzo extra en cada cambio. El SWEBOK v4.0a [1] la ubica en el "
  "mantenimiento de software y propone estimarla a partir del tamaño, la complejidad y las violaciones de buenas prácticas.")
P("El método **SQALE** [20] concreta esa idea: cada problema detectado tiene un costo de corrección en minutos, y la deuda es "
  "la suma de esos costos. Herramientas como SonarQube lo usan para dar una nota de la A a la E.")
H2("2.2 Lo que mostró la revisión del Hito 1")
P("El estudio de mapeo sistemático del Hito 1 seleccionó 10 estudios primarios (S01–S10) en Scopus y Web of Science [29]. Los "
  "hallazgos que orientan este trabajo son:")
T(["Hallazgo", "Estudios", "Cómo lo usa debtguard"], [
    ["El código de agentes aumenta la complejidad cognitiva (+39 %) y las advertencias (+18 %)", "S01 [5]", "Mide complejidad cognitiva y ciclomática y advertencias"],
    ["Los agentes declaran menos deuda en comentarios", "S02 [6], S09 [13]", "Cuenta los comentarios TODO, FIXME, HACK y XXX"],
    ["El código de agentes es más redundante (1,87 veces)", "S03 [7]", "Detecta clones exactos y, desde la v1.1, parecidos"],
    ["Los parches de LLM concentran importaciones cíclicas (360–365 casos)", "S06 [10]", "Detecta ciclos de importación nuevos"],
    ["El LLM solo no es fiable para detectar o corregir deuda (37 % de aciertos sin validación)", "S04 [8], S08 [12]", "Es determinista: no usa un LLM para decidir"],
    ["Casi nadie estima la deuda en tiempo o costo", "SWEBOK [1]", "Expresa la deuda en horas con el modelo SQALE"],
    ["Ningún estudio mide el acoplamiento en código generado", "S05 [9]", "Mide el acoplamiento entre módulos (v1.1)"],
], [6.5, 2.2, 5.5], "Hallazgos del Hito 1 y cómo los aplica el prototipo")
H2("2.3 SWE-bench Lite")
P("SWE-bench [19] es un conjunto de problemas reales (issues) de proyectos de Python en GitHub. Cada problema incluye el "
  "reporte original, el commit donde estaba el error, la solución escrita por los desarrolladores y pruebas automáticas que "
  "dicen si una solución resuelve el problema. La versión Lite tiene 300 problemas de 12 proyectos, como Django, scikit-learn "
  "o SymPy. Permite comparar una solución humana y una del LLM partiendo exactamente del mismo código.")

# ====================== 3 ======================
H1("3. El prototipo debtguard")
H2("3.1 Qué hace")
P("debtguard recibe un **diff** (las líneas que cambia un parche o commit) y el proyecto con ese cambio aplicado. Analiza "
  "solo las líneas añadidas en código Python de producción, sin contar pruebas ni migraciones. Para cada problema que "
  "encuentra genera un hallazgo con su ubicación, regla y severidad; luego suma su costo en minutos, calcula un índice de "
  "riesgo y da un veredicto: aceptar, advertir o bloquear.")
P("Una decisión importante del diseño es **cobrar solo lo que el cambio introduce**. Si una función ya era compleja antes del "
  "cambio, el prototipo no se lo atribuye; solo cobra el aumento. Así, cada cambio responde por su propia deuda.")
F(FIG / "flujo_prototipo_v11.png", "Flujo de análisis de debtguard", 11.5)
H2("3.2 Arquitectura")
P("El núcleo está en el paquete src/debtguard y se divide en cuatro partes: ingest lee el diff y el repositorio git; metrics "
  "mide; estimator calcula costos, índice y veredicto; y report escribe los resultados. Se puede usar desde la consola, desde "
  "el dashboard o desde los scripts del experimento. Las herramientas de medición son de código abierto.")
F(FIG / "arquitectura_v11.png", "Arquitectura del prototipo", 12)
T(["Herramienta", "Versión", "Para qué se usa"], [
    ["Python", "3.13", "Lenguaje del prototipo"],
    ["complexipy", "8.3.0", "Complejidad cognitiva"],
    ["Radon", "6.0.1", "Complejidad ciclomática e índice de mantenibilidad"],
    ["Ruff", "0.17.3", "Reglas de buenas prácticas y seguridad"],
    ["jscpd", "5.4.2", "Clones exactos y parecidos"],
    ["ast (Python)", "3.13", "Grafo de imports: acoplamiento y ciclos"],
    ["tokenize (Python)", "3.13", "Comentarios de deuda autoadmitida"],
    ["unidiff", "1.0.1", "Lectura de diffs"],
    ["SciPy y statsmodels", "1.18.1 y 0.15.0", "Pruebas estadísticas"],
    ["Flask", "3.1.2", "Servidor local del dashboard"],
], [4, 3, 9], "Herramientas utilizadas")
H2("3.3 Las métricas explicadas")
P("Cada métrica responde una pregunta concreta sobre el código. La Tabla 3 las resume y los apartados siguientes explican "
  "cómo leer sus valores.")
T(["Métrica", "Pregunta que responde", "Mejor si es", "Herramienta"], [
    ["Complejidad cognitiva", "¿Qué tan difícil es entender la función?", "Baja (≤ 15)", "complexipy"],
    ["Complejidad ciclomática", "¿Cuántos caminos de ejecución tiene la función?", "Baja (≤ 10)", "Radon"],
    ["Clones exactos", "¿Hay código copiado casi literalmente?", "0", "jscpd"],
    ["Clones parecidos", "¿Hay funciones con la misma estructura y otros nombres?", "0", "jscpd --similarity"],
    ["Advertencias", "¿Hay malas prácticas, errores probables o riesgos de seguridad?", "Pocas", "Ruff"],
    ["Acoplamiento", "¿Cuánto depende cada módulo de otros del proyecto?", "Moderado", "Grafo de imports"],
    ["Ciclos de importación", "¿Hay módulos que se importan entre sí?", "0", "Grafo de imports"],
    ["Índice de mantenibilidad", "¿Qué tan fácil es mantener el archivo?", "Alto (≥ 20)", "Radon"],
    ["SATD", "¿Quien programó dejó deuda declarada en comentarios?", "Pocos", "tokenize"],
    ["Horas de deuda", "¿Cuánto tiempo costaría corregir lo detectado?", "Pocas", "Modelo SQALE"],
], [3.6, 6.8, 2.2, 3.4], "Métricas de debtguard")
H3("Complejidad cognitiva")
P("Mide el esfuerzo mental para entender una función [21]. Suma un punto por cada condición o bucle, y más puntos cuanto más "
  "anidado está. Una función con 15 puntos o menos se considera manejable; por encima del doble del umbral (30) la "
  "severidad es alta. Es la métrica en la que S01 encontró un aumento del 39 % con agentes.")
H3("Complejidad ciclomática")
P("Cuenta los caminos independientes de una función [22]: cada if, for, while o condición lógica abre uno nuevo. Más "
  "caminos significa más casos que probar. El umbral usado es 10.")
H3("Clones exactos y parecidos")
P("Un clon exacto es un fragmento copiado casi literalmente (al menos 50 tokens). Un clon parecido (Tipo 3) es una función "
  "con la misma estructura que otra, aunque cambien los nombres de variables o los valores. Si un duplicado tiene un error, "
  "hay que corregirlo en cada copia. Solo se atribuye al cambio si al menos la mitad del fragmento es nuevo.")
H3("Advertencias")
P("Son malas prácticas detectadas por reglas de Ruff: errores probables, código innecesario, riesgos de seguridad como "
  "consultas SQL armadas con texto, y problemas de estilo. Cada una tiene una categoría (estilo, mantenibilidad o seguridad) y "
  "una severidad (baja, media, alta o crítica), que determinan su costo.")
H3("Acoplamiento y ciclos de importación")
P("A partir de los import de cada archivo se arma un grafo de dependencias entre los módulos del proyecto. De él salen tres "
  "valores por módulo [30]: el acoplamiento de salida o eferente (cuántos módulos importa), el de entrada o aferente (cuántos "
  "lo importan) y la inestabilidad, que es salida ÷ (salida + entrada). Un módulo con mucha entrada es delicado de cambiar; "
  "uno con mucha salida se rompe con facilidad cuando cambian otros. Un ciclo de importación aparece cuando varios módulos se "
  "importan entre sí; puede provocar errores al cargar el programa.")
H3("Índice de mantenibilidad")
P("Es un puntaje de 0 a 100 que combina el tamaño, la complejidad y los comentarios de un archivo [23]. Según Radon, de 20 a "
  "100 es alto, de 10 a 19 medio y de 0 a 9 bajo. En un cambio se reporta cuánto sube o baja el índice; en un archivo muy "
  "grande el valor suele ser 0.")
H3("SATD (deuda autoadmitida)")
P("Son los comentarios en los que quien programó admite algo pendiente: TODO, FIXME, HACK o XXX [4]. Que no haya no significa "
  "que no haya deuda; solo que nadie la dejó escrita.")
H2("3.4 Modelo de costo")
P("Cada hallazgo recibe un costo en minutos y la deuda es la suma. Por tamaño se informa en horas por cada 1000 líneas "
  "añadidas (h/KLOC). La nota SQALE compara la deuda con el costo de escribir el código, estimado en 30 minutos por línea.")
T(["Hallazgo", "Costo"], [
    ["Advertencia", "Base × factor. Base: estilo 5, mantenibilidad 15, seguridad 30 min. Factor: baja 0,5; media 1; alta 2; crítica 4"],
    ["Complejidad cognitiva", "3 min por punto de aumento sobre el umbral de 15"],
    ["Complejidad ciclomática", "2 min por punto de aumento sobre el umbral de 10"],
    ["Función larga", "15 min si el cambio la lleva a más de 70 líneas"],
    ["Clon exacto o parecido", "20 min"],
    ["Ciclo de importación nuevo", "30 min (mantenibilidad, severidad alta)"],
    ["Comentario SATD", "10 min"],
], [4.5, 11.5], "Costos de corrección")
T(["Nota", "Razón de deuda (deuda ÷ costo de desarrollo)"], [
    ["A", "Hasta 5 %"], ["B", "Hasta 10 %"], ["C", "Hasta 20 %"], ["D", "Hasta 50 %"], ["E", "Más de 50 %"],
], [3, 13], "Escala de notas SQALE")
H2("3.5 Índice de riesgo y veredicto")
P(f"El índice de riesgo de deuda (IRD) va de 0 a 100. Promedia cinco componentes: horas por KLOC, complejidad cognitiva "
  f"máxima, clones, advertencias graves por KLOC y SATD por KLOC. Cada componente se compara con el percentil 95 de "
  f"{th['n_calibracion']} parches humanos de SWE-bench que no forman parte de la comparación. Con esa calibración, un cambio "
  f"se advierte desde un IRD de {n(th['ird']['advertir'], 1)} y se bloquea desde {n(th['ird']['bloquear'], 1)}, o si tiene un "
  f"hallazgo crítico de seguridad. El veredicto está pensado para cambios, no para un proyecto completo.")
H2("3.6 Versión 1.1")
P("La versión 1.1 añade tres mejoras para cubrir vacíos del Hito 1:")
B("**Clones parecidos (Tipo 3):** detecta funciones con la misma estructura aunque cambien los nombres, que es la "
  "redundancia que S03 asocia a los LLMs y que los clones exactos no ven.")
B("**Acoplamiento y ciclos con un grafo propio:** el grafo de imports se construye con el módulo ast de Python, sin ejecutar "
  "el código. Reemplaza a Pylint para los ciclos: en Django (815 módulos) tardó 17 s frente a 33 s, y agrupa los ciclos en "
  "7 grupos de módulos donde Pylint enumeraba 341 ciclos.")
B("**Cambio del índice de mantenibilidad:** en lugar del mínimo, que casi no se movía con parches pequeños, se reporta "
  "cuánto empeora el archivo que más cambia.")
H2("3.7 Formas de uso")
P("**Consola.** El comando analiza un parche ya aplicado e imprime el veredicto, las horas, la nota y el número de "
  "hallazgos. El código de salida es 1 cuando el veredicto es bloquear, lo que permite usarlo en procesos automáticos.")
F(FIG / "consola_analisis.png", "Salida real de la consola: un parche aceptado y otro bloqueado por el uso de eval", 15)
P("**Dashboard web.** Es una aplicación local: se elige una carpeta, el sistema encuentra su repositorio git y analiza el "
  "código actual, los últimos commits o los cambios sin confirmar. Muestra las métricas en tarjetas que explican su "
  "resultado, el historial de deuda por commit, las funciones y módulos más problemáticos y la lista de hallazgos. Trabaja en "
  "modo de solo lectura: hace los análisis sobre una copia temporal y nunca ejecuta el código analizado.")
H2("3.8 Pruebas del prototipo")
P("El prototipo tiene 43 pruebas automáticas y el dashboard 13. Incluyen archivos con deuda conocida: una función con "
  "anidamiento profundo, un except genérico, una función duplicada, un TODO, dos módulos que se importan entre sí y un archivo "
  "limpio. Para cada uno, el costo esperado se calculó a mano. Por ejemplo, la función anidada tiene complejidad cognitiva 37 "
  "y debe costar (37 − 15) × 3 = 66 minutos, que es lo que entrega el prototipo. También hay pruebas de regresión para "
  "errores encontrados durante el desarrollo, como el manejo de saltos de línea de Windows.")
F(FIG / "consola_pruebas.png", "Ejecución de las pruebas automáticas", 13)
H2("3.9 Ejemplo de reporte")
_ej = json.loads((RAIZ / "reports" / "pytest-dev__pytest-7373_llm.json").read_text(encoding="utf-8"))
_h = _ej["hallazgos"][0]
P("Cada análisis produce un reporte JSON. Este es el del parche del LLM para pytest-7373, abreviado. Tiene un único hallazgo: "
  "el parche conserva una llamada a eval, que Ruff marca como riesgo de seguridad crítico (regla S307); por eso el veredicto "
  "es bloquear aunque la deuda sea de solo 2 horas.")
_txt = json.dumps({"caso_id": _ej["caso_id"], "origen": _ej["origen"], "modelo": _ej["modelo"],
                   "metricas": {k: _ej["metricas"][k] for k in ("cognitiva_max", "ciclomatica_max", "clones", "advertencias", "satd", "lineas_anadidas")},
                   "hallazgos": [{k: _h[k] for k in ("archivo", "linea", "familia", "regla", "severidad", "categoria", "costo_min", "detalle")}],
                   "deuda_min": _ej["deuda_min"], "deuda_horas": _ej["deuda_horas"], "nota_sqale": _ej["nota_sqale"],
                   "ird": _ej["ird"], "veredicto": _ej["veredicto"]}, ensure_ascii=False, indent=2)
for _l in _txt.splitlines():
    _p = doc.add_paragraph()
    _p.paragraph_format.space_after = Pt(0)
    _p.paragraph_format.line_spacing = 1.0
    _r = _p.add_run(_l)
    _r.font.name, _r.font.size = "Consolas", Pt(8.5)
doc.add_paragraph()

# ====================== 4 ======================
H1("4. Diseño del experimento")
H2("4.1 Pregunta e hipótesis")
P("**Pregunta:** ¿el código generado por un LLM introduce más deuda técnica que el código humano que resuelve el mismo "
  "problema?")
T(["H", "Hipótesis (frente a H0: no hay diferencia)", "Métricas", "Respaldo"], [
    ["H1", "El código del LLM tiene mayor complejidad", "Cognitiva y ciclomática máximas", "S01"],
    ["H2", "El código del LLM introduce más clones", "Clones nuevos", "S03"],
    ["H3", "El código del LLM tiene más advertencias y menor mantenibilidad", "Advertencias/KLOC, índice de mantenibilidad", "S06"],
    ["H4", "El código del LLM tiene más deuda en horas y menos SATD", "Horas/KLOC, SATD/KLOC", "S02, S07"],
], [1, 7, 5.5, 2], "Hipótesis")
H2("4.2 Variables")
T(["Tipo", "Variable"], [
    ["Independiente", "Origen del código: humano (solución de los desarrolladores) o LLM (DeepSeek-V4-Pro)"],
    ["Dependientes", "Las siete métricas de la Tabla 6"],
    ["De control", "Mismo problema y mismo código de partida en cada par; solo Python; mismo prompt; temperatura 0"],
    ["Registradas", "Tamaño del parche, forma en que se aplicó, similitud con la solución humana y si resuelve el problema"],
], [3.5, 12.5], "Variables del experimento")
H2("4.3 Selección de los casos")
P(f"De los 300 problemas de SWE-bench Lite se conservaron los 86 cuya solución humana cambia entre 10 y 300 líneas de código "
  f"de producción. Con una semilla fija (42) se barajaron y se asignaron 30 a la comparación y 20 a la calibración del IRD, "
  f"con un máximo de 4 por proyecto para tener variedad. Los demás quedaron como reserva. Los 30 casos cubren 11 proyectos y "
  f"se listan en el Anexo A.")
H2("4.4 Generación con el LLM")
P(f"Se usó deepseek-v4-pro con temperatura 0, razonamiento desactivado y el mismo prompt para todos los casos (Anexo B). El "
  f"prompt incluye el texto del problema y los archivos que modifica la solución humana. Se probaron {len(gen)} problemas: "
  f"{int((gen.estado != 'ok').sum())} no produjeron un parche utilizable, incluso después de un reintento, y se reemplazaron "
  f"con casos de la reserva. De los 30 parches finales, {int((sel.modo == 'laxo').sum())} se aplicaron con una opción más "
  f"flexible de git porque no cumplían el formato estricto. El costo total de la API fue de 0,28 USD.")
H2("4.5 Procedimiento")
P("Para cada caso se tomó el código del commit original, se aplicó el parche humano, se ejecutó debtguard y se repitió con el "
  "parche del LLM. Así se obtuvieron 60 reportes. La configuración del prototipo (umbrales y costos) se congeló antes de "
  "medir los parches del LLM, en la etiqueta git v1.0-experimento, para que los resultados no se ajustaran a posteriori. "
  "Después se ejecutaron las pruebas oficiales de SWE-bench en contenedores Docker para saber qué parches resuelven el "
  "problema.")
F(FIG / "flujo_experimento.png", "Flujo del experimento", 8)
H2("4.6 Análisis estadístico")
P("Como cada caso tiene una solución humana y otra del LLM sobre el mismo problema, se usaron pruebas para datos pareados:")
B("**Prueba de Wilcoxon de rangos con signo** [24]: indica si, par por par, un grupo tiende a tener valores mayores que "
  "el otro. No supone que los datos sigan una distribución normal.")
B("**Delta de Cliff** [25]: mide el tamaño de la diferencia, de −1 a 1. Por debajo de 0,147 en valor absoluto se considera "
  "despreciable; hasta 0,33, pequeña; hasta 0,474, mediana; y por encima, grande.")
B("**Corrección de Holm** [26]: como se prueban siete métricas a la vez, ajusta los valores p para no encontrar diferencias "
  "por azar.")
P("Una hipótesis se acepta si el p ajustado es menor que 0,05, el efecto no es despreciable y la diferencia va en el sentido "
  "esperado.")

# ====================== 5 ======================
H1("5. Resultados del experimento")
H2("5.1 Contraste de hipótesis")
P(f"**Ninguna hipótesis se confirmó.** Todos los p ajustados valen {n(t.p_holm.min(), 3)} o más y todos los efectos son "
  f"despreciables. La columna «LLM > / = / <» cuenta en cuántos pares el LLM tuvo un valor mayor, igual o menor que el humano.")
T(["H", "Métrica", "Mediana humano", "Mediana LLM", "LLM > / = / <", "p", "p Holm", "δ Cliff", "Resultado"],
  [[f.hipotesis, NOMBRES[f.metrica], n(f.med_humano), n(f.med_llm), f"{f.llm_mayor} / {f.empates} / {f.llm_menor}", ps(f.p), ps(f.p_holm),
    n(f.cliff, 3), "Sin diferencia"] for f in t.itertuples()],
  [0.8, 3, 1.6, 1.6, 1.8, 1.1, 1.1, 1.2, 1.8], "Resultados de H1 a H4 (Wilcoxon, 30 pares)")
F(FIG / "boxplots.png", "Distribución de las métricas por origen; cada punto es un parche", ANCHO)
P("Los diagramas de caja muestran distribuciones muy parecidas. En varias métricas la mayoría de los valores es 0: muchos "
  "parches pequeños no generan clones, advertencias ni comentarios de deuda.")
H2("5.2 Tamaño de los parches")
P(f"La diferencia más clara está en el tamaño. El LLM añadió menos líneas en {int((w.LLM < w.humano).sum())} de 30 pares: "
  f"mediana de {n(ex.loc['lineas_anadidas', 'med_llm'], 0)} frente a {n(ex.loc['lineas_anadidas', 'med_humano'], 0)} "
  f"(p = {ps(ex.loc['lineas_anadidas', 'p'])}; δ = {n(ex.loc['lineas_anadidas', 'cliff'])}, grande). También eliminó menos: "
  f"mediana de {n(ex.loc['lineas_eliminadas', 'med_llm'], 0)} frente a {n(ex.loc['lineas_eliminadas', 'med_humano'], 0)}. "
  f"Coincide con S03, que observó que los humanos eliminan más código que los agentes.")
H2("5.3 Deuda total y su composición")
h_t, l_t = comp.loc["humano", "deuda_horas"], comp.loc["LLM", "deuda_horas"]
h_l, l_l = comp.loc["humano", "lineas_anadidas"], comp.loc["LLM", "lineas_anadidas"]
P(f"Sumando los 30 parches, el código humano acumula {n(h_t, 1)} h y el del LLM {n(l_t, 1)} h. Por tamaño, en cambio, es al "
  f"revés: {n(h_t / h_l * 1000, 1)} h/KLOC frente a {n(l_t / l_l * 1000, 1)} h/KLOC. En {ceros} de los 30 pares ambos parches "
  f"tienen 0 horas de deuda.")
T(["Origen", "Complejidad", "Reglas", "Clones", "SATD", "Total", "Líneas añadidas", "Hallazgos"],
  [[{"humano": "Humano", "LLM": "LLM"}[o], f"{n(comp.loc[o, 'min_complejidad'] / 60)} h", f"{n(comp.loc[o, 'min_regla'] / 60)} h",
    f"{n(comp.loc[o, 'min_clon'] / 60)} h", f"{n(comp.loc[o, 'min_satd'] / 60)} h", f"{n(comp.loc[o, 'deuda_horas'])} h",
    int(comp.loc[o, "lineas_anadidas"]), int(comp.loc[o, "n_hallazgos"])] for o in ("humano", "LLM")],
  [2, 2, 2, 2, 1.6, 1.8, 2.2, 1.8], "Composición de la deuda en los 30 pares")
P("**Sensibilidad a los costos.** Los costos son parámetros del modelo, así que se variaron ±25 % por familia. El resultado de "
  "horas/KLOC no cambió en ningún escenario.")
T(["Familia variada", "Factor", "Mediana humano (h/KLOC)", "Mediana LLM (h/KLOC)", "p", "δ Cliff"],
  [[{"complejidad": "Complejidad", "regla": "Reglas", "clon": "Clones", "satd": "SATD"}[f.familia], n(f.factor), n(f.med_humano), n(f.med_llm), ps(f.p), n(f.cliff, 3)]
   for f in sens.itertuples()], [3, 1.5, 3.5, 3.5, 1.5, 1.5], "Sensibilidad de horas/KLOC a los costos (±25 %)")
P(f"**Veredictos.** Humano: {ver.loc['humano', 'ACEPTAR']} aceptar, {ver.loc['humano', 'ADVERTIR']} advertir y "
  f"{ver.loc['humano', 'BLOQUEAR']} bloquear. LLM: {ver.loc['LLM', 'ACEPTAR']} aceptar, {ver.loc['LLM', 'ADVERTIR']} advertir y "
  f"{ver.loc['LLM', 'BLOQUEAR']} bloquear.")
H2("5.4 ¿Las soluciones funcionan?")
P(f"Las pruebas oficiales de SWE-bench muestran una diferencia grande: **las 30 soluciones humanas resuelven su problema y "
  f"solo {n_ok} de las 30 del LLM lo hacen** ({n(n_ok / 30 * 100, 0)} %). De las {30 - n_ok} restantes, {n_no_corre} impidieron "
  f"que las pruebas llegaran a ejecutarse (por ejemplo, con un import circular), y {30 - n_ok - n_no_corre} se ejecutaron sin "
  f"pasarlas; {n_prev} de estas además rompieron pruebas que antes funcionaban.")
P(f"La brevedad no se explica por los errores: la mediana de líneas añadidas por el LLM es la misma, 3, en los parches "
  f"correctos y en los incorrectos. Con solo los {n_ok} pares en que el LLM acertó, tampoco aparecen diferencias de deuda "
  f"(todos los p ajustados valen 1); la deuda total es {n(tot_ok.loc['humano', 'deuda_horas'])} h para el humano y "
  f"{n(tot_ok.loc['LLM', 'deuda_horas'])} h para el LLM, con {n(tot_ok.loc['humano', 'deuda_horas'] / tot_ok.loc['humano', 'lineas_anadidas'] * 1000, 1)} "
  f"y {n(tot_ok.loc['LLM', 'deuda_horas'] / tot_ok.loc['LLM', 'lineas_anadidas'] * 1000, 1)} h/KLOC.")
T(["H", "Métrica", "Mediana humano", "Mediana LLM", "LLM > / = / <", "p", "p Holm", "δ Cliff"],
  [[f.hipotesis, NOMBRES[f.metrica], n(f.med_humano), n(f.med_llm), f"{f.llm_mayor} / {f.empates} / {f.llm_menor}", ps(f.p), ps(f.p_holm), n(f.cliff, 3)]
   for f in tc.itertuples()], [0.8, 3.6, 1.8, 1.8, 2, 1.2, 1.2, 1.3], f"Resultados con los {n_ok} pares en que el LLM resolvió el problema")
H2("5.5 Comprobaciones adicionales")
P(f"**Memorización.** La similitud entre las líneas nuevas de cada par tuvo una mediana de {n(eje.similitud.median())} y un "
  f"máximo de {n(eje.similitud.max())}. Ningún caso superó 0,9, así que no hay indicios de que el modelo copiara la solución "
  f"humana.")
P(f"**Fecha de las soluciones humanas.** {n_2022} de los 30 commits base son de 2022 en adelante, cuando ya existían asistentes "
  f"de programación. Con los {30 - n_2022} pares anteriores a 2022 los resultados son los mismos: ningún p ajustado baja de "
  f"{n(t22.p_holm.min(), 3)}.")
H2("5.6 Resultados con la versión 1.1")
P("Los 60 parches se midieron de nuevo con la versión 1.1. Los resultados coinciden con la versión 1.0 salvo en un parche del "
  "LLM, donde aparece un clon parecido nuevo. Ninguna de las métricas nuevas muestra diferencias entre humanos y LLM, y "
  "ninguna versión encontró ciclos de importación nuevos.")
T(["Métrica (v1.1)", "Mediana humano", "Mediana LLM", "Media humano", "Media LLM", "p Holm", "δ Cliff"],
  [[f.nombre, n(f.med_humano), n(f.med_llm), n(f.media_humano), n(f.media_llm), ps(f.p_holm), n(f.cliff, 3)] for f in v11.itertuples()],
  [5, 2, 2, 2, 2, 1.5, 1.5], "Métricas de la versión 1.1 sobre los mismos 30 pares")
H2("5.7 Resultados por caso")
P("La Tabla 13 muestra cada par como humano / LLM. Muchos valores coinciden porque ambos parches tocan la misma función; las "
  "pruebas estadísticas usan los 30 pares en conjunto, no cada caso por separado.")


def par(i, m):
    return f"{nc(por.loc[('humano', i), m])} / {nc(por.loc[('LLM', i), m])}"


filas = [[i.split("__")[1], par(i, "cognitiva_max"), par(i, "ciclomatica_max"), par(i, "clones"), par(i, "advertencias"), par(i, "mi_min"),
          par(i, "deuda_horas"), par(i, "lineas_anadidas"), "Sí" if cor.loc[i, "llm_resuelto"] == True else "No"] for i in ids]  # noqa: E712
T(["Caso", "Cogn.", "Cicl.", "Clones", "Adv.", "MI", "Horas", "Líneas +", "¿LLM resuelve?"], filas,
  [3.2, 1.3, 1.3, 1.25, 1.1, 2.4, 2.1, 1.6, 1.6], "Resultados por caso (humano / LLM)", fuente=8)

# ====================== 6 ======================
H1("6. Estudio de caso: sqlite-utils")
cm = codigo["metricas"]
fam = codigo["minutos_familia"]
P(f"Para mostrar el prototipo en un proyecto real se analizó **sqlite-utils**, una librería de Python de código abierto "
  f"(licencia Apache 2.0) para trabajar con bases de datos SQLite. Se eligió porque entre sus commits recientes hay algunos "
  f"que declaran el uso de IA y otros que no. Se analizaron el código actual (commit 9c66baf, del 10 de octubre de 2026) y los "
  f"últimos 100 commits, con el dashboard de la versión 1.1. La primera ejecución tardó unos 2 min 40 s.")
H2("6.1 Código actual")
P(f"El código de producción tiene {cm['archivos']} archivos, {n(cm['lineas'], 0)} líneas y {cm['funciones']} funciones; se "
  f"excluyeron {codigo['excluidos']} archivos de pruebas.")
F(CAP / "01_resumen.png", "Pestaña Resumen del dashboard con el análisis de sqlite-utils", ANCHO, recorte=1630)
T(["Métrica", "Valor", "Lectura"], [
    ["Deuda estimada", f"{n(codigo['deuda_horas'], 1)} h ({n(codigo['horas_kloc'], 1)} h/KLOC)", f"Nota SQALE {codigo['nota_sqale']}: razón de deuda {n(codigo['debt_ratio'] * 100, 1)} %"],
    ["Origen de la deuda", f"Complejidad {n(fam['complejidad'] / 60, 1)} h · reglas {n(fam['regla'] / 60, 1)} h · clones {n(fam['clon'] / 60, 1)} h · SATD {n(fam['satd'] / 60, 1)} h", "La complejidad y las reglas explican el 90 %"],
    ["Complejidad cognitiva máx.", n(cm["cognitiva_max"], 0), f"{codigo['funciones'][0]['funcion']}: casi 18 veces el umbral"],
    ["Complejidad ciclomática máx.", n(cm["ciclomatica_max"], 0), "13 veces el umbral"],
    ["Clones exactos / parecidos", f"{cm['clones']} / {cm['clones_similares']}", "Los parecidos solo los detecta la v1.1"],
    ["Advertencias", f"{cm['advertencias']} ({n(cm['advertencias_kloc'], 1)} por KLOC)", "2 críticas y 29 altas; la mayoría son de severidad baja"],
    ["Acoplamiento máx. (salida / entrada)", f"{cm['acoplamiento_eferente_max']} / {cm['acoplamiento_aferente_max']}", "Bajo: es un paquete pequeño"],
    ["Ciclos de importación", n(cm["ciclos"], 0), "Ninguno"],
    ["Mantenibilidad", f"mínimo {n(cm['mi_min'], 1)}; promedio {n(cm['mi_promedio'], 1)}", f"{cm['mi_en_cero']} archivos muy grandes tienen el índice en 0"],
    ["SATD", n(cm["satd"], 0), "Pocos comentarios de deuda declarada"],
], [4, 5, 7], "Código actual de sqlite-utils")
P("La nota A convive con funciones muy complejas: la razón de deuda se diluye en más de 10 000 líneas, mientras la deuda se "
  "concentra en unas pocas funciones de db.py y cli.py. Para decidir qué mejorar sirven más las tablas de funciones y de "
  "archivos que la nota global.")
F(CAP / "03_archivos_y_modulos.png", "Funciones más complejas, módulos más acoplados y archivos con más deuda", 14.5, recorte=2861)
P("La pestaña Hallazgos lista cada problema con su ubicación, regla, severidad y costo, y permite filtrarlos por familia, "
  "severidad o texto. En sqlite-utils, los más costosos son funciones con complejidad muy alta y consultas SQL armadas con "
  "texto.")
F(CAP / "04_hallazgos.png", "Lista de hallazgos del código actual, ordenada por costo", ANCHO)
H2("6.2 Historial de commits")
cs = hist["commits"]
grupos = {o: [c for c in cs if c["origen"] == o] for o in ("ia", "sin_declarar")}
P(f"De los 100 commits revisados, {len(cs)} cambian Python de producción: {len(grupos['ia'])} declaran el uso de IA y "
  f"{len(grupos['sin_declarar'])} no lo declaran.")


def med(xs):
    xs = sorted(xs)
    k = len(xs)
    return (xs[k // 2] if k % 2 else (xs[k // 2 - 1] + xs[k // 2]) / 2) if k else 0


T(["Grupo", "Commits", "Deuda introducida", "Líneas añadidas", "Mediana h/KLOC", "Bloqueados"],
  [[{"ia": "IA declarada", "sin_declarar": "Sin declarar"}[o], len(g), f"{n(sum(c['deuda_horas'] for c in g), 1)} h",
    n(sum(c["metricas"]["lineas_anadidas"] for c in g), 0), n(med([c["horas_kloc"] for c in g]), 1),
    sum(c["veredicto"] == "BLOQUEAR" for c in g)] for o, g in grupos.items()],
  [3, 2, 3, 3, 3, 2], "Historial de sqlite-utils por grupo")
F(CAP / "02_commits.png", "Pestaña Commits: métricas y veredicto de cada commit", ANCHO)
P(f"La comparación entre ambos grupos (Mann-Whitney U, delta de Cliff y Holm) no muestra diferencias significativas en "
  f"ninguna de las {len(ec_cmp['metricas'])} métricas: todos los p ajustados valen "
  f"{n(min(m['p_holm'] for m in ec_cmp['metricas'] if m['p_holm'] is not None), 3)} o más. Es el mismo resultado que el "
  f"experimento, en un proyecto distinto y con otro tipo de uso de la IA. Esta comparación muestra una asociación, no una "
  f"causa: los grupos no resuelven las mismas tareas y «sin declarar» no garantiza que no se haya usado IA.")
F(CAP / "05_ia_y_resto.png", "Comparación entre commits con IA declarada y el resto", 14)
P("El commit con más deuda (22,2 h) es una corrección de estilo que reescribe muchas líneas de funciones ya complejas. "
  "debtguard le atribuye las advertencias que siguen presentes en las líneas reescritas, porque mide lo que contiene cada "
  "línea nueva.")
H2("6.3 Explicación de los resultados en el dashboard")
P("Cada tarjeta del dashboard abre una explicación de la métrica, la herramienta, el cálculo y la lectura del valor obtenido, "
  "con una etiqueta (Bueno, Aceptable, Conviene revisar, Alto o Informativo) acompañada de texto, para no depender solo del "
  "color.")
F(CAP / "07_modal_advertencias.png", "Explicación de las advertencias de sqlite-utils", 14)
P("Las métricas de la versión 1.1 tienen su propia explicación. La de acoplamiento muestra los módulos con más dependencias, y "
  "la de clones parecidos señala dónde hay funciones con la misma estructura.")
F(CAP / "08_modal_acoplamiento.png", "Explicación del acoplamiento entre módulos", 14)
F(CAP / "09_modal_clones_parecidos.png", "Explicación de los clones parecidos", 14)

# ====================== 7 ======================
H1("7. Discusión")
H2("7.1 Comparación con los estudios del Hito 1")
T(["Estudio", "Qué reporta", "Qué se observó aquí"], [
    ["S01", "+39 % de complejidad cognitiva y +18 % de advertencias con agentes", "Sin diferencia en complejidad ni advertencias"],
    ["S02", "Los agentes declaran menos deuda", "Un SATD humano y ninguno del LLM; demasiado poco para comparar"],
    ["S03", "Más redundancia en el código de agentes; los humanos eliminan más", "Sin diferencia en clones, ni exactos ni parecidos; los humanos sí eliminan más"],
    ["S06", "Muchas importaciones cíclicas en parches de LLM", "Ningún ciclo nuevo en los 60 parches"],
    ["S07", "Menos días de deuda en el código traducido por LLM", "Menos horas totales en el LLM, sin diferencia por KLOC"],
    ["S04, S08", "El LLM solo no es fiable", f"El LLM resolvió {n_ok} de 30 problemas; el prototipo, determinista, mide igual cada vez"],
], [1.8, 7, 7.2], "Resultados frente a los estudios del Hito 1")
P("La diferencia con S01 y S06 se explica por el contexto. Aquí el LLM recibió los archivos exactos que debía modificar y "
  "produjo cambios muy pequeños, mientras que esos estudios observan agentes que recorren el repositorio completo y hacen "
  "cambios más amplios. Un parche de tres líneas apenas puede añadir complejidad o duplicación.")
H2("7.2 Deuda y funcionamiento")
P(f"El hallazgo más útil para la práctica es que una deuda baja no indica que un parche sirva. El LLM no acumuló más deuda, "
  f"pero falló en {30 - n_ok} de 30 problemas, y debtguard no marcó ningún hallazgo en uno de los parches que introduce un "
  f"import circular y detiene las pruebas. La medición de deuda y las pruebas responden preguntas distintas: la primera, "
  f"cuánto costará mantener el cambio; la segunda, si hace lo que debe.")
H2("7.3 Alcance de los resultados")
B("**Modelo y modalidad:** los resultados corresponden a un LLM (DeepSeek-V4-Pro) usado con un único prompt y temperatura 0, "
  "no a agentes que trabajan sobre el repositorio.")
B("**Tamaño de la muestra:** 30 pares permiten detectar diferencias medianas o grandes; diferencias pequeñas podrían existir "
  "sin aparecer en este experimento.")
B("**Lenguaje:** el prototipo y el experimento cubren solo Python.")
B("**Horas:** son las que produce el modelo SQALE con los costos de la Tabla 4. Representan una estimación del esfuerzo, no "
  "tiempo medido; el análisis de sensibilidad muestra que las conclusiones no dependen de esos valores.")
B(f"**Grupo humano:** {n_2022} de los 30 commits base son de 2022 en adelante. Con los 20 pares anteriores, el resultado es el "
  f"mismo.")

# ====================== 8 ======================
H1("8. Conclusiones")
P("Este trabajo construyó debtguard, un prototipo que detecta la deuda técnica que introduce un cambio de código Python y la "
  "expresa en horas de corrección, y lo usó para comparar soluciones humanas y de un LLM sobre los mismos problemas.")
B("**El prototipo responde al vacío del Hito 1.** Traduce la complejidad, las malas prácticas, los clones, el acoplamiento, "
  "los ciclos y la deuda declarada a una estimación en horas, como propone el SWEBOK, y mide solo lo que cada cambio introduce.")
B("**El código del LLM no acumuló más deuda.** En los 30 pares no hubo diferencias significativas en ninguna métrica, ni con "
  "las de la versión 1.1, ni con solo los parches correctos, ni con solo los casos anteriores a 2022.")
B(f"**El LLM falló mucho más en resolver los problemas.** Resolvió {n_ok} de 30, frente a 30 de 30 de las personas, y sus "
  f"parches fueron más cortos.")
B("**Medir deuda y probar el código son complementarios.** Una deuda baja no garantiza que el cambio funcione; por eso "
  "debtguard debe usarse junto con las pruebas del proyecto.")
B("**La herramienta funciona en proyectos reales.** El dashboard analizó sqlite-utils en pocos minutos, identificó las "
  "funciones que concentran la deuda y repitió el resultado del experimento al comparar los commits con IA declarada.")
P("En resumen, con un prompt acotado el LLM produce código tan mantenible como el humano según estas métricas, pero con mucha "
  "menor eficacia para resolver el problema. debtguard permite ver ambas caras de forma reproducible y explicar cada "
  "resultado.")

# ====================== Referencias ======================
H1("Referencias")
REFS = [
    "H. Washizaki, Ed., Guide to the Software Engineering Body of Knowledge (SWEBOK Guide), Version 4.0a. IEEE Computer Society, 2026.",
    "W. Cunningham, \"The WyCash portfolio management system,\" in Addendum to the Proc. OOPSLA '92, 1992, pp. 29–30.",
    "P. Avgeriou, P. Kruchten, I. Ozkaya, and C. Seaman, \"Managing technical debt in software engineering (Dagstuhl Seminar 16162),\" Dagstuhl Reports, vol. 6, no. 4, pp. 110–138, 2016.",
    "A. Potdar and E. Shihab, \"An exploratory study on self-admitted technical debt,\" in Proc. IEEE ICSME, 2014, pp. 91–100.",
    "[S01] S. Agarwal, H. He, and B. Vasilescu, \"AI IDEs or autonomous agents? Measuring the impact of coding agents on software development,\" in Proc. MSR '26, 2026.",
    "[S02] Z. Brahmi, A. Ouni, M. Sayagh, and M. A. Saied, \"Characterizing self-admitted technical debt generated by AI coding agents,\" in Proc. MSR '26, 2026, pp. 852–856.",
    "[S03] H. Huang et al., \"More code, less reuse: Investigation on code quality and reviewer sentiment towards AI-generated pull requests,\" in Proc. MSR '26, 2026, pp. 1024–1028.",
    "[S04] Q. Li et al., \"IMPACT: Identifying and classifying multiple sourced and categorized self-admitted technical debts,\" ACM TOSEM, vol. 35, no. 4, 2026.",
    "[S05] M. S. Patel, R. Dhawan, L. Bramhanwade, and D. J. Mishra, \"Code comprehension gaps in AI-assisted development,\" IEEE Access, vol. 14, pp. 66740–66757, 2026.",
    "[S06] X. Sun, D. Ståhl, K. Sandahl, and C. Kessler, \"Quality assurance of LLM-generated code: Addressing non-functional quality characteristics,\" J. Systems and Software, vol. 238, 2026.",
    "[S07] V. Bhutani, F. G. Toosi, and J. Buckley, \"Analysing software quality of AI-translated code,\" Applied Computer Systems, vol. 30, no. 1, pp. 105–121, 2025.",
    "[S08] A. Tornhill, M. Borg, N. Hagatulah, and E. Söderberg, \"ACE: Automated technical debt remediation with validated large language model refactorings,\" in Companion Proc. FSE '25, 2025, pp. 1318–1324.",
    "[S09] D. OBrien et al., \"Are prompt engineering and TODO comments friends or foes? An evaluation on GitHub Copilot,\" in Proc. ICSE '24, 2024.",
    "[S10] H. Wang et al., \"Just-in-time TODO-missed commits detection,\" IEEE Trans. Software Engineering, vol. 50, no. 11, pp. 2732–2752, 2024.",
    "S. Moreschini et al., \"The evolution of technical debt from DevOps to generative AI,\" J. Systems and Software, vol. 231, 2026.",
    "S. Gosu, D. Feitosa, and P. Avgeriou, \"The use of generative AI in technical debt management,\" Information and Software Technology, vol. 199, 2026.",
    "A. Abdulaziz, R. Sonbol, and M. Alnoukari, \"Automated detection of self-admitted technical debt,\" IEEE Access, vol. 14, pp. 20803–20825, 2026.",
    "I. Kosmas, T. Papadopoulos, and C. Michalakelis, \"Machine learning lifecycle: A survey,\" AppliedMath, vol. 6, no. 7, 2026.",
    "C. E. Jimenez et al., \"SWE-bench: Can language models resolve real-world GitHub issues?,\" in Proc. ICLR, 2024.",
    "J.-L. Letouzey, \"The SQALE method for evaluating technical debt,\" in Proc. 3rd Int. Workshop on Managing Technical Debt, 2012, pp. 31–36.",
    "G. A. Campbell, \"Cognitive complexity: An overview and evaluation,\" in Proc. Int. Conf. Technical Debt, 2018, pp. 57–58.",
    "T. J. McCabe, \"A complexity measure,\" IEEE Trans. Software Engineering, vol. SE-2, no. 4, pp. 308–320, 1976.",
    "P. Oman and J. Hagemeister, \"Metrics for assessing a software system's maintainability,\" in Proc. Conf. Software Maintenance, 1992, pp. 337–344.",
    "F. Wilcoxon, \"Individual comparisons by ranking methods,\" Biometrics Bulletin, vol. 1, no. 6, pp. 80–83, 1945.",
    "N. Cliff, \"Dominance statistics: Ordinal analyses to answer ordinal questions,\" Psychological Bulletin, vol. 114, no. 3, pp. 494–509, 1993.",
    "S. Holm, \"A simple sequentially rejective multiple test procedure,\" Scandinavian J. Statistics, vol. 6, no. 2, pp. 65–70, 1979.",
    "J. Cohen, \"A coefficient of agreement for nominal scales,\" Educational and Psychological Measurement, vol. 20, no. 1, pp. 37–46, 1960.",
    "C. Wohlin et al., Experimentation in Software Engineering. Springer, 2012.",
    "A. M. Carrasco Choque, A. R. Caceres Pari, K. Chancuaña Alvis, and L. E. Yana Agramonte, \"Deuda técnica en el desarrollo de software asistido por LLMs: un estudio de mapeo sistemático,\" informe del Hito 1, 2026.",
    "R. C. Martin, \"OO design quality metrics: An analysis of dependencies,\" 1994.",
]
for i, r in enumerate(REFS, 1):
    p = P(f"[{i}] {r}")
    p.paragraph_format.left_indent = Cm(0.9)
    p.paragraph_format.first_line_indent = Cm(-0.9)
    for run in p.runs:
        run.font.size = Pt(9.5)

# ====================== Anexos ======================
H1("Anexo A. Los 30 casos del experimento")
T(["Caso", "Proyecto", "Año", "Problema", "¿LLM resuelve?"],
  [[i.split("__")[1], casos.loc[i, "repo"].split("/")[1], fechas.loc[i, "fecha_base"][:4], PROBLEMAS[i],
    "Sí" if cor.loc[i, "llm_resuelto"] == True else "No"] for i in ids],  # noqa: E712
  [3.4, 2.3, 1.1, 7.6, 1.6], "Casos del experimento; el año es el del commit base", fuente=8)
H1("Anexo B. Prompt utilizado", nueva_pagina=False)
for lin in ("Eres un desarrollador. Repositorio: {repo}. Resuelve el siguiente issue.",
            "Devuelve SOLO un parche en formato unified diff aplicable con `git apply`.",
            "Issue: {texto del problema}",
            "Archivos relevantes: {contenido de los archivos que modifica la solución humana}"):
    r = doc.add_paragraph().add_run(lin)
    r.font.name, r.font.size = "Consolas", Pt(9)
H1("Anexo C. Reproducción", nueva_pagina=False)
P("El código, los datos y las instrucciones están en el repositorio github.com/AngelCaceresPari01/Debtguard. La etiqueta "
  "v1.0-experimento contiene la configuración con la que se midieron los parches; la rama v1.1-vacios, la versión 1.1, la "
  "re-medición y el estudio de caso. Las respuestas del LLM están guardadas, por lo que el análisis se puede repetir sin usar "
  "la API.")
H1("Anexo D. Glosario")
T(["Término", "Significado"], [
    ["Deuda técnica", "Trabajo futuro que deja un código difícil de mantener; no impide que funcione hoy, pero encarece los cambios"],
    ["Diff o parche", "Las líneas que un cambio añade, elimina o modifica en el código"],
    ["Commit", "Cambio guardado en el historial de git, con autor, fecha y mensaje"],
    ["LLM", "Modelo de lenguaje grande que genera texto o código a partir de una instrucción"],
    ["SWE-bench", "Conjunto de problemas reales de proyectos de Python, con soluciones humanas y pruebas automáticas"],
    ["SQALE", "Método que asigna a cada problema un costo de corrección en minutos y suma la deuda"],
    ["KLOC", "Mil líneas de código; h/KLOC son horas de deuda por cada mil líneas añadidas"],
    ["SATD", "Deuda técnica autoadmitida: comentarios como TODO o FIXME"],
    ["Clon Tipo 3", "Fragmento con la misma estructura que otro, aunque cambien nombres o valores"],
    ["Acoplamiento eferente y aferente", "Cuántos módulos importa uno (salida) y cuántos lo importan (entrada)"],
    ["IRD", "Índice de riesgo de deuda de debtguard, de 0 a 100"],
    ["Valor p", "Probabilidad de ver una diferencia igual o mayor si en realidad no hubiera ninguna; menos de 0,05 se considera significativo"],
    ["Delta de Cliff", "Tamaño de una diferencia entre dos grupos, de −1 a 1"],
    ["Corrección de Holm", "Ajuste de los valores p cuando se hacen varias pruebas a la vez"],
], [4.5, 11.5], "Glosario")
H1("Anexo E. Uso de asistentes de IA", nueva_pagina=False)
P("El prototipo, el análisis y la redacción se apoyaron en Claude Code. Los parches del experimento los generó únicamente "
  "DeepSeek-V4-Pro.")

pie = sec.footer.paragraphs[0]
pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
campo(pie, "PAGE")
SALIDA.parent.mkdir(parents=True, exist_ok=True)
doc.save(SALIDA)
print(SALIDA)
