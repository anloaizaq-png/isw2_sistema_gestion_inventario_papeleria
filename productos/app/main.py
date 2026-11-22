from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea las tablas si no existen (sin migraciones, igual que el resto del equipo)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Servicio de Productos - Cotton Cloud Paper",
    version="1.0.0",
    description="CRUD de productos, categorías y subcategorías.",
    lifespan=lifespan,
    # Rutas bajo /api/productos para que pasen por el API Gateway
    docs_url="/api/productos/docs",
    openapi_url="/api/productos/openapi.json",
    redoc_url=None,
)


@app.get("/health", tags=["Salud"])
def health():
    return {"status": "ok", "service": "productos-service"}