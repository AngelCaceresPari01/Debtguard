# debtguard dashboard

Aplicación local que aplica el prototipo de los Hitos 1 y 2 a cualquier carpeta. Eliges una carpeta, y el sistema busca su repositorio git, mide el código Python y muestra las métricas del experimento: complejidad, clones, advertencias, mantenibilidad, SATD y horas de deuda.

## Requisitos

- Windows, Python 3.13, git y Node.js 18 o superior.
- Este dashboard vive dentro del repositorio Debtguard: usa el paquete de la raíz, y antes hay que ejecutar `npm ci` en la raíz para disponer de jscpd.

## Iniciar

Haz doble clic en `iniciar.bat`, o ejecuta:

```bash
.venv/Scripts/python -m dashboard.server
```

Luego abre http://127.0.0.1:8765. Para usar otro puerto, define `DEBTGUARD_PUERTO`.

## Qué analiza

| Opción | Qué mide | Requiere git |
|---|---|---|
| Código actual | Todo el código Python de producción, tratado como nuevo | No |
| Historial | Lo que introduce cada commit, igual que el experimento | Sí |
| Cambios sin confirmar | Lo que introducen tus cambios actuales frente a HEAD, incluidos los archivos Python nuevos | Sí |

Si la carpeta no es un repositorio, el sistema busca repositorios dentro de ella, hasta 3 niveles.

## Seguridad

- **Solo lectura:** los checkouts ocurren en un clon temporal, y el código actual se copia a una carpeta temporal.
- **No ejecuta el código analizado:** todas las herramientas lo leen sin importarlo, y git se llama sin hooks ni programas externos configurados por la carpeta.
- **Solo local:** el servidor escucha en 127.0.0.1 y rechaza peticiones de otros sitios.
- **Sin servicios externos:** no llama a ninguna API de LLM ni envía datos fuera del equipo.

## Límites

- Solo mide Python.
- No comprueba si el código funciona.
- Las horas son una estimación, y la precisión de las alertas sigue pendiente de validación manual.
- «IA declarada» se detecta por menciones en los commits (por ejemplo, `Co-Authored-By: Claude`). «Sin declarar» no significa que lo haya escrito una persona.
- El IRD y el veredicto están calibrados con 20 parches humanos pequeños, por lo que solo se aplican a cambios.

## Pruebas

```bash
.venv/Scripts/python -m pytest
```

Los resultados por commit se guardan en `cache/`. Se puede borrar sin problema.
