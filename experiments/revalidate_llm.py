"""Vuelve a aplicar las respuestas guardadas de DeepSeek, sin llamar a la API, y fija los 30 casos.

Regla: se recorren comparacion y reserva en el orden del muestreo; entra todo caso con parche valido
hasta llegar a 30, con un maximo de 4 por proyecto. Se toma el primer intento que se aplique.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import pandas as pd

from debtguard.ingest.diff_reader import read_diff
from debtguard.ingest.repo import PatchError, ensure_clone, prepare_case
from generate_llm import extraer_diff

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    casos = pd.read_csv(RAIZ / "data" / "casos.csv").sort_values("orden")
    filas, por_repo = [], collections.Counter()
    for c in casos[casos.rol != "calibracion"].itertuples():
        ruta = RAIZ / "data" / "llm" / f"{c.instance_id}.json"
        if not ruta.exists():
            continue
        reg = json.loads(ruta.read_text(encoding="utf-8"))
        repo = ensure_clone(c.repo, RAIZ / "repos")
        reg["estado"] = "no_aplica"
        reg.pop("intento_ok", None)
        reg.pop("modo_aplicacion", None)
        for n, intento in enumerate(reg["intentos"], 1):
            parche = extraer_diff(intento["texto"])
            try:
                if not parche:
                    raise PatchError("la respuesta no contiene un diff")
                canonico, modo = prepare_case(repo, c.base_commit, parche)
                if not read_diff(canonico, "x", "LLM", None, ".").archivos:
                    raise PatchError("el parche no cambia codigo Python de produccion")
            except (PatchError, ValueError, UnicodeError) as e:
                reg["estado"] = f"no_aplica: {str(e)[:300]}"
                continue
            (RAIZ / "casos" / f"{c.instance_id}_llm.patch").write_text(canonico, encoding="utf-8", newline="\n")
            reg.update(estado="ok", intento_ok=n, modo_aplicacion=modo)
            break
        ruta.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
        elegido = reg["estado"] == "ok" and sum(por_repo.values()) < 30 and por_repo[c.repo] < 4
        if elegido:
            por_repo[c.repo] += 1
        filas.append({"instance_id": c.instance_id, "repo": c.repo, "rol": c.rol, "estado": reg["estado"][:120],
                      "intento_ok": reg.get("intento_ok"), "modo": reg.get("modo_aplicacion"),
                      "n_intentos": len(reg["intentos"]), "elegido": elegido,
                      "tokens_entrada": sum(i["uso"]["prompt_tokens"] for i in reg["intentos"]),
                      "tokens_salida": sum(i["uso"]["completion_tokens"] for i in reg["intentos"])})
    df = pd.DataFrame(filas)
    df.to_csv(RAIZ / "data" / "generacion_llm.csv", index=False)
    df[df.elegido][["instance_id"]].to_csv(RAIZ / "data" / "seleccion.csv", index=False)
    print(df.groupby(["rol", "elegido"]).size().to_string())
    print(df.modo.value_counts(dropna=False).to_string(), df.intento_ok.value_counts(dropna=False).to_string())
    print(df[df.estado != "ok"][["instance_id", "estado"]].to_string())
    print("por repo", dict(por_repo), "| tokens", df.tokens_entrada.sum(), df.tokens_salida.sum())


if __name__ == "__main__":
    main()
