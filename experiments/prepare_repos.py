"""Paso 3: deja listo un clon por proyecto. Cada clon se reutiliza con checkout (ver run_batch.py)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from debtguard.ingest.repo import ensure_clone

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    casos = pd.read_csv(RAIZ / "data" / "casos.csv")
    for slug in sorted(casos[casos.rol != "reserva"]["repo"].unique()):
        print(slug, ensure_clone(slug, RAIZ / "repos"))


if __name__ == "__main__":
    main()
