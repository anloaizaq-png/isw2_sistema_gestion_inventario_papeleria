'use strict';

const { verifyAccessToken } = require('../utils/security');
const { getPool } = require('../db/connection');
const { sendError } = require('../utils/http');

/**
 * Middleware para autenticación mediante Bearer Access Token JWT
 * Verifica firma, expiración, issuer, audience, estado activo del usuario y sesión no revocada.
 * Inyecta `req.user` con { id, email, roles, permissions, sessionId }.
 *
 * @param {import('http').IncomingMessage} req
 * @param {import('http').ServerResponse} res
 * @returns {Promise<boolean>} Retorna true si es autenticado; false si envió error y debe detenerse.
 */
async function authenticate(req, res) {
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    sendError(res, 401, 'Unauthorized', 'Cabecera Authorization ausente o formato inválido (se espera "Bearer <token>")');
    return false;
  }

  const token = authHeader.substring(7).trim();
  let payload;
  try {
    payload = verifyAccessToken(token);
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      sendError(res, 401, 'TokenExpired', 'El token de acceso ha expirado');
      return false;
    }
    sendError(res, 401, 'InvalidToken', 'Token de acceso inválido o no reconocido');
    return false;
  }

  const userId = payload.sub;
  const sessionId = payload.sid;

  if (!userId || !sessionId) {
    sendError(res, 401, 'InvalidTokenClaims', 'El token carece de los identificadores requeridos');
    return false;
  }

  const pool = getPool();

  try {
    // 1. Verificar que la sesión siga activa y no haya sido revocada ni expirada
    const [sessions] = await pool.execute(
      'SELECT `id`, `revocada_en`, `expira_en` FROM `sesion` WHERE `id` = ?',
      [sessionId]
    );

    if (sessions.length === 0) {
      sendError(res, 401, 'SessionNotFound', 'La sesión asociada al token no existe');
      return false;
    }

    const session = sessions[0];
    if (session.revocada_en !== null) {
      sendError(res, 401, 'SessionRevoked', 'La sesión ha sido revocada');
      return false;
    }

    if (new Date(session.expira_en) <= new Date()) {
      sendError(res, 401, 'SessionExpired', 'La sesión ha expirado');
      return false;
    }

    // 2. Verificar que el usuario siga existiendo y esté activo
    const [users] = await pool.execute(
      'SELECT `id`, `activo` FROM `usuario` WHERE `id` = ?',
      [userId]
    );

    if (users.length === 0 || !users[0].activo) {
      sendError(res, 401, 'UserInactive', 'El usuario no existe o se encuentra inactivo');
      return false;
    }

    // Inyectar datos del usuario autenticado en la petición
    req.user = {
      id: Number(userId),
      email: payload.email,
      nombre: payload.nombre,
      roles: Array.isArray(payload.roles) ? payload.roles : [],
      permissions: Array.isArray(payload.permissions) ? payload.permissions : [],
      sessionId: sessionId
    };

    return true;
  } catch (err) {
    console.error('[AUTH-MIDDLEWARE] Error validando autenticación:', err);
    sendError(res, 500, 'InternalServerError', 'Error interno al validar la autenticación');
    return false;
  }
}

module.exports = {
  authenticate
};
