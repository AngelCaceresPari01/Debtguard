"""Complejidad de las funciones tocadas: solo se cobra el aumento que introduce el cambio."""
from __future__ import annotations

from dataclasses import dataclass

from complexipy import code_complexity
from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.visitors import Function

from debtguard.models import Finding


@dataclass
class Fn:
    nombre: str
    inicio: int
    fin: int
    ciclomatica: int
    cognitiva: int = 0

    @property
    def loc(self) -> int:
        return self.fin - self.inicio + 1


def _aplanar(bloque: Function, prefijo: str = ""):
    nombre = f"{prefijo}{bloque.fullname}"
    yield Fn(nombre, bloque.lineno, bloque.endline, bloque.complexity)
    for c in bloque.closures:
        yield from _aplanar(c, f"{nombre}.")


def functions(fuente: str) -> dict[str, Fn]:
    """Une Radon y complexipy por nombre. Lanza SyntaxError si Radon no puede leer el archivo."""
    fns: dict[str, Fn] = {}
    for b in cc_visit(fuente):
        if isinstance(b, Function):
            for fn in _aplanar(b):
                fns[fn.nombre] = fn
    try:
        for f in code_complexity(fuente).functions:
            nombre = f.name.replace("::", ".")
            if nombre in fns:
                fns[nombre].cognitiva = f.complexity
            else:
                for fn in fns.values():
                    if fn.inicio == f.line_start:
                        fn.cognitiva = f.complexity
    except Exception:  # noqa: BLE001 - complexipy no reconoce parte del codigo antiguo
        pass
    return fns


def mi(fuente: str) -> float:
    return float(mi_visit(fuente, multi=True))


def _severidad(valor: float, umbral: float) -> str:
    return "alta" if valor > 2 * umbral else "media"


def analyze(archivo: str, fuente: str, previa: str | None, anadidas: set[int], cfg: dict):
    """Devuelve (hallazgos, metricas de archivo)."""
    actuales = functions(fuente)
    try:
        anteriores = functions(previa) if previa else {}
    except (SyntaxError, ValueError):
        anteriores = {}
    c = cfg["complejidad"]
    hallazgos: list[Finding] = []
    tocadas = [f for f in actuales.values() if anadidas & set(range(f.inicio, f.fin + 1))]
    for f in tocadas:
        prev = anteriores.get(f.nombre)
        for regla, valor, ant, umbral in (
            ("cognitive>15", f.cognitiva, prev.cognitiva if prev else 0, c["cognitiva"]["umbral"]),
            ("cyclomatic>10", f.ciclomatica, prev.ciclomatica if prev else 0, c["ciclomatica"]["umbral"]),
        ):
            if valor > umbral and valor > ant:
                hallazgos.append(Finding(archivo, f.inicio, f.nombre, "complejidad", regla,
                                         _severidad(valor, umbral), valor, umbral, valor_previo=ant))
        lim = c["funcion_larga"]["umbral_loc"]
        if f.loc > lim and (prev is None or prev.loc <= lim):
            hallazgos.append(Finding(archivo, f.inicio, f.nombre, "complejidad", "long_function>70",
                                     "baja", f.loc, lim, valor_previo=prev.loc if prev else 0))
    metricas = {
        "cognitiva_max": max((f.cognitiva for f in tocadas), default=0),
        "ciclomatica_max": max((f.ciclomatica for f in tocadas), default=0),
        "delta_cognitiva": sum(f.cognitiva - (anteriores[f.nombre].cognitiva if f.nombre in anteriores else 0)
                               for f in tocadas),
        "delta_ciclomatica": sum(f.ciclomatica - (anteriores[f.nombre].ciclomatica if f.nombre in anteriores else 0)
                                 for f in tocadas),
        "funciones_tocadas": len(tocadas),
        "mi": mi(fuente),
    }
    if previa:
        try:
            metricas["delta_mi"] = metricas["mi"] - mi(previa)
        except (SyntaxError, ValueError):
            pass
    return hallazgos, metricas
