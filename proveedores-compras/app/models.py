from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    nit: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    contacto_nombre: Mapped[str | None] = mapped_column(String(150), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum("activo", "inactivo", name="estado_proveedor"),
        nullable=False,
        default="activo",
        server_default="activo",
    )
    fecha_registro: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProveedorProducto(Base):
    """Qué productos suministra cada proveedor. producto_id es una referencia
    lógica al servicio de Productos (no hay FK entre bases de datos)."""

    __tablename__ = "proveedor_producto"
    __table_args__ = (
        UniqueConstraint("proveedor_id", "producto_id", name="uq_proveedor_producto"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    proveedor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False
    )
    producto_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_asociacion: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OrdenCompra(Base):
    __tablename__ = "ordenes_compra"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    proveedor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # referencia lógica
    sugerencia_id: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True
    )  # referencia lógica a Alertas
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    estado: Mapped[str] = mapped_column(
        Enum("pendiente", "recibida_parcial", "recibida_total", "cancelada", name="estado_orden"),
        nullable=False,
        default="pendiente",
        server_default="pendiente",
        index=True,
    )
    origen: Mapped[str] = mapped_column(
        Enum("manual", "alerta", name="origen_orden"),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    detalles: Mapped[list["OrdenCompraDetalle"]] = relationship(
        back_populates="orden", order_by="OrdenCompraDetalle.id", cascade="all, delete-orphan"
    )


class OrdenCompraDetalle(Base):
    __tablename__ = "orden_compra_detalle"
    __table_args__ = (
        UniqueConstraint("orden_compra_id", "producto_id", name="uq_orden_producto"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    orden_compra_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ordenes_compra.id", ondelete="RESTRICT"), nullable=False
    )
    producto_id: Mapped[int] = mapped_column(Integer, nullable=False)  # referencia lógica
    cantidad_solicitada: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_recibida: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    cantidad_devuelta: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    orden: Mapped["OrdenCompra"] = relationship(back_populates="detalles")