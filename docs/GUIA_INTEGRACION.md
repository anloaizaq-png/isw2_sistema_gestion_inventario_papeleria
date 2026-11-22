# Guía de Integración para el Equipo de Desarrollo
## Sistema de Gestión de Inventarios - Cotton Cloud Paper

Esta guía describe cómo cada integrante del equipo conecta su microservicio y base de datos con el ecosistema de contenedores gestionado por **Docker Compose** y el **API Gateway**.

---

## 1. Arquitectura de Despliegue y Red

El sistema utiliza una arquitectura contenerizada compuesta por:
- **Red interna (`cotton-net`):** Red tipo bridge privada en Docker donde conviven todos los servicios y bases de datos.
- **Punto único de entrada:** Únicamente `gateway-service` expone puerto al exterior (`8080:8080`).
- **Aislamiento de bases de datos:** Cada microservicio tiene su propio contenedor MySQL 8 independiente con volumen persistente (`cotton_db_*`). Ninguna base de datos expone puertos hacia la máquina host.

```
                         [ CLIENTES EXTERNOS / POSTMAN / LOCUST ]
                                            │
                                            ▼ Puerto 8080:8080
                                ┌───────────────────────┐
                                │    gateway-service    │
                                └───────────────────────┘
                                            │ (Red interna cotton-net)
        ┌───────────────┬───────────────────┼───────────────────┬───────────────┐
        ▼               ▼                   ▼                   ▼               ▼
┌──────────────┐ ┌──────────────┐   ┌──────────────┐    ┌──────────────┐ ┌──────────────┐
│  productos   │ │  inventario  │   │    ventas    │    │   compras    │ │  analitica   │
│   service    │ │   service    │   │   service    │    │   service    │ │   service    │
└──────┬───────┘ └──────┬───────┘   └──────┬───────┘    └──────┬───────┘ └──────┬───────┘
       │                │                  │                   │                │
       ▼                ▼                  ▼                   ▼                ▼
┌──────────────┐ ┌──────────────┐   ┌──────────────┐    ┌──────────────┐ ┌──────────────┐
│ db-productos │ │db-inventario │   │  db-ventas   │    │  db-compras  │ │ db-analitica │
└──────────────┘ └──────────────┘   └──────────────┘    └──────────────┘ └──────────────┘
```

---

## 2. Mapa de Carpetas y Contenedores

| Microservicio | Carpeta del Repo | Contenedor Servicio | Contenedor MySQL | Prefijo de Ruta |
| :--- | :--- | :--- | :--- | :--- |
| **Gateway e Identidad** | `./api-gateway` | `gateway-service` | `db-identidad` | `/api/auth`, `/api/usuarios`, `/api/roles` |
| **Productos** | `./productos` | `productos-service` | `db-productos` | `/api/productos` |
| **Inventario** | `./inventario` | `inventario-service` | `db-inventario` | `/api/inventario` |
| **Ventas y Pedidos** | `./ventas-pedidos` | `ventas-service` | `db-ventas` | `/api/ventas` |
| **Proveedores y Compras** | `./proveedores-compras` | `compras-service` | `db-compras` | `/api/compras` |
| **Alertas y Analítica** | `./alertas-analitica` | `analitica-service` | `db-analitica` | `/api/alertas` |

---

## 3. Requisitos para Cada Integrante

Para conectar tu microservicio al `docker-compose.yml`, debes cumplir con 3 requisitos sencillos en tu carpeta:

1. **Crear tu propio `Dockerfile`:**
   En la raíz de tu carpeta (ej. `productos/Dockerfile`), crea tu Dockerfile exponiendo el puerto `8080` interno:
   ```dockerfile
   EXPOSE 8080
   ```

2. **Conexión a tu Base de Datos MySQL:**
   Tu microservicio se conecta a su base de datos usando el nombre del contenedor en la red `cotton-net` (no uses `localhost`):
   - **Host:** `db-<tu-modulo>` (ej. `db-productos`, `db-inventario`, etc.)
   - **Puerto:** `3306`
   - **Usuario / Password / BD:** Según las variables definidas en [.env.example](file:///home/vanessa/Documentos/isw2_sistema_gestion_inventario_papeleria/.env.example).

3. **Prefijo de Endpoints:**
   Tus endpoints deben comenzar con `/api/<tu-dominio>/...` (ej. `/api/productos`, `/api/inventario/movimientos`), ya que el Gateway realiza enrutamiento transparente (*pass-through*).

---

## 4. Contrato de Cabeceras de Identidad y Auditoría

Para los servicios que requieren auditoría (`compras`, `inventario`, `ventas` y `alertas`), el Gateway valida el token JWT y reenvía automáticamente las siguientes cabeceras internas en cada petición:

- `X-User-Id`: ID numérico del usuario que ejecuta la acción (ej. `1`, `42`).
- `X-User-Roles`: Lista de roles asignados separados por coma (ej. `ADMIN`, `OPERADOR_INVENTARIO`).
- `X-User-Permissions`: Lista de permisos vigentes (ej. `inventario:*,productos:*`).
- `X-Request-Id`: UUID único para trazabilidad y correlación de logs entre microservicios.

> **Importante:** Tu microservicio no necesita validar firmas JWT; confía en las cabeceras `X-User-*` inyectadas por el Gateway, ya que ningún tráfico externo puede llegar directamente a tu servicio sin pasar por el Gateway.

---

## 5. Comandos para Levantar el Entorno

### Preparación Inicial
Copia el archivo de variables de entorno de ejemplo:
```bash
cp .env.example .env
```

### Levantar Todo el Ecosistema
```bash
docker compose up --build
```

### Levantar Únicamente el Gateway y su Base de Datos
Si deseas probar el Gateway de forma independiente antes de que los otros servicios tengan su Dockerfile listo:
```bash
docker compose up --build gateway-service db-identidad
```

### Probar Salud del Gateway
```bash
curl http://localhost:8080/health
```
Respuesta esperada:
```json
{
  "status": "UP",
  "service": "gateway-service",
  "environment": "production",
  "timestamp": "2026-11-21T..."
}
```

### Iniciar Sesión como Administrador
```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"correo": "admin@cottoncloud.com", "password": "Admin1234*"}'
```
Retorna `accessToken` y `refreshToken` para probar endpoints protegidos.
