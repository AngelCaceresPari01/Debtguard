# Debtguard

Detección y estimación en horas de la deuda técnica en código generado por LLMs. Es el trabajo de los Hitos 1 y 2 del curso Tópicos Avanzados de Ingeniería de Sistemas.

El repositorio reúne tres partes:

1. **`debtguard`:** prototipo de consola. Recibe un diff de Python, detecta la deuda que introduce (complejidad, malas prácticas, clones y comentarios `TODO`) y la estima en horas de corrección con un modelo de tipo SQALE.
2. **Experimento del Hito 2:** compara 30 problemas reales de SWE-bench Lite resueltos por personas y por DeepSeek-V4-Pro.
3. **`dashboard-web`:** aplicación web local para analizar cualquier carpeta o repositorio git con las mismas métricas.

## Resultados en breve

- **Deuda:** no hubo diferencias significativas entre el código humano y el del LLM en ninguna de las 7 métricas (Wilcoxon con corrección de Holm, n = 30 pares).
- **Corrección:** según las pruebas oficiales de SWE-bench, el LLM resolvió **9 de 30** problemas y las personas, 30 de 30. Con solo los 9 pares correctos tampoco hubo diferencias.
- **Tamaño:** los parches del LLM son más pequeños: mediana de 3 líneas añadidas frente a 9.

**Pendiente del equipo:** la revisión manual de 60 alertas (Kappa y precisión) y la validación cronometrada de los costos.

## Versión 1.1 (rama `v1.1-vacios`)

Cubre tres vacíos detectados en el Hito 1. No cambia los resultados entregados, que siguen siendo los de `v1.0-experimento` en `reports/`.

| Mejora | Qué hace | Dónde |
|---|---|---|
| Clones parecidos (Tipo 3) | Detecta funciones con la misma estructura aunque cambien los nombres (`jscpd --similarity 0.8`). Se cuentan aparte de los exactos y cuestan 20 min | `metrics/clones.py` |
| Acoplamiento | Construye el grafo de imports con `ast` y calcula, por módulo, dependencias de salida (Ce), de entrada (Ca) e inestabilidad. En un cambio, cuenta también las dependencias internas nuevas | `metrics/coupling.py` |
| Ciclos de importación | Usa el mismo grafo en lugar de Pylint R0401 y agrupa los ciclos en componentes, en vez de enumerar caminos. En Django (815 módulos) tardó 17 s frente a 33 s de Pylint, y encontró 7 grupos en ciclo donde Pylint lista 341 ciclos | `metrics/coupling.py` |
| Índice de mantenibilidad | Reporta el cambio que produce el parche (`delta_mi`) y cuántos archivos tienen el índice en 0, en vez de usar solo el mínimo | `pipeline.py` |

Las opciones `clones.similitud` y `ciclos.motor` de `config/remediation_costs.yaml` permiten volver al comportamiento de la v1.0.

**Re-medición del experimento:** `experiments/remedir_v11.py` mide de nuevo los 60 parches en `reports_v11/`, y `experiments/analysis_v11.py` guarda las tablas en `data/v11/`. Tampoco aquí hubo diferencias significativas entre el código humano y el del LLM. Los resultados coinciden con la v1.0 salvo en un parche del LLM, en el que aparece un clon parecido nuevo, y ninguna de las dos versiones encontró ciclos nuevos.

**Estudio de caso:** `estudio_caso/` analiza un repositorio real con el dashboard y guarda datos y capturas. Ver [`estudio_caso/README.md`](estudio_caso/README.md).

## Contenido

| Carpeta | Contenido |
|---|---|
| `src/debtguard/` | Prototipo: lectura del diff, métricas, estimador de costo, veredicto y reportes |
| `config/` | Costos de remediación y umbrales calibrados |
| `tests/` | Pruebas automáticas y archivos con deuda conocida |
| `experiments/` | Muestreo, generación con DeepSeek, lote, análisis, validación y comprobación funcional |
| `data/` | Casos, respuestas crudas del LLM, resultados, tablas y plantillas de validación |
| `casos/` | Parches humanos y del LLM de cada caso |
| `reports/` | JSON del prototipo para cada parche y para la muestra de calibración |
| `docs/` | Figuras y capturas del experimento |
| `dashboard-web/` | Dashboard local |

La etiqueta `v1.0-experimento` marca la configuración congelada antes de medir los parches del LLM.

## Requisitos

- Windows 10 u 11 (lo probado), Python 3.13, Node.js 18 o superior y git.
- Docker solo si quieres repetir la comprobación funcional con SWE-bench.

## Instalación

En PowerShell:

```powershell
git clone https://github.com/AngelCaceresPari01/Debtguard.git
cd Debtguard
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -e .
npm ci
.venv\Scripts\python.exe -m pytest
```

Las pruebas deben terminar con `34 passed`. `npm ci` instala jscpd, el detector de clones, con la versión fijada en `package-lock.json`.

## Usar el prototipo

El prototipo analiza un parche **ya aplicado** en un repositorio, y compara contra el commit anterior (`HEAD`):

```powershell
.venv\Scripts\python.exe -m debtguard analyze --diff cambio.patch --repo C:\ruta\al\repo --case-id mi-cambio --origin LLM --json salida\mi-cambio.json --md salida\mi-cambio.md
```

Imprime el veredicto, las horas, la nota SQALE y el número de hallazgos. El código de salida es 1 si el veredicto es BLOQUEAR.

### Volver a medir uno de los 30 casos

Primero descarga los repositorios del experimento. Pesan varios GB y se guardan en `repos\`, que no se sube a git:

```powershell
.venv\Scripts\python.exe experiments\prepare_repos.py
```

Después, cambiando solo las dos primeras líneas:

```powershell
$id = 'pytest-dev__pytest-7373'
$origen = 'llm'     # 'llm' o 'humano'

$fila = Import-Csv data\casos.csv | Where-Object instance_id -eq $id
$repo = 'repos\' + ($fila.repo -replace '/', '__')
git -C $repo reset -q --hard
git -C $repo clean -qfdx
git -C $repo checkout -qf $fila.base_commit
git -C $repo apply --index --whitespace=nowarn (Resolve-Path "casos\${id}_$origen.patch")
if ($origen -eq 'llm') { $extra = @('--origin','LLM','--model','deepseek-v4-pro') } else { $extra = @('--origin','humano') }
.venv\Scripts\python.exe -m debtguard analyze --diff "casos\${id}_$origen.patch" --repo $repo --case-id "${id}_$origen" @extra --json "salida\${id}_$origen.json" --md "salida\${id}_$origen.md"
git -C $repo reset -q --hard
git -C $repo clean -qfdx
```

El resultado queda en `salida\`. No lo guardes en `reports\`, porque el análisis lee todos los JSON de esa carpeta. Los identificadores de los 30 casos están en `data\seleccion.csv`.

## Dashboard

```powershell
cd dashboard-web
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m dashboard.server
```

Abre http://127.0.0.1:8765, elige una carpeta y pulsa Analizar. También puedes iniciarlo con doble clic en `dashboard-web\iniciar.bat`, que instala las dependencias la primera vez.

- **Qué puede analizar:** el código actual, los últimos commits o los cambios sin confirmar.
- **Qué muestra:** cada métrica abre una explicación de qué significa el resultado.
- **Solo lectura:** la carpeta analizada no se modifica y su código no se ejecuta.

Más detalle en [`dashboard-web/README.md`](dashboard-web/README.md).

## Reproducir el experimento

Las respuestas de DeepSeek ya están guardadas en `data/llm/`, así que **no hace falta la API** para repetir las mediciones y el análisis:

```powershell
.venv\Scripts\python.exe experiments\prepare_repos.py
.venv\Scripts\python.exe experiments\run_batch.py --rol calibracion
.venv\Scripts\python.exe experiments\run_batch.py --rol comparacion
.venv\Scripts\python.exe experiments\analysis.py
cd experiments
..\.venv\Scripts\python.exe analysis_correccion.py
..\.venv\Scripts\python.exe fechas_base.py
cd ..
```

Los comandos de `run_batch.py` no vuelven a medir los casos que ya tienen JSON en `reports\`. Para medirlos de nuevo, mueve esos archivos a otra carpeta.

**Para generar parches nuevos con DeepSeek**, crea un archivo `.env` con `DEEPSEEK_API_KEY=tu_clave` (ver `.env.example`) y ejecuta `experiments\generate_llm.py`. El archivo `.env` está en `.gitignore`: nunca subas tu clave.

**Para la comprobación funcional con SWE-bench**, necesitas Docker. El procedimiento está en `experiments/swe_eval.py`, y sus resultados en `data/correccion/correccion.csv`.

## Validación manual

P2 y P3 etiquetan por separado `data/validacion/alertas_P2.csv` y `data/validacion/alertas_P3.csv` con VP o FP, sin abrir `clave_no_abrir.csv`. Después:

```powershell
.venv\Scripts\python.exe experiments\validation.py calcular
```

## Uso de asistentes de IA

El prototipo y el análisis se hicieron con ayuda de Claude Code. Los parches del experimento los generó únicamente DeepSeek-V4-Pro.

## Autores

Carrasco Choque Arles Melvin, Caceres Pari Angel Raul, Chancuaña Alvis Klismann y Yana Agramonte Luis Efrain.
