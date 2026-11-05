from __future__ import annotations

from debtguard.models import Finding


def decide(ird: float | None, hallazgos: list[Finding], th: dict) -> str:
    claves = {f"{f.categoria}:{f.severidad}" for f in hallazgos if f.familia == "regla"}
    if claves & set(th.get("bloquear_si", [])):
        return "BLOQUEAR"
    lim = th.get("ird") or {}
    if ird is None or lim.get("advertir") is None:
        return "SIN_CALIBRAR"
    if ird >= lim["bloquear"]:
        return "BLOQUEAR"
    return "ADVERTIR" if ird >= lim["advertir"] else "ACEPTAR"
