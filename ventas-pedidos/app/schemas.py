from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# Modelos para ítems de venta
class ItemPedidoCreate(BaseModel):
    producto_id: int = Field(..., gt=0, description="ID lógico del producto")
    cantidad: int = Field(..., gt=0, description="Cantidad a ordenar")


class DetalleVentaResponse(BaseModel):
    id: int
    venta_id: int
    producto_id: int
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


# Modelos para Venta
class VentaCreate(BaseModel):
    usuario_id: Optional[int] = Field(default=None, description="ID del usuario (opcional si viene en X-User-Id)")
    bodega_id: int = Field(..., gt=0, description="ID de la bodega de despacho")
    detalles: List[ItemPedidoCreate] = Field(..., min_length=1, description="Lista de productos y cantidades")


class VentaResponse(BaseModel):
    id: int
    usuario_id: int
    bodega_id: int
    estado: str
    total: Decimal
    fecha: datetime
    operacion_id: Optional[str] = None
    detalles: List[DetalleVentaResponse] = []

    model_config = ConfigDict(from_attributes=True)


# Modelos para Confirmación y Cancelación
class ConfirmacionRequest(BaseModel):
    operacion_id: str = Field(..., min_length=1, max_length=100, description="Identificador único para idempotencia")


class ConfirmacionResponse(BaseModel):
    mensaje: str
    venta_id: int
    estado: str
    operacion_id: str
    total: Decimal
    idempotente: bool = False


class CancelacionRequest(BaseModel):
    motivo: Optional[str] = Field(default=None, max_length=255, description="Motivo de la cancelación")


class CancelacionResponse(BaseModel):
    mensaje: str
    venta_id: int
    estado: str
    motivo: Optional[str] = None


# Modelos para Devoluciones
class ItemDevolucionCreate(BaseModel):
    detalle_venta_id: int = Field(..., gt=0, description="ID del detalle_venta a devolver")
    cantidad: int = Field(..., gt=0, description="Cantidad de unidades a devolver")


class DevolucionCreate(BaseModel):
    operacion_id: str = Field(..., min_length=1, max_length=100, description="Identificador único de la operación")
    motivo: Optional[str] = Field(default="Devolución de cliente", max_length=255, description="Motivo de la devolución")
    detalles: List[ItemDevolucionCreate] = Field(..., min_length=1, description="Detalles de los productos a devolver")


class DetalleDevolucionResponse(BaseModel):
    id: int
    devolucion_id: int
    detalle_venta_id: int
    cantidad: int

    model_config = ConfigDict(from_attributes=True)


class DevolucionResponse(BaseModel):
    id: int
    venta_id: int
    estado: str
    motivo: Optional[str] = None
    fecha: datetime
    operacion_id: Optional[str] = None
    detalles: List[DetalleDevolucionResponse] = []

    model_config = ConfigDict(from_attributes=True)
