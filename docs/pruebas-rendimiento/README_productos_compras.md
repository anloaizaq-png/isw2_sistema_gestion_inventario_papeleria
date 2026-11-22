# Pruebas de rendimiento: Productos y Proveedores/Compras (`PC-01` a `PC-15`)

Los 15 escenarios corresponden a la Tabla 21 del documento de la Entrega 2, ejecutados con Locust.
Script: `locustfile_productos_compras.py`. Cada escenario se ejecuta con `--tags`.

## 1. Escenarios

| Código | Endpoint | Tipo | Usuarios | Spawn rate | Duración | Qué se verifica |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| PC-01 | `GET /api/productos` | Humo | 1 | 1 | 10 s | 200, JSON válido con productos |
| PC-02 | `GET /api/productos/{id}` | Carga | 100 | 3 | 2 min | 200 existentes, 404 inexistentes, sin 500 |
| PC-03 | `POST /api/productos` | Concurrencia | 20 | 5 | 1 min | 201 con códigos únicos, 409 duplicados |
| PC-04 | `GET /api/productos/buscar` | Capacidad | 50 | 5 | 1 min | Cada filtro devuelve solo lo que cumple |
| PC-05 | `PUT /api/productos/{id}` | Concurrencia | 20 | 5 | 1 min | Registro consistente, sin 500 |
| PC-06 | `DELETE /api/productos/{id}` | Funcional bajo carga | 10 | 2 | 1 min | Queda `inactivo` y sigue consultable |
| PC-07 | `GET /api/productos/categorias` | Carga | 50 | 5 | 1 min | 200 en todas las respuestas |
| PC-08 | `POST /api/productos/categorias` | Integridad | 20 | 5 | 1 min | 201 y subcategoría ligada a su padre |
| PC-09 | `GET /api/productos` | Estrés | 10→25→50→75→100 | 10 | 1 min por nivel | Punto de degradación; solo 200/429/503 |
| PC-10 | `GET /api/compras/proveedores` | Carga | 50 | 5 | 1 min | 200; filtros por estado y nombre correctos |
| PC-11 | `GET /api/compras/proveedores/{id}` | Resistencia | 20 | 5 | 10 min | 200/404, sin degradación |
| PC-12 | `POST /api/compras/proveedores` | Concurrencia | 20 | 5 | 1 min | 201 NIT distinto, 422 NIT repetido |
| PC-13 | `POST /api/compras/ordenes-compra` | Consistencia | 20 | 5 | 1 min | 201; total = suma(cantidad × precio) |
| PC-14 | `PUT /api/compras/ordenes-compra/{id}/recibir` | Integración | 10 | 2 | 1 min | Cantidades, estado parcial/total y 409 si cerrada o cancelada |
| PC-15 | Productos y Compras a la vez | Pico y recuperación | 200 → 10 | 200 | 1 min + 1 min | Sin pérdida de datos; se recupera al bajar la carga |

## 2. Requisitos

1. Servicios y bases de datos corriendo (en local: Productos `:5001`, Compras `:5004`, Inventario `:5002` con la bodega `1`). Para PC-14 Inventario es obligatorio.
2. Locust: `pip install locust`. Si falla en tu versión de Python, usa Docker:
   `docker run --rm --network host -v "$PWD":/work -w /work locustio/locust ...` (mismos argumentos).
3. Apuntar al destino (directo, o el API Gateway cuando esté disponible):
   ```bash
   export PRODUCTOS_HOST=http://localhost:5001
   export COMPRAS_HOST=http://localhost:5004
   export BODEGA_ID=1
   ```

## 3. Ejecución (desde la raíz del repositorio)

```bash
correr() {   # uso: correr ETIQUETA CLASES USUARIOS SPAWN DURACION
  locust -f docs/pruebas-rendimiento/locustfile_productos_compras.py --headless \
    --tags "$1" --users "$3" --spawn-rate "$4" --run-time "$5" \
    --html "docs/pruebas-rendimiento/resultados/reporte_$1_$3u.html" $2
}

correr PC-01 ProductosUser 1 1 10s
correr PC-02 ProductosUser 100 3 2m
correr PC-03 ProductosUser 20 5 1m
correr PC-04 ProductosUser 50 5 1m
correr PC-05 ProductosUser 20 5 1m
correr PC-06 ProductosUser 10 2 1m
correr PC-07 ProductosUser 50 5 1m
correr PC-08 ProductosUser 20 5 1m
for u in 10 25 50 75 100; do correr PC-09 ProductosUser $u 10 1m; done
correr PC-10 ComprasUser 50 5 1m
correr PC-11 ComprasUser 20 5 10m
correr PC-12 ComprasUser 20 5 1m
correr PC-13 ComprasUser 20 5 1m
correr PC-14 ComprasUser 10 2 1m
correr PC-15 "ProductosUser ComprasUser" 200 200 1m   # pico
correr PC-15 "ProductosUser ComprasUser" 10 10 1m     # recuperación
```

Al terminar cada ejecución, Locust imprime una tabla con peticiones, fallos, tiempos (media, p50, p95, p99) y RPS. Esos valores se copian a la siguiente tabla.

## 4. Resultados preliminares

| Código | Usuarios | RPS | Media (ms) | p95 (ms) | p99 (ms) | % fallos | Criterio | Resultado |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| PC-01 | 1 | | | | | | 200 y JSON válido | |
| PC-02 | 100 | | | | | | 200/404, sin 500 | |
| PC-03 | 20 | | | | | | 201 / 409 | |
| PC-04 | 50 | | | | | | Filtros correctos | |
| PC-05 | 20 | | | | | | Registro consistente | |
| PC-06 | 10 | | | | | | Queda `inactivo` | |
| PC-07 | 50 | | | | | | 200 | |
| PC-08 | 20 | | | | | | Subcategoría ligada | |
| PC-09 | 10 a 100 | | | | | | Sin 500; recupera | |
| PC-10 | 50 | | | | | | 200; filtros correctos | |
| PC-11 | 20 | | | | | | 200/404; sin degradación | |
| PC-12 | 20 | | | | | | 201 / 422 | |
| PC-13 | 20 | | | | | | Total consistente | |
| PC-14 | 10 | | | | | | Estado y 409 correctos | |
| PC-15 | 200 → 10 | | | | | | Recupera sin intervención | |