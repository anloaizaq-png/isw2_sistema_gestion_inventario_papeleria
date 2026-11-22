# Imagen base oficial de Python 3.11 slim
FROM python:3.11-slim

# Variables de entorno para Python y configuración por defecto
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    DB_HOST=compras-db \
    DB_PORT=3306 \
    DB_NAME=compras \
    DB_USER=root \
    DB_PASSWORD=root \
    PRODUCTOS_URL=http://productos-service:8080 \
    INVENTARIO_URL=http://inventario-service:8080 \
    ALERTAS_URL=http://analitica-service:8080

# Utilidades del sistema (curl para el HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Código fuente
COPY app/ ./app/

# Usuario no-root
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]