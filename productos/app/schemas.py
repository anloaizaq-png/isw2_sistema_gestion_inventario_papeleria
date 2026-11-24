from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# Precio: se recibe como decimal con 2 decimales y se devuelve como número JSON
# (por defecto pydantic lo devolvería como texto y los otros servicios esperan número)
Precio = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=2),
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]

Estado = Literal["activo", "inactivo"]


# ---------- Categorías ----------
class CategoriaBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=100)
    categoria_padre_id: int | None = None


class CategoriaCreate(CategoriaBase):
    pass


class CategoriaUpdate(CategoriaBase):
    pass


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    categoria_padre_id: int | None


# ---------- Productos ----------
class ProductoCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    codigo: str = Field(min_length=1, max_length=50)
    codigo_barras: str | None = Field(default=None, max_length=50)
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: str | None = None
    categoria_id: int | None = None
    unidad_medida: str | None = Field(default=None, max_length=30)
    marca: str | None = Field(default=None, max_length=100)
    precio_venta: Precio
    proveedor_id: int | None = None
    estado: Estado = "activo"


class ProductoUpdate(ProductoCreate):
    """PUT: reemplaza todos los campos editables."""


class ProductoPatch(BaseModel):
    """PATCH: solo los campos enviados."""

    model_config = ConfigDict(str_strip_whitespace=True)

    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    codigo_barras: str | None = Field(default=None, max_length=50)
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    descripcion: str | None = None
    categoria_id: int | None = None
    unidad_medida: str | None = Field(default=None, max_length=30)
    marca: str | None = Field(default=None, max_length=100)
    precio_venta: Precio | None = None
    proveedor_id: int | None = None
    estado: Estado | None = None


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    codigo_barras: str | None
    nombre: str
    descripcion: str | None
    categoria_id: int | None
    unidad_medida: str | None
    marca: str | None
    precio_venta: Precio
    proveedor_id: int | None
    estado: Estado
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    

class ProductoPagina(BaseModel):
    page: int
    limit: int
    total: int
    data: list[ProductoOut]