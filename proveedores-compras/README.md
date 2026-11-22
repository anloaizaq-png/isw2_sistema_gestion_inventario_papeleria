# Microservicio de Proveedores y Compras (`compras-service`)

Proveedores, órdenes de compra, recepciones de mercancía y devoluciones a proveedores.

## Stack
Python 3.11, FastAPI, SQLAlchemy 2.x, PyMySQL, httpx, MySQL 8 (base de datos propia `compras`).

## Endpoints (`/api/compras/...`)
- Proveedores: `POST | GET /proveedores`, `GET | PUT | DELETE /proveedores/{id}` (`DELETE` es una baja lógica)
- Productos del proveedor: `POST | GET /proveedores/{id}/productos`
- Órdenes de compra: `POST | GET /ordenes-compra`, `GET /ordenes-compra/sugeridas`, `GET /ordenes-compra/{id}`,
  `PUT /ordenes-compra/{id}/recibir`, `PUT /ordenes-compra/{id}/cancelar`
- Devoluciones a proveedor: `POST | GET /devoluciones-proveedor`, `GET /devoluciones-proveedor/{id}`
- `GET /health`

Documentación interactiva (Swagger): `/api/compras/docs`.

## Integración con otros servicios (REST)
- **Productos:** valida que el producto exista y esté activo.
- **Inventario:** registra una `ENTRADA` al recibir mercancía y una `SALIDA` al devolver al proveedor. Usa un
  identificador de operación fijo por movimiento, de modo que un reintento no duplica el stock.
- **Alertas y Analítica:** consulta las sugerencias de reabastecimiento y marca como atendida la sugerencia que originó una orden.

Las devoluciones a proveedor de este servicio son distintas de las devoluciones de clientes, que corresponden a Ventas y Pedidos.

## Variables de entorno

| Variable | Descripción |
| --- | --- |
| `DB_HOST` | Host de la base de datos MySQL |
| `DB_PORT` | Puerto de MySQL |
| `DB_NAME` | Nombre de la base de datos (`compras`) |
| `DB_USER` | Usuario de la base de datos |
| `DB_PASSWORD` | Contraseña de la base de datos |
| `PRODUCTOS_URL` | URL interna del servicio de Productos |
| `INVENTARIO_URL` | URL interna del servicio de Inventario |
| `ALERTAS_URL` | URL interna del servicio de Alertas y Analítica |
| `PORT` | Puerto interno del servicio (por defecto `8080`) |

Los valores de `.env.example` son solo para desarrollo local. En cualquier otro entorno, la contraseña
debe definirse mediante variables de entorno o secretos, y el archivo `.env` real no se versiona.

## Ejecución local
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --port 5004
```

## Docker
```bash
docker build -t compras-service .
```