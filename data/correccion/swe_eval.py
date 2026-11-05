"""Corre el harness de SWE-bench para el parche LLM y el humano de cada caso y borra luego su imagen.

Se ejecuta dentro de un contenedor Linux con el socket de Docker montado: en Windows el harness
escribiria patch.diff y eval.sh con CRLF. Es reanudable: el harness omite lo que ya tiene report.json.

  python swe_eval.py --workers 2 [--ids a b c]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import docker

DIR = Path("/work")
TIMEOUT = "1800"


def evaluar(iid: str) -> dict:
    fila = {"instance_id": iid}
    for origen in ("llm", "humano"):
        cmd = [sys.executable, "-m", "swebench.harness.run_evaluation", "-d", "SWE-bench/SWE-bench_Lite", "-s", "test",
               "-i", iid, "-p", f"/work/preds_{origen}.jsonl", "--run_id", f"hito2_{origen}", "--max_workers", "1",
               "--timeout", TIMEOUT]
        p = subprocess.run(cmd, cwd=DIR, capture_output=True, text=True, errors="replace")
        modelo = "deepseek-v4-pro" if origen == "llm" else "humano"
        rep = DIR / "logs" / "run_evaluation" / f"hito2_{origen}" / modelo / iid / "report.json"
        if rep.exists():
            r = json.loads(rep.read_text())[iid]
            fila[f"{origen}_aplica"] = r.get("patch_successfully_applied")
            fila[f"{origen}_resuelto"] = r.get("resolved")
        else:
            fila[f"{origen}_resuelto"] = None
            fila[f"{origen}_error"] = (p.stderr or p.stdout)[-300:]
    cliente = docker.from_env()
    # Solo contenedores e imagenes de este caso; el resto de Docker no se toca.
    for c in cliente.containers.list(all=True):
        if c.name.startswith("sweb.eval.") and iid in c.name:
            c.remove(force=True)
    for img in cliente.images.list():
        if any(iid.lower().replace("__", "_1776_") in t.lower() or iid.lower() in t.lower() for t in img.tags):
            try:
                cliente.images.remove(img.id, force=True)
            except docker.errors.APIError as e:
                fila["error_imagen"] = str(e)[:150]
    print(json.dumps(fila), flush=True)
    return fila


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--ids", nargs="*")
    args = ap.parse_args()
    ids = args.ids or (DIR / "ids.txt").read_text().split()
    with ThreadPoolExecutor(args.workers) as ex:
        filas = list(ex.map(evaluar, ids))
    salida = DIR / "resultado_harness.jsonl"
    previas = {}
    if salida.exists():
        previas = {json.loads(l)["instance_id"]: json.loads(l) for l in salida.read_text().splitlines()}
    previas.update({f["instance_id"]: f for f in filas})
    salida.write_text("".join(json.dumps(f) + "\n" for f in previas.values()))


if __name__ == "__main__":
    main()
