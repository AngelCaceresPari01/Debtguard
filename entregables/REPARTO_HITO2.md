# Reparto del Hito 2: qué está hecho y qué falta

Entrega: 10 de noviembre de 2026. El informe sigue la numeración de `ej1.jpeg`. Lo que falta está resaltado en amarillo como **PENDIENTE** en el Word.

## Lo que debe hacer cada persona

### P1: prototipo e implementación

| Tarea | Estado |
|---|---|
| Código, pruebas y README (raíz del repositorio) | Hecho; 34 pruebas pasan |
| Preparar repositorios y correr los 60 casos | Hecho |
| Índice de riesgo y veredicto | Hecho |
| Secciones 4.1, 4.2 y 4.3 | Borrador hecho; revisar |
| Publicar el repositorio en GitHub y poner el enlace en el Anexo A | **Falta** |

### P2: datos y análisis

| Tarea | Estado |
|---|---|
| Elegir 30 issues y generar parches con DeepSeek | Hecho |
| Estadística, gráficos y sensibilidad de costos | Hecho |
| Secciones 3.3, 3.4 y 5 | Borrador hecho; revisar |
| Primer revisor: etiquetar `data/validacion/alertas_P2.csv` | **Falta** |
| Corregir y cronometrar 10–15 hallazgos para medir el error del costo | **Falta** |

### P3: informe y validación

| Tarea | Estado |
|---|---|
| Carátula, índice, secciones 1, 2, 3.1, 3.2 y 6, referencias y anexos | Borrador hecho; revisar |
| Segundo revisor: etiquetar `data/validacion/alertas_P3.csv`, sin ver las etiquetas de P2 | **Falta** |
| Calcular el Kappa y la precisión y llevarlos a la tabla de validación | **Falta** |
| Unir, revisar y entregar el documento final | **Falta** |

Para calcular el Kappa y la precisión:

```bash
cd Debtguard
.venv/Scripts/python experiments/validation.py calcular
```

Para regenerar el Word con datos nuevos, usa `docs/build_informe.py`. Ojo: sobrescribe los cambios hechos a mano en el Word.

## Decisiones que debe confirmar el equipo

1. **Integrantes y roles.** La carátula del Hito 1 tiene 4 integrantes, `ej1` y `ej2` tienen 3 personas (P1–P3) y la guía reparte entre 4. Falta decidir quién es cada P y qué hace la cuarta persona.
2. **Corrección funcional (ya medida).** Con las pruebas de SWE-bench, los 30 parches humanos pasan y solo 9 de 30 de DeepSeek resuelven el issue. Conviene preparar esta explicación para la exposición: la comparación principal mezcla parches correctos e incorrectos, y con solo los 9 correctos tampoco hay diferencias.
## Corrección para la exposición

La guía responde que se usó SWE-bench porque «el parche humano es previo a los asistentes de IA». **No lo digan así, porque no se cumple en toda la muestra.** Usen esto:

> «SWE-bench es pareado: mismo issue y mismo commit base. 10 de los 30 commits base son de 2022 en adelante, así que parte del grupo humano pudo usar asistentes. Repetimos el análisis con los 20 pares anteriores a 2022 y tampoco encontramos diferencias.»

La tabla P1 de la guía también dice que los parches humanos son «previos a 2023»; aquí 5 de los 30 commits base son de 2023 en adelante.

## Cambios frente a la guía

| Guía | Lo que se hizo | Motivo |
|---|---|---|
| Python 3.11 | Python 3.13.5 | Es la versión instalada; 3.11 no lo está |
| Se cobra toda la complejidad de la función tocada | Se cobra solo el aumento | Es lo que la guía pide medir: no culpar al cambio de la deuda previa |
| Clones que tocan líneas nuevas | Al menos 50 % de líneas nuevas | Tocar una línea de un bloque ya duplicado no crea un clon |
| R0401 directo | Un ciclo por import nuevo, si no estaba ya enredado | Sin esto, un parche pequeño recibía 2 390 h |
| Excluir los parches que no aplican | Reemplazarlos desde la reserva | Mantener 30 pares; se reporta la tasa de fallo |
| Sin indicación sobre el razonamiento del modelo | Razonamiento desactivado | Para que la temperatura 0 tenga efecto |
| `analysis.ipynb` | `analysis.py` | Se ejecuta de principio a fin sin pasos manuales |
| Sensibilidad ±25 % | ±25 % por familia | Escalar todos los costos por igual no cambia la prueba |
| Etiqueta antes del lote | Etiqueta después de calibrar | Los umbrales ya quedan fijados dentro de ella |
| Pruebas de SWE-bench «si hay tiempo» | Hechas tras el lote, con Docker | El análisis con parches correctos se declara exploratorio |
| Clonar con GitPython | Se usa `git` directamente | Se necesita controlar los bytes del parche en Windows; GitPython se retiró de las dependencias |
| Tests en verde en la etiqueta | Un test de la CLI falla en `v1.0-experimento` y se corrigió después | Solo cambió el test; `src/` y `config/` siguen iguales, por lo que los resultados no cambian |
| Opcionales: AIDev, SonarQube, hook o Action, exhaustividad | No realizados | Quedan declarados en Limitaciones |

## Observaciones de los demás archivos

- **`ej1` y `ej2`:** numeran distinto las secciones. `ej2` usa §5–§10 y `ej1` usa 1–6. Se usó `ej1`, porque indica que sigue la numeración del informe.
- **`GUIA_PROTOTIPO.md` y `GUIA_DESARROLLO_HITO2.md`:** citan material que no está en esta carpeta: `Informe_Hito1_..._v2.docx`, `Estudios_Primarios_S01-S10/`, `Matriz_..._Hito1.xlsx` y `diagramas_hito2/`. La discusión frente a S01–S10 se basa en lo que resume el PDF del Hito 1, no en los artículos originales.
- **PDF del Hito 1:** el índice no coincide con el cuerpo. El índice pone Trabajos Relacionados en la sección 2 y el cuerpo en la 3, y no recoge el Marco Teórico. Además, tiene un punto 9 vacío y dos tablas numeradas como 18. Conviene no copiar esa numeración.
- **`GUIA_DESARROLLO_HITO2.md`:** su cronograma empieza el 2/11 con 4 integrantes. El informe usa un cronograma ajustado a P1–P3.

## Seguridad

La clave de DeepSeek está en `.env`, que git ignora. Como se compartió en el chat, revócala en DeepSeek cuando ya no haga falta.
