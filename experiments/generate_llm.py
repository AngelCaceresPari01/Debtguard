"""Paso 2: genera los parches con DeepSeek y guarda prompt, respuesta cruda, modelo, fecha y tokens.

Procesa los casos de comparacion por rondas: los que no producen un parche aplicable se reemplazan
con la reserva, en orden y sin superar 4 issues por proyecto, hasta tener 30.
Se detiene si el saldo baja de --saldo-minimo. Es reanudable: no repite casos ya guardados.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from openai import OpenAI
from unidiff import PatchSet

from debtguard.ingest.diff_reader import read_diff
from debtguard.ingest.repo import PatchError, ensure_clone, file_at, prepare_case

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data" / "llm"
BASE_URL = "https://api.deepseek.com"
TOPE_CHARS = 600_000
PROMPT = """Eres un desarrollador. Repositorio: {repo}. Resuelve el siguiente issue.
Devuelve SOLO un parche en formato unified diff aplicable con `git apply`.

Issue:
{problem}

Archivos relevantes:
{archivos}"""
_parar = threading.Event()


def cargar_env() -> None:
    for linea in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in linea:
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def saldo() -> float:
    r = requests.get(f"{BASE_URL}/user/balance", timeout=30,
                     headers={"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"})
    return float(r.json()["balance_infos"][0]["total_balance"])


def extraer_diff(texto: str) -> str:
    bloques = re.findall(r"```(?:diff|patch)?\s*\n(.*?)```", texto, flags=re.S)
    candidato = next((b for b in bloques if "@@" in b), texto)
    m = re.search(r"^(diff --git |--- )", candidato, flags=re.M)
    return candidato[m.start():].rstrip() + "\n" if m else ""


def construir_prompt(caso, textos, repo: Path) -> str | None:
    rutas = [pf.path for pf in PatchSet(textos.loc[caso.instance_id, "patch"]) if not pf.is_added_file]
    partes = []
    for ruta in rutas:
        contenido = file_at(repo, caso.base_commit, ruta)
        if contenido is not None:
            partes.append(f"--- {ruta} ---\n{contenido}")
    p = PROMPT.format(repo=caso.repo, problem=textos.loc[caso.instance_id, "problem_statement"],
                      archivos="\n\n".join(partes))
    return p if len(p) <= TOPE_CHARS else None


def llamar(cliente, modelo, mensajes) -> dict:
    r = cliente.chat.completions.create(model=modelo, temperature=0, max_tokens=16000, messages=mensajes,
                                        extra_body={"thinking": {"type": "disabled"}})
    return {"texto": r.choices[0].message.content or "", "finish_reason": r.choices[0].finish_reason,
            "modelo": r.model, "fingerprint": r.system_fingerprint, "uso": r.usage.model_dump(),
            "fecha": dt.datetime.now(dt.timezone.utc).isoformat()}


def procesar(caso, textos, cliente, modelo, repo: Path) -> dict:
    destino = SALIDA / f"{caso.instance_id}.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    reg = {"instance_id": caso.instance_id, "repo": caso.repo, "estado": "", "intentos": []}
    prompt = construir_prompt(caso, textos, repo)
    if prompt is None:
        reg["estado"] = "prompt_excede_tope"
    else:
        reg["prompt"] = prompt
        mensajes = [{"role": "user", "content": prompt}]
        for intento in range(2):  # un solo reintento, como fija la guia
            resp = llamar(cliente, modelo, mensajes)
            reg["intentos"].append(resp)
            parche = extraer_diff(resp["texto"])
            try:
                if not parche:
                    raise PatchError("la respuesta no contiene un diff")
                canonico, modo = prepare_case(repo, caso.base_commit, parche)
                if not read_diff(canonico, "x", "LLM", None, ".").archivos:
                    raise PatchError("el parche no cambia codigo Python de produccion")
                (RAIZ / "casos" / f"{caso.instance_id}_llm.patch").write_text(canonico, encoding="utf-8", newline="\n")
                reg.update(estado="ok", intento_ok=intento + 1, modo_aplicacion=modo)
                break
            except (PatchError, ValueError, UnicodeError) as e:
                reg["estado"] = f"no_aplica: {str(e)[:300]}"
                mensajes = [{"role": "user", "content": prompt}, {"role": "assistant", "content": resp["texto"]},
                            {"role": "user", "content": f"El parche no se pudo aplicar: {str(e)[:500]}\n"
                                                        "Devuelve SOLO el parche corregido en unified diff."}]
    destino.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{caso.instance_id}: {reg['estado'][:70]}", flush=True)
    return reg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="deepseek-v4-pro")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--saldo-minimo", type=float, default=0.5)
    ap.add_argument("--max-casos", type=int, help="procesa solo N casos (prueba)")
    args = ap.parse_args()
    cargar_env()
    SALIDA.mkdir(parents=True, exist_ok=True)
    (RAIZ / "casos").mkdir(exist_ok=True)
    cliente = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=BASE_URL, timeout=900)
    casos = pd.read_csv(RAIZ / "data" / "casos.csv")
    textos = pd.read_parquet(RAIZ / "data" / "swebench_textos.parquet").set_index("instance_id")
    pendientes = list(casos[casos.rol == "comparacion"].itertuples())
    reserva = list(casos[casos.rol == "reserva"].itertuples())
    ok: dict[str, int] = {}
    procesados = 0

    def grupo(lista):
        repo = ensure_clone(lista[0].repo, RAIZ / "repos")
        res = []
        for c in lista:
            if _parar.is_set():
                break
            if saldo() < args.saldo_minimo:
                print("Saldo bajo el minimo: se detiene.", flush=True)
                _parar.set()
                break
            res.append((c, procesar(c, textos, cliente, args.modelo, repo)))
        return res

    while pendientes and not _parar.is_set():
        if args.max_casos:
            pendientes = pendientes[:args.max_casos - procesados]
        por_repo: dict[str, list] = {}
        for c in pendientes:
            por_repo.setdefault(c.repo, []).append(c)
        with ThreadPoolExecutor(max_workers=8) as ex:
            resultados = [r for rs in ex.map(grupo, por_repo.values()) for r in rs]
        procesados += len(resultados)
        for c, reg in resultados:
            if reg["estado"] == "ok":
                ok[c.repo] = ok.get(c.repo, 0) + 1
        faltan = args.n - sum(ok.values())
        if args.max_casos and procesados >= args.max_casos:
            break
        pendientes = []
        while faltan > len(pendientes) and reserva:
            c = reserva.pop(0)
            ya = ok.get(c.repo, 0) + sum(p.repo == c.repo for p in pendientes)
            if ya < 4:
                pendientes.append(c)
    print(f"Parches validos: {sum(ok.values())} | por repo: {ok} | saldo: {saldo():.2f} USD")


if __name__ == "__main__":
    main()
