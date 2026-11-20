'use strict';

const config = require('./config');
const { handleAuthRoutes } = require('./routes/authRoutes');
const { handleUserRoutes } = require('./routes/userRoutes');
const { handleRoleRoutes } = require('./routes/roleRoutes');
const { sendJson, sendError, getRequestId } = require('./utils/http');

/**
 * Enrutador principal del API Gateway y Servicio de Identidad
 */
async function dispatch(req, res) {
  const requestId = getRequestId(req);

  // Inyectar cabeceras comunes y de seguridad
  res.setHeader('X-Powered-By', 'Cotton-Cloud-Gateway');
  res.setHeader('X-Request-Id', requestId);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Request-Id');

  // Soporte de peticiones CORS pre-flight
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = parsedUrl.pathname;
  const searchParams = parsedUrl.searchParams;

  // Endpoint de salud (Health Check)
  if (pathname === '/health' && req.method === 'GET') {
    return sendJson(res, 200, {
      status: 'UP',
      service: 'gateway-service',
      environment: config.env,
      timestamp: new Date().toISOString()
    });
  }

  // 1. Enrutamiento hacia módulo de Autenticación (/api/auth/*)
  if (pathname.startsWith('/api/auth/')) {
    return handleAuthRoutes(req, res, pathname);
  }

  // 2. Enrutamiento hacia módulo de Usuarios (/api/usuarios)
  if (pathname === '/api/usuarios' || pathname.startsWith('/api/usuarios/')) {
    return handleUserRoutes(req, res, pathname, searchParams);
  }

  // 3. Enrutamiento hacia Roles y Permisos (/api/roles, /api/permisos)
  if (pathname === '/api/roles' || pathname.startsWith('/api/roles/') || pathname === '/api/permisos') {
    return handleRoleRoutes(req, res, pathname);
  }

  // Ruta no encontrada en el gateway
  sendError(res, 404, 'NotFound', `Ruta ${req.method} ${pathname} no encontrada`);
}

module.exports = {
  dispatch
};
