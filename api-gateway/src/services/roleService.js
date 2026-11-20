'use strict';

const { getPool } = require('../db/connection');

/**
 * Servicio de consulta y gestión de Roles y Permisos (requiere usuarios:administrar)
 */

/**
 * Consulta de todos los roles junto con sus permisos vigentes
 * GET /api/roles
 */
async function listRoles() {
  const pool = getPool();

  const [roles] = await pool.execute(
    'SELECT `id`, `nombre`, `descripcion` FROM `rol` ORDER BY `id` ASC'
  );

  for (const rol of roles) {
    const [permisos] = await pool.execute(
      `SELECT p.\`id\`, p.\`codigo\`, p.\`descripcion\`
       FROM \`permiso\` p
       JOIN \`rol_permiso\` rp ON rp.\`permiso_id\` = p.\`id\`
       WHERE rp.\`rol_id\` = ?
       ORDER BY p.\`codigo\` ASC`,
      [rol.id]
    );
    rol.permisos = permisos.map(p => ({
      id: p.id,
      codigo: p.codigo,
      descripcion: p.descripcion
    }));
  }

  return roles;
}

/**
 * Consulta de un rol específico con sus permisos
 * GET /api/roles/:id
 */
async function getRoleById(id) {
  const pool = getPool();

  const [roles] = await pool.execute(
    'SELECT `id`, `nombre`, `descripcion` FROM `rol` WHERE `id` = ?',
    [id]
  );

  if (roles.length === 0) {
    const error = new Error(`Rol con ID ${id} no encontrado`);
    error.statusCode = 404;
    error.code = 'RoleNotFound';
    throw error;
  }

  const rol = roles[0];
  const [permisos] = await pool.execute(
    `SELECT p.\`id\`, p.\`codigo\`, p.\`descripcion\`
     FROM \`permiso\` p
     JOIN \`rol_permiso\` rp ON rp.\`permiso_id\` = p.\`id\`
     WHERE rp.\`rol_id\` = ?`,
    [rol.id]
  );
  rol.permisos = permisos;

  return rol;
}

/**
 * Asigna/sincroniza permisos a un rol
 * PUT /api/roles/:id/permisos
 */
async function assignPermissionsToRole(roleId, permissionCodesOrIds = []) {
  const pool = getPool();

  // Validar existencia de rol
  await getRoleById(roleId);

  // Eliminar permisos actuales del rol
  await pool.execute('DELETE FROM `rol_permiso` WHERE `rol_id` = ?', [roleId]);

  if (Array.isArray(permissionCodesOrIds) && permissionCodesOrIds.length > 0) {
    for (const item of permissionCodesOrIds) {
      let permId = null;
      if (typeof item === 'number') {
        permId = item;
      } else {
        const [rows] = await pool.execute(
          'SELECT `id` FROM `permiso` WHERE `codigo` = ?',
          [String(item).trim()]
        );
        if (rows.length > 0) {
          permId = rows[0].id;
        }
      }

      if (permId) {
        await pool.execute(
          'INSERT IGNORE INTO `rol_permiso` (`rol_id`, `permiso_id`) VALUES (?, ?)',
          [roleId, permId]
        );
      }
    }
  }

  return await getRoleById(roleId);
}

/**
 * Listado de todos los permisos disponibles en el sistema
 * GET /api/permisos
 */
async function listPermissions() {
  const pool = getPool();
  const [permisos] = await pool.execute(
    'SELECT `id`, `codigo`, `descripcion` FROM `permiso` ORDER BY `codigo` ASC'
  );
  return permisos;
}

module.exports = {
  listRoles,
  getRoleById,
  assignPermissionsToRole,
  listPermissions
};
