# Bot de Recordatorios con Telegram, Gemini y MySQL

Bot inteligente de recordatorios que utiliza procesamiento de lenguaje natural para entender y agendar tareas.

## 🏗️ Arquitectura Refactorizada

El proyecto ha sido refactorizado siguiendo principios de código limpio y arquitectura modular:

### Estructura del Proyecto

```
recordatorios/
├── bot_recordatorios.py    # Punto de entrada principal
├── config.py                # Configuración centralizada
├── database.py              # Gestión de base de datos
├── gemini_service.py        # Servicio de IA (Gemini)
├── scheduler.py             # Scheduler de recordatorios
├── handlers.py              # Handlers de Telegram
├── requirements.txt         # Dependencias del proyecto
└── .env                     # Variables de entorno
```

### Módulos

#### 🔧 `config.py`
- Carga y valida variables de entorno
- Configuración centralizada de la aplicación
- Validación de parámetros requeridos

#### 💾 `database.py`
- Clase `DatabaseManager` para gestión de BD
- Pool de conexiones a MySQL
- Operaciones CRUD para recordatorios
- Context manager para manejo seguro de conexiones

#### 🤖 `gemini_service.py`
- Clase `GeminiService` para integración con IA
- Parseo de lenguaje natural
- Extracción de tareas y fechas
- Validación de respuestas

#### ⏰ `scheduler.py`
- Clase `ReminderScheduler` para envío automático
- Ejecución en thread separado
- Verificación periódica de recordatorios pendientes
- Envío de notificaciones

#### 📱 `handlers.py`
- Clase `TelegramHandlers` para lógica del bot
- Comandos y callbacks organizados
- Flujo de conversación para edición
- Interfaz de usuario con botones interactivos

## 🚀 Características

- ✅ **Lenguaje Natural**: Entiende frases como "Recordame comprar pan mañana a las 10"
- ✅ **Base de Datos MySQL**: Persistencia de recordatorios
- ✅ **IA con Gemini**: Procesamiento inteligente de texto
- ✅ **Notificaciones Automáticas**: Scheduler en segundo plano
- ✅ **Interfaz Interactiva**: Botones para editar/borrar recordatorios
- ✅ **Arquitectura Modular**: Código limpio y mantenible

## 📦 Instalación

1. **Clonar el repositorio o copiar los archivos**

2. **Instalar dependencias**:
```bash
pip install -r requirements.txt
```

3. **Configurar variables de entorno** (archivo `.env`):
```env
# Telegram Bot Token
TELEGRAM_TOKEN=tu_token_aqui

# Gemini API Key
GEMINI_API_KEY=tu_api_key_aqui
GEMINI_MODEL=gemini-2.0-flash-exp

# MySQL Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASS=tu_password
DB_NAME=recordatorios_db

# Scheduler
SCHEDULER_INTERVAL=10
```

4. **Crear la base de datos**:
```sql
CREATE DATABASE recordatorios_db;
USE recordatorios_db;

CREATE TABLE recordatorios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    tarea TEXT NOT NULL,
    fecha_hora DATETIME NOT NULL,
    notificado TINYINT DEFAULT 0,
    INDEX idx_chat_notificado (chat_id, notificado),
    INDEX idx_fecha_notificado (fecha_hora, notificado)
);
```

## 🎯 Uso

### Iniciar el bot:
```bash
python bot_recordatorios.py
```

### 📱 Menú Interactivo

Al iniciar el bot con `/start`, verás un **menú interactivo** con las siguientes opciones:

- **📝 Crear Recordatorio** - Instrucciones para crear un nuevo recordatorio
- **📋 Ver Mis Recordatorios** - Lista todos tus recordatorios pendientes
- **✏️ Editar** - Guía para editar recordatorios existentes
- **🗑️ Eliminar** - Opciones para borrar recordatorios
- **❓ Ayuda** - Información completa sobre comandos y uso

### Comandos disponibles:

- `/start` - Mostrar menú principal
- `/menu` - Volver al menú principal
- `/listar` - Ver recordatorios pendientes
- `/editar <ID>` - Editar un recordatorio
- `/borrar <ID>` - Borrar un recordatorio específico
- `/eliminar` - Borrar todos los recordatorios
- `/cancelar` - Cancelar operación actual

### Ejemplos de uso:

```
"Recordame pagar la luz mañana a las 10"
"Llamar al dentista el viernes a las 15:30"
"Comprar pan en 20 minutos"
"Reunión con el equipo el lunes 10 de noviembre a las 9"
```

## 🔄 Mejoras Implementadas

### Separación de Responsabilidades
- Cada módulo tiene una responsabilidad única y bien definida
- Fácil de testear y mantener

### Gestión de Recursos
- Context managers para conexiones de BD
- Pool de conexiones reutilizable
- Manejo apropiado de excepciones

### Configuración Centralizada
- Variables de entorno validadas al inicio
- Configuración fácilmente modificable
- Valores por defecto sensatos

### Código Limpio
- Documentación en docstrings
- Type hints donde es apropiado
- Nombres descriptivos
- Funciones pequeñas y enfocadas

### Manejo de Errores
- Try-except apropiados en cada capa
- Logging detallado
- Rollback de transacciones en caso de error

## 📝 Notas Técnicas

- **Python**: >= 3.8
- **MySQL**: >= 8.0
- **Telegram Bot API**: >= 20.0
- **Google Generative AI**: >= 0.3.0

## 🛠️ Mantenimiento

Para agregar nuevas funcionalidades:

1. **Nuevos comandos**: Agregar métodos en `handlers.py`
2. **Operaciones de BD**: Agregar métodos en `database.py`
3. **Lógica de IA**: Modificar `gemini_service.py`
4. **Configuración**: Actualizar `config.py`

## 📄 Licencia

Este proyecto es de código abierto y está disponible para uso educativo.
