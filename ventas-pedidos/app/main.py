import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers.ventas import router as ventas_router

logger = logging.getLogger("ventas-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verificación y creación de tablas en la base de datos si no existen
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas de base de datos de ventas verificadas/creadas exitosamente.")
    except Exception as exc:
        logger.warning("No se pudieron verificar/crear tablas automáticamente en arranque: %s", exc)
    yield


app = FastAPI(
    title="Cotton Cloud Paper - Microservicio Ventas y Pedidos",
    version="1.0.0",
    description="Microservicio de gestión de ventas, pedidos, confirmaciones, cancelaciones y devoluciones",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ventas_router)


@app.get("/health", tags=["health"])
def health_check():
    """
    Endpoint para verificación de salud HTTP del servicio.
    """
    return {"status": "ok", "service": "ventas-service"}


@app.get("/", tags=["info"])
def root():
    """
    Información general del servicio.
    """
    return {
        "service": "ventas-service",
        "status": "running",
        "docs_url": "/docs",
    }
