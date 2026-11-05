# debtguard

Prototipo que recibe un diff de Python, detecta la deuda técnica que introduce y la estima en horas de remediación con un modelo de tipo SQALE. También calcula un índice de riesgo y un veredicto. Es determinista: no usa un LLM para decidir.

## Instalación

Requiere Python 3.13, Node.js 18 o superior y git.

```bash
py -3.13 -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/pip install -e .
npm ci
.venv/Scripts/python -m pytest
```

## Uso

Aplica primero el parche en el repositorio, sin hacer commit, y ejecuta:

```bash
python -m debtguard analyze --diff cambio.patch --repo ruta/al/repo --case-id X --origin LLM --json reports/X.json --md reports/X.md
```

El código de salida es 1 si el veredicto es BLOQUEAR.

## Reproducir el experimento

Crea un archivo `.env` con `DEEPSEEK_API_KEY=...`. Este archivo no se versiona.

```bash
python experiments/sample.py
python experiments/generate_llm.py
cd experiments && python revalidate_llm.py && cd ..
python experiments/run_batch.py --rol calibracion
python experiments/calibrate.py
python experiments/run_batch.py --rol comparacion
python experiments/validation.py muestra
python experiments/analysis.py
```

Las respuestas crudas del LLM están en `data/llm/`, así que no hace falta volver a llamar a la API para repetir el análisis.

## Validación manual

P2 y P3 completan por separado `data/validacion/alertas_P2.csv` y `alertas_P3.csv` con VP o FP. Después:

```bash
python experiments/validation.py calcular
```

No abras `clave_no_abrir.csv` antes de etiquetar: indica el origen de cada alerta.

## Estructura

- `src/debtguard/`: ingesta, métricas, estimador y reportes
- `config/`: costos, umbrales y resultados de calibración
- `experiments/`: muestreo, generación, lote, análisis y validación
- `data/`, `casos/`, `reports/`: casos, parches, resultados y JSON por caso
- `docs/`: figuras y generador del informe

## Comprobar corrección (opcional, requiere Docker)

Construye una imagen con `swebench==5.0.2`, monta `data/correccion` en `/work` y el socket de Docker, y ejecuta `swe_eval.py` dentro. Después:

```bash
python experiments/swe_predicciones.py
cd experiments && python analysis_correccion.py
```
