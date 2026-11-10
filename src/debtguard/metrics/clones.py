"""Clones con jscpd contra el proyecto completo; se atribuyen si el fragmento es sobre todo nuevo."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from debtguard.models import ChangeSet, Finding

RAIZ = Path(__file__).resolve().parents[3]
JSCPD = RAIZ / "node_modules" / "jscpd" / "run-jscpd.js"
IGNORAR = ("**/tests/**,**/test/**,**/testing/**,**/migrations/**,**/doc/**,**/docs/**,"
           "**/examples/**,**/test_*.py,**/.git/**")


def run_jscpd(repo: Path, min_tokens: int, similitud: float | None = None) -> list[dict]:
    with tempfile.TemporaryDirectory() as td:
        cmd = ["node", str(JSCPD), ".", "--format", "python", "--min-tokens", str(min_tokens),
               "--reporters", "json", "--output", td, "--silent", "--ignore", IGNORAR]
        if similitud:
            cmd.append(f"--similarity={similitud}")
        p = subprocess.run(cmd, cwd=repo, capture_output=True, encoding="utf-8", errors="replace", timeout=1800)
        salida = Path(td) / "jscpd-report.json"
        if not salida.exists():
            if p.returncode:
                raise RuntimeError(f"jscpd: {(p.stderr or p.stdout)[-400:]}")
            return []
        return json.loads(salida.read_text(encoding="utf-8")).get("duplicates", [])


def _rel(nombre: str, repo: Path) -> str:
    n = Path(nombre)
    return (n.resolve().relative_to(repo) if n.is_absolute() else n).as_posix().removeprefix("./")


def attribute(duplicados: list[dict], cs: ChangeSet, repo: Path, min_solap: float) -> list[Finding]:
    exactos = _fusionar(_fragmentos([d for d in duplicados if d.get("kind", "exact") != "similar"], cs, repo, min_solap), "clone")
    # Un clon parecido que se superpone a uno exacto es el mismo problema: se cuenta una sola vez.
    tapados = {(h.archivo, l) for h in exactos for l in range(h.linea, h.linea + int(h.valor))}
    parecidos = [h for h in _fusionar(_fragmentos([d for d in duplicados if d.get("kind") == "similar"], cs, repo, min_solap), "clone-similar")
                 if not any((h.archivo, l) in tapados for l in range(h.linea, h.linea + int(h.valor)))]
    return exactos + parecidos


def _fragmentos(duplicados: list[dict], cs: ChangeSet, repo: Path, min_solap: float) -> dict:
    fragmentos: dict[str, list[tuple[int, int, str]]] = {}
    for d in duplicados:
        a, b = d["firstFile"], d["secondFile"]
        for lado, otro in ((a, b), (b, a)):
            ruta = _rel(lado["name"], repo)
            lineas = set(cs.archivos.get(ruta, []))
            ini, fin = lado["start"], lado["end"]
            total = fin - ini + 1
            if lineas and total > 0 and len(lineas & set(range(ini, fin + 1))) / total >= min_solap:
                fragmentos.setdefault(ruta, []).append((ini, fin, f"{_rel(otro['name'], repo)}:{otro['start']}"))
    return fragmentos


def _fusionar(fragmentos: dict, regla: str) -> list[Finding]:
    hallazgos = []
    for ruta, frs in fragmentos.items():
        frs.sort()
        actual = list(frs[0])
        fusionados = []
        for ini, fin, otro in frs[1:]:
            if ini <= actual[1]:  # el mismo fragmento nuevo clonado de varios sitios cuenta una vez
                actual[1] = max(actual[1], fin)
            else:
                fusionados.append(actual)
                actual = [ini, fin, otro]
        fusionados.append(actual)
        for ini, fin, otro in fusionados:
            hallazgos.append(Finding(ruta, ini, None, "clon", regla, "media", fin - ini + 1,
                                     detalle=f"lineas {ini}-{fin}; {'igual' if regla == 'clone' else 'parecido'} a {otro}"))
    return hallazgos


def analyze(cs: ChangeSet, cfg: dict) -> list[Finding]:
    if not cs.archivos:
        return []
    repo = Path(cs.ruta_repo).resolve()
    c = cfg["clones"]
    return attribute(run_jscpd(repo, c["min_tokens"], c.get("similitud")), cs, repo, c["min_solapamiento"])
