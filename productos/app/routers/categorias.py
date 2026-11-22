from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Categoria
from app.schemas import CategoriaCreate, CategoriaOut, CategoriaUpdate

router = APIRouter(prefix="/api/productos/categorias", tags=["Categorías"])


def _get_or_404(db: Session, categoria_id: int) -> Categoria:
    categoria = db.get(Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(404, "Categoría no encontrada")
    return categoria


def _validar_padre(db: Session, padre_id: int | None, categoria_id: int | None = None):
    """El padre debe existir y ser una categoría raíz (máximo dos niveles)."""
    if padre_id is None:
        return
    if categoria_id is not None and padre_id == categoria_id:
        raise HTTPException(400, "Una categoría no puede ser su propio padre")
    padre = db.get(Categoria, padre_id)
    if padre is None:
        raise HTTPException(400, "La categoría padre no existe")
    if padre.categoria_padre_id is not None:
        raise HTTPException(400, "Solo se permiten dos niveles: el padre debe ser una categoría raíz")


def _validar_nombre_unico(db: Session, nombre: str, padre_id: int | None, excluir_id: int | None = None):
    consulta = select(Categoria).where(
        Categoria.nombre == nombre, Categoria.categoria_padre_id == padre_id
    )
    if excluir_id is not None:
        consulta = consulta.where(Categoria.id != excluir_id)
    if db.scalars(consulta).first() is not None:
        raise HTTPException(409, "Ya existe una categoría con ese nombre en el mismo nivel")


@router.get("", response_model=list[CategoriaOut])
def listar_categorias(db: Session = Depends(get_db)):
    return db.scalars(select(Categoria).order_by(Categoria.id)).all()


@router.post("", response_model=CategoriaOut, status_code=201)
def crear_categoria(datos: CategoriaCreate, db: Session = Depends(get_db)):
    _validar_padre(db, datos.categoria_padre_id)
    _validar_nombre_unico(db, datos.nombre, datos.categoria_padre_id)
    categoria = Categoria(nombre=datos.nombre, categoria_padre_id=datos.categoria_padre_id)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.get("/{categoria_id}", response_model=CategoriaOut)
def obtener_categoria(categoria_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, categoria_id)


@router.put("/{categoria_id}", response_model=CategoriaOut)
def actualizar_categoria(categoria_id: int, datos: CategoriaUpdate, db: Session = Depends(get_db)):
    categoria = _get_or_404(db, categoria_id)
    _validar_padre(db, datos.categoria_padre_id, categoria_id)
    if datos.categoria_padre_id is not None:
        tiene_hijas = db.scalars(
            select(Categoria.id).where(Categoria.categoria_padre_id == categoria_id)
        ).first()
        if tiene_hijas is not None:
            raise HTTPException(400, "Una categoría con subcategorías no puede pasar a ser subcategoría")
    _validar_nombre_unico(db, datos.nombre, datos.categoria_padre_id, excluir_id=categoria_id)
    categoria.nombre = datos.nombre
    categoria.categoria_padre_id = datos.categoria_padre_id
    db.commit()
    db.refresh(categoria)
    return categoria


@router.delete("/{categoria_id}", status_code=204)
def eliminar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    categoria = _get_or_404(db, categoria_id)
    tiene_hijas = db.scalars(
        select(Categoria.id).where(Categoria.categoria_padre_id == categoria_id)
    ).first()
    if tiene_hijas is not None:
        raise HTTPException(409, "La categoría tiene subcategorías")
    try:
        db.delete(categoria)
        db.commit()
    except IntegrityError:
        # La FK RESTRICT de producto.categoria_id impide borrar si hay productos
        db.rollback()
        raise HTTPException(409, "La categoría tiene productos asociados")
    return Response(status_code=204)