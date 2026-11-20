'use strict';

// Configuración centralizada del microservicio Gateway y Base de Datos Identidad
module.exports = {
  env: process.env.NODE_ENV || 'development',
  port: parseInt(process.env.PORT, 10) || 8080,

  db: {
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT, 10) || 3306,
    user: process.env.DB_USER || 'identidad_user',
    password: process.env.DB_PASSWORD || 'identidad_pass',
    database: process.env.DB_NAME || 'identidad',
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0,
    charset: 'utf8mb4'
  },

  jwt: {
    secret: process.env.JWT_SECRET || 'cotton_cloud_super_secret_jwt_key_2024',
    accessTtl: process.env.JWT_EXPIRES_IN || '15m',
    refreshTtl: process.env.JWT_REFRESH_EXPIRES_IN || '7d',
    issuer: process.env.JWT_ISSUER || 'cotton-cloud-gateway',
    audience: process.env.JWT_AUDIENCE || 'cotton-cloud-services'
  },

  adminSeed: {
    name: process.env.ADMIN_NAME || 'Administrador Inicial',
    email: process.env.ADMIN_EMAIL || 'admin@cottoncloud.com',
    password: process.env.ADMIN_PASSWORD || 'Admin1234*'
  },

  services: {
    productos: process.env.PRODUCTOS_URL || 'http://productos-service:8080',
    inventario: process.env.INVENTARIO_URL || 'http://inventario-service:8080',
    ventas: process.env.VENTAS_URL || 'http://ventas-service:8080',
    compras: process.env.COMPRAS_URL || 'http://compras-service:8080',
    analitica: process.env.ANALITICA_URL || 'http://analitica-service:8080'
  }
};
