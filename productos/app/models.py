from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = (
        UniqueConstraint("nombre", "categoria_padre_id", name="uq_categoria_nombre_padre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria_padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("categoria.id", ondelete="RESTRICT"), nullable=True
    )