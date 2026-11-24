from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Bodega(Base):
    """
    Tabla de bodegas de almacenamiento.
    """
    __tablename__ = "bodega"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(255), nullable=False)
    ubicacion = Column(String(255), nullable=False)
    activa = Column(Boolean, default=True, nullable=False)

    existencias = relationship("Existencia", back_populates="bodega", cascade="all, delete-orphan")
    movimientos = relationship("Movimiento", back_populates="bodega")


class Existencia(Base):
    """
    Tabla de existencias por producto y bodega con restricción única (producto_id, bodega_id).
    Sin llaves foráneas a otros servicios (producto_id es referencia lógica).
    """
    __tablename__ = "existencia"

    id = Column(Integer, primary_key=True, autoincrement=True)
    producto_id = Column(Integer, nullable=False, index=True)
    bodega_id = Column(Integer, ForeignKey("bodega.id", ondelete="CASCADE"), nullable=False, index=True)
    cantidad = Column(Integer, default=0, nullable=False)
    cantidad_reservada = Column(Integer, default=0, nullable=False)
    stock_minimo = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("producto_id", "bodega_id", name="uq_existencia_producto_bodega"),
    )

    bodega = relationship("Bodega", back_populates="existencias")
    movimientos = relationship("Movimiento", back_populates="existencia")


class Traslado(Base):
    """
    Tabla de traslados de existencias entre bodegas.
    origen_id y destino_id son referencias lógicas a bodegas.
    """
    __tablename__ = "traslado"

    id = Column(Integer, primary_key=True, autoincrement=True)
    producto_id = Column(Integer, nullable=False, index=True)
    origen_id = Column(Integer, nullable=False, index=True)
    destino_id = Column(Integer, nullable=False, index=True)
    cantidad = Column(Integer, nullable=False)
    estado = Column(String(50), default="COMPLETADO", nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)

    movimientos = relationship("Movimiento", back_populates="traslado")


class Movimiento(Base):
    """
    Tabla de movimientos de inventario con operacion_id único para idempotencia.
    traslado_id es opcional (nullable=True).
    usuario_id es referencia lógica al usuario.
    """
    __tablename__ = "movimiento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    existencia_id = Column(Integer, ForeignKey("existencia.id", ondelete="RESTRICT"), nullable=False, index=True)
    bodega_id = Column(Integer, ForeignKey("bodega.id", ondelete="RESTRICT"), nullable=False, index=True)
    traslado_id = Column(Integer, ForeignKey("traslado.id", ondelete="SET NULL"), nullable=True, index=True)
    operacion_id = Column(String(100), unique=True, nullable=False, index=True)
    tipo = Column(String(50), nullable=False)
    cantidad = Column(Integer, nullable=False)
    usuario_id = Column(Integer, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)

    existencia = relationship("Existencia", back_populates="movimientos")
    bodega = relationship("Bodega", back_populates="movimientos")
    traslado = relationship("Traslado", back_populates="movimientos")
