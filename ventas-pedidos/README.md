# Microservicio de Ventas y Pedidos (`ventas-service`)

Microservicio de gestión de ventas, pedidos, confirmación con descuento de inventario, cancelaciones y devoluciones para el proyecto **Cotton Cloud Paper**.

## Stack Tecnológico
- Python 3.11
- FastAPI
- SQLAlchemy 2.x
- PyMySQL
- HTTPX

## Base de Datos Aislada: `ventas` (MySQL 8)
Tablas implementadas:
1. `venta`: Pedidos y ventas (`id`, `usuario_id`, `bodega_id`, `estado` [`pendiente`, `confirmada`, `cancelada`], `total`, `fecha`, `operacion_id`).
2. `detalle_venta`: Detalle de productos por venta (`id`, `venta_id`, `producto_id`, `cantidad`, `precio_unitario`, `subtotal`).
3. `devolucion`: Devoluciones sobre ventas confirmadas (`id`, `venta_id`, `estado`, `motivo`, `fecha`, `operacion_id`).
4. `detalle_devolucion`: Detalle de ítems devueltos asociados a `detalle_venta` (`id`, `devolucion_id`, `detalle_venta_id`, `cantidad`).

## Endpoints REST (`/api/ventas/...`)
- `GET /api/ventas`: Lista ventas con filtros opcionales `estado`, `fecha_inicio`, `fecha_fin`.
- `POST /api/ventas`: Crea pedido en estado `pendiente`. Consulta cada producto en `PRODUCTOS_URL` (`GET /api/productos/{id}`) para validar que esté activo y obtener su `precioventa` real, calculando `subtotal` y `total`.
- `GET /api/ventas/{id}`: Consulta venta con sus detalles.
- `POST /api/ventas/{id}/confirmacion`: Recibe `operacion_id` (idempotencia). Valida venta `pendiente`, verifica disponibilidad y llama a `POST {INVENTARIO_URL}/api/inventario/descuentos` por cada ítem. Si todos se confirman, transiciona a `confirmada` (`200`); si falla alguno por stock insuficiente, revierte/compensa y retorna `409 Conflict`.
- `POST /api/ventas/{id}/cancelacion`: Recibe `motivo`. Si está `pendiente`, cambia a `cancelada` (`200`); si ya estaba `confirmada` o `cancelada`, retorna `409 Conflict`.
- `POST /api/ventas/{id}/devoluciones`: Recibe `operacion_id`, `motivo`, `detalles`. Valida que la venta esté `confirmada` y que la suma acumulada de devoluciones por `detalle_venta_id` no supere la `cantidad` vendida. Llama a `POST {INVENTARIO_URL}/api/inventario/devoluciones` para reintegrar stock.
- `GET /api/ventas/{id}/devoluciones`: Lista las devoluciones registradas de una venta.

## Variables de Entorno
- `DB_HOST`: Host de la base de datos MySQL (por defecto `localhost` / `ventas-db`)
- `DB_PORT`: Puerto de MySQL (por defecto `3306`)
- `DB_NAME`: Nombre de la base de datos (por defecto `ventas`)
- `DB_USER`: Usuario de MySQL (por defecto `root`)
- `DB_PASSWORD`: Contraseña de MySQL
- `PRODUCTOS_URL`: URL base del microservicio de productos (por defecto `http://productos-service:8080`)
- `INVENTARIO_URL`: URL base del microservicio de inventario (por defecto `http://inventario-service:8080`)
- `PORT`: Puerto interno del servicio (por defecto `8080`)
