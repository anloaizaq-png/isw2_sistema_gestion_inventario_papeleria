'use strict';

/**
 * Limitador de tasa (Rate Limiter) en memoria para protección contra fuerza bruta
 * Aplica control por correo electrónico e IP ante intentos fallidos de autenticación.
 */
class RateLimiter {
  constructor(options = {}) {
    // Número máximo de intentos fallidos antes de bloquear temporalmente
    this.maxAttempts = options.maxAttempts || 5;
    // Ventana de bloqueo temporal en milisegundos (por defecto 15 minutos)
    this.blockDurationMs = options.blockDurationMs || 15 * 60 * 1000;
    // Almacén en memoria de intentos por clave
    this.records = new Map();

    // Limpieza periódica de registros antiguos para prevenir fugas de memoria
    const cleanupInterval = options.cleanupIntervalMs || 5 * 60 * 1000;
    setInterval(() => this.cleanup(), cleanupInterval).unref();
  }

  /**
   * Genera la clave de identificación del intento (por correo normalizado)
   */
  _getKey(identifier) {
    return String(identifier).trim().toLowerCase();
  }

  /**
   * Verifica si el identificador está bloqueado
   * @param {string} identifier (ej. correo electrónico)
   * @returns {{ blocked: boolean, remainingAttempts: number, retryAfterSeconds: number }}
   */
  check(identifier) {
    const key = this._getKey(identifier);
    const now = Date.now();
    const record = this.records.get(key);

    if (!record) {
      return { blocked: false, remainingAttempts: this.maxAttempts, retryAfterSeconds: 0 };
    }

    // Si el registro ya expiró, se limpia
    if (now > record.resetAt) {
      this.records.delete(key);
      return { blocked: false, remainingAttempts: this.maxAttempts, retryAfterSeconds: 0 };
    }

    if (record.attempts >= this.maxAttempts) {
      const retryAfterSeconds = Math.ceil((record.resetAt - now) / 1000);
      return { blocked: true, remainingAttempts: 0, retryAfterSeconds };
    }

    return {
      blocked: false,
      remainingAttempts: Math.max(0, this.maxAttempts - record.attempts),
      retryAfterSeconds: 0
    };
  }

  /**
   * Registra un intento fallido
   * @param {string} identifier
   * @returns {{ blocked: boolean, remainingAttempts: number, retryAfterSeconds: number }}
   */
  recordFailure(identifier) {
    const key = this._getKey(identifier);
    const now = Date.now();
    let record = this.records.get(key);

    if (!record || now > record.resetAt) {
      record = {
        attempts: 1,
        resetAt: now + this.blockDurationMs
      };
    } else {
      record.attempts += 1;
    }

    this.records.set(key, record);

    const isBlocked = record.attempts >= this.maxAttempts;
    const retryAfterSeconds = Math.ceil((record.resetAt - now) / 1000);

    return {
      blocked: isBlocked,
      remainingAttempts: Math.max(0, this.maxAttempts - record.attempts),
      retryAfterSeconds: isBlocked ? retryAfterSeconds : 0
    };
  }

  /**
   * Restablece el contador ante un inicio de sesión exitoso
   * @param {string} identifier
   */
  reset(identifier) {
    const key = this._getKey(identifier);
    this.records.delete(key);
  }

  /**
   * Limpia registros vencidos
   */
  cleanup() {
    const now = Date.now();
    for (const [key, record] of this.records.entries()) {
      if (now > record.resetAt) {
        this.records.delete(key);
      }
    }
  }
}

// Instancia global para intentos de login (5 intentos, bloqueo 15 min)
const loginRateLimiter = new RateLimiter({
  maxAttempts: 5,
  blockDurationMs: 15 * 60 * 1000
});

// Instancia global para solicitudes de recuperación de contraseña (3 intentos, 15 min)
const forgotPasswordRateLimiter = new RateLimiter({
  maxAttempts: 3,
  blockDurationMs: 15 * 60 * 1000
});

module.exports = {
  RateLimiter,
  loginRateLimiter,
  forgotPasswordRateLimiter
};
