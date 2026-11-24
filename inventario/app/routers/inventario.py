import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.productos_client import verificar_producto_activo

router = APIRouter(prefix="/api/inventario", tags=["inventario"])


@router.get("/stock", response_model=List[schemas.ExistenciaResponse], status_code=status.HTTP_200_OK)
def consultar_stock(
    producto_id: Optional[int] = Query(None, description="Filtro opcional por ID de producto"),
    bodega_id: Optional[int] = Query(None, description="Filtro opcional por ID de bodega"),
    db: Session = Depends(get_db),
):
    """
    Consulta existencias con filtros opcionales producto_id y bodega_id.
    """
    query = db.query(models.Existencia)
    if producto_id is not None:
        query = query.filter(models.Existencia.producto_id == producto_id)
    if bodega_id is not None:
        query = query.filter(models.Existencia.bodega_id == bodega_id)
    return query.all()


@router.get("/disponibilidad", response_model=schemas.DisponibilidadResponse, status_code=status.HTTP_200_OK)
def verificar_disponibilidad(
    producto_id: int = Query(..., description="ID del producto a verificar"),
    bodega_id: int = Query(..., description="ID de la bodega a consultar"),
    cantidad: int = Query(..., gt=0, description="Cantidad requerida a verificar"),
    db: Session = Depends(get_db),
):
    """
    Verifica si cantidad - cantidad_reservada >= cantidad solicitada.
    """
    existencia = (
        db.query(models.Existencia)
        .filter(
            models.Existencia.producto_id == producto_id,
            models.Existencia.bodega_id == bodega_id,
        )
        .first()
    )

    if not existencia:
        return schemas.DisponibilidadResponse(
            disponible=False,
            producto_id=producto_id,
            bodega_id=bodega_id,
            cantidad_solicitada=cantidad,
            stock_disponible=0,
            cantidad=0,
            cantidad_reservada=0,
        )

    stock_disponible = existencia.cantidad - existencia.cantidad_reservada
    disponible = stock_disponible >= cantidad

    return schemas.DisponibilidadResponse(
        disponible=disponible,
        producto_id=producto_id,
        bodega_id=bodega_id,
        cantidad_solicitada=cantidad,
        stock_disponible=max(0, stock_disponible),
        cantidad=existencia.cantidad,
        cantidad_reservada=existencia.cantidad_reservada,
    )


@router.get("/bodegas", response_model=List[schemas.BodegaResponse], status_code=status.HTTP_200_OK)
def listar_bodegas(db: Session = Depends(get_db)):
    """
    Lista todas las bodegas registradas.
    """
    return db.query(models.Bodega).all()


@router.post("/bodegas", response_model=schemas.BodegaResponse, status_code=status.HTTP_201_CREATED)
def crear_bodega(payload: schemas.BodegaCreate, db: Session = Depends(get_db)):
    """
    Crea una nueva bodega.
    """
    bodega = models.Bodega(
        nombre=payload.nombre,
        ubicacion=payload.ubicacion,
        activa=payload.activa,
    )
    db.add(bodega)
    db.commit()
    db.refresh(bodega)
    return bodega


@router.get("/movimientos", response_model=List[schemas.MovimientoResponse], status_code=status.HTTP_200_OK)
def listar_movimientos(
    producto_id: Optional[int] = Query(None, description="Filtro opcional por ID de producto"),
    bodega_id: Optional[int] = Query(None, description="Filtro opcional por ID de bodega"),
    tipo: Optional[str] = Query(None, description="Filtro opcional por tipo de movimiento"),
    fecha: Optional[datetime] = Query(None, description="Filtro opcional por fecha"),
    db: Session = Depends(get_db),
):
    """
    Historial de movimientos con filtros opcionales.
    """
    query = db.query(models.Movimiento)
    if producto_id is not None:
        query = query.join(models.Existencia).filter(models.Existencia.producto_id == producto_id)
    if bodega_id is not None:
        query = query.filter(models.Movimiento.bodega_id == bodega_id)
    if tipo is not None:
        query = query.filter(models.Movimiento.tipo == tipo)
    if fecha is not None:
        query = query.filter(func.date(models.Movimiento.fecha) == fecha.date())
    return query.order_by(models.Movimiento.fecha.desc()).all()


@router.post("/movimientos", response_model=schemas.MovimientoResponse, status_code=status.HTTP_201_CREATED)
async def registrar_movimiento(
    payload: schemas.MovimientoCreate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    """
    Registra entradas y ajustes autorizados de inventario.
    Valida producto con Productos antes de registrar movimientos iniciales.
    Idempotente con base en operacion_id.
    """
    usuario_id = payload.usuario_id or x_user_id

    # 1. Idempotencia: Verificar operacion_id única
    movimiento_existente = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.operacion_id == payload.operacion_id)
        .first()
    )
    if movimiento_existente:
        return movimiento_existente

    # 2. Validación de producto en servicio Productos
    await verificar_producto_activo(payload.producto_id)

    # 3. Validación de bodega
    bodega = db.query(models.Bodega).filter(models.Bodega.id == payload.bodega_id).first()
    if not bodega:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bodega {payload.bodega_id} no encontrada",
        )
    if not bodega.activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bodega {payload.bodega_id} no está activa",
        )

    # 4. Transacción ACID con bloqueo pesimista
    try:
        existencia = (
            db.query(models.Existencia)
            .filter(
                models.Existencia.producto_id == payload.producto_id,
                models.Existencia.bodega_id == payload.bodega_id,
            )
            .with_for_update()
            .first()
        )

        tipo_upper = payload.tipo.upper()
        if not existencia:
            if "SALIDA" in tipo_upper or "REDUCCION" in tipo_upper:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Stock insuficiente: no existe inventario previo para realizar la salida",
                )
            existencia = models.Existencia(
                producto_id=payload.producto_id,
                bodega_id=payload.bodega_id,
                cantidad=payload.cantidad,
                cantidad_reservada=0,
                stock_minimo=0,
            )
            db.add(existencia)
            db.flush()
        else:
            if "SALIDA" in tipo_upper or "REDUCCION" in tipo_upper:
                if existencia.cantidad < payload.cantidad:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Stock insuficiente: disponible {existencia.cantidad}, requerido {payload.cantidad}",
                    )
                existencia.cantidad -= payload.cantidad
            else:
                existencia.cantidad += payload.cantidad

        movimiento = models.Movimiento(
            existencia_id=existencia.id,
            bodega_id=payload.bodega_id,
            operacion_id=payload.operacion_id,
            tipo=payload.tipo,
            cantidad=payload.cantidad,
            usuario_id=usuario_id,
            fecha=datetime.utcnow(),
        )
        db.add(movimiento)
        db.commit()
        db.refresh(movimiento)
        return movimiento
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        mov = (
            db.query(models.Movimiento)
            .filter(models.Movimiento.operacion_id == payload.operacion_id)
            .first()
        )
        if mov:
            return mov
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto de integridad concurrente",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando movimiento: {str(exc)}",
        )


@router.post("/descuentos", response_model=schemas.DescuentoResponse, status_code=status.HTTP_200_OK)
def descontar_stock(
    payload: schemas.DescuentoRequest,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    """
    Descuenta unidades por venta confirmada con bloqueo pesimista e idempotencia.
    Cero stock negativo garantizado (retorna 409 si stock insuficiente).
    """
    # 1. Idempotencia: Verificar si la operacion_id ya fue procesada
    movimiento_existente = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.operacion_id == payload.operacion_id)
        .first()
    )
    if movimiento_existente:
        existencia_actual = (
            db.query(models.Existencia)
            .filter(models.Existencia.id == movimiento_existente.existencia_id)
            .first()
        )
        stock_actual = existencia_actual.cantidad if existencia_actual else 0
        return schemas.DescuentoResponse(
            mensaje="Descuento ya procesado previamente (idempotencia)",
            operacion_id=payload.operacion_id,
            venta_id=payload.venta_id,
            producto_id=payload.producto_id,
            bodega_id=payload.bodega_id,
            cantidad_descontada=movimiento_existente.cantidad,
            nuevo_stock=stock_actual,
            idempotente=True,
        )

    # 2. Transacción ACID con bloqueo pesimista (with_for_update)
    try:
        existencia = (
            db.query(models.Existencia)
            .filter(
                models.Existencia.producto_id == payload.producto_id,
                models.Existencia.bodega_id == payload.bodega_id,
            )
            .with_for_update()
            .first()
        )

        if not existencia:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente: no existe registro de stock para producto {payload.producto_id} en bodega {payload.bodega_id}",
            )

        disponible = existencia.cantidad - existencia.cantidad_reservada
        if disponible < payload.cantidad or existencia.cantidad < payload.cantidad:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente para producto {payload.producto_id} en bodega {payload.bodega_id}: disponible {disponible}, requerido {payload.cantidad}",
            )

        existencia.cantidad -= payload.cantidad

        movimiento = models.Movimiento(
            existencia_id=existencia.id,
            bodega_id=payload.bodega_id,
            operacion_id=payload.operacion_id,
            tipo="DESCUENTO",
            cantidad=payload.cantidad,
            usuario_id=x_user_id,
            fecha=datetime.utcnow(),
        )
        db.add(movimiento)
        db.commit()
        db.refresh(existencia)

        return schemas.DescuentoResponse(
            mensaje="Descuento de inventario realizado con éxito",
            operacion_id=payload.operacion_id,
            venta_id=payload.venta_id,
            producto_id=payload.producto_id,
            bodega_id=payload.bodega_id,
            cantidad_descontada=payload.cantidad,
            nuevo_stock=existencia.cantidad,
            idempotente=False,
        )
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        mov = (
            db.query(models.Movimiento)
            .filter(models.Movimiento.operacion_id == payload.operacion_id)
            .first()
        )
        if mov:
            existencia_actual = (
                db.query(models.Existencia)
                .filter(models.Existencia.id == mov.existencia_id)
                .first()
            )
            stock_actual = existencia_actual.cantidad if existencia_actual else 0
            return schemas.DescuentoResponse(
                mensaje="Descuento ya procesado previamente (idempotencia concurrente)",
                operacion_id=payload.operacion_id,
                venta_id=payload.venta_id,
                producto_id=payload.producto_id,
                bodega_id=payload.bodega_id,
                cantidad_descontada=mov.cantidad,
                nuevo_stock=stock_actual,
                idempotente=True,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto de integridad en descuento de existencias",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando descuento: {str(exc)}",
        )


@router.post("/devoluciones", response_model=schemas.DevolucionResponse, status_code=status.HTTP_200_OK)
def reintegrar_stock(
    payload: schemas.DevolucionRequest,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    """
    Reintegra unidades al inventario por devolución con idempotencia.
    """
    # 1. Idempotencia: Verificar si la operacion_id ya existe
    movimiento_existente = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.operacion_id == payload.operacion_id)
        .first()
    )
    if movimiento_existente:
        existencia_actual = (
            db.query(models.Existencia)
            .filter(models.Existencia.id == movimiento_existente.existencia_id)
            .first()
        )
        stock_actual = existencia_actual.cantidad if existencia_actual else 0
        return schemas.DevolucionResponse(
            mensaje="Devolución ya procesada previamente (idempotencia)",
            operacion_id=payload.operacion_id,
            devolucion_id=payload.devolucion_id,
            producto_id=payload.producto_id,
            bodega_id=payload.bodega_id,
            cantidad_reintegrada=movimiento_existente.cantidad,
            nuevo_stock=stock_actual,
            idempotente=True,
        )

    # 2. Transacción ACID con bloqueo pesimista
    try:
        existencia = (
            db.query(models.Existencia)
            .filter(
                models.Existencia.producto_id == payload.producto_id,
                models.Existencia.bodega_id == payload.bodega_id,
            )
            .with_for_update()
            .first()
        )

        if not existencia:
            existencia = models.Existencia(
                producto_id=payload.producto_id,
                bodega_id=payload.bodega_id,
                cantidad=payload.cantidad,
                cantidad_reservada=0,
                stock_minimo=0,
            )
            db.add(existencia)
            db.flush()
        else:
            existencia.cantidad += payload.cantidad

        movimiento = models.Movimiento(
            existencia_id=existencia.id,
            bodega_id=payload.bodega_id,
            operacion_id=payload.operacion_id,
            tipo="DEVOLUCION",
            cantidad=payload.cantidad,
            usuario_id=x_user_id,
            fecha=datetime.utcnow(),
        )
        db.add(movimiento)
        db.commit()
        db.refresh(existencia)

        return schemas.DevolucionResponse(
            mensaje="Devolución reintegrada con éxito al inventario",
            operacion_id=payload.operacion_id,
            devolucion_id=payload.devolucion_id,
            producto_id=payload.producto_id,
            bodega_id=payload.bodega_id,
            cantidad_reintegrada=payload.cantidad,
            nuevo_stock=existencia.cantidad,
            idempotente=False,
        )
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        mov = (
            db.query(models.Movimiento)
            .filter(models.Movimiento.operacion_id == payload.operacion_id)
            .first()
        )
        if mov:
            existencia_actual = (
                db.query(models.Existencia)
                .filter(models.Existencia.id == mov.existencia_id)
                .first()
            )
            stock_actual = existencia_actual.cantidad if existencia_actual else 0
            return schemas.DevolucionResponse(
                mensaje="Devolución ya procesada previamente (idempotencia concurrente)",
                operacion_id=payload.operacion_id,
                devolucion_id=payload.devolucion_id,
                producto_id=payload.producto_id,
                bodega_id=payload.bodega_id,
                cantidad_reintegrada=mov.cantidad,
                nuevo_stock=stock_actual,
                idempotente=True,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto de integridad en devolución de existencias",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando devolución: {str(exc)}",
        )


@router.post("/traslados", response_model=schemas.TrasladoResponse, status_code=status.HTTP_201_CREATED)
def trasladar_stock(
    payload: schemas.TrasladoRequest,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    """
    Traslada existencias entre bodegas con bloqueo pesimista y prevención de deadlocks.
    Rechaza con 409 si la bodega de origen no cuenta con existencias suficientes.
    """
    if payload.bodega_origen_id == payload.bodega_destino_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La bodega de origen y destino no pueden ser iguales",
        )

    usuario_id = payload.usuario_id or x_user_id
    operacion_id = payload.operacion_id or f"traslado-{uuid.uuid4()}"

    # Idempotencia si se envió operacion_id
    movimiento_existente = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.operacion_id == operacion_id)
        .first()
    )
    if movimiento_existente and movimiento_existente.traslado_id:
        traslado_existente = (
            db.query(models.Traslado)
            .filter(models.Traslado.id == movimiento_existente.traslado_id)
            .first()
        )
        if traslado_existente:
            stock_origen = (
                db.query(models.Existencia.cantidad)
                .filter(
                    models.Existencia.producto_id == payload.producto_id,
                    models.Existencia.bodega_id == payload.bodega_origen_id,
                )
                .scalar()
                or 0
            )
            stock_destino = (
                db.query(models.Existencia.cantidad)
                .filter(
                    models.Existencia.producto_id == payload.producto_id,
                    models.Existencia.bodega_id == payload.bodega_destino_id,
                )
                .scalar()
                or 0
            )
            return schemas.TrasladoResponse(
                mensaje="Traslado ya procesado previamente (idempotencia)",
                traslado_id=traslado_existente.id,
                operacion_id=operacion_id,
                producto_id=payload.producto_id,
                bodega_origen_id=payload.bodega_origen_id,
                bodega_destino_id=payload.bodega_destino_id,
                cantidad=traslado_existente.cantidad,
                stock_origen=stock_origen,
                stock_destino=stock_destino,
                idempotente=True,
            )

    # Validar que ambas bodegas existan y estén activas
    bodegas = (
        db.query(models.Bodega)
        .filter(models.Bodega.id.in_([payload.bodega_origen_id, payload.bodega_destino_id]))
        .all()
    )
    bodegas_dict = {b.id: b for b in bodegas}
    if payload.bodega_origen_id not in bodegas_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bodega de origen {payload.bodega_origen_id} no encontrada",
        )
    if payload.bodega_destino_id not in bodegas_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bodega de destino {payload.bodega_destino_id} no encontrada",
        )
    if not bodegas_dict[payload.bodega_origen_id].activa or not bodegas_dict[payload.bodega_destino_id].activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una o ambas bodegas no están activas",
        )

    # Transacción ACID con orden consistente para evitar interbloqueos (deadlocks)
    try:
        b_first, b_second = sorted([payload.bodega_origen_id, payload.bodega_destino_id])

        existencias_bloqueadas = (
            db.query(models.Existencia)
            .filter(
                models.Existencia.producto_id == payload.producto_id,
                models.Existencia.bodega_id.in_([b_first, b_second]),
            )
            .with_for_update()
            .all()
        )
        existencias_map = {e.bodega_id: e for e in existencias_bloqueadas}

        existencia_origen = existencias_map.get(payload.bodega_origen_id)
        if not existencia_origen:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente: origen {payload.bodega_origen_id} no tiene existencias para producto {payload.producto_id}",
            )

        disponible_origen = existencia_origen.cantidad - existencia_origen.cantidad_reservada
        if disponible_origen < payload.cantidad or existencia_origen.cantidad < payload.cantidad:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente en bodega origen {payload.bodega_origen_id}: disponible {disponible_origen}, requerido {payload.cantidad}",
            )

        existencia_destino = existencias_map.get(payload.bodega_destino_id)
        if not existencia_destino:
            existencia_destino = models.Existencia(
                producto_id=payload.producto_id,
                bodega_id=payload.bodega_destino_id,
                cantidad=0,
                cantidad_reservada=0,
                stock_minimo=0,
            )
            db.add(existencia_destino)
            db.flush()

        existencia_origen.cantidad -= payload.cantidad
        existencia_destino.cantidad += payload.cantidad

        traslado = models.Traslado(
            producto_id=payload.producto_id,
            origen_id=payload.bodega_origen_id,
            destino_id=payload.bodega_destino_id,
            cantidad=payload.cantidad,
            estado="COMPLETADO",
            fecha=datetime.utcnow(),
        )
        db.add(traslado)
        db.flush()

        movimiento = models.Movimiento(
            existencia_id=existencia_origen.id,
            bodega_id=payload.bodega_origen_id,
            traslado_id=traslado.id,
            operacion_id=operacion_id,
            tipo="TRASLADO",
            cantidad=payload.cantidad,
            usuario_id=usuario_id,
            fecha=datetime.utcnow(),
        )
        db.add(movimiento)
        db.commit()
        db.refresh(existencia_origen)
        db.refresh(existencia_destino)

        return schemas.TrasladoResponse(
            mensaje="Traslado realizado con éxito",
            traslado_id=traslado.id,
            operacion_id=operacion_id,
            producto_id=payload.producto_id,
            bodega_origen_id=payload.bodega_origen_id,
            bodega_destino_id=payload.bodega_destino_id,
            cantidad=payload.cantidad,
            stock_origen=existencia_origen.cantidad,
            stock_destino=existencia_destino.cantidad,
            idempotente=False,
        )
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        mov = (
            db.query(models.Movimiento)
            .filter(models.Movimiento.operacion_id == operacion_id)
            .first()
        )
        if mov and mov.traslado_id:
            tras = (
                db.query(models.Traslado)
                .filter(models.Traslado.id == mov.traslado_id)
                .first()
            )
            if tras:
                return schemas.TrasladoResponse(
                    mensaje="Traslado ya procesado previamente (idempotencia concurrente)",
                    traslado_id=tras.id,
                    operacion_id=operacion_id,
                    producto_id=payload.producto_id,
                    bodega_origen_id=payload.bodega_origen_id,
                    bodega_destino_id=payload.bodega_destino_id,
                    cantidad=tras.cantidad,
                    stock_origen=0,
                    stock_destino=0,
                    idempotente=True,
                )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto de integridad en traslado de existencias",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando traslado: {str(exc)}",
        )
