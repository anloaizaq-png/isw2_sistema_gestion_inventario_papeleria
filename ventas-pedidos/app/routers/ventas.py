from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.inventario_client import (
    descontar_stock_inventario,
    reintegrar_stock_inventario,
    verificar_disponibilidad_stock,
)
from app.services.productos_client import consultar_producto

router = APIRouter(prefix="/api/ventas", tags=["ventas"])


@router.get("", response_model=List[schemas.VentaResponse], status_code=status.HTTP_200_OK)
def listar_ventas(
    estado: Optional[str] = Query(None, description="Filtro opcional por estado (pendiente, confirmada, cancelada)"),
    fecha_inicio: Optional[datetime] = Query(None, description="Filtro opcional por fecha inicial"),
    fecha_fin: Optional[datetime] = Query(None, description="Filtro opcional por fecha final"),
    db: Session = Depends(get_db),
):
    """
    Lista ventas con filtros opcionales estado, fecha_inicio, fecha_fin.
    """
    query = db.query(models.Venta)
    if estado:
        query = query.filter(models.Venta.estado == estado.lower())
    if fecha_inicio:
        query = query.filter(models.Venta.fecha >= fecha_inicio)
    if fecha_fin:
        query = query.filter(models.Venta.fecha <= fecha_fin)
    return query.order_by(models.Venta.fecha.desc()).all()


@router.post("", response_model=schemas.VentaResponse, status_code=status.HTTP_201_CREATED)
async def crear_venta(
    payload: schemas.VentaCreate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    """
    Crea pedido en estado 'pendiente'.
    Consulta cada producto en PRODUCTOS_URL para validar que esté activo y
    obtener su precioventa real, calculando subtotal y total.
    """
    usuario_id = payload.usuario_id or x_user_id
    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere usuario_id en el cuerpo o cabecera X-User-Id",
        )

    if not payload.detalles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El pedido debe incluir al menos un detalle de producto",
        )

    total_acumulado = Decimal("0.00")
    detalles_calculados = []

    for item in payload.detalles:
        producto_data = await consultar_producto(item.producto_id)
        precio_unitario = producto_data["_precio_unitario"]
        subtotal = precio_unitario * Decimal(str(item.cantidad))
        total_acumulado += subtotal

        detalles_calculados.append({
            "producto_id": item.producto_id,
            "cantidad": item.cantidad,
            "precio_unitario": precio_unitario,
            "subtotal": subtotal,
        })

    try:
        nueva_venta = models.Venta(
            usuario_id=usuario_id,
            bodega_id=payload.bodega_id,
            estado="pendiente",
            total=total_acumulado,
            fecha=datetime.utcnow(),
        )
        db.add(nueva_venta)
        db.flush()

        for d in detalles_calculados:
            detalle = models.DetalleVenta(
                venta_id=nueva_venta.id,
                producto_id=d["producto_id"],
                cantidad=d["cantidad"],
                precio_unitario=d["precio_unitario"],
                subtotal=d["subtotal"],
            )
            db.add(detalle)

        db.commit()
        db.refresh(nueva_venta)
        return nueva_venta
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar la venta: {str(exc)}",
        )


@router.get("/{id}", response_model=schemas.VentaResponse, status_code=status.HTTP_200_OK)
def consultar_venta(id: int, db: Session = Depends(get_db)):
    """
    Consulta venta con sus detalles por ID.
    """
    venta = db.query(models.Venta).filter(models.Venta.id == id).first()
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venta con ID {id} no encontrada",
        )
    return venta


@router.post("/{id}/confirmacion", response_model=schemas.ConfirmacionResponse, status_code=status.HTTP_200_OK)
async def confirmar_venta(
    id: int,
    payload: schemas.ConfirmacionRequest,
    db: Session = Depends(get_db),
):
    """
    Confirma una venta en estado 'pendiente' validando stock y descontando en Inventario.
    Idempotente con operacion_id. En caso de fallo por stock insuficiente, revierte/compensa.
    """
    venta = db.query(models.Venta).filter(models.Venta.id == id).with_for_update().first()
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venta con ID {id} no encontrada",
        )

    # 1. Idempotencia y validación de estado
    if venta.estado == "confirmada":
        if venta.operacion_id == payload.operacion_id:
            return schemas.ConfirmacionResponse(
                mensaje="Venta ya confirmada previamente (idempotencia)",
                venta_id=venta.id,
                estado=venta.estado,
                operacion_id=payload.operacion_id,
                total=venta.total,
                idempotente=True,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La venta ya ha sido confirmada con otra operación",
        )

    if venta.estado == "cancelada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede confirmar una venta en estado cancelada",
        )

    if venta.estado != "pendiente":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La venta no está pendiente para confirmación (estado: {venta.estado})",
        )

    # 2. Consultar disponibilidad previa de stock en inventario
    for detalle in venta.detalles:
        disponible = await verificar_disponibilidad_stock(
            producto_id=detalle.producto_id,
            bodega_id=venta.bodega_id,
            cantidad=detalle.cantidad,
        )
        if not disponible:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente para producto {detalle.producto_id} en bodega {venta.bodega_id}",
            )

    # 3. Descontar stock ítem por ítem en inventario con compensación ante fallos
    descuentos_completados = []
    try:
        for detalle in venta.detalles:
            op_item = f"{payload.operacion_id}-item-{detalle.id}"
            await descontar_stock_inventario(
                operacion_id=op_item,
                venta_id=venta.id,
                producto_id=detalle.producto_id,
                bodega_id=venta.bodega_id,
                cantidad=detalle.cantidad,
            )
            descuentos_completados.append((detalle, op_item))
    except Exception as exc:
        # Revertir/compensar ítems ya descontados
        for det_prev, op_prev in descuentos_completados:
            compensa_op = f"reversion-{op_prev}"
            try:
                await reintegrar_stock_inventario(
                    operacion_id=compensa_op,
                    devolucion_id=0,
                    producto_id=det_prev.producto_id,
                    bodega_id=venta.bodega_id,
                    cantidad=det_prev.cantidad,
                    motivo="Compensación automática por fallo durante confirmación de venta",
                )
            except Exception:
                pass

        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Fallo al descontar stock en inventario: {str(exc)}. Operaciones revertidas.",
        )

    # 4. Transicionar estado a confirmada
    venta.estado = "confirmada"
    venta.operacion_id = payload.operacion_id
    db.commit()
    db.refresh(venta)

    return schemas.ConfirmacionResponse(
        mensaje="Venta confirmada y stock descontado con éxito",
        venta_id=venta.id,
        estado=venta.estado,
        operacion_id=payload.operacion_id,
        total=venta.total,
        idempotente=False,
    )


@router.post("/{id}/cancelacion", response_model=schemas.CancelacionResponse, status_code=status.HTTP_200_OK)
def cancelar_venta(
    id: int,
    payload: schemas.CancelacionRequest,
    db: Session = Depends(get_db),
):
    """
    Cancela un pedido si está en estado 'pendiente'.
    Si ya estaba 'confirmada' o 'cancelada', retorna 409 Conflict.
    """
    venta = db.query(models.Venta).filter(models.Venta.id == id).with_for_update().first()
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venta con ID {id} no encontrada",
        )

    if venta.estado != "pendiente":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede cancelar la venta: estado actual '{venta.estado}'",
        )

    venta.estado = "cancelada"
    db.commit()
    db.refresh(venta)

    return schemas.CancelacionResponse(
        mensaje="Venta cancelada exitosamente",
        venta_id=venta.id,
        estado=venta.estado,
        motivo=payload.motivo,
    )


@router.post("/{id}/devoluciones", response_model=schemas.DevolucionResponse, status_code=status.HTTP_201_CREATED)
async def registrar_devolucion(
    id: int,
    payload: schemas.DevolucionCreate,
    db: Session = Depends(get_db),
):
    """
    Registra devolución sobre venta confirmada.
    Valida que la suma acumulada de devoluciones no supere la cantidad vendida.
    Llama a POST {INVENTARIO_URL}/api/inventario/devoluciones para reintegrar el stock.
    Idempotente con operacion_id.
    """
    # 1. Idempotencia: Verificar si operacion_id ya existe
    dev_existente = (
        db.query(models.Devolucion)
        .filter(models.Devolucion.operacion_id == payload.operacion_id)
        .first()
    )
    if dev_existente:
        return dev_existente

    venta = db.query(models.Venta).filter(models.Venta.id == id).with_for_update().first()
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venta con ID {id} no encontrada",
        )

    if venta.estado != "confirmada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Solo se pueden registrar devoluciones sobre ventas confirmadas (estado actual: '{venta.estado}')",
        )

    # 2. Validar detalles y cantidades acumuladas
    detalles_dict = {d.id: d for d in venta.detalles}
    for item in payload.detalles:
        if item.detalle_venta_id not in detalles_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El detalle_venta {item.detalle_venta_id} no pertenece a la venta {id}",
            )
        det_v = detalles_dict[item.detalle_venta_id]

        total_devuelto = (
            db.query(func.coalesce(func.sum(models.DetalleDevolucion.cantidad), 0))
            .filter(models.DetalleDevolucion.detalle_venta_id == item.detalle_venta_id)
            .scalar()
        )
        if total_devuelto + item.cantidad > det_v.cantidad:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cantidad acumulada a devolver ({total_devuelto + item.cantidad}) "
                    f"supera la cantidad vendida ({det_v.cantidad}) para el detalle {item.detalle_venta_id}"
                ),
            )

    # 3. Registrar devolución en la base de datos
    try:
        devolucion = models.Devolucion(
            venta_id=venta.id,
            estado="COMPLETADA",
            motivo=payload.motivo,
            operacion_id=payload.operacion_id,
            fecha=datetime.utcnow(),
        )
        db.add(devolucion)
        db.flush()

        for item in payload.detalles:
            d_dev = models.DetalleDevolucion(
                devolucion_id=devolucion.id,
                detalle_venta_id=item.detalle_venta_id,
                cantidad=item.cantidad,
            )
            db.add(d_dev)

        # 4. Reintegrar stock en inventario vía HTTPX
        for item in payload.detalles:
            det_v = detalles_dict[item.detalle_venta_id]
            op_reintegro = f"{payload.operacion_id}-item-{item.detalle_venta_id}"
            await reintegrar_stock_inventario(
                operacion_id=op_reintegro,
                devolucion_id=devolucion.id,
                producto_id=det_v.producto_id,
                bodega_id=venta.bodega_id,
                cantidad=item.cantidad,
                motivo=payload.motivo or "Devolución de venta",
            )

        db.commit()
        db.refresh(devolucion)
        return devolucion
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        dev = (
            db.query(models.Devolucion)
            .filter(models.Devolucion.operacion_id == payload.operacion_id)
            .first()
        )
        if dev:
            return dev
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto de integridad en devolución",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando devolución: {str(exc)}",
        )


@router.get("/{id}/devoluciones", response_model=List[schemas.DevolucionResponse], status_code=status.HTTP_200_OK)
def listar_devoluciones_venta(id: int, db: Session = Depends(get_db)):
    """
    Lista las devoluciones registradas para una venta específica.
    """
    venta = db.query(models.Venta).filter(models.Venta.id == id).first()
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venta con ID {id} no encontrada",
        )
    return db.query(models.Devolucion).filter(models.Devolucion.venta_id == id).all()
