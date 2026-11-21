'use strict';

const { runAuthTests } = require('./auth.test');
const { runRbacTests } = require('./rbac.test');
const { runProxyTests } = require('./proxy.test');

async function main() {
  console.log('================================================================');
  console.log(' Ejecutando Suite de Pruebas Unitarias del Gateway (Pasos 1-3) ');
  console.log('================================================================\n');

  try {
    await runAuthTests();
    console.log('');
    runRbacTests();
    console.log('');
    runProxyTests();

    console.log('\n================================================================');
    console.log(' ✔ TODAS LAS PRUEBAS UNITARIAS (AUTH, RBAC, PROXY) PASARON OK ');
    console.log('================================================================');
    process.exit(0);
  } catch (err) {
    console.error('\n✖ FALLÓ UNA PRUEBA UNITARIA:', err);
    process.exit(1);
  }
}

main();
