"""Cliente REST del servicio de Inventario.

Se llama directamente por la dirección interna INVENTARIO_URL
(Entrega 2, sección 1.2). Ruta usada:

GET /api/inventario/stock   Lista de existencias:
    [{"id", "producto_id", "bodega_id", "cantidad", "cantidad_reservada", "stock_minimo"}]
"""

import requests
from flask import abort

from config import Config

TIMEOUT = 5  # segundos


def obtener_stock(producto_id=None, bodega_id=None):
    """Devuelve la lista de existencias de Inventario.

    Responde 503 si Inventario no está disponible y 502 si su respuesta
    no tiene el formato esperado.
    """
    parametros = {}
    if producto_id is not None:
        parametros["producto_id"] = producto_id
    if bodega_id is not None:
        parametros["bodega_id"] = bodega_id

    try:
        respuesta = requests.get(
            f"{Config.INVENTARIO_URL}/api/inventario/stock",
            params=parametros,
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        abort(503, "Inventario no disponible")

    if respuesta.status_code != 200:
        abort(502, "Respuesta inesperada del servicio de Inventario")
    try:
        existencias = respuesta.json()
    except ValueError:
        abort(502, "Respuesta inesperada del servicio de Inventario")
    if not isinstance(existencias, list):
        abort(502, "Respuesta inesperada del servicio de Inventario")
    return existencias


def stock_agrupado():
    """Agrupa el stock de Inventario.

    Devuelve dos diccionarios:
      - por_producto: {producto_id: cantidad total en todas las bodegas}
      - por_producto_bodega: {(producto_id, bodega_id): cantidad}
    """
    por_producto = {}
    por_producto_bodega = {}
    for existencia in obtener_stock():
        producto_id = existencia.get("producto_id")
        bodega_id = existencia.get("bodega_id")
        cantidad = existencia.get("cantidad") or 0
        if producto_id is None:
            continue
        por_producto[producto_id] = por_producto.get(producto_id, 0) + cantidad
        por_producto_bodega[(producto_id, bodega_id)] = cantidad
    return por_producto, por_producto_bodega