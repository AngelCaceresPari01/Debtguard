"""Archivos con deuda conocida y diff real del PR 3690. Los minutos esperados estan calculados a mano."""
from pathlib import Path

import pytest

from debtguard import pipeline
from debtguard.ingest.diff_reader import read_diff
from test_prototipo import caso

FIX = Path(__file__).parent / "fixtures"


def analizar(tmp_path, *nombres):
    cambio = {f"pkg/{n}.py": (FIX / f"{n}.py").read_text(encoding="utf-8") for n in nombres}
    d, repo = caso(tmp_path, {"pkg/__init__.py": ""}, cambio)
    return pipeline.analyze(d, repo, "fixture", "LLM")


def reglas(a):
    return sorted(h.regla for h in a.hallazgos)


def test_anidamiento_profundo(tmp_path):
    # Cognitiva: 1+2+...+8 por los ocho niveles, mas 1 por el `and` = 37. Costo: (37 - 15) * 3 = 66.
    a = analizar(tmp_path, "anidada")
    assert a.metricas["cognitiva_max"] == 37
    assert reglas(a) == ["cognitive>15"]
    assert a.deuda_min == 66


def test_except_generico(tmp_path):
    a = analizar(tmp_path, "except_generico")
    assert "BLE001" in reglas(a)
    assert next(h.costo_min for h in a.hallazgos if h.regla == "BLE001") == 15


def test_funcion_duplicada(tmp_path):
    a = analizar(tmp_path, "duplicada")
    clones = [h for h in a.hallazgos if h.familia == "clon"]
    assert len(clones) >= 1
    assert all(h.costo_min == 20 for h in clones)


def test_todo(tmp_path):
    a = analizar(tmp_path, "con_todo")
    assert reglas(a) == ["TODO"]
    assert a.deuda_min == 10


def test_importacion_ciclica_entre_dos_modulos(tmp_path):
    a = analizar(tmp_path, "ciclo_a", "ciclo_b")
    ciclos = [h for h in a.hallazgos if h.regla == "R0401"]
    assert ciclos, a.errores
    assert all(h.costo_min == 30 for h in ciclos)


def test_archivo_limpio(tmp_path):
    a = analizar(tmp_path, "limpio")
    assert a.hallazgos == [] and a.deuda_min == 0 and a.errores == []


@pytest.mark.parametrize("ruta", ["pr3690.diff"])
def test_diff_real_del_pr_3690(ruta):
    cs = read_diff((FIX / ruta).read_text(encoding="utf-8"), "pr3690", "LLM", "OpenAI_Codex", ".")
    assert "alpha_factory_v1/scripts/preflight.py" in cs.archivos
    assert cs.lineas_anadidas > 0
    assert all(p.endswith(".py") for p in cs.archivos)
