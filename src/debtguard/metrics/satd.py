"""Deuda autoadmitida: comentarios TODO/FIXME/HACK/XXX en lineas anadidas."""
from __future__ import annotations

import io
import re
import tokenize

from debtguard.models import Finding

PATRON = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


def _comentarios(fuente: str) -> list[tuple[int, str]]:
    try:
        return [(t.start[0], t.string) for t in tokenize.generate_tokens(io.StringIO(fuente).readline)
                if t.type == tokenize.COMMENT]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Archivo no tokenizable: se busca el comentario de forma aproximada.
        return [(i, l[l.index("#"):]) for i, l in enumerate(fuente.splitlines(), 1) if "#" in l]


def analyze(archivo: str, fuente: str, anadidas: set[int]) -> list[Finding]:
    hallazgos = []
    for linea, texto in _comentarios(fuente):
        m = PATRON.search(texto)
        if linea in anadidas and m:
            hallazgos.append(Finding(archivo, linea, None, "satd", m.group(1).upper(), "baja", 1,
                                     detalle=texto.strip()[:160]))
    return hallazgos
