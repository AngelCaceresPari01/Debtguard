"""Pasos 5 y 6: consolida los JSON, ejecuta las pruebas, la sensibilidad de costos y los graficos."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import yaml
from scipy.stats import wilcoxon
from statsmodels.stats.multitest import multipletests

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DATA, FIG = RAIZ / "data", RAIZ / "docs" / "figuras"
# Hipotesis, metrica y sentido esperado para LLM frente a humano. Fijado antes de ver resultados.
PRIMARIAS = [("H1", "cognitiva_max", "mayor"), ("H1", "ciclomatica_max", "mayor"), ("H2", "clones", "mayor"),
             ("H3", "advertencias_kloc", "mayor"), ("H3", "mi_min", "menor"),
             ("H4", "horas_kloc", "mayor"), ("H4", "satd_kloc", "menor")]
EXPLORATORIAS = ["delta_cognitiva", "delta_ciclomatica", "delta_mi", "deuda_horas", "advertencias", "satd",
                 "lineas_anadidas", "lineas_eliminadas", "archivos"]
COLOR = {"humano": "#2a78d6", "LLM": "#eb6834"}
TINTA, TINTA2, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"


def cliffs_delta(a, b) -> float:
    gt = sum(x > y for x in a for y in b)
    lt = sum(x < y for x in a for y in b)
    return (gt - lt) / (len(a) * len(b))


def magnitud(d: float) -> str:
    d = abs(d)
    return "despreciable" if d < 0.147 else "pequeno" if d < 0.33 else "mediano" if d < 0.474 else "grande"


def consolidar() -> pd.DataFrame:
    filas = []
    for p in sorted((RAIZ / "reports").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        iid = d["caso_id"].rsplit("_", 1)[0]
        hs = d["hallazgos"]
        fila = {"instance_id": iid, "origen": d["origen"], "deuda_horas": d["deuda_horas"],
                "horas_kloc": d["horas_kloc"], "debt_ratio": d["debt_ratio"], "nota_sqale": d["nota_sqale"],
                "ird": d["ird"], "veredicto": d["veredicto"], "n_errores": len(d["errores"]),
                "errores": " | ".join(d["errores"])[:300], "n_hallazgos": len(hs), **d["metricas"]}
        for fam in ("complejidad", "regla", "clon", "satd"):
            fila[f"min_{fam}"] = sum(h["costo_min"] for h in hs if h["familia"] == fam)
        filas.append(fila)
    df = pd.DataFrame(filas)
    completos = df.groupby("instance_id")["origen"].nunique()
    df = df[df.instance_id.isin(completos[completos == 2].index)].sort_values(["instance_id", "origen"])
    df.to_csv(DATA / "resultados.csv", index=False)
    return df


def prueba(df: pd.DataFrame, metrica: str) -> dict:
    w = df.pivot(index="instance_id", columns="origen", values=metrica).dropna()
    h, l = w["humano"].to_numpy(float), w["LLM"].to_numpy(float)
    dif = l - h
    if np.all(dif == 0):
        est, p = 0.0, 1.0
    else:
        r = wilcoxon(l, h, zero_method="wilcox", alternative="two-sided")
        est, p = float(r.statistic), float(r.pvalue)
    return {"metrica": metrica, "n": len(w), "med_humano": float(np.median(h)), "med_llm": float(np.median(l)),
            "media_humano": float(h.mean()), "media_llm": float(l.mean()), "llm_mayor": int((dif > 0).sum()),
            "empates": int((dif == 0).sum()), "llm_menor": int((dif < 0).sum()), "W": est, "p": p,
            "cliff": cliffs_delta(l, h), "magnitud": magnitud(cliffs_delta(l, h))}


def tabla_hipotesis(df: pd.DataFrame) -> pd.DataFrame:
    filas = [{"hipotesis": hip, "esperado": sentido, **prueba(df, m)} for hip, m, sentido in PRIMARIAS]
    t = pd.DataFrame(filas)
    t["p_holm"] = multipletests(t["p"], method="holm")[1]

    def decidir(f):
        if f.p_holm >= 0.05 or abs(f.cliff) < 0.147:
            return "No se rechaza H0"
        coincide = (f.cliff > 0) == (f.esperado == "mayor")
        return "Se rechaza H0" if coincide else "Se rechaza H0, sentido contrario"
    t["decision"] = t.apply(decidir, axis=1)
    return t


def sensibilidad(df: pd.DataFrame) -> pd.DataFrame:
    """Varia +-25 % el costo de cada familia. Escalar todas por igual no altera los rangos."""
    filas = []
    for fam in ("complejidad", "regla", "clon", "satd"):
        for factor in (0.75, 1.25):
            d = df.copy()
            total = sum(d[f"min_{x}"] * (factor if x == fam else 1) for x in ("complejidad", "regla", "clon", "satd"))
            d["sens"] = np.where(d["lineas_anadidas"] > 0, (total / 60) / (d["lineas_anadidas"] / 1000), 0)
            r = prueba(d, "sens")
            filas.append({"familia": fam, "factor": factor, "med_humano": r["med_humano"], "med_llm": r["med_llm"],
                          "p": r["p"], "cliff": r["cliff"]})
    return pd.DataFrame(filas)


def excluir_similares(df: pd.DataFrame) -> pd.DataFrame:
    ruta = DATA / "ejecucion_comparacion.csv"
    if not ruta.exists():
        return df
    e = pd.read_csv(ruta)
    return df[~df.instance_id.isin(e[e.similitud > 0.9].instance_id)]


def boxplots(df: pd.DataFrame) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": TINTA, "axes.labelcolor": TINTA2,
                         "xtick.color": TINTA2, "ytick.color": TINTA2})
    paneles = [("cognitiva_max", "Cognitiva máxima (H1)"), ("ciclomatica_max", "Ciclomática máxima (H1)"),
               ("clones", "Clones nuevos (H2)"), ("advertencias_kloc", "Advertencias/KLOC (H3)"),
               ("mi_min", "Índice de mantenibilidad (H3)"), ("horas_kloc", "Horas/KLOC (H4)"),
               ("satd_kloc", "SATD/KLOC (H4)"), ("lineas_anadidas", "Líneas añadidas (contexto)")]
    fig, ejes = plt.subplots(2, 4, figsize=(10, 5.2))
    rng = np.random.default_rng(42)
    for ax, (m, titulo) in zip(ejes.flat, paneles):
        for i, origen in enumerate(("humano", "LLM")):
            v = df[df.origen == origen][m].dropna().to_numpy(float)
            ax.boxplot(v, positions=[i], widths=0.5, showfliers=False, patch_artist=True,
                       boxprops={"facecolor": "white", "edgecolor": COLOR[origen], "linewidth": 1.5},
                       medianprops={"color": COLOR[origen], "linewidth": 2},
                       whiskerprops={"color": COLOR[origen]}, capprops={"color": COLOR[origen]})
            ax.scatter(i + rng.uniform(-0.12, 0.12, len(v)), v, s=9, color=COLOR[origen], alpha=0.55,
                       linewidths=0, zorder=3)
        ax.set_xticks([0, 1], ["Humano", "LLM"])
        ax.set_title(titulo, fontsize=9, loc="left", color=TINTA)
        ax.grid(axis="y", color=REJILLA, linewidth=0.7)
        ax.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color(REJILLA)
        ax.tick_params(length=0)
    fig.tight_layout()
    fig.savefig(FIG / "boxplots.png", dpi=200)
    plt.close(fig)


def composicion(df: pd.DataFrame) -> pd.DataFrame:
    c = df.groupby("origen")[["min_complejidad", "min_regla", "min_clon", "min_satd", "deuda_horas",
                              "lineas_anadidas", "n_hallazgos"]].sum()
    c.to_csv(DATA / "composicion_deuda.csv")
    return c


def main() -> None:
    df = consolidar()
    t = tabla_hipotesis(df)
    t.to_csv(DATA / "tabla_hipotesis.csv", index=False)
    pd.DataFrame([prueba(df, m) for m in EXPLORATORIAS]).to_csv(DATA / "tabla_exploratoria.csv", index=False)
    sensibilidad(df).to_csv(DATA / "sensibilidad_costos.csv", index=False)
    d2 = excluir_similares(df)
    t2 = tabla_hipotesis(d2)
    t2.to_csv(DATA / "tabla_sin_similares.csv", index=False)
    boxplots(df)
    c = composicion(df)
    pd.crosstab(df.origen, df.veredicto).to_csv(DATA / "veredictos.csv")
    pd.crosstab(df.origen, df.nota_sqale).to_csv(DATA / "notas_sqale.csv")
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print("pares:", df.instance_id.nunique(), "| pares sin similares:", d2.instance_id.nunique())
    print(t[["hipotesis", "metrica", "n", "med_humano", "med_llm", "llm_mayor", "empates", "llm_menor", "W", "p",
             "p_holm", "cliff", "magnitud", "decision"]].round(4).to_string())
    print(c.round(1).to_string())
    print(pd.read_csv(DATA / "tabla_exploratoria.csv").round(4)[["metrica", "n", "med_humano", "med_llm", "media_humano",
                                                                 "media_llm", "p", "cliff"]].to_string())
    print(pd.read_csv(DATA / "sensibilidad_costos.csv").round(4).to_string())
    print(pd.read_csv(DATA / "veredictos.csv").to_string())
    print(pd.read_csv(DATA / "notas_sqale.csv").to_string())
    print("errores por caso:", df[df.n_errores > 0][["instance_id", "origen", "errores"]].to_string())


if __name__ == "__main__":
    main()
