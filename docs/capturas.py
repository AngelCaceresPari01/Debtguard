"""Ejecuta comandos reales y guarda su salida como imagen para el informe. No edita lo que imprimen."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from debtguard.ingest.repo import ensure_clone, prepare_case, reset_to

RAIZ = Path(__file__).resolve().parents[1]
FIG = RAIZ / "docs" / "figuras"
FUENTE = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 26)
ANCHO_LINEA = 106


def ejecutar(args: list[str], mostrado: str) -> list[str]:
    p = subprocess.run([sys.executable, *args], cwd=RAIZ, capture_output=True, encoding="utf-8", errors="replace")
    salida = (p.stdout + p.stderr).strip().splitlines()
    return [f"$ {mostrado}", *salida, f"[codigo de salida: {p.returncode}]", ""]


def caso(iid: str, sufijo: str, origen: str) -> list[str]:
    casos = pd.read_csv(RAIZ / "data" / "casos.csv").set_index("instance_id")
    c = casos.loc[iid]
    repo = ensure_clone(c.repo, RAIZ / "repos")
    diff = RAIZ / "casos" / f"{iid}_{sufijo}.patch"
    prepare_case(repo, c.base_commit, diff.read_text(encoding="utf-8"))
    rel_repo = repo.relative_to(RAIZ).as_posix()
    lineas = ejecutar(["-m", "debtguard", "analyze", "--diff", str(diff), "--repo", str(repo), "--case-id", f"{iid}_{sufijo}",
                       "--origin", origen],
                      f"python -m debtguard analyze --diff casos/{iid}_{sufijo}.patch --repo {rel_repo} "
                      f"--case-id {iid}_{sufijo} --origin {origen}")
    reset_to(repo, c.base_commit)
    return lineas


def imagen(lineas: list[str], nombre: str) -> None:
    partidas = []
    for l in lineas:
        while len(l) > ANCHO_LINEA:
            partidas.append(l[:ANCHO_LINEA])
            l = "  " + l[ANCHO_LINEA:]
        partidas.append(l)
    img = Image.new("RGB", (ANCHO_LINEA * 15 + 40, len(partidas) * 34 + 40), "#16181d")
    d = ImageDraw.Draw(img)
    for i, l in enumerate(partidas):
        d.text((20, 20 + i * 34), l, font=FUENTE, fill="#7fd1ff" if l.startswith("$") else "#e6e6e3")
    img.save(FIG / nombre)
    print("\n".join(partidas))


def main() -> None:
    imagen(ejecutar(["-m", "pytest", "-q", "--no-header"], "python -m pytest -q --no-header")[:-1], "consola_pruebas.png")
    imagen(caso("django__django-14752", "llm", "LLM") + caso("pytest-dev__pytest-7373", "llm", "LLM")[:-1], "consola_analisis.png")


if __name__ == "__main__":
    main()
