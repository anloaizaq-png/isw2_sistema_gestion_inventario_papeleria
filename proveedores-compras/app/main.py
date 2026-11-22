from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Servicio de Proveedores y Compras - Cotton Cloud Paper",
    version="1.0.0",
    description="Proveedores, órdenes de compra, recepciones y devoluciones a proveedores.",
    lifespan=lifespan,
    docs_url="/api/compras/docs",
    openapi_url="/api/compras/openapi.json",
    redoc_url=None,
)


@app.get("/health", tags=["Salud"])
def health():
    return {"status": "ok", "service": "compras-service"}