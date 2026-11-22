from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.database import Base, engine
from app.routers import categorias


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Servicio de Productos - Cotton Cloud Paper",
    version="1.0.0",
    description="CRUD de productos, categorías y subcategorías.",
    lifespan=lifespan,
    docs_url="/api/productos/docs",
    openapi_url="/api/productos/openapi.json",
    redoc_url=None,
)

# Las rutas fijas (/categorias) se registran antes que /{producto_id}
app.include_router(categorias.router)


@app.get("/health", tags=["Salud"])
def health():
    return {"status": "ok", "service": "productos-service"}