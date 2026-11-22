# Microservicio de Productos (`productos-service`)

Catálogo de productos, categorías y subcategorías de Cotton Cloud Paper.

## Stack
Python 3.11, FastAPI, SQLAlchemy 2.x, PyMySQL, MySQL 8 (base de datos propia `productos`).

## Endpoints (`/api/productos/...`)
- `POST /api/productos`
- `GET /api/productos` (paginado, con filtros por categoría, proveedor y estado)
- `GET /api/productos/buscar` (por código, código de barras, nombre, categoría, marca y proveedor)
- `GET | PUT | PATCH | DELETE /api/productos/{id}` (`DELETE` es una baja lógica: el producto queda `inactivo`)
- `GET | POST /api/productos/categorias`
- `GET | PUT | DELETE /api/productos/categorias/{id}`
- `GET /health`

Documentación interactiva (Swagger): `/api/productos/docs`.

## Variables de entorno

| Variable | Descripción |
| --- | --- |
| `DB_HOST` | Host de la base de datos MySQL |
| `DB_PORT` | Puerto de MySQL |
| `DB_NAME` | Nombre de la base de datos (`productos`) |
| `DB_USER` | Usuario de la base de datos |
| `DB_PASSWORD` | Contraseña de la base de datos |
| `PORT` | Puerto interno del servicio (por defecto `8080`) |

Los valores de `.env.example` son solo para desarrollo local. En cualquier otro entorno, la contraseña
debe definirse mediante variables de entorno o secretos, y el archivo `.env` real no se versiona.

## Ejecución local
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --port 5001
```

## Docker
```bash
docker build -t productos-service .
```