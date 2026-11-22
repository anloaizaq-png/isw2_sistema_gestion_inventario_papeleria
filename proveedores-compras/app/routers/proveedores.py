from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Proveedor
from app.schemas import Estado, ProveedorCreate, ProveedorOut, ProveedorUpdate

router = APIRouter(prefix="/api/compras/proveedores", tags=["Proveedores"])

NIT_DUPLICADO = "Ya existe un proveedor con ese NIT"


def _get_or_404(db: Session, proveedor_id: int) -> Proveedor:
    proveedor = db.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise HTTPException(404, "Proveedor no encontrado")
    return proveedor


def _validar_nit_unico(db: Session, nit: str, excluir_id: int | None = None):
    consulta = select(Proveedor.id).where(Proveedor.nit == nit)
    if excluir_id is not None:
        consulta = consulta.where(Proveedor.id != excluir_id)
    if db.scalars(consulta).first() is not None:
        raise HTTPException(422, NIT_DUPLICADO)


def _guardar(db: Session, proveedor: Proveedor) -> Proveedor:
    try:
        db.add(proveedor)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(422, NIT_DUPLICADO)
    db.refresh(proveedor)
    return proveedor


@router.post("", response_model=ProveedorOut, status_code=201)
def crear_proveedor(datos: ProveedorCreate, db: Session = Depends(get_db)):
    _validar_nit_unico(db, datos.nit)
    return _guardar(db, Proveedor(**datos.model_dump()))


@router.get("", response_model=list[ProveedorOut])
def listar_proveedores(
    estado: Estado | None = None,
    nombre: str | None = None,
    db: Session = Depends(get_db),
):
    consulta = select(Proveedor)
    if estado is not None:
        consulta = consulta.where(Proveedor.estado == estado)
    if nombre:
        consulta = consulta.where(Proveedor.nombre.contains(nombre, autoescape=True))
    return db.scalars(consulta.order_by(Proveedor.id)).all()


@router.get("/{proveedor_id}", response_model=ProveedorOut)
def obtener_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, proveedor_id)


@router.put("/{proveedor_id}", response_model=ProveedorOut)
def actualizar_proveedor(proveedor_id: int, datos: ProveedorUpdate, db: Session = Depends(get_db)):
    proveedor = _get_or_404(db, proveedor_id)
    _validar_nit_unico(db, datos.nit, excluir_id=proveedor_id)
    for campo, valor in datos.model_dump().items():
        setattr(proveedor, campo, valor)
    return _guardar(db, proveedor)


@router.delete("/{proveedor_id}", response_model=ProveedorOut)
def dar_de_baja_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    """Baja lógica: el proveedor queda 'inactivo' para conservar sus órdenes."""
    proveedor = _get_or_404(db, proveedor_id)
    proveedor.estado = "inactivo"
    return _guardar(db, proveedor)