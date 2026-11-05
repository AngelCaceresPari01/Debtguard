"""CLI: python -m debtguard analyze --diff X.patch --repo ruta --case-id X --origin LLM"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from debtguard import pipeline
from debtguard.report import json_report, md_report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="debtguard")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="mide la deuda que introduce un diff ya aplicado en --repo")
    a.add_argument("--diff", required=True)
    a.add_argument("--repo", required=True)
    a.add_argument("--case-id", required=True)
    a.add_argument("--origin", default="desconocido")
    a.add_argument("--model")
    a.add_argument("--base-rev", default="HEAD", help="revision previa al cambio")
    a.add_argument("--json")
    a.add_argument("--md")
    args = ap.parse_args(argv)
    r = pipeline.analyze(Path(args.diff).read_text(encoding="utf-8", errors="replace"), args.repo, args.case_id,
                         args.origin, args.model, args.base_rev)
    if args.json:
        json_report.write(r, args.json)
    if args.md:
        md_report.write(r, args.md)
    print(f"{r.caso_id}: {r.veredicto} | {r.deuda_horas:.2f} h ({r.horas_kloc:.1f} h/KLOC) | "
          f"SQALE {r.nota_sqale} | IRD {r.ird} | {len(r.hallazgos)} hallazgos")
    for e in r.errores:
        print(f"  aviso: {e}", file=sys.stderr)
    return 1 if r.veredicto == "BLOQUEAR" else 0


if __name__ == "__main__":
    sys.exit(main())
