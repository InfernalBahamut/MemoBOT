"""
Módulo de servicio de IA para el bot de recordatorios.
Maneja la integración con Google Gemini para parseo de lenguaje natural.
"""

import json
import logging
import os
from datetime import datetime
from typing import Tuple, Optional
from dotenv import load_dotenv
import google.generativeai as genai
from timezone_utils import now_for_user, format_datetime_argentina

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)


class GeminiService:
    """Servicio para interactuar con la API de Gemini."""
    
    def __init__(self, api_key: str, model_name: str = None):
        """
        Inicializa el servicio de Gemini.
        
        Args:
            api_key: API key de Google Gemini
            model_name: Nombre del modelo a utilizar (si es None, se toma del .env)
        """
        self.api_key = api_key
        # Si no se proporciona model_name, leer del .env
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        self.model = None
        self._configure()
    
    def _configure(self):
        """Configura la API de Gemini."""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"API de Gemini configurada exitosamente con modelo {self.model_name}")
        except Exception as e:
            logger.critical(f"Error al configurar la API de Gemini: {e}")
            raise
    
    def _build_prompt(self, texto_usuario: str) -> str:
        """
        Construye el prompt para Gemini.
        
        Args:
            texto_usuario: Texto del usuario a parsear
        
        Returns:
            str: Prompt formateado
        """
        ahora = format_datetime_argentina(now_for_user())
        # NOTE: solicitamos explícitamente los nombres de campo que la base de datos
        # espera. Excluimos campos gestionados por el sistema (chat_id, notificado,
        # username, id, version, recordatorio_original_id, es_version_actual,
        # eliminado, fecha_eliminacion, usuario_eliminacion, fecha_creacion,
        # fecha_modificacion). Gemini debe devolver SOLO los campos que se muestran
        # abajo y con los nombres indicados.

        return f"""
Sos un asistente para agendar recordatorios.
La fecha y hora actual es: {ahora}
Texto del usuario: "{texto_usuario}"

RESPONDE UN JSON con LOS SIGUIENTES CAMPOS (exactamente con estos nombres):

- tarea: Texto completo y detallado del recordatorio (string)
- fecha_hora: Fecha y hora en formato 'YYYY-MM-DD HH:MM:SS' (string) — primera ocurrencia
- contexto_original: Texto original completo del usuario (string)
- es_recurrente: true o false (boolean)
- tipo_recurrencia: uno de 'diario', 'semanal', 'mensual', 'anual' (string) O null
- intervalo_recurrencia: entero (ej: cada 2 semanas -> 2). Si no aplica, 1 o null
- dias_semana: lista de enteros [0-6] para semanal (0=domingo). Si no aplica, null
- fecha_fin_recurrencia: Fecha límite 'YYYY-MM-DD HH:MM:SS' o null

Campos QUE NO DEBES RELLENAR (los gestiona el sistema): chat_id, notificado, username, id,
version, recordatorio_original_id, es_version_actual, eliminado, fecha_eliminacion,
usuario_eliminacion, fecha_creacion, fecha_modificacion, ultima_ejecucion

IMPORTANTE:
- Si detectás un recordatorio recurrente (ej. "cada 4 horas", "todos los lunes"),
  devolvé es_recurrente=true y completá los campos de recurrencia.
- Si no hay hora específica, poné la hora por defecto '00:00:00' en fecha_hora
  y dejá claro en el contexto_original que la hora no fue especificada.
- Si no podés entender, devolvé: {"error": "no entendí, podés ser más específico?"}

Ejemplos de respuesta JSON:
{"tarea": "tomar agua", "fecha_hora": "2025-11-06 08:00:00", "contexto_original": "Debo tomar agua cada 4 horas toda esta semana", "es_recurrente": true, "tipo_recurrencia": "diario", "intervalo_recurrencia": 4, "dias_semana": null, "fecha_fin_recurrencia": "2025-11-12 23:59:59"}

Responde ÚNICAMENTE con el objeto JSON solicitado.
"""
    
    async def parse_reminder(self, texto_usuario: str) -> Tuple[Optional[str], Optional[datetime], Optional[str], Optional[dict]]:
        """
        Parsea el texto del usuario para extraer tarea, fecha y recurrencia.
        
        Args:
            texto_usuario: Texto del usuario
        
        Returns:
            Tuple: (tarea, fecha_hora, error_msg, recurrence_data)
                - Si es exitoso: (tarea, fecha_hora, None, recurrence_data)
                - Si falla: (None, None, error_msg, None)
                - recurrence_data es un dict con información de recurrencia o None (incluye contexto_original)
        """
        prompt = self._build_prompt(texto_usuario)
        logger.info("Enviando prompt a Gemini...")
        
        try:
            response = await self.model.generate_content_async(prompt)
            respuesta_gemini_str = response.text
            logger.info(f"Respuesta de Gemini: {respuesta_gemini_str}")
            
            # Extraer JSON de la respuesta
            json_data = self._extract_json(respuesta_gemini_str)
            
            if not json_data:
                return None, None, "No se pudo parsear la respuesta de la IA.", None
            
            # Verificar si hay error
            if "error" in json_data:
                return None, None, f"No pude entender tu recordatorio. (Error: {json_data['error']})", None
            
            # Extraer y validar campos devueltos por Gemini (usando los nombres de DB)
            # Campos esperados: tarea, fecha_hora, contexto_original, es_recurrente,
            # tipo_recurrencia, intervalo_recurrencia, dias_semana, fecha_fin_recurrencia
            tarea = json_data.get('tarea')
            fecha_hora_str = json_data.get('fecha_hora')
            contexto_original = json_data.get('contexto_original', texto_usuario)

            if not tarea or not fecha_hora_str:
                return None, None, "Falta información en la respuesta de la IA.", None

            # Convertir fecha string a datetime
            try:
                fecha_hora_obj = datetime.fromisoformat(fecha_hora_str)
            except ValueError:
                # Intentar con espacio en lugar de T o complementar segundos
                try:
                    fecha_hora_obj = datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.error(f"Error al convertir fecha: {e}")
                    return None, None, "Error al interpretar la fecha.", None

            # Validar que la fecha no haya pasado (solo para no recurrentes)
            es_recurrente = bool(json_data.get('es_recurrente', False))
            if not es_recurrente and fecha_hora_obj <= now_for_user():
                return None, None, "La fecha y hora que entendí ya pasó. Por favor, intentá de nuevo.", None

            # Construir recurrence_data con los nombres que usa la base de datos
            recurrence_data = {
                'contexto_original': contexto_original,
                'es_recurrente': es_recurrente,
                'tipo_recurrencia': json_data.get('tipo_recurrencia') or None,
                'intervalo_recurrencia': json_data.get('intervalo_recurrencia') or json_data.get('intervalo') or None,
                'dias_semana': json_data.get('dias_semana') or None,
                'fecha_fin_recurrencia': json_data.get('fecha_fin_recurrencia') or json_data.get('fecha_fin') or None
            }

            return tarea, fecha_hora_obj, None, recurrence_data
        
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear JSON de Gemini: {e}")
            return None, None, "Error procesando la respuesta de la IA.", None
        except ValueError as e:
            logger.error(f"Error al convertir fecha: {e}")
            return None, None, "Error al interpretar la fecha.", None
        except Exception as e:
            logger.error(f"Error inesperado en parse_reminder: {e}")
            return None, None, f"Hubo un error inesperado: {e}", None
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Extrae JSON de un texto que puede contener otros elementos.
        
        Args:
            text: Texto que contiene JSON
        
        Returns:
            dict o None: JSON parseado o None si falla
        """
        json_start = text.find('{')
        json_end = text.rfind('}')
        
        if json_start == -1 or json_end == -1:
            logger.error(f"No se encontró JSON válido en: {text}")
            return None
        
        json_str = text[json_start:json_end + 1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON: {e}")
            return None
    
    async def generate_funny_reminder_message(self, tarea: str, contexto_original: str = None) -> str:
        """
        Genera un mensaje simpático y picarón para un recordatorio usando Gemini.
        
        Args:
            tarea: La tarea del recordatorio
            contexto_original: El texto original del usuario (para mejor contexto)
        
        Returns:
            str: Mensaje con humor generado por Gemini
        """
        prompt = f"""
Sos un asistente virtual simpático y picarón. Tu trabajo es generar un mensaje MUY BREVE (máximo 20 palabras) 
con humor para acompañar un recordatorio.

Recordatorio: "{tarea}"
{f'Contexto original del usuario: "{contexto_original}"' if contexto_original else ''}

IMPORTANTE:
- El mensaje DEBE estar ESTRICTAMENTE relacionado con el contenido del recordatorio
- Debe ser simpático, divertido, y un poco picarón (pero sin pasarse)
- Debe motivar, hacer reír o reflexionar
- Usa emojis relacionados al tema
- Máximo 20 palabras
- NO uses comillas en la respuesta

Ejemplos de buen estilo:
- Para "pagar la luz": "💸 Tu billetera llora, pero tus electrodomésticos te lo van a agradecer 😅"
- Para "ir al gym": "💪 Hoy no hay excusas! El sofá puede esperar (aunque te llame) 🛋️"
- Para "estudiar para examen": "📚 Acordate: no estudiaste todo el año, pero AHORA sí o sí! Dale campeón 💪"
- Para "comprar regalo cumpleaños": "🎁 Amazon Prime es tu mejor amigo. La procrastinación, tu peor enemigo 😂"

Responde SOLO con el mensaje, sin formato extra ni explicaciones.
"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            mensaje = response.text.strip()
            # Limpiar comillas si las tiene
            mensaje = mensaje.strip('"').strip("'")
            logger.info(f"Mensaje con humor generado: {mensaje}")
            return mensaje
        except Exception as e:
            logger.error(f"Error generando mensaje con humor: {e}")
            # Fallback a mensaje genérico
            return "⏰ ¡Es hora! Dale que vos podés 💪"
    
    async def parse_multiple_reminders(self, texto_usuario: str) -> Tuple[Optional[list], Optional[str]]:
        """
        Parsea el texto del usuario para detectar múltiples recordatorios o recurrencia.
        
        Args:
            texto_usuario: Texto del usuario
        
        Returns:
            Tuple: (lista_de_recordatorios, error_msg)
        """
        ahora = format_datetime_argentina(now_for_user())
        
        prompt = f"""
Fecha/hora actual: {ahora}
Texto: "{texto_usuario}"

Parseá a JSON. Detectá:
- RECURRENTE: "cada X minutos/horas/días", "todos los lunes", etc.
- MÚLTIPLES: varios eventos con fechas distintas

RECURRENTE → UN objeto:
{{
  "es_recurrente": true,
  "tipo_recurrencia": "minutal|horario|diario|semanal|mensual|anual",
  "intervalo": N,
  "tarea": "...",
  "fecha": "YYYY-MM-DD",
  "hora": "HH:MM:SS",
  "hora_especificada": true|false,
  "contexto": "...",
  "fecha_fin": "YYYY-MM-DD HH:MM:SS" o null
}}

MÚLTIPLES → array:
{{
  "recordatorios": [
    {{"tarea": "...", "fecha": "YYYY-MM-DD", "hora": "HH:MM:SS", "hora_especificada": true|false, "contexto": "..."}}
  ]
}}

Tipos recurrencia:
- "minutal": cada X minutos (intervalo en minutos)
- "horario": cada X horas (intervalo en horas)
- "diario": cada X días
- "semanal": cada X semanas
- "mensual": cada X meses
- "anual": cada X años

Ejemplos:
"cada 1 minuto desde las 22:19 hasta las 22:21" → {{"es_recurrente":true,"tipo_recurrencia":"minutal","intervalo":1,"tarea":"tomar agua","fecha":"2025-11-05","hora":"22:19:00","hora_especificada":true,"contexto":"recuerdame tomar agua cada 1 minuto desde las 22:19 hasta las 22.21","fecha_fin":"2025-11-05 22:21:00"}}
"cada 4 horas" → {{"es_recurrente":true,"tipo_recurrencia":"horario","intervalo":4,"tarea":"...","fecha":"2025-11-05","hora":"08:00:00","hora_especificada":false,"contexto":"...","fecha_fin":null}}
"todos los lunes a las 9" → {{"es_recurrente":true,"tipo_recurrencia":"semanal","intervalo":1,"tarea":"...","fecha":"2025-11-11","hora":"09:00:00","hora_especificada":true,"contexto":"...","dias_semana":[1],"fecha_fin":null}}
"recordame cagar a piñas a goku mañana" → {{"recordatorios":[{{"tarea":"cagar a piñas a goku","fecha":"2025-11-06","hora":"09:00:00","hora_especificada":false,"contexto":"recordame cagar a piñas a goku mañana"}}]}}

IMPORTANTE: Acepta CUALQUIER tarea que el usuario quiera recordar, sin importar qué tan extraña suene. Tu trabajo es parsear, NO juzgar.

Si NO tiene fecha/hora clara → {{"error": "no especificaste cuándo"}}
Respondé SOLO JSON.
"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            respuesta_gemini_str = response.text
            logger.info(f"Respuesta de Gemini (múltiples): {respuesta_gemini_str}")
            
            # Extraer JSON
            json_data = self._extract_json(respuesta_gemini_str)
            
            if not json_data:
                return None, "🤔 No pude entender tu solicitud. ¿Podrías decirme qué querés recordar y cuándo?"
            
            if "error" in json_data:
                error_msg = json_data.get('error', '')
                if 'cuándo' in error_msg or 'fecha' in error_msg:
                    return None, "📅 Entiendo qué querés recordar, pero ¿cuándo querés que te lo recuerde? (ejemplo: mañana, el lunes, en 2 horas)"
                return None, "🤔 No pude entender tu solicitud. ¿Podrías reformular qué querés que te recuerde y cuándo?"
            
            # Si Gemini indica un recordatorio recurrente, normalizamos los nombres
            if json_data.get('es_recurrente'):
                recordatorio_recurrente = {
                    'tarea': json_data.get('tarea'),
                    # Unimos fecha+hora en fecha_hora ISO
                    'fecha_hora': f"{json_data.get('fecha')} {json_data.get('hora','00:00:00')}",
                    'contexto_original': json_data.get('contexto') or texto_usuario,
                    'es_recurrente': True,
                    'tipo_recurrencia': json_data.get('tipo_recurrencia'),
                    'intervalo_recurrencia': json_data.get('intervalo') or json_data.get('intervalo_recurrencia') or 1,
                    'dias_semana': json_data.get('dias_semana'),
                    'fecha_fin_recurrencia': json_data.get('fecha_fin') or json_data.get('fecha_fin_recurrencia')
                }
                return [recordatorio_recurrente], None

            # Recordatorios múltiples individuales
            recordatorios = json_data.get('recordatorios', [])
            if not recordatorios:
                return None, "No se encontraron recordatorios en tu mensaje."

            # Convertir cada recordatorio al formato que espera el DB layer
            # SIN límite de cantidad (se eliminó el [:3])
            salida = []
            for r in recordatorios:
                fecha = r.get('fecha')
                hora = r.get('hora', '00:00:00')
                fecha_hora = f"{fecha} {hora}"
                salida.append({
                    'tarea': r.get('tarea'),
                    'fecha_hora': fecha_hora,
                    'contexto_original': r.get('contexto') or texto_usuario,
                    'es_recurrente': False,
                    'tipo_recurrencia': None,
                    'intervalo_recurrencia': None,
                    'dias_semana': None,
                    'fecha_fin_recurrencia': None
                })

            return salida, None
        
        except Exception as e:
            logger.error(f"Error en parse_multiple_reminders: {e}")
            return None, f"Hubo un error procesando tu solicitud: {e}"
    
    async def parse_reminder_edit(self, texto_usuario: str, tarea_original: str, fecha_original: datetime, contexto_original: str = None) -> Tuple[Optional[str], Optional[datetime], Optional[str], Optional[dict]]:
        """
        Parsea una edición de recordatorio considerando el contexto original.
        
        Args:
            texto_usuario: Lo que el usuario escribió para editar
            tarea_original: La tarea original del recordatorio
            fecha_original: La fecha/hora original del recordatorio
            contexto_original: El texto original completo (si existe)
        
        Returns:
            Tuple: (tarea, fecha_hora, error_msg, recurrence_data)
        """
        ahora = format_datetime_argentina(now_for_user())
        fecha_original_str = format_datetime_argentina(fecha_original)
        
        prompt = f"""
Sos un asistente para editar recordatorios. El usuario quiere modificar un recordatorio existente.

FECHA Y HORA ACTUAL: {ahora}

RECORDATORIO ORIGINAL:
- Tarea: "{tarea_original}"
- Fecha/hora: {fecha_original_str}
{f'- Contexto original: "{contexto_original}"' if contexto_original else ''}

TEXTO DE EDICIÓN DEL USUARIO: "{texto_usuario}"

Tu tarea es interpretar qué quiere cambiar el usuario. El usuario puede:
1. Cambiar solo la fecha/hora (ej: "cambiá la fecha al martes")
2. Cambiar solo la tarea (ej: "en lugar de repasar, estudiar")
3. Hacer una corrección contextual (ej: "el examen era el martes no el lunes")
4. Reescribir todo completamente

IMPORTANTE:
- Si el usuario hace una corrección contextual (ej: "era el martes no el lunes"), interpretá el contexto original y aplicá el cambio
- Si solo menciona un cambio parcial, mantené el resto del recordatorio original
- Si reescribe todo, usá el texto nuevo completo

Extraé la información del recordatorio EDITADO:

1. "tarea": El texto COMPLETO Y ACTUALIZADO del recordatorio con TODOS los cambios aplicados
2. "fecha_hora": La fecha y hora ACTUALIZADAS en formato 'YYYY-MM-DD HH:MM:SS'
3. "contexto_original": El nuevo texto completo que escribió el usuario (o el contexto actualizado)

Si es recurrente:
4. "es_recurrente": true o false
5. "tipo_recurrencia": "diario", "semanal", "mensual", o "anual"
6. "intervalo": número
7. "dias_semana": lista [0-6]
8. "fecha_fin": opcional

Ejemplos:

Ejemplo 1:
Original: "repasar para el examen del lunes" - 2025-11-09 18:00:00
Usuario: "el examen era el martes no el lunes"
Respuesta: {{"tarea": "repasar para el examen del martes", "fecha_hora": "2025-11-09 18:00:00", "contexto_original": "el examen era el martes no el lunes", "es_recurrente": false}}

Ejemplo 2:
Original: "comprar leche" - 2025-11-06 10:00:00
Usuario: "mejor mañana a las 15"
Respuesta: {{"tarea": "comprar leche", "fecha_hora": "2025-11-06 15:00:00", "contexto_original": "mejor mañana a las 15", "es_recurrente": false}}

Ejemplo 3:
Original: "llamar al dentista" - 2025-11-07 10:00:00
Usuario: "llamar al médico el viernes a las 16"
Respuesta: {{"tarea": "llamar al médico", "fecha_hora": "2025-11-08 16:00:00", "contexto_original": "llamar al médico el viernes a las 16", "es_recurrente": false}}

Responde ÚNICAMENTE con un objeto JSON.
Si no podés entender, respondé: {{"error": "no entendí la modificación, podés ser más específico?"}}
"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            respuesta_gemini_str = response.text
            logger.info(f"Respuesta de Gemini (edición): {respuesta_gemini_str}")
            
            # Extraer JSON
            json_data = self._extract_json(respuesta_gemini_str)
            
            if not json_data:
                return None, None, "No se pudo parsear la respuesta de la IA.", None
            
            if "error" in json_data:
                return None, None, f"No pude entender tu edición. {json_data['error']}", None
            
            # Extraer campos con los nombres de DB
            tarea = json_data.get('tarea')
            fecha_hora_str = json_data.get('fecha_hora')
            contexto_nuevo = json_data.get('contexto_original', texto_usuario)

            if not tarea or not fecha_hora_str:
                return None, None, "Falta información en la respuesta de la IA.", None

            try:
                fecha_hora_obj = datetime.fromisoformat(fecha_hora_str)
            except Exception:
                try:
                    fecha_hora_obj = datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.error(f"Error al convertir fecha (edición): {e}")
                    return None, None, "Error al interpretar la fecha.", None

            es_recurrente = bool(json_data.get('es_recurrente', False))
            if not es_recurrente and fecha_hora_obj <= now_for_user():
                return None, None, "La fecha debe ser en el futuro. Intentá con una fecha posterior.", None

            recurrence_data = {
                'contexto_original': contexto_nuevo,
                'es_recurrente': es_recurrente,
                'tipo_recurrencia': json_data.get('tipo_recurrencia') or None,
                'intervalo_recurrencia': json_data.get('intervalo_recurrencia') or json_data.get('intervalo') or None,
                'dias_semana': json_data.get('dias_semana') or None,
                'fecha_fin_recurrencia': json_data.get('fecha_fin_recurrencia') or json_data.get('fecha_fin') or None
            }

            return tarea, fecha_hora_obj, None, recurrence_data
        
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear JSON de Gemini (edición): {e}")
            return None, None, "Error procesando la respuesta de la IA.", None
        except ValueError as e:
            logger.error(f"Error al convertir fecha (edición): {e}")
            return None, None, "Error al interpretar la fecha.", None
        except Exception as e:
            logger.error(f"Error inesperado en parse_reminder_edit: {e}")
            return None, None, f"Hubo un error inesperado: {e}", None

    async def classify_and_respond(self, texto_usuario: str) -> Tuple[str, bool]:
        """
        Clasifica el mensaje del usuario y genera una respuesta apropiada.
        
        Args:
            texto_usuario: Texto del usuario
        
        Returns:
            Tuple[str, bool]: (respuesta, es_recordatorio)
                - respuesta: Mensaje de respuesta para el usuario
                - es_recordatorio: True si es intención de crear recordatorio, False si es fuera de tema
        """
        prompt = f"""
Sos un bot de recordatorios amigable y con sentido del humor. Tu ÚNICO propósito es ayudar a crear, editar y gestionar recordatorios.

Texto del usuario: "{texto_usuario}"

Clasificá este mensaje en una de estas categorías:

1. RECORDATORIO: El usuario quiere crear, modificar o consultar un recordatorio (incluso si suena extraño o gracioso)
   Ejemplos: "recuerdame comprar pan", "tengo que estudiar mañana", "agenda reunión el lunes", "recordatorio para las 3pm"
   También incluye: "recordame cagar a piñas a goku", "avisame cuando sea hora de ser batman", "recuerdame dominar el mundo"

2. SALUDO/CORTESIA: Saludo, despedida o cortesía relacionada con recordatorios
   Ejemplos: "hola", "gracias", "chau", "buenas", "cómo estás", "qué tal"

3. FUERA_DE_TEMA: Pregunta o solicitud NO relacionada con recordatorios (cosas que NO son tareas para recordar)
   Ejemplos: "cuánto es 2+2", "dame una receta", "contame un chiste", "qué hora es", "cómo está el clima"

IMPORTANTE: Si el usuario dice "recuerdame X" o "recordatorio de X", SIEMPRE es RECORDATORIO, sin importar qué sea X.

Responde SOLO con un JSON:
{{
  "categoria": "RECORDATORIO" | "SALUDO" | "FUERA_DE_TEMA",
  "respuesta": "mensaje apropiado para el usuario (si no es RECORDATORIO)"
}}

Si es RECORDATORIO, deja "respuesta" vacío ("").
Si es SALUDO, responde de forma amigable pero breve, mencionando que estás listo para ayudar con recordatorios.
Si es FUERA_DE_TEMA, responde con humor que solo podés ayudar con recordatorios, y sugerí crear uno.

Responde SOLO el JSON, sin texto adicional.
"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            json_data = self._extract_json(response.text)
            
            if not json_data:
                # Fallback: asumir que es intención de recordatorio
                return "", True
            
            categoria = json_data.get('categoria', 'RECORDATORIO')
            respuesta_bot = json_data.get('respuesta', '')
            
            if categoria == 'RECORDATORIO':
                return "", True
            elif categoria == 'SALUDO':
                if not respuesta_bot:
                    respuesta_bot = "¡Hola! 👋 Soy tu asistente de recordatorios. Escribime qué querés recordar y yo me encargo 😊"
                return respuesta_bot, False
            else:  # FUERA_DE_TEMA
                if not respuesta_bot:
                    respuesta_bot = "🤖 Disculpá, pero solo puedo ayudarte con recordatorios. ¿Querés que agende algo para vos?"
                return respuesta_bot, False
        
        except Exception as e:
            logger.error(f"Error en classify_and_respond: {e}")
            # En caso de error, asumir que es recordatorio para no bloquear funcionalidad
            return "", True

    async def ask_for_time(self, tarea: str, fecha: str) -> str:
        """
        Genera un mensaje natural preguntando por la hora de un recordatorio.
        
        Args:
            tarea: La tarea del recordatorio
            fecha: La fecha del recordatorio
        
        Returns:
            str: Mensaje preguntando la hora
        """
        prompt = f"""
Sos un asistente amigable. El usuario quiere crear este recordatorio:

Tarea: "{tarea}"
Fecha: {fecha}

Generá un mensaje BREVE (máximo 15 palabras) preguntando a qué hora quiere que se le recuerde.
Debe ser natural, amigable y directo.

Ejemplos de buen estilo:
- "¿A qué hora querés que te recuerde?"
- "Dale, ¿a qué hora te lo recuerdo?"
- "Perfecto! ¿Qué hora te viene bien?"
- "¿A qué hora necesitás el recordatorio?"

Responde SOLO con el mensaje, sin formato extra.
"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            mensaje = response.text.strip().strip('"').strip("'")
            return mensaje
        except Exception as e:
            logger.error(f"Error generando pregunta de hora: {e}")
            return "¿A qué hora querés que te recuerde?"


