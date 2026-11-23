# Imagen del microservicio Alertas y Analítica
FROM python:3.12-slim

# Python sin archivos .pyc y con salida inmediata en los logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8080

WORKDIR /app

# Primero las dependencias, para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código del servicio (lo excluido en .dockerignore no se copia)
COPY . .

# Usuario sin privilegios (RNF07)
RUN useradd --create-home appuser
USER appuser

# Puerto interno del servicio (Entrega 2, Tabla 3)
EXPOSE 8080

# Servidor de producción con 2 procesos
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${APP_PORT} --workers 2 --access-logfile - app:app"]