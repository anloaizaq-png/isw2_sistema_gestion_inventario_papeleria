from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Venta(Base):
    """
    Tabla de ventas y pedidos aislada.
    usuario_id y bodega_id son referencias lógicas a otros servicios.
    """
    __tablename__ = "venta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, nullable=False, index=True)
    bodega_id = Column(Integer, nullable=False, index=True)
    estado = Column(String(50), default="pendiente", nullable=False, index=True)  # pendiente, confirmada, cancelada
    total = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    operacion_id = Column(String(100), unique=True, nullable=True, index=True)

    detalles = relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")
    devoluciones = relationship("Devolucion", back_populates="venta", cascade="all, delete-orphan")


class DetalleVenta(Base):
    """
    Detalle de ítems de la venta.
    producto_id es referencia lógica al microservicio de productos.
    """
    __tablename__ = "detalle_venta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venta_id = Column(Integer, ForeignKey("venta.id", ondelete="CASCADE"), nullable=False, index=True)
    producto_id = Column(Integer, nullable=False, index=True)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)

    venta = relationship("Venta", back_populates="detalles")
    detalles_devolucion = relationship("DetalleDevolucion", back_populates="detalle_venta", cascade="all, delete-orphan")


class Devolucion(Base):
    """
    Devoluciones registradas sobre ventas confirmadas.
    """
    __tablename__ = "devolucion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venta_id = Column(Integer, ForeignKey("venta.id", ondelete="CASCADE"), nullable=False, index=True)
    estado = Column(String(50), default="COMPLETADA", nullable=False)
    motivo = Column(String(255), nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)
    operacion_id = Column(String(100), unique=True, nullable=True, index=True)

    venta = relationship("Venta", back_populates="devoluciones")
    detalles = relationship("DetalleDevolucion", back_populates="devolucion", cascade="all, delete-orphan")


class DetalleDevolucion(Base):
    """
    Ítems devueltos asociados a un detalle_venta específico.
    """
    __tablename__ = "detalle_devolucion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    devolucion_id = Column(Integer, ForeignKey("devolucion.id", ondelete="CASCADE"), nullable=False, index=True)
    detalle_venta_id = Column(Integer, ForeignKey("detalle_venta.id", ondelete="CASCADE"), nullable=False, index=True)
    cantidad = Column(Integer, nullable=False)

    devolucion = relationship("Devolucion", back_populates="detalles")
    detalle_venta = relationship("DetalleVenta", back_populates="detalles_devolucion")
