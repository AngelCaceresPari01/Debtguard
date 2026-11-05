"""Reglas estaticas: Ruff sobre lineas anadidas y ciclos nuevos con Pylint R0401."""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

from debtguard.models import ChangeSet, Finding

_IMPORT = re.compile(r"^\s*(from\s+\S+\s+)?import\s")
_CICLO = re.compile(r"Cyclic import \((.+)\)")


def clasificar(codigo: str, mapa: dict) -> tuple[str, str]:
    for n in range(len(codigo), 0, -1):
        if codigo[:n] in mapa:
            return tuple(mapa[codigo[:n]])
    return ("mantenibilidad", "baja")


def run_ruff(cs: ChangeSet, cfg: dict) -> list[Finding]:
    if not cs.archivos:
        return []
    r = cfg["ruff"]
    cmd = [sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache", "--exit-zero",
           "--output-format", "json", "--select", ",".join(r["select"]), "--ignore", ",".join(r["ignore"]),
           *cs.archivos]
    p = subprocess.run(cmd, cwd=cs.ruta_repo, capture_output=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError(f"ruff: {p.stderr[:400]}")
    raiz = Path(cs.ruta_repo).resolve()
    hallazgos = []
    for it in json.loads(p.stdout or "[]"):
        ruta = Path(it["filename"]).resolve().relative_to(raiz).as_posix()
        linea = it["location"]["row"]
        if linea not in cs.archivos.get(ruta, []):
            continue
        codigo = it.get("code") or "invalid-syntax"
        cat, sev = clasificar(codigo, r["mapa"])
        hallazgos.append(Finding(ruta, linea, None, "regla", codigo, sev, 1, categoria=cat,
                                 detalle=it.get("message", "")[:160]))
    return hallazgos


def _ciclos(raiz: Path, objetivo: str, timeout: int) -> set[frozenset[str]]:
    cmd = [sys.executable, "-m", "pylint", "--disable=all", "--enable=R0401", "--output-format=json",
           "--recursive=y", "--score=n", objetivo]
    p = subprocess.run(cmd, cwd=raiz, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    if p.returncode >= 32 or not p.stdout.strip().startswith("["):
        raise RuntimeError(f"pylint: {p.stderr[-300:]}")
    ciclos = set()
    for m in json.loads(p.stdout):
        g = _CICLO.search(m.get("message", ""))
        if g:
            ciclos.add(frozenset(x.strip() for x in g.group(1).split("->")))
    return ciclos


def _snapshot_base(repo: Path, rev: str, objetivo: str, destino: Path) -> bool:
    p = subprocess.run(["git", "-C", str(repo), "archive", rev, objetivo], capture_output=True)
    if p.returncode:
        return False
    with tarfile.open(fileobj=BytesIO(p.stdout)) as t:
        t.extractall(destino, filter="data")
    return True


def _modulo(ruta: str) -> str:
    partes = ruta.removesuffix(".py").split("/")
    return ".".join(partes[:-1] if partes[-1] == "__init__" else partes)


def _destinos(linea: str, modulo: str) -> set[str]:
    """Modulos que nombra una linea de import, con los relativos ya resueltos."""
    try:
        nodo = ast.parse(linea.strip()).body[0]
    except (SyntaxError, IndexError):
        return set()
    if isinstance(nodo, ast.Import):
        return {a.name for a in nodo.names}
    if not isinstance(nodo, ast.ImportFrom):
        return set()
    base = nodo.module or ""
    if nodo.level:
        paquete = modulo.split(".")[:-nodo.level]
        base = ".".join([*paquete, base] if base else paquete)
    return {base, *(f"{base}.{a.name}" for a in nodo.names)}


def _componentes(ciclos: set[frozenset[str]]) -> list[set[str]]:
    grupos: list[set[str]] = []
    for ciclo in ciclos:
        nuevo = set(ciclo)
        for g in [g for g in grupos if g & nuevo]:
            nuevo |= g
            grupos.remove(g)
        grupos.append(nuevo)
    return grupos


def nuevos_por_linea(imports, fuentes, antes, despues) -> list[tuple[str, int, set[str]]]:
    """Atribuye como mucho un ciclo a cada import anadido.

    Pylint enumera ciclos de forma distinta al cambiar el grafo, asi que la diferencia de conjuntos no
    basta: el ciclo debe contener el modulo y su destino, y ambos no deben estar ya enredados en la base.
    """
    comps = _componentes(antes)
    salida = []
    for archivo, linea in imports:
        mod = _modulo(archivo)
        destinos = _destinos(fuentes[archivo].splitlines()[linea - 1], mod) - {mod}
        for ciclo in despues - antes:
            comunes = destinos & ciclo
            if mod not in ciclo or not comunes:
                continue
            if any(mod in c and comunes & c for c in comps):
                continue
            salida.append((archivo, linea, set(ciclo)))
            break
    return salida


def run_cycles(cs: ChangeSet, fuentes: dict[str, str], cfg: dict) -> list[Finding]:
    """Solo si el cambio anade imports: compara los ciclos del paquete antes y despues."""
    imports = []
    for archivo, lineas in cs.archivos.items():
        texto = fuentes.get(archivo, "").splitlines()
        imports += [(archivo, l) for l in lineas if l <= len(texto) and _IMPORT.match(texto[l - 1])]
    if not imports:
        return []
    repo = Path(cs.ruta_repo).resolve()
    hallazgos = []
    timeout = cfg.get("pylint_timeout_s", 300)
    for objetivo in sorted({a.split("/")[0] for a, _ in imports}):
        despues = _ciclos(repo, objetivo, timeout)
        with tempfile.TemporaryDirectory() as td:
            hay_base = _snapshot_base(repo, cs.base_rev, objetivo, Path(td))
            antes = _ciclos(Path(td), objetivo, timeout) if hay_base else set()
        de_objetivo = [(a, l) for a, l in imports if a.split("/")[0] == objetivo]
        for archivo, linea, ciclo in nuevos_por_linea(de_objetivo, fuentes, antes, despues):
            hallazgos.append(Finding(archivo, linea, None, "regla", "R0401", "alta", 1, categoria="mantenibilidad",
                                     detalle=" -> ".join(sorted(ciclo))[:160]))
    return hallazgos
