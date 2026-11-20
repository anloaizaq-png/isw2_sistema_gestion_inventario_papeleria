'use strict';

const assert = require('assert');
const {
  hashPassword,
  comparePassword,
  generateAccessToken,
  verifyAccessToken,
  generateRefreshToken,
  generateResetToken
} = require('../src/utils/security');
const { hashToken } = require('../src/utils/http');
const { RateLimiter } = require('../src/utils/rateLimiter');

async function runAuthTests() {
  console.log('--- [TEST] Pruebas Unitarias de Seguridad y Autenticación ---');

  // 1. Hashing de contraseña con bcrypt
  const plainPassword = 'SecretPassword123*';
  const hashed = await hashPassword(plainPassword);
  assert.ok(hashed && hashed.startsWith('$2'), 'El hash generado debe ser un hash bcrypt válido');
  const isMatch = await comparePassword(plainPassword, hashed);
  assert.strictEqual(isMatch, true, 'comparePassword debe validar la contraseña correcta');
  const isWrongMatch = await comparePassword('WrongPassword', hashed);
  assert.strictEqual(isWrongMatch, false, 'comparePassword debe rechazar contraseñas incorrectas');
  console.log('✔ Hashing y comparación con bcrypt aprobados.');

  // 2. Access Token JWT (Claims exactos requeridos: sub, email, roles, permissions, sid, iss, aud)
  const mockUser = { id: 42, correo: 'usuario@cottoncloud.com', nombre: 'Usuario Prueba' };
  const mockRoles = ['VENDEDOR'];
  const mockPermissions = ['ventas:*', 'productos:*'];
  const mockSessionId = '11111111-2222-3333-4444-555555555555';

  const token = generateAccessToken(mockUser, mockRoles, mockPermissions, mockSessionId);
  assert.ok(typeof token === 'string' && token.split('.').length === 3, 'El token debe ser un JWT con 3 partes');

  const decoded = verifyAccessToken(token);
  assert.strictEqual(decoded.sub, '42', 'Claim "sub" debe coincidir con el ID de usuario');
  assert.strictEqual(decoded.email, 'usuario@cottoncloud.com', 'Claim "email" debe coincidir');
  assert.strictEqual(decoded.sid, mockSessionId, 'Claim "sid" debe coincidir con el sessionId');
  assert.deepStrictEqual(decoded.roles, mockRoles, 'Claim "roles" debe coincidir');
  assert.deepStrictEqual(decoded.permissions, mockPermissions, 'Claim "permissions" debe coincidir');
  assert.strictEqual(decoded.iss, 'cotton-cloud-gateway', 'Claim "iss" debe ser cotton-cloud-gateway');
  assert.strictEqual(decoded.aud, 'cotton-cloud-services', 'Claim "aud" debe ser cotton-cloud-services');
  console.log('✔ Emisión y validación de Access Token JWT con claims aprobados.');

  // 3. Tokens aleatorios criptográficamente seguros y su hash SHA-256
  const refreshRaw = generateRefreshToken();
  assert.strictEqual(refreshRaw.length, 80, 'Refresh token debe tener 40 bytes hexadecimales');
  const refreshHash = hashToken(refreshRaw);
  assert.strictEqual(refreshHash.length, 64, 'El hash SHA-256 debe tener 64 caracteres');

  const resetRaw = generateResetToken();
  assert.strictEqual(resetRaw.length, 64, 'Reset token debe tener 32 bytes hexadecimales');
  const resetHash = hashToken(resetRaw);
  assert.strictEqual(resetHash.length, 64, 'El hash SHA-256 del reset token debe tener 64 caracteres');
  console.log('✔ Generación criptográfica de tokens y hashing SHA-256 aprobados.');

  // 4. Rate Limiter (Protección contra fuerza bruta y escenario PR14)
  const limiter = new RateLimiter({ maxAttempts: 3, blockDurationMs: 60000 });
  const testEmail = 'fuerzabruta@cottoncloud.com';

  assert.strictEqual(limiter.check(testEmail).blocked, false, 'Inicialmente no debe estar bloqueado');

  limiter.recordFailure(testEmail); // Intento 1
  assert.strictEqual(limiter.check(testEmail).blocked, false);
  assert.strictEqual(limiter.check(testEmail).remainingAttempts, 2);

  limiter.recordFailure(testEmail); // Intento 2
  assert.strictEqual(limiter.check(testEmail).blocked, false);
  assert.strictEqual(limiter.check(testEmail).remainingAttempts, 1);

  const blockedStatus = limiter.recordFailure(testEmail); // Intento 3 -> Bloqueado
  assert.strictEqual(blockedStatus.blocked, true, 'Al alcanzar maxAttempts debe bloquearse');
  assert.strictEqual(limiter.check(testEmail).blocked, true, 'check() debe reportar bloqueo');
  assert.ok(blockedStatus.retryAfterSeconds > 0, 'Debe indicar tiempo de espera');

  // Otra cuenta no debe verse afectada (aislamiento por cuenta, clave de PR14)
  const anotherEmail = 'valido@cottoncloud.com';
  assert.strictEqual(limiter.check(anotherEmail).blocked, false, 'Otra cuenta no debe estar bloqueada');

  // Restablecimiento al ingresar correctamente
  limiter.reset(testEmail);
  assert.strictEqual(limiter.check(testEmail).blocked, false, 'El reset debe limpiar el bloqueo');
  console.log('✔ Rate Limiter en memoria y aislamiento por cuenta (PR14) aprobados.');
}

module.exports = {
  runAuthTests
};
