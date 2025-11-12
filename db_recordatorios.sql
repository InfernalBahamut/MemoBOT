-- ============================================
-- SCRIPT COMPLETO DE BASE DE DATOS (LIMPIO)
-- Bot de Recordatorios v3.2.0
-- Soporta: Múltiples recordatorios, Recurrencia (minutal/horario/diario/semanal/mensual/anual), Soft Delete, Control de Versiones
-- SIN DATOS DE EJEMPLO
-- ============================================

-- Crear base de datos
CREATE DATABASE IF NOT EXISTS recordatorios_db;
USE recordatorios_db;

-- Eliminar tabla si existe (para fresh install)
DROP TABLE IF EXISTS recordatorios;

-- ============================================
-- TABLA PRINCIPAL DE RECORDATORIOS
-- ============================================
CREATE TABLE recordatorios (
    -- Campos básicos
    id INT AUTO_INCREMENT PRIMARY KEY,
    chat_id BIGINT NOT NULL COMMENT 'ID del chat de Telegram',
    tarea TEXT NOT NULL COMMENT 'Descripción corta del recordatorio',
    fecha_hora DATETIME NOT NULL COMMENT 'Fecha y hora del recordatorio',
    notificado TINYINT(1) DEFAULT 0 COMMENT '0 = pendiente, 1 = enviado',
    
    -- Contexto completo del usuario
    contexto_original TEXT DEFAULT NULL COMMENT 'Contexto completo del usuario para IA',
    
    -- Campos de auditoría
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    username VARCHAR(255) DEFAULT NULL COMMENT 'Usuario de Telegram (@username)',
    
    -- Campos de recurrencia (TODOS en un solo registro)
    es_recurrente TINYINT(1) DEFAULT 0 COMMENT '0 = único, 1 = recurrente',
    tipo_recurrencia ENUM('minutal', 'horario', 'diario', 'semanal', 'mensual', 'anual') DEFAULT NULL COMMENT 'Tipo de repetición (minutal=minutos, horario=horas, etc)',
    intervalo_recurrencia INT DEFAULT 1 COMMENT 'Cada cuántos minutos/horas/días/semanas/meses/años',
    dias_semana VARCHAR(50) DEFAULT NULL COMMENT 'Para semanal: días separados por coma (0=Lun, 6=Dom)',
    fecha_fin_recurrencia DATETIME DEFAULT NULL COMMENT 'Fecha límite de recurrencia (NULL = infinito)',
    ultima_ejecucion DATETIME DEFAULT NULL COMMENT 'Última vez que se envió el recordatorio',
    
    -- Campos de borrado lógico (soft delete)
    eliminado TINYINT(1) DEFAULT 0 COMMENT '0 = activo, 1 = eliminado',
    fecha_eliminacion DATETIME DEFAULT NULL,
    usuario_eliminacion VARCHAR(255) DEFAULT NULL COMMENT 'Usuario que eliminó (@username)',
    
    -- Campos de control de versiones
    version INT DEFAULT 1 COMMENT 'Versión del recordatorio',
    recordatorio_original_id INT DEFAULT NULL COMMENT 'ID del recordatorio original (para versiones editadas)',
    es_version_actual TINYINT(1) DEFAULT 1 COMMENT '1 = versión actual, 0 = versión antigua',
    
    -- Índices para optimizar consultas
    INDEX idx_chat_id (chat_id),
    INDEX idx_fecha_hora (fecha_hora),
    INDEX idx_notificado (notificado),
    INDEX idx_eliminado (eliminado),
    INDEX idx_es_recurrente (es_recurrente),
    INDEX idx_chat_activos (chat_id, eliminado, notificado),
    INDEX idx_pendientes (fecha_hora, notificado, eliminado),
    INDEX idx_version_control (recordatorio_original_id, version, es_version_actual)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Recordatorios con soporte de recurrencia en un solo registro y control de versiones';

-- ============================================
-- PROCEDIMIENTOS ALMACENADOS
-- ============================================

DELIMITER //

-- Procedimiento para obtener recordatorios vencidos
CREATE PROCEDURE ObtenerRecordatoriosVencidos()
BEGIN
    SELECT 
        id,
        chat_id,
        tarea,
        contexto_original,
        fecha_hora,
        es_recurrente,
        tipo_recurrencia,
        intervalo_recurrencia,
        dias_semana,
        ultima_ejecucion
    FROM recordatorios
    WHERE eliminado = 0
      AND es_version_actual = 1
      AND (
          (es_recurrente = 0 AND notificado = 0 AND fecha_hora <= NOW())
          OR
          (es_recurrente = 1 AND (ultima_ejecucion IS NULL OR ultima_ejecucion < fecha_hora))
      )
    ORDER BY fecha_hora;
END //

-- Procedimiento para marcar recordatorio como notificado
CREATE PROCEDURE MarcarNotificado(IN p_id INT)
BEGIN
    UPDATE recordatorios
    SET notificado = 1,
        ultima_ejecucion = NOW()
    WHERE id = p_id;
END //

-- Procedimiento para calcular próxima ejecución de recurrente
CREATE PROCEDURE CalcularProximaEjecucion(
    IN p_id INT,
    IN p_tipo_recurrencia VARCHAR(20),
    IN p_intervalo INT
)
BEGIN
    DECLARE nueva_fecha DATETIME;
    
    SELECT fecha_hora INTO nueva_fecha FROM recordatorios WHERE id = p_id;
    
    CASE p_tipo_recurrencia
        WHEN 'minutal' THEN
            SET nueva_fecha = DATE_ADD(nueva_fecha, INTERVAL p_intervalo MINUTE);
        WHEN 'horario' THEN
            SET nueva_fecha = DATE_ADD(nueva_fecha, INTERVAL p_intervalo HOUR);
        WHEN 'diario' THEN
            SET nueva_fecha = DATE_ADD(nueva_fecha, INTERVAL p_intervalo DAY);
        WHEN 'semanal' THEN
            SET nueva_fecha = DATE_ADD(nueva_fecha, INTERVAL p_intervalo WEEK);
        WHEN 'mensual' THEN
            SET nueva_fecha = DATE_ADD(nueva_fecha, INTERVAL p_intervalo MONTH);
        WHEN 'anual' THEN
            SET nueva_fecha = DATE_ADD(nueva_fecha, INTERVAL p_intervalo YEAR);
    END CASE;
    
    UPDATE recordatorios
    SET fecha_hora = nueva_fecha,
        notificado = 0
    WHERE id = p_id;
END //

DELIMITER ;

-- ============================================
-- TRIGGERS PARA AUDITORÍA
-- ============================================

-- Trigger para registrar fecha de eliminación
DELIMITER //
CREATE TRIGGER before_recordatorio_delete
BEFORE UPDATE ON recordatorios
FOR EACH ROW
BEGIN
    IF NEW.eliminado = 1 AND OLD.eliminado = 0 THEN
        SET NEW.fecha_eliminacion = NOW();
    END IF;
END //
DELIMITER ;

-- ============================================
-- ÍNDICES ADICIONALES PARA PERFORMANCE
-- ============================================

-- Índice compuesto para consultas frecuentes del scheduler
CREATE INDEX idx_scheduler_query ON recordatorios(eliminado, notificado, fecha_hora, es_recurrente);

-- ============================================
-- VERIFICACIÓN
-- ============================================

-- Mostrar estructura de la tabla
DESCRIBE recordatorios;

-- Verificar que la tabla esté vacía
SELECT COUNT(*) as total_recordatorios FROM recordatorios;

-- ============================================
-- INFORMACIÓN DEL SCHEMA
-- ============================================

SELECT 
    'Base de datos creada exitosamente (sin datos de ejemplo)' AS estado,
    DATABASE() AS base_datos,
    (SELECT COUNT(*) FROM recordatorios) AS registros_ejemplo,
    VERSION() AS version_mysql;

-- ============================================
-- CONSULTAS ÚTILES PARA EL BOT
-- ============================================

-- 1. Ver recordatorios ACTIVOS (no eliminados, versión actual)
-- SELECT * FROM recordatorios WHERE eliminado = 0 AND es_version_actual = 1;

-- 2. Ver recordatorios PENDIENTES de notificación
-- SELECT * FROM recordatorios 
-- WHERE eliminado = 0 
--   AND es_version_actual = 1
--   AND notificado = 0 
--   AND fecha_hora <= NOW()
-- ORDER BY fecha_hora;

-- 3. Ver recordatorios FUTUROS de un chat específico
-- SELECT id, tarea, fecha_hora, es_recurrente, tipo_recurrencia
-- FROM recordatorios 
-- WHERE chat_id = 123456789 
--   AND eliminado = 0
--   AND es_version_actual = 1
--   AND (notificado = 0 OR es_recurrente = 1)
-- ORDER BY fecha_hora;

-- 4. Ver solo recordatorios RECURRENTES activos
-- SELECT id, tarea, tipo_recurrencia, intervalo_recurrencia, dias_semana
-- FROM recordatorios 
-- WHERE es_recurrente = 1 
--   AND eliminado = 0
--   AND es_version_actual = 1;

-- 5. Ver recordatorios ELIMINADOS (papelera)
-- SELECT id, tarea, fecha_eliminacion, usuario_eliminacion
-- FROM recordatorios 
-- WHERE eliminado = 1
-- ORDER BY fecha_eliminacion DESC;

-- 6. Ver HISTORIAL de versiones de un recordatorio
-- SELECT 
--     id,
--     tarea,
--     fecha_hora,
--     version,
--     es_version_actual,
--     fecha_modificacion
-- FROM recordatorios
-- WHERE recordatorio_original_id = 123 OR id = 123
-- ORDER BY version DESC;

-- 7. Estadísticas generales
-- SELECT 
--     COUNT(*) as total,
--     SUM(CASE WHEN eliminado = 0 AND es_version_actual = 1 THEN 1 ELSE 0 END) as activos,
--     SUM(CASE WHEN eliminado = 1 THEN 1 ELSE 0 END) as eliminados,
--     SUM(CASE WHEN es_recurrente = 1 AND eliminado = 0 AND es_version_actual = 1 THEN 1 ELSE 0 END) as recurrentes_activos,
--     SUM(CASE WHEN es_version_actual = 0 THEN 1 ELSE 0 END) as versiones_antiguas
-- FROM recordatorios;

-- ============================================
-- FIN DEL SCRIPT
-- Bot de Recordatorios v3.2.0 (Clean)
-- Incluye: Control de Versiones para Ediciones + Recurrencia Minutal/Horario
-- ============================================
