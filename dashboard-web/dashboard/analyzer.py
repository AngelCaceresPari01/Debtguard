"""Aplica debtguard a una carpeta: codigo actual, commits y cambios sin confirmar.

Los commits usan pipeline.analyze sin cambios, igual que el experimento. El codigo actual reutiliza los
mismos detectores y costos, tratando cada linea como nueva, porque ahi no hay un cambio con el que comparar.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from debtguard import pipeline
from debtguard.estimator import costs
from debtguard.ingest.diff_reader import es_excluido
from debtguard.metrics import clones, complexity, satd, static
from debtguard.models import ChangeSet

from . import gitrepo

CACHE = Path(__file__).resolve().parents[1] / "cache"
MAX_ARCHIVOS, MAX_BYTES, LOTE_RUFF, MAX_OBJETIVOS_CICLOS = 5000, 1_000_000, 200, 12


class Cancelado(Exception):
    pass


def _firma_config() -> str:
    cfg, th = pipeline.load_config()
    return hashlib.sha256(json.dumps([cfg, th], sort_keys=True).encode()).hexdigest()[:12]


def _a_dict(a) -> dict:
    d = a.to_dict()
    d["hallazgos"] = [dict(h) for h in d["hallazgos"]]
    return d


def inspeccionar(carpeta: Path) -> dict:
    raiz = gitrepo.raiz_git(carpeta)
    info = {"carpeta": str(carpeta), "es_git": raiz is not None, "raiz": str(raiz) if raiz else None, "rama": None,
            "commits": 0, "repos_internos": []}
    if raiz:
        info["rama"] = gitrepo.git(raiz, "branch", "--show-current", check=False).strip() or "(sin rama)"
        n = gitrepo.git(raiz, "rev-list", "--count", "--no-merges", "HEAD", check=False).strip()
        info["commits"] = int(n) if n.isdigit() else 0
        info["sin_confirmar"] = bool(gitrepo.git(raiz, "status", "--porcelain", "--", "*.py", check=False).strip())
    else:
        info["repos_internos"] = gitrepo.buscar_repos(carpeta)
    base = raiz or carpeta
    rutas = gitrepo.archivos_de_carpeta(base, raiz)
    ext = Counter(Path(r).suffix.lower() or "(sin extensión)" for r in rutas)
    python = [r for r in rutas if r.endswith(".py")]
    info.update(archivos=len(rutas), python=len(python), python_produccion=sum(not es_excluido(r) for r in python),
                extensiones=ext.most_common(6))
    return info


def analizar_codigo(carpeta: Path, raiz_repo: Path | None, avance, cancelado) -> dict:
    """Estado actual de la carpeta. Copia solo los .py a un directorio temporal y lo analiza alli."""
    base = raiz_repo or carpeta
    cfg = {**pipeline.load_config()[0], "pylint_timeout_s": 120}
    rutas = [r for r in gitrepo.archivos_de_carpeta(base, raiz_repo) if r.endswith(".py")]
    excluidos = [r for r in rutas if es_excluido(r)]
    rutas = [r for r in rutas if not es_excluido(r)]
    avisos = []
    if len(rutas) > MAX_ARCHIVOS:
        avisos.append(f"Se analizaron {MAX_ARCHIVOS} de {len(rutas)} archivos Python.")
        rutas = rutas[:MAX_ARCHIVOS]
    temporal = Path(tempfile.mkdtemp(prefix="debtguard-codigo-"))
    try:
        cs = ChangeSet("codigo", "desconocido", None, str(temporal), "HEAD")
        fuentes, hallazgos, por_archivo, funciones, errores = {}, [], {}, [], []
        for i, ruta in enumerate(rutas, 1):
            if cancelado():
                raise Cancelado
            avance(f"Midiendo {ruta}", i, len(rutas))
            origen = base / ruta
            if origen.stat().st_size > MAX_BYTES:
                avisos.append(f"Omitido por tamaño: {ruta}")
                continue
            texto = origen.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
            destino = temporal / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8", newline="\n")
            lineas_txt = texto.splitlines()
            todas = set(range(1, len(lineas_txt) + 1))
            if not todas:
                continue
            fuentes[ruta] = texto
            cs.archivos[ruta] = sorted(todas)
            loc = sum(bool(l.strip()) for l in lineas_txt)
            cs.lineas_anadidas += loc
            hallazgos += satd.analyze(ruta, texto, todas)
            fila = {"archivo": ruta, "loc": loc, "funciones": 0, "cognitiva_max": 0, "ciclomatica_max": 0, "mi": None}
            try:
                hs, m = complexity.analyze(ruta, texto, None, todas, cfg)
                hallazgos += hs
                fila.update(funciones=m["funciones_tocadas"], cognitiva_max=m["cognitiva_max"],
                            ciclomatica_max=m["ciclomatica_max"], mi=round(m["mi"], 2))
                funciones += [{"archivo": ruta, "funcion": f.nombre, "linea": f.inicio, "cognitiva": f.cognitiva,
                               "ciclomatica": f.ciclomatica, "loc": f.loc} for f in complexity.functions(texto).values()]
            except (SyntaxError, ValueError) as e:
                errores.append(f"{ruta}: no se pudo medir la complejidad ({e.__class__.__name__})")
            por_archivo[ruta] = fila

        avance("Revisando reglas con Ruff", 0, 0)
        claves = list(cs.archivos)
        for i in range(0, len(claves), LOTE_RUFF):
            if cancelado():
                raise Cancelado
            parte = ChangeSet("codigo", "desconocido", None, str(temporal), "HEAD",
                              archivos={k: cs.archivos[k] for k in claves[i:i + LOTE_RUFF]})
            try:
                hallazgos += static.run_ruff(parte, cfg)
            except (RuntimeError, OSError) as e:
                errores.append(f"ruff: {str(e)[:200]}")
        avance("Buscando código duplicado con jscpd", 0, 0)
        try:
            hallazgos += clones.analyze(cs, cfg)
        except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as e:
            errores.append(f"jscpd: {str(e)[:200]}")
        if cancelado():
            raise Cancelado
        avance("Buscando importaciones cíclicas con Pylint", 0, 0)
        hallazgos += _ciclos_acotados(cs, fuentes, cfg, avisos, errores)

        deuda_min = costs.assign(hallazgos, cfg)
        for h in hallazgos:
            f = por_archivo.get(h.archivo)
            if f is not None:
                f["hallazgos"] = f.get("hallazgos", 0) + 1
                f["minutos"] = f.get("minutos", 0) + h.costo_min
        filas = list(por_archivo.values())
        for f in filas:
            f.setdefault("hallazgos", 0)
            f["horas"] = round(f.pop("minutos", 0) / 60, 2)
        return {"tipo": "codigo", **_resumen(cs, hallazgos, deuda_min, filas), "errores": errores, "avisos": avisos,
                "excluidos": len(excluidos), "archivos": sorted(filas, key=lambda f: -f["horas"]),
                "funciones": sorted(funciones, key=lambda f: (-f["cognitiva"], -f["ciclomatica"]))[:15]}
    finally:
        shutil.rmtree(temporal, ignore_errors=True)


def _ciclos_acotados(cs, fuentes, cfg, avisos, errores) -> list:
    # Pylint revisa cada elemento de primer nivel; en carpetas con muchos scripts sueltos se acota el tiempo.
    tops = Counter(a.split("/")[0] for a in cs.archivos)
    elegidos = {t for t, _ in tops.most_common(MAX_OBJETIVOS_CICLOS)}
    if len(tops) > MAX_OBJETIVOS_CICLOS:
        avisos.append(f"Importaciones cíclicas: se revisaron {MAX_OBJETIVOS_CICLOS} de {len(tops)} elementos de primer nivel.")
    parte = ChangeSet(cs.caso_id, cs.origen, None, cs.ruta_repo, cs.base_rev,
                      archivos={a: l for a, l in cs.archivos.items() if a.split("/")[0] in elegidos})
    try:
        return static.run_cycles(parte, fuentes, cfg)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
        errores.append(f"pylint: {str(e)[:200]}")
        return []


def _resumen(cs: ChangeSet, hallazgos, deuda_min: float, filas: list[dict]) -> dict:
    kloc = cs.lineas_anadidas / 1000
    por_kloc = (lambda x: x / kloc) if kloc else (lambda x: 0.0)
    reglas = [h for h in hallazgos if h.familia == "regla"]
    mis = [f["mi"] for f in filas if f.get("mi") is not None]
    n_satd = sum(h.familia == "satd" for h in hallazgos)
    horas = deuda_min / 60
    ratio = deuda_min / (cs.lineas_anadidas * 30) if cs.lineas_anadidas else 0.0
    return {
        "kloc": kloc, "deuda_min": deuda_min, "deuda_horas": horas, "horas_kloc": por_kloc(horas), "debt_ratio": ratio,
        "nota_sqale": costs.sqale_rating(ratio),
        "metricas": {"cognitiva_max": max((f["cognitiva_max"] for f in filas), default=0),
                     "ciclomatica_max": max((f["ciclomatica_max"] for f in filas), default=0),
                     "mi_min": min(mis) if mis else None, "clones": sum(h.familia == "clon" for h in hallazgos),
                     "advertencias": len(reglas), "advertencias_kloc": por_kloc(len(reglas)), "satd": n_satd,
                     "satd_kloc": por_kloc(n_satd), "lineas": cs.lineas_anadidas, "archivos": len(cs.archivos),
                     "funciones": sum(f["funciones"] for f in filas)},
        "hallazgos": [asdict(h) for h in sorted(hallazgos, key=lambda h: -h.costo_min)],
        "minutos_familia": {f: sum(h.costo_min for h in hallazgos if h.familia == f) for f in ("complejidad", "regla", "clon", "satd")},
    }


def _desde_cache(clave: str) -> dict | None:
    ruta = CACHE / f"{clave}.json"
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None


def _a_cache(clave: str, datos: dict) -> None:
    CACHE.mkdir(exist_ok=True)
    (CACHE / f"{clave}.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def analizar_commits(raiz: Path, limite: int, avance, cancelado) -> dict:
    commits = gitrepo.listar_commits(raiz, limite)
    firma = _firma_config()
    filas, errores, sin_python = [], [], 0
    instantanea = None
    try:
        for i, c in enumerate(commits, 1):
            if cancelado():
                raise Cancelado
            avance(f"Commit {c['corto']}: {c['asunto'][:60]}", i, len(commits))
            clave = f"{c['sha']}-{firma}"
            datos = _desde_cache(clave)
            if datos is None:
                if instantanea is None:
                    instantanea = gitrepo.Instantanea(raiz)
                try:
                    datos = _medir_commit(instantanea, c)
                except (gitrepo.GitError, ValueError, UnicodeError, subprocess.TimeoutExpired) as e:
                    errores.append(f"{c['corto']}: {str(e)[:200]}")
                    continue
                _a_cache(clave, datos)
            if not datos["metricas"]["archivos"]:
                sin_python += 1
                continue
            filas.append({**datos, **c})  # el origen declarado del commit manda sobre el del reporte
    finally:
        if instantanea is not None:
            instantanea.cerrar()
    return {"tipo": "commits", "commits": filas, "revisados": len(commits), "sin_python": sin_python, "errores": errores}


def _medir_commit(inst: gitrepo.Instantanea, c: dict) -> dict:
    inst.ir_a(c["sha"])
    diff = inst.diff(c["padre"], c["sha"])
    a = pipeline.analyze(diff, inst.ruta, c["corto"], "desconocido", None, base_rev=c["padre"])
    return _a_dict(a)


def analizar_sin_confirmar(raiz: Path, avance) -> dict:
    avance("Midiendo los cambios sin confirmar", 0, 0)
    with gitrepo.Instantanea(raiz) as inst:
        diff = gitrepo.aplicar_sin_confirmar(raiz, inst)
        a = pipeline.analyze(diff, inst.ruta, "sin_confirmar", "desconocido", None, base_rev="HEAD")
    return {"tipo": "sin_confirmar", **_a_dict(a)}


def analizar(carpeta: Path, codigo: bool, commits: int, sin_confirmar: bool, avance, cancelado) -> dict:
    raiz = gitrepo.raiz_git(carpeta)
    salida = {"carpeta": str(carpeta), "raiz": str(raiz) if raiz else None, "info": inspeccionar(carpeta)}
    if commits and raiz:
        salida["historial"] = analizar_commits(raiz, commits, avance, cancelado)
    if sin_confirmar and raiz:
        salida["sin_confirmar"] = analizar_sin_confirmar(raiz, avance)
    if codigo:
        salida["codigo"] = analizar_codigo(carpeta, raiz, avance, cancelado)
    return salida
