# Estudio de caso: sqlite-utils

Aplicación de debtguard v1.1 y su dashboard a un repositorio real, para mostrar cómo se usa y qué datos produce. Sirve como insumo para un informe posterior.

## Repositorio analizado

| Dato | Valor |
|---|---|
| Proyecto | [simonw/sqlite-utils](https://github.com/simonw/sqlite-utils): librería y herramienta de consola en Python para trabajar con bases SQLite |
| Licencia | Apache 2.0 |
| Commit analizado | `9c66bafa52ae23d40499c74b0db3b635bcddb876` (10 de octubre de 2026) |
| Por qué este repositorio | Es Python de producción real, y en sus últimos commits mezcla algunos que declaran IA (`Co-Authored-By: Claude`) con otros que no |
| Alcance | Código actual y últimos 100 commits sin merges |

El clon está en `estudio_caso/repo/` y no se sube a git. Para reproducir:

```powershell
git clone https://github.com/simonw/sqlite-utils.git estudio_caso\repo
git -C estudio_caso\repo checkout 9c66bafa52ae23d40499c74b0db3b635bcddb876
dashboard-web\.venv\Scripts\python.exe -m pip install websocket-client
dashboard-web\.venv\Scripts\python.exe -m dashboard.server
```

Después, en otra terminal, con el dashboard ya iniciado:

```powershell
dashboard-web\.venv\Scripts\python.exe estudio_caso\capturar.py estudio_caso\repo --commits 100
```

La primera ejecución tardó unos 2 min 40 s en medir los 100 commits; las siguientes reutilizan la caché.

## Resultados: código actual

Mide 11 archivos Python de producción: 10 368 líneas y 319 funciones. Se excluyeron 54 archivos de pruebas.

| Métrica | Valor | Lectura |
|---|---|---|
| Deuda estimada | 186,1 h (18 h/KLOC) | Nota SQALE A: la razón de deuda es 3,6 % |
| Origen de la deuda | Complejidad 90,9 h · reglas 76,4 h · clones 18,3 h · SATD 0,5 h | La complejidad y las reglas explican el 90 % |
| Complejidad cognitiva máxima | 265 (`Table.insert_all`, en `db.py`) | Casi 18 veces el umbral de 15 |
| Complejidad ciclomática máxima | 133 (`Table.transform_sql`) | 13 veces el umbral de 10 |
| Clones exactos | 49 | |
| Clones parecidos (v1.1) | 6 | Funciones con la misma estructura que solo los clones exactos no habrían detectado |
| Advertencias | 293 (28 por KLOC): 2 críticas, 29 altas, 66 medias, 196 bajas | Las más frecuentes: demasiados argumentos (PLR0913: 52; PLR0917: 50), `raise` sin `from` (B904: 37) y SQL construido con texto (S608: 29) |
| Acoplamiento (v1.1) | Salida máxima 5 (`sqlite_utils.cli`); entrada máxima 3 (`sqlite_utils.db`, `sqlite_utils.utils`) | Bajo: es un paquete pequeño |
| Ciclos de importación (v1.1) | 0 | |
| Mantenibilidad (Radon) | Mínimo 0; promedio por líneas 5,0; 3 archivos en 0 | `db.py` (5 072 líneas) y `cli.py` (3 465) son archivos muy grandes, y por eso el mínimo queda en 0 |
| SATD | 3 comentarios | |

**Lectura:** la nota A convive con funciones muy complejas. La razón de deuda se diluye en 10 000 líneas, mientras que la deuda se concentra en pocas funciones de `db.py` y `cli.py`. Para priorizar sirven más la tabla de funciones y la de archivos que la nota global.

## Resultados: historial

De los 100 commits, 62 cambian Python de producción, entre el 5 de julio y el 22 de septiembre de 2026.

| Grupo | Commits | Deuda introducida | Líneas añadidas | Mediana h/KLOC | Bloqueados |
|---|---|---|---|---|---|
| IA declarada | 22 | 16,2 h | 598 | 6,9 | 5 |
| Sin declarar | 40 | 57,2 h | 2 445 | 6,7 | 8 |
| **Total** | **62** | **73,4 h** | **3 043** | | **13** |

**Comparación entre grupos** (Mann-Whitney U, delta de Cliff y Holm, en `datos/comparacion_ia.json`): no hay diferencias significativas en ninguna de las 10 métricas, y todos los p ajustados valen 0,555 o más. La mayor diferencia aparece en la complejidad cognitiva máxima de las funciones tocadas (mediana 38 frente a 23,5; δ = 0,15, pequeño; p = 0,34), sin significancia. Coincide con el experimento del Hito 2.

**Commit con más deuda:** `69a1c0d9`, «Fixes for Ruff>=0.16.0» (22,2 h, sin declarar). Es un commit que corrige estilo, pero reescribe muchas líneas de funciones ya complejas; debtguard le atribuye las advertencias que siguen presentes en esas líneas nuevas. Es una limitación conocida: una reescritura «hereda» los problemas de las líneas que toca.

**Cautelas:**
- «Sin declarar» no significa escrito por una persona.
- Los grupos no se emparejan por tarea, como en el experimento, así que la comparación muestra asociación, no causa.
- Las horas son estimaciones sin validar.

## Archivos

| Archivo | Contenido |
|---|---|
| `datos/resultado_completo.json` | Todo lo que devolvió el dashboard |
| `datos/commits.csv` | Una fila por commit con Python: métricas, horas, IRD y veredicto |
| `datos/hallazgos_codigo.csv` | Los 473 hallazgos del código actual |
| `datos/archivos.csv`, `datos/funciones.csv`, `datos/modulos.csv` | Tablas por archivo, por función (las 15 más complejas) y por módulo (acoplamiento) |
| `datos/comparacion_ia.json` | Prueba estadística entre IA declarada y el resto |
| `capturas/01`–`06` | Las seis pestañas del dashboard |
| `capturas/07`–`09` | Explicaciones de advertencias, acoplamiento y clones parecidos |
| `capturar.py` | Script que genera todo lo anterior |
