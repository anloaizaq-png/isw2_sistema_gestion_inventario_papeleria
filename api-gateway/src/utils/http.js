'use strict';

const crypto = require('crypto');

/**
 * Parsea el cuerpo de una petición entrante como JSON
 * @param {import('http').IncomingMessage} req
 * @param {number} maxBytes Límite de tamaño en bytes (por defecto 1MB)
 * @returns {Promise<any>}
 */
function parseJsonBody(req, maxBytes = 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let body = '';
    let bytesReceived = 0;

    req.on('data', chunk => {
      bytesReceived += chunk.length;
      if (bytesReceived > maxBytes) {
        const err = new Error('PayloadTooLarge: El cuerpo de la petición excede el límite permitido');
        err.statusCode = 413;
        reject(err);
        req.destroy();
        return;
      }
      body += chunk.toString('utf8');
    });

    req.on('end', () => {
      if (!body || body.trim() === '') {
        return resolve({});
      }
      try {
        const parsed = JSON.parse(body);
        resolve(parsed);
      } catch (err) {
        const parseErr = new Error('InvalidJSON: El formato del cuerpo debe ser un JSON válido');
        parseErr.statusCode = 400;
        reject(parseErr);
      }
    });

    req.on('error', err => reject(err));
  });
}

/**
 * Envía una respuesta HTTP en formato JSON
 * @param {import('http').ServerResponse} res
 * @param {number} statusCode
 * @param {any} data
 * @param {Record<string, string>} headers
 */
function sendJson(res, statusCode, data, headers = {}) {
  const payload = JSON.stringify(data);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload),
    ...headers
  });
  res.end(payload);
}

/**
 * Envía una respuesta de error estandarizada
 * @param {import('http').ServerResponse} res
 * @param {number} statusCode
 * @param {string} error
 * @param {string} message
 * @param {any} details
 * @param {Record<string, string>} headers
 */
function sendError(res, statusCode, error, message, details = null, headers = {}) {
  const body = {
    status: 'error',
    error,
    message,
    timestamp: new Date().toISOString()
  };
  if (details) {
    body.details = details;
  }
  sendJson(res, statusCode, body, headers);
}

/**
 * Obtiene la dirección IP del cliente
 * @param {import('http').IncomingMessage} req
 * @returns {string}
 */
function getClientIp(req) {
  const forwarded = req.headers['x-forwarded-for'];
  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  return req.socket.remoteAddress || '127.0.0.1';
}

/**
 * Obtiene o genera un Request ID para rastreo de auditoría
 * @param {import('http').IncomingMessage} req
 * @returns {string}
 */
function getRequestId(req) {
  return req.headers['x-request-id'] || crypto.randomUUID();
}

/**
 * Calcula el hash SHA-256 de una cadena (para refresh tokens y tokens de recuperación)
 * @param {string} token
 * @returns {string}
 */
function hashToken(token) {
  return crypto.createHash('sha256').update(String(token)).digest('hex');
}

module.exports = {
  parseJsonBody,
  sendJson,
  sendError,
  getClientIp,
  getRequestId,
  hashToken
};
