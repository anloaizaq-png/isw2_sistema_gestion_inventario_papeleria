from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

Estado = Literal["activo", "inactivo"]
EstadoOrden = Literal["pendiente", "recibida_parcial", "recibida_total", "cancelada"]

NIT_PATTERN = r"^\d{6,12}(-\d)?$"  # ej: 900123456-7
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ---------- Proveedores ----------
class ProveedorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=150)
    nit: str = Field(pattern=NIT_PATTERN, max_length=30)
    contacto_nombre: str | None = Field(default=None, max_length=150)
    telefono: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=150, pattern=EMAIL_PATTERN)
    direccion: str | None = Field(default=None, max_length=200)
    estado: Estado = "activo"


class ProveedorUpdate(ProveedorCreate):
    """PUT: reemplaza todos los campos editables."""


class ProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    nit: str
    contacto_nombre: str | None
    telefono: str | None
    email: str | None
    direccion: str | None
    estado: Estado
    fecha_registro: datetime


# ---------- Proveedor-Producto ----------
class AsociarProducto(BaseModel):
    producto_id: int = Field(gt=0)


class ProveedorProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proveedor_id: int
    producto_id: int
    fecha_asociacion: datetime


# ---------- Órdenes de compra ----------
# Se devuelve como número JSON (por defecto pydantic serializaría Decimal como texto)
Precio = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=2),
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]
Total = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


class DetalleCreate(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)
    precio_unitario: Precio


class OrdenCompraCreate(BaseModel):
    proveedor_id: int = Field(gt=0)
    detalles: list[DetalleCreate] = Field(min_length=1)
    sugerencia_id: int | None = Field(default=None, gt=0)


class DetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    producto_id: int
    cantidad_solicitada: int
    cantidad_recibida: int
    cantidad_devuelta: int
    precio_unitario: Precio


class OrdenCompraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proveedor_id: int
    usuario_id: int | None
    sugerencia_id: int | None
    fecha_creacion: datetime
    estado: EstadoOrden
    origen: Literal["manual", "alerta"]
    total: Total
    detalles: list[DetalleOut]


# ---------- Recepción ----------
class LineaRecepcion(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class RecepcionCreate(BaseModel):
    bodega_id: int = Field(gt=0)
    productos_recibidos: list[LineaRecepcion] = Field(min_length=1)


# ---------- Devoluciones a proveedor ----------
class LineaDevolucion(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class DevolucionProveedorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    orden_compra_id: int = Field(gt=0)
    bodega_id: int = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=255)
    productos: list[LineaDevolucion] = Field(min_length=1)


class DevolucionDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    producto_id: int
    cantidad: int


class DevolucionProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    orden_compra_id: int
    proveedor_id: int
    bodega_id: int
    usuario_id: int | None
    motivo: str
    fecha: datetime
    detalles: list[DevolucionDetalleOut]