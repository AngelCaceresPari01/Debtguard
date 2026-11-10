"""Estudio de caso: analiza un repositorio real con el dashboard, guarda los datos y toma capturas.

Uso (con el dashboard ya iniciado en http://127.0.0.1:8765):
    dashboard-web\\.venv\\Scripts\\python.exe estudio_caso\\capturar.py estudio_caso\\repo --commits 100

Las capturas usan Chrome sin ventana mediante el protocolo DevTools; requiere `pip install websocket-client`.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

BASE = "http://127.0.0.1:8765"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
AQUI = Path(__file__).resolve().parent


def api(ruta: str, cuerpo: dict | None = None) -> dict:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    req = urllib.request.Request(BASE + ruta, data=datos, headers={"Content-Type": "application/json"} if datos else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def analizar(ruta: Path, commits: int) -> tuple[str, dict]:
    jid = api("/api/analizar", {"ruta": str(ruta), "codigo": True, "commits": commits, "sin_confirmar": False})["id"]
    inicio = time.time()
    while True:
        t = api(f"/api/trabajos/{jid}")
        print(f"\r{int(time.time() - inicio)} s  {t['hecho']}/{t['total']}  {t['mensaje'][:70]:70s}", end="", flush=True)
        if t["estado"] != "en_curso":
            print()
            if t["estado"] != "listo":
                raise SystemExit(f"El análisis terminó en estado {t['estado']}: {t['mensaje']}")
            t["resultado"]["duracion_s"] = round(time.time() - inicio)
            return jid, t["resultado"]
        time.sleep(2)


def guardar_csv(ruta: Path, filas: list[dict], columnas: list[str]) -> None:
    with ruta.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def exportar(res: dict, comparacion: dict, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "resultado_completo.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (destino / "comparacion_ia.json").write_text(json.dumps(comparacion, ensure_ascii=False, indent=1), encoding="utf-8")
    commits = []
    for c in res.get("historial", {}).get("commits", []):
        commits.append({"commit": c["corto"], "fecha": c["fecha"][:10], "origen": c["origen"], "asunto": c["asunto"],
                        **{k: c["metricas"].get(k) for k in ("lineas_anadidas", "lineas_eliminadas", "cognitiva_max", "ciclomatica_max", "clones",
                                                             "clones_similares", "advertencias", "dependencias_nuevas", "acoplamiento_eferente_max",
                                                             "delta_mi", "satd")},
                        "horas": round(c["deuda_horas"], 3), "horas_kloc": round(c["horas_kloc"], 2), "ird": c["ird"], "veredicto": c["veredicto"],
                        "hallazgos": len(c["hallazgos"])})
    if commits:
        guardar_csv(destino / "commits.csv", commits, list(commits[0]))
    codigo = res.get("codigo")
    if codigo:
        guardar_csv(destino / "hallazgos_codigo.csv", codigo["hallazgos"],
                    ["archivo", "linea", "funcion", "familia", "regla", "severidad", "categoria", "valor", "costo_min", "detalle"])
        guardar_csv(destino / "archivos.csv", codigo["archivos"], ["archivo", "loc", "funciones", "cognitiva_max", "ciclomatica_max", "mi", "hallazgos", "horas"])
        guardar_csv(destino / "modulos.csv", codigo.get("modulos", []), ["modulo", "archivo", "eferente", "aferente", "inestabilidad"])
        guardar_csv(destino / "funciones.csv", codigo["funciones"], ["archivo", "funcion", "linea", "cognitiva", "ciclomatica", "loc"])


class Chrome:
    def __init__(self, ancho: int):
        self.perfil = tempfile.mkdtemp(prefix="debtguard-chrome-")
        self.proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333", f"--user-data-dir={self.perfil}",
                                      "--hide-scrollbars", "--force-color-profile=srgb", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                pestanas = json.loads(urllib.request.urlopen("http://127.0.0.1:9333/json", timeout=2).read())
                pagina = next(p for p in pestanas if p["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(0.3)
        self.ws = websocket.create_connection(pagina["webSocketDebuggerUrl"], timeout=120)
        self.n = 0
        self.cmd("Emulation.setDeviceMetricsOverride", width=ancho, height=900, deviceScaleFactor=1.5, mobile=False)
        self.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])

    def cmd(self, metodo: str, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": metodo, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    def js(self, codigo: str):
        r = self.cmd("Runtime.evaluate", expression=codigo, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"])
        return r.get("result", {}).get("value")

    def captura(self, archivo: Path, pagina_completa: bool = True) -> None:
        time.sleep(0.6)
        r = self.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=pagina_completa)
        archivo.write_bytes(base64.b64decode(r["data"]))
        print("captura", archivo.name)

    def cerrar(self) -> None:
        self.ws.close()
        self.proc.terminate()


def capturar(jid: str, carpeta: Path, destino: Path, n_commits: int) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    c = Chrome(1360)
    try:
        c.cmd("Page.navigate", url=BASE)
        time.sleep(2)
        ruta = json.dumps(str(carpeta))
        c.js(f"(async () => {{ await elegirCarpeta({ruta}); const t = await api('/api/trabajos/{jid}'); "
             f"document.getElementById('op-n').value = '{n_commits}'; document.getElementById('op-sucio').checked = false; "
             f"estado.trabajo = '{jid}'; estado.resultado = t.resultado; pintarTodo(); }})()")
        time.sleep(2)
        c.js("window.scrollTo(0, 0)")
        c.captura(destino / "01_resumen.png")
        for i, (pestana, nombre) in enumerate([("commits", "02_commits"), ("archivos", "03_archivos_y_modulos"), ("hallazgos", "04_hallazgos"),
                                                ("comparar", "05_ia_y_resto"), ("metodo", "06_como_se_mide")]):
            c.js(f"abrirPestana('{pestana}'); window.scrollTo(0, 0)")
            time.sleep(1.5 if pestana == "comparar" else 0.5)
            c.captura(destino / f"{nombre}.png", pagina_completa=pestana not in ("hallazgos", "commits"))
        c.js("abrirPestana('resumen'); window.scrollTo(0, 0)")
        for clave, nombre in [("advertencias", "07_modal_advertencias"), ("acoplamiento", "08_modal_acoplamiento"),
                              ("clones_similares", "09_modal_clones_parecidos")]:
            c.js(f"abrirExplicacion('{clave}', estado.resultado.codigo, 'codigo')")
            c.captura(destino / f"{nombre}.png", pagina_completa=False)
            c.js("document.getElementById('dlg-metrica').close()")
    finally:
        c.cerrar()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("--commits", type=int, default=100)
    args = ap.parse_args()
    carpeta = args.carpeta.resolve()
    jid, res = analizar(carpeta, args.commits)
    comparacion = api("/api/comparar", {"id": jid})
    exportar(res, comparacion, AQUI / "datos")
    capturar(jid, carpeta, AQUI / "capturas", args.commits)
    print(f"Listo en {res['duracion_s']} s")


if __name__ == "__main__":
    main()
