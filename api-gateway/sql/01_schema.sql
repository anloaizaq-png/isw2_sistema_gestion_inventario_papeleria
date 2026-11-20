CREATE DATABASE IF NOT EXISTS `identidad`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `identidad`;

-- 1. Tabla: usuario
CREATE TABLE IF NOT EXISTS `usuario` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `nombre` VARCHAR(255) NOT NULL,
  `correo` VARCHAR(255) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `activo` BOOLEAN NOT NULL DEFAULT TRUE,
  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Tabla: rol
CREATE TABLE IF NOT EXISTS `rol` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `nombre` VARCHAR(100) NOT NULL UNIQUE,
  `descripcion` VARCHAR(255) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Tabla: permiso
CREATE TABLE IF NOT EXISTS `permiso` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `codigo` VARCHAR(100) NOT NULL UNIQUE,
  `descripcion` VARCHAR(255) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Tabla: rol_permiso
CREATE TABLE IF NOT EXISTS `rol_permiso` (
  `rol_id` BIGINT NOT NULL,
  `permiso_id` BIGINT NOT NULL,
  PRIMARY KEY (`rol_id`, `permiso_id`),
  CONSTRAINT `fk_rol_permiso_rol` FOREIGN KEY (`rol_id`) REFERENCES `rol` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rol_permiso_permiso` FOREIGN KEY (`permiso_id`) REFERENCES `permiso` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Tabla: usuario_rol
CREATE TABLE IF NOT EXISTS `usuario_rol` (
  `usuario_id` BIGINT NOT NULL,
  `rol_id` BIGINT NOT NULL,
  PRIMARY KEY (`usuario_id`, `rol_id`),
  CONSTRAINT `fk_usuario_rol_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuario` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_usuario_rol_rol` FOREIGN KEY (`rol_id`) REFERENCES `rol` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Tabla: sesion
CREATE TABLE IF NOT EXISTS `sesion` (
  `id` CHAR(36) NOT NULL PRIMARY KEY,
  `usuario_id` BIGINT NOT NULL,
  `refresh_token_hash` VARCHAR(255) NOT NULL UNIQUE,
  `creada_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expira_en` DATETIME NOT NULL,
  `revocada_en` DATETIME NULL,
  CONSTRAINT `fk_sesion_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuario` (`id`) ON DELETE CASCADE,
  INDEX `idx_sesion_usuario` (`usuario_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Tabla: recuperacion_contrasena
CREATE TABLE IF NOT EXISTS `recuperacion_contrasena` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `usuario_id` BIGINT NOT NULL,
  `token_hash` VARCHAR(255) NOT NULL UNIQUE,
  `creada_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expira_en` DATETIME NOT NULL,
  `usada_en` DATETIME NULL,
  CONSTRAINT `fk_recuperacion_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuario` (`id`) ON DELETE CASCADE,
  INDEX `idx_recuperacion_usuario` (`usuario_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Tabla: evento_autenticacion
CREATE TABLE IF NOT EXISTS `evento_autenticacion` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `usuario_id` BIGINT NULL,
  `tipo` VARCHAR(50) NOT NULL,
  `resultado` VARCHAR(50) NOT NULL,
  `ip_origen` VARCHAR(45) NULL,
  `request_id` VARCHAR(100) NULL,
  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_evento_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuario` (`id`) ON DELETE SET NULL,
  INDEX `idx_evento_usuario` (`usuario_id`),
  INDEX `idx_evento_ip_tipo` (`ip_origen`, `tipo`),
  INDEX `idx_evento_creado_en` (`creado_en`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
