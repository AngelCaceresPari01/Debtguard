"""Pruebas de extremo a extremo con deuda conocida; los minutos esperados estan calculados a mano."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from debtguard import pipeline
from debtguard.estimator import costs, ird, verdict
from debtguard.ingest.diff_reader import es_excluido, read_diff
from debtguard.metrics import complexity, satd
from debtguard.models import Finding

CFG, _ = pipeline.load_config()


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def caso(tmp_path, base: dict, cambio: dict) -> tuple[str, Path]:
    """Crea un repo con `base`, aplica `cambio` en el arbol y devuelve (diff, repo)."""
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "core.autocrlf", "false")  # igual que ensure_clone
    for ruta, txt in base.items():
        p = repo / ruta
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8", newline="\n")
    (repo / "x.txt").write_text("x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    for ruta, txt in cambio.items():
        p = repo / ruta
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    d = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "HEAD"], capture_output=True,
                       text=True, encoding="utf-8").stdout
    return d, repo


def analizar(tmp_path, base, cambio):
    d, repo = caso(tmp_path, base, cambio)
    return pipeline.analyze(d, repo, "c", "LLM")


ANIDADA = """def f(a, b, c, d, e):
    r = 0
    for x in a:
        if x:
            for y in b:
                if y:
                    for z in c:
                        if z:
                            for w in d:
                                if w and e:
                                    r += 1
    return r
"""


def test_excluye_tests_y_migraciones():
    assert es_excluido("django/tests/test_a.py")
    assert es_excluido("app/migrations/0001.py")
    assert es_excluido("pkg/test_a.py")
    assert not es_excluido("pkg/latest_things.py")


def test_diff_solo_cuenta_python_de_produccion():
    d = ("diff --git a/a.py b/a.py\n--- /dev/null\n+++ b/a.py\n@@ -0,0 +1,2 @@\n+x = 1\n+\n"
         "diff --git a/tests/t.py b/tests/t.py\n--- /dev/null\n+++ b/tests/t.py\n@@ -0,0 +1 @@\n+y = 1\n"
         "diff --git a/r.md b/r.md\n--- /dev/null\n+++ b/r.md\n@@ -0,0 +1 @@\n+z\n")
    cs = read_diff(d, "c", "LLM", None, ".")
    assert cs.archivos == {"a.py": [1, 2]}
    assert cs.lineas_anadidas == 1
    assert cs.excluidos == ["tests/t.py"]


def test_satd_solo_en_lineas_anadidas_y_no_en_cadenas():
    src = '# TODO viejo\nx = "TODO no"\ny = 1  # fixme nuevo\n'
    hs = satd.analyze("a.py", src, {2, 3})
    assert [(h.linea, h.regla) for h in hs] == [(3, "FIXME")]


def test_complejidad_cobra_funcion_nueva_compleja():
    hs, m = complexity.analyze("a.py", ANIDADA, None, set(range(1, 13)), CFG)
    cog = next(h for h in hs if h.regla == "cognitive>15")
    assert m["cognitiva_max"] == cog.valor > 15
    assert costs.cost_of(cog, CFG) == (cog.valor - 15) * 3


def test_complejidad_no_culpa_al_cambio_de_la_deuda_previa():
    # Se cambia una linea sin anadir ramas: la complejidad alta ya existia.
    nueva = ANIDADA.replace("r += 1", "r += 2")
    linea = nueva.splitlines().index("                                    r += 2") + 1
    hs, m = complexity.analyze("a.py", nueva, ANIDADA, {linea}, CFG)
    assert hs == []
    assert m["delta_cognitiva"] == 0
    assert m["cognitiva_max"] > 15


def test_complejidad_cobra_solo_el_aumento():
    nueva = ANIDADA.replace("r += 1", "r += 1 if w else 2")
    linea = nueva.splitlines().index("                                    r += 1 if w else 2") + 1
    hs, _ = complexity.analyze("a.py", nueva, ANIDADA, {linea}, CFG)
    cog = next(h for h in hs if h.regla == "cognitive>15")
    assert costs.cost_of(cog, CFG) == (cog.valor - cog.valor_previo) * 3


def test_funcion_larga_solo_al_cruzar_el_umbral():
    larga = "def g():\n" + "".join(f"    a{i} = {i}\n" for i in range(80))
    hs, _ = complexity.analyze("a.py", larga, None, {2}, CFG)
    assert [h.regla for h in hs] == ["long_function>70"]
    hs2, _ = complexity.analyze("a.py", larga, larga, {2}, CFG)
    assert hs2 == []


def test_costo_por_regla():
    def regla(cat, sev):
        return Finding("a", 1, None, "regla", "X", sev, 1, categoria=cat)
    assert costs.cost_of(regla("seguridad", "critica"), CFG) == 120
    assert costs.cost_of(regla("mantenibilidad", "media"), CFG) == 15
    assert costs.cost_of(regla("estilo", "baja"), CFG) == 2.5
    assert costs.cost_of(Finding("a", 1, None, "clon", "clone", "media", 9), CFG) == 20
    assert costs.cost_of(Finding("a", 1, None, "satd", "TODO", "baja", 1), CFG) == 10


def test_except_generico_y_filtro_de_lineas(tmp_path):
    base = {"pkg/a.py": "try:\n    x = 1\nexcept Exception:\n    x = 2\n"}
    cambio = {"pkg/a.py": base["pkg/a.py"] + "try:\n    y = 1\nexcept Exception:\n    y = 2\n"}
    a = analizar(tmp_path, base, cambio)
    ble = [h for h in a.hallazgos if h.regla == "BLE001"]
    assert [h.linea for h in ble] == [7]  # el except previo (linea 3) no se atribuye al cambio
    assert ble[0].costo_min == 15


def test_clon_contra_el_proyecto(tmp_path):
    cuerpo = "".join(f"    x{i} = compute(a, b, {i})\n    if x{i} > {i}:\n        total += x{i} * {i}\n"
                     for i in range(12))
    orig = f"def uno(a, b):\n    total = 0\n{cuerpo}    return total\n"
    a = analizar(tmp_path, {"pkg/a.py": orig}, {"pkg/b.py": orig.replace("uno", "dos")})
    cl = [h for h in a.hallazgos if h.familia == "clon"]
    assert len(cl) == 1 and cl[0].archivo == "pkg/b.py" and cl[0].costo_min == 20
    assert a.metricas["clones"] == 1


def test_sin_clon_si_es_distinto(tmp_path):
    a = analizar(tmp_path, {"pkg/a.py": "x = 1\n"}, {"pkg/b.py": "y = 2\n"})
    assert a.metricas["clones"] == 0


def test_ciclo_nuevo_con_pylint(tmp_path):
    base = {"pkg/__init__.py": "", "pkg/a.py": "import pkg.b\nX = 1\n", "pkg/b.py": "Y = 2\n"}
    cambio = {"pkg/b.py": "import pkg.a\nY = 2\n"}
    a = analizar(tmp_path, base, cambio)
    assert [h.regla for h in a.hallazgos if h.familia == "regla" and h.regla == "R0401"] == ["R0401"]


def test_ciclo_previo_no_se_atribuye(tmp_path):
    base = {"pkg/__init__.py": "", "pkg/a.py": "import pkg.b\n", "pkg/b.py": "import pkg.a\n"}
    cambio = {"pkg/b.py": "import pkg.a\nimport os\n"}
    a = analizar(tmp_path, base, cambio)
    assert not [h for h in a.hallazgos if h.regla == "R0401"]


def test_archivo_limpio_no_tiene_deuda(tmp_path):
    a = analizar(tmp_path, {"pkg/a.py": "X = 1\n"}, {"pkg/a.py": 'X = 1\n\n\ndef doble(n):\n    return n * 2\n'})
    assert a.hallazgos == [] and a.deuda_min == 0 and a.nota_sqale == "A"
    assert a.errores == []


def test_codigo_con_error_de_sintaxis_se_registra(tmp_path):
    a = analizar(tmp_path, {"pkg/a.py": "X = 1\n"}, {"pkg/a.py": "def (:\n"})
    assert any("complejidad" in e for e in a.errores)
    assert any(h.severidad == "critica" for h in a.hallazgos)


def test_ird_y_veredicto():
    p95 = {c: 10 for c in ird.COMPONENTES}
    assert ird.compute({c: 0 for c in ird.COMPONENTES}, p95) == 0
    assert ird.compute({c: 99 for c in ird.COMPONENTES}, p95) == 100
    assert ird.compute({c: 0 for c in ird.COMPONENTES}, {}) is None
    th = {"ird": {"advertir": 40, "bloquear": 60}, "bloquear_si": ["seguridad:critica"]}
    assert verdict.decide(10, [], th) == "ACEPTAR"
    assert verdict.decide(50, [], th) == "ADVERTIR"
    assert verdict.decide(70, [], th) == "BLOQUEAR"
    crit = Finding("a", 1, None, "regla", "S307", "critica", 1, categoria="seguridad")
    assert verdict.decide(0, [crit], th) == "BLOQUEAR"
    assert verdict.decide(None, [], {"ird": {}}) == "SIN_CALIBRAR"


def test_cli_devuelve_json(tmp_path):
    d, repo = caso(tmp_path, {"pkg/a.py": "X = 1\n"}, {"pkg/a.py": "X = 1  # TODO revisar\n"})
    pf = tmp_path / "c.patch"
    pf.write_text(d, encoding="utf-8")
    js = tmp_path / "o.json"
    p = subprocess.run([sys.executable, "-m", "debtguard", "analyze", "--diff", str(pf), "--repo", str(repo),
                        "--case-id", "c", "--origin", "LLM", "--json", str(js)], capture_output=True, text=True)
    reporte = json.loads(js.read_text(encoding="utf-8"))
    assert reporte["metricas"]["satd"] == 1
    # El veredicto depende de la calibracion vigente; el codigo de salida debe reflejarlo.
    assert p.returncode == (1 if reporte["veredicto"] == "BLOQUEAR" else 0), p.stderr


@pytest.mark.parametrize("ratio,nota", [(0.0, "A"), (0.05, "A"), (0.1, "B"), (0.2, "C"), (0.5, "D"), (0.6, "E")])
def test_nota_sqale(ratio, nota):
    assert costs.sqale_rating(ratio) == nota
