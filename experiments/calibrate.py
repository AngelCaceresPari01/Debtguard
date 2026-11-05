"""Calcula p95 de cada componente y los umbrales p75/p90 del IRD con la muestra humana de calibracion."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from debtguard.estimator import ird

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    filas = []
    for p in sorted((RAIZ / "reports" / "calibracion").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        filas.append({"horas_kloc": d["horas_kloc"], **d["metricas"]})
    p95 = {c: round(float(np.percentile([f[c] for f in filas], 95)), 4) for c in ird.COMPONENTES}
    indices = [ird.compute(f, p95) for f in filas]
    th = {"ird": {"advertir": round(float(np.percentile(indices, 75)), 2),
                  "bloquear": round(float(np.percentile(indices, 90)), 2)},
          "p95": p95, "bloquear_si": ["seguridad:critica"], "n_calibracion": len(filas)}
    (RAIZ / "config" / "thresholds.yaml").write_text(yaml.safe_dump(th, sort_keys=False), encoding="utf-8")
    print(th)


if __name__ == "__main__":
    main()
