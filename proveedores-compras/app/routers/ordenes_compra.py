from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.clients import (
    exigir_producto_activo,
    listar_sugerencias_pendientes,
    marcar_sugerencia_atendida,
)
from app.database import get_db
from app.models import OrdenCompra, OrdenCompraDetalle, Proveedor
from app.schemas import EstadoOrden, OrdenCompraCreate, OrdenCompraOut

router = APIRouter(prefix="/api/compras/ordenes-compra", tags=["Órdenes de compra"])


def _get_or_404(db: Session, orden_id: int) -> OrdenCompra:
    orden = db.get(OrdenCompra, orden_id)
    if orden is None:
        raise HTTPException(404, "Orden de compra no encontrada")
    return orden


@router.post("", response_model=OrdenCompraOut, status_code=201)
def crear_orden(
    datos: OrdenCompraCreate,
    x_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    proveedor = db.get(Proveedor, datos.proveedor_id)
    if proveedor is None or proveedor.estado != "activo":
        raise HTTPException(422, "El proveedor no existe o está inactivo")

    ids = [d.producto_id for d in datos.detalles]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "No se puede repetir un producto en la misma orden")

    if datos.sugerencia_id is not None:
        ya_usada = db.scalars(
            select(OrdenCompra.id).where(OrdenCompra.sugerencia_id == datos.sugerencia_id)
        ).first()
        if ya_usada is not None:
            raise HTTPException(409, "Esa sugerencia ya generó una orden de compra")

    for producto_id in ids:
        exigir_producto_activo(producto_id)  # consulta a Productos

    # El total lo calcula el servidor, nunca se acepta del cliente
    total = sum((d.cantidad * d.precio_unitario for d in datos.detalles), Decimal("0"))

    orden = OrdenCompra(
        proveedor_id=datos.proveedor_id,
        usuario_id=x_user_id,
        sugerencia_id=datos.sugerencia_id,
        origen="alerta" if datos.sugerencia_id is not None else "manual",
        estado="pendiente",
        total=total,
    )
    orden.detalles = [
        OrdenCompraDetalle(
            producto_id=d.producto_id,
            cantidad_solicitada=d.cantidad,
            precio_unitario=d.precio_unitario,
        )
        for d in datos.detalles
    ]
    try:
        db.add(orden)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Esa sugerencia ya generó una orden de compra")
    db.refresh(orden)

    if datos.sugerencia_id is not None:
        marcar_sugerencia_atendida(datos.sugerencia_id, orden.id)
    return orden


@router.get("", response_model=list[OrdenCompraOut])
def listar_ordenes(
    estado: EstadoOrden | None = None,
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
):
    consulta = select(OrdenCompra).options(selectinload(OrdenCompra.detalles))
    if estado is not None:
        consulta = consulta.where(OrdenCompra.estado == estado)
    if proveedor_id is not None:
        consulta = consulta.where(OrdenCompra.proveedor_id == proveedor_id)
    return db.scalars(consulta.order_by(OrdenCompra.id.desc())).all()


# Debe ir ANTES de /{orden_id}
@router.get("/sugeridas")
def listar_sugeridas():
    """Sugerencias de reabastecimiento pendientes (vienen del servicio de Alertas)."""
    return listar_sugerencias_pendientes()


@router.get("/{orden_id}", response_model=OrdenCompraOut)
def obtener_orden(orden_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, orden_id)


@router.put("/{orden_id}/cancelar", response_model=OrdenCompraOut)
def cancelar_orden(orden_id: int, db: Session = Depends(get_db)):
    orden = _get_or_404(db, orden_id)
    if orden.estado != "pendiente":
        raise HTTPException(409, f"Solo se puede cancelar una orden pendiente (estado actual: {orden.estado})")
    orden.estado = "cancelada"
    db.commit()
    db.refresh(orden)
    return orden