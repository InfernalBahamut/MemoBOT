"""
Módulo de configuración para el bot de recordatorios.
Centraliza la carga de variables de entorno y validación.
"""

import os
import sys
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    """Clase para manejar la configuración de la aplicación."""
    
    def __init__(self):
        """Inicializa y carga la configuración desde variables de entorno."""
        load_dotenv()
        self._load_and_validate()
    
    def _load_and_validate(self):
        """Carga y valida las variables de entorno requeridas."""
        # Telegram
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        
        # Gemini
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.GEMINI_MODEL = os.getenv("GEMINI_MODEL")
        
        # Base de datos
        self.DB_HOST = os.getenv("DB_HOST", "localhost")
        self.DB_PORT = os.getenv("DB_PORT", "3306")
        self.DB_USER = os.getenv("DB_USER")
        self.DB_PASS = os.getenv("DB_PASS")
        self.DB_NAME = os.getenv("DB_NAME")
        
        # Scheduler
        self.SCHEDULER_INTERVAL = int(os.getenv("SCHEDULER_INTERVAL", "10"))
        
        # Validación
        self._validate_required_vars()
    
    def _validate_required_vars(self):
        """Valida que todas las variables requeridas estén presentes."""
        required_vars = {
            "TELEGRAM_TOKEN": self.TELEGRAM_TOKEN,
            "GEMINI_API_KEY": self.GEMINI_API_KEY,
            "DB_USER": self.DB_USER,
            "DB_PASS": self.DB_PASS,
            "DB_NAME": self.DB_NAME
        }
        
        missing_vars = [name for name, value in required_vars.items() if not value]
        
        if missing_vars:
            error_msg = f"Faltan variables de entorno: {', '.join(missing_vars)}"
            logger.critical(error_msg)
            sys.exit(f"Error: Revisa tu archivo .env, {error_msg}")
    
    @property
    def db_config(self):
        """Retorna la configuración de la base de datos como diccionario."""
        return {
            "host": self.DB_HOST,
            "port": self.DB_PORT,
            "user": self.DB_USER,
            "password": self.DB_PASS,
            "database": self.DB_NAME
        }


# Instancia global de configuración
config = Config()
