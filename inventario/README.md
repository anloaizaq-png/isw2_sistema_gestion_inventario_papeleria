# Microservicio de Inventario (`inventario-service`)

Microservicio de gestión de bodegas, existencias, movimientos y traslados para el proyecto **Cotton Cloud Paper**.

## Stack Tecnológico
- Python 3.11
- FastAPI
- SQLAlchemy 2.x
- PyMySQL
- HTTPX

## Base de Datos Aislada: `inventario` (MySQL 8)
Tablas implementadas:
1. `bodega`: Bodegas de almacenamiento (`id`, `nombre`, `ubicacion`, `activa`).
2. `existencia`: Stock por producto y bodega (`id`, `producto_id`, `bodega_id`, `cantidad`, `cantidad_reservada`, `stock_minimo`), con restricción única `(producto_id, bodega_id)`.
3. `traslado`: Registro de traslados entre bodegas (`id`, `producto_id`, `origen_id`, `destino_id`, `cantidad`, `estado`, `fecha`).
4. `movimiento`: Historial y auditoría de movimientos con clave única `operacion_id` para garantizar idempotencia (`id`, `existencia_id`, `bodega_id`, `traslado_id`, `operacion_id`, `tipo`, `cantidad`, `usuario_id`, `fecha`).

## Endpoints REST (`/api/inventario/...`)
- `GET /api/inventario/stock`: Consulta existencias con filtros opcionales `producto_id`, `bodega_id`.
- `GET /api/inventario/disponibilidad`: Verifica si `cantidad - cantidad_reservada >= cantidad`.
- `GET /api/inventario/bodegas`: Lista todas las bodegas.
- `POST /api/inventario/bodegas`: Registra una nueva bodega (`nombre`, `ubicacion`, `activa`).
- `GET /api/inventario/movimientos`: Historial de movimientos con filtros opcionales `producto_id`, `bodega_id`, `tipo`, `fecha`.
- `POST /api/inventario/movimientos`: Registra entradas y ajustes de stock con validación de producto activo en `PRODUCTOS_URL` e idempotencia.
- `POST /api/inventario/descuentos`: Descuenta unidades por venta confirmada con bloqueo pesimista (`with_for_update`) e idempotencia (`409` si no hay stock suficiente).
- `POST /api/inventario/devoluciones`: Reintegra unidades al inventario por devolución con idempotencia.
- `POST /api/inventario/traslados`: Traslado atómico de existencias entre bodegas con bloqueo pesimista y orden determinista anti-deadlock.

## Variables de Entorno
- `DB_HOST`: Host de la base de datos MySQL (por defecto `localhost` / `inventario-db`)
- `DB_PORT`: Puerto de MySQL (por defecto `3306`)
- `DB_NAME`: Nombre de la base de datos (por defecto `inventario`)
- `DB_USER`: Usuario de MySQL (por defecto `root`)
- `DB_PASSWORD`: Contraseña de MySQL
- `PRODUCTOS_URL`: URL base del microservicio de productos (por defecto `http://productos-service:8080`)
- `PORT`: Puerto interno del servicio (por defecto `8080`)
