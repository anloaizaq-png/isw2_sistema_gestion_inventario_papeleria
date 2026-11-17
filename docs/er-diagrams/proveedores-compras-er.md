# Modelo entidad-relación: Proveedores y Compras

Base de datos propia: `compras` (MySQL). Las referencias a otros servicios son lógicas: guardan solo el identificador, sin llave foránea.

```mermaid
erDiagram
    proveedores ||--o{ proveedor_producto : "suministra"
    proveedores ||--o{ ordenes_compra : "recibe"
    ordenes_compra ||--|{ orden_compra_detalle : "contiene"
    ordenes_compra ||--o{ recepcion : "se recibe en"
    recepcion ||--|{ recepcion_detalle : "contiene"
    ordenes_compra ||--o{ devolucion_proveedor : "origina"
    devolucion_proveedor ||--|{ devolucion_proveedor_detalle : "contiene"

    proveedores {
        bigint id PK "autoincremental"
        varchar nombre "VARCHAR(150)"
        varchar nit UK "VARCHAR(30), unico"
        varchar contacto_nombre "VARCHAR(150), nullable"
        varchar telefono "VARCHAR(30), nullable"
        varchar email "VARCHAR(150), nullable"
        varchar direccion "VARCHAR(200), nullable"
        enum estado "activo o inactivo"
        timestamp fecha_registro
    }

    proveedor_producto {
        bigint id PK "autoincremental"
        bigint proveedor_id FK "proveedores.id"
        bigint producto_id "referencia logica a Productos"
        timestamp fecha_asociacion
    }

    ordenes_compra {
        bigint id PK "autoincremental"
        bigint proveedor_id FK "proveedores.id"
        bigint usuario_id "nullable, referencia logica a Usuarios"
        bigint sugerencia_id "nullable, referencia logica a Alertas"
        timestamp fecha_creacion
        enum estado "pendiente, recibida_parcial, recibida_total o cancelada"
        enum origen "manual o alerta"
        decimal total "DECIMAL(14,2)"
    }

    orden_compra_detalle {
        bigint id PK "autoincremental"
        bigint orden_compra_id FK "ordenes_compra.id"
        bigint producto_id "referencia logica a Productos"
        int cantidad_solicitada
        int cantidad_recibida "por defecto 0"
        int cantidad_devuelta "por defecto 0"
        decimal precio_unitario "DECIMAL(12,2)"
    }

    recepcion {
        bigint id PK "autoincremental"
        bigint orden_compra_id FK "ordenes_compra.id"
        bigint bodega_id "referencia logica a Inventario"
        bigint usuario_id "nullable, referencia logica a Usuarios"
        timestamp fecha
    }

    recepcion_detalle {
        bigint id PK "autoincremental"
        bigint recepcion_id FK "recepcion.id"
        bigint producto_id "referencia logica a Productos"
        int cantidad
        enum estado_inventario "PENDIENTE, APLICADA o FALLIDA"
        char idempotency_key UK "CHAR(36), uuid enviado a Inventario"
    }

    devolucion_proveedor {
        bigint id PK "autoincremental"
        bigint orden_compra_id FK "ordenes_compra.id"
        bigint bodega_id "referencia logica a Inventario"
        bigint usuario_id "nullable, referencia logica a Usuarios"
        varchar motivo "VARCHAR(255)"
        timestamp fecha
    }

    devolucion_proveedor_detalle {
        bigint id PK "autoincremental"
        bigint devolucion_proveedor_id FK "devolucion_proveedor.id"
        bigint producto_id "referencia logica a Productos"
        int cantidad
        enum estado_inventario "PENDIENTE, APLICADA o FALLIDA"
        char idempotency_key UK "CHAR(36), uuid enviado a Inventario"
    }
```

## Integridad referencial

| Campo | Tipo | Observación |
|---|---|---|
| `proveedor_producto.proveedor_id`, `ordenes_compra.proveedor_id` | FK real | Hacia `proveedores.id`, misma base de datos. |
| `orden_compra_detalle.orden_compra_id`, `recepcion.orden_compra_id`, `devolucion_proveedor.orden_compra_id` | FK real | Hacia `ordenes_compra.id`, misma base de datos. |
| `recepcion_detalle.recepcion_id`, `devolucion_proveedor_detalle.devolucion_proveedor_id` | FK real | Hacia su encabezado, misma base de datos. |
| `producto_id` (en todas las tablas que lo tienen) | Referencia lógica | Apunta a Productos. Se valida por API, sin FK física. |
| `usuario_id` | Referencia lógica | Apunta a Usuarios, en el API Gateway. |
| `bodega_id` | Referencia lógica | Apunta a las bodegas de Inventario. |
| `sugerencia_id` | Referencia lógica | Apunta a las sugerencias de Alertas y Analítica. |

## Restricciones e índices

- `proveedores.nit`: `UNIQUE`.
- `proveedor_producto (proveedor_id, producto_id)`: `UNIQUE`.
- `orden_compra_detalle (orden_compra_id, producto_id)`: `UNIQUE`, para no repetir un producto en la misma orden.
- `recepcion_detalle.idempotency_key` y `devolucion_proveedor_detalle.idempotency_key`: `UNIQUE`.
- `ordenes_compra (estado)` y `ordenes_compra (proveedor_id)`: índices para los filtros del listado.
- El proveedor de una devolución no se guarda: se obtiene a través de `ordenes_compra.proveedor_id`.

## Cambios respecto a la Entrega 2

| Cambio | Motivo |
|---|---|
| Tablas nuevas `recepcion` y `recepcion_detalle` | Guardar cada recepción con su bodega y la `idempotency_key` de cada línea enviada a Inventario, para reintentar sin duplicar stock. |
| Tablas nuevas `devolucion_proveedor` y `devolucion_proveedor_detalle` | La Entrega 2 asigna las devoluciones a proveedores a este servicio (RF13), pero no tenían modelo de datos. |
| Columna nueva `orden_compra_detalle.cantidad_devuelta` | Limitar las devoluciones a lo recibido. |
| Columna nueva `ordenes_compra.sugerencia_id` | Trazabilidad de las órdenes creadas a partir de una alerta. |
| `UNIQUE` en `proveedor_producto` y en `orden_compra_detalle` | Evitar asociaciones y líneas duplicadas. |
