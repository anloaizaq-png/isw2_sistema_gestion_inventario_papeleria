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
└── src/
    ├── config/
    │   └── index.js          # Configuración y lectura de variables de entorno
    ├── db/
    │   ├── connection.js     # Pool de conexiones MySQL y reintentos de arranque
    │   ├── initDb.js         # Ejecutor de migración y seed inicial
    │   ├── schema.sql        # Esquema DDL de referencia para initDb
    │   └── seed.js           # Lógica idempotente de inserción de roles, permisos y admin
    └── server.js             # Servidor HTTP nativo y punto de entrada
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

## Seed Inicial Idempotente

El seed crea automáticamente los datos iniciales necesarios sin duplicar registros al ejecutarse múltiples veces:
- **Roles:** `ADMIN`, `OPERADOR_INVENTARIO`, `VENDEDOR`, `COMPRADOR`, `ANALISTA`.
- **Permisos:** `usuarios:administrar`, `productos:*`, `inventario:*`, `ventas:*`, `compras:*`, `alertas:*`.
- **Usuario Administrador Inicial:**
  - Correo: `admin@cottoncloud.com` (o según variable `ADMIN_EMAIL`).
  - Contraseña: `Admin1234*` (o según variable `ADMIN_PASSWORD`).
  - Rol asignado: `ADMIN`.
