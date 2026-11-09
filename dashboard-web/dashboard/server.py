"""Servidor local: solo escucha en 127.0.0.1 y rechaza peticiones de otros sitios."""
from __future__ import annotations

import os
import string
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

from . import analyzer, gitrepo, stats

PUERTO = int(os.environ.get("DEBTGUARD_PUERTO", "8765"))
ESTATICOS = Path(__file__).parent / "static"
app = Flask(__name__, static_folder=None)
trabajos: dict[str, dict] = {}
_candado = threading.Lock()
_ELEGIR = ("import tkinter as t,tkinter.filedialog as f;r=t.Tk();r.withdraw();r.attributes('-topmost',True);"
           "print(f.askdirectory(title='Elige la carpeta que quieres analizar') or '')")


@app.before_request
def proteger():
    # Evita que una pagina web cualquiera use este servidor local para leer carpetas (DNS rebinding y CSRF).
    host = request.host.split(":")[0]
    if host not in ("127.0.0.1", "localhost"):
        abort(403)
    origen = request.headers.get("Origin")
    if origen and origen.split("//")[-1].split(":")[0] not in ("127.0.0.1", "localhost"):
        abort(403)
    if request.method == "POST" and not request.is_json:
        abort(415)


@app.after_request
def cabeceras(resp):
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _carpeta(valor: str | None) -> Path:
    if not valor:
        abort(400, "Falta la carpeta.")
    ruta = Path(valor).expanduser()
    if not ruta.is_absolute() or not ruta.is_dir():
        abort(400, "La carpeta no existe.")
    return ruta.resolve()


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(415)
def error_http(e):
    return jsonify(error=e.description), e.code


@app.get("/")
def inicio():
    return send_from_directory(ESTATICOS, "index.html")


@app.get("/static/<path:nombre>")
def estatico(nombre):
    return send_from_directory(ESTATICOS, nombre)


@app.get("/api/raices")
def raices():
    unidades = [f"{l}:\\" for l in string.ascii_uppercase if os.path.exists(f"{l}:\\")] if os.name == "nt" else ["/"]
    casa = Path.home()
    accesos = [{"nombre": n, "ruta": str(p)} for n, p in (("Inicio", casa), ("Descargas", casa / "Downloads"), ("Documentos", casa / "Documents"),
                                                          ("Escritorio", casa / "Desktop")) if p.is_dir()]
    return jsonify(unidades=unidades, accesos=accesos)


@app.get("/api/explorar")
def explorar():
    carpeta = _carpeta(request.args.get("ruta"))
    dirs = []
    try:
        for e in sorted(os.scandir(carpeta), key=lambda x: x.name.lower()):
            if e.is_dir(follow_symlinks=False) and not e.name.startswith(("$", ".")) and e.name not in gitrepo.OMITIR:
                try:
                    es_git = os.path.isdir(os.path.join(e.path, ".git"))
                except OSError:
                    es_git = False
                dirs.append({"nombre": e.name, "ruta": e.path, "git": es_git})
    except PermissionError:
        abort(400, "No hay permiso para abrir esta carpeta.")
    padre = str(carpeta.parent) if carpeta.parent != carpeta else None
    return jsonify(ruta=str(carpeta), padre=padre, carpetas=dirs, git=(carpeta / ".git").exists())


@app.post("/api/elegir")
def elegir():
    try:
        r = subprocess.run([sys.executable, "-c", _ELEGIR], capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return jsonify(ruta=None)
    if r.returncode:
        return jsonify(ruta=None, error="No se pudo abrir el selector de Windows. Usa Examinar.")
    return jsonify(ruta=r.stdout.strip() or None)


@app.get("/api/inspeccionar")
def inspeccionar():
    return jsonify(analyzer.inspeccionar(_carpeta(request.args.get("ruta"))))


@app.post("/api/analizar")
def analizar():
    d = request.get_json()
    carpeta = _carpeta(d.get("ruta"))
    commits = max(0, min(int(d.get("commits", 0) or 0), 500))
    codigo, sin_confirmar = bool(d.get("codigo")), bool(d.get("sin_confirmar"))
    if not (codigo or commits or sin_confirmar):
        abort(400, "Elige al menos un tipo de análisis.")
    with _candado:
        if any(t["estado"] == "en_curso" for t in trabajos.values()):
            abort(400, "Ya hay un análisis en curso.")
        jid = uuid.uuid4().hex
        trabajos[jid] = t = {"id": jid, "estado": "en_curso", "mensaje": "Preparando", "hecho": 0, "total": 0, "cancelar": False, "resultado": None}

    def avance(mensaje, hecho, total):
        t.update(mensaje=mensaje, hecho=hecho, total=total)

    def correr():
        try:
            t["resultado"] = analyzer.analizar(carpeta, codigo, commits, sin_confirmar, avance, lambda: t["cancelar"])
            t["estado"] = "listo"
        except analyzer.Cancelado:
            t["estado"] = "cancelado"
        except Exception as e:  # noqa: BLE001 - se muestra al usuario en lugar de dejar el trabajo colgado
            t.update(estado="error", mensaje=f"{e.__class__.__name__}: {str(e)[:400]}")

    threading.Thread(target=correr, daemon=True).start()
    return jsonify(id=jid)


@app.get("/api/trabajos/<jid>")
def trabajo(jid):
    t = trabajos.get(jid) or abort(404, "Trabajo no encontrado.")
    return jsonify({k: v for k, v in t.items() if k != "cancelar"})


@app.post("/api/trabajos/<jid>/cancelar")
def cancelar(jid):
    t = trabajos.get(jid) or abort(404, "Trabajo no encontrado.")
    t["cancelar"] = True
    return jsonify(ok=True)


@app.post("/api/comparar")
def comparar():
    d = request.get_json()
    t = trabajos.get(d.get("id")) or abort(404, "Trabajo no encontrado.")
    filas = ((t.get("resultado") or {}).get("historial") or {}).get("commits", [])
    return jsonify(stats.comparar(filas, d.get("etiquetas") or {}))


def main():
    print(f"debtguard dashboard en http://127.0.0.1:{PUERTO}")
    app.run(host="127.0.0.1", port=PUERTO, threaded=True, debug=False)


if __name__ == "__main__":
    main()
