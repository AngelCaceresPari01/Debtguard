def resumen_ventas(filas, minimo, maximo):
    total = 0
    cuenta = 0
    for fila in filas:
        valor = fila["importe"] * fila["cantidad"]
        if valor >= minimo and valor <= maximo:
            total = total + valor
            cuenta = cuenta + 1
    promedio = total / cuenta if cuenta else 0
    return {"total": total, "cuenta": cuenta, "promedio": promedio}


def resumen_compras(filas, minimo, maximo):
    total = 0
    cuenta = 0
    for fila in filas:
        valor = fila["importe"] * fila["cantidad"]
        if valor >= minimo and valor <= maximo:
            total = total + valor
            cuenta = cuenta + 1
    promedio = total / cuenta if cuenta else 0
    return {"total": total, "cuenta": cuenta, "promedio": promedio}
