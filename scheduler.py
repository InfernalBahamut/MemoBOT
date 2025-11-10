"""
Módulo de scheduler para el bot de recordatorios.
Maneja el envío automático de recordatorios en segundo plano.
"""

import logging
import time
import threading
import asyncio
from telegram import Bot
from typing import Callable

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Scheduler para verificar y enviar recordatorios pendientes."""
    
    def __init__(self, bot_token: str, database_manager, gemini_service, interval: int = 10):
        """
        Inicializa el scheduler.
        
        Args:
            bot_token: Token del bot de Telegram
            database_manager: Instancia de DatabaseManager
            gemini_service: Instancia de GeminiService para generar mensajes
            interval: Intervalo en segundos entre verificaciones
        """
        self.bot_token = bot_token
        self.db = database_manager
        self.gemini = gemini_service
        self.interval = interval
        self.bot = Bot(token=bot_token)
        self._thread = None
        self._stop_event = threading.Event()
    
    def start(self):
        """Inicia el scheduler en un thread separado."""
        if self._thread and self._thread.is_alive():
            logger.warning("El scheduler ya está ejecutándose")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Scheduler iniciado exitosamente")
    
    def stop(self):
        """Detiene el scheduler."""
        if not self._thread or not self._thread.is_alive():
            logger.warning("El scheduler no está ejecutándose")
            return
        
        self._stop_event.set()
        self._thread.join(timeout=5)
        logger.info("Scheduler detenido")
    
    def _run(self):
        """Loop principal del scheduler."""
        logger.info(f"Iniciando loop del scheduler (intervalo: {self.interval}s)...")
        
        while not self._stop_event.is_set():
            try:
                self._check_and_send_reminders()
            except Exception as e:
                logger.error(f"Error en el loop del scheduler: {e}")
            
            # Esperar el intervalo o hasta que se detenga
            self._stop_event.wait(self.interval)
    
    def _check_and_send_reminders(self):
        """Verifica y envía los recordatorios pendientes."""
        try:
            # 1. Obtener recordatorios que deben ser enviados
            reminders = self.db.get_due_reminders()
            
            if not reminders:
                return
            
            logger.info(f"Encontrados {len(reminders)} recordatorios para enviar")
            
            # 2. Enviar mensajes y manejar recurrencia
            for r_id, chat_id, tarea, contexto_original in reminders:
                try:
                    # Verificar si es recurrente ANTES de procesar
                    recurrent_data = self.db.get_recurrent_reminder(r_id)
                    
                    # Enviar el recordatorio con contexto
                    self._send_reminder(chat_id, tarea, r_id, contexto_original)
                    
                    # Manejar recurrencia
                    if recurrent_data:
                        # Es recurrente: actualizar la fecha del MISMO registro
                        success = self.db.update_recurrent_reminder_next_date(r_id, recurrent_data)
                        if success:
                            logger.info(f"Recordatorio recurrente {r_id} actualizado a su próxima fecha")
                        else:
                            # Alcanzó la fecha límite, marcar como notificado
                            self.db.mark_as_notified([r_id])
                            logger.info(f"Recordatorio recurrente {r_id} finalizó (alcanzó fecha límite)")
                    else:
                        # No es recurrente: marcar como notificado (completado)
                        self.db.mark_as_notified([r_id])
                        logger.info(f"Recordatorio único {r_id} marcado como completado")
                
                except Exception as e:
                    logger.error(f"Error procesando recordatorio {r_id} a {chat_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error en _check_and_send_reminders: {e}")
    
    def _send_reminder(self, chat_id: int, tarea: str, reminder_id: int, contexto_original: str = None):
        """
        Envía un recordatorio a un chat con mensaje divertido generado por Gemini.
        Incluye el contexto original si está disponible.
        
        Args:
            chat_id: ID del chat
            tarea: Texto del recordatorio (en infinitivo)
            reminder_id: ID del recordatorio
            contexto_original: Texto original del usuario (opcional)
        """
        try:
            # Generar mensaje con humor usando Gemini
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            funny_msg = loop.run_until_complete(
                self.gemini.generate_funny_reminder_message(tarea, contexto_original)
            )
            loop.close()
            
            # Construir mensaje con contexto si está disponible
            mensaje = f"🔔 ¡RECORDATORIO! 🔔\n\n"
            mensaje += f"📌 <b>{tarea.capitalize()}</b>\n"
            
            # Agregar contexto si existe y es diferente de la tarea
            if contexto_original and contexto_original.strip().lower() != tarea.strip().lower():
                # Extraer información relevante del contexto
                contexto_limpio = self._extraer_contexto_relevante(contexto_original, tarea)
                if contexto_limpio:
                    mensaje += f"💬 <i>{contexto_limpio}</i>\n"
            
            mensaje += f"\n{funny_msg}"
            
            # Ejecutar el envío asíncrono en el loop
            asyncio.run(self.bot.send_message(chat_id=chat_id, text=mensaje, parse_mode="HTML"))
            logger.info(f"Recordatorio {reminder_id} enviado a {chat_id}")
        except Exception as e:
            logger.error(f"Error enviando recordatorio {reminder_id}: {e}")
            # Fallback: enviar sin mensaje de humor ni formato HTML
            mensaje = f"🔔 ¡RECORDATORIO! 🔔\n\n📌 {tarea}"
            if contexto_original and contexto_original.strip().lower() != tarea.strip().lower():
                mensaje += f"\n💬 {contexto_original}"
            asyncio.run(self.bot.send_message(chat_id=chat_id, text=mensaje))
    
    def _extraer_contexto_relevante(self, contexto_original: str, tarea: str) -> str:
        """
        Extrae información relevante del contexto original que no esté en la tarea.
        
        Args:
            contexto_original: Texto completo del usuario
            tarea: Tarea extraída (en infinitivo)
        
        Returns:
            str: Contexto relevante o cadena vacía
        """
        # Limpiar y normalizar
        contexto = contexto_original.strip()
        tarea_lower = tarea.lower()
        
        # Si el contexto es muy similar a la tarea, no mostrarlo
        if contexto.lower() == tarea_lower:
            return ""
        
        # Intentar extraer información adicional (ej: "para el examen de química")
        # Buscar patrones como "para", "de", "del", etc.
        palabras_clave = ["para el", "para la", "del", "de la", "de", "sobre", "acerca de"]
        
        for palabra in palabras_clave:
            if palabra in contexto.lower():
                # Encontrar la posición y extraer desde ahí
                idx = contexto.lower().find(palabra)
                fragmento = contexto[idx:].strip()
                # Limitar longitud
                if len(fragmento) > 100:
                    fragmento = fragmento[:97] + "..."
                return fragmento
        
        # Si no encontramos patrones específicos pero el contexto es diferente, mostrarlo completo
        if len(contexto) <= 100:
            return f"Contexto: {contexto}"
        else:
            return f"Contexto: {contexto[:97]}..."
