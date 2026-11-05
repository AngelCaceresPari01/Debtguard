import json
from pathlib import Path


def write(a, destino) -> None:
    p = Path(destino)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(a.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
