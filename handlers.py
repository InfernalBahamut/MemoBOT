"""
Módulo de handlers de Telegram para el bot de recordatorios.
Centraliza toda la lógica de interacción con el usuario.
"""

import logging
import locale
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from timezone_utils import to_utc, to_argentina, now_for_user, format_datetime_argentina

logger = logging.getLogger(__name__)

# Estados para ConversationHandler
EDITANDO_RECORDATORIO = 1
ESPERANDO_HORA = 2


class TelegramHandlers:
    """Clase que agrupa todos los handlers del bot de Telegram."""
    
    def __init__(self, database_manager, gemini_service):
        """
        Inicializa los handlers.
        
        Args:
            database_manager: Instancia de DatabaseManager
            gemini_service: Instancia de GeminiService
        """
        self.db = database_manager
        self.gemini = gemini_service
        self._configure_locale()
    
    def _configure_locale(self):
        """Configura el locale para fechas en español."""
        try:
            # Intentar varios locales españoles
            for loc in ['es_ES.UTF-8', 'es_AR.UTF-8', 'es_ES', 'Spanish_Spain.1252', 'spanish']:
                try:
                    locale.setlocale(locale.LC_TIME, loc)
                    logger.info(f"Locale configurado: {loc}")
                    return
                except locale.Error:
                    continue
            
            # Si ninguno funciona, advertir pero continuar
            logger.warning("No se pudo configurar locale español, usando traducciones manuales")
        except Exception as e:
            logger.error(f"Error configurando locale: {e}")
    
    def _formatear_fecha_es(self, dt: datetime, formato: str = "completo") -> str:
        """
        Formatea una fecha en español sin depender del locale del sistema.
        
        Args:
            dt: Datetime a formatear
            formato: "completo" para día completo, "corto" para numérico
        
        Returns:
            str: Fecha formateada en español
        """
        # Nombres de días y meses en español
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        
        dia_semana = dias[dt.weekday()]
        mes = meses[dt.month - 1]
        
        if formato == "completo":
            # Formato: "lunes 11 de noviembre a las 10:00 hs"
            return f"{dia_semana} {dt.day} de {mes} a las {dt.strftime('%H:%M')} hs"
        elif formato == "lista":
            # Formato para listas: "lunes 11 de noviembre - 10:00 hs"
            return f"{dia_semana} {dt.day} de {mes} - {dt.strftime('%H:%M')} hs"
        elif formato == "corto":
            # Formato corto: "11/11/2025 - 10:00 hs"
            return dt.strftime('%d/%m/%Y - %H:%M hs')
        else:
            return f"{dia_semana} {dt.day} de {mes}"
    
    # ==================== COMANDOS PRINCIPALES ====================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /start. Da la bienvenida y muestra menú principal."""
        user_name = update.message.from_user.first_name
        
        # Menú principal simplificado (sin editar/eliminar)
        keyboard = [
            [InlineKeyboardButton("📝 Crear Recordatorio", callback_data="menu_crear")],
            [InlineKeyboardButton("📋 Ver Mis Recordatorios", callback_data="listar")],
            [InlineKeyboardButton("❓ Ayuda", callback_data="new_help")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        mensaje_bienvenida = (
            f"👋 <b>¡Hola {user_name}!</b>\n\n"
            "🤖 Soy tu <b>Bot de Recordatorios Inteligente</b>\n\n"
            "💡 Puedo entender lenguaje natural y ayudarte a recordar "
            "cualquier cosa que necesites.\n\n"
            "<b>¿Qué querés hacer?</b>"
        )
        
        await update.message.reply_html(
            mensaje_bienvenida,
            reply_markup=reply_markup
        )
    
    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /menu. Muestra el menú principal."""
        keyboard = [
            [InlineKeyboardButton("📝 Crear Recordatorio", callback_data="menu_crear")],
            [InlineKeyboardButton("📋 Ver Mis Recordatorios", callback_data="listar")],
            [InlineKeyboardButton("❓ Ayuda", callback_data="new_help")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            "🤖 <b>Menú Principal</b>\n\n"
            "<b>¿Qué querés hacer?</b>",
            reply_markup=reply_markup
        )
    
    async def create_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Maneja cualquier mensaje de texto para CREAR recordatorio(s).
        Primero clasifica si es sobre recordatorios o fuera de tema.
        Soporta múltiples recordatorios en un solo mensaje.
        Si falta la hora, pregunta al usuario de forma natural.
        
        Returns:
            int: Estado del ConversationHandler (ESPERANDO_HORA o ConversationHandler.END)
        """
        chat_id = update.message.chat_id
        texto_usuario = update.message.text
        username = update.message.from_user.username
        
        logger.info(f"Mensaje de {chat_id}: {texto_usuario}")
        
        # PASO 1: Clasificar el mensaje
        msg_temporal = await update.message.reply_text("🤔 Procesando...")
        respuesta_dialogo, es_recordatorio = await self.gemini.classify_and_respond(texto_usuario)
        
        # Si NO es recordatorio (saludo o fuera de tema), responder y terminar
        if not es_recordatorio:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_temporal.message_id,
                text=respuesta_dialogo
            )
            return ConversationHandler.END
        
        # PASO 2: Es un recordatorio, parsearlo
        recordatorios, error_msg = await self.gemini.parse_multiple_reminders(texto_usuario)
        
        if error_msg:
            await context.bot.edit_message_text(
                chat_id=chat_id, 
                message_id=msg_temporal.message_id, 
                text=error_msg
            )
            return ConversationHandler.END
        
        # PASO 3: Verificar si algún recordatorio no tiene hora
        recordatorios_sin_hora = [r for r in recordatorios if not r.get('hora_especificada', True)]
        
        if recordatorios_sin_hora:
            # Guardar en contexto para procesar después
            context.user_data['recordatorios_pendientes'] = recordatorios
            context.user_data['username'] = username
            context.user_data['msg_temporal_id'] = msg_temporal.message_id
            context.user_data['recordatorio_actual_index'] = 0
            
            # Preguntar hora para el primer recordatorio sin hora de forma natural
            primer_recordatorio = recordatorios_sin_hora[0]
            
            # Generar mensaje personalizado preguntando la hora
            mensaje_hora = await self.gemini.ask_for_time(
                primer_recordatorio['tarea'],
                primer_recordatorio['fecha']
            )
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_temporal.message_id,
                text=f"📅 <b>Recordatorio:</b> {primer_recordatorio['tarea']}\n\n"
                     f"📆 <b>Fecha:</b> {primer_recordatorio['fecha']}\n\n"
                     f"⏰ {mensaje_hora}\n\n"
                     f"<i>Ejemplo: 10:30, 15:00, 9am</i>",
                parse_mode="HTML"
            )
            
            return ESPERANDO_HORA
        
        # Si todos tienen hora, crear los recordatorios directamente
        await self._crear_multiples_recordatorios(
            update, context, recordatorios, username, msg_temporal.message_id
        )
        
        return ConversationHandler.END
    
    async def handle_hora_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Maneja la respuesta del usuario cuando se le pregunta la hora.
        """
        chat_id = update.message.chat_id
        hora_texto = update.message.text.strip()
        msg_temporal_id = context.user_data.get('msg_temporal_id')
        
        # Parsear hora con Gemini
        hora_parseada = await self._parsear_hora(hora_texto)
        
        if not hora_parseada:
            await update.message.reply_text(
                "🤔 Mmm, no entendí esa hora.\n\n"
                "Intentá con algo como:\n"
                "• <i>10:30</i>\n"
                "• <i>3pm</i>\n"
                "• <i>15:00</i>\n"
                "• <i>9 de la mañana</i>",
                parse_mode="HTML"
            )
            return ESPERANDO_HORA
        
        # Actualizar el primer recordatorio sin hora
        recordatorios = context.user_data.get('recordatorios_pendientes', [])
        username = context.user_data.get('username')
        
        for recordatorio in recordatorios:
            if not recordatorio.get('hora_especificada', True):
                recordatorio['hora'] = hora_parseada
                recordatorio['hora_especificada'] = True
                break
        
        # Verificar si quedan recordatorios sin hora
        recordatorios_sin_hora = [r for r in recordatorios if not r.get('hora_especificada', True)]
        
        if recordatorios_sin_hora:
            # Preguntar por el siguiente
            siguiente = recordatorios_sin_hora[0]
            await update.message.reply_text(
                f"✅ ¡Perfecto!\n\n"
                f"� <b>Siguiente recordatorio:</b> {siguiente['tarea']}\n\n"
                f"� <b>Fecha:</b> {siguiente['fecha']}\n\n"
                f"⏰ <b>¿A qué hora?</b>",
                parse_mode="HTML"
            )
            return ESPERANDO_HORA
        
        # Todos tienen hora, crear los recordatorios
        await self._crear_multiples_recordatorios(
            update, context, recordatorios, username, msg_temporal_id
        )
        
        # Limpiar contexto
        context.user_data.clear()
        
        return ConversationHandler.END
    
    async def _parsear_hora(self, hora_texto: str) -> str:
        """
        Parsea un texto de hora usando Gemini.
        
        Args:
            hora_texto: Texto con la hora (ej: "10am", "14:30", "3pm")
        
        Returns:
            str: Hora en formato HH:MM:SS o None si no se pudo parsear
        """
        prompt = f"""
Parsea esta hora al formato HH:MM:SS de 24 horas.

Texto: "{hora_texto}"

Ejemplos:
- "10am" → "10:00:00"
- "3pm" → "15:00:00"
- "14:30" → "14:30:00"
- "9" → "09:00:00"

Responde SOLO con la hora en formato HH:MM:SS o "ERROR" si no podés entender.
"""
        
        try:
            response = await self.gemini.model.generate_content_async(prompt)
            resultado = response.text.strip()
            
            # Validar formato HH:MM:SS
            if len(resultado) == 8 and resultado[2] == ':' and resultado[5] == ':':
                return resultado
            
            return None
        
        except Exception as e:
            logger.error(f"Error parseando hora: {e}")
            return None
    
    async def _crear_multiples_recordatorios(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        recordatorios: list,
        username: str,
        msg_temporal_id: int = None
    ) -> None:
        """
        Crea múltiples recordatorios en la base de datos.
        Incluye validaciones anti-flood y límites de seguridad.
        
        Args:
            update: Update de Telegram
            context: Contexto de Telegram
            recordatorios: Lista de diccionarios con la info de cada recordatorio
            username: Username del usuario
            msg_temporal_id: ID del mensaje temporal a editar (opcional)
        """
        chat_id = update.effective_chat.id
        
        # ==================== VALIDACIONES ANTI-FLOOD ====================
        
        # 1. Límite de recordatorios activos totales por chat (máximo 200)
        LIMITE_RECORDATORIOS_ACTIVOS = 200
        activos_actuales = self.db.count_active_reminders(chat_id)
        
        if activos_actuales >= LIMITE_RECORDATORIOS_ACTIVOS:
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            mensaje = (
                f"⚠️ <b>Límite alcanzado</b>\n\n"
                f"Ya tenés {activos_actuales} recordatorios activos.\n"
                f"Por favor, eliminá algunos antes de crear nuevos.\n\n"
                f"📋 Usá /listar para ver tus recordatorios."
            )
            
            if msg_temporal_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_temporal_id,
                    text=mensaje,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_html(mensaje, reply_markup=reply_markup)
            return
        
        # 2. Límite de creaciones por minuto (máximo 20 por minuto para prevenir spam)
        LIMITE_POR_MINUTO = 20
        creaciones_recientes = self.db.count_recent_creations(chat_id, minutes=1)
        
        if creaciones_recientes >= LIMITE_POR_MINUTO:
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            mensaje = (
                f"⚠️ <b>Límite de velocidad</b>\n\n"
                f"Estás creando recordatorios muy rápido.\n"
                f"Por favor, esperá un minuto antes de continuar."
            )
            
            if msg_temporal_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_temporal_id,
                    text=mensaje,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_html(mensaje, reply_markup=reply_markup)
            return
        
        # 3. Verificar que no se exceda el límite con los nuevos recordatorios
        if activos_actuales + len(recordatorios) > LIMITE_RECORDATORIOS_ACTIVOS:
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            disponibles = LIMITE_RECORDATORIOS_ACTIVOS - activos_actuales
            mensaje = (
                f"⚠️ <b>Límite excedido</b>\n\n"
                f"Solo podés crear {disponibles} recordatorios más.\n"
                f"Actualmente tenés {activos_actuales} activos de {LIMITE_RECORDATORIOS_ACTIVOS} máximo."
            )
            
            if msg_temporal_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_temporal_id,
                    text=mensaje,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_html(mensaje, reply_markup=reply_markup)
            return
        
        # ==================== CREAR RECORDATORIOS ====================
        
        creados = []
        errores = []
        
        for recordatorio in recordatorios:
            try:
                # Combinar fecha y hora (Gemini devuelve en hora Argentina)
                fecha_str = recordatorio.get('fecha')
                hora_str = recordatorio.get('hora', '00:00:00')
                
                # Si no hay fecha (solo tiene fecha_hora ya combinada)
                if not fecha_str and recordatorio.get('fecha_hora'):
                    fecha_hora_str = recordatorio['fecha_hora']
                    fecha_hora_obj = datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S')
                else:
                    fecha_hora_str = f"{fecha_str} {hora_str}"
                    fecha_hora_obj = datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S')
                
                # Convertir de hora Argentina a UTC para almacenar
                fecha_hora_utc = to_utc(fecha_hora_obj)
                
                # Verificar si es recurrente
                if recordatorio.get('es_recurrente'):
                    tipo_rec = recordatorio.get('tipo_recurrencia')
                    intervalo_rec = recordatorio.get('intervalo_recurrencia') or recordatorio.get('intervalo', 1)
                    
                    # VALIDAR INTERVALO DE RECURRENCIA
                    es_valido, error_validacion = self.db.validate_recurrence_interval(tipo_rec, intervalo_rec)
                    
                    if not es_valido:
                        errores.append(f"{recordatorio['tarea']}: {error_validacion}")
                        logger.warning(f"Intervalo inválido: {error_validacion}")
                        continue
                    
                    # Crear recurrence_data completo para recordatorio recurrente
                    recurrence_data = {
                        'contexto_original': recordatorio.get('contexto_original') or recordatorio.get('contexto', recordatorio['tarea']),
                        'es_recurrente': True,
                        'tipo_recurrencia': tipo_rec,
                        'intervalo_recurrencia': intervalo_rec,
                        'dias_semana': recordatorio.get('dias_semana'),
                        'fecha_fin_recurrencia': recordatorio.get('fecha_fin_recurrencia') or recordatorio.get('fecha_fin')
                    }
                else:
                    # Recordatorio único, solo contexto
                    recurrence_data = {
                        'contexto_original': recordatorio.get('contexto_original') or recordatorio.get('contexto', recordatorio['tarea']),
                        'es_recurrente': False,
                        'tipo_recurrencia': None,
                        'intervalo_recurrencia': None,
                        'dias_semana': None,
                        'fecha_fin_recurrencia': None
                    }
                
                # Guardar en base de datos (fecha_hora_utc está en UTC)
                nuevo_id = self.db.create_reminder(
                    chat_id, 
                    recordatorio['tarea'], 
                    fecha_hora_utc, 
                    recurrence_data,
                    username
                )
                
                creados.append({
                    'id': nuevo_id,
                    'tarea': recordatorio['tarea'],
                    'fecha_hora': fecha_hora_obj,  # Guardar en Argentina para mostrar
                    'es_recurrente': recordatorio.get('es_recurrente', False),
                    'tipo_recurrencia': recordatorio.get('tipo_recurrencia')
                })
            
            except Exception as e:
                logger.error(f"Error creando recordatorio: {e}")
                errores.append(recordatorio['tarea'])
        
        # Construir mensaje de confirmación
        keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not creados:
            mensaje = "❌ <b>No se pudo crear ningún recordatorio</b>\n\n"
            if errores:
                mensaje += "Hubo problemas con:\n"
                for error in errores:
                    mensaje += f"• {error}\n"
        
        elif len(creados) == 1:
            # Un solo recordatorio
            r = creados[0]
            if r.get('es_recurrente'):
                tipo_texto = {
                    'diario': 'diariamente',
                    'semanal': 'semanalmente',
                    'mensual': 'mensualmente',
                    'anual': 'anualmente'
                }.get(r.get('tipo_recurrencia'), 'periódicamente')
                
                mensaje = (
                    f"✅ <b>¡Recordatorio recurrente agendado!</b>\n\n"
                    f"📌 <i>{r['tarea']}</i>\n\n"
                    f"🔄 <b>Se repetirá {tipo_texto}</b>\n"
                    f"📅 <b>Primera vez:</b> {self._formatear_fecha_es(r['fecha_hora'], 'completo')}\n\n"
                    f"💡 Usá /listar para ver todos tus recordatorios"
                )
            else:
                mensaje = (
                    f"✅ <b>¡Recordatorio agendado!</b>\n\n"
                    f"📌 <i>{r['tarea']}</i>\n\n"
                    f"📅 {self._formatear_fecha_es(r['fecha_hora'], 'completo')}\n\n"
                    f"💡 Usá /listar para ver todos tus recordatorios"
                )
        
        else:
            # Múltiples recordatorios
            mensaje = f"✅ <b>¡{len(creados)} recordatorios agendados!</b>\n\n"
            
            for r in creados:
                mensaje += f"📌 <i>{r['tarea']}</i>\n"
                mensaje += f"📅 {self._formatear_fecha_es(r['fecha_hora'], 'lista')}\n"
                mensaje += "─────────────────────\n"
            
            mensaje += "\n💡 Usá /listar para ver todos tus recordatorios"
            
            if errores:
                mensaje += "\n\n⚠️ No se pudieron crear:\n"
                for error in errores:
                    mensaje += f"• {error}\n"
        
        # Enviar o editar mensaje
        if msg_temporal_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_temporal_id,
                text=mensaje,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        else:
            # Si no hay mensaje temporal, usar el mensaje del update
            message = update.callback_query.message if update.callback_query else update.message
            await message.reply_html(mensaje, reply_markup=reply_markup)
    
    async def list_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /listar. Muestra solo los recordatorios en curso (futuros)."""
        chat_id = update.effective_chat.id
        
        # Determinar si viene de callback o mensaje
        is_callback = update.callback_query is not None
        message = update.callback_query.message if is_callback else update.message
        
        try:
            upcoming_jobs = self.db.get_upcoming_reminders(chat_id)
            
            if not upcoming_jobs:
                keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                mensaje = (
                    "📭 No tenés recordatorios para esta semana.\n\n"
                    "💡 <i>Tip: El listado muestra solo los próximos 7 días</i>\n\n"
                    "¡Creá uno escribiendo qué querés recordar!"
                )
                
                if is_callback:
                    # Si viene de callback, editar el mensaje existente
                    await update.callback_query.edit_message_text(
                        mensaje,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    # Si viene de comando, crear nuevo mensaje
                    await message.reply_html(mensaje, reply_markup=reply_markup)
                return
            
            keyboard = []
            message_text = (
                f"📋 <b>Recordatorios de esta semana ({len(upcoming_jobs)}):</b>\n"
                f"<i>Mostrando próximos 7 días</i>\n\n"
            )
            
            # Mostrar solo recordatorios en curso (futuros)
            for job_id, tarea, fecha_hora in upcoming_jobs:
                # Convertir de UTC (desde BD) a hora Argentina para mostrar
                fecha_hora_arg = to_argentina(fecha_hora)
                
                # Truncar tarea para mostrar en botón
                tarea_corta = (tarea[:30] + '...') if len(tarea) > 30 else tarea
                message_text += f"📌 <b>{tarea}</b>\n"
                message_text += f"📅 {self._formatear_fecha_es(fecha_hora_arg, 'lista')}\n"
                
                keyboard.append([
                    InlineKeyboardButton(f"✏️ {tarea_corta}", callback_data=f"edit:{job_id}"),
                    InlineKeyboardButton("🗑️", callback_data=f"del:{job_id}")
                ])
                message_text += "─────────────────────\n"
            
            keyboard.append([InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if is_callback:
                # Si viene de callback, editar el mensaje existente
                await update.callback_query.edit_message_text(
                    message_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                # Si viene de comando, crear nuevo mensaje
                await message.reply_html(message_text, reply_markup=reply_markup)
        
        except Exception as e:
            logger.error(f"Error listando recordatorios: {e}")
            await message.reply_text("Error al consultar tus recordatorios.")

    async def delete_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE, job_id_from_button: int = None, confirmed: bool = False) -> None:
        """Elimina un recordatorio (llamado desde un botón) con confirmación."""
        chat_id = update.effective_chat.id
        username = update.effective_user.username if update.effective_user else None
        
        try:
            job_id = job_id_from_button
            
            if not job_id:
                await update.message.reply_text(
                    "Para eliminar un recordatorio, usá los botones desde /listar\n\n"
                    "O presioná el botón 🗑️ junto al recordatorio que querés borrar."
                )
                return
        
        except (ValueError, TypeError):
            await update.message.reply_text("Ocurrió un error.")
            return
        except AttributeError:
            pass
        
        try:
            # Obtener info del recordatorio antes de borrar
            job = self.db.get_reminder_by_id(job_id, chat_id)
            
            if not job:
                if update.callback_query:
                    await update.callback_query.answer("Este recordatorio ya no existe", show_alert=True)
                    # Actualizar la lista
                    await self.list_reminders(update, context)
                else:
                    await update.message.reply_text("No encontré ese recordatorio (quizás ya fue borrado).")
                return
            
            tarea, fecha_hora, contexto_original = job
            
            # Si no está confirmado, pedir confirmación
            if not confirmed:
                tarea_corta = (tarea[:50] + '...') if len(tarea) > 50 else tarea
                keyboard = [
                    [InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"delconfirm:{job_id}")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="delcancel")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                mensaje_confirmacion = (
                    f"⚠️ <b>¿Confirmar eliminación?</b>\n\n"
                    f"📌 <i>{tarea_corta}</i>\n"
                    f"📅 {fecha_hora.strftime('%d/%m/%Y - %H:%M hs')}"
                )
                
                if update.callback_query:
                    await update.callback_query.answer()
                    # Editar el mensaje de la lista para mostrar confirmación
                    await update.callback_query.edit_message_text(
                        mensaje_confirmacion,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                return
            
            # Si está confirmado, proceder con la eliminación
            deleted = self.db.delete_reminder(job_id, chat_id, username)
            
            if deleted:
                tarea_corta = (tarea[:40] + '...') if len(tarea) > 40 else tarea
                
                if update.callback_query:
                    await update.callback_query.answer("✅ Eliminado", show_alert=True)
                    # Actualizar la lista automáticamente (esto refresca la vista)
                    await self.list_reminders(update, context)
                else:
                    keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    message_to_send = f"✅ <b>Recordatorio eliminado:</b>\n<i>{tarea_corta}</i>"
                    await update.message.reply_html(message_to_send, reply_markup=reply_markup)
        
        except Exception as e:
            logger.error(f"Error borrando recordatorio: {e}")
            if update.callback_query:
                await update.callback_query.message.reply_text("Hubo un error al intentar borrar.")
            else:
                await update.message.reply_text("Hubo un error al intentar borrar.")
    
    async def delete_all_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE, confirmed: bool = False) -> None:
        """Comando /eliminar. Pide confirmación con botones."""
        chat_id = update.effective_chat.id
        message = update.message or update.callback_query.message
        username = update.effective_user.username if update.effective_user else None
        
        if not confirmed:
            keyboard = [
                [InlineKeyboardButton("Sí, eliminar todo", callback_data="delall_confirm")],
                [InlineKeyboardButton("No, cancelar", callback_data="delall_cancel")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "⚠️ ¿Estás seguro de que querés borrar TODOS tus recordatorios pendientes?", 
                reply_markup=reply_markup
            )
            return
        
        try:
            count = self.db.delete_all_reminders(chat_id, username)
            
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                if count == 0:
                    await update.callback_query.edit_message_text(
                        "No tenías recordatorios pendientes para borrar.",
                        reply_markup=reply_markup
                    )
                else:
                    await update.callback_query.edit_message_text(
                        f"¡Listo! Borré {count} recordatorios pendientes.",
                        reply_markup=reply_markup
                    )
        
        except Exception as e:
            logger.error(f"Error eliminando todos los recordatorios: {e}")
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    "Hubo un error al intentar borrar todo.",
                    reply_markup=reply_markup
                )
    
    # ==================== EDICIÓN DE RECORDATORIOS ====================
    
    async def _iniciar_edicion(self, chat_id: int, job_id: int, context: ContextTypes.DEFAULT_TYPE) -> tuple:
        """Helper interno para iniciar la edición."""
        try:
            job = self.db.get_reminder_by_id(job_id, chat_id)
            
            if not job:
                mensaje = "No encontré ese recordatorio (quizás ya fue borrado)."
                return False, mensaje, None
            
            tarea, fecha_hora, contexto_original = job
            
            # Convertir fecha de UTC (desde BD) a hora Argentina para mostrar
            fecha_hora_arg = to_argentina(fecha_hora)
            
            # Verificar que sea un recordatorio futuro
            if fecha_hora_arg <= now_for_user():
                mensaje = (
                    "⚠️ <b>No se puede editar este recordatorio</b>\n\n"
                    "Solo podés editar recordatorios que aún no hayan vencido.\n\n"
                    "Este recordatorio ya pasó su fecha y hora programada."
                )
                return False, mensaje, None
            
            # Guardar los datos originales para el contexto
            context.user_data['job_to_edit'] = job_id
            context.user_data['job_original_tarea'] = tarea
            context.user_data['job_original_fecha'] = fecha_hora
            context.user_data['job_original_contexto'] = contexto_original
            
            keyboard = [[InlineKeyboardButton("❌ Cancelar edición", callback_data="cancel_edit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            mensaje = (
                f"✏️ <b>Editando recordatorio:</b>\n"
                f"<i>'{tarea}'</i>\n"
                f"📅 {self._formatear_fecha_es(fecha_hora_arg, 'completo')}\n\n"
                f"💬 <b>Escribí qué querés cambiar</b>\n\n"
                f"Podés hacer cambios incrementales:\n"
                f"• <i>El examen era el martes no el lunes</i>\n"
                f"• <i>Mejor a las 15 en vez de las 18</i>\n"
                f"• <i>Cambiar a comprar pan en vez de leche</i>\n\n"
                f"O reescribir todo:\n"
                f"• <i>Comprar pan mañana a las 10</i>"
            )
            return True, mensaje, reply_markup
        
        except Exception as e:
            logger.error(f"Error iniciando edición: {e}")
            return False, "Error al buscar el recordatorio.", None
    
    async def edit_reminder_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ya no se usa comando /editar con ID, solo botones."""
        await update.message.reply_html(
            "✏️ <b>Para editar un recordatorio:</b>\n\n"
            "1️⃣ Usa el comando /listar\n"
            "2️⃣ Presioná el botón ✏️ del recordatorio que querés editar\n\n"
            "💡 Solo podés editar recordatorios que aún no hayan vencido."
        )
        return ConversationHandler.END
    
    async def edit_reminder_start_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Inicia la edición desde un botón."""
        query = update.callback_query
        await query.answer()
        
        chat_id = query.message.chat_id
        job_id = int(query.data.split(":")[1])
        
        success, mensaje, reply_markup = await self._iniciar_edicion(chat_id, job_id, context)
        await query.message.reply_html(mensaje, reply_markup=reply_markup)
        
        return EDITANDO_RECORDATORIO if success else ConversationHandler.END
    
    async def handle_edit_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Procesa la respuesta del usuario con los nuevos datos."""
        chat_id = update.message.chat_id
        texto_usuario = update.message.text
        
        # Recuperar datos originales SIN hacer pop (mantenerlos para reintentos)
        old_job_id = context.user_data.get('job_to_edit')
        tarea_original = context.user_data.get('job_original_tarea')
        fecha_original = context.user_data.get('job_original_fecha')
        contexto_original = context.user_data.get('job_original_contexto')
        
        if not old_job_id or not tarea_original or not fecha_original:
            # Limpiar datos si faltan
            context.user_data.pop('job_to_edit', None)
            context.user_data.pop('job_original_tarea', None)
            context.user_data.pop('job_original_fecha', None)
            context.user_data.pop('job_original_contexto', None)
            
            await update.message.reply_text("⚠️ Ocurrió un error. Usá /listar y presioná el botón ✏️")
            return ConversationHandler.END
        
        msg_temporal = await update.message.reply_text("⏳ Procesando tu edición...")
        
        # Parsear usando el nuevo método con contexto
        tarea, fecha_hora_obj, error_msg, recurrence_data = await self.gemini.parse_reminder_edit(
            texto_usuario, 
            tarea_original, 
            fecha_original,
            contexto_original
        )
        
        if error_msg:
            # Crear botón de cancelar
            keyboard = [[InlineKeyboardButton("❌ Cancelar edición", callback_data="cancel_edit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.edit_message_text(
                chat_id=chat_id, 
                message_id=msg_temporal.message_id, 
                text=f"{error_msg}\n\n💬 <b>Intentá de nuevo o cancelá:</b>",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            return EDITANDO_RECORDATORIO
        
        # Validar que la nueva fecha sea futura (solo si no es recurrente)
        es_recurrente = recurrence_data and recurrence_data.get('tipo')
        if not es_recurrente and fecha_hora_obj <= now_for_user():
            # Crear botón de cancelar
            keyboard = [[InlineKeyboardButton("❌ Cancelar edición", callback_data="cancel_edit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.edit_message_text(
                chat_id=chat_id, 
                message_id=msg_temporal.message_id,
                text="⚠️ <b>La fecha debe ser en el futuro.</b>\n\n💬 Intentá con una fecha posterior o cancelá:",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            return EDITANDO_RECORDATORIO
        
        try:
            # Convertir de hora Argentina a UTC para almacenar
            fecha_hora_utc = to_utc(fecha_hora_obj)
            
            # Extraer nuevo contexto
            # Si es recurrente y viene contexto en recurrence_data, usarlo
            # Si no, usar texto_usuario como nuevo contexto (la solicitud completa de edición)
            if recurrence_data and recurrence_data.get('contexto_original'):
                nuevo_contexto = recurrence_data.get('contexto_original')
            else:
                # Usar el texto del usuario como contexto (ej: "mejor hoy a las 20.00")
                # Esto permite que Gemini extraiga info útil al momento de notificar
                nuevo_contexto = texto_usuario
            
            # Actualizar con el nuevo contexto
            self.db.update_reminder(old_job_id, chat_id, tarea, fecha_hora_utc, nuevo_contexto)
            
            # Limpiar datos de edición (solo cuando es exitoso)
            context.user_data.pop('job_to_edit', None)
            context.user_data.pop('job_original_tarea', None)
            context.user_data.pop('job_original_fecha', None)
            context.user_data.pop('job_original_contexto', None)
            
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            mensaje_confirmacion = (
                f"✅ <b>Recordatorio actualizado!</b>\n\n"
                f"📌 <b>Nuevo recordatorio:</b>\n"
                f"<i>'{tarea}'</i>\n\n"
                f"📅 <b>Nueva fecha:</b>\n{self._formatear_fecha_es(fecha_hora_obj, 'completo')}"
            )
            await context.bot.edit_message_text(
                chat_id=chat_id, 
                message_id=msg_temporal.message_id,
                text=mensaje_confirmacion, 
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        
        except Exception as e:
            logger.error(f"Error actualizando recordatorio: {e}")
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.edit_message_text(
                chat_id=chat_id, 
                message_id=msg_temporal.message_id,
                text="Error al actualizar en la base de datos.",
                reply_markup=reply_markup
            )
        
        return ConversationHandler.END
    
    async def cancel_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Comando /cancelar o botón de 'Cancelar'."""
        # Limpiar todos los datos de edición
        context.user_data.pop('job_to_edit', None)
        context.user_data.pop('job_original_tarea', None)
        context.user_data.pop('job_original_fecha', None)
        context.user_data.pop('job_original_contexto', None)
        
        logger.info(f"Usuario {update.effective_chat.id} canceló la edición")
        
        keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ <b>Edición cancelada.</b>\n\nNo se hicieron cambios al recordatorio.",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ <b>Edición cancelada.</b>\n\nNo se hicieron cambios al recordatorio.",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        
        return ConversationHandler.END
    
    # ==================== CALLBACKS DE BOTONES ====================
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja TODAS las pulsaciones de botones."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        logger.info(f"Callback recibido: {data}")
        
        if data.startswith("del:"):
            job_id = int(data.split(":")[1])
            await self.delete_reminder(update, context, job_id_from_button=job_id, confirmed=False)
        
        elif data.startswith("delconfirm:"):
            job_id = int(data.split(":")[1])
            await self.delete_reminder(update, context, job_id_from_button=job_id, confirmed=True)
        
        elif data == "delcancel":
            # Cancelar eliminación y volver a mostrar la lista
            await self.list_reminders(update, context)
        
        elif data == "listar":
            await self.list_reminders(update, context)
        
        elif data == "menu_crear":
            # Mostrar instrucciones para crear recordatorio
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_html(
                "📝 <b>Crear un Recordatorio</b>\n\n"
                "Es muy fácil! Simplemente escribime qué querés recordar y cuándo.\n\n"
                "🌟 <b>Ejemplos:</b>\n"
                "• <i>Recordame pagar la luz mañana a las 10</i>\n"
                "• <i>Llamar al dentista el viernes a las 15:30</i>\n"
                "• <i>Comprar pan en 20 minutos</i>\n"
                "• <i>Reunión con el equipo el lunes 10 a las 9</i>\n\n"
                "💬 Escribí tu recordatorio ahora:",
                reply_markup=reply_markup
            )
        
        elif data == "menu_editar":
            # Mostrar instrucciones para editar
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_html(
                "✏️ <b>Editar un Recordatorio</b>\n\n"
                "Para editar un recordatorio:\n\n"
                "1️⃣ Usa el comando /listar o el botón 'Ver Mis Recordatorios'\n"
                "2️⃣ Presioná el botón ✏️ junto al recordatorio\n"
                "3️⃣ Escribí el nuevo texto y fecha\n\n"
                "⚠️ <b>Importante:</b> Solo podés editar recordatorios que aún no hayan vencido (en curso).",
                reply_markup=reply_markup
            )
        
        elif data == "menu_eliminar":
            # Mostrar opciones de eliminación
            keyboard = [
                [InlineKeyboardButton("🗑️ Eliminar uno específico", callback_data="help_borrar")],
                [InlineKeyboardButton("⚠️ Eliminar TODOS", callback_data="confirm_eliminar")],
                [InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_html(
                "🗑️ <b>Eliminar Recordatorios</b>\n\n"
                "¿Qué querés hacer?",
                reply_markup=reply_markup
            )
        
        elif data == "help_borrar":
            # Instrucciones para borrar un recordatorio específico
            keyboard = [[InlineKeyboardButton("« Volver", callback_data="menu_eliminar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_html(
                "🗑️ <b>Eliminar un Recordatorio</b>\n\n"
                "Para eliminar un recordatorio específico:\n\n"
                "1️⃣ Usa el comando /listar o el botón 'Ver Mis Recordatorios'\n"
                "2️⃣ Presioná el botón 🗑️ junto al recordatorio que querés borrar\n"
                "3️⃣ Confirmá la eliminación\n\n"
                "¡Es muy simple! Solo presioná el botón.",
                reply_markup=reply_markup
            )
        
        elif data == "confirm_eliminar":
            # Redirigir a delete_all_reminders
            await self.delete_all_reminders(update, context, confirmed=False)
        
        elif data == "menu_principal":
            # Mostrar el menú principal simplificado (sin editar/eliminar)
            keyboard = [
                [InlineKeyboardButton("📝 Crear Recordatorio", callback_data="menu_crear")],
                [InlineKeyboardButton("📋 Ver Mis Recordatorios", callback_data="listar")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="new_help")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🤖 <b>Menú Principal</b>\n\n"
                "<b>¿Qué querés hacer?</b>",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        
        elif data == "new_help":
            # Ayuda general mejorada
            keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_html(
                "❓ <b>Ayuda - Bot de Recordatorios</b>\n\n"
                "<b>📋 Comandos Disponibles:</b>\n"
                "• <code>/start</code> - Mostrar menú principal\n"
                "• <code>/menu</code> - Mostrar menú\n"
                "• <code>/listar</code> - Ver tus recordatorios\n"
                "• <code>/eliminar</code> - Eliminar todos\n"
                "• <code>/cancelar</code> - Cancelar edición\n\n"
                "<b>💡 Cómo Funciona:</b>\n"
                "Solo escribí en lenguaje natural qué querés recordar y cuándo.\n\n"
                "<b>🌟 Ejemplos de Recordatorios:</b>\n"
                "• <i>Pagar el alquiler el 5 a las 10</i>\n"
                "• <i>Comprar regalo para mamá mañana</i>\n"
                "• <i>Llamar al médico el viernes a las 3 pm</i>\n"
                "• <i>Recordame todos los lunes a las 9 revisar emails</i>\n\n"
                "<b>🔄 Recordatorios Recurrentes:</b>\n"
                "Podés crear recordatorios que se repiten:\n"
                "• <i>Todos los días...</i> (diario)\n"
                "• <i>Todos los lunes...</i> (semanal)\n"
                "• <i>Cada primer día del mes...</i> (mensual)\n"
                "• <i>Cada año el 15 de marzo...</i> (anual)\n\n"
                "<b>✏️ Editar y Borrar:</b>\n"
                "Desde <b>Ver Mis Recordatorios</b> podés:\n"
                "• Presionar ✏️ para editar un recordatorio\n"
                "• Presionar 🗑️ para eliminarlo (con confirmación)\n\n"
                "¡Es así de simple! 😊",
                reply_markup=reply_markup
            )
        
        elif data == "delall_confirm":
            await self.delete_all_reminders(update, context, confirmed=True)
        
        elif data == "delall_cancel":
            await query.edit_message_text("Operación cancelada. No se borró nada.")
