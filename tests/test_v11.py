"""v1.1: clones parecidos, acoplamiento y ciclos con el grafo de imports, y cambio del indice de mantenibilidad."""
from pathlib import Path

from debtguard.ingest.diff_reader import read_diff
from debtguard.metrics import coupling
from test_prototipo import analizar, caso

FIX = Path(__file__).parent / "fixtures"
ORIGINAL = (FIX / "duplicada.py").read_text(encoding="utf-8").split("\n\n\n")[0] + "\n"
RENOMBRADA = """def calcular_compras(registros, piso, techo):
    suma = 0
    n = 0
    for r in registros:
        monto = r["precio"] * r["unidades"]
        if monto >= piso and monto <= techo:
            suma = suma + monto
            n = n + 1
    media = suma / n if n else 0
    return {"suma": suma, "n": n, "media": media}
"""


def test_clon_parecido_con_otros_nombres(tmp_path):
    a = analizar(tmp_path, {"pkg/a.py": ORIGINAL}, {"pkg/b.py": RENOMBRADA})
    assert a.metricas["clones"] == 0
    assert a.metricas["clones_similares"] == 1
    h = next(h for h in a.hallazgos if h.regla == "clone-similar")
    assert h.archivo == "pkg/b.py" and h.costo_min == 20


def test_clon_exacto_no_se_cuenta_dos_veces(tmp_path):
    copia = ORIGINAL.replace("resumen_ventas", "resumen_compras")
    a = analizar(tmp_path, {"pkg/a.py": ORIGINAL}, {"pkg/b.py": copia})
    assert a.metricas["clones"] == 1 and a.metricas["clones_similares"] == 0


def test_nombres_de_modulo():
    existe = {"src/app/__init__.py", "src/app/core/__init__.py", "lib/__init__.py"}.__contains__
    assert coupling.nombre_modulo("src/app/core/x.py", existe) == "app.core.x"
    assert coupling.nombre_modulo("src/app/__init__.py", existe) == "app"
    assert coupling.nombre_modulo("scripts/run.py", existe) == "run"


def test_acoplamiento_y_relativos():
    g = coupling.construir({
        "p/__init__.py": "", "p/a.py": "from . import b\nfrom .c import f\nimport os\n",
        "p/b.py": "import p.c\n", "p/c.py": "def f():\n    import p.a\n",
    })
    assert g.aristas["p.a"] == {"p.b": 1, "p.c": 2}
    assert g.aristas["p.c"] == {}  # el import dentro de una funcion no cuenta
    filas = {f["modulo"]: f for f in coupling.resumen_modulos(g, ["p/a.py", "p/c.py"])}
    assert filas["p.a"]["eferente"] == 2 and filas["p.a"]["aferente"] == 0 and filas["p.a"]["inestabilidad"] == 1
    assert filas["p.c"]["aferente"] == 2 and filas["p.c"]["inestabilidad"] == 0
    assert g.ciclos() == []


def test_ciclos_por_componentes():
    g = coupling.construir({"a.py": "import b\n", "b.py": "import c\n", "c.py": "import a\n", "d.py": "import a\n"})
    assert g.ciclos() == [{"a", "b", "c"}]
    hallazgos, m = coupling.analizar_todo({"a.py": "import b\n", "b.py": "import a\n"})
    assert len(hallazgos) == 1 and m["ciclos"] == 1


def test_ciclo_nuevo_y_dependencias_en_un_cambio(tmp_path):
    base = {"pkg/__init__.py": "", "pkg/a.py": "import pkg.b\nX = 1\n", "pkg/b.py": "Y = 2\n"}
    a = analizar(tmp_path, base, {"pkg/b.py": "import pkg.a\nY = 2\n"})
    assert [h.regla for h in a.hallazgos if h.regla == "R0401"] == ["R0401"]
    assert a.metricas["dependencias_nuevas"] == 1
    assert a.metricas["acoplamiento_eferente_max"] == 1 and a.metricas["acoplamiento_aferente_max"] == 1


def test_enredo_previo_no_crea_ciclo_nuevo(tmp_path):
    base = {"pkg/__init__.py": "", "pkg/a.py": "import pkg.b\n", "pkg/b.py": "import pkg.a\n", "pkg/c.py": "Z = 1\n"}
    a = analizar(tmp_path, base, {"pkg/a.py": "import pkg.b\nimport pkg.c\n"})
    assert not [h for h in a.hallazgos if h.regla == "R0401"]
    assert a.metricas["dependencias_nuevas"] == 1


def test_cambio_del_indice_de_mantenibilidad(tmp_path):
    base = {"pkg/a.py": "def f(x):\n    return x\n"}
    enredado = "def f(x):\n" + "".join(f"    if x == {i}:\n        x += {i}\n" for i in range(25)) + "    return x\n"
    a = analizar(tmp_path, base, {"pkg/a.py": enredado})
    assert a.metricas["delta_mi"] < 0
    assert a.metricas["mi_en_cero"] == 0


def test_diff_sin_cambios_python_no_falla(tmp_path):
    d, _ = caso(tmp_path, {"pkg/a.py": "X = 1\n"}, {"notas.md": "hola\n"})
    assert read_diff(d, "c", "LLM", None, ".").archivos == {}
