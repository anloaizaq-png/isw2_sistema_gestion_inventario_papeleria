'use strict';

const config = require('../config');
const { forwardRequest } = require('../proxy/reverseProxy');
const { authenticate } = require('../middlewares/auth');
const { requirePermission } = require('../middlewares/rbac');

/**
 * Tabla de enrutamiento hacia los 5 microservicios destino
 * Define prefijo de ruta, URL destino, permiso RBAC requerido y métodos públicos permitidos.
 */
const PROXY_ROUTES = [
  {
    prefix: '/api/productos',
    serviceKey: 'productos',
    serviceName: 'productos-service',
    requiredPermission: 'productos:*',
    // Permite consulta pública de catálogo (GET) si no se provee token
    publicMethods: ['GET']
  },
  {
    prefix: '/api/inventario',
    serviceKey: 'inventario',
    serviceName: 'inventario-service',
    requiredPermission: 'inventario:*',
    publicMethods: []
  },
  {
    prefix: '/api/ventas',
    serviceKey: 'ventas',
    serviceName: 'ventas-service',
    requiredPermission: 'ventas:*',
    publicMethods: []
  },
  {
    prefix: '/api/compras',
    serviceKey: 'compras',
    serviceName: 'compras-service',
    requiredPermission: 'compras:*',
    publicMethods: []
  },
  {
    prefix: '/api/alertas',
    serviceKey: 'analitica',
    serviceName: 'analitica-service',
    requiredPermission: 'alertas:*',
    publicMethods: []
  }
];

/**
 * Busca si la ruta coincide con alguno de los microservicios destino
 * @param {string} pathname
 * @returns {object|null}
 */
function matchProxyRoute(pathname) {
  for (const route of PROXY_ROUTES) {
    if (pathname === route.prefix || pathname.startsWith(route.prefix + '/')) {
      return route;
    }
  }
  return null;
}

/**
 * Manejador principal de rutas de proxy inverso
 * Aplica autenticación JWT y RBAC antes de reenviar la petición
 *
 * @param {import('http').IncomingMessage} req
 * @param {import('http').ServerResponse} res
 * @param {string} pathname
 * @returns {Promise<boolean>} Retorna true si la ruta fue capturada por el proxy, false si no corresponde
 */
async function handleProxyRoutes(req, res, pathname) {
  const route = matchProxyRoute(pathname);
  if (!route) {
    return false;
  }

  const authHeader = req.headers['authorization'];
  const isPublicMethod = route.publicMethods.includes(req.method);

  // Si la ruta requiere autenticación obligatoria o si el cliente envió cabecera Authorization
  if (!isPublicMethod || Boolean(authHeader)) {
    const isAuthed = await authenticate(req, res);
    if (!isAuthed) {
      return true; // Error 401 ya fue enviado por authenticate
    }

    // Validar permiso RBAC correspondiente al módulo
    if (route.requiredPermission) {
      const hasPerm = requirePermission(req, res, route.requiredPermission);
      if (!hasPerm) {
        return true; // Error 403 ya fue enviado por requirePermission
      }
    }
  }

  // Obtener URL de destino desde configuración
  const targetBaseUrl = config.services[route.serviceKey];
  forwardRequest(req, res, targetBaseUrl, route.serviceName);
  return true;
}

module.exports = {
  PROXY_ROUTES,
  matchProxyRoute,
  handleProxyRoutes
};
