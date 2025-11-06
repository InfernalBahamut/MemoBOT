"""
Bot de Recordatorios con Telegram, Gemini y MySQL (Refactorizado)

Dependencias:
    - python-telegram-bot
    - google-generativeai
    - mysql-connector-python
    - python-dotenv

Arquitectura modular:
    - config.py: Configuración centralizada
    - database.py: Gestión de base de datos
    - gemini_service.py: Servicio de IA
    - scheduler.py: Scheduler de recordatorios
    - handlers.py: Handlers de Telegram
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)

# Importaciones de módulos propios
from config import config
from database import DatabaseManager
from gemini_service import GeminiService
from scheduler import ReminderScheduler
from handlers import TelegramHandlers, EDITANDO_RECORDATORIO, ESPERANDO_HORA

# --- Configuración de Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Inicia el bot y el scheduler."""
    logger.info("Iniciando Bot de Recordatorios...")
    
    # 1. Inicializar componentes
    db_manager = DatabaseManager(config.db_config)
    gemini_service = GeminiService(config.GEMINI_API_KEY, config.GEMINI_MODEL)
    handlers = TelegramHandlers(db_manager, gemini_service)
    
    # 2. Iniciar scheduler con gemini_service
    scheduler = ReminderScheduler(
        config.TELEGRAM_TOKEN,
        db_manager,
        gemini_service,  # Pasar gemini_service para generar mensajes dinámicos
        config.SCHEDULER_INTERVAL
    )
    scheduler.start()
    
    # 3. Configurar aplicación de Telegram
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    # --- Handlers (manejadores de comandos/mensajes) ---
    
    # Flujo de conversación de EDICIÓN
    conv_handler_edicion = ConversationHandler(
        entry_points=[
            CommandHandler("editar", handlers.edit_reminder_start),
            CallbackQueryHandler(handlers.edit_reminder_start_button, pattern='^edit:')
        ],
        states={
            EDITANDO_RECORDATORIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_edit_response)
            ]
        },
        fallbacks=[
            CommandHandler("cancelar", handlers.cancel_edit),
            CallbackQueryHandler(handlers.cancel_edit, pattern='^cancel_edit$')
        ],
        per_message=False
    )
    
    # Flujo de conversación de CREACIÓN (para pedir hora si falta)
    conv_handler_creacion = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.create_reminder)
        ],
        states={
            ESPERANDO_HORA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_hora_response)
            ]
        },
        fallbacks=[
            CommandHandler("cancelar", handlers.cancel_edit)
        ],
        per_message=False
    )
    
    application.add_handler(conv_handler_edicion)
    application.add_handler(conv_handler_creacion)
    
    # Comandos simples
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("menu", handlers.menu))
    application.add_handler(CommandHandler("listar", handlers.list_reminders))
    application.add_handler(CommandHandler("eliminar", handlers.delete_all_reminders))
    application.add_handler(CommandHandler("cancelar", handlers.cancel_edit))
    
    # Handler para botones
    application.add_handler(
        CallbackQueryHandler(handlers.handle_callback_query)
    )
    
    # NOTA: El MessageHandler para create_reminder ahora está en conv_handler_creacion
    # No agregar otro MessageHandler aquí para evitar conflictos
    
    logger.info("El bot está corriendo. Presioná Ctrl+C para detener.")
    
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("Deteniendo bot...")
        scheduler.stop()
    finally:
        logger.info("Bot detenido.")


if __name__ == "__main__":
    main()
