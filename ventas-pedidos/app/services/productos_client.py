from decimal import Decimal
import httpx
from fastapi import HTTPException, status
from app.config import settings


async def consultar_producto(producto_id: int) -> dict:
    """
    Consulta GET {PRODUCTOS_URL}/api/productos/{producto_id}
    para validar que el producto exista y esté activo,
    además de obtener su precio de venta real.
    Si el microservicio de Productos no responde, retorna 503 controlado.
    """
    url = f"{settings.PRODUCTOS_URL.rstrip('/')}/api/productos/{producto_id}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de Productos no disponible o sin respuesta: {str(exc)}",
        )

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El producto con ID {producto_id} no fue encontrado en el catálogo",
        )

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error inesperado al consultar servicio de Productos (HTTP {response.status_code})",
        )

    data = response.json()
    is_active = True
    if isinstance(data, dict):
        if "activo" in data:
            is_active = bool(data["activo"])
        elif "estado" in data:
            is_active = str(data["estado"]).lower() in ("activo", "active", "1", "true")

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El producto con ID {producto_id} no se encuentra activo",
        )

    # Extraer precio de venta de los campos estándar
    raw_precio = (
        data.get("precioventa")
        or data.get("precio_venta")
        or data.get("precio")
        or 0
    )
    try:
        precio_decimal = Decimal(str(raw_precio))
    except Exception:
        precio_decimal = Decimal("0.00")

    data["_precio_unitario"] = precio_decimal
    return data
