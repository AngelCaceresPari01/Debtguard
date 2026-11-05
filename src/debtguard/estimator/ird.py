"""Indice de riesgo de deuda: 5 componentes normalizados con el p95 de calibracion."""
from __future__ import annotations

COMPONENTES = ("horas_kloc", "cognitiva_max", "clones", "adv_altas_kloc", "satd_kloc")


def _norm(valor: float, p95: float) -> float:
    if p95 <= 0:
        return 1.0 if valor > 0 else 0.0
    return min(1.0, valor / p95)


def compute(valores: dict, p95: dict) -> float | None:
    if not p95:
        return None
    return round(100 * sum(0.2 * _norm(valores[c], p95.get(c, 0)) for c in COMPONENTES), 2)
