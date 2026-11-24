import httpx
from fastapi import HTTPException, status
from app.config import settings


async def verificar_disponibilidad_stock(producto_id: int, bodega_id: int, cantidad: int) -> bool:
    """
    Consulta GET {INVENTARIO_URL}/api/inventario/disponibilidad
    para verificar que exista stock suficiente disponible antes de descontar.
    """
    url = f"{settings.INVENTARIO_URL.rstrip('/')}/api/inventario/disponibilidad"
    params = {
        "producto_id": producto_id,
        "bodega_id": bodega_id,
        "cantidad": cantidad,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de Inventario no disponible o sin respuesta al consultar disponibilidad: {str(exc)}",
        )

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error al consultar disponibilidad en Inventario (HTTP {response.status_code})",
        )

    data = response.json()
    return bool(data.get("disponible", False))


async def descontar_stock_inventario(
    operacion_id: str,
    venta_id: int,
    producto_id: int,
    bodega_id: int,
    cantidad: int,
) -> dict:
    """
    Llama a POST {INVENTARIO_URL}/api/inventario/descuentos
    para descontar stock en una venta confirmada.
    """
    url = f"{settings.INVENTARIO_URL.rstrip('/')}/api/inventario/descuentos"
    payload = {
        "operacion_id": operacion_id,
        "venta_id": venta_id,
        "producto_id": producto_id,
        "bodega_id": bodega_id,
        "cantidad": cantidad,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de Inventario no disponible al realizar descuento: {str(exc)}",
        )

    if response.status_code == status.HTTP_409_CONFLICT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stock insuficiente en Inventario para producto {producto_id} en bodega {bodega_id}",
        )

    if response.status_code not in (status.HTTP_200_OK, status.HTTP_201_CREATED):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error al descontar stock en Inventario (HTTP {response.status_code}): {response.text}",
        )

    return response.json()


async def reintegrar_stock_inventario(
    operacion_id: str,
    devolucion_id: int,
    producto_id: int,
    bodega_id: int,
    cantidad: int,
    motivo: str,
) -> dict:
    """
    Llama a POST {INVENTARIO_URL}/api/inventario/devoluciones
    para reintegrar stock por devolución o compensación.
    """
    url = f"{settings.INVENTARIO_URL.rstrip('/')}/api/inventario/devoluciones"
    payload = {
        "operacion_id": operacion_id,
        "devolucion_id": devolucion_id,
        "producto_id": producto_id,
        "bodega_id": bodega_id,
        "cantidad": cantidad,
        "motivo": motivo,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de Inventario no disponible al reintegrar stock: {str(exc)}",
        )

    if response.status_code not in (status.HTTP_200_OK, status.HTTP_201_CREATED):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error al reintegrar stock en Inventario (HTTP {response.status_code}): {response.text}",
        )

    return response.json()
