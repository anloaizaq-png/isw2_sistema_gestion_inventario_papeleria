# API Gateway y Microservicio de Identidad (`gateway-service`)

Microservicio de autenticación, gestión de usuarios, roles, permisos y enrutamiento inverso (API Gateway) para el proyecto **Sistema de Gestión de Inventarios - Cotton Cloud Paper**.

## Stack Tecnológico
- **Runtime:** Node.js (v20+) nativo (sin Express).
- **Módulos nativos:** `http`, `crypto`, `fetch`.
- **Dependencias de producción:**
  - `mysql2`: Cliente de base de datos MySQL con soporte de promesas.
  - `jsonwebtoken`: Emisión y validación de Access Tokens JWT.
  - `bcryptjs`: Hashing seguro de contraseñas.
- **Base de Datos:** MySQL 8 (`identidad`).

---

## Estructura del Proyecto

```
api-gateway/
├── .env.example              # Variables de entorno de referencia
├── package.json              # Configuración y dependencias de Node.js
├── README.md                 # Documentación del microservicio
├── sql/
│   ├── 01_schema.sql         # Esquema DDL con las 8 tablas de la BD identidad
│   └── 02_seed.sql           # Seed inicial SQL idempotente (roles, permisos, admin)
├── src/
│   ├── config/
│   │   └── index.js          # Configuración y lectura de variables de entorno
│   ├── db/
│   │   ├── connection.js     # Pool de conexiones MySQL y reintentos de arranque
│   │   ├── initDb.js         # Ejecutor de migración y seed inicial
│   │   ├── schema.sql        # Esquema DDL de referencia para initDb
│   │   └── seed.js           # Lógica idempotente de inserción de roles, permisos y admin
│   ├── middlewares/
│   │   ├── auth.js           # Validación Bearer JWT, sesión activa y usuario activo
│   │   └── rbac.js           # Guards de autorización por permisos y roles
│   ├── proxy/
│   │   └── reverseProxy.js   # Proxy inverso con streams nativos y manejo de 502/503
│   ├── routes/
│   │   ├── authRoutes.js     # Rutas /api/auth/*
│   │   ├── userRoutes.js     # Rutas /api/usuarios/*
│   │   ├── roleRoutes.js     # Rutas /api/roles/* y /api/permisos
│   │   └── proxyRoutes.js    # Tabla de enrutamiento hacia los 5 microservicios
│   ├── services/
│   │   ├── authService.js    # Lógica de login, refresh, logout, me, reset/change password
│   │   ├── userService.js    # CRUD de usuarios, paginación, unicidad de correo
│   │   └── roleService.js    # Consulta de roles, asignación de permisos
│   ├── utils/
│   │   ├── http.js           # Utilidades HTTP (body parser, respuestas JSON, IPs, UUID, SHA256)
│   │   ├── rateLimiter.js    # Limitador de tasa en memoria (protección fuerza bruta)
│   │   └── security.js       # Hashing bcrypt y generación/verificación JWT
│   ├── router.js             # Despachador de rutas nativo (internas + proxy inverso)
│   └── server.js             # Servidor HTTP nativo y punto de entrada
└── tests/
    ├── auth.test.js          # Pruebas unitarias de tokens, contraseñas y rate-limit
    ├── rbac.test.js          # Pruebas unitarias de control de acceso RBAC
    ├── proxy.test.js         # Pruebas unitarias de reverse proxy y cabeceras
    └── runTests.js           # Ejecutor integral de pruebas
```

---

## 3. Reverse Proxy Nativo y Enrutamiento

El Gateway redirige las peticiones entrantes hacia los microservicios correspondientes conservando el método HTTP, query params, cabeceras y cuerpo mediante streams nativos de `http.request`:

| Ruta Externa | Microservicio Destino | Variable de Entorno | Permiso Requerido | Acceso Público |
| :--- | :--- | :--- | :--- | :--- |
| `/api/productos/*` | `productos-service:8080` | `PRODUCTOS_URL` | `productos:*` | Sí (`GET` catálogo) |
| `/api/inventario/*` | `inventario-service:8080` | `INVENTARIO_URL` | `inventario:*` | No (Protegido) |
| `/api/ventas/*` | `ventas-service:8080` | `VENTAS_URL` | `ventas:*` | No (Protegido) |
| `/api/compras/*` | `compras-service:8080` | `COMPRAS_URL` | `compras:*` | No (Protegido) |
| `/api/alertas/*` | `analitica-service:8080` | `ANALITICA_URL` | `alertas:*` | No (Protegido) |

### Propagación de Identidad y Auditoría
En todas las peticiones reenviadas, el Gateway inyecta las siguientes cabeceras internas para auditoría de los microservicios:
- `X-User-Id`: ID numérico del usuario autenticado.
- `X-User-Roles`: Lista de roles separados por coma (ej. `ADMIN`, `VENDEDOR`).
- `X-User-Permissions`: Lista de permisos separados por coma (ej. `productos:*,inventario:*`).
- `X-Request-Id`: Identificador único UUID de rastreo de la petición.

### Resiliencia y Manejo de Errores
- **503 Service Unavailable:** Si el microservicio de destino se encuentra caído o detenido (`ECONNREFUSED`, `ENOTFOUND`).
- **504 Gateway Timeout:** Si el microservicio de destino supera el tiempo límite de respuesta (`PROXY_TIMEOUT_MS`).
- **502 Bad Gateway:** Si ocurre una interrupción de conexión o respuesta truncada.
- Las fallas en un microservicio destino no afectan al Gateway ni a los otros servicios activos.
