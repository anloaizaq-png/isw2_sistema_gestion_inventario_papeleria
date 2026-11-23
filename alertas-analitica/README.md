# Microservicio Alertas y Analítica

Sistema de Gestión de Inventarios – Cotton Cloud Paper.
Responsable: Salomé Arroyave Urrea.

Genera alertas de bajo inventario mediante reglas configurables (sin inteligencia artificial),
administra umbrales de stock mínimo y temporadas de demanda, ofrece sugerencias de
reabastecimiento a Proveedores y Compras y calcula indicadores de rotación y clasificación ABC.

## Tecnologías

| Elemento | Valor |
|---|---|
| Lenguaje | Python 3.12 |
| Framework | Flask |
| Base de datos | MySQL 8.0, base `analitica` (propia del servicio, RNF02) |
| Acceso a datos | PyMySQL con SQL directo |
| Servidor en el contenedor | gunicorn (2 procesos) |
| Puerto interno | 8080 (Entrega 2, Tabla 3) |

## Estructura

```
alertas-analitica/
├── app.py              Aplicación Flask, formato de errores y ruta /salud
├── config.py           Lectura de variables de entorno
├── database.py         Conexión y consultas a MySQL
├── rutas/
│   ├── umbrales.py     /api/alertas/umbrales
│   ├── temporadas.py   /api/alertas/temporadas
│   ├── alertas.py      /api/alertas/
│   └── sugerencias.py  /api/alertas/sugerencias-reabastecimiento
├── db/schema.sql       Creación de la base de datos y sus 6 tablas
├── requirements.txt    Dependencias
├── .env.example        Ejemplo de variables de entorno
├── Dockerfile          Imagen del servicio
└── .dockerignore       Archivos excluidos de la imagen
```

## Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `APP_PORT` | Puerto del servicio | `8080` |
| `DB_HOST` | Servidor MySQL | `analitica-db` |
| `DB_PORT` | Puerto de MySQL | `3306` |
| `DB_USER` | Usuario de MySQL | `analitica_user` |
| `DB_PASSWORD` | Contraseña de MySQL | — |
| `DB_NAME` | Nombre de la base | `analitica` |
| `INVENTARIO_URL` | Dirección interna de Inventario | `http://inventario-service:8080` |
| `VENTAS_URL` | Dirección interna de Ventas y Pedidos | `http://ventas-service:8080` |

El archivo `.env` con los valores reales no se sube al repositorio.

## Endpoints

Todas las rutas usan el prefijo `/api/alertas/` y se acceden a través del API Gateway.
El contrato completo está en el contrato OpenAPI del servicio (Entrega 2).

| Método | Ruta | Estado |
|---|---|---|
| GET | `/api/alertas/` | Implementado |
| GET | `/api/alertas/{id}` | Implementado |
| PATCH | `/api/alertas/{id}/estado` | Implementado |
| POST | `/api/alertas/evaluar` | Pendiente (requiere Inventario) |
| GET, POST | `/api/alertas/umbrales` | Implementado |
| PUT, DELETE | `/api/alertas/umbrales/{id}` | Implementado |
| GET, POST | `/api/alertas/temporadas` | Implementado |
| PUT, DELETE | `/api/alertas/temporadas/{id}` | Implementado |
| GET | `/api/alertas/analitica/rotacion` | Pendiente (requiere Ventas) |
| GET | `/api/alertas/analitica/clasificacion-abc` | Pendiente (requiere Ventas) |
| GET | `/api/alertas/analitica/proximos-agotarse` | Pendiente (requiere Inventario) |
| GET | `/api/alertas/analitica/sin-movimiento` | Pendiente (requiere Ventas) |
| GET | `/api/alertas/analitica/demanda-temporada` | Pendiente (requiere Ventas) |
| GET | `/api/alertas/sugerencias-reabastecimiento` | Implementado |
| PATCH | `/api/alertas/sugerencias-reabastecimiento/{id}/estado` | Implementado |

Además, `GET /salud` (fuera del contrato y del Gateway) indica si el servicio y la base de
datos responden.

Los errores responden con el formato `{"codigo": 404, "mensaje": "..."}`.

## Integración con los demás servicios

**API Gateway (Wendy).** El Gateway valida el token y los permisos y reenvía las rutas
`/api/alertas/...` sin cambios a `http://analitica-service:8080`. Si envía el encabezado
`X-Usuario-Id` con el id del usuario autenticado, el servicio lo guarda como
`usuario_atencion_id` al cambiar el estado de una alerta; si no lo envía, el campo queda vacío.

**Inventario y Ventas y Pedidos (Ana).** El servicio los consulta directamente por sus
direcciones internas (Entrega 2, sección 1.2). Necesita:

- De Inventario: el stock actual por producto (y por bodega, si aplica).
- De Ventas y Pedidos: las unidades vendidas por producto en un rango de fechas.

Las rutas exactas se agregarán cuando estén definidas.

**Proveedores y Compras (Angie).** Consume `GET /api/alertas/sugerencias-reabastecimiento`
y, al generar una orden de compra, `PATCH /api/alertas/sugerencias-reabastecimiento/{id}/estado`
con `{"estado": "atendida", "orden_compra_id": ...}`.

## Reglas de negocio

- **Estado de una alerta:** `pendiente` borra el usuario y la fecha de atención; `en_gestion`
  guarda el usuario; `atendida` o `descartada` guardan el usuario y la fecha actual.
- **Estado de una sugerencia:** `atendida` guarda el `orden_compra_id` recibido; `pendiente`
  lo borra.
- **Umbrales:** `DELETE` los desactiva (`activo = false`), no los borra.
- **Fechas:** se guardan en UTC.

## Ejecución local

```
cd alertas-analitica
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # y ajustar los valores
python app.py
```

Base de datos de prueba con Docker (crea las tablas con `db/schema.sql`):

```
docker run --name analitica-db-prueba -e MYSQL_ROOT_PASSWORD=root -p 3307:3306 \
  -v "$PWD/db:/docker-entrypoint-initdb.d" -d mysql:8.0
```

## Ejecución con Docker

```
docker build -t alertas-analitica .
docker run --rm -p 8080:8080 \
  -e DB_HOST=... -e DB_PORT=3306 -e DB_USER=... -e DB_PASSWORD=... -e DB_NAME=analitica \
  -e INVENTARIO_URL=http://inventario-service:8080 -e VENTAS_URL=http://ventas-service:8080 \
  alertas-analitica
```