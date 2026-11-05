"""Orquesta el analisis de un diff sobre un repositorio con el parche ya aplicado."""
from __future__ import annotations

import importlib.metadata as im
import subprocess
from pathlib import Path

import yaml

from debtguard.estimator import costs, ird as ird_mod, verdict
from debtguard.ingest.diff_reader import read_diff
from debtguard.ingest.repo import file_at
from debtguard.metrics import clones, complexity, satd, static
from debtguard.models import Assessment

CONFIG = Path(__file__).resolve().parents[2] / "config"
ALTAS = {"alta", "critica"}


def load_config(config_dir: Path = CONFIG) -> tuple[dict, dict]:
    cost = yaml.safe_load((config_dir / "remediation_costs.yaml").read_text(encoding="utf-8"))
    th = yaml.safe_load((config_dir / "thresholds.yaml").read_text(encoding="utf-8"))
    return cost, th


def _versiones() -> dict:
    v = {p: im.version(p) for p in ("radon", "complexipy", "ruff", "pylint", "unidiff")}
    try:
        v["jscpd"] = subprocess.run(["node", str(clones.JSCPD), "--version"], capture_output=True,
                                    text=True).stdout.strip()
    except OSError:
        v["jscpd"] = "no disponible"
    return v


def analyze(diff_text: str, repo: str | Path, caso_id: str, origen: str, modelo: str | None = None,
            base_rev: str = "HEAD", config_dir: Path = CONFIG) -> Assessment:
    cfg, th = load_config(config_dir)
    repo = Path(repo).resolve()
    cs = read_diff(diff_text, caso_id, origen, modelo, str(repo), base_rev)
    hallazgos, errores, por_archivo, fuentes = [], [], [], {}
    for ruta, lineas in cs.archivos.items():
        ruta_abs = repo / ruta
        if not ruta_abs.exists():
            errores.append(f"{ruta}: no existe en el repositorio")
            continue
        fuente = ruta_abs.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        fuentes[ruta] = fuente
        anadidas = set(lineas)
        hallazgos += satd.analyze(ruta, fuente, anadidas)
        previa = file_at(repo, base_rev, ruta) if (repo / ".git").exists() else None
        try:
            hs, m = complexity.analyze(ruta, fuente, previa, anadidas, cfg)
            hallazgos += hs
            por_archivo.append(m)
        except (SyntaxError, ValueError) as e:
            errores.append(f"{ruta}: complejidad no medible ({e.__class__.__name__})")
    for nombre, paso in (("ruff", lambda: static.run_ruff(cs, cfg)),
                         ("pylint", lambda: static.run_cycles(cs, fuentes, cfg)),
                         ("jscpd", lambda: clones.analyze(cs, cfg))):
        try:
            hallazgos += paso()
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
            errores.append(f"{nombre}: {str(e)[:200]}")

    deuda_min = costs.assign(hallazgos, cfg)
    kloc = cs.kloc_cambiadas
    por_kloc = (lambda n: n / kloc) if kloc else (lambda n: 0.0)
    reglas = [f for f in hallazgos if f.familia == "regla"]
    n_satd = sum(f.familia == "satd" for f in hallazgos)
    n_altas = sum(f.severidad in ALTAS for f in reglas)
    mis = [m["mi"] for m in por_archivo]
    deltas_mi = [m["delta_mi"] for m in por_archivo if "delta_mi" in m]
    metricas = {
        "cognitiva_max": max((m["cognitiva_max"] for m in por_archivo), default=0),
        "ciclomatica_max": max((m["ciclomatica_max"] for m in por_archivo), default=0),
        "delta_cognitiva": sum(m["delta_cognitiva"] for m in por_archivo),
        "delta_ciclomatica": sum(m["delta_ciclomatica"] for m in por_archivo),
        "funciones_tocadas": sum(m["funciones_tocadas"] for m in por_archivo),
        "mi_min": min(mis) if mis else None,
        "delta_mi": min(deltas_mi) if deltas_mi else None,
        "advertencias": len(reglas),
        "advertencias_kloc": por_kloc(len(reglas)),
        "adv_altas_kloc": por_kloc(n_altas),
        "clones": sum(f.familia == "clon" for f in hallazgos),
        "satd": n_satd,
        "satd_kloc": por_kloc(n_satd),
        "lineas_anadidas": cs.lineas_anadidas,
        "lineas_eliminadas": cs.lineas_eliminadas,
        "archivos": len(cs.archivos),
    }
    horas = deuda_min / 60
    horas_kloc = por_kloc(horas)
    ratio = deuda_min / (cs.lineas_anadidas * 30) if cs.lineas_anadidas else 0.0
    valores = {"horas_kloc": horas_kloc, **metricas}
    indice = ird_mod.compute(valores, th.get("p95") or {})
    return Assessment(caso_id, origen, modelo, kloc, metricas, hallazgos, deuda_min, horas, horas_kloc, ratio,
                      costs.sqale_rating(ratio), indice, verdict.decide(indice, hallazgos, th), _versiones(),
                      errores, cs.excluidos)
