"""Rutas de analítica de inventario y ventas (tag Analitica del contrato OpenAPI).

GET /api/alertas/analitica/rotacion             Rotación por producto (alta, media, baja)
GET /api/alertas/analitica/clasificacion-abc    Clasificación A, B o C del mes en curso
GET /api/alertas/analitica/proximos-agotarse    Productos con stock cercano al umbral
GET /api/alertas/analitica/sin-movimiento       Productos sin ventas en los últimos N días
GET /api/alertas/analitica/demanda-temporada    Productos más vendidos en una temporada

Usa el stock de Inventario y las ventas confirmadas de Ventas y Pedidos.
Las fechas se manejan en UTC.
"""

import math
from datetime import date, datetime, timezone
from decimal import Decimal

from flask import Blueprint, abort, jsonify, request

from clientes.inventario import stock_agrupado
from clientes.ventas import resumen_por_producto
from database import consultar, consultar_uno, transaccion

bp = Blueprint("analitica", __name__, url_prefix="/api/alertas/analitica")

NIVELES = ("alta", "media", "baja")

# Margen sobre el umbral aplicado para "próximos a agotarse" (25 %)
MARGEN_PROXIMOS = Decimal("1.25")

# Límites de la clasificación ABC (porcentaje acumulado de ingresos)
LIMITE_A = Decimal("80")
LIMITE_B = Decimal("95")


def _hoy():
    return datetime.now(timezone.utc).date()


def _leer_fecha(nombre, obligatoria=True):
    """Lee una fecha AAAA-MM-DD de la URL (?nombre=valor) o responde 400."""
    valor = request.args.get(nombre)
    if not valor:
        if obligatoria:
            abort(400, f"{nombre} es obligatoria (formato AAAA-MM-DD)")
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        abort(400, f"{nombre} no es una fecha válida (formato AAAA-MM-DD)")


def _multiplicador_vigente():
    """Multiplicador de la temporada vigente hoy (el mayor si hay varias), o 1."""
    hoy = _hoy()
    fila = consultar_uno(
        "SELECT MAX(multiplicador) AS multiplicador FROM temporada "
        "WHERE fecha_inicio <= %s AND fecha_fin >= %s",
        (hoy, hoy),
    )
    return Decimal(fila["multiplicador"] or 1)


def _calcular_rotacion(ventas, stock_por_producto, productos):
    """Calcula índice y nivel de rotación para los productos indicados.

    Índice = unidades vendidas / stock actual (si el stock es 0, se usan las unidades).
    Nivel: los productos sin ventas son "baja"; los vendidos se dividen en tercios
    ordenados de mayor a menor índice: alta, media, baja.
    """
    filas = []
    for producto_id in productos:
        unidades = ventas.get(producto_id, {}).get("unidades", 0)
        stock = stock_por_producto.get(producto_id, 0)
        indice = unidades / stock if stock > 0 else float(unidades)
        filas.append(
            {
                "producto_id": producto_id,
                "unidades_vendidas": unidades,
                "indice_rotacion": round(indice, 2),
            }
        )

    filas.sort(key=lambda f: (-f["indice_rotacion"], f["producto_id"]))
    vendidos = [fila for fila in filas if fila["unidades_vendidas"] > 0]
    for posicion, fila in enumerate(vendidos):
        fila["nivel"] = NIVELES[min(posicion * 3 // len(vendidos), 2)]
    for fila in filas:
        fila.setdefault("nivel", "baja")
    return filas


@bp.get("/rotacion")
def rotacion():
    desde = _leer_fecha("desde")
    hasta = _leer_fecha("hasta")
    if hasta < desde:
        abort(400, "hasta no puede ser anterior a desde")
    nivel = request.args.get("nivel")
    if nivel and nivel not in NIVELES:
        abort(400, "nivel debe ser uno de: " + ", ".join(NIVELES))

    ventas = resumen_por_producto(desde, hasta)
    por_producto, _ = stock_agrupado()
    productos = set(ventas) | set(por_producto)

    filas = _calcular_rotacion(ventas, por_producto, productos)
    if nivel:
        filas = [fila for fila in filas if fila["nivel"] == nivel]
    return jsonify(filas)


@bp.get("/clasificacion-abc")
def clasificacion_abc():
    """Clasifica los productos por ingresos del mes en curso (regla de Pareto).

    A: hasta el 80 % acumulado de ingresos; B: hasta el 95 %; C: el resto.
    Guarda el resultado en clasificacion_producto y el resumen en resumen_ventas_producto.
    """
    hoy = _hoy()
    inicio_mes = hoy.replace(day=1)
    periodo = hoy.strftime("%Y-%m")

    ventas = resumen_por_producto(inicio_mes, hoy)
    por_producto, _ = stock_agrupado()
    productos = set(ventas) | set(por_producto)
    if not productos:
        return jsonify([])

    rotaciones = {
        fila["producto_id"]: fila
        for fila in _calcular_rotacion(ventas, por_producto, productos)
    }

    ordenados = sorted(
        productos,
        key=lambda p: (-ventas.get(p, {}).get("ingresos", Decimal("0")), p),
    )
    total = sum((ventas.get(p, {}).get("ingresos", Decimal("0")) for p in productos), Decimal("0"))

    resultado = []
    acumulado = Decimal("0")
    with transaccion() as cursor:
        for producto_id in ordenados:
            datos = ventas.get(producto_id, {})
            ingresos = datos.get("ingresos", Decimal("0"))
            porcentaje_previo = acumulado * 100 / total if total > 0 else Decimal("100")
            if ingresos <= 0:
                categoria = "C"
            elif porcentaje_previo < LIMITE_A:
                categoria = "A"
            elif porcentaje_previo < LIMITE_B:
                categoria = "B"
            else:
                categoria = "C"
            acumulado += ingresos

            rot = rotaciones[producto_id]
            cursor.execute(
                "INSERT INTO clasificacion_producto (producto_id, categoria_abc, "
                "nivel_rotacion, indice_rotacion, periodo_calculo) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE categoria_abc = VALUES(categoria_abc), "
                "nivel_rotacion = VALUES(nivel_rotacion), "
                "indice_rotacion = VALUES(indice_rotacion)",
                (producto_id, categoria, rot["nivel"], rot["indice_rotacion"], periodo),
            )
            cursor.execute(
                "INSERT INTO resumen_ventas_producto (producto_id, periodo, "
                "unidades_vendidas, ingresos) VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE unidades_vendidas = VALUES(unidades_vendidas), "
                "ingresos = VALUES(ingresos)",
                (producto_id, periodo, datos.get("unidades", 0), ingresos),
            )
            resultado.append(
                {"producto_id": producto_id, "categoria": categoria, "periodo_calculo": periodo}
            )

    return jsonify(resultado)


@bp.get("/proximos-agotarse")
def proximos_agotarse():
    """Productos con stock por encima del umbral aplicado, pero a no más del 25 %."""
    umbrales = consultar(
        "SELECT producto_id, bodega_id, stock_minimo FROM umbral_stock "
        "WHERE activo = TRUE ORDER BY id"
    )
    if not umbrales:
        return jsonify([])

    por_producto, por_producto_bodega = stock_agrupado()
    multiplicador = _multiplicador_vigente()

    resultado = {}
    for umbral in umbrales:
        producto_id = umbral["producto_id"]
        if umbral["bodega_id"] is None:
            stock = por_producto.get(producto_id, 0)
        else:
            stock = por_producto_bodega.get((producto_id, umbral["bodega_id"]), 0)

        umbral_aplicado = math.ceil(umbral["stock_minimo"] * multiplicador)
        if umbral_aplicado < stock <= umbral_aplicado * MARGEN_PROXIMOS:
            resultado.setdefault(
                producto_id,
                {
                    "producto_id": producto_id,
                    "stock_actual": stock,
                    "stock_minimo": umbral_aplicado,
                    "dias_sin_movimiento": None,
                },
            )

    return jsonify(list(resultado.values()))


@bp.get("/sin-movimiento")
def sin_movimiento():
    """Productos con stock en Inventario y sin ventas en los últimos N días."""
    valor = request.args.get("dias", "90")
    try:
        dias = int(valor)
    except ValueError:
        abort(400, "dias debe ser un número entero")
    if dias < 1:
        abort(400, "dias debe ser mayor o igual a 1")

    hoy = _hoy()
    ventas = resumen_por_producto()  # todo el historial, para conocer la última venta
    por_producto, _ = stock_agrupado()

    umbrales = {
        fila["producto_id"]: fila["stock_minimo"]
        for fila in consultar(
            "SELECT producto_id, MAX(stock_minimo) AS stock_minimo FROM umbral_stock "
            "WHERE activo = TRUE GROUP BY producto_id"
        )
    }

    resultado = []
    for producto_id in sorted(por_producto):
        stock = por_producto[producto_id]
        if stock <= 0:
            continue
        ultima_venta = ventas.get(producto_id, {}).get("ultima_venta")
        dias_sin_venta = (hoy - ultima_venta.date()).days if ultima_venta else None
        if dias_sin_venta is None or dias_sin_venta > dias:
            resultado.append(
                {
                    "producto_id": producto_id,
                    "stock_actual": stock,
                    "stock_minimo": umbrales.get(producto_id),
                    "dias_sin_movimiento": dias_sin_venta,
                }
            )
    return jsonify(resultado)


@bp.get("/demanda-temporada")
def demanda_temporada():
    """Productos vendidos durante una temporada, de mayor a menor demanda."""
    valor = request.args.get("temporada_id")
    if not valor or not valor.isdigit():
        abort(400, "temporada_id es obligatorio y debe ser un número entero")

    temporada = consultar_uno(
        "SELECT fecha_inicio, fecha_fin FROM temporada WHERE id = %s", (int(valor),)
    )
    if temporada is None:
        abort(404, "Temporada no encontrada")

    ventas = resumen_por_producto(temporada["fecha_inicio"], temporada["fecha_fin"])
    if not ventas:
        return jsonify([])

    por_producto, _ = stock_agrupado()
    filas = _calcular_rotacion(ventas, por_producto, set(ventas))
    filas.sort(key=lambda f: (-f["unidades_vendidas"], f["producto_id"]))
    return jsonify(filas)