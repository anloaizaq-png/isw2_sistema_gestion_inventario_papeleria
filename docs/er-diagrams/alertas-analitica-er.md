# Diagrama entidad-relación – Alertas y Analítica

Base de datos: `analitica` (propia del microservicio).

El modelo tiene seis tablas. La única llave foránea es interna: `sugerencia_reabastecimiento.alerta_id` hacia `alerta.id`.
Los campos `producto_id`, `bodega_id`, `proveedor_id`, `usuario_atencion_id` y `orden_compra_id` son **referencias lógicas** a otros servicios: guardan solo el identificador, sin llave foránea, para cumplir el requerimiento de bases de datos independientes (RNF02).

```mermaid
erDiagram
    alerta ||--o{ sugerencia_reabastecimiento : "genera"

    alerta {
        int id PK
        int producto_id "Ref. lógica a Productos"
        varchar tipo "varchar(20): stock_bajo, agotado, sin_movimiento"
        varchar estado "varchar(20): pendiente, en_gestion, atendida, descartada"
        int stock_actual
        int umbral_aplicado
        decimal multiplicador_aplicado "decimal(4,2)"
        datetime fecha_generacion
        datetime fecha_atencion "nullable"
        int usuario_atencion_id "Ref. lógica a Usuarios (API Gateway), nullable"
    }

    sugerencia_reabastecimiento {
        int id PK
        int alerta_id FK
        int producto_id "Ref. lógica a Productos"
        int proveedor_id "Ref. lógica a Proveedores y Compras, nullable"
        int cantidad_sugerida
        varchar estado "varchar(20): pendiente, atendida"
        int orden_compra_id "Ref. lógica a Proveedores y Compras, nullable"
    }

    umbral_stock {
        int id PK
        int producto_id "Ref. lógica a Productos"
        int bodega_id "Ref. lógica a Inventario, nullable"
        int stock_minimo
        boolean activo
    }

    temporada {
        int id PK
        varchar nombre "varchar(100)"
        date fecha_inicio
        date fecha_fin
        decimal multiplicador "decimal(4,2)"
    }

    resumen_ventas_producto {
        int id PK
        int producto_id "Ref. lógica a Productos"
        varchar periodo "varchar(7), formato AAAA-MM"
        int unidades_vendidas
        decimal ingresos "decimal(12,2)"
    }

    clasificacion_producto {
        int id PK
        int producto_id "Ref. lógica a Productos"
        char categoria_abc "char(1): A, B o C"
        varchar nivel_rotacion "varchar(10): alta, media, baja"
        decimal indice_rotacion "decimal(8,2)"
        varchar periodo_calculo "varchar(7), formato AAAA-MM"
    }
```

## Tablas

| Tabla | Propósito |
|---|---|
| `umbral_stock` | Nivel mínimo configurable por producto o bodega. |
| `temporada` | Temporadas con su multiplicador de demanda. |
| `alerta` | Alertas generadas por el sistema y su estado de atención. |
| `sugerencia_reabastecimiento` | Recomendación de compra derivada de una alerta. |
| `resumen_ventas_producto` | Copia resumida del historial de ventas por producto y período. |
| `clasificacion_producto` | Resultado del análisis de rotación y clasificación A, B o C. |

## Relaciones

| Origen | Destino | Cardinalidad | Tipo |
|---|---|---|---|
| `sugerencia_reabastecimiento.alerta_id` | `alerta.id` | N:1 | Llave foránea interna |

## Referencias lógicas (sin llave foránea)

| Campo | Servicio dueño del dato |
|---|---|
| `producto_id` | Productos |
| `bodega_id` | Inventario |
| `proveedor_id` | Proveedores y Compras |
| `orden_compra_id` | Proveedores y Compras |
| `usuario_atencion_id` | API Gateway y Usuarios |