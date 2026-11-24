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
├── app.py              Aplicación Flask, formato de errores y ruta /health
├── config.py           Lectura de variables de entorno
├── database.py         Conexión y consultas a MySQL
├── clientes/
│   ├── inventario.py   Consulta el stock en Inventario
│   └── ventas.py       Consulta las ventas confirmadas en Ventas y Pedidos
├── rutas/
│   ├── umbrales.py     /api/alertas/umbrales
│   ├── temporadas.py   /api/alertas/temporadas
│   ├── alertas.py      /api/alertas/ (incluye /evaluar)
│   ├── sugerencias.py  /api/alertas/sugerencias-reabastecimiento
│   └── analitica.py    /api/alertas/analitica/...
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
| POST | `/api/alertas/evaluar` | Implementado |
| GET, POST | `/api/alertas/umbrales` | Implementado |
| PUT, DELETE | `/api/alertas/umbrales/{id}` | Implementado |
| GET, POST | `/api/alertas/temporadas` | Implementado |
| PUT, DELETE | `/api/alertas/temporadas/{id}` | Implementado |
| GET | `/api/alertas/analitica/rotacion` | Implementado |
| GET | `/api/alertas/analitica/clasificacion-abc` | Implementado |
| GET | `/api/alertas/analitica/proximos-agotarse` | Implementado |
| GET | `/api/alertas/analitica/sin-movimiento` | Implementado |
| GET | `/api/alertas/analitica/demanda-temporada` | Implementado |
| GET | `/api/alertas/sugerencias-reabastecimiento` | Implementado |
| PATCH | `/api/alertas/sugerencias-reabastecimiento/{id}/estado` | Implementado |

Además, `GET /health` (fuera del contrato y del Gateway) indica si el servicio y la base de
datos responden.

Los errores responden con el formato `{"codigo": 404, "mensaje": "..."}`.

## Integración con los demás servicios

**API Gateway (Wendy).** El Gateway valida el token y los permisos y reenvía las rutas
`/api/alertas/...` sin cambios a `http://analitica-service:8080`. Si envía el encabezado
`X-User-Id` (el mismo que usan los demás servicios) con el id del usuario autenticado, el servicio lo guarda como
`usuario_atencion_id` al cambiar el estado de una alerta; si no lo envía, el campo queda vacío.

**Inventario y Ventas y Pedidos (Ana).** El servicio los consulta directamente por sus
direcciones internas (Entrega 2, sección 1.2), nunca accediendo a sus bases de datos:

| Servicio | Ruta consumida | Uso |
|---|---|---|
| Inventario | `GET {INVENTARIO_URL}/api/inventario/stock` | Stock por producto y bodega (`evaluar`, rotación, próximos a agotarse, sin movimiento) |
| Ventas y Pedidos | `GET {VENTAS_URL}/api/ventas?estado=confirmada&fecha_inicio=...&fecha_fin=...` | Unidades e ingresos por producto (rotación, ABC, sin movimiento, demanda por temporada) |

Si alguno no responde, el endpoint que lo necesita responde `503`; si su respuesta no tiene
el formato esperado, responde `502`.

**Proveedores y Compras (Angie).** Consume `GET /api/alertas/sugerencias-reabastecimiento`
y, al generar una orden de compra, `PATCH /api/alertas/sugerencias-reabastecimiento/{id}/estado`
con `{"estado": "atendida", "orden_compra_id": ...}`.

## Reglas de negocio

- **Estado de una alerta:** `pendiente` borra el usuario y la fecha de atención; `en_gestion`
  guarda el usuario; `atendida` o `descartada` guardan el usuario y la fecha actual.
- **Estado de una sugerencia:** `atendida` guarda el `orden_compra_id` recibido; `pendiente`
  lo borra.
- **Umbrales:** `DELETE` los desactiva (`activo = false`), no los borra.
- **Evaluación (`POST /evaluar`, RF09):** para cada umbral activo se toma el stock de su
  bodega (o la suma de todas si no tiene bodega). Umbral aplicado = `stock_minimo` ×
  multiplicador de la temporada vigente (1 si no hay), redondeado hacia arriba. Si el stock
  es menor o igual, se crea una alerta `agotado` (stock 0) o `stock_bajo`, sin duplicar una
  alerta pendiente o en gestión del mismo producto y tipo, junto con una sugerencia de
  `2 × umbral aplicado − stock` unidades.
- **Rotación:** unidades vendidas ÷ stock actual. Los productos vendidos se dividen en tercios
  (`alta`, `media`, `baja`); los no vendidos son `baja`.
- **Clasificación ABC:** ingresos del mes en curso; A hasta el 80 % acumulado, B hasta el 95 %,
  C el resto. Se guarda en `clasificacion_producto` y `resumen_ventas_producto`.
- **Próximos a agotarse:** stock por encima del umbral aplicado, pero no más de un 25 %.
- **Sin movimiento:** productos con stock y sin ventas en los últimos `dias` (90 por defecto).
- **Ventas consideradas:** solo las confirmadas; las devoluciones no se descuentan.
- **Fechas:** se guardan y comparan en UTC.

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