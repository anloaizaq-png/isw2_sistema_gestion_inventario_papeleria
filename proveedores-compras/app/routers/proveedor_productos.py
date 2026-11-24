from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients import exigir_producto_activo
from app.database import get_db
from app.models import Proveedor, ProveedorProducto
from app.schemas import AsociarProducto, ProveedorProductoOut

router = APIRouter(prefix="/api/compras/proveedores", tags=["Proveedor-Productos"])


@router.post("/{proveedor_id}/productos", response_model=ProveedorProductoOut, status_code=201)
def asociar_producto(proveedor_id: int, datos: AsociarProducto, db: Session = Depends(get_db)):
    proveedor = db.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise HTTPException(404, "Proveedor no encontrado")
    if proveedor.estado != "activo":
        raise HTTPException(409, "El proveedor está inactivo")

    exigir_producto_activo(datos.producto_id)  # consulta al servicio de Productos

    ya_existe = db.scalars(
        select(ProveedorProducto.id).where(
            ProveedorProducto.proveedor_id == proveedor_id,
            ProveedorProducto.producto_id == datos.producto_id,
        )
    ).first()
    if ya_existe is not None:
        raise HTTPException(409, "El producto ya está asociado a este proveedor")

    asociacion = ProveedorProducto(proveedor_id=proveedor_id, producto_id=datos.producto_id)
    try:
        db.add(asociacion)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "El producto ya está asociado a este proveedor")
    db.refresh(asociacion)
    return asociacion


@router.get("/{proveedor_id}/productos", response_model=list[ProveedorProductoOut])
def listar_productos_del_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    if db.get(Proveedor, proveedor_id) is None:
        raise HTTPException(404, "Proveedor no encontrado")
    return db.scalars(
        select(ProveedorProducto)
        .where(ProveedorProducto.proveedor_id == proveedor_id)
        .order_by(ProveedorProducto.id)
    ).all()