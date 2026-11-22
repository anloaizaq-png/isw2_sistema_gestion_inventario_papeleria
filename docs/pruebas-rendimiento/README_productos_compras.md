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

Ejecución local (un proceso Uvicorn por servicio, bases MySQL en Docker, Locust en el mismo equipo). Fecha: 22/11/2026.

| Código | Usuarios | RPS | Media (ms) | p95 (ms) | p99 (ms) | % fallos | Criterio | Resultado |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| PC-01 | 1 | 3.03 | 15 | 19 | 27 | 0 | 200 y JSON válido | Cumple |
| PC-02 | 100 | 213.99 | 100 | 250 | 310 | 0 | 200/404, sin 500 | Cumple |
| PC-03 | 20 | 59.19 | 27 | 54 | 80 | 0 | 201 únicos / 409 duplicados | Cumple |
| PC-04 | 50 | 140.15 | 30 | 78 | 160 | 0 | Filtros correctos | Cumple |
| PC-05 | 20 | 59.24 | 29 | 60 | 79 | 0 | Registro consistente | Cumple |
| PC-06 | 10 | 71.44 (3 peticiones por ciclo) | 34 | 55 | 420 | 0 | Queda `inactivo` y consultable | Cumple |
| PC-07 | 50 | 147.23 | 12 | 28 | 62 | 0 | 200 | Cumple |
| PC-08 | 20 | 109.29 | 27 | 54 | 78 | 0 | Subcategoría ligada al padre | Cumple |
| PC-09 | 10 | 30.09 | 24 | 39 | 47 | 0 | Sin 500 | Cumple |
| PC-09 | 25 | 75.80 | 22 | 46 | 61 | 0 | Sin 500 | Cumple |
| PC-09 | 50 | 139.80 | 42 | 150 | 300 | 0 | Sin 500 | Cumple |
| PC-09 | 75 | 147.03 | 180 | 390 | 690 | 0 | Sin 500 | Cumple (degradación) |
| PC-09 | 100 | 152.93 | 292 | 670 | 1200 | 0 | Sin 500 | Cumple (degradación) |
| PC-10 | 50 | 145.88 | 15 | 35 | 100 | 0 | 200; filtros correctos | Cumple |
| PC-11 | 20 | 62.04 | 16 | 30 | 39 | 0 | 200/404, sin degradación (2 min, preliminar) | Cumple |
| PC-12 | 20 | 58.57 | 31 | 110 | 190 | 0 | 201 / 422 | Cumple |
| PC-13 | 20 | 38.25 | 209 | 410 | 550 | 0 | Total = suma(cantidad × precio) | Cumple |
| PC-14 | 10 | 60.62 | 114 | 300 | 910 | 0 | Estado y 409 correctos | Cumple |
| PC-15 pico | 200 | 122.06 | 1223 | 1500 | 18000 | 0 | Sin pérdida de datos | Cumple, con hallazgo |
| PC-15 recuperación | 10 | 21.03 | 92 | 360 | 470 | 0 | Se recupera sin intervención | Cumple |

## 5. Análisis

- **Consultas, creaciones y actualizaciones:** todas respondieron muy por debajo de los 2 s del RNF06, con 0 fallos.
- **Estrés (PC-09):** el servicio se degrada de forma gradual entre 50 y 75 usuarios y se estanca en unas 150 peticiones por segundo. No hubo errores 500 ni pérdida de datos. El límite corresponde a un solo proceso de Uvicorn.
- **Pico (PC-15):** el listado `GET /api/compras/proveedores` no está paginado y, con más de 2.800 proveedores creados por las pruebas, tardó 15,8 s de media con 200 usuarios. El servicio se recuperó al bajar a 10 usuarios (227 ms) sin intervención.
- **Optimizaciones propuestas para la Entrega 4:** paginar los listados de proveedores y categorías, y ejecutar varias réplicas de cada servicio en Kubernetes para escalar la capacidad de lectura (RNF05).
- **PC-11** se ejecutó 2 minutos en esta entrega; la prueba completa de 10 minutos queda para la Entrega 4.