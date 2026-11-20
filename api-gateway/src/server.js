'use strict';

const http = require('http');
const config = require('./config');
const { getPool, closePool } = require('./db/connection');
const { initDatabase } = require('./db/initDb');

/**
 * Manejador principal de peticiones HTTP en Node.js nativo
 */
function handleRequest(req, res) {
  // Manejo de cabeceras comunes
  res.setHeader('X-Powered-By', 'Cotton-Cloud-Gateway');

  const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = parsedUrl.pathname;

  // Endpoint de salud (Health Check)
  if (pathname === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'UP',
      service: 'gateway-service',
      environment: config.env,
      timestamp: new Date().toISOString()
    }));
    return;
  }

  // Respuesta temporal para rutas aún no conectadas en el Paso 1
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    error: 'NotFound',
    message: `Ruta ${req.method} ${pathname} no encontrada en gateway-service`,
    timestamp: new Date().toISOString()
  }));
}

/**
 * Inicializa y levanta el servidor HTTP nativo
 */
async function startServer() {
  const server = http.createServer(handleRequest);

  // Intentar inicializar esquema y seed de base de datos en segundo plano
  try {
    await initDatabase();
  } catch (err) {
    console.warn(`[SERVER] Inicialización de BD pendiente o diferida: ${err.message}`);
  }

  server.listen(config.port, '0.0.0.0', () => {
    console.log(`[GATEWAY] gateway-service escuchando en el puerto ${config.port} (Modo: ${config.env})`);
  });

  // Apagado ordenado (Graceful Shutdown)
  const shutdown = async (signal) => {
    console.log(`[GATEWAY] Señal ${signal} recibida, cerrando servidor...`);
    server.close(async () => {
      console.log('[GATEWAY] Servidor HTTP cerrado.');
      await closePool();
      process.exit(0);
    });

    // Forzar salida si tarda más de 5 segundos
    setTimeout(() => {
      console.error('[GATEWAY] Cierre forzado por tiempo límite excedido.');
      process.exit(1);
    }, 5000);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

if (require.main === module) {
  startServer().catch(err => {
    console.error('[GATEWAY] Error fatal al iniciar el servidor:', err);
    process.exit(1);
  });
}

module.exports = {
  startServer,
  handleRequest
};
