"""
Módulo de scheduler para el bot de recordatorios.
Maneja el envío automático de recordatorios en segundo plano.
"""

import logging
import time
import threading
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
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
            
            # Crear botón para volver al menú
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Ejecutar el envío asíncrono en el loop
            asyncio.run(self.bot.send_message(
                chat_id=chat_id, 
                text=mensaje, 
                parse_mode="HTML",
                reply_markup=reply_markup
            ))
            logger.info(f"Recordatorio {reminder_id} enviado a {chat_id}")
        except Exception as e:
            logger.error(f"Error enviando recordatorio {reminder_id}: {e}")
            # Fallback: enviar sin mensaje de humor ni formato HTML
            mensaje = f"🔔 ¡RECORDATORIO! 🔔\n\n📌 {tarea}"
            if contexto_original and contexto_original.strip().lower() != tarea.strip().lower():
                mensaje += f"\n💬 {contexto_original}"
            
            # Intentar enviar con botón incluso en fallback
            try:
                keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                asyncio.run(self.bot.send_message(
                    chat_id=chat_id, 
                    text=mensaje,
                    reply_markup=reply_markup
                ))
            except:
                # Si todo falla, enviar solo texto
                asyncio.run(self.bot.send_message(chat_id=chat_id, text=mensaje))
    
    def _extraer_contexto_relevante(self, contexto_original: str, tarea: str) -> str:
        """
        Extrae información relevante del contexto original que no esté en la tarea.
        Formatea el contexto de manera natural sin copiar literalmente.
        
        Args:
            contexto_original: Texto completo del usuario
            tarea: Tarea extraída (en infinitivo)
        
        Returns:
            str: Contexto relevante formateado naturalmente o cadena vacía
        """
        # Limpiar y normalizar
        contexto = contexto_original.strip().lower()
        tarea_lower = tarea.lower()
        
        # Si el contexto es muy similar a la tarea, no mostrarlo
        if contexto == tarea_lower or tarea_lower in contexto and len(contexto) - len(tarea_lower) < 5:
            return ""
        
        # Patrones para extraer información adicional
        patrones_temporales = {
            "mañana": "mañana",
            "pasado mañana": "pasado mañana", 
            "la semana que viene": "la próxima semana",
            "el lunes": "el lunes",
            "el martes": "el martes",
            "el miércoles": "el miércoles",
            "el jueves": "el jueves",
            "el viernes": "el viernes",
            "el sábado": "el sábado",
            "el domingo": "el domingo",
            "hoy": "hoy",
            "esta tarde": "esta tarde",
            "esta noche": "esta noche"
        }
        
        # Patrones de contexto con reformateo
        patrones_contexto = [
            # "para el examen de química" -> "Para el examen de química"
            (r"para el (.+)", lambda m: f"Para el {m.group(1)}"),
            (r"para la (.+)", lambda m: f"Para la {m.group(1)}"),
            (r"para (.+)", lambda m: f"Para {m.group(1)}"),
            
            # "del trabajo" -> "Del trabajo"
            (r"del (.+)", lambda m: f"Del {m.group(1)}"),
            (r"de la (.+)", lambda m: f"De la {m.group(1)}"),
            (r"de (.+)", lambda m: f"De {m.group(1)}"),
            
            # "sobre matemática" -> "Sobre matemática"
            (r"sobre (.+)", lambda m: f"Sobre {m.group(1)}"),
            (r"acerca de (.+)", lambda m: f"Acerca de {m.group(1)}"),
            
            # "con juan" -> "Con Juan"
            (r"con (.+)", lambda m: f"Con {m.group(1).title()}"),
            
            # "en el gimnasio" -> "En el gimnasio"
            (r"en el (.+)", lambda m: f"En el {m.group(1)}"),
            (r"en la (.+)", lambda m: f"En la {m.group(1)}"),
            (r"en (.+)", lambda m: f"En {m.group(1)}"),
            
            # "a las 10" (solo si tiene más contexto)
            (r"(.+) a las? \d{1,2}(?::\d{2})?", lambda m: m.group(1).strip().capitalize()),
        ]
        
        import re
        
        # Intentar extraer contexto con patrones
        for patron, formateador in patrones_contexto:
            match = re.search(patron, contexto)
            if match:
                try:
                    resultado = formateador(match)
                    # Evitar que sea demasiado largo
                    if len(resultado) > 80:
                        resultado = resultado[:77] + "..."
                    # Evitar que sea solo la tarea repetida
                    if resultado.lower() != tarea_lower and tarea_lower not in resultado.lower():
                        return resultado
                except:
                    continue
        
        # Si encontramos información temporal, formatearla
        for patron_temp, reemplazo in patrones_temporales.items():
            if patron_temp in contexto:
                # Intentar extraer más contexto alrededor de la referencia temporal
                partes = contexto.split(patron_temp)
                if len(partes) > 1 and partes[1].strip():
                    # Hay información después de la referencia temporal
                    info_extra = partes[1].strip()
                    # Limpiar conectores y palabras innecesarias
                    info_extra = re.sub(r'^(a las?|por|en|de|para)\s+', '', info_extra)
                    if info_extra and len(info_extra) > 3:
                        return f"{reemplazo.capitalize()}: {info_extra}"
                elif partes[0].strip() and len(partes[0].strip()) > len(tarea_lower):
                    # Hay información antes de la referencia temporal
                    return f"{reemplazo.capitalize()}"
        
        # Si no encontramos patrones específicos pero el contexto tiene info extra útil
        # Intentar limpiar la tarea del contexto y ver qué queda
        contexto_sin_tarea = contexto.replace(tarea_lower, "").strip()
        contexto_sin_tarea = re.sub(r'^(recordame|recuerdame|que|me|te)\s+', '', contexto_sin_tarea)
        contexto_sin_tarea = re.sub(r'\s+a las? \d{1,2}(?::\d{2})?\s*(?:hs?)?$', '', contexto_sin_tarea)
        
        if contexto_sin_tarea and len(contexto_sin_tarea) > 5:
            # Capitalizar y limitar longitud
            resultado = contexto_sin_tarea.strip().capitalize()
            if len(resultado) > 80:
                resultado = resultado[:77] + "..."
            return resultado
        
        return ""
