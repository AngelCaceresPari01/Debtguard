"""Paso 1: muestrea SWE-bench Lite con semilla fija y guarda data/casos.csv.

Orden: 30 de comparacion, 20 humanos de calibracion (sin solaparse) y el resto como reserva
para reemplazar casos cuyo parche LLM no se aplique. Maximo 4 issues por proyecto.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from datasets import load_dataset

from debtguard.ingest.diff_reader import read_diff

SEMILLA, N_COMP, N_CALIB, TOPE = 42, 30, 20, 4
RAIZ = Path(__file__).resolve().parents[1]


def tamano(patch: str) -> int:
    cs = read_diff(patch, "x", "h", None, ".")
    return cs.lineas_anadidas + cs.lineas_eliminadas


def main() -> None:
    df = load_dataset("princeton-nlp/SWE-bench_Lite", split="test").to_pandas()
    df["lineas"] = df["patch"].map(tamano)
    apto = df[df["lineas"].between(10, 300)].sample(frac=1, random_state=SEMILLA).reset_index(drop=True)
    print(f"Lite: {len(df)} issues; aptos (10-300 lineas): {len(apto)}")
    print(apto["repo"].value_counts().to_string())

    filas, usados = [], {"comparacion": {}, "calibracion": {}}
    for _, f in apto.iterrows():
        rol = "reserva"
        for candidato, n in (("comparacion", N_COMP), ("calibracion", N_CALIB)):
            cuenta = usados[candidato]
            if sum(cuenta.values()) < n and cuenta.get(f["repo"], 0) < TOPE:
                cuenta[f["repo"]] = cuenta.get(f["repo"], 0) + 1
                rol = candidato
                break
        filas.append({"instance_id": f["instance_id"], "repo": f["repo"], "base_commit": f["base_commit"],
                      "lineas_humano": f["lineas"], "rol": rol})
    casos = pd.DataFrame(filas)
    casos["orden"] = range(len(casos))
    (RAIZ / "data").mkdir(exist_ok=True)
    casos.to_csv(RAIZ / "data" / "casos.csv", index=False)
    df[["instance_id", "problem_statement", "patch"]].to_parquet(RAIZ / "data" / "swebench_textos.parquet")
    print(casos["rol"].value_counts().to_string())
    print(casos[casos.rol == "comparacion"]["repo"].value_counts().to_string())


if __name__ == "__main__":
    main()
