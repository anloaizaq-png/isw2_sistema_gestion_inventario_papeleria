# Sistema de Gestión de Inventarios - Cotton Cloud Paper

Sistema distribuido basado en microservicios contenerizados para la gestión integral de inventarios, compras, ventas, alertas y analítica de la papelería **Cotton Cloud Paper**.

---

## Arquitectura de Microservicios

1. **API Gateway y Servicio de Identidad (`api-gateway`):**
   - Único punto de entrada público expuesto al host en `http://localhost:8080`.
   - Autenticación JWT, renovación con rotación obligatoria, control de acceso RBAC, rate limiting contra fuerza bruta y reverse proxy nativo en Node.js.
   - Base de datos aislada: `identidad` (MySQL 8).
2. **Productos (`productos`):** Catálogo de artículos, categorías y precios.
3. **Inventario (`inventario`):** Control de existencias, almacén y movimientos.
4. **Ventas y Pedidos (`ventas-pedidos`):** Registro de pedidos y ventas.
5. **Proveedores y Compras (`proveedores-compras`):** Gestión de proveedores y órdenes de compra.
6. **Alertas y Analítica (`alertas-analitica`):** Indicadores, analítica y alertas de stock.

---

## Despliegue con Docker Compose

### 1. Variables de entorno
```bash
cp .env.example .env
```

### 2. Levantar el ecosistema completo
```bash
docker compose up --build
```

### 3. Levantar únicamente el Gateway y su Base de Datos
```bash
docker compose up --build gateway-service db-identidad
```

### 4. Verificar salud del servicio
```bash
curl http://localhost:8080/health
```

---

## Guía de Integración para el Equipo

Para conocer los detalles sobre cómo cada integrante conecta su microservicio, las cabeceras internas de auditoría (`X-User-*`) y el mapa de bases de datos, consulta la [Guía de Integración](file:///home/vanessa/Documentos/isw2_sistema_gestion_inventario_papeleria/docs/GUIA_INTEGRACION.md).
