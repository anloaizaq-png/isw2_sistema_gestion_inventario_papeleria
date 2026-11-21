'use strict';

const http = require('http');
const https = require('https');
const config = require('../config');
const { sendError, getRequestId } = require('../utils/http');

/**
 * Reenvía la petición entrante hacia el microservicio de destino usando streams nativos de Node.js.
 * Conserva método HTTP, query params, cabeceras y cuerpo (body stream).
 * Inyecta cabeceras internas de identidad y auditoría (X-User-*, X-Request-Id).
 * Gestiona de forma controlada caídas del servicio (503) o timeouts (504/502).
 *
 * @param {import('http').IncomingMessage} req Petición entrante del cliente
 * @param {import('http').ServerResponse} res Respuesta hacia el cliente
 * @param {string} targetBaseUrl URL base del microservicio de destino (ej. http://productos-service:8080)
 * @param {string} serviceName Nombre identificador del servicio (para logs y errores)
 */
function forwardRequest(req, res, targetBaseUrl, serviceName) {
  const requestId = getRequestId(req);

  // Construir la URL de destino conservando ruta completa y query string (pass-through)
  let targetUrl;
  try {
    targetUrl = new URL(req.url, targetBaseUrl);
  } catch (err) {
    sendError(res, 400, 'InvalidUrl', `URL de destino inválida: ${err.message}`);
    return;
  }

  // Preparar cabeceras para el reenvío
  const proxyHeaders = { ...req.headers };

  // Sobrescribir Host con el del servicio destino
  proxyHeaders['host'] = targetUrl.host;

  // Cabeceras estándar de proxy inverso
  const clientIp = req.socket.remoteAddress || '127.0.0.1';
  if (proxyHeaders['x-forwarded-for']) {
    proxyHeaders['x-forwarded-for'] = `${proxyHeaders['x-forwarded-for']}, ${clientIp}`;
  } else {
    proxyHeaders['x-forwarded-for'] = clientIp;
  }
  proxyHeaders['x-forwarded-proto'] = req.socket.encrypted ? 'https' : 'http';
  proxyHeaders['x-forwarded-host'] = req.headers['host'] || '';

  // Inyectar X-Request-Id garantizado
  proxyHeaders['x-request-id'] = requestId;

  // Inyectar cabeceras internas de propagación de identidad si el usuario está autenticado
  if (req.user) {
    proxyHeaders['x-user-id'] = String(req.user.id);
    proxyHeaders['x-user-roles'] = (req.user.roles || []).join(',');
    proxyHeaders['x-user-permissions'] = (req.user.permissions || []).join(',');
  } else {
    // Si la petición es pública, eliminar cabeceras X-User que pudieran venir del exterior
    delete proxyHeaders['x-user-id'];
    delete proxyHeaders['x-user-roles'];
    delete proxyHeaders['x-user-permissions'];
  }

  // Opciones de la petición HTTP cliente hacia el microservicio
  const isHttps = targetUrl.protocol === 'https:';
  const clientModule = isHttps ? https : http;

  const requestOptions = {
    protocol: targetUrl.protocol,
    hostname: targetUrl.hostname,
    port: targetUrl.port || (isHttps ? 443 : 80),
    path: targetUrl.pathname + targetUrl.search,
    method: req.method,
    headers: proxyHeaders,
    timeout: config.proxyTimeoutMs
  };

  const proxyReq = clientModule.request(requestOptions, (proxyRes) => {
    // Propagar código de estado y cabeceras del microservicio hacia el cliente
    const responseHeaders = { ...proxyRes.headers };
    responseHeaders['x-request-id'] = requestId;
    res.writeHead(proxyRes.statusCode, responseHeaders);

    // Conectar el stream de respuesta del microservicio directamente a la respuesta del cliente
    proxyRes.pipe(res);
  });

  // Manejo de Timeout (Servicio no responde en el tiempo límite -> 504 / 502)
  proxyReq.on('timeout', () => {
    proxyReq.destroy();
    if (!res.headersSent) {
      sendError(
        res,
        504,
        'GatewayTimeout',
        `Tiempo de espera agotado al comunicar con el microservicio '${serviceName}'`,
        { service: serviceName, timeoutMs: config.proxyTimeoutMs }
      );
    }
  });

  // Manejo de errores de conexión (Servicio caído / detenido -> 503 / 502)
  proxyReq.on('error', (err) => {
    if (res.headersSent) return;

    const isConnectionError = (
      err.code === 'ECONNREFUSED' ||
      err.code === 'ENOTFOUND' ||
      err.code === 'EHOSTUNREACH' ||
      err.code === 'ENETUNREACH'
    );

    const statusCode = isConnectionError ? 503 : 502;
    const errorCode = isConnectionError ? 'ServiceUnavailable' : 'BadGateway';
    const message = isConnectionError
      ? `El microservicio destino '${serviceName}' no está disponible o se encuentra detenido`
      : `Error de pasarela en la comunicación con '${serviceName}': ${err.message}`;

    sendError(res, statusCode, errorCode, message, {
      service: serviceName,
      code: err.code || 'UNKNOWN'
    });
  });

  // Manejo de cancelación o error en el stream de la petición del cliente
  req.on('error', (err) => {
    proxyReq.destroy(err);
  });

  // Conectar el cuerpo de la petición entrante al stream de la petición reenviada
  req.pipe(proxyReq);
}

module.exports = {
  forwardRequest
};
