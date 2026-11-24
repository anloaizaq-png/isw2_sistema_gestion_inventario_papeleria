"""Cliente REST del servicio de Ventas y Pedidos.

Se llama directamente por la dirección interna VENTAS_URL
(Entrega 2, sección 1.2). Ruta usada:

GET /api/ventas?estado=confirmada&fecha_inicio=...&fecha_fin=...
    Lista de ventas: [{"id", "fecha", "estado", "total",
                       "detalles": [{"producto_id", "cantidad", "precio_unitario", "subtotal"}]}]

Solo se usan ventas confirmadas. Las fechas se manejan en UTC.
"""

from datetime import datetime, time
from decimal import Decimal, InvalidOperation

import requests
from flask import abort

from config import Config

TIMEOUT = 5  # segundos


def obtener_ventas_confirmadas(desde=None, hasta=None):
    """Devuelve las ventas confirmadas entre dos fechas (ambas incluidas).

    desde y hasta son objetos date (o None para no limitar).
    Responde 503 si Ventas no está disponible y 502 si su respuesta
    no tiene el formato esperado.
    """
    parametros = {"estado": "confirmada"}
    if desde is not None:
        parametros["fecha_inicio"] = datetime.combine(desde, time.min).isoformat()
    if hasta is not None:
        parametros["fecha_fin"] = datetime.combine(hasta, time.max).isoformat()

    try:
        respuesta = requests.get(
            f"{Config.VENTAS_URL}/api/ventas",
            params=parametros,
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        abort(503, "Ventas no disponible")

    if respuesta.status_code != 200:
        abort(502, "Respuesta inesperada del servicio de Ventas")
    try:
        ventas = respuesta.json()
    except ValueError:
        abort(502, "Respuesta inesperada del servicio de Ventas")
    if not isinstance(ventas, list):
        abort(502, "Respuesta inesperada del servicio de Ventas")
    return ventas


def _a_decimal(valor):
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _a_fecha(valor):
    try:
        return datetime.fromisoformat(str(valor))
    except ValueError:
        return None


def resumen_por_producto(desde=None, hasta=None):
    """Resume las ventas confirmadas por producto.

    Devuelve {producto_id: {"unidades": int, "ingresos": Decimal, "ultima_venta": datetime}}.
    """
    resumen = {}
    for venta in obtener_ventas_confirmadas(desde, hasta):
        fecha_venta = _a_fecha(venta.get("fecha"))
        for detalle in venta.get("detalles") or []:
            producto_id = detalle.get("producto_id")
            if producto_id is None:
                continue
            datos = resumen.setdefault(
                producto_id,
                {"unidades": 0, "ingresos": Decimal("0"), "ultima_venta": None},
            )
            datos["unidades"] += detalle.get("cantidad") or 0
            datos["ingresos"] += _a_decimal(detalle.get("subtotal"))
            if fecha_venta and (
                datos["ultima_venta"] is None or fecha_venta > datos["ultima_venta"]
            ):
                datos["ultima_venta"] = fecha_venta
    return resumen