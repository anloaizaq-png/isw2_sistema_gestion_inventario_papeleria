'use strict';

const { sendError } = require('../utils/http');

/**
 * Valida si el usuario autenticado tiene el permiso requerido
 * Soporta comodines (ej. `productos:*` autoriza `productos:crear`, `productos:leer`, etc.)
 * Los usuarios con rol `ADMIN` o con permiso `*` tienen acceso total.
 *
 * @param {object} user Objeto req.user
 * @param {string} requiredPermission Código del permiso requerido
 * @returns {boolean}
 */
function hasPermission(user, requiredPermission) {
  if (!user) return false;

  const roles = user.roles || [];
  if (roles.includes('ADMIN')) return true;

  const userPerms = user.permissions || [];
  if (userPerms.includes('*') || userPerms.includes(requiredPermission)) {
    return true;
  }

  // Comprobar coincidencia con comodín de módulo (ej. 'productos:*')
  const [reqModule] = requiredPermission.split(':');
  if (reqModule && userPerms.includes(`${reqModule}:*`)) {
    return true;
  }

  return false;
}

/**
 * Valida si el usuario posee alguno de los roles permitidos
 * @param {object} user Objeto req.user
 * @param {string|string[]} allowedRoles
 * @returns {boolean}
 */
function hasRole(user, allowedRoles) {
  if (!user) return false;
  const userRoles = user.roles || [];
  if (userRoles.includes('ADMIN')) return true;

  const rolesToCheck = Array.isArray(allowedRoles) ? allowedRoles : [allowedRoles];
  return rolesToCheck.some(r => userRoles.includes(r));
}

/**
 * Guard para validar permiso requerido en rutas protegidas
 * @param {import('http').IncomingMessage} req
 * @param {import('http').ServerResponse} res
 * @param {string} requiredPermission
 * @returns {boolean} true si tiene permiso; false si envió 403
 */
function requirePermission(req, res, requiredPermission) {
  if (!req.user) {
    sendError(res, 401, 'Unauthorized', 'Se requiere autenticación');
    return false;
  }

  if (!hasPermission(req.user, requiredPermission)) {
    sendError(
      res,
      403,
      'Forbidden',
      `Acceso denegado: se requiere el permiso '${requiredPermission}'`
    );
    return false;
  }

  return true;
}

/**
 * Guard para validar rol requerido en rutas protegidas
 * @param {import('http').IncomingMessage} req
 * @param {import('http').ServerResponse} res
 * @param {string|string[]} allowedRoles
 * @returns {boolean}
 */
function requireRole(req, res, allowedRoles) {
  if (!req.user) {
    sendError(res, 401, 'Unauthorized', 'Se requiere autenticación');
    return false;
  }

  if (!hasRole(req.user, allowedRoles)) {
    sendError(
      res,
      403,
      'Forbidden',
      `Acceso denegado: se requiere uno de los roles autorizados`
    );
    return false;
  }

  return true;
}

module.exports = {
  hasPermission,
  hasRole,
  requirePermission,
  requireRole
};
