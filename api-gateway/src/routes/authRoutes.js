'use strict';

const authService = require('../services/authService');
const { authenticate } = require('../middlewares/auth');
const { parseJsonBody, sendJson, sendError, getClientIp, getRequestId } = require('../utils/http');

/**
 * Rutas internas de Autenticación (/api/auth/*)
 */
async function handleAuthRoutes(req, res, pathname) {
  const method = req.method;
  const ip = getClientIp(req);
  const requestId = getRequestId(req);

  // POST /api/auth/login [Público]
  if (method === 'POST' && pathname === '/api/auth/login') {
    try {
      const body = await parseJsonBody(req);
      const result = await authService.login({
        correo: body.correo || body.email,
        password: body.password || body.contrasena,
        ip,
        requestId
      });
      return sendJson(res, 200, { status: 'success', data: result }, { 'X-Request-Id': requestId });
    } catch (err) {
      const status = err.statusCode || 500;
      const headers = err.retryAfter ? { 'Retry-After': String(err.retryAfter) } : {};
      return sendError(res, status, err.code || 'LoginError', err.message, null, headers);
    }
  }

  // POST /api/auth/refresh [Público con refresh token]
  if (method === 'POST' && pathname === '/api/auth/refresh') {
    try {
      const body = await parseJsonBody(req);
      const refreshToken = body.refreshToken || body.refresh_token;
      const result = await authService.refresh({ refreshToken, ip, requestId });
      return sendJson(res, 200, { status: 'success', data: result }, { 'X-Request-Id': requestId });
    } catch (err) {
      const status = err.statusCode || 401;
      return sendError(res, status, err.code || 'RefreshError', err.message);
    }
  }

  // POST /api/auth/logout [Autenticado]
  if (method === 'POST' && pathname === '/api/auth/logout') {
    const isAuthed = await authenticate(req, res);
    if (!isAuthed) return;

    try {
      const result = await authService.logout({
        sessionId: req.user.sessionId,
        userId: req.user.id,
        ip,
        requestId
      });
      return sendJson(res, 200, { status: 'success', ...result });
    } catch (err) {
      return sendError(res, err.statusCode || 500, err.code || 'LogoutError', err.message);
    }
  }

  // GET /api/auth/me [Autenticado]
  if (method === 'GET' && pathname === '/api/auth/me') {
    const isAuthed = await authenticate(req, res);
    if (!isAuthed) return;

    try {
      const profile = await authService.getMe({ userId: req.user.id });
      return sendJson(res, 200, { status: 'success', data: profile });
    } catch (err) {
      return sendError(res, err.statusCode || 500, err.code || 'MeError', err.message);
    }
  }

  // POST /api/auth/password/forgot [Público con control de intentos]
  if (method === 'POST' && pathname === '/api/auth/password/forgot') {
    try {
      const body = await parseJsonBody(req);
      const result = await authService.forgotPassword({
        correo: body.correo || body.email,
        ip,
        requestId
      });
      return sendJson(res, 200, { status: 'success', ...result });
    } catch (err) {
      return sendError(res, err.statusCode || 400, err.code || 'ForgotPasswordError', err.message);
    }
  }

  // POST /api/auth/password/reset [Token recuperación válido]
  if (method === 'POST' && pathname === '/api/auth/password/reset') {
    try {
      const body = await parseJsonBody(req);
      const result = await authService.resetPassword({
        token: body.token,
        nuevaPassword: body.nuevaPassword || body.password,
        ip,
        requestId
      });
      return sendJson(res, 200, { status: 'success', ...result });
    } catch (err) {
      return sendError(res, err.statusCode || 400, err.code || 'ResetPasswordError', err.message);
    }
  }

  // POST /api/auth/password/change [Autenticado]
  if (method === 'POST' && pathname === '/api/auth/password/change') {
    const isAuthed = await authenticate(req, res);
    if (!isAuthed) return;

    try {
      const body = await parseJsonBody(req);
      const result = await authService.changePassword({
        userId: req.user.id,
        passwordActual: body.passwordActual || body.currentPassword,
        nuevaPassword: body.nuevaPassword || body.newPassword,
        ip,
        requestId
      });
      return sendJson(res, 200, { status: 'success', ...result });
    } catch (err) {
      return sendError(res, err.statusCode || 400, err.code || 'ChangePasswordError', err.message);
    }
  }

  // Ruta no encontrada dentro de /api/auth
  sendError(res, 404, 'NotFound', `Endpoint ${method} ${pathname} no encontrado`);
}

module.exports = {
  handleAuthRoutes
};
