"""Analisis exploratorio de la v1.1 sobre los mismos 30 pares. No reemplaza H1-H4 de la v1.0."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from statsmodels.stats.multitest import multipletests

from analysis import prueba

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data" / "v11"
METRICAS = [("clones_similares", "Clones parecidos (Tipo 3)"), ("clones_total", "Clones exactos + parecidos"),
            ("dependencias_nuevas", "Dependencias internas nuevas"), ("acoplamiento_eferente_max", "Acoplamiento eferente máx."),
            ("acoplamiento_aferente_max", "Acoplamiento aferente máx."), ("delta_mi", "Cambio del índice de mantenibilidad"),
            ("horas_kloc", "Horas/KLOC (v1.1)")]


def cargar(carpeta: Path, version: str) -> pd.DataFrame:
    filas = []
    for p in sorted(carpeta.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        m = d["metricas"]
        filas.append({"instance_id": d["caso_id"].rsplit("_", 1)[0], "origen": d["origen"], "version": version,
                      "horas_kloc": d["horas_kloc"], "deuda_horas": d["deuda_horas"],
                      "r0401": sum(h["regla"] == "R0401" for h in d["hallazgos"]),
                      "clones_total": m.get("clones", 0) + (m.get("clones_similares") or 0),
                      **{k: v for k, v in m.items() if not isinstance(v, (list, dict))}})
    return pd.DataFrame(filas)


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    v11 = cargar(RAIZ / "reports_v11", "v1.1")
    v10 = cargar(RAIZ / "reports", "v1.0")
    v11.to_csv(SALIDA / "resultados_v11.csv", index=False)
    t = pd.DataFrame([{"metrica": m, "nombre": n, **prueba(v11, m)} for m, n in METRICAS])
    t["p_holm"] = multipletests(t["p"], method="holm")[1]
    t.to_csv(SALIDA / "tabla_v11.csv", index=False)
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print("pares:", v11.instance_id.nunique())
    print(t[["nombre", "n", "med_humano", "med_llm", "media_humano", "media_llm", "llm_mayor", "empates", "llm_menor", "p", "p_holm", "cliff", "magnitud"]].round(3).to_string())
    resumen = v11.groupby("origen")[["clones", "clones_similares", "dependencias_nuevas", "r0401", "deuda_horas", "mi_en_cero"]].sum()
    resumen.to_csv(SALIDA / "totales_v11.csv")
    print(resumen.to_string())
    comp = v10.set_index(["instance_id", "origen"])[["deuda_horas", "r0401", "clones"]].join(
        v11.set_index(["instance_id", "origen"])[["deuda_horas", "r0401", "clones", "clones_similares"]], rsuffix="_v11")
    comp["cambio_horas"] = comp["deuda_horas_v11"] - comp["deuda_horas"]
    comp.to_csv(SALIDA / "v10_vs_v11.csv")
    print("casos con horas distintas entre v1.0 y v1.1:", int((comp.cambio_horas.abs() > 1e-9).sum()), "de", len(comp))
    print(comp[comp.cambio_horas.abs() > 1e-9].round(2).to_string())
    print("ciclos R0401: v1.0 =", int(comp.r0401.sum()), "| v1.1 =", int(comp.r0401_v11.sum()))


if __name__ == "__main__":
    main()
