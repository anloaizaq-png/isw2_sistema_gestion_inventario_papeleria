'use strict';

const { getPool } = require('../db/connection');
const { hashPassword } = require('../utils/security');

/**
 * Servicio de administración de usuarios (requiere permiso usuarios:administrar)
 */

/**
 * Listado paginado de usuarios
 * GET /api/usuarios?page=1&limit=10&search=...
 */
async function listUsers({ page = 1, limit = 10, search = '' }) {
  const pool = getPool();

  const pageNum = Math.max(1, parseInt(page, 10) || 1);
  const limitNum = Math.min(100, Math.max(1, parseInt(limit, 10) || 10));
  const offset = (pageNum - 1) * limitNum;

  let countSql = 'SELECT COUNT(*) as total FROM `usuario`';
  let querySql = `
    SELECT \`id\`, \`nombre\`, \`correo\`, \`activo\`, \`creado_en\`, \`actualizado_en\`
    FROM \`usuario\`
  `;
  const params = [];

  if (search && search.trim() !== '') {
    const term = `%${search.trim()}%`;
    countSql += ' WHERE `nombre` LIKE ? OR `correo` LIKE ?';
    querySql += ' WHERE `nombre` LIKE ? OR `correo` LIKE ?';
    params.push(term, term);
  }

  querySql += ' ORDER BY `id` ASC LIMIT ? OFFSET ?';

  const [countResult] = await pool.execute(countSql, params);
  const total = countResult[0].total;

  const [users] = await pool.query(querySql, [...params, limitNum, offset]);

  // Asociar roles a cada usuario
  for (const user of users) {
    const [roles] = await pool.execute(
      `SELECT r.\`id\`, r.\`nombre\`, r.\`descripcion\`
       FROM \`rol\` r
       JOIN \`usuario_rol\` ur ON ur.\`rol_id\` = r.\`id\`
       WHERE ur.\`usuario_id\` = ?`,
      [user.id]
    );
    user.activo = Boolean(user.activo);
    user.roles = roles.map(r => r.nombre);
  }

  return {
    data: users,
    pagination: {
      total,
      page: pageNum,
      limit: limitNum,
      totalPages: Math.ceil(total / limitNum)
    }
  };
}

/**
 * Consulta de perfil de usuario por ID
 * GET /api/usuarios/:id
 */
async function getUserById(id) {
  const pool = getPool();

  const [users] = await pool.execute(
    'SELECT `id`, `nombre`, `correo`, `activo`, `creado_en`, `actualizado_en` FROM `usuario` WHERE `id` = ?',
    [id]
  );

  if (users.length === 0) {
    const error = new Error(`Usuario con ID ${id} no encontrado`);
    error.statusCode = 404;
    error.code = 'UserNotFound';
    throw error;
  }

  const user = users[0];
  user.activo = Boolean(user.activo);

  // Obtener roles
  const [roles] = await pool.execute(
    `SELECT r.\`id\`, r.\`nombre\`, r.\`descripcion\`
     FROM \`rol\` r
     JOIN \`usuario_rol\` ur ON ur.\`rol_id\` = r.\`id\`
     WHERE ur.\`usuario_id\` = ?`,
    [id]
  );
  user.roles = roles.map(r => r.nombre);

  // Obtener permisos consolidados
  if (roles.length > 0) {
    const roleIds = roles.map(r => r.id);
    const placeholders = roleIds.map(() => '?').join(',');
    const [perms] = await pool.execute(
      `SELECT DISTINCT p.\`codigo\`, p.\`descripcion\`
       FROM \`permiso\` p
       JOIN \`rol_permiso\` rp ON rp.\`permiso_id\` = p.\`id\`
       WHERE rp.\`rol_id\` IN (${placeholders})`,
      roleIds
    );
    user.permissions = perms.map(p => p.codigo);
  } else {
    user.permissions = [];
  }

  return user;
}

/**
 * Creación de usuario (valida unicidad de correo -> 409 en duplicados)
 * POST /api/usuarios
 */
async function createUser({ nombre, correo, password, activo = true, roles = [] }) {
  if (!nombre || !correo || !password) {
    const error = new Error('Los campos "nombre", "correo" y "password" son obligatorios');
    error.statusCode = 400;
    error.code = 'ValidationError';
    throw error;
  }

  const pool = getPool();
  const normalizedEmail = correo.trim().toLowerCase();

  // Validar unicidad de correo previamente
  const [existing] = await pool.execute(
    'SELECT `id` FROM `usuario` WHERE `correo` = ?',
    [normalizedEmail]
  );

  if (existing.length > 0) {
    const error = new Error(`El correo '${normalizedEmail}' ya se encuentra registrado`);
    error.statusCode = 409;
    error.code = 'EmailConflict';
    throw error;
  }

  const passwordHash = await hashPassword(password);

  try {
    const [result] = await pool.execute(
      `INSERT INTO \`usuario\` (\`nombre\`, \`correo\`, \`password_hash\`, \`activo\`)
       VALUES (?, ?, ?, ?)`,
      [nombre.trim(), normalizedEmail, passwordHash, activo ? 1 : 0]
    );

    const userId = result.insertId;

    // Asignar roles si se especificaron
    if (Array.isArray(roles) && roles.length > 0) {
      for (const roleName of roles) {
        const [roleRows] = await pool.execute(
          'SELECT `id` FROM `rol` WHERE `nombre` = ?',
          [roleName]
        );
        if (roleRows.length > 0) {
          await pool.execute(
            'INSERT IGNORE INTO `usuario_rol` (`usuario_id`, `rol_id`) VALUES (?, ?)',
            [userId, roleRows[0].id]
          );
        }
      }
    }

    return await getUserById(userId);
  } catch (err) {
    // Si la BD reporta error de llave duplicada (carrera concurrente)
    if (err.code === 'ER_DUP_ENTRY') {
      const error = new Error(`El correo '${normalizedEmail}' ya se encuentra registrado`);
      error.statusCode = 409;
      error.code = 'EmailConflict';
      throw error;
    }
    throw err;
  }
}

/**
 * Actualización parcial de usuario (datos, activo, asignación de roles)
 * PATCH /api/usuarios/:id
 */
async function updateUser(id, { nombre, correo, password, activo, roles }) {
  const pool = getPool();

  const user = await getUserById(id);

  const updates = [];
  const params = [];

  if (nombre !== undefined && nombre.trim() !== '') {
    updates.push('`nombre` = ?');
    params.push(nombre.trim());
  }

  if (correo !== undefined && correo.trim() !== '') {
    const normalizedEmail = correo.trim().toLowerCase();
    if (normalizedEmail !== user.correo) {
      // Verificar conflicto de correo con otro usuario
      const [existing] = await pool.execute(
        'SELECT `id` FROM `usuario` WHERE `correo` = ? AND `id` != ?',
        [normalizedEmail, id]
      );
      if (existing.length > 0) {
        const error = new Error(`El correo '${normalizedEmail}' ya está en uso por otro usuario`);
        error.statusCode = 409;
        error.code = 'EmailConflict';
        throw error;
      }
      updates.push('`correo` = ?');
      params.push(normalizedEmail);
    }
  }

  if (password !== undefined && password.trim() !== '') {
    if (password.length < 6) {
      const error = new Error('La contraseña debe tener al menos 6 caracteres');
      error.statusCode = 400;
      error.code = 'ValidationError';
      throw error;
    }
    const hash = await hashPassword(password);
    updates.push('`password_hash` = ?');
    params.push(hash);
  }

  if (activo !== undefined) {
    updates.push('`activo` = ?');
    params.push(activo ? 1 : 0);
  }

  if (updates.length > 0) {
    params.push(id);
    await pool.execute(
      `UPDATE \`usuario\` SET ${updates.join(', ')} WHERE \`id` = ?`,
      params
    );
  }

  // Sincronizar roles si se enviaron en la petición
  if (roles !== undefined && Array.isArray(roles)) {
    // Eliminar asignaciones actuales
    await pool.execute('DELETE FROM `usuario_rol` WHERE `usuario_id` = ?', [id]);

    for (const roleName of roles) {
      const [roleRows] = await pool.execute(
        'SELECT `id` FROM `rol` WHERE `nombre` = ?',
        [roleName]
      );
      if (roleRows.length > 0) {
        await pool.execute(
          'INSERT INTO `usuario_rol` (`usuario_id`, `rol_id`) VALUES (?, ?)',
          [id, roleRows[0].id]
        );
      }
    }
  }

  return await getUserById(id);
}

module.exports = {
  listUsers,
  getUserById,
  createUser,
  updateUser
};
