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