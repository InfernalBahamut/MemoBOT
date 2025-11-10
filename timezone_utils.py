"""
Módulo de utilidades para manejar zonas horarias.
El servidor opera en UTC, pero el bot está configurado para Argentina (UTC-3).
"""

from datetime import datetime, timedelta
from typing import Optional
import pytz

# Zona horaria de Argentina
ARGENTINA_TZ = pytz.timezone('America/Argentina/Buenos_Aires')
UTC_TZ = pytz.UTC


def get_now_argentina() -> datetime:
    """
    Obtiene la fecha/hora actual en zona horaria de Argentina.
    
    Returns:
        datetime: Fecha/hora actual en Argentina (aware)
    """
    return datetime.now(ARGENTINA_TZ)


def get_now_utc() -> datetime:
    """
    Obtiene la fecha/hora actual en UTC.
    
    Returns:
        datetime: Fecha/hora actual en UTC (aware)
    """
    return datetime.now(UTC_TZ)


def to_utc(dt_argentina: datetime) -> datetime:
    """
    Convierte un datetime de Argentina a UTC para almacenar en la base de datos.
    
    Args:
        dt_argentina: DateTime en zona horaria de Argentina (puede ser naive o aware)
    
    Returns:
        datetime: DateTime en UTC (naive, para MySQL)
    """
    # Si el datetime es naive, asumir que está en hora de Argentina
    if dt_argentina.tzinfo is None:
        dt_aware = ARGENTINA_TZ.localize(dt_argentina)
    else:
        dt_aware = dt_argentina
    
    # Convertir a UTC
    dt_utc = dt_aware.astimezone(UTC_TZ)
    
    # Retornar sin timezone info (naive) para MySQL
    return dt_utc.replace(tzinfo=None)


def to_argentina(dt_utc: datetime) -> datetime:
    """
    Convierte un datetime de UTC (de la base de datos) a hora de Argentina.
    
    Args:
        dt_utc: DateTime en UTC (naive, desde MySQL)
    
    Returns:
        datetime: DateTime en Argentina (naive)
    """
    # Asumir que el datetime de la BD está en UTC
    if dt_utc.tzinfo is None:
        dt_aware = UTC_TZ.localize(dt_utc)
    else:
        dt_aware = dt_utc
    
    # Convertir a Argentina
    dt_argentina = dt_aware.astimezone(ARGENTINA_TZ)
    
    # Retornar sin timezone info (naive) para facilitar comparaciones
    return dt_argentina.replace(tzinfo=None)


def format_datetime_argentina(dt: datetime) -> str:
    """
    Formatea un datetime para mostrar al usuario en hora de Argentina.
    
    Args:
        dt: DateTime (puede estar en UTC o Argentina)
    
    Returns:
        str: String formateado en formato ISO
    """
    if dt.tzinfo is None:
        # Asumir que viene de la BD (UTC) y convertir a Argentina
        dt_argentina = to_argentina(dt)
    else:
        dt_argentina = dt.astimezone(ARGENTINA_TZ)
    
    return dt_argentina.strftime('%Y-%m-%d %H:%M:%S')


def parse_user_datetime(fecha_str: str, hora_str: str) -> datetime:
    """
    Parsea fecha y hora ingresadas por el usuario (en hora de Argentina)
    y las convierte a UTC para almacenar.
    
    Args:
        fecha_str: Fecha en formato 'YYYY-MM-DD'
        hora_str: Hora en formato 'HH:MM:SS'
    
    Returns:
        datetime: DateTime en UTC (naive) listo para la BD
    """
    # Combinar fecha y hora
    fecha_hora_str = f"{fecha_str} {hora_str}"
    dt_argentina = datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S')
    
    # Convertir a UTC
    return to_utc(dt_argentina)


def now_for_db() -> datetime:
    """
    Obtiene el datetime actual en UTC para almacenar en la base de datos.
    Equivalente a NOW() de MySQL pero calculado en Python.
    
    Returns:
        datetime: Fecha/hora actual en UTC (naive)
    """
    return datetime.now(UTC_TZ).replace(tzinfo=None)


def now_for_user() -> datetime:
    """
    Obtiene el datetime actual en Argentina para mostrar al usuario o comparar
    con fechas ingresadas por el usuario.
    
    Returns:
        datetime: Fecha/hora actual en Argentina (naive)
    """
    return datetime.now(ARGENTINA_TZ).replace(tzinfo=None)
