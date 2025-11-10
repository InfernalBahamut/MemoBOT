"""
Módulo de gestión de base de datos para el bot de recordatorios.
Maneja todas las operaciones CRUD y la conexión a MySQL.
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple
from contextlib import contextmanager
import mysql.connector
from mysql.connector import pooling, Error
from timezone_utils import to_argentina, to_utc, now_for_db

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestiona todas las operaciones de base de datos para recordatorios."""
    
    def __init__(self, db_config: dict, pool_size: int = 5):
        """
        Inicializa el gestor de base de datos.
        
        Args:
            db_config: Diccionario con configuración de BD (host, port, user, password, database)
            pool_size: Tamaño del pool de conexiones
        """
        self.db_config = db_config
        self.pool_size = pool_size
        self.db_pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Inicializa el pool de conexiones a MySQL."""
        try:
            self.db_pool = pooling.MySQLConnectionPool(
                pool_name="bot_pool",
                pool_size=self.pool_size,
                **self.db_config
            )
            logger.info("Pool de conexiones a MySQL creado exitosamente.")
        except Error as err:
            logger.critical(f"Error al conectar con MySQL: {err}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager para obtener conexiones del pool.
        
        Yields:
            tuple: (conexión, cursor)
        """
        conn = None
        cursor = None
        try:
            conn = self.db_pool.get_connection()
            cursor = conn.cursor()
            yield conn, cursor
            conn.commit()
        except Error as err:
            logger.error(f"Error en operación de base de datos: {err}")
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def create_reminder(self, chat_id: int, tarea: str, fecha_hora: datetime, 
                       recurrence_data: Optional[dict] = None, username: Optional[str] = None) -> int:
        """
        Crea un nuevo recordatorio en la base de datos.
        
        Args:
            chat_id: ID del chat de Telegram
            tarea: Descripción del recordatorio
            fecha_hora: Fecha y hora del recordatorio
            recurrence_data: Datos de recurrencia (opcional)
                - tipo: 'diario', 'semanal', 'mensual', 'anual'
                - intervalo: cada cuántos días/semanas/meses
                - dias_semana: lista de días para semanal
                - fecha_fin: fecha límite (opcional)
                - contexto_original: texto original del usuario
            username: Nombre de usuario de Telegram (opcional)
        
        Returns:
            int: ID del recordatorio creado
        """
        # Extraer contexto_original si existe
        contexto_original = None
        if recurrence_data:
            contexto_original = recurrence_data.get('contexto_original')
        
        with self.get_connection() as (conn, cursor):
            # Determinar si es recurrente (verificar ambos nombres de campo por compatibilidad)
            es_recurrente = recurrence_data.get('es_recurrente') if recurrence_data else False
            tipo_rec = recurrence_data.get('tipo_recurrencia') or recurrence_data.get('tipo') if recurrence_data else None
            
            if es_recurrente and tipo_rec:
                # Recordatorio recurrente
                intervalo = recurrence_data.get('intervalo_recurrencia') or recurrence_data.get('intervalo', 1)
                dias_semana_list = recurrence_data.get('dias_semana')
                dias_semana_str = ','.join(map(str, dias_semana_list)) if dias_semana_list else None
                
                fecha_fin_str = recurrence_data.get('fecha_fin_recurrencia') or recurrence_data.get('fecha_fin')
                fecha_fin = datetime.fromisoformat(fecha_fin_str) if fecha_fin_str else None
                
                query = """
                    INSERT INTO recordatorios 
                    (chat_id, tarea, contexto_original, fecha_hora, es_recurrente, tipo_recurrencia, 
                     intervalo_recurrencia, dias_semana, fecha_fin_recurrencia, username) 
                    VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    chat_id, tarea, contexto_original, fecha_hora, 
                    tipo_rec,
                    intervalo,
                    dias_semana_str,
                    fecha_fin,
                    username
                ))
            else:
                # Recordatorio simple
                query = "INSERT INTO recordatorios (chat_id, tarea, contexto_original, fecha_hora, username) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (chat_id, tarea, contexto_original, fecha_hora, username))
            
            nuevo_id = cursor.lastrowid
            logger.info(f"Recordatorio {nuevo_id} creado para chat {chat_id}")
            return nuevo_id
    
    def get_upcoming_reminders(self, chat_id: int) -> List[Tuple[int, str, datetime]]:
        """
        Obtiene los recordatorios futuros de un usuario (próximos 7 días).
        
        Args:
            chat_id: ID del chat de Telegram
        
        Returns:
            List[Tuple]: Lista de (id, tarea, fecha_hora_utc)
            NOTA: fecha_hora está en UTC, debe ser convertida a Argentina para mostrar
        """
        with self.get_connection() as (conn, cursor):
            query = """
                SELECT id, tarea, fecha_hora 
                FROM recordatorios 
                WHERE chat_id = %s AND notificado = 0 AND eliminado = 0
                ORDER BY fecha_hora ASC
            """
            cursor.execute(query, (chat_id,))
            return cursor.fetchall()
    
    def get_upcoming_reminders(self, chat_id: int) -> List[Tuple[int, str, datetime]]:
        """
        Obtiene los recordatorios de LA SEMANA ACTUAL (próximos 7 días) de un usuario.
        Incluye recordatorios únicos pendientes y recurrentes activos.
        Solo muestra las VERSIONES ACTUALES.
        
        Args:
            chat_id: ID del chat de Telegram
        
        Returns:
            List[Tuple]: Lista de (id, tarea, fecha_hora)
        """
        with self.get_connection() as (conn, cursor):
            query = """
                SELECT id, tarea, fecha_hora 
                FROM recordatorios 
                WHERE chat_id = %s 
                  AND eliminado = 0
                  AND es_version_actual = 1
                  AND (
                      -- Recordatorios únicos de esta semana (próximos 7 días)
                      (es_recurrente = 0 AND notificado = 0 
                       AND fecha_hora > NOW() 
                       AND fecha_hora <= DATE_ADD(NOW(), INTERVAL 7 DAY))
                      OR
                      -- Recordatorios recurrentes activos cuya próxima ejecución es en esta semana
                      (es_recurrente = 1 
                       AND fecha_hora <= DATE_ADD(NOW(), INTERVAL 7 DAY))
                  )
                ORDER BY fecha_hora ASC
            """
            cursor.execute(query, (chat_id,))
            return cursor.fetchall()
    
    def get_past_reminders(self, chat_id: int) -> List[Tuple[int, str, datetime]]:
        """
        Obtiene los recordatorios pasados (no notificados aún) de un usuario.
        
        Args:
            chat_id: ID del chat de Telegram
        
        Returns:
            List[Tuple]: Lista de (id, tarea, fecha_hora)
        """
        with self.get_connection() as (conn, cursor):
            query = """
                SELECT id, tarea, fecha_hora 
                FROM recordatorios 
                WHERE chat_id = %s AND notificado = 0 AND fecha_hora <= NOW() AND eliminado = 0
                ORDER BY fecha_hora DESC
            """
            cursor.execute(query, (chat_id,))
            return cursor.fetchall()
    
    def get_reminder_by_id(self, reminder_id: int, chat_id: int) -> Optional[Tuple[str, datetime, str]]:
        """
        Obtiene un recordatorio específico por ID.
        
        Args:
            reminder_id: ID del recordatorio
            chat_id: ID del chat (para seguridad)
        
        Returns:
            Tuple: (tarea, fecha_hora_utc, contexto_original) o None si no existe
            NOTA: fecha_hora está en UTC, debe ser convertida a Argentina para mostrar
        """
        with self.get_connection() as (conn, cursor):
            query = """
                SELECT tarea, fecha_hora, contexto_original 
                FROM recordatorios 
                WHERE id = %s AND chat_id = %s AND notificado = 0 AND eliminado = 0
            """
            cursor.execute(query, (reminder_id, chat_id))
            return cursor.fetchone()
    
    def update_reminder(self, reminder_id: int, chat_id: int, tarea: str, fecha_hora: datetime, contexto_original: str = None) -> bool:
        """
        Actualiza un recordatorio creando una NUEVA VERSIÓN.
        La versión anterior se marca como no actual.
        
        Args:
            reminder_id: ID del recordatorio a editar
            chat_id: ID del chat (para validación)
            tarea: Nueva descripción
            fecha_hora: Nueva fecha y hora
            contexto_original: Nuevo contexto original (opcional)
        
        Returns:
            bool: True si se actualizó, False si no se encontró
        """
        with self.get_connection() as (conn, cursor):
            # 1. Obtener la versión actual y datos del recordatorio original
            query_get = """
                SELECT version, recordatorio_original_id, es_recurrente, tipo_recurrencia, 
                       intervalo_recurrencia, dias_semana, fecha_fin_recurrencia
                FROM recordatorios 
                WHERE id = %s AND chat_id = %s AND eliminado = 0
            """
            cursor.execute(query_get, (reminder_id, chat_id))
            result = cursor.fetchone()
            
            if not result:
                return False
            
            version_actual, original_id, es_recurrente, tipo_rec, intervalo, dias_sem, fecha_fin = result
            
            # 2. Marcar la versión actual como no actual
            query_update = """
                UPDATE recordatorios 
                SET es_version_actual = 0
                WHERE id = %s
            """
            cursor.execute(query_update, (reminder_id,))
            
            # 3. Crear una nueva versión
            # Si no tiene recordatorio_original_id, el ID actual es el original
            id_original = original_id if original_id else reminder_id
            nueva_version = version_actual + 1
            
            query_insert = """
                INSERT INTO recordatorios (
                    chat_id, tarea, fecha_hora, contexto_original, notificado,
                    es_recurrente, tipo_recurrencia, intervalo_recurrencia, 
                    dias_semana, fecha_fin_recurrencia,
                    version, recordatorio_original_id, es_version_actual,
                    eliminado
                ) VALUES (
                    %s, %s, %s, %s, 0,
                    %s, %s, %s, %s, %s,
                    %s, %s, 1,
                    0
                )
            """
            cursor.execute(query_insert, (
                chat_id, tarea, fecha_hora, contexto_original,
                es_recurrente, tipo_rec, intervalo, dias_sem, fecha_fin,
                nueva_version, id_original
            ))
            
            logger.info(f"Recordatorio {reminder_id} actualizado a versión {nueva_version} (nuevo ID: {cursor.lastrowid})")
            return True
    
    def delete_reminder(self, reminder_id: int, chat_id: int, username: Optional[str] = None) -> bool:
        """
        Elimina lógicamente un recordatorio específico.
        
        Args:
            reminder_id: ID del recordatorio
            chat_id: ID del chat (para validación)
            username: Nombre de usuario que realiza la eliminación
        
        Returns:
            bool: True si se eliminó, False si no se encontró
        """
        with self.get_connection() as (conn, cursor):
            query = """
                UPDATE recordatorios 
                SET eliminado = 1, fecha_eliminacion = NOW()
                WHERE id = %s AND chat_id = %s AND eliminado = 0
            """
            cursor.execute(query, (reminder_id, chat_id))
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Recordatorio {reminder_id} eliminado lógicamente por {username or 'usuario desconocido'}")
            return deleted
    
    def delete_all_reminders(self, chat_id: int, username: Optional[str] = None) -> int:
        """
        Elimina lógicamente todos los recordatorios pendientes de un usuario.
        
        Args:
            chat_id: ID del chat
            username: Nombre de usuario que realiza la eliminación
        
        Returns:
            int: Número de recordatorios eliminados
        """
        with self.get_connection() as (conn, cursor):
            query = """
                UPDATE recordatorios 
                SET eliminado = 1, fecha_eliminacion = NOW() 
                WHERE chat_id = %s AND notificado = 0 AND eliminado = 0
            """
            cursor.execute(query, (chat_id,))
            count = cursor.rowcount
            logger.info(f"Usuario {username or chat_id} eliminó lógicamente {count} recordatorios")
            return count
    
    def get_due_reminders(self) -> List[Tuple[int, int, str, str]]:
        """
        Obtiene todos los recordatorios que deben ser notificados ahora.
        Incluye recordatorios únicos pendientes y recurrentes que deben enviarse.
        Solo procesa las VERSIONES ACTUALES.
        
        Returns:
            List[Tuple]: Lista de (id, chat_id, tarea, contexto_original)
        """
        with self.get_connection() as (conn, cursor):
            query = """
                SELECT id, chat_id, tarea, contexto_original 
                FROM recordatorios 
                WHERE eliminado = 0
                  AND es_version_actual = 1
                  AND (
                      -- Recordatorios únicos no notificados
                      (es_recurrente = 0 AND notificado = 0 AND fecha_hora <= NOW())
                      OR
                      -- Recordatorios recurrentes que deben enviarse
                      (es_recurrente = 1 AND fecha_hora <= NOW() AND 
                       (ultima_ejecucion IS NULL OR ultima_ejecucion < fecha_hora))
                  )
                ORDER BY fecha_hora
            """
            cursor.execute(query)
            return cursor.fetchall()
    
    def mark_as_notified(self, reminder_ids: List[int]) -> int:
        """
        Marca recordatorios como notificados.
        
        Args:
            reminder_ids: Lista de IDs a marcar
        
        Returns:
            int: Número de recordatorios marcados
        """
        if not reminder_ids:
            return 0
        
        with self.get_connection() as (conn, cursor):
            if len(reminder_ids) == 1:
                query = "UPDATE recordatorios SET notificado = 1 WHERE id = %s"
                cursor.execute(query, (reminder_ids[0],))
            else:
                placeholders = ','.join(['%s'] * len(reminder_ids))
                query = f"UPDATE recordatorios SET notificado = 1 WHERE id IN ({placeholders})"
                cursor.execute(query, tuple(reminder_ids))
            
            count = cursor.rowcount
            logger.info(f"Marcados {count} recordatorios como notificados")
            return count
    
    def get_recurrent_reminder(self, reminder_id: int) -> Optional[dict]:
        """
        Obtiene los datos de un recordatorio recurrente.
        
        Args:
            reminder_id: ID del recordatorio
        
        Returns:
            Optional[dict]: Datos del recordatorio recurrente o None
        """
        with self.get_connection() as (conn, cursor):
            query = """
                SELECT id, chat_id, tarea, fecha_hora, tipo_recurrencia, 
                       intervalo_recurrencia, dias_semana, fecha_fin_recurrencia
                FROM recordatorios 
                WHERE id = %s AND es_recurrente = 1 AND eliminado = 0
            """
            cursor.execute(query, (reminder_id,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'id': result[0],
                    'chat_id': result[1],
                    'tarea': result[2],
                    'fecha_hora': result[3],
                    'tipo': result[4],
                    'intervalo': result[5],
                    'dias_semana': result[6],
                    'fecha_fin': result[7]
                }
            return None
    
    def update_recurrent_reminder_next_date(self, reminder_id: int, recurrent_data: dict) -> bool:
        """
        Actualiza la fecha del recordatorio recurrente a su próxima ejecución.
        Actualiza el MISMO registro en lugar de crear uno nuevo.
        
        Args:
            reminder_id: ID del recordatorio recurrente
            recurrent_data: Datos del recordatorio recurrente
        
        Returns:
            bool: True si se actualizó, False si alcanzó la fecha límite
        """
        from datetime import timedelta
        import calendar
        
        fecha_actual = recurrent_data['fecha_hora']
        tipo = recurrent_data['tipo']
        intervalo = recurrent_data['intervalo']
        fecha_fin = recurrent_data['fecha_fin']
        
        # Calcular próxima fecha según el tipo de recurrencia
        if tipo == 'minutal':
            proxima_fecha = fecha_actual + timedelta(minutes=intervalo)
        elif tipo == 'horario':
            proxima_fecha = fecha_actual + timedelta(hours=intervalo)
        elif tipo == 'diario':
            proxima_fecha = fecha_actual + timedelta(days=intervalo)
        elif tipo == 'semanal':
            proxima_fecha = fecha_actual + timedelta(weeks=intervalo)
        elif tipo == 'mensual':
            # Agregar meses
            year = fecha_actual.year
            month = fecha_actual.month + intervalo
            while month > 12:
                month -= 12
                year += 1
            try:
                proxima_fecha = fecha_actual.replace(year=year, month=month)
            except ValueError:
                # Manejar caso de días que no existen en el mes destino (ej: 31 de febrero)
                last_day = calendar.monthrange(year, month)[1]
                proxima_fecha = fecha_actual.replace(year=year, month=month, day=last_day)
        elif tipo == 'anual':
            try:
                proxima_fecha = fecha_actual.replace(year=fecha_actual.year + intervalo)
            except ValueError:
                # Caso especial: 29 de febrero en año no bisiesto
                proxima_fecha = fecha_actual.replace(year=fecha_actual.year + intervalo, day=28)
        else:
            logger.error(f"Tipo de recurrencia desconocido: {tipo}")
            return False
        
        # Verificar si ya pasó la fecha fin
        if fecha_fin and proxima_fecha > fecha_fin:
            logger.info(f"Recordatorio recurrente {reminder_id} alcanzó su fecha fin")
            # Marcar como notificado para que no se envíe más
            with self.get_connection() as (conn, cursor):
                query = "UPDATE recordatorios SET notificado = 1, ultima_ejecucion = NOW() WHERE id = %s"
                cursor.execute(query, (reminder_id,))
            return False
        
        # Actualizar la fecha del MISMO registro
        with self.get_connection() as (conn, cursor):
            query = """
                UPDATE recordatorios 
                SET fecha_hora = %s, 
                    notificado = 0,
                    ultima_ejecucion = NOW(),
                    fecha_modificacion = NOW()
                WHERE id = %s
            """
            cursor.execute(query, (proxima_fecha, reminder_id))
            logger.info(f"Recordatorio recurrente {reminder_id} actualizado a {proxima_fecha}")
            return True

    # ==================== MÉTODOS DE VALIDACIÓN ANTI-FLOOD ====================
    
    def count_active_reminders(self, chat_id: int) -> int:
        """
        Cuenta la cantidad de recordatorios activos (no eliminados, versión actual) de un chat.
        
        Args:
            chat_id: ID del chat de Telegram
        
        Returns:
            int: Cantidad de recordatorios activos
        """
        with self.get_connection() as (conn, cursor):
            query = """
                SELECT COUNT(*) 
                FROM recordatorios 
                WHERE chat_id = %s 
                  AND eliminado = 0 
                  AND es_version_actual = 1
            """
            cursor.execute(query, (chat_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
    
    def count_recent_creations(self, chat_id: int, minutes: int = 1) -> int:
        """
        Cuenta cuántos recordatorios creó un chat en los últimos N minutos.
        
        Args:
            chat_id: ID del chat de Telegram
            minutes: Ventana de tiempo en minutos (default: 1)
        
        Returns:
            int: Cantidad de recordatorios creados recientemente
        """
        with self.get_connection() as (conn, cursor):
            query = """
                SELECT COUNT(*) 
                FROM recordatorios 
                WHERE chat_id = %s 
                  AND fecha_creacion >= DATE_SUB(NOW(), INTERVAL %s MINUTE)
            """
            cursor.execute(query, (chat_id, minutes))
            result = cursor.fetchone()
            return result[0] if result else 0
    
    def validate_recurrence_interval(self, tipo_recurrencia: str, intervalo: int) -> tuple:
        """
        Valida que el intervalo de recurrencia sea razonable.
        
        Args:
            tipo_recurrencia: 'minutal', 'horario', 'diario', 'semanal', 'mensual', 'anual'
            intervalo: Número de unidades de tiempo
        
        Returns:
            tuple: (es_valido: bool, mensaje_error: str)
        """
        # Intervalos mínimos razonables para evitar spam
        limites_minimos = {
            'minutal': 1,     # Mínimo cada 1 minuto
            'horario': 1,     # Mínimo cada 1 hora
            'diario': 1,      # Mínimo cada 1 día
            'semanal': 1,     # Mínimo cada 1 semana
            'mensual': 1,     # Mínimo cada 1 mes
            'anual': 1        # Mínimo cada 1 año
        }
        
        # Intervalos máximos razonables
        limites_maximos = {
            'minutal': 1440,  # Máximo cada 24 horas (1440 minutos)
            'horario': 168,   # Máximo cada semana (168 horas)
            'diario': 365,    # Máximo cada 365 días
            'semanal': 52,    # Máximo cada 52 semanas
            'mensual': 24,    # Máximo cada 24 meses
            'anual': 10       # Máximo cada 10 años
        }
        
        if tipo_recurrencia not in limites_minimos:
            return False, f"Tipo de recurrencia inválido: {tipo_recurrencia}"
        
        min_intervalo = limites_minimos[tipo_recurrencia]
        max_intervalo = limites_maximos[tipo_recurrencia]
        
        if intervalo < min_intervalo:
            return False, f"Intervalo demasiado corto. Mínimo: {min_intervalo} {tipo_recurrencia}"
        
        if intervalo > max_intervalo:
            return False, f"Intervalo demasiado largo. Máximo: {max_intervalo} {tipo_recurrencia}"
        
        return True, ""
