"""Regresiones encontradas al ejecutar el prototipo sobre repositorios reales."""
import subprocess

from debtguard.ingest.repo import prepare_case
from debtguard.metrics import static
from test_prototipo import caso


def test_reenumerar_ciclos_previos_no_crea_deuda():
    # Pylint lista otros ciclos del mismo enredo al anadir un import ya enredado.
    fuentes = {"p/a.py": "from p import b\n"}
    antes = {frozenset({"p.a", "p.b"}), frozenset({"p.b", "p.c"})}
    despues = {frozenset({"p.a", "p.b", "p.c"}), frozenset({"p.b", "p.c", "p.d"})}
    assert static.nuevos_por_linea([("p/a.py", 1)], fuentes, antes, despues) == []


def test_un_import_genera_como_mucho_un_ciclo():
    fuentes = {"p/a.py": "from . import z\n"}
    despues = {frozenset({"p.a", "p.z"}), frozenset({"p.a", "p.z", "p.k"})}
    r = static.nuevos_por_linea([("p/a.py", 1)], fuentes, set(), despues)
    assert len(r) == 1 and r[0][:2] == ("p/a.py", 1)


def test_ciclo_que_no_pasa_por_el_import_no_se_atribuye():
    fuentes = {"p/a.py": "import os\n"}
    assert static.nuevos_por_linea([("p/a.py", 1)], fuentes, set(), {frozenset({"p.a", "p.b"})}) == []


def test_parche_se_aplica_en_modo_estricto_sin_tocar_finales_de_linea(tmp_path):
    d, repo = caso(tmp_path, {"pkg/a.py": "A = 1\nB = 2\n"}, {"pkg/a.py": "A = 1\nB = 3\n"})
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    canonico, modo = prepare_case(repo, base, d)
    assert modo == "estricto"
    assert b"\r" not in (repo / "pkg" / "a.py").read_bytes()
    assert canonico.count("\n+B = 3") == 1
