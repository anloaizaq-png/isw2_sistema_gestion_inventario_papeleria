from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# Bodega schemas
class BodegaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=255, description="Nombre de la bodega")
    ubicacion: str = Field(..., min_length=1, max_length=255, description="Ubicación física de la bodega")
    activa: bool = Field(default=True, description="Estado de la bodega (activa o inactiva)")


class BodegaCreate(BodegaBase):
    pass


class BodegaResponse(BodegaBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Existencia schemas
class ExistenciaResponse(BaseModel):
    id: int
    producto_id: int
    bodega_id: int
    cantidad: int
    cantidad_reservada: int
    stock_minimo: int

    model_config = ConfigDict(from_attributes=True)


class DisponibilidadResponse(BaseModel):
    disponible: bool
    producto_id: int
    bodega_id: int
    cantidad_solicitada: int
    stock_disponible: int
    cantidad: int
    cantidad_reservada: int


# Movimiento schemas
class MovimientoCreate(BaseModel):
    operacion_id: str = Field(..., min_length=1, max_length=100, description="Identificador único para idempotencia")
    producto_id: int = Field(..., gt=0, description="ID lógico del producto")
    bodega_id: int = Field(..., gt=0, description="ID de la bodega")
    tipo: str = Field(..., min_length=1, max_length=50, description="Tipo de movimiento (ENTRADA, AJUSTE, etc.)")
    cantidad: int = Field(..., gt=0, description="Cantidad de unidades a ingresar o ajustar")
    usuario_id: Optional[int] = Field(default=None, description="ID lógico del usuario (opcional si viene en X-User-Id)")


class MovimientoResponse(BaseModel):
    id: int
    existencia_id: int
    bodega_id: int
    traslado_id: Optional[int] = None
    operacion_id: str
    tipo: str
    cantidad: int
    usuario_id: Optional[int] = None
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


# Descuento schemas
class DescuentoRequest(BaseModel):
    operacion_id: str = Field(..., min_length=1, max_length=100, description="Identificador único de la operación para idempotencia")
    venta_id: Optional[int] = Field(default=None, description="ID lógico de la venta asociada")
    producto_id: int = Field(..., gt=0, description="ID lógico del producto")
    bodega_id: int = Field(..., gt=0, description="ID de la bodega")
    cantidad: int = Field(..., gt=0, description="Cantidad de unidades a descontar")


class DescuentoResponse(BaseModel):
    mensaje: str
    operacion_id: str
    venta_id: Optional[int] = None
    producto_id: int
    bodega_id: int
    cantidad_descontada: int
    nuevo_stock: int
    idempotente: bool = False


# Devolucion schemas
class DevolucionRequest(BaseModel):
    operacion_id: str = Field(..., min_length=1, max_length=100, description="Identificador único para idempotencia")
    devolucion_id: Optional[int] = Field(default=None, description="ID lógico de la devolución asociada")
    producto_id: int = Field(..., gt=0, description="ID lógico del producto")
    bodega_id: int = Field(..., gt=0, description="ID de la bodega")
    cantidad: int = Field(..., gt=0, description="Cantidad de unidades a reintegrar")
    motivo: Optional[str] = Field(default=None, max_length=255, description="Motivo de la devolución")


class DevolucionResponse(BaseModel):
    mensaje: str
    operacion_id: str
    devolucion_id: Optional[int] = None
    producto_id: int
    bodega_id: int
    cantidad_reintegrada: int
    nuevo_stock: int
    idempotente: bool = False


# Traslado schemas
class TrasladoRequest(BaseModel):
    producto_id: int = Field(..., gt=0, description="ID lógico del producto")
    bodega_origen_id: int = Field(..., gt=0, description="ID de la bodega de origen")
    bodega_destino_id: int = Field(..., gt=0, description="ID de la bodega de destino")
    cantidad: int = Field(..., gt=0, description="Cantidad a trasladar")
    usuario_id: Optional[int] = Field(default=None, description="ID lógico del usuario")
    operacion_id: Optional[str] = Field(default=None, max_length=100, description="ID de operación para idempotencia")


class TrasladoResponse(BaseModel):
    mensaje: str
    traslado_id: int
    operacion_id: str
    producto_id: int
    bodega_origen_id: int
    bodega_destino_id: int
    cantidad: int
    stock_origen: int
    stock_destino: int
    idempotente: bool = False
