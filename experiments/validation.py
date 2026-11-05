"""Paso 7: validacion manual. No etiqueta nada: prepara las plantillas y calcula al recibirlas.

  python experiments/validation.py muestra    crea las plantillas ciegas para P2 y P3
  python experiments/validation.py calcular   lee etiquetas (VP/FP) y calcula Kappa y precision
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

RAIZ = Path(__file__).resolve().parents[1]
VAL = RAIZ / "data" / "validacion"
SEMILLA, TOTAL = 42, 60
FAMILIAS = ("complejidad", "regla", "clon", "satd")


def muestra() -> None:
    rng = random.Random(SEMILLA)
    por_familia = {f: [] for f in FAMILIAS}
    for p in sorted((RAIZ / "reports").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for h in d["hallazgos"]:
            por_familia[h["familia"]].append({"caso": d["caso_id"], **h})
    cupo = TOTAL // len(FAMILIAS)
    elegidas = []
    for f in FAMILIAS:
        rng.shuffle(por_familia[f])
        elegidas += por_familia[f][:cupo]
    sobrantes = [h for f in FAMILIAS for h in por_familia[f][cupo:]]
    rng.shuffle(sobrantes)
    elegidas += sobrantes[:TOTAL - len(elegidas)]
    rng.shuffle(elegidas)
    VAL.mkdir(parents=True, exist_ok=True)
    clave, ciega = [], []
    for i, h in enumerate(elegidas, 1):
        # El origen (humano o LLM) va solo en la clave: los revisores etiquetan a ciegas.
        repo_caso = h["caso"].rsplit("_", 1)
        clave.append({"id": i, "caso": h["caso"], "origen": "LLM" if repo_caso[1] == "llm" else "humano",
                      "familia": h["familia"], "regla": h["regla"], "costo_min": h["costo_min"]})
        ciega.append({"id": i, "issue": repo_caso[0], "archivo": h["archivo"], "linea": h["linea"],
                      "funcion": h["funcion"], "familia": h["familia"], "regla": h["regla"],
                      "severidad": h["severidad"], "valor": h["valor"], "detalle": h["detalle"],
                      "etiqueta_VP_FP": "", "comentario": ""})
    pd.DataFrame(clave).to_csv(VAL / "clave_no_abrir.csv", index=False)
    for persona in ("P2", "P3"):
        pd.DataFrame(ciega).to_csv(VAL / f"alertas_{persona}.csv", index=False, encoding="utf-8-sig")
    print(pd.DataFrame(clave).groupby(["familia", "origen"]).size().to_string())


def calcular() -> None:
    a = pd.read_csv(VAL / "alertas_P2.csv", encoding="utf-8-sig").set_index("id")["etiqueta_VP_FP"]
    b = pd.read_csv(VAL / "alertas_P3.csv", encoding="utf-8-sig").set_index("id")["etiqueta_VP_FP"]
    if a.isna().any() or b.isna().any():
        sys.exit("Faltan etiquetas: P2 y P3 deben completar todas las filas con VP o FP.")
    a, b = a.str.upper().str.strip(), b.str.upper().str.strip()
    print(f"Kappa de Cohen: {cohen_kappa_score(a, b):.3f} | acuerdo simple: {(a == b).mean():.3f}")
    desacuerdos = a.index[a != b].tolist()
    ruta_final = VAL / "desacuerdos_resueltos.csv"
    if desacuerdos and not ruta_final.exists():
        print(f"Resolver {len(desacuerdos)} desacuerdos en {ruta_final.name} (columnas id, etiqueta_final): {desacuerdos}")
        return
    final = a.copy()
    if desacuerdos:
        r = pd.read_csv(ruta_final).set_index("id")["etiqueta_final"].str.upper().str.strip()
        final.loc[desacuerdos] = r.loc[desacuerdos]
    clave = pd.read_csv(VAL / "clave_no_abrir.csv").set_index("id")
    clave["final"] = final
    print(f"Precision global: {(final == 'VP').mean():.3f}")
    print(clave.groupby("familia")["final"].apply(lambda s: (s == "VP").mean()).round(3).to_string())


if __name__ == "__main__":
    {"muestra": muestra, "calcular": calcular}[sys.argv[1]]()
