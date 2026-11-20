# Imagen base oficial de Python 3.11 slim
FROM python:3.11-slim

# Variables de entorno para Python y configuración por defecto
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    DB_HOST=ventas-db \
    DB_PORT=3306 \
    DB_NAME=ventas \
    DB_USER=root \
    DB_PASSWORD=root \
    PRODUCTOS_URL=http://productos-service:8080 \
    INVENTARIO_URL=http://inventario-service:8080

# Instalación de utilidades del sistema (curl para HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo de la aplicación
WORKDIR /app

# Instalación de dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia del código fuente
COPY app/ ./app/

# Creación y configuración de usuario no-root
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Cambio al usuario no-root
USER appuser

# Exponer el puerto interno 8080
EXPOSE 8080

# Verificación de salud HTTP periódica
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Comando de inicio del servidor ASGI Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
