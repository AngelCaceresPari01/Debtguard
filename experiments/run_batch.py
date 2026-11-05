"""Pasos 3 y 4: prepara cada caso y ejecuta el prototipo. Reanudable.

--rol calibracion  analiza los parches humanos de la muestra de calibracion
--rol comparacion  analiza 30 pares (humano y LLM) con parche LLM valido
"""
from __future__ import annotations

import argparse
import difflib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from debtguard import pipeline
from unidiff import PatchSet

from debtguard.ingest.diff_reader import es_excluido
from debtguard.ingest.repo import PatchError, ensure_clone, prepare_case, reset_to
from debtguard.report import json_report

RAIZ = Path(__file__).resolve().parents[1]
MODELO_LLM_DEFECTO = "deepseek-v4-pro"


def lineas_nuevas(diff: str) -> str:
    """Lineas anadidas en codigo de produccion, para medir la similitud entre parches."""
    salida = []
    for pf in PatchSet(diff):
        if pf.path.endswith(".py") and not es_excluido(pf.path):
            salida += [ln.value.strip() for h in pf for ln in h if ln.is_added]
    return chr(10).join(salida)


def analizar(caso, parche: str, origen: str, modelo, repo: Path, destino: Path) -> tuple[dict, str]:
    canonico, _ = prepare_case(repo, caso.base_commit, parche)
    casos_dir = RAIZ / "casos"
    sufijo = "humano" if origen == "humano" else "llm"
    (casos_dir / f"{caso.instance_id}_{sufijo}.patch").write_text(canonico, encoding="utf-8", newline="\n")
    a = pipeline.analyze(canonico, repo, f"{caso.instance_id}_{sufijo}", origen, modelo)
    json_report.write(a, destino)
    print(f"{a.caso_id}: {a.deuda_horas:.2f} h | {len(a.hallazgos)} hallazgos | errores {len(a.errores)}", flush=True)
    return a.to_dict(), canonico


def por_caso(caso, rol: str, textos, modelo: str) -> dict:
    fila = {"instance_id": caso.instance_id, "repo": caso.repo, "estado": "ok"}
    repo = ensure_clone(caso.repo, RAIZ / "repos")
    humano = textos.loc[caso.instance_id, "patch"]
    try:
        if rol == "calibracion":
            d = RAIZ / "reports" / "calibracion" / f"{caso.instance_id}.json"
            if not d.exists():
                analizar(caso, humano, "humano", None, repo, d)
            return fila
        dh = RAIZ / "reports" / f"{caso.instance_id}_humano.json"
        dl = RAIZ / "reports" / f"{caso.instance_id}_llm.json"
        pl = RAIZ / "casos" / f"{caso.instance_id}_llm.patch"
        parche_llm = pl.read_text(encoding="utf-8")
        canon_h = (RAIZ / "casos" / f"{caso.instance_id}_humano.patch")
        if not dh.exists():
            analizar(caso, humano, "humano", None, repo, dh)
        if not dl.exists():
            analizar(caso, parche_llm, "LLM", modelo, repo, dl)
        fila["similitud"] = difflib.SequenceMatcher(
            None, lineas_nuevas(canon_h.read_text(encoding="utf-8")), lineas_nuevas(parche_llm)).ratio()
    except (PatchError, RuntimeError) as e:
        fila["estado"] = f"error: {str(e)[:200]}"
        print(caso.instance_id, fila["estado"], flush=True)
    return fila


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rol", required=True, choices=["calibracion", "comparacion"])
    ap.add_argument("--modelo", default=MODELO_LLM_DEFECTO)
    args = ap.parse_args()
    casos = pd.read_csv(RAIZ / "data" / "casos.csv")
    textos = pd.read_parquet(RAIZ / "data" / "swebench_textos.parquet").set_index("instance_id")
    if args.rol == "calibracion":
        lista = casos[casos.rol == "calibracion"]
    else:
        elegidos = pd.read_csv(RAIZ / "data" / "seleccion.csv")["instance_id"]
        lista = casos[casos.instance_id.isin(elegidos)].sort_values("orden")
    grupos = [list(g.itertuples()) for _, g in lista.groupby("repo")]

    def grupo(cs):
        filas = [por_caso(c, args.rol, textos, args.modelo) for c in cs]
        reset_to(ensure_clone(cs[0].repo, RAIZ / "repos"), cs[0].base_commit)
        return filas

    with ThreadPoolExecutor(max_workers=4) as ex:
        filas = [f for fs in ex.map(grupo, grupos) for f in fs]
    pd.DataFrame(filas).to_csv(RAIZ / "data" / f"ejecucion_{args.rol}.csv", index=False)
    print(pd.DataFrame(filas)["estado"].value_counts().to_string())


if __name__ == "__main__":
    main()
