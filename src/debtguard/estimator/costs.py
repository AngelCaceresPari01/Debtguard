"""Asigna minutos de remediacion a cada hallazgo (modelo tipo SQALE)."""
from __future__ import annotations

from debtguard.models import Finding


def cost_of(f: Finding, cfg: dict) -> float:
    if f.familia == "satd":
        return float(cfg["satd_min"])
    if f.familia == "clon":
        return float(cfg["clon_min"])
    if f.familia == "regla":
        return cfg["regla_base_min"][f.categoria] * cfg["severidad_factor"][f.severidad]
    c = cfg["complejidad"]
    if f.regla.startswith("long_function"):
        return float(c["funcion_larga"]["min"])
    clave = "cognitiva" if f.regla.startswith("cognitive") else "ciclomatica"
    piso = max(f.valor_previo or 0, c[clave]["umbral"])
    return max(0.0, f.valor - piso) * c[clave]["min_por_punto"]


def assign(hallazgos: list[Finding], cfg: dict) -> float:
    for f in hallazgos:
        f.costo_min = cost_of(f, cfg)
    return sum(f.costo_min for f in hallazgos)


def sqale_rating(ratio: float) -> str:
    for limite, nota in ((0.05, "A"), (0.10, "B"), (0.20, "C"), (0.50, "D")):
        if ratio <= limite:
            return nota
    return "E"
