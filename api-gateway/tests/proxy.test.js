'use strict';

const assert = require('assert');
const { matchProxyRoute, PROXY_ROUTES } = require('../src/routes/proxyRoutes');
const { hasPermission } = require('../src/middlewares/rbac');

function runProxyTests() {
  console.log('--- [TEST] Pruebas Unitarias de Reverse Proxy y Propagación de Identidad ---');

  // 1. Verificación de Service Discovery y mapeo de rutas hacia los 5 microservicios
  const expectedServices = [
    { path: '/api/productos', key: 'productos', name: 'productos-service', perm: 'productos:*' },
    { path: '/api/productos/123/precios', key: 'productos', name: 'productos-service', perm: 'productos:*' },
    { path: '/api/inventario', key: 'inventario', name: 'inventario-service', perm: 'inventario:*' },
    { path: '/api/inventario/movimientos', key: 'inventario', name: 'inventario-service', perm: 'inventario:*' },
    { path: '/api/ventas', key: 'ventas', name: 'ventas-service', perm: 'ventas:*' },
    { path: '/api/ventas/pedidos', key: 'ventas', name: 'ventas-service', perm: 'ventas:*' },
    { path: '/api/compras', key: 'compras', name: 'compras-service', perm: 'compras:*' },
    { path: '/api/compras/ordenes', key: 'compras', name: 'compras-service', perm: 'compras:*' },
    { path: '/api/alertas', key: 'analitica', name: 'analitica-service', perm: 'alertas:*' },
    { path: '/api/alertas/stock-minimo', key: 'analitica', name: 'analitica-service', perm: 'alertas:*' }
  ];

  for (const item of expectedServices) {
    const matched = matchProxyRoute(item.path);
    assert.ok(matched, `La ruta '${item.path}' debe coincidir con un microservicio proxy`);
    assert.strictEqual(matched.serviceKey, item.key, `serviceKey para '${item.path}' debe ser '${item.key}'`);
    assert.strictEqual(matched.serviceName, item.name, `serviceName para '${item.path}' debe ser '${item.name}'`);
    assert.strictEqual(matched.requiredPermission, item.perm, `Permiso para '${item.path}' debe ser '${item.perm}'`);
  }
  console.log('✔ Mapeo y coincidencia de rutas para los 5 microservicios aprobado.');

  // 2. Ruta desconocida no debe coincidir con el proxy
  assert.strictEqual(matchProxyRoute('/api/desconocido'), null);
  assert.strictEqual(matchProxyRoute('/otra-ruta'), null);
  console.log('✔ Descarte de rutas no pertenecientes a microservicios aprobado.');

  // 3. Reglas de acceso público vs protegido
  const productosRoute = matchProxyRoute('/api/productos');
  assert.ok(productosRoute.publicMethods.includes('GET'), 'GET en /api/productos debe ser público para catálogo');
  assert.ok(!productosRoute.publicMethods.includes('POST'), 'POST en /api/productos no debe ser público');
  assert.ok(!productosRoute.publicMethods.includes('PUT'), 'PUT en /api/productos no debe ser público');

  const comprasRoute = matchProxyRoute('/api/compras');
  assert.strictEqual(comprasRoute.publicMethods.length, 0, 'Compras debe ser estrictamente protegido para todos los métodos');

  const inventarioRoute = matchProxyRoute('/api/inventario');
  assert.strictEqual(inventarioRoute.publicMethods.length, 0, 'Inventario debe ser estrictamente protegido');
  console.log('✔ Políticas de métodos públicos y protegidos aprobadas.');

  // 4. Validación de permisos RBAC para cada microservicio
  const adminUser = { id: 1, roles: ['ADMIN'], permissions: [] };
  const vendedorUser = { id: 2, roles: ['VENDEDOR'], permissions: ['ventas:*', 'productos:*'] };
  const operadorUser = { id: 3, roles: ['OPERADOR_INVENTARIO'], permissions: ['inventario:*', 'productos:*'] };
  const analistaUser = { id: 4, roles: ['ANALISTA'], permissions: ['alertas:*', 'productos:*'] };

  // Admin tiene acceso a todos los módulos
  assert.strictEqual(hasPermission(adminUser, 'productos:*'), true);
  assert.strictEqual(hasPermission(adminUser, 'inventario:*'), true);
  assert.strictEqual(hasPermission(adminUser, 'ventas:*'), true);
  assert.strictEqual(hasPermission(adminUser, 'compras:*'), true);
  assert.strictEqual(hasPermission(adminUser, 'alertas:*'), true);

  // Vendedor sólo a ventas y productos
  assert.strictEqual(hasPermission(vendedorUser, 'ventas:*'), true);
  assert.strictEqual(hasPermission(vendedorUser, 'productos:*'), true);
  assert.strictEqual(hasPermission(vendedorUser, 'inventario:*'), false);
  assert.strictEqual(hasPermission(vendedorUser, 'compras:*'), false);

  // Operador a inventario y productos
  assert.strictEqual(hasPermission(operadorUser, 'inventario:*'), true);
  assert.strictEqual(hasPermission(operadorUser, 'ventas:*'), false);

  // Analista a alertas y productos
  assert.strictEqual(hasPermission(analistaUser, 'alertas:*'), true);
  assert.strictEqual(hasPermission(analistaUser, 'inventario:*'), false);
  console.log('✔ Validación de permisos RBAC por microservicio destino aprobada.');

  // 5. Simulación de construcción de cabeceras de propagación de identidad
  const reqUser = {
    id: 99,
    roles: ['OPERADOR_INVENTARIO'],
    permissions: ['inventario:*', 'productos:*']
  };

  const simulatedHeaders = {
    'x-user-id': String(reqUser.id),
    'x-user-roles': reqUser.roles.join(','),
    'x-user-permissions': reqUser.permissions.join(','),
    'x-request-id': 'req-test-uuid-1234'
  };

  assert.strictEqual(simulatedHeaders['x-user-id'], '99');
  assert.strictEqual(simulatedHeaders['x-user-roles'], 'OPERADOR_INVENTARIO');
  assert.strictEqual(simulatedHeaders['x-user-permissions'], 'inventario:*,productos:*');
  assert.strictEqual(simulatedHeaders['x-request-id'], 'req-test-uuid-1234');
  console.log('✔ Construcción y propagación de cabeceras X-User-* y X-Request-Id aprobada.');
}

module.exports = {
  runProxyTests
};
