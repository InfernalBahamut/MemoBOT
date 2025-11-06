"""
Script de pruebas básicas para validar la configuración del bot.
Ejecutar antes de iniciar el bot en producción.
"""

import sys
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def test_imports():
    """Verifica que todos los módulos se puedan importar."""
    logger.info("🧪 Probando imports...")
    try:
        from config import config
        from database import DatabaseManager
        from gemini_service import GeminiService
        from scheduler import ReminderScheduler
        from handlers import TelegramHandlers
        logger.info("✅ Todos los módulos importados correctamente")
        return True
    except ImportError as e:
        logger.error(f"❌ Error al importar módulos: {e}")
        return False


def test_config():
    """Verifica la configuración."""
    logger.info("🧪 Probando configuración...")
    try:
        from config import config
        
        # Verificar que existan las variables críticas
        assert config.TELEGRAM_TOKEN, "TELEGRAM_TOKEN no configurado"
        assert config.GEMINI_API_KEY, "GEMINI_API_KEY no configurado"
        assert config.DB_USER, "DB_USER no configurado"
        assert config.DB_PASS, "DB_PASS no configurado"
        assert config.DB_NAME, "DB_NAME no configurado"
        
        logger.info(f"   Modelo Gemini: {config.GEMINI_MODEL}")
        logger.info(f"   DB Host: {config.DB_HOST}:{config.DB_PORT}")
        logger.info(f"   DB Name: {config.DB_NAME}")
        logger.info(f"   Scheduler Interval: {config.SCHEDULER_INTERVAL}s")
        logger.info("✅ Configuración válida")
        return True
    except AssertionError as e:
        logger.error(f"❌ Error en configuración: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        return False


def test_database():
    """Verifica la conexión a la base de datos."""
    logger.info("🧪 Probando conexión a base de datos...")
    try:
        from config import config
        from database import DatabaseManager
        
        db = DatabaseManager(config.db_config)
        
        # Intentar obtener una conexión
        with db.get_connection() as (conn, cursor):
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            logger.info(f"   MySQL Version: {version[0]}")
        
        logger.info("✅ Conexión a base de datos exitosa")
        return True
    except Exception as e:
        logger.error(f"❌ Error de base de datos: {e}")
        logger.error("   Verifica que MySQL esté corriendo y las credenciales sean correctas")
        return False


def test_gemini():
    """Verifica la configuración de Gemini."""
    logger.info("🧪 Probando servicio de Gemini...")
    try:
        from config import config
        from gemini_service import GeminiService
        
        gemini = GeminiService(config.GEMINI_API_KEY, config.GEMINI_MODEL)
        logger.info(f"   Modelo: {gemini.model_name}")
        logger.info("✅ Servicio de Gemini configurado")
        return True
    except Exception as e:
        logger.error(f"❌ Error configurando Gemini: {e}")
        logger.error("   Verifica tu GEMINI_API_KEY")
        return False


def test_scheduler():
    """Verifica el scheduler."""
    logger.info("🧪 Probando scheduler...")
    try:
        from config import config
        from database import DatabaseManager
        from scheduler import ReminderScheduler
        
        db = DatabaseManager(config.db_config)
        scheduler = ReminderScheduler(config.TELEGRAM_TOKEN, db, config.SCHEDULER_INTERVAL)
        
        logger.info(f"   Intervalo: {scheduler.interval}s")
        logger.info("✅ Scheduler creado correctamente")
        return True
    except Exception as e:
        logger.error(f"❌ Error creando scheduler: {e}")
        return False


def main():
    """Ejecuta todas las pruebas."""
    logger.info("=" * 60)
    logger.info("🚀 Iniciando pruebas del Bot de Recordatorios")
    logger.info("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Configuración", test_config),
        ("Base de Datos", test_database),
        ("Gemini AI", test_gemini),
        ("Scheduler", test_scheduler),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"❌ Error ejecutando prueba '{name}': {e}")
            results.append((name, False))
        logger.info("")
    
    # Resumen
    logger.info("=" * 60)
    logger.info("📊 RESUMEN DE PRUEBAS")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {name}")
    
    logger.info("-" * 60)
    logger.info(f"Resultado: {passed}/{total} pruebas pasadas")
    
    if passed == total:
        logger.info("🎉 ¡Todas las pruebas pasaron! El bot está listo para ejecutarse.")
        return 0
    else:
        logger.warning("⚠️ Algunas pruebas fallaron. Revisa los errores antes de ejecutar el bot.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
