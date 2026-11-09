# Guía para plantear el prototipo — Parte experimental

Esta guía no trae código. Reúne lo que la revisión (Hito 1) aporta para que el equipo diseñe y construya el prototipo por su cuenta.

## 1. Problema que debe atacar el prototipo (sale de la revisión)

- El código generado por LLMs, sobre todo por **agentes**, acumula más complejidad y más problemas de mantenibilidad: +39 % de complejidad cognitiva y +18 % de advertencias estáticas (S01); 1,87 veces más redundancia semántica (S03); 423 recomendaciones de mantenibilidad frente a 30 (S06).
- La deuda es **menos visible**: los agentes la declaran menos (S02) y los revisores no la notan (S03).
- El **LLM solo no es fiable** para detectarla o repararla: 37 % de refactorizaciones correctas sin validación frente a 98 % de precisión con validación (S08).
- **Vacíos abiertos:** casi nadie estima la deuda en tiempo o costo (SWEBOK §2.3.1), no se mide el acoplamiento y no hay comparaciones entre chat, IDE y agentes sobre la misma tarea.

**Pregunta guía para el prototipo:** ¿cómo detectar y estimar, antes de integrarla al repositorio, la deuda técnica que introduce el código generado por LLMs?

## 2. Ideas de prototipo (elegir una)

| Opción | Qué hace | Vacío que cubre | Dificultad |
|---|---|---|---|
| A. Analizador de deuda en código generado | Recibe código o un *diff* y reporta métricas sensibles: complejidad cognitiva, reglas estáticas, clones y SATD | RQ2: métricas sensibles | Baja–media |
| B. Guardián previo a la integración (pre-commit o pre-push, GitHub Action) | Bloquea o advierte si el cambio supera un umbral de riesgo | Deuda poco visible (S02, S03) | Media |
| C. Estimador de costo de la deuda | Traduce los hallazgos a tiempo de remediación (horas o días) | SWEBOK §2.3.1: costo, casi inexplorado | Media |
| D. Comparador chat vs. IDE vs. agente | Genera la misma tarea con las tres modalidades y compara la deuda | Comparación inexistente en la literatura | Media–alta |
| E. Refactorizador con validación | Un LLM propone refactorizaciones y una capa de validación descarta las malas (enfoque de S08) | Fiabilidad del LLM | Alta |

Recomendación: **A + C** (analizar y estimar el costo). Es alcanzable en un semestre y se alinea con el área SWEBOK elegida. B es una extensión natural.

## 3. Herramientas disponibles (todas gratuitas)

| Necesidad | Herramientas | Usadas en |
|---|---|---|
| Complejidad, tamaño, mantenibilidad | Radon (Python), Lizard (multilenguaje), SonarQube Community | S01, S03, S07 |
| Reglas estáticas y seguridad | CodeQL, Pylint, Ruff, Bandit, SonarQube | S06, S07 |
| Duplicación y clones | jscpd, PMD-CPD; embeddings de código para clones semánticos (CodeBERT, UniXcoder, CodeSage) | S03 |
| Deuda autoadmitida (SATD) | Búsqueda de TODO/FIXME/HACK; clasificadores de SATD | S02, S09, S10 |
| Costo de la deuda | Modelo SQALE (tiempo de remediación de SonarQube) | S07 |
| Integración en el flujo | Git hooks (pre-commit), GitHub Actions | — |
| Generar código con LLM | API de OpenAI, Anthropic o Gemini; GitHub Copilot; agentes (Claude Code, Codex, Cursor) | S06, S07, S09 |
| Análisis de resultados | Python con pandas, scipy (Mann-Whitney U) y matplotlib | S02, S03 |

## 4. Datos para el experimento

- **AIDev**: conjunto público de pull requests creados por agentes en GitHub (lo usan S01, S02 y S03). Permite comparar código de agentes con código humano real.
- **SWE-bench Lite**: 300 issues reales de proyectos Python, con el parche humano de referencia (S06). Permite generar soluciones con LLMs y comparar con el parche humano.
- **XLCoST**: problemas con código en varios lenguajes (S07).
- **Datos propios**: un conjunto de tareas que el grupo resuelve a mano y con LLM.

## 5. Diseño experimental sugerido

1. **Hipótesis:** el código generado por LLM tiene mayor complejidad, más clones y menor mantenibilidad que el código humano equivalente.
2. **Variables independientes:** origen del código (humano o LLM) y, opcionalmente, la modalidad (chat, IDE o agente) y el modelo usado.
3. **Variables dependientes:** complejidad cognitiva y ciclomática, advertencias estáticas, clones, densidad de SATD, índice de mantenibilidad y tiempo de remediación estimado.
4. **Muestra:** por ejemplo, 30–50 tareas o PRs por grupo.
5. **Análisis:** prueba de Mann-Whitney U y tamaño del efecto (delta de Cliff), como en S02 y S03.
6. **Validación del prototipo:** comparar sus alertas con una revisión manual de una muestra. Reportar precisión y exhaustividad y medir el acuerdo entre evaluadores con Kappa de Cohen (como S08 y S09).
7. **Amenazas a la validez:** un solo lenguaje, no determinismo de los LLMs (repetir generaciones) y umbrales elegidos por el equipo.

## 6. Entregables que debería producir el equipo

- Documento de diseño: objetivo, requisitos, arquitectura y métricas elegidas, justificadas con la revisión.
- Prototipo funcional y su repositorio.
- Protocolo y resultados del experimento (tablas, gráficos y pruebas estadísticas).
- Discusión de los resultados frente a S01–S10.

## 7. Reparto sugerido (4 integrantes)

| Integrante | Responsabilidad |
|---|---|
| 1 | Diseño y arquitectura; integración con Git o CI |
| 2 | Métricas y análisis estático (complejidad, reglas, mantenibilidad, costo) |
| 3 | Clones y SATD; datos (AIDev, SWE-bench) y generación con LLMs |
| 4 | Diseño experimental, estadística, validación manual y redacción |

## 8. Material de apoyo en esta carpeta

- `Informe_Hito1_..._v2.docx`: hallazgos, tablas de métricas y técnicas (RQ2) y vacíos de investigación (Discusión).
- `Estudios_Primarios_S01-S10/`: leer primero **S01, S03, S06 y S08**, que describen métricas, herramientas y diseños experimentales replicables.
- `Matriz_..._Hito1.xlsx`, hoja *Extraccion*: stack tecnológico y datos de cada estudio.
