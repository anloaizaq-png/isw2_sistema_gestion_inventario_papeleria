"""Llamadas REST a otros microservicios (Productos, Inventario, Alertas)."""
import logging

import httpx
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger("compras")
TIMEOUT = 5.0


def _llamar(servicio: str, metodo: str, url: str, **kwargs) -> httpx.Response:
    try:
        return httpx.request(metodo, url, timeout=TIMEOUT, **kwargs)
    except httpx.RequestError:
        raise HTTPException(503, f"No se pudo conectar con el servicio de {servicio}")


# ---------- Productos ----------
def obtener_producto(producto_id: int) -> dict | None:
    """Devuelve el producto desde el servicio de Productos, o None si no existe."""
    r = _llamar("Productos", "GET", f"{settings.productos_url}/api/productos/{producto_id}")
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise HTTPException(502, "Respuesta inesperada del servicio de Productos")
    return r.json()


def exigir_producto_activo(producto_id: int) -> dict:
    """Valida que el producto exista y esté activo; si no, responde 422."""
    producto = obtener_producto(producto_id)
    if producto is None:
        raise HTTPException(422, f"El producto {producto_id} no existe")
    if producto.get("estado") != "activo":
        raise HTTPException(422, f"El producto {producto_id} está inactivo")
    return producto