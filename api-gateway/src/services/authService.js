'use strict';

const crypto = require('crypto');
const { getPool } = require('../db/connection');
const {
  comparePassword,
  hashPassword,
  generateAccessToken,
  generateRefreshToken,
  generateResetToken
} = require('../utils/security');
const { hashToken } = require('../utils/http');
const { loginRateLimiter, forgotPasswordRateLimiter } = require('../utils/rateLimiter');

/**
 * Registra un evento de autenticación en la tabla `evento_autenticacion`
 */
async function logAuthEvent(pool, { userId = null, tipo, resultado, ip = null, requestId = null }) {
  try {
    await pool.execute(
      `INSERT INTO \`evento_autenticacion\` (\`usuario_id\`, \`tipo\`, \`resultado\`, \`ip_origen\`, \`request_id\`)
       VALUES (?, ?, ?, ?, ?)`,
      [userId, tipo, resultado, ip, requestId]
    );
  } catch (err) {
    console.error('[AUTH-SERVICE] Error registrando evento de autenticación:', err.message);
  }
}

/**
 * Obtiene los nombres de roles y códigos de permisos vigentes de un usuario
 */
async function getUserRolesAndPermissions(pool, userId) {
  // 1. Roles del usuario
  const [roleRows] = await pool.execute(
    `SELECT r.\`id\`, r.\`nombre\`
     FROM \`rol\` r
     JOIN \`usuario_rol\` ur ON ur.\`rol_id\` = r.\`id\`
     WHERE ur.\`usuario_id\` = ?`,
    [userId]
  );
  const roles = roleRows.map(r => r.nombre);
  const roleIds = roleRows.map(r => r.id);

  if (roleIds.length === 0) {
    return { roles: [], permissions: [] };
  }

  // 2. Permisos asociados a dichos roles
  const placeholders = roleIds.map(() => '?').join(',');
  const [permRows] = await pool.execute(
    `SELECT DISTINCT p.\`codigo\`
     FROM \`permiso\` p
     JOIN \`rol_permiso\` rp ON rp.\`permiso_id\` = p.\`id\`
     WHERE rp.\`rol_id\` IN (${placeholders})`,
    roleIds
  );
  const permissions = permRows.map(p => p.codigo);

  return { roles, permissions };
}

/**
 * Inicio de sesión (POST /api/auth/login)
 */
async function login({ correo, password, ip, requestId }) {
  if (!correo || !password) {
    const error = new Error('Los campos "correo" y "password" son obligatorios');
    error.statusCode = 400;
    error.code = 'ValidationError';
    throw error;
  }

  const pool = getPool();

  // 1. Verificar Rate Limit por correo (protección fuerza bruta)
  const rateStatus = loginRateLimiter.check(correo);
  if (rateStatus.blocked) {
    await logAuthEvent(pool, {
      tipo: 'LOGIN',
      resultado: 'BLOCKED_RATE_LIMIT',
      ip,
      requestId
    });
    const error = new Error(`Demasiados intentos fallidos para esta cuenta. Acceso bloqueado temporalmente. Intente en ${rateStatus.retryAfterSeconds} segundos.`);
    error.statusCode = 429;
    error.code = 'RateLimitExceeded';
    error.retryAfter = rateStatus.retryAfterSeconds;
    throw error;
  }

  // 2. Buscar usuario por correo
  const [users] = await pool.execute(
    'SELECT `id`, `nombre`, `correo`, `password_hash`, `activo` FROM `usuario` WHERE `correo` = ?',
    [correo.trim().toLowerCase()]
  );

  if (users.length === 0) {
    loginRateLimiter.recordFailure(correo);
    await logAuthEvent(pool, { tipo: 'LOGIN', resultado: 'FAILURE_USER_NOT_FOUND', ip, requestId });
    const error = new Error('Credenciales inválidas');
    error.statusCode = 401;
    error.code = 'InvalidCredentials';
    throw error;
  }

  const user = users[0];

  // 3. Validar estado activo
  if (!user.activo) {
    await logAuthEvent(pool, { userId: user.id, tipo: 'LOGIN', resultado: 'FAILURE_USER_INACTIVE', ip, requestId });
    const error = new Error('La cuenta de usuario se encuentra inactiva');
    error.statusCode = 401;
    error.code = 'UserInactive';
    throw error;
  }

  // 4. Validar contraseña
  const passwordMatch = await comparePassword(password, user.password_hash);
  if (!passwordMatch) {
    const failStatus = loginRateLimiter.recordFailure(correo);
    await logAuthEvent(pool, { userId: user.id, tipo: 'LOGIN', resultado: 'FAILURE_BAD_PASSWORD', ip, requestId });

    if (failStatus.blocked) {
      const error = new Error(`Demasiados intentos fallidos para esta cuenta. Acceso bloqueado temporalmente. Intente en ${failStatus.retryAfterSeconds} segundos.`);
      error.statusCode = 429;
      error.code = 'RateLimitExceeded';
      error.retryAfter = failStatus.retryAfterSeconds;
      throw error;
    }

    const error = new Error('Credenciales inválidas');
    error.statusCode = 401;
    error.code = 'InvalidCredentials';
    throw error;
  }

  // Restablecer rate limit ante login exitoso
  loginRateLimiter.reset(correo);

  // 5. Cargar roles y permisos
  const { roles, permissions } = await getUserRolesAndPermissions(pool, user.id);

  // 6. Crear sesión persistida y generar tokens
  const sessionId = crypto.randomUUID();
  const refreshTokenRaw = generateRefreshToken();
  const refreshTokenHash = hashToken(refreshTokenRaw);

  // TTL Refresh Token: 7 días
  const expiraEn = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);

  await pool.execute(
    `INSERT INTO \`sesion\` (\`id\`, \`usuario_id\`, \`refresh_token_hash\`, \`expira_en\`)
     VALUES (?, ?, ?, ?)`,
    [sessionId, user.id, refreshTokenHash, expiraEn]
  );

  const accessToken = generateAccessToken(user, roles, permissions, sessionId);

  // 7. Registrar evento de auditoría exitoso
  await logAuthEvent(pool, {
    userId: user.id,
    tipo: 'LOGIN',
    resultado: 'SUCCESS',
    ip,
    requestId
  });

  return {
    accessToken,
    refreshToken: refreshTokenRaw,
    tokenType: 'Bearer',
    expiresIn: 900, // 15 minutos en segundos
    user: {
      id: user.id,
      nombre: user.nombre,
      correo: user.correo,
      roles,
      permissions
    }
  };
}

/**
 * Renovación de sesión con rotación obligatoria (POST /api/auth/refresh)
 */
async function refresh({ refreshToken, ip, requestId }) {
  if (!refreshToken) {
    const error = new Error('El parámetro "refreshToken" es obligatorio');
    error.statusCode = 400;
    error.code = 'ValidationError';
    throw error;
  }

  const pool = getPool();
  const tokenHash = hashToken(refreshToken);

  // 1. Buscar la sesión por el hash del refresh token proporcionado
  const [sessions] = await pool.execute(
    'SELECT `id`, `usuario_id`, `revocada_en`, `expira_en` FROM `sesion` WHERE `refresh_token_hash` = ?',
    [tokenHash]
  );

  if (sessions.length === 0) {
    await logAuthEvent(pool, { tipo: 'REFRESH', resultado: 'FAILURE_TOKEN_NOT_FOUND', ip, requestId });
    const error = new Error('Token de refresco no reconocido o inválido');
    error.statusCode = 401;
    error.code = 'InvalidRefreshToken';
    throw error;
  }

  const session = sessions[0];

  // 2. DETECCIÓN DE REUTILIZACIÓN DE TOKEN ROTADO / REVOCADO:
  // Si se presenta un token que ya fue revocado (por ejemplo en una rotación anterior),
  // se revoca de inmediato TODA la sesión y sesiones activas del usuario por seguridad.
  if (session.revocada_en !== null) {
    await pool.execute(
      'UPDATE `sesion` SET `revocada_en` = NOW() WHERE `usuario_id` = ? AND `revocada_en` IS NULL',
      [session.usuario_id]
    );

    await logAuthEvent(pool, {
      userId: session.usuario_id,
      tipo: 'REFRESH',
      resultado: 'SECURITY_ALERT_REUSE_DETECTED',
      ip,
      requestId
    });

    const error = new Error('Reutilización de token rotado detectada. Todas las sesiones activas han sido revocadas por seguridad.');
    error.statusCode = 401;
    error.code = 'TokenReusedRevoked';
    throw error;
  }

  // 3. Validar expiración del refresh token
  if (new Date(session.expira_en) <= new Date()) {
    await logAuthEvent(pool, { userId: session.usuario_id, tipo: 'REFRESH', resultado: 'FAILURE_EXPIRED', ip, requestId });
    const error = new Error('El token de refresco ha expirado');
    error.statusCode = 401;
    error.code = 'RefreshTokenExpired';
    throw error;
  }

  // 4. Validar que el usuario siga existiendo y activo
  const [users] = await pool.execute(
    'SELECT `id`, `nombre`, `correo`, `activo` FROM `usuario` WHERE `id` = ?',
    [session.usuario_id]
  );

  if (users.length === 0 || !users[0].activo) {
    const error = new Error('Usuario inactivo o no encontrado');
    error.statusCode = 401;
    error.code = 'UserInactive';
    throw error;
  }

  const user = users[0];

  // 5. ROTACIÓN OBLIGATORIA:
  // Marcar la sesión anterior como revocada (de modo que si alguien intenta reutilizarla, se detecta el robo)
  await pool.execute(
    'UPDATE `sesion` SET `revocada_en` = NOW() WHERE `id` = ?',
    [session.id]
  );

  // Emitir nueva sesión y nuevo par de tokens
  const newSessionId = crypto.randomUUID();
  const newRefreshTokenRaw = generateRefreshToken();
  const newRefreshTokenHash = hashToken(newRefreshTokenRaw);
  const newExpiraEn = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);

  await pool.execute(
    `INSERT INTO \`sesion\` (\`id\`, \`usuario_id\`, \`refresh_token_hash\`, \`expira_en\`)
     VALUES (?, ?, ?, ?)`,
    [newSessionId, user.id, newRefreshTokenHash, newExpiraEn]
  );

  const { roles, permissions } = await getUserRolesAndPermissions(pool, user.id);
  const newAccessToken = generateAccessToken(user, roles, permissions, newSessionId);

  await logAuthEvent(pool, {
    userId: user.id,
    tipo: 'REFRESH',
    resultado: 'SUCCESS',
    ip,
    requestId
  });

  return {
    accessToken: newAccessToken,
    refreshToken: newRefreshTokenRaw,
    tokenType: 'Bearer',
    expiresIn: 900
  };
}

/**
 * Cierre de sesión (POST /api/auth/logout)
 */
async function logout({ sessionId, userId, ip, requestId }) {
  const pool = getPool();

  if (sessionId) {
    await pool.execute(
      'UPDATE `sesion` SET `revocada_en` = NOW() WHERE `id` = ?',
      [sessionId]
    );
  }

  await logAuthEvent(pool, {
    userId,
    tipo: 'LOGOUT',
    resultado: 'SUCCESS',
    ip,
    requestId
  });

  return { message: 'Sesión cerrada exitosamente' };
}

/**
 * Perfil autenticado (GET /api/auth/me)
 */
async function getMe({ userId }) {
  const pool = getPool();

  const [users] = await pool.execute(
    'SELECT `id`, `nombre`, `correo`, `activo`, `creado_en`, `actualizado_en` FROM `usuario` WHERE `id` = ?',
    [userId]
  );

  if (users.length === 0) {
    const error = new Error('Usuario no encontrado');
    error.statusCode = 404;
    error.code = 'UserNotFound';
    throw error;
  }

  const user = users[0];
  const { roles, permissions } = await getUserRolesAndPermissions(pool, user.id);

  return {
    id: user.id,
    nombre: user.nombre,
    correo: user.correo,
    activo: Boolean(user.activo),
    creadoEn: user.creado_en,
    actualizadoEn: user.actualizado_en,
    roles,
    permissions
  };
}

/**
 * Solicitud de recuperación de contraseña (POST /api/auth/password/forgot)
 * Genera token de recuperación con expiración corta sin filtrar existencia de correo.
 */
async function forgotPassword({ correo, ip, requestId }) {
  if (!correo) {
    const error = new Error('El campo "correo" es obligatorio');
    error.statusCode = 400;
    error.code = 'ValidationError';
    throw error;
  }

  const pool = getPool();

  // Control de intentos por correo
  const rateStatus = forgotPasswordRateLimiter.check(correo);
  if (rateStatus.blocked) {
    const error = new Error(`Demasiadas solicitudes de recuperación. Intente en ${rateStatus.retryAfterSeconds} segundos.`);
    error.statusCode = 429;
    error.code = 'RateLimitExceeded';
    throw error;
  }
  forgotPasswordRateLimiter.recordFailure(correo);

  const [users] = await pool.execute(
    'SELECT `id`, `activo` FROM `usuario` WHERE `correo` = ?',
    [correo.trim().toLowerCase()]
  );

  let resetToken = null;

  if (users.length > 0 && users[0].activo) {
    const user = users[0];
    resetToken = generateResetToken();
    const tokenHash = hashToken(resetToken);
    // Expiración corta de 1 hora
    const expiraEn = new Date(Date.now() + 60 * 60 * 1000);

    await pool.execute(
      `INSERT INTO \`recuperacion_contrasena\` (\`usuario_id\`, \`token_hash\`, \`expira_en\`)
       VALUES (?, ?, ?)`,
      [user.id, tokenHash, expiraEn]
    );

    await logAuthEvent(pool, {
      userId: user.id,
      tipo: 'PASSWORD_FORGOT',
      resultado: 'SUCCESS',
      ip,
      requestId
    });
  } else {
    await logAuthEvent(pool, {
      tipo: 'PASSWORD_FORGOT',
      resultado: 'USER_NOT_FOUND_OR_INACTIVE',
      ip,
      requestId
    });
  }

  // Respuesta unificada para no revelar la existencia o inexistencia del correo
  const response = {
    message: 'Si el correo electrónico está registrado en el sistema, se ha generado el enlace de recuperación correspondiente.'
  };

  // En entorno no de producción se incluye el token para facilitar pruebas automatizadas
  if (process.env.NODE_ENV !== 'production' && resetToken) {
    response.debugToken = resetToken;
  }

  return response;
}

/**
 * Restablecimiento de contraseña con token válido (POST /api/auth/password/reset)
 */
async function resetPassword({ token, nuevaPassword, ip, requestId }) {
  if (!token || !nuevaPassword) {
    const error = new Error('Los campos "token" y "nuevaPassword" son requeridos');
    error.statusCode = 400;
    error.code = 'ValidationError';
    throw error;
  }

  if (nuevaPassword.length < 6) {
    const error = new Error('La nueva contraseña debe tener al menos 6 caracteres');
    error.statusCode = 400;
    error.code = 'ValidationError';
    throw error;
  }

  const pool = getPool();
  const tokenHash = hashToken(token);

  // 1. Buscar token no usado y no expirado
  const [tokens] = await pool.execute(
    `SELECT \`id\`, \`usuario_id\`, \`expira_en\`, \`usada_en\`
     FROM \`recuperacion_contrasena\`
     WHERE \`token_hash\` = ?`,
    [tokenHash]
  );

  if (tokens.length === 0) {
    const error = new Error('Token de recuperación no válido o inexistente');
    error.statusCode = 400;
    error.code = 'InvalidToken';
    throw error;
  }

  const record = tokens[0];

  if (record.usada_en !== null) {
    const error = new Error('El token de recuperación ya ha sido utilizado');
    error.statusCode = 400;
    error.code = 'TokenAlreadyUsed';
    throw error;
  }

  if (new Date(record.expira_en) <= new Date()) {
    const error = new Error('El token de recuperación ha expirado');
    error.statusCode = 400;
    error.code = 'TokenExpired';
    throw error;
  }

  // 2. Actualizar hash de contraseña del usuario
  const newHash = await hashPassword(nuevaPassword);
  await pool.execute(
    'UPDATE `usuario` SET `password_hash` = ? WHERE `id` = ?',
    [newHash, record.usuario_id]
  );

  // 3. Marcar token como usado
  await pool.execute(
    'UPDATE `recuperacion_contrasena` SET `usada_en` = NOW() WHERE `id` = ?',
    [record.id]
  );

  // 4. Revocar todas las sesiones activas del usuario
  await pool.execute(
    'UPDATE `sesion` SET `revocada_en` = NOW() WHERE `usuario_id` = ? AND `revocada_en` IS NULL',
    [record.usuario_id]
  );

  await logAuthEvent(pool, {
    userId: record.usuario_id,
    tipo: 'PASSWORD_RESET',
    resultado: 'SUCCESS',
    ip,
    requestId
  });

  return { message: 'Contraseña restablecida exitosamente. Las sesiones previas han sido revocadas.' };
}

/**
 * Cambio de contraseña autenticado (POST /api/auth/password/change)
 */
async function changePassword({ userId, passwordActual, nuevaPassword, ip, requestId }) {
  if (!passwordActual || !nuevaPassword) {
    const error = new Error('Los campos "passwordActual" y "nuevaPassword" son obligatorios');
    error.statusCode = 400;
    error.code = 'ValidationError';
    throw error;
  }

  if (nuevaPassword.length < 6) {
    const error = new Error('La nueva contraseña debe tener al menos 6 caracteres');
    error.statusCode = 400;
    error.code = 'ValidationError';
    throw error;
  }

  const pool = getPool();

  const [users] = await pool.execute(
    'SELECT `id`, `password_hash` FROM `usuario` WHERE `id` = ?',
    [userId]
  );

  if (users.length === 0) {
    const error = new Error('Usuario no encontrado');
    error.statusCode = 404;
    error.code = 'UserNotFound';
    throw error;
  }

  const user = users[0];
  const isMatch = await comparePassword(passwordActual, user.password_hash);
  if (!isMatch) {
    const error = new Error('La contraseña actual es incorrecta');
    error.statusCode = 400;
    error.code = 'InvalidCurrentPassword';
    throw error;
  }

  const newHash = await hashPassword(nuevaPassword);
  await pool.execute(
    'UPDATE `usuario` SET `password_hash` = ? WHERE `id` = ?',
    [newHash, userId]
  );

  await logAuthEvent(pool, {
    userId,
    tipo: 'PASSWORD_CHANGE',
    resultado: 'SUCCESS',
    ip,
    requestId
  });

  return { message: 'Contraseña actualizada exitosamente' };
}

module.exports = {
  login,
  refresh,
  logout,
  getMe,
  forgotPassword,
  resetPassword,
  changePassword,
  getUserRolesAndPermissions
};
