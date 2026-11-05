"""Crea las predicciones para el harness oficial de SWE-bench.

Usa data/swebench_textos.parquet para el parche humano y los diffs canonicos de casos/ para el LLM.
Salida: data/correccion/preds_llm.jsonl y preds_humano.jsonl, mas una lista de ids.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data" / "correccion"


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    ids = pd.read_csv(RAIZ / "data" / "seleccion.csv")["instance_id"].tolist()
    textos = pd.read_parquet(RAIZ / "data" / "swebench_textos.parquet").set_index("instance_id")
    with open(SALIDA / "preds_llm.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i in ids:
            parche = (RAIZ / "casos" / f"{i}_llm.patch").read_bytes().decode("utf-8")
            f.write(json.dumps({"instance_id": i, "model_name_or_path": "deepseek-v4-pro", "model_patch": parche}) + "\n")
    with open(SALIDA / "preds_humano.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i in ids:
            f.write(json.dumps({"instance_id": i, "model_name_or_path": "humano", "model_patch": textos.loc[i, "patch"]}) + "\n")
    (SALIDA / "ids.txt").write_text(" ".join(ids), encoding="utf-8")
    print(len(ids), "casos")


if __name__ == "__main__":
    main()
