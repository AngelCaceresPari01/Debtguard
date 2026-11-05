"""Une los resultados del harness de SWE-bench con las metricas y repite H1-H4 con parches correctos."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from statsmodels.stats.multitest import multipletests

from analysis import PRIMARIAS, prueba

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"
LOGS = DATA / "correccion" / "logs" / "run_evaluation"


def leer(origen: str, modelo: str, iid: str) -> dict:
    ruta = LOGS / f"hito2_{origen}" / modelo / iid / "report.json"
    if not ruta.exists():
        return {f"{origen}_resuelto": None}
    r = json.loads(ruta.read_text(encoding="utf-8"))[iid]
    t = r.get("tests_status", {})
    return {f"{origen}_aplica": r.get("patch_successfully_applied"), f"{origen}_resuelto": r.get("resolved"),
            f"{origen}_f2p_ok": len(t.get("FAIL_TO_PASS", {}).get("success", [])),
            f"{origen}_f2p_mal": len(t.get("FAIL_TO_PASS", {}).get("failure", [])),
            f"{origen}_p2p_mal": len(t.get("PASS_TO_PASS", {}).get("failure", []))}


def main() -> None:
    res = pd.read_csv(DATA / "resultados.csv")
    gen = pd.read_csv(DATA / "generacion_llm.csv").set_index("instance_id")
    ids = sorted(res.instance_id.unique())
    filas = [{"instance_id": i, "repo": gen.loc[i, "repo"], "modo": gen.loc[i, "modo"],
              **leer("llm", "deepseek-v4-pro", i), **leer("humano", "humano", i)} for i in ids]
    c = pd.DataFrame(filas)
    c.to_csv(DATA / "correccion" / "correccion.csv", index=False)
    print("casos:", len(c), "| humano resuelto:", (c.humano_resuelto == True).sum(),  # noqa: E712
          "| LLM resuelto:", (c.llm_resuelto == True).sum(), "| LLM aplica:", (c.llm_aplica == True).sum())  # noqa: E712
    print("rompe pruebas previas (LLM):", (c.llm_p2p_mal > 0).sum(), "| no pasa pruebas objetivo:", (c.llm_f2p_mal > 0).sum())
    print(pd.crosstab(c.repo, c.llm_resuelto).to_string())
    print(pd.crosstab(c.modo, c.llm_resuelto).to_string())

    buenos = c[(c.llm_resuelto == True) & (c.humano_resuelto == True)].instance_id  # noqa: E712
    sub = res[res.instance_id.isin(buenos)]
    t = pd.DataFrame([{"hipotesis": h, "esperado": s, **prueba(sub, m)} for h, m, s in PRIMARIAS])
    t["p_holm"] = multipletests(t["p"], method="holm")[1]
    t.to_csv(DATA / "correccion" / "tabla_solo_correctos.csv", index=False)
    pd.set_option("display.width", 200, "display.max_columns", 20)
    print(t[["hipotesis", "metrica", "n", "med_humano", "med_llm", "llm_mayor", "empates", "llm_menor", "p", "p_holm", "cliff"]]
          .round(3).to_string())

    llm = res[res.origen == "LLM"].merge(c[["instance_id", "llm_resuelto"]], on="instance_id")
    g = llm.groupby("llm_resuelto")[["lineas_anadidas", "lineas_eliminadas", "deuda_horas", "n_hallazgos"]]
    d = pd.concat({"mediana": g.median(), "suma": g.sum()}, axis=1)
    d.to_csv(DATA / "correccion" / "llm_por_correccion.csv")
    print(d.round(2).to_string())
    for m in ("lineas_anadidas", "lineas_eliminadas", "deuda_horas"):
        r = prueba(sub, m)
        print(m, "solo correctos:", {k: round(r[k], 3) for k in ("n", "med_humano", "med_llm", "media_humano", "media_llm", "p", "cliff")})
    cs = sub.groupby("origen")[["deuda_horas", "lineas_anadidas"]].sum()
    print(cs.round(2).to_string())


if __name__ == "__main__":
    main()
