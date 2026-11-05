"""Operaciones git: clonar una vez, preparar un caso y leer archivos del commit base."""
from __future__ import annotations

import subprocess
from pathlib import Path


class PatchError(RuntimeError):
    pass


def git(repo: Path | str, *args: str, check: bool = True, input_text: str | None = None,
        timeout: int = 1800) -> subprocess.CompletedProcess:
    # Se trabaja en bytes: el modo texto de Windows convertiria LF en CRLF y romperia los parches.
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                       input=input_text.encode("utf-8") if input_text is not None else None, timeout=timeout)
    r.stdout = r.stdout.decode("utf-8", errors="replace")
    r.stderr = r.stderr.decode("utf-8", errors="replace")
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:500]}")
    return r


def ensure_clone(slug: str, repos_dir: Path) -> Path:
    destino = repos_dir / slug.replace("/", "__")
    if not (destino / ".git").exists():
        repos_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-c", "core.longpaths=true", "clone", "--filter=blob:none", "--no-checkout",
                        f"https://github.com/{slug}", str(destino)], check=True, capture_output=True)
        git(destino, "config", "core.autocrlf", "false")
        git(destino, "config", "core.longpaths", "true")
    return destino


def reset_to(repo: Path, commit: str) -> None:
    git(repo, "reset", "-q", "--hard")
    git(repo, "clean", "-qfdx")
    git(repo, "checkout", "-qf", commit)


def file_at(repo: Path, rev: str, ruta: str) -> str | None:
    r = git(repo, "show", f"{rev}:{ruta}", check=False)
    return r.stdout if r.returncode == 0 else None


def apply_patch(repo: Path, patch: str) -> tuple[str, str]:
    """Aplica en el indice. Devuelve (diff canonico, modo: estricto | laxo)."""
    if not patch.endswith("\n"):
        patch += "\n"
    modo = "estricto"
    r = git(repo, "apply", "--index", "--whitespace=nowarn", input_text=patch, check=False)
    if r.returncode:
        modo = "laxo"
        laxo = git(repo, "apply", "--index", "--recount", "--ignore-whitespace", "--whitespace=nowarn",
                   input_text=patch, check=False)
        if laxo.returncode:
            raise PatchError(r.stderr.strip()[:800])
    return git(repo, "diff", "--cached", "HEAD").stdout, modo


def prepare_case(repo: Path, commit: str, patch: str) -> tuple[str, str]:
    reset_to(repo, commit)
    return apply_patch(repo, patch)
