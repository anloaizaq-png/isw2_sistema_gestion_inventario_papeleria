'use strict';

const bcrypt = require('bcryptjs');
const config = require('../config');

// Roles base requeridos por la especificación
const ROLES = [
  { nombre: 'ADMIN', descripcion: 'Administrador con acceso total al sistema' },
  { nombre: 'OPERADOR_INVENTARIO', descripcion: 'Operador con acceso al inventario y catálogo de productos' },
  { nombre: 'VENDEDOR', descripcion: 'Vendedor con acceso a gestión de pedidos, ventas y productos' },
  { nombre: 'COMPRADOR', descripcion: 'Comprador con acceso a proveedores, compras y productos' },
  { nombre: 'ANALISTA', descripcion: 'Analista con acceso a reportes, alertas e indicadores' }
];

// Permisos base requeridos por la especificación
const PERMISOS = [
  { codigo: 'usuarios:administrar', descripcion: 'Administrar usuarios, roles y permisos de acceso' },
  { codigo: 'productos:*', descripcion: 'Acceso y gestión completa de productos y categorías' },
  { codigo: 'inventario:*', descripcion: 'Acceso y control de movimientos, stock y almacén' },
  { codigo: 'ventas:*', descripcion: 'Acceso a registro y consulta de ventas y pedidos' },
  { codigo: 'compras:*', descripcion: 'Acceso a gestión de proveedores y órdenes de compra' },
  { codigo: 'alertas:*', descripcion: 'Acceso a alertas de stock y analítica de datos' }
];

// Asignación de permisos por rol
const ROLE_PERMISOS = {
  ADMIN: [
    'usuarios:administrar',
    'productos:*',
    'inventario:*',
    'ventas:*',
    'compras:*',
    'alertas:*'
  ],
  OPERADOR_INVENTARIO: [
    'inventario:*',
    'productos:*'
  ],
  VENDEDOR: [
    'ventas:*',
    'productos:*'
  ],
  COMPRADOR: [
    'compras:*',
    'productos:*'
  ],
  ANALISTA: [
    'alertas:*',
    'productos:*',
    'inventario:*',
    'ventas:*',
    'compras:*'
  ]
};

/**
 * Ejecuta el seed inicial de forma idempotente en la base de datos `identidad`
 */
async function seed(pool) {
  console.log('[SEED] Iniciando seed inicial idempotente...');

  // 1. Insertar roles base
  for (const rol of ROLES) {
    await pool.execute(
      `INSERT INTO \`rol\` (\`nombre\`, \`descripcion\`)
       VALUES (?, ?)
       ON DUPLICATE KEY UPDATE \`descripcion\` = VALUES(\`descripcion\`)`,
      [rol.nombre, rol.descripcion]
    );
  }

  // 2. Insertar permisos base
  for (const permiso of PERMISOS) {
    await pool.execute(
      `INSERT INTO \`permiso\` (\`codigo\`, \`descripcion\`)
       VALUES (?, ?)
       ON DUPLICATE KEY UPDATE \`descripcion\` = VALUES(\`descripcion\`)`,
      [permiso.codigo, permiso.descripcion]
    );
  }

  // 3. Mapear IDs de roles y permisos
  const [dbRoles] = await pool.query('SELECT `id`, `nombre` FROM `rol`');
  const [dbPermisos] = await pool.query('SELECT `id`, `codigo` FROM `permiso`');

  const roleMap = new Map(dbRoles.map(r => [r.nombre, r.id]));
  const permisoMap = new Map(dbPermisos.map(p => [p.codigo, p.id]));

  // 4. Asignar permisos a cada rol de forma idempotente
  for (const [roleName, permisosList] of Object.entries(ROLE_PERMISOS)) {
    const roleId = roleMap.get(roleName);
    if (!roleId) continue;

    for (const permisoCodigo of permisosList) {
      const permisoId = permisoMap.get(permisoCodigo);
      if (!permisoId) continue;

      await pool.execute(
        `INSERT IGNORE INTO \`rol_permiso\` (\`rol_id\`, \`permiso_id\`)
         VALUES (?, ?)`,
        [roleId, permisoId]
      );
    }
  }

  // 5. Crear o actualizar usuario administrador inicial configurable
  const { name: adminName, email: adminEmail, password: adminPassword } = config.adminSeed;
  const passwordHash = await bcrypt.hash(adminPassword, 10);

  const [existingUsers] = await pool.execute(
    'SELECT `id` FROM `usuario` WHERE `correo` = ?',
    [adminEmail]
  );

  let adminUserId;
  if (existingUsers.length > 0) {
    adminUserId = existingUsers[0].id;
    await pool.execute(
      'UPDATE `usuario` SET `nombre` = ?, `activo` = TRUE WHERE `id` = ?',
      [adminName, adminUserId]
    );
    console.log(`[SEED] Usuario administrador existente verificado: ${adminEmail} (ID: ${adminUserId})`);
  } else {
    const [result] = await pool.execute(
      `INSERT INTO \`usuario\` (\`nombre\`, \`correo\`, \`password_hash\`, \`activo\`)
       VALUES (?, ?, ?, TRUE)`,
      [adminName, adminEmail, passwordHash]
    );
    adminUserId = result.insertId;
    console.log(`[SEED] Usuario administrador creado exitosamente: ${adminEmail} (ID: ${adminUserId})`);
  }

  // 6. Asignar rol ADMIN al administrador
  const adminRoleId = roleMap.get('ADMIN');
  if (adminRoleId && adminUserId) {
    await pool.execute(
      `INSERT IGNORE INTO \`usuario_rol\` (\`usuario_id\`, \`rol_id\`)
       VALUES (?, ?)`,
      [adminUserId, adminRoleId]
    );
  }

  console.log('[SEED] Seed inicial idempotente completado con éxito.');
}

module.exports = {
  seed,
  ROLES,
  PERMISOS,
  ROLE_PERMISOS
};
