'use strict';

const { runAuthTests } = require('./auth.test');
const { runRbacTests } = require('./rbac.test');

async function main() {
  console.log('=====================================================');
  console.log(' Ejecutando Suite de Pruebas Unitarias Gateway (Paso 2)');
  console.log('=====================================================\n');

  try {
    await runAuthTests();
    console.log('');
    runRbacTests();

    console.log('\n=====================================================');
    console.log(' ✔ TODAS LAS PRUEBAS UNITARIAS PASARON EXITOSAMENTE ');
    console.log('=====================================================');
    process.exit(0);
  } catch (err) {
    console.error('\n✖ FALLÓ UNA PRUEBA UNITARIA:', err);
    process.exit(1);
  }
}

main();
