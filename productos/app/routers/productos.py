from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Categoria, Producto
from app.schemas import (
    Estado,
    ProductoCreate,
    ProductoOut,
    ProductoPagina,
    ProductoPatch,
    ProductoUpdate,
)

router = APIRouter(prefix="/api/productos", tags=["Productos"])


def _get_or_404(db: Session, producto_id: int) -> Producto:
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise HTTPException(404, "Producto no encontrado")
    return producto


def _validar_categoria(db: Session, categoria_id: int | None):
    if categoria_id is not None and db.get(Categoria, categoria_id) is None:
        raise HTTPException(400, "La categoría indicada no existe")


def _validar_codigo_unico(db: Session, codigo: str, excluir_id: int | None = None):
    consulta = select(Producto.id).where(Producto.codigo == codigo)
    if excluir_id is not None:
        consulta = consulta.where(Producto.id != excluir_id)
    if db.scalars(consulta).first() is not None:
        raise HTTPException(409, "Ya existe un producto con ese código")


def _guardar(db: Session, producto: Producto) -> Producto:
    try:
        db.add(producto)
        db.commit()
    except IntegrityError:
        # Respaldo ante dos POST simultáneos con el mismo código (UNIQUE en BD)
        db.rollback()
        raise HTTPException(409, "Ya existe un producto con ese código")
    db.refresh(producto)
    return producto


@router.post("", response_model=ProductoOut, status_code=201)
def crear_producto(datos: ProductoCreate, db: Session = Depends(get_db)):
    _validar_categoria(db, datos.categoria_id)
    _validar_codigo_unico(db, datos.codigo)
    return _guardar(db, Producto(**datos.model_dump()))


@router.get("", response_model=ProductoPagina)
def listar_productos(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    categoria_id: int | None = None,
    proveedor_id: int | None = None,
    estado: Estado | None = None,
    db: Session = Depends(get_db),
):
    filtros = []
    if categoria_id is not None:
        filtros.append(Producto.categoria_id == categoria_id)
    if proveedor_id is not None:
        filtros.append(Producto.proveedor_id == proveedor_id)
    if estado is not None:
        filtros.append(Producto.estado == estado)

    total = db.scalar(select(func.count()).select_from(Producto).where(*filtros))
    productos = db.scalars(
        select(Producto)
        .where(*filtros)
        .order_by(Producto.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return {"page": page, "limit": limit, "total": total, "data": productos}


# Debe ir ANTES de /{producto_id}; si no, "buscar" se interpretaría como un id
@router.get("/buscar", response_model=list[ProductoOut])
def buscar_productos(
    codigo: str | None = None,
    codigo_barras: str | None = None,
    nombre: str | None = None,
    categoria: str | None = None,
    marca: str | None = None,
    proveedor: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    consulta = select(Producto)
    if codigo:
        consulta = consulta.where(Producto.codigo == codigo)
    if codigo_barras:
        consulta = consulta.where(Producto.codigo_barras == codigo_barras)
    if nombre:
        consulta = consulta.where(Producto.nombre.contains(nombre, autoescape=True))
    if marca:
        consulta = consulta.where(Producto.marca.contains(marca, autoescape=True))
    if proveedor is not None:
        consulta = consulta.where(Producto.proveedor_id == proveedor)
    if categoria:
        consulta = consulta.join(Categoria, Producto.categoria_id == Categoria.id).where(
            Categoria.nombre.contains(categoria, autoescape=True)
        )
    return db.scalars(consulta.order_by(Producto.id).limit(limit)).all()


@router.get("/{producto_id}", response_model=ProductoOut)
def obtener_producto(producto_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, producto_id)


@router.put("/{producto_id}", response_model=ProductoOut)
def actualizar_producto(producto_id: int, datos: ProductoUpdate, db: Session = Depends(get_db)):
    producto = _get_or_404(db, producto_id)
    _validar_categoria(db, datos.categoria_id)
    _validar_codigo_unico(db, datos.codigo, excluir_id=producto_id)
    for campo, valor in datos.model_dump().items():
        setattr(producto, campo, valor)
    return _guardar(db, producto)


@router.patch("/{producto_id}", response_model=ProductoOut)
def modificar_producto(producto_id: int, datos: ProductoPatch, db: Session = Depends(get_db)):
    producto = _get_or_404(db, producto_id)
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("codigo", "nombre", "precio_venta", "estado"):
        if campo in cambios and cambios[campo] is None:
            raise HTTPException(422, f"El campo '{campo}' no puede ser nulo")
    if "categoria_id" in cambios:
        _validar_categoria(db, cambios["categoria_id"])
    if "codigo" in cambios:
        _validar_codigo_unico(db, cambios["codigo"], excluir_id=producto_id)
    for campo, valor in cambios.items():
        setattr(producto, campo, valor)
    return _guardar(db, producto)


@router.delete("/{producto_id}", response_model=ProductoOut)
def dar_de_baja_producto(producto_id: int, db: Session = Depends(get_db)):
    """Baja lógica: el producto queda 'inactivo' para conservar el historial."""
    producto = _get_or_404(db, producto_id)
    producto.estado = "inactivo"
    return _guardar(db, producto)