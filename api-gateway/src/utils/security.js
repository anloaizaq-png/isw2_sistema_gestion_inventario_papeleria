'use strict';

const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const config = require('../config');

const SALT_ROUNDS = 10;

/**
 * Hashea una contraseña con bcrypt
 * @param {string} password
 * @returns {Promise<string>}
 */
async function hashPassword(password) {
  return bcrypt.hash(password, SALT_ROUNDS);
}

/**
 * Compara una contraseña con su hash bcrypt
 * @param {string} password
 * @param {string} hash
 * @returns {Promise<boolean>}
 */
async function comparePassword(password, hash) {
  return bcrypt.compare(password, hash);
}

/**
 * Genera un Access Token JWT con los claims requeridos por la especificación:
 * sub, email, roles, permissions, sid, iss, aud, exp, iat
 * @param {object} user
 * @param {string[]} roles
 * @param {string[]} permissions
 * @param {string} sessionId
 * @returns {string}
 */
function generateAccessToken(user, roles, permissions, sessionId) {
  const payload = {
    sub: String(user.id),
    email: user.correo,
    nombre: user.nombre,
    roles: Array.isArray(roles) ? roles : [],
    permissions: Array.isArray(permissions) ? permissions : [],
    sid: sessionId
  };

  const options = {
    expiresIn: config.jwt.accessTtl,
    issuer: config.jwt.issuer,
    audience: config.jwt.audience
  };

  return jwt.sign(payload, config.jwt.secret, options);
}

/**
 * Valida y decodifica un Access Token JWT
 * @param {string} token
 * @returns {object} payload decodificado
 */
function verifyAccessToken(token) {
  return jwt.verify(token, config.jwt.secret, {
    issuer: config.jwt.issuer,
    audience: config.jwt.audience
  });
}

/**
 * Genera un Refresh Token criptográficamente seguro
 * @returns {string}
 */
function generateRefreshToken() {
  return crypto.randomBytes(40).toString('hex');
}

/**
 * Genera un token de recuperación de contraseña criptográficamente seguro
 * @returns {string}
 */
function generateResetToken() {
  return crypto.randomBytes(32).toString('hex');
}

module.exports = {
  hashPassword,
  comparePassword,
  generateAccessToken,
  verifyAccessToken,
  generateRefreshToken,
  generateResetToken
};
