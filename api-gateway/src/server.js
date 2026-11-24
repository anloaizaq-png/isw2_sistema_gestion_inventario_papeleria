'use strict';

const http = require('http');
const config = require('./config');
const { closePool } = require('./db/connection');
const { initDatabase } = require('./db/initDb');
const { dispatch } = require('./router');

/**
 * Punto de entrada del microservicio Gateway y Servicio de Identidad
 */
async function startServer() {
  const server = http.createServer((req, res) => {
    dispatch(req, res).catch(err => {
      console.error('[GATEWAY] Error no capturado en la petición:', err);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'error',
          error: 'InternalServerError',
          message: 'Ocurrió un error interno no controlado'
        }));
      }
    });
  });

  // Intentar inicialización de la BD en segundo plano (reintenta hasta conectar con MySQL)
  initDatabase().catch(err => {
    console.warn(`[SERVER] Inicialización de BD diferida o en espera: ${err.message}`);
  });

  server.listen(config.port, '0.0.0.0', () => {
    console.log(`[GATEWAY] gateway-service escuchando en el puerto ${config.port} (Modo: ${config.env})`);
  });

  // Apagado ordenado (Graceful Shutdown)
  const shutdown = async (signal) => {
    console.log(`[GATEWAY] Señal ${signal} recibida, procediendo a apagar el servidor...`);
    server.close(async () => {
      console.log('[GATEWAY] Servidor HTTP cerrado.');
      await closePool();
      process.exit(0);
    });

    setTimeout(() => {
      console.error('[GATEWAY] Apagado forzado por tiempo límite excedido.');
      process.exit(1);
    }, 5000).unref();
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
  startServer
};
