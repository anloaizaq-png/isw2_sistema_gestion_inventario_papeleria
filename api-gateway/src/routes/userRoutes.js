'use strict';

const userService = require('../services/userService');
const { authenticate } = require('../middlewares/auth');
const { requirePermission } = require('../middlewares/rbac');
const { parseJsonBody, sendJson, sendError } = require('../utils/http');

/**
 * Rutas de Administración de Usuarios (/api/usuarios/*)
 * Todas requieren permiso `usuarios:administrar`
 */
async function handleUserRoutes(req, res, pathname, query) {
  const method = req.method;

  // Validación de autenticación y permiso usuarios:administrar
  const isAuthed = await authenticate(req, res);
  if (!isAuthed) return;

  const hasPerm = requirePermission(req, res, 'usuarios:administrar');
  if (!hasPerm) return;

  // GET /api/usuarios (paginado)
  if (method === 'GET' && pathname === '/api/usuarios') {
    try {
      const page = query.get('page') || 1;
      const limit = query.get('limit') || 10;
      const search = query.get('search') || '';

      const result = await userService.listUsers({ page, limit, search });
      return sendJson(res, 200, { status: 'success', ...result });
    } catch (err) {
      return sendError(res, err.statusCode || 500, err.code || 'UserListError', err.message);
    }
  }

  // POST /api/usuarios (creación)
  if (method === 'POST' && pathname === '/api/usuarios') {
    try {
      const body = await parseJsonBody(req);
      const newUser = await userService.createUser({
        nombre: body.nombre,
        correo: body.correo || body.email,
        password: body.password,
        activo: body.activo !== undefined ? body.activo : true,
        roles: body.roles || []
      });
      return sendJson(res, 201, { status: 'success', data: newUser });
    } catch (err) {
      return sendError(res, err.statusCode || 500, err.code || 'CreateUserError', err.message);
    }
  }

  // Rutas con ID: /api/usuarios/{id}
  const match = pathname.match(/^\/api\/usuarios\/(\d+)$/);
  if (match) {
    const userId = parseInt(match[1], 10);

    // GET /api/usuarios/{id}
    if (method === 'GET') {
      try {
        const user = await userService.getUserById(userId);
        return sendJson(res, 200, { status: 'success', data: user });
      } catch (err) {
        return sendError(res, err.statusCode || 500, err.code || 'GetUserError', err.message);
      }
    }

    // PATCH /api/usuarios/{id}
    if (method === 'PATCH' || method === 'PUT') {
      try {
        const body = await parseJsonBody(req);
        const updatedUser = await userService.updateUser(userId, {
          nombre: body.nombre,
          correo: body.correo || body.email,
          password: body.password,
          activo: body.activo,
          roles: body.roles
        });
        return sendJson(res, 200, { status: 'success', data: updatedUser });
      } catch (err) {
        return sendError(res, err.statusCode || 500, err.code || 'UpdateUserError', err.message);
      }
    }
  }

  sendError(res, 404, 'NotFound', `Ruta ${method} ${pathname} no encontrada en usuarios`);
}

module.exports = {
  handleUserRoutes
};
