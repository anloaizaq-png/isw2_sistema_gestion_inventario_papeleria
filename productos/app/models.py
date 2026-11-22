from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = (
        UniqueConstraint("nombre", "categoria_padre_id", name="uq_categoria_nombre_padre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria_padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("categoria.id", ondelete="RESTRICT"), nullable=True
    )


class Producto(Base):
    __tablename__ = "producto"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    codigo_barras: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    categoria_id: Mapped[int | None] = mapped_column(
        ForeignKey("categoria.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unidad_medida: Mapped[str | None] = mapped_column(String(30), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(100), nullable=True)
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Referencia lógica al proveedor (vive en la BD de Compras, sin FK)
    proveedor_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    estado: Mapped[str] = mapped_column(
        Enum("activo", "inactivo", name="estado_producto"),
        nullable=False,
        default="activo",
        server_default="activo",
        index=True,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    categoria: Mapped[Categoria | None] = relationship()