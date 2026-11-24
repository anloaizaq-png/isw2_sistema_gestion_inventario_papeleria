
USE `identidad`;

-- 1. Roles base
INSERT INTO `rol` (`nombre`, `descripcion`) VALUES
  ('ADMIN', 'Administrador con acceso total al sistema'),
  ('OPERADOR_INVENTARIO', 'Operador con acceso al inventario y catálogo de productos'),
  ('VENDEDOR', 'Vendedor con acceso a gestión de pedidos, ventas y productos'),
  ('COMPRADOR', 'Comprador con acceso a proveedores, compras y productos'),
  ('ANALISTA', 'Analista con acceso a reportes, alertas e indicadores')
ON DUPLICATE KEY UPDATE `descripcion` = VALUES(`descripcion`);

-- 2. Permisos base
INSERT INTO `permiso` (`codigo`, `descripcion`) VALUES
  ('usuarios:administrar', 'Administrar usuarios, roles y permisos de acceso'),
  ('productos:*', 'Acceso y gestión completa de productos y categorías'),
  ('inventario:*', 'Acceso y control de movimientos, stock y almacén'),
  ('ventas:*', 'Acceso a registro y consulta de ventas y pedidos'),
  ('compras:*', 'Acceso a gestión de proveedores y órdenes de compra'),
  ('alertas:*', 'Acceso a alertas de stock y analítica de datos')
ON DUPLICATE KEY UPDATE `descripcion` = VALUES(`descripcion`);

-- 3. Asignación de permisos a roles
-- ADMIN -> todos los permisos
INSERT IGNORE INTO `rol_permiso` (`rol_id`, `permiso_id`)
SELECT r.`id`, p.`id`
FROM `rol` r
CROSS JOIN `permiso` p
WHERE r.`nombre` = 'ADMIN';

-- OPERADOR_INVENTARIO -> inventario:*, productos:*
INSERT IGNORE INTO `rol_permiso` (`rol_id`, `permiso_id`)
SELECT r.`id`, p.`id`
FROM `rol` r
JOIN `permiso` p ON p.`codigo` IN ('inventario:*', 'productos:*')
WHERE r.`nombre` = 'OPERADOR_INVENTARIO';

-- VENDEDOR -> ventas:*, productos:*
INSERT IGNORE INTO `rol_permiso` (`rol_id`, `permiso_id`)
SELECT r.`id`, p.`id`
FROM `rol` r
JOIN `permiso` p ON p.`codigo` IN ('ventas:*', 'productos:*')
WHERE r.`nombre` = 'VENDEDOR';

-- COMPRADOR -> compras:*, productos:*
INSERT IGNORE INTO `rol_permiso` (`rol_id`, `permiso_id`)
SELECT r.`id`, p.`id`
FROM `rol` r
JOIN `permiso` p ON p.`codigo` IN ('compras:*', 'productos:*')
WHERE r.`nombre` = 'COMPRADOR';

-- ANALISTA -> alertas:*, productos:*, inventario:*, ventas:*, compras:*
INSERT IGNORE INTO `rol_permiso` (`rol_id`, `permiso_id`)
SELECT r.`id`, p.`id`
FROM `rol` r
JOIN `permiso` p ON p.`codigo` IN ('alertas:*', 'productos:*', 'inventario:*', 'ventas:*', 'compras:*')
WHERE r.`nombre` = 'ANALISTA';

-- 4. Usuario Administrador Inicial
-- Password por defecto: Admin1234* (hash bcrypt con costo 10)
INSERT INTO `usuario` (`nombre`, `correo`, `password_hash`, `activo`)
VALUES (
  'Administrador Inicial',
  'admin@cottoncloud.com',
  '$2b$10$tOYS7LoUz7smfOV2eaaN4u.Y3koS7ykTfUmvqIY3yAZ2JtaCSUP3O',
  TRUE
)
ON DUPLICATE KEY UPDATE `nombre` = VALUES(`nombre`);

-- Asignar rol ADMIN al usuario administrador inicial
INSERT IGNORE INTO `usuario_rol` (`usuario_id`, `rol_id`)
SELECT u.`id`, r.`id`
FROM `usuario` u
JOIN `rol` r ON r.`nombre` = 'ADMIN'
WHERE u.`correo` = 'admin@cottoncloud.com';
