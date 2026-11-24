from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.clients import consultar_disponibilidad, registrar_movimiento_inventario
from app.database import get_db
from app.models import DevolucionProveedor, DevolucionProveedorDetalle, OrdenCompra
from app.schemas import DevolucionProveedorCreate, DevolucionProveedorOut

router = APIRouter(prefix="/api/compras/devoluciones-proveedor", tags=["Devoluciones a proveedor"])


@router.post("", response_model=DevolucionProveedorOut, status_code=201)
def crear_devolucion(
    datos: DevolucionProveedorCreate,
    x_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Se bloquea la orden para que dos devoluciones simultáneas no superen lo recibido
    orden = db.scalars(
        select(OrdenCompra).where(OrdenCompra.id == datos.orden_compra_id).with_for_update()
    ).first()
    if orden is None:
        raise HTTPException(404, "Orden de compra no encontrada")
    if orden.estado not in ("recibida_parcial", "recibida_total"):
        raise HTTPException(409, "Solo se pueden devolver productos de una orden que ya recibió mercancía")

    detalles = {d.producto_id: d for d in orden.detalles}
    vistos = set()
    for linea in datos.productos:
        if linea.producto_id in vistos:
            raise HTTPException(422, f"El producto {linea.producto_id} está repetido en la devolución")
        vistos.add(linea.producto_id)
        detalle = detalles.get(linea.producto_id)
        if detalle is None:
            raise HTTPException(422, f"El producto {linea.producto_id} no pertenece a la orden")
        devolvible = detalle.cantidad_recibida - detalle.cantidad_devuelta
        if linea.cantidad > devolvible:
            raise HTTPException(
                422, f"Producto {linea.producto_id}: se devuelven {linea.cantidad} y solo se pueden devolver {devolvible}"
            )

    # 1) Se verifica el stock de TODAS las líneas antes de sacar algo de Inventario
    for linea in datos.productos:
        disp = consultar_disponibilidad(linea.producto_id, datos.bodega_id, linea.cantidad)
        if not disp["disponible"]:
            raise HTTPException(
                409,
                f"Stock insuficiente en la bodega para el producto {linea.producto_id}: "
                f"disponible {disp['stock_disponible']}",
            )

    # 2) Salidas en Inventario (idempotentes por operacion_id: un reintento no descuenta dos veces)
    for linea in datos.productos:
        detalle = detalles[linea.producto_id]
        registrar_movimiento_inventario(
            operacion_id=f"devprov-{orden.id}-{linea.producto_id}-{detalle.cantidad_devuelta}",
            producto_id=linea.producto_id,
            bodega_id=datos.bodega_id,
            tipo="SALIDA",
            cantidad=linea.cantidad,
            usuario_id=x_user_id,
        )

    # 3) Solo si Inventario aceptó todo, se registra la devolución en Compras
    devolucion = DevolucionProveedor(
        orden_compra_id=orden.id,
        bodega_id=datos.bodega_id,
        usuario_id=x_user_id,
        motivo=datos.motivo,
    )
    devolucion.detalles = [
        DevolucionProveedorDetalle(producto_id=l.producto_id, cantidad=l.cantidad) for l in datos.productos
    ]
    for linea in datos.productos:
        detalles[linea.producto_id].cantidad_devuelta += linea.cantidad
    db.add(devolucion)
    db.commit()
    db.refresh(devolucion)
    return devolucion


@router.get("", response_model=list[DevolucionProveedorOut])
def listar_devoluciones(
    orden_compra_id: int | None = None,
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
):
    consulta = select(DevolucionProveedor).options(
        selectinload(DevolucionProveedor.detalles), selectinload(DevolucionProveedor.orden)
    )
    if orden_compra_id is not None:
        consulta = consulta.where(DevolucionProveedor.orden_compra_id == orden_compra_id)
    if proveedor_id is not None:
        consulta = consulta.join(OrdenCompra, DevolucionProveedor.orden_compra_id == OrdenCompra.id).where(
            OrdenCompra.proveedor_id == proveedor_id
        )
    return db.scalars(consulta.order_by(DevolucionProveedor.id.desc())).all()


@router.get("/{devolucion_id}", response_model=DevolucionProveedorOut)
def obtener_devolucion(devolucion_id: int, db: Session = Depends(get_db)):
    devolucion = db.get(DevolucionProveedor, devolucion_id)
    if devolucion is None:
        raise HTTPException(404, "Devolución no encontrada")
    return devolucion