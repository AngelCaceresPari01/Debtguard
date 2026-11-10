"""El sistema mide con los mismos resultados que debtguard y no toca la carpeta analizada."""
import hashlib
import subprocess
from pathlib import Path

import pytest

from dashboard import analyzer, gitrepo, stats
from dashboard.server import app, trabajos


def g(repo, *a, autor="Ana"):
    subprocess.run(["git", "-C", str(repo), "-c", f"user.name={autor}", "-c", "user.email=a@a", "-c", "core.autocrlf=false", *a],
                   check=True, capture_output=True)


def escribir(repo, ruta, txt):
    p = Path(repo) / ruta
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8", newline="\n")


ANIDADA = (Path(__file__).parents[2] / "tests" / "fixtures" / "anidada.py").read_text(encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "CACHE", tmp_path / "cache")
    r = tmp_path / "proyecto"
    r.mkdir()
    g(r, "init", "-q")
    g(r, "config", "core.autocrlf", "false")
    escribir(r, "pkg/a.py", "X = 1\n")
    g(r, "add", "-A")
    g(r, "commit", "-qm", "inicio")
    escribir(r, "pkg/b.py", ANIDADA)
    g(r, "add", "-A")
    g(r, "commit", "-qm", "agrega funcion\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
    escribir(r, "pkg/a.py", "X = 2  # TODO revisar\n")
    g(r, "add", "-A")
    g(r, "commit", "-qm", "cambia valor")
    escribir(r, "notas.md", "hola\n")
    g(r, "add", "-A")
    g(r, "commit", "-qm", "solo documentacion")
    return r


def huella(carpeta: Path) -> dict:
    return {str(p.relative_to(carpeta)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(carpeta.rglob("*")) if p.is_file() and "logs" not in p.parts}


NADA = (lambda *a: None, lambda: False)


def test_commits_miden_cada_cambio(repo):
    r = analyzer.analizar_commits(repo, 10, *NADA)
    assert r["revisados"] == 4 and r["sin_python"] == 1 and not r["errores"]
    por_asunto = {c["asunto"]: c for c in r["commits"]}
    assert por_asunto["agrega funcion"]["origen"] == "ia"
    assert por_asunto["agrega funcion"]["metricas"]["cognitiva_max"] == 37
    assert por_asunto["agrega funcion"]["deuda_min"] == 66
    assert por_asunto["cambia valor"]["origen"] == "sin_declarar"
    assert por_asunto["cambia valor"]["metricas"]["satd"] == 1


def test_no_modifica_la_carpeta_analizada(repo):
    escribir(repo, "pkg/sucio.py", "Y = 3\n")
    escribir(repo, "pkg/a.py", "X = 9\n")
    antes = huella(repo)
    estado = gitrepo.git(repo, "status", "--porcelain")
    cabeza = gitrepo.git(repo, "rev-parse", "HEAD")
    analyzer.analizar(repo, True, 10, True, *NADA)
    assert huella(repo) == antes
    assert gitrepo.git(repo, "status", "--porcelain") == estado
    assert gitrepo.git(repo, "rev-parse", "HEAD") == cabeza


def test_checkout_con_crlf_no_parece_modificado(tmp_path, monkeypatch):
    # Git para Windows suele usar autocrlf=true: los archivos quedan con CRLF aunque git guarde LF.
    monkeypatch.setattr(analyzer, "CACHE", tmp_path / "cache")
    r = tmp_path / "crlf"
    r.mkdir()
    def git_crlf(*a):  # sin el -c core.autocrlf=false del ayudante g()
        subprocess.run(["git", "-C", str(r), "-c", "user.name=Ana", "-c", "user.email=a@a", *a], check=True, capture_output=True)
    git_crlf("init", "-q")
    git_crlf("config", "core.autocrlf", "true")
    (r / "a.py").write_bytes(b"X = 1\r\nY = 2\r\n")
    git_crlf("add", "-A")
    git_crlf("commit", "-qm", "inicio")
    assert b"\r" not in subprocess.run(["git", "-C", str(r), "show", "HEAD:a.py"], capture_output=True).stdout  # git guarda LF
    import os
    import time
    futuro = time.time() + 120  # misma contenido, otra fecha: obliga a git a comparar el contenido
    os.utime(r / "a.py", (futuro, futuro))
    info = analyzer.inspeccionar(r)
    assert not info["sin_confirmar"]
    assert analyzer.analizar_sin_confirmar(r, lambda *a: None)["metricas"]["archivos"] == 0


def test_sin_confirmar_incluye_modificados_y_nuevos(repo):
    escribir(repo, "pkg/nuevo.py", "# FIXME luego\nZ = 1\n")
    escribir(repo, "pkg/a.py", "X = 2  # TODO revisar\nW = 1  # HACK temporal\n")
    r = analyzer.analizar_sin_confirmar(repo, lambda *a: None)
    assert r["metricas"]["satd"] == 2
    assert r["metricas"]["archivos"] == 2


def test_codigo_actual_mide_todo_y_excluye_pruebas(repo):
    escribir(repo, "tests/test_x.py", "# TODO nada\n")
    r = analyzer.analizar_codigo(repo, repo, *NADA)
    assert r["metricas"]["archivos"] == 2
    assert r["metricas"]["cognitiva_max"] == 37
    assert r["metricas"]["satd"] == 1
    assert r["excluidos"] == 1
    # (37 - 15) * 3 = 66 de complejidad y 10 del TODO
    assert r["deuda_min"] == 76
    assert r["archivos"][0]["archivo"] == "pkg/b.py" and r["funciones"][0]["cognitiva"] == 37


def test_carpeta_sin_git_analiza_codigo_y_busca_repos(tmp_path):
    (tmp_path / "plano").mkdir()
    escribir(tmp_path / "plano", "m.py", "# TODO algo\nA = 1\n")
    escribir(tmp_path / "plano", "node_modules/x/o.py", "# TODO no contar\n")
    sub = tmp_path / "plano" / "interno"
    sub.mkdir()
    g(sub, "init", "-q")
    info = analyzer.inspeccionar(tmp_path / "plano")
    assert not info["es_git"] and info["python"] == 1
    assert info["repos_internos"] == [str(sub)]
    r = analyzer.analizar(tmp_path / "plano", True, 25, True, *NADA)
    assert r["codigo"]["metricas"]["satd"] == 1 and "historial" not in r


def test_cancelar():
    with pytest.raises(analyzer.Cancelado):
        analyzer.analizar_codigo(Path(__file__).parent, None, lambda *a: None, lambda: True)


def test_cache_devuelve_lo_mismo_sin_clonar(repo, monkeypatch):
    primero = analyzer.analizar_commits(repo, 10, *NADA)

    def prohibido(*_):
        raise AssertionError("no debe clonar si todo esta en cache")
    monkeypatch.setattr(gitrepo, "Instantanea", prohibido)
    assert analyzer.analizar_commits(repo, 10, *NADA) == primero


def fila(sha, origen, horas):
    return {"sha": sha, "origen": origen, "horas_kloc": horas,
            "metricas": {"cognitiva_max": horas, "ciclomatica_max": 1, "clones": 0, "advertencias_kloc": 0, "mi_min": 50, "satd_kloc": 0}}


def test_comparacion_exige_muestra_y_acepta_etiquetas():
    pocas = [fila("a", "ia", 1), fila("b", "sin_declarar", 2)]
    r = stats.comparar(pocas)
    assert not r["suficiente"] and r["metricas"][5]["p"] is None
    filas = [fila(f"i{k}", "ia", 100 + k) for k in range(6)] + [fila(f"h{k}", "sin_declarar", k) for k in range(6)]
    r = stats.comparar(filas)
    horas = next(m for m in r["metricas"] if m["clave"] == "horas_kloc")
    assert r["suficiente"] and horas["cliff"] == 1 and horas["significativo"]
    assert stats.comparar(filas, {"i0": "sin_declarar"})["n_ia"] == 5
    import json
    json.dumps(r)  # la API devuelve este resultado como JSON


@pytest.fixture
def cliente():
    trabajos.clear()
    return app.test_client()


def test_rechaza_otros_sitios(cliente, tmp_path):
    ok = {"Host": "127.0.0.1:8765"}
    assert cliente.get(f"/api/explorar?ruta={tmp_path}", headers=ok).status_code == 200
    assert cliente.get(f"/api/explorar?ruta={tmp_path}", headers={"Host": "malo.example"}).status_code == 403
    assert cliente.post("/api/analizar", json={}, headers={**ok, "Origin": "https://malo.example"}).status_code == 403
    assert cliente.post("/api/analizar", data="x", headers=ok).status_code == 415


def test_valida_la_carpeta(cliente, tmp_path):
    h = {"Host": "127.0.0.1:8765"}
    assert cliente.get("/api/explorar?ruta=relativa", headers=h).status_code == 400
    assert cliente.get(f"/api/inspeccionar?ruta={tmp_path}/no-existe", headers=h).status_code == 400
    assert cliente.post("/api/analizar", json={"ruta": str(tmp_path)}, headers=h).status_code == 400


def test_trabajo_de_principio_a_fin(cliente, repo):
    import time
    h = {"Host": "127.0.0.1:8765"}
    jid = cliente.post("/api/analizar", json={"ruta": str(repo), "codigo": True, "commits": 5}, headers=h).get_json()["id"]
    for _ in range(600):
        t = cliente.get(f"/api/trabajos/{jid}", headers=h).get_json()
        if t["estado"] != "en_curso":
            break
        time.sleep(0.2)
    assert t["estado"] == "listo", t["mensaje"]
    assert len(t["resultado"]["historial"]["commits"]) == 3
    r = cliente.post("/api/comparar", json={"id": jid}, headers=h).get_json()
    assert r["n_ia"] == 1 and not r["suficiente"]


def test_codigo_actual_incluye_acoplamiento_y_ciclos(tmp_path):
    escribir(tmp_path, "p/__init__.py", "")
    escribir(tmp_path, "p/a.py", "import p.b\n")
    escribir(tmp_path, "p/b.py", "import p.a\n")
    r = analyzer.analizar_codigo(tmp_path, None, *NADA)
    assert r["metricas"]["ciclos"] == 1
    assert r["metricas"]["acoplamiento_eferente_max"] == 1 and r["metricas"]["acoplamiento_aferente_max"] == 1
    assert {m["modulo"] for m in r["modulos"]} == {"p.a", "p.b"}
    assert any(h["regla"] == "R0401" for h in r["hallazgos"])
