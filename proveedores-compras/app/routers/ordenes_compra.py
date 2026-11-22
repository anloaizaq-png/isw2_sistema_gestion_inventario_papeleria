from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.clients import (
    exigir_producto_activo,
    listar_sugerencias_pendientes,
    marcar_sugerencia_atendida,
    registrar_movimiento_inventario,
)
from app.database import get_db
from app.models import OrdenCompra, OrdenCompraDetalle, Proveedor
from app.schemas import EstadoOrden, OrdenCompraCreate, OrdenCompraOut, RecepcionCreate

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


@router.put("/{orden_id}/recibir", response_model=OrdenCompraOut)
def recibir_orden(
    orden_id: int,
    datos: RecepcionCreate,
    x_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Se bloquea la fila de la orden: dos recepciones simultáneas no pueden superar lo solicitado
    orden = db.scalars(
        select(OrdenCompra).where(OrdenCompra.id == orden_id).with_for_update()
    ).first()
    if orden is None:
        raise HTTPException(404, "Orden de compra no encontrada")
    if orden.estado in ("cancelada", "recibida_total"):
        raise HTTPException(409, f"No se puede recibir una orden en estado {orden.estado}")

    detalles = {d.producto_id: d for d in orden.detalles}
    vistos = set()
    for linea in datos.productos_recibidos:
        if linea.producto_id in vistos:
            raise HTTPException(422, f"El producto {linea.producto_id} está repetido en la recepción")
        vistos.add(linea.producto_id)
        detalle = detalles.get(linea.producto_id)
        if detalle is None:
            raise HTTPException(422, f"El producto {linea.producto_id} no pertenece a la orden")
        pendiente = detalle.cantidad_solicitada - detalle.cantidad_recibida
        if linea.cantidad > pendiente:
            raise HTTPException(
                422, f"Producto {linea.producto_id}: se reciben {linea.cantidad} y solo faltan {pendiente}"
            )

    # Entradas en Inventario. El operacion_id es siempre el mismo para la misma recepción,
    # así que si algo falla y se reintenta, Inventario no duplica el stock.
    for linea in datos.productos_recibidos:
        detalle = detalles[linea.producto_id]
        registrar_movimiento_inventario(
            operacion_id=f"compra-{orden.id}-{linea.producto_id}-{detalle.cantidad_recibida}",
            producto_id=linea.producto_id,
            bodega_id=datos.bodega_id,
            tipo="ENTRADA",
            cantidad=linea.cantidad,
            usuario_id=x_user_id,
        )

    # Solo si Inventario aceptó todas las entradas se actualiza la orden
    for linea in datos.productos_recibidos:
        detalles[linea.producto_id].cantidad_recibida += linea.cantidad
    todo_recibido = all(d.cantidad_recibida == d.cantidad_solicitada for d in orden.detalles)
    orden.estado = "recibida_total" if todo_recibido else "recibida_parcial"
    db.commit()
    db.refresh(orden)
    return orden