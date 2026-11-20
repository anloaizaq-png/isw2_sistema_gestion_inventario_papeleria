'use strict';

const fs = require('fs');
const path = require('path');
const { getPool, waitForDatabase, closePool } = require('./connection');
const { seed } = require('./seed');

/**
 * Inicializa el esquema y ejecuta el seed inicial en la BD `identidad`
 */
async function initDatabase() {
  console.log('[DB-INIT] Iniciando proceso de inicialización de base de datos...');
  await waitForDatabase();

  const pool = getPool();
  const schemaPath = path.join(__dirname, 'schema.sql');
  const schemaSql = fs.readFileSync(schemaPath, 'utf8');

  // Separar y ejecutar sentencias SQL válidas
  const statements = schemaSql
    .split(';')
    .map(s => s.trim())
    .filter(s => s.length > 0);

  for (const statement of statements) {
    await pool.query(statement);
  }
  console.log('[DB-INIT] Esquema SQL de 8 tablas creado/verificado correctamente.');

  // Ejecutar seed idempotente
  await seed(pool);
  console.log('[DB-INIT] Inicialización completa con éxito.');
}

// Ejecución directa desde CLI si se llama con `node initDb.js`
if (require.main === module) {
  initDatabase()
    .then(async () => {
      console.log('[DB-INIT] Proceso CLI terminado.');
      await closePool();
      process.exit(0);
    })
    .catch(async (err) => {
      console.error('[DB-INIT] Error fatal durante la inicialización:', err);
      await closePool();
      process.exit(1);
    });
}

module.exports = {
  initDatabase
};
