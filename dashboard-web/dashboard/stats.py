"""Comparacion entre commits con IA declarada y el resto: Mann-Whitney U, delta de Cliff y Holm."""
from __future__ import annotations

import statistics

from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests

METRICAS = [("cognitiva_max", "Cognitiva máxima", "H1"), ("ciclomatica_max", "Ciclomática máxima", "H1"), ("clones", "Clones nuevos", "H2"),
            ("advertencias_kloc", "Advertencias/KLOC", "H3"), ("delta_mi", "Cambio del índice de mantenibilidad", "H3"),
            ("horas_kloc", "Horas/KLOC", "H4"), ("satd_kloc", "SATD/KLOC", "H4"),
            ("clones_similares", "Clones parecidos", "v1.1"), ("dependencias_nuevas", "Dependencias internas nuevas", "v1.1"),
            ("acoplamiento_eferente_max", "Acoplamiento eferente máx.", "v1.1")]
MIN_POR_GRUPO = 5


def cliffs_delta(a, b) -> float:
    gt = sum(x > y for x in a for y in b)
    lt = sum(x < y for x in a for y in b)
    return (gt - lt) / (len(a) * len(b))


def magnitud(d: float) -> str:
    d = abs(d)
    return "despreciable" if d < 0.147 else "pequeño" if d < 0.33 else "mediano" if d < 0.474 else "grande"


def _valor(fila: dict, metrica: str):
    return fila["horas_kloc"] if metrica == "horas_kloc" else fila["metricas"].get(metrica)


def comparar(filas: list[dict], etiquetas: dict[str, str] | None = None) -> dict:
    etiquetas = etiquetas or {}
    ia, resto = [], []
    for f in filas:
        (ia if etiquetas.get(f["sha"], f["origen"]) == "ia" else resto).append(f)
    salida = {"n_ia": len(ia), "n_resto": len(resto), "suficiente": len(ia) >= MIN_POR_GRUPO and len(resto) >= MIN_POR_GRUPO,
              "min_por_grupo": MIN_POR_GRUPO, "metricas": []}
    pvalores = []
    for clave, nombre, hip in METRICAS:
        a = [v for f in ia if (v := _valor(f, clave)) is not None]
        b = [v for f in resto if (v := _valor(f, clave)) is not None]
        fila = {"clave": clave, "nombre": nombre, "hipotesis": hip, "med_ia": statistics.median(a) if a else None,
                "med_resto": statistics.median(b) if b else None, "p": None, "p_holm": None, "cliff": None, "magnitud": None}
        if salida["suficiente"] and a and b:
            fila["p"] = 1.0 if set(a) == set(b) and len(set(a)) == 1 else float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
            fila["cliff"] = cliffs_delta(a, b)
            fila["magnitud"] = magnitud(fila["cliff"])
            pvalores.append(fila)
        salida["metricas"].append(fila)
    if pvalores:
        for fila, p in zip(pvalores, multipletests([f["p"] for f in pvalores], method="holm")[1]):
            fila["p_holm"] = float(p)
            fila["significativo"] = bool(p < 0.05 and abs(fila["cliff"]) >= 0.147)  # bool de Python: numpy no es serializable
    return salida
