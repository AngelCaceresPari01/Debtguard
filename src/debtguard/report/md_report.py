from pathlib import Path


def render(a) -> str:
    filas = "\n".join(f"| {f.archivo}:{f.linea} | {f.familia} | {f.regla} | {f.severidad} | {f.costo_min:g} |"
                      for f in sorted(a.hallazgos, key=lambda x: -x.costo_min))
    return (f"# {a.caso_id}\n\n**Veredicto:** {a.veredicto} | **Deuda:** {a.deuda_horas:.2f} h "
            f"({a.horas_kloc:.1f} h/KLOC) | **Nota SQALE:** {a.nota_sqale} | **IRD:** {a.ird}\n\n"
            f"| Ubicacion | Familia | Regla | Severidad | Minutos |\n|---|---|---|---|---|\n{filas}\n")


def write(a, destino) -> None:
    Path(destino).write_text(render(a), encoding="utf-8")
