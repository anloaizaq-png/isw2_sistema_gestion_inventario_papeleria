'use strict';

const roleService = require('../services/roleService');
const { authenticate } = require('../middlewares/auth');
const { requirePermission } = require('../middlewares/rbac');
const { parseJsonBody, sendJson, sendError } = require('../utils/http');

/**
 * Rutas de Roles y Permisos (/api/roles/* y /api/permisos)
 * Todas requieren permiso `usuarios:administrar`
 */
async function handleRoleRoutes(req, res, pathname) {
  const method = req.method;

  // Validación obligatoria de autenticación y permiso usuarios:administrar
  const isAuthed = await authenticate(req, res);
  if (!isAuthed) return;

  const hasPerm = requirePermission(req, res, 'usuarios:administrar');
  if (!hasPerm) return;

  // GET /api/roles (listado de roles con sus permisos)
  if (method === 'GET' && pathname === '/api/roles') {
    try {
      const roles = await roleService.listRoles();
      return sendJson(res, 200, { status: 'success', data: roles });
    } catch (err) {
      return sendError(res, err.statusCode || 500, err.code || 'RoleListError', err.message);
    }
  }

  // GET /api/permisos (catálogo completo de permisos)
  if (method === 'GET' && pathname === '/api/permisos') {
    try {
      const permisos = await roleService.listPermissions();
      return sendJson(res, 200, { status: 'success', data: permisos });
    } catch (err) {
      return sendError(res, err.statusCode || 500, err.code || 'PermissionListError', err.message);
    }
  }

  // GET /api/roles/{id}
  const matchRole = pathname.match(/^\/api\/roles\/(\d+)$/);
  if (matchRole && method === 'GET') {
    const roleId = parseInt(matchRole[1], 10);
    try {
      const rol = await roleService.getRoleById(roleId);
      return sendJson(res, 200, { status: 'success', data: rol });
    } catch (err) {
      return sendError(res, err.statusCode || 500, err.code || 'GetRoleError', err.message);
    }
  }

  // PUT /api/roles/{id}/permisos (asignación de permisos a un rol)
  const matchPermisos = pathname.match(/^\/api\/roles\/(\d+)\/permisos$/);
  if (matchPermisos && (method === 'PUT' || method === 'POST')) {
    const roleId = parseInt(matchPermisos[1], 10);
    try {
      const body = await parseJsonBody(req);
      const permisos = body.permisos || body.permissions || [];
      const updatedRole = await roleService.assignPermissionsToRole(roleId, permisos);
      return sendJson(res, 200, { status: 'success', data: updatedRole });
    } catch (err) {
      return sendError(res, err.statusCode || 500, err.code || 'AssignRolePermissionError', err.message);
    }
  }

  sendError(res, 404, 'NotFound', `Ruta ${method} ${pathname} no encontrada en roles`);
}

module.exports = {
  handleRoleRoutes
};
