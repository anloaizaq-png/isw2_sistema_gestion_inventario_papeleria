CREATE DATABASE IF NOT EXISTS analitica
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE analitica;

-- Nivel mínimo de stock configurable por producto o bodega
CREATE TABLE IF NOT EXISTS umbral_stock (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  producto_id   INT NOT NULL,
  bodega_id     INT NULL,
  stock_minimo  INT NOT NULL,
  activo        BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT chk_umbral_stock_minimo CHECK (stock_minimo >= 0),
  INDEX idx_umbral_producto (producto_id)
) ENGINE=InnoDB;

-- Temporadas con su multiplicador de demanda
CREATE TABLE IF NOT EXISTS temporada (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  nombre        VARCHAR(100) NOT NULL,
  fecha_inicio  DATE NOT NULL,
  fecha_fin     DATE NOT NULL,
  multiplicador DECIMAL(4,2) NOT NULL,
  CONSTRAINT chk_temporada_fechas CHECK (fecha_fin >= fecha_inicio),
  CONSTRAINT chk_temporada_multiplicador CHECK (multiplicador >= 1)
) ENGINE=InnoDB;

-- Alertas generadas por el sistema y su estado de atención
CREATE TABLE IF NOT EXISTS alerta (
  id                     INT AUTO_INCREMENT PRIMARY KEY,
  producto_id            INT NOT NULL,
  tipo                   VARCHAR(20) NOT NULL,
  estado                 VARCHAR(20) NOT NULL DEFAULT 'pendiente',
  stock_actual           INT NOT NULL,
  umbral_aplicado        INT NOT NULL,
  multiplicador_aplicado DECIMAL(4,2) NOT NULL DEFAULT 1.00,
  fecha_generacion       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_atencion         DATETIME NULL,
  usuario_atencion_id    INT NULL,
  CONSTRAINT chk_alerta_tipo
    CHECK (tipo IN ('stock_bajo', 'agotado', 'sin_movimiento')),
  CONSTRAINT chk_alerta_estado
    CHECK (estado IN ('pendiente', 'en_gestion', 'atendida', 'descartada')),
  INDEX idx_alerta_producto (producto_id),
  INDEX idx_alerta_estado (estado)
) ENGINE=InnoDB;

-- Recomendación de compra derivada de una alerta
CREATE TABLE IF NOT EXISTS sugerencia_reabastecimiento (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  alerta_id         INT NOT NULL,
  producto_id       INT NOT NULL,
  proveedor_id      INT NULL,
  cantidad_sugerida INT NOT NULL,
  estado            VARCHAR(20) NOT NULL DEFAULT 'pendiente',
  orden_compra_id   INT NULL,
  CONSTRAINT fk_sugerencia_alerta
    FOREIGN KEY (alerta_id) REFERENCES alerta(id),
  CONSTRAINT chk_sugerencia_cantidad CHECK (cantidad_sugerida > 0),
  CONSTRAINT chk_sugerencia_estado
    CHECK (estado IN ('pendiente', 'atendida')),
  INDEX idx_sugerencia_estado (estado)
) ENGINE=InnoDB;

-- Copia resumida del historial de ventas por producto y período (AAAA-MM)
CREATE TABLE IF NOT EXISTS resumen_ventas_producto (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  producto_id       INT NOT NULL,
  periodo           VARCHAR(7) NOT NULL,
  unidades_vendidas INT NOT NULL DEFAULT 0,
  ingresos          DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  CONSTRAINT uq_resumen_producto_periodo UNIQUE (producto_id, periodo)
) ENGINE=InnoDB;

-- Resultado del análisis de rotación y clasificación A, B o C
CREATE TABLE IF NOT EXISTS clasificacion_producto (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  producto_id     INT NOT NULL,
  categoria_abc   CHAR(1) NOT NULL,
  nivel_rotacion  VARCHAR(10) NOT NULL,
  indice_rotacion DECIMAL(8,2) NOT NULL DEFAULT 0.00,
  periodo_calculo VARCHAR(7) NOT NULL,
  CONSTRAINT chk_clasificacion_categoria
    CHECK (categoria_abc IN ('A', 'B', 'C')),
  CONSTRAINT chk_clasificacion_nivel
    CHECK (nivel_rotacion IN ('alta', 'media', 'baja')),
  CONSTRAINT uq_clasificacion_producto_periodo
    UNIQUE (producto_id, periodo_calculo)
) ENGINE=InnoDB;