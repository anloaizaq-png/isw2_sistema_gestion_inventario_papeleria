'use strict';

const mysql = require('mysql2/promise');
const config = require('../config');

let pool = null;

/**
 * Obtiene o inicializa el pool de conexiones a la base de datos `identidad`
 */
function getPool() {
  if (!pool) {
    pool = mysql.createPool(config.db);
  }
  return pool;
}

/**
 * Espera a que la base de datos esté lista para recibir conexiones.
 * Reintenta con retroceso exponencial, esencial durante el arranque en Docker.
 */
async function waitForDatabase(maxRetries = 15, delayMs = 2000) {
  const currentPool = getPool();
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const connection = await currentPool.getConnection();
      await connection.ping();
      connection.release();
      console.log(`[DB] Conexión establecida exitosamente con MySQL (${config.db.host}:${config.db.port}/${config.db.database})`);
      return true;
    } catch (err) {
      console.warn(`[DB] Intento ${attempt}/${maxRetries} fallido al conectar con MySQL: ${err.message}`);
      if (attempt === maxRetries) {
        throw new Error(`[DB] No fue posible conectar con MySQL después de ${maxRetries} intentos: ${err.message}`);
      }
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
  }
}

/**
 * Cierra ordenadamente el pool de conexiones
 */
async function closePool() {
  if (pool) {
    await pool.end();
    pool = null;
    console.log('[DB] Pool de conexiones cerrado.');
  }
}

module.exports = {
  getPool,
  waitForDatabase,
  closePool
};
