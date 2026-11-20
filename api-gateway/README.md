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
│   ├── routes/
│   │   ├── authRoutes.js     # Rutas /api/auth/*
│   │   ├── userRoutes.js     # Rutas /api/usuarios/*
│   │   └── roleRoutes.js     # Rutas /api/roles/* y /api/permisos
│   ├── services/
│   │   ├── authService.js    # Lógica de login, refresh, logout, me, reset/change password
│   │   ├── userService.js    # CRUD de usuarios, paginación, unicidad de correo
│   │   └── roleService.js    # Consulta de roles, asignación de permisos
│   ├── utils/
│   │   ├── http.js           # Utilidades HTTP (body parser, respuestas JSON, IPs, UUID, SHA256)
│   │   ├── rateLimiter.js    # Limitador de tasa en memoria (protección fuerza bruta)
│   │   └── security.js       # Hashing bcrypt y generación/verificación JWT
│   ├── router.js             # Despachador de rutas nativo
│   └── server.js             # Servidor HTTP nativo y punto de entrada
└── tests/
    ├── auth.test.js          # Pruebas unitarias de tokens, contraseñas y rate-limit
    ├── rbac.test.js          # Pruebas unitarias de control de acceso RBAC
    └── runTests.js           # Ejecutor de pruebas
```

---

## Base de Datos Aislada: `identidad`

El microservicio utiliza exclusivamente la base de datos `identidad` con sus **8 tablas**:
1. `usuario`: Cuentas de usuario con correo único, hash de contraseña y estado activo.
2. `rol`: Roles del sistema (`ADMIN`, `OPERADOR_INVENTARIO`, `VENDEDOR`, `COMPRADOR`, `ANALISTA`).
3. `permiso`: Códigos de permiso (`usuarios:administrar`, `productos:*`, `inventario:*`, etc.).
4. `rol_permiso`: Asociación N:M entre roles y permisos.
5. `usuario_rol`: Asociación N:M entre usuarios y roles.
6. `sesion`: Registro de sesiones activas, tokens de refresco hasheados y revocaciones.
7. `recuperacion_contrasena`: Tokens de restablecimiento temporal de contraseñas.
8. `evento_autenticacion`: Registro de auditoría de intentos de login, logout, refresh y fallos.

---

## Endpoints Implementados (Paso 2)

### 1. Autenticación (`/api/auth/*`)
- `POST /api/auth/login` [Público]: Valida credenciales y usuario activo. Genera Access Token JWT (15 min) y Refresh Token (7 días) persistido con hash en `sesion`. Registra evento de auditoría y aplica rate limiting por correo/IP.
- `POST /api/auth/refresh` [Público con refresh token]: Valida el hash no revocado/expirado. Ejecuta **rotación obligatoria** (revoca token anterior y emite nuevo par). Si se detecta reutilización de un token rotado, revoca de inmediato todas las sesiones del usuario.
- `POST /api/auth/logout` [Autenticado]: Marca la sesión como revocada en `sesion`.
- `GET /api/auth/me` [Autenticado]: Retorna perfil del usuario autenticado con sus roles y permisos consolidados.
- `POST /api/auth/password/forgot` [Público con control de intentos]: Genera token de recuperación de expiración corta sin filtrar existencia de correo.
- `POST /api/auth/password/reset` [Token válido]: Valida token no usado/expirado, actualiza `password_hash`, marca token como usado y revoca sesiones activas.
- `POST /api/auth/password/change` [Autenticado]: Valida contraseña actual y actualiza contraseña.

### 2. Usuarios (`/api/usuarios/*`)
- `GET /api/usuarios` [Permiso `usuarios:administrar`]: Listado paginado de usuarios con sus roles (`?page=1&limit=10&search=...`).
- `POST /api/usuarios` [Permiso `usuarios:administrar`]: Creación de usuario. Valida unicidad de correo retornando `409 Conflict` en duplicados.
- `GET /api/usuarios/:id` [Permiso `usuarios:administrar`]: Perfil detallado de un usuario con roles y permisos.
- `PATCH /api/usuarios/:id` [Permiso `usuarios:administrar`]: Actualización parcial (nombre, correo, password, estado `activo`, roles).

### 3. Roles y Permisos (`/api/roles/*`, `/api/permisos`)
- `GET /api/roles` [Permiso `usuarios:administrar`]: Listado de todos los roles y sus permisos asociados.
- `GET /api/roles/:id` [Permiso `usuarios:administrar`]: Consulta de un rol específico.
- `PUT /api/roles/:id/permisos` [Permiso `usuarios:administrar`]: Asignación y sincronización de permisos por rol.
- `GET /api/permisos` [Permiso `usuarios:administrar`]: Catálogo completo de permisos disponibles.
