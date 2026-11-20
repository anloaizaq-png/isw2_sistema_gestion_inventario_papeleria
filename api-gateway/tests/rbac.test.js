'use strict';

const assert = require('assert');
const { hasPermission, hasRole } = require('../src/middlewares/rbac');

function runRbacTests() {
  console.log('--- [TEST] Pruebas Unitarias de RBAC y Permisos ---');

  // 1. Usuario con rol ADMIN (acceso total a cualquier recurso)
  const adminUser = {
    id: 1,
    roles: ['ADMIN'],
    permissions: []
  };
  assert.strictEqual(hasPermission(adminUser, 'usuarios:administrar'), true, 'ADMIN debe tener permiso usuarios:administrar');
  assert.strictEqual(hasPermission(adminUser, 'productos:*'), true, 'ADMIN debe tener permiso productos:*');
  assert.strictEqual(hasPermission(adminUser, 'inventario:movimientos:crear'), true, 'ADMIN debe tener acceso a cualquier sub-permiso');
  assert.strictEqual(hasRole(adminUser, 'VENDEDOR'), true, 'ADMIN satisface cualquier validación de rol');
  console.log('✔ Permisos totales de ADMIN aprobados.');

  // 2. Operador de inventario con permiso comodín productos:* e inventario:*
  const operadorUser = {
    id: 2,
    roles: ['OPERADOR_INVENTARIO'],
    permissions: ['inventario:*', 'productos:*']
  };
  assert.strictEqual(hasPermission(operadorUser, 'productos:*'), true);
  assert.strictEqual(hasPermission(operadorUser, 'productos:crear'), true, 'Comodín de módulo debe autorizar acción específica');
  assert.strictEqual(hasPermission(operadorUser, 'inventario:ajuste'), true);
  assert.strictEqual(hasPermission(operadorUser, 'usuarios:administrar'), false, 'No debe tener permisos no asignados');
  assert.strictEqual(hasPermission(operadorUser, 'ventas:*'), false, 'No debe tener permiso de ventas');
  console.log('✔ Validación de permisos granulares y comodines de módulo aprobada.');

  // 3. Vendedor
  const vendedorUser = {
    id: 3,
    roles: ['VENDEDOR'],
    permissions: ['ventas:*', 'productos:*']
  };
  assert.strictEqual(hasRole(vendedorUser, ['VENDEDOR', 'ADMIN']), true);
  assert.strictEqual(hasRole(vendedorUser, 'COMPRADOR'), false);
  assert.strictEqual(hasPermission(vendedorUser, 'ventas:pedidos:crear'), true);
  assert.strictEqual(hasPermission(vendedorUser, 'compras:*'), false);
  console.log('✔ Validación de roles y permisos de vendedor aprobada.');
}

module.exports = {
  runRbacTests
};
