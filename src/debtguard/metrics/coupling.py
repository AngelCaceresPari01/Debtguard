"""Grafo de imports con `ast`: acoplamiento por modulo y ciclos de importacion.

Sustituye a Pylint R0401 como motor de ciclos (mas rapido y sin ejecutar codigo). Solo cuenta los imports
que se ejecutan al importar el modulo: los de nivel de modulo, dentro de if/try y en cuerpos de clase.
Los imports dentro de funciones se ignoran, porque son la forma habitual de romper un ciclo.

Acoplamiento (Martin, 1994): eferente Ce = modulos internos de los que depende; aferente Ca = modulos
internos que dependen de el; inestabilidad I = Ce / (Ca + Ce).
"""
from __future__ import annotations

import ast
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from debtguard.ingest.diff_reader import es_excluido
from debtguard.models import ChangeSet, Finding

OMITIR = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", "build", "dist", ".tox", "site-packages"}


@dataclass
class Grafo:
    nombres: dict[str, str] = field(default_factory=dict)          # ruta -> modulo
    rutas: dict[str, str] = field(default_factory=dict)            # modulo -> ruta
    aristas: dict[str, dict[str, int]] = field(default_factory=dict)  # modulo -> {destino: linea}
    errores: list[str] = field(default_factory=list)

    def entrantes(self) -> dict[str, set[str]]:
        e = {m: set() for m in self.rutas}
        for a, destinos in self.aristas.items():
            for b in destinos:
                e.setdefault(b, set()).add(a)
        return e

    def componentes(self) -> dict[str, int]:
        """Componente fuertemente conexa de cada modulo (Tarjan iterativo). Ciclo = componente con 2 o mas."""
        indice, bajo, pila, en_pila, comp = {}, {}, [], set(), {}
        contador = [0, 0]
        for raiz in self.rutas:
            if raiz in indice:
                continue
            trabajo = [(raiz, iter(self.aristas.get(raiz, {})))]
            indice[raiz] = bajo[raiz] = contador[0]
            contador[0] += 1
            pila.append(raiz)
            en_pila.add(raiz)
            while trabajo:
                v, hijos = trabajo[-1]
                avanzo = False
                for w in hijos:
                    if w not in self.rutas:
                        continue
                    if w not in indice:
                        indice[w] = bajo[w] = contador[0]
                        contador[0] += 1
                        pila.append(w)
                        en_pila.add(w)
                        trabajo.append((w, iter(self.aristas.get(w, {}))))
                        avanzo = True
                        break
                    if w in en_pila:
                        bajo[v] = min(bajo[v], indice[w])
                if avanzo:
                    continue
                trabajo.pop()
                if trabajo:
                    bajo[trabajo[-1][0]] = min(bajo[trabajo[-1][0]], bajo[v])
                if bajo[v] == indice[v]:
                    while True:
                        w = pila.pop()
                        en_pila.discard(w)
                        comp[w] = contador[1]
                        if w == v:
                            break
                    contador[1] += 1
        return comp

    def ciclos(self) -> list[set[str]]:
        grupos: dict[int, set[str]] = {}
        for m, c in self.componentes().items():
            grupos.setdefault(c, set()).add(m)
        return [g for g in grupos.values() if len(g) > 1]


def nombre_modulo(ruta: str, existe_init) -> str:
    """Nombre importable: sube mientras haya __init__.py; lo que queda por encima es la raiz de busqueda."""
    p = PurePosixPath(ruta)
    partes = [p.stem] if p.stem != "__init__" else []
    carpeta = p.parent
    while str(carpeta) not in ("", ".") and existe_init(f"{carpeta.as_posix()}/__init__.py"):
        partes.insert(0, carpeta.name)
        carpeta = carpeta.parent
    return ".".join(partes) or p.parent.name


def _imports(arbol: ast.AST, modulo: str, es_paquete: bool):
    """(submodulos candidatos, modulo base, linea) de los imports que se ejecutan al importar el modulo.

    En `from x import y`, si y es un submodulo la dependencia es x.y; si es un nombre definido en x, es x.
    """
    pendientes = list(getattr(arbol, "body", []))
    while pendientes:
        n = pendientes.pop(0)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Import):
            for a in n.names:
                yield [], a.name, n.lineno
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:
                paquete = modulo.split(".") if es_paquete else modulo.split(".")[:-1]
                paquete = paquete[: len(paquete) - (n.level - 1)] if n.level > 1 else paquete
                base = ".".join([*paquete, base] if base else paquete)
            yield [f"{base}.{a.name}" for a in n.names if a.name != "*"], base, n.lineno
        else:
            for campo in ("body", "orelse", "finalbody", "handlers"):
                pendientes.extend(getattr(n, campo, []) or [])


def construir(fuentes: dict[str, str]) -> Grafo:
    g = Grafo()
    rutas = set(fuentes)
    for ruta in fuentes:
        nombre = nombre_modulo(ruta, rutas.__contains__)
        g.nombres[ruta] = nombre
        g.rutas.setdefault(nombre, ruta)
    for ruta, texto in fuentes.items():
        modulo = g.nombres[ruta]
        try:
            arbol = ast.parse(texto)
        except (SyntaxError, ValueError):
            g.errores.append(f"{ruta}: no se pudo leer para el grafo de imports")
            continue
        destinos = g.aristas.setdefault(modulo, {})

        def agregar(nombre, linea):
            if nombre and nombre != modulo:
                destinos.setdefault(nombre, linea)

        for submodulos, base, linea in _imports(arbol, modulo, ruta.endswith("__init__.py")):
            exactos = [s for s in submodulos if s in g.rutas]
            if exactos:
                for s in exactos:
                    agregar(s, linea)
                continue
            partes = base.split(".")
            for k in range(len(partes), 0, -1):  # el modulo interno mas especifico que exista
                nombre = ".".join(partes[:k])
                if nombre in g.rutas:
                    agregar(nombre, linea)
                    break
    return g


def fuentes_del_repo(repo: Path) -> dict[str, str]:
    """Codigo Python de produccion del arbol de trabajo (respeta .gitignore si hay git)."""
    if (repo / ".git").exists():
        r = subprocess.run(["git", "-C", str(repo), "ls-files", "-co", "--exclude-standard", "--", "*.py"],
                           capture_output=True, encoding="utf-8", errors="replace")
        rutas = r.stdout.splitlines()
    else:
        rutas = []
        for base, dirs, nombres in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in OMITIR]
            rutas += [(Path(base) / n).relative_to(repo).as_posix() for n in nombres if n.endswith(".py")]
    salida = {}
    for ruta in rutas:
        if es_excluido(ruta) or not (repo / ruta).is_file():
            continue
        salida[ruta] = (repo / ruta).read_text(encoding="utf-8", errors="replace")
    return salida


def resumen_modulos(g: Grafo, rutas: list[str] | None = None, top: int = 10) -> list[dict]:
    entrantes = g.entrantes()
    filas = []
    for ruta in (rutas if rutas is not None else list(g.nombres)):
        m = g.nombres.get(ruta)
        if m is None or g.rutas.get(m) != ruta:
            continue
        ce, ca = len(g.aristas.get(m, {})), len(entrantes.get(m, ()))
        filas.append({"modulo": m, "archivo": ruta, "eferente": ce, "aferente": ca,
                      "inestabilidad": round(ce / (ce + ca), 3) if ce + ca else 0.0})
    filas.sort(key=lambda f: (-(f["eferente"] + f["aferente"]), f["modulo"]))
    if rutas is not None:
        return filas
    return [f for f in filas if f["eferente"] + f["aferente"]][:top]  # el ranking omite modulos sin dependencias


def analizar_cambio(cs: ChangeSet, despues: dict[str, str], antes_de: dict[str, str | None]) -> tuple[list[Finding], dict]:
    """Compara el grafo antes y despues del cambio. `antes_de` da el contenido previo de cada archivo cambiado."""
    previas = {r: t for r, t in despues.items() if r not in antes_de}
    previas.update({r: t for r, t in antes_de.items() if t is not None})
    g1, g0 = construir(despues), construir(previas)
    comp1, comp0 = g1.componentes(), g0.componentes()
    hallazgos, nuevas = [], 0
    for ruta in cs.archivos:
        m = g1.nombres.get(ruta)
        if m is None:
            continue
        antes = g0.aristas.get(m, {})
        for destino, linea in g1.aristas.get(m, {}).items():
            if destino in antes:
                continue
            nuevas += 1
            en_ciclo = comp1.get(m) == comp1.get(destino)
            ya_estaba = m in comp0 and destino in comp0 and comp0[m] == comp0[destino]
            if en_ciclo and not ya_estaba:
                hallazgos.append(Finding(ruta, linea, None, "regla", "R0401", "alta", 1, categoria="mantenibilidad",
                                         detalle=f"Importación cíclica nueva: {m} -> {destino}"))
    modulos = resumen_modulos(g1, list(cs.archivos))
    metricas = {
        "dependencias_nuevas": nuevas,
        "acoplamiento_eferente_max": max((f["eferente"] for f in modulos), default=0),
        "acoplamiento_aferente_max": max((f["aferente"] for f in modulos), default=0),
        "modulos": modulos,
    }
    return hallazgos, metricas


def analizar_todo(fuentes: dict[str, str]) -> tuple[list[Finding], dict]:
    """Para el codigo completo: cada ciclo existente es deuda; se reporta una vez, en su primer import."""
    g = construir(fuentes)
    hallazgos = []
    for ciclo in g.ciclos():
        candidatos = sorted((g.rutas[a], linea, a, b) for a in ciclo for b, linea in g.aristas.get(a, {}).items() if b in ciclo)
        ruta, linea, a, b = candidatos[0]
        hallazgos.append(Finding(ruta, linea, None, "regla", "R0401", "alta", 1, categoria="mantenibilidad",
                                 detalle=f"Importación cíclica entre {len(ciclo)} módulos: {', '.join(sorted(ciclo))[:140]}"))
    modulos = resumen_modulos(g)
    todos = resumen_modulos(g, list(g.nombres))
    metricas = {"acoplamiento_eferente_max": max((f["eferente"] for f in todos), default=0),
                "acoplamiento_aferente_max": max((f["aferente"] for f in todos), default=0),
                "ciclos": len(hallazgos), "modulos": modulos, "errores_grafo": g.errores}
    return hallazgos, metricas
