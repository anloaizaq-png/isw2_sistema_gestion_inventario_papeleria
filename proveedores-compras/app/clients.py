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


# ---------- Alertas ----------
ALERTAS_SUGERENCIAS = "/api/alertas/sugerencias-reabastecimiento"


def listar_sugerencias_pendientes():
    """Proxy: devuelve las sugerencias de reabastecimiento pendientes de Alertas."""
    r = _llamar(
        "Alertas",
        "GET",
        f"{settings.alertas_url}{ALERTAS_SUGERENCIAS}",
        params={"estado": "pendiente"},
    )
    if r.status_code != 200:
        raise HTTPException(502, "Respuesta inesperada del servicio de Alertas")
    return r.json()


def marcar_sugerencia_atendida(sugerencia_id: int, orden_id: int) -> None:
    """Avisa a Alertas que la sugerencia ya generó una orden.
    Es 'mejor esfuerzo': si Alertas no responde, la orden ya creada no se revierte."""
    try:
        httpx.patch(
            f"{settings.alertas_url}{ALERTAS_SUGERENCIAS}/{sugerencia_id}/estado",
            json={"estado": "atendida", "orden_compra_id": orden_id},
            timeout=TIMEOUT,
        )
    except httpx.RequestError:
        logger.warning("No se pudo notificar a Alertas la sugerencia %s", sugerencia_id)


# ---------- Inventario ----------
def _detalle_error(r: httpx.Response) -> str:
    try:
        detalle = r.json().get("detail")
    except (ValueError, AttributeError):
        detalle = None
    return str(detalle) if detalle else r.text[:200]


def registrar_movimiento_inventario(
    *,
    operacion_id: str,
    producto_id: int,
    bodega_id: int,
    tipo: str,
    cantidad: int,
    usuario_id: int | None = None,
) -> dict:
    """Registra una ENTRADA o SALIDA en Inventario.
    Inventario es idempotente por operacion_id: repetir la misma operación no duplica stock."""
    headers = {"X-User-Id": str(usuario_id)} if usuario_id is not None else {}
    r = _llamar(
        "Inventario",
        "POST",
        f"{settings.inventario_url}/api/inventario/movimientos",
        json={
            "operacion_id": operacion_id,
            "producto_id": producto_id,
            "bodega_id": bodega_id,
            "tipo": tipo,
            "cantidad": cantidad,
        },
        headers=headers,
    )
    if r.status_code in (200, 201):
        return r.json()
    if r.status_code == 409:
        raise HTTPException(409, f"Inventario: {_detalle_error(r)}")
    if r.status_code in (400, 404, 422):
        raise HTTPException(422, f"Inventario rechazó la operación: {_detalle_error(r)}")
    raise HTTPException(502, "Respuesta inesperada del servicio de Inventario")


def consultar_disponibilidad(producto_id: int, bodega_id: int, cantidad: int) -> dict:
    """Pregunta a Inventario si hay stock suficiente (devuelve 'disponible' y 'stock_disponible')."""
    r = _llamar(
        "Inventario",
        "GET",
        f"{settings.inventario_url}/api/inventario/disponibilidad",
        params={"producto_id": producto_id, "bodega_id": bodega_id, "cantidad": cantidad},
    )
    if r.status_code == 200:
        return r.json()
    if r.status_code in (400, 404, 422):
        raise HTTPException(422, f"Inventario rechazó la consulta: {_detalle_error(r)}")
    raise HTTPException(502, "Respuesta inesperada del servicio de Inventario")