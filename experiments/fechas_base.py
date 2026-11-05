"""Fecha de cada commit base (amenaza P1) y repeticion de H1-H4 con los pares anteriores a 2022."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from statsmodels.stats.multitest import multipletests

from analysis import PRIMARIAS, prueba
from debtguard.ingest.repo import git

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"


def main() -> None:
    casos = pd.read_csv(DATA / "casos.csv").set_index("instance_id")
    ids = pd.read_csv(DATA / "seleccion.csv")["instance_id"]
    filas = []
    for i in ids:
        c = casos.loc[i]
        fecha = git(RAIZ / "repos" / c.repo.replace("/", "__"), "log", "-1", "--format=%ad", "--date=short", c.base_commit).stdout.strip()
        filas.append({"instance_id": i, "repo": c.repo, "fecha_base": fecha})
    f = pd.DataFrame(filas).sort_values("fecha_base")
    f.to_csv(DATA / "fechas_base.csv", index=False)
    print(f.fecha_base.min(), f.fecha_base.max(), "| desde 2022:", (f.fecha_base >= "2022").sum(), "| desde 2023:", (f.fecha_base >= "2023").sum())

    res = pd.read_csv(DATA / "resultados.csv")
    previos = f[f.fecha_base < "2022"].instance_id
    t = pd.DataFrame([{"hipotesis": h, "esperado": s, **prueba(res[res.instance_id.isin(previos)], m)} for h, m, s in PRIMARIAS])
    t["p_holm"] = multipletests(t["p"], method="holm")[1]
    t.to_csv(DATA / "tabla_antes_2022.csv", index=False)
    pd.set_option("display.width", 200, "display.max_columns", 20)
    print(t[["hipotesis", "metrica", "n", "med_humano", "med_llm", "p", "p_holm", "cliff"]].round(3).to_string())
    cor = pd.read_csv(DATA / "correccion" / "correccion.csv")
    print("resueltos por LLM antes de 2022:", (cor[cor.instance_id.isin(previos)].llm_resuelto == True).sum(), "de", len(previos))  # noqa: E712


if __name__ == "__main__":
    main()
