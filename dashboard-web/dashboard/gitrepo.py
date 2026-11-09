"""Lectura de la carpeta y de su git. Nunca escribe en la carpeta seleccionada."""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

ARBOL_VACIO = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
OMITIR = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", "dist", "build", ".tox", ".mypy_cache",
          ".pytest_cache", ".ruff_cache", "site-packages", ".idea", ".vscode", "target", "vendor"}
_IA = re.compile(r"(co-authored-by:[^\n]*(claude|copilot|cursor|codex|devin|aider|gemini|chatgpt|openai|anthropic|windsurf))"
                 r"|generated (with|by) .{0,30}(claude|copilot|cursor|codex|chatgpt|gemini|aider|devin)", re.IGNORECASE)
_ENTORNO = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
# Una carpeta analizada no debe poder ejecutar programas a traves de su configuracion de git.
_SEGURO = ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "core.quotepath=off", "-c", "core.longpaths=true",
           "-c", "core.autocrlf=false", "-c", "diff.external=", "-c", "core.sshCommand="]


class GitError(RuntimeError):
    pass


def git(carpeta: Path | str, *args: str, entrada: bytes | None = None, check: bool = True, timeout: int = 900) -> str:
    r = subprocess.run(["git", *_SEGURO, "-C", str(carpeta), *args], capture_output=True, input=entrada, timeout=timeout, env=_ENTORNO)
    if check and r.returncode:
        raise GitError(r.stderr.decode("utf-8", "replace").strip()[:400] or f"git {args[0]} falló")
    return r.stdout.decode("utf-8", "replace")


def raiz_git(carpeta: Path | str) -> Path | None:
    try:
        salida = git(carpeta, "rev-parse", "--show-toplevel", timeout=30).strip()
    except (GitError, OSError, subprocess.TimeoutExpired):
        return None
    return Path(salida) if salida else None


def origen_declarado(autor: str, mensaje: str) -> str:
    return "ia" if _IA.search(f"{autor}\n{mensaje}") else "sin_declarar"


def listar_commits(raiz: Path, limite: int) -> list[dict]:
    formato = "%H%x1f%P%x1f%an%x1f%aI%x1f%s%x1f%b%x1e"
    salida = git(raiz, "log", "--no-merges", f"-n{int(limite)}", f"--format={formato}", check=False)
    commits = []
    for bloque in salida.split("\x1e"):
        partes = bloque.strip("\n").split("\x1f")
        if len(partes) != 6:
            continue
        sha, padres, autor, fecha, asunto, cuerpo = partes
        commits.append({"sha": sha, "corto": sha[:8], "padre": padres.split()[0] if padres.strip() else ARBOL_VACIO,
                        "autor": autor, "fecha": fecha, "asunto": asunto,
                        "origen": origen_declarado(autor, f"{asunto}\n{cuerpo}")})
    return commits


def _forzar_borrado(funcion, ruta, _exc):
    os.chmod(ruta, stat.S_IWRITE)
    funcion(ruta)


class Instantanea:
    """Clon temporal con objetos compartidos: los checkouts ocurren aqui, no en la carpeta original."""

    def __init__(self, raiz: Path):
        self.temporal = Path(tempfile.mkdtemp(prefix="debtguard-"))
        self.ruta = self.temporal / "repo"
        subprocess.run(["git", *_SEGURO, "clone", "-q", "--shared", "--no-checkout", str(raiz), str(self.ruta)],
                       check=True, capture_output=True, env=_ENTORNO, timeout=600)
        git(self.ruta, "config", "core.autocrlf", "false")
        git(self.ruta, "config", "core.longpaths", "true")
        git(self.ruta, "config", "core.hooksPath", "/dev/null")

    def ir_a(self, sha: str) -> None:
        git(self.ruta, "reset", "-q", "--hard", check=False)
        git(self.ruta, "clean", "-qfdx", check=False)
        git(self.ruta, "checkout", "-qf", sha)

    def diff(self, padre: str, sha: str) -> str:
        return git(self.ruta, "diff", "--no-ext-diff", "--no-textconv", "--no-color", padre, sha, "--", "*.py")

    def cerrar(self) -> None:
        shutil.rmtree(self.temporal, onexc=_forzar_borrado)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()


def aplicar_sin_confirmar(raiz: Path, inst: Instantanea) -> str:
    """Reproduce en la instantanea los cambios sin confirmar y devuelve su diff frente a HEAD."""
    inst.ir_a("HEAD")
    cambios = subprocess.run(["git", *_SEGURO, "-C", str(raiz), "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--binary", "HEAD"],
                             capture_output=True, env=_ENTORNO, timeout=300, check=True).stdout
    if cambios.strip():
        git(inst.ruta, "apply", "--index", "--whitespace=nowarn", entrada=cambios)
    for ruta in git(raiz, "ls-files", "-o", "--exclude-standard", "--", "*.py").splitlines():
        destino = inst.ruta / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raiz / ruta, destino)
        git(inst.ruta, "add", "--", ruta)
    return git(inst.ruta, "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--cached", "HEAD", "--", "*.py")


def archivos_de_carpeta(carpeta: Path, raiz: Path | None, limite: int = 200_000) -> list[str]:
    """Rutas relativas a `carpeta`. En un repo respeta .gitignore; fuera de git omite carpetas pesadas."""
    if raiz is not None:
        salida = git(carpeta, "ls-files", "-co", "--exclude-standard", timeout=120)
        return [r for r in salida.splitlines() if r and (carpeta / r).is_file()][:limite]
    rutas = []
    for base, dirs, nombres in os.walk(carpeta):
        dirs[:] = [d for d in dirs if d not in OMITIR]
        for nombre in nombres:
            rutas.append((Path(base) / nombre).relative_to(carpeta).as_posix())
            if len(rutas) >= limite:
                return rutas
    return rutas


def buscar_repos(carpeta: Path, profundidad: int = 3, maximo: int = 40) -> list[str]:
    """Repositorios git dentro de la carpeta, sin entrar en carpetas pesadas."""
    encontrados = []

    def recorrer(actual: Path, nivel: int) -> None:
        if nivel > profundidad or len(encontrados) >= maximo:
            return
        try:
            hijos = sorted((e for e in os.scandir(actual) if e.is_dir(follow_symlinks=False)), key=lambda e: e.name.lower())
        except OSError:
            return
        for e in hijos:
            if e.name == ".git" and actual != carpeta:
                encontrados.append(str(actual))
                return
        for e in hijos:
            if e.name not in OMITIR and not e.name.startswith("."):
                recorrer(Path(e.path), nivel + 1)

    recorrer(carpeta, 0)
    return encontrados
