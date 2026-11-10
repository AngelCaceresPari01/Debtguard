"""Vuelve a medir los 60 parches del experimento con la v1.1 (clones parecidos, acoplamiento y ciclos por grafo).

No toca reports/ (resultados de la v1.0, congelados en v1.0-experimento): escribe en reports_v11/.
Requiere los clones de repos/ (experiments/prepare_repos.py).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from debtguard import pipeline
from debtguard.ingest.repo import PatchError, ensure_clone, prepare_case, reset_to
from debtguard.report import json_report

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "reports_v11"


def grupo(casos) -> list[str]:
    repo = ensure_clone(casos[0].repo, RAIZ / "repos")
    mensajes = []
    for c in casos:
        for sufijo, origen, modelo in (("humano", "humano", None), ("llm", "LLM", "deepseek-v4-pro")):
            destino = SALIDA / f"{c.instance_id}_{sufijo}.json"
            if destino.exists():
                continue
            parche = (RAIZ / "casos" / f"{c.instance_id}_{sufijo}.patch").read_text(encoding="utf-8")
            try:
                canonico, _ = prepare_case(repo, c.base_commit, parche)
            except (PatchError, RuntimeError) as e:
                mensajes.append(f"{c.instance_id}_{sufijo}: {e}")
                continue
            a = pipeline.analyze(canonico, repo, f"{c.instance_id}_{sufijo}", origen, modelo)
            json_report.write(a, destino)
            mensajes.append(f"{a.caso_id}: {a.deuda_horas:.2f} h | parecidos {a.metricas['clones_similares']} | "
                            f"dep. nuevas {a.metricas['dependencias_nuevas']} | errores {len(a.errores)}")
            print(mensajes[-1], flush=True)
    reset_to(repo, casos[0].base_commit)
    return mensajes


def main() -> None:
    SALIDA.mkdir(exist_ok=True)
    casos = pd.read_csv(RAIZ / "data" / "casos.csv")
    elegidos = pd.read_csv(RAIZ / "data" / "seleccion.csv")["instance_id"]
    lista = casos[casos.instance_id.isin(elegidos)].sort_values("orden")
    grupos = [list(g.itertuples()) for _, g in lista.groupby("repo")]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for mensajes in ex.map(grupo, grupos):
            for m in mensajes:
                if "error" in m.lower() and "errores 0" not in m:
                    print("AVISO", m)
    print(len(list(SALIDA.glob("*.json"))), "reportes en", SALIDA)


if __name__ == "__main__":
    main()
