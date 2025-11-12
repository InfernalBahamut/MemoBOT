# Informe Técnico-Académico

Bot de Recordatorios Inteligente con Telegram, Gemini y MySQL

Autores: Mariano Cabeda, Lucas Medina  
Fecha: Noviembre 2025  
Repositorio: https://github.com/InfernalBahamut/MemoBOT

---

## Resumen

Este informe presenta el diseño, implementación y evaluación de un bot de recordatorios para Telegram que integra un servicio de IA (Google Gemini) para interpretar lenguaje natural en español. El sistema permite crear, listar, editar y eliminar recordatorios, incluyendo recurrencias, mediante una arquitectura modular compuesta por: interfaz Telegram (python-telegram-bot), servicio de IA (Gemini), capa de persistencia (MySQL) y un planificador de notificaciones en segundo plano. Se detallan decisiones de diseño, modelo de datos, manejo de zonas horarias (UTC ↔ Argentina), políticas anti-flood, y se discuten limitaciones y trabajo futuro.

Palabras clave: Telegram Bot, PLN, Gemini, MySQL, Recordatorios, Recurrencia, Zonas horarias.

---

## 1. Introducción

La gestión de recordatorios personales es una necesidad transversal. Los bots de mensajería ofrecen un canal natural y accesible. Este proyecto implementa un bot que permite a usuarios en Telegram expresar recordatorios en lenguaje natural, que son interpretados y almacenados, para luego notificar en el momento oportuno. A diferencia de enfoques rígidos basados en comandos, se utiliza IA generativa para comprender matices del español informal y extraer estructuras temporales y de tarea.

## 2. Objetivos y Alcance

- Objetivo general: Diseñar e implementar un bot de recordatorios que entienda lenguaje natural y gestione recordatorios únicos y recurrentes con notificaciones oportunas.
- Objetivos específicos:
  - Integrar un modelo de IA (Gemini) para parsing de intención, fecha/hora y recurrencia.
  - Persistir recordatorios con control de versiones y soft delete en MySQL.
  - Implementar un scheduler robusto para notificaciones y manejo de recurrencias.
  - Proveer interfaz conversacional en Telegram, con flujos de creación, edición y listado.

Alcance: Español (variante rioplatense), zona horaria Argentina por defecto, persistencia local en MySQL, envío de mensajes vía Telegram Bot API.

## 3. Tecnologías y Marco Conceptual

- Python 3.8+ como lenguaje principal.
- python-telegram-bot v20+ para la interfaz Telegram (handlers asincrónicos, teclados inline).
- Google Generative AI (Gemini) para: clasificación de mensajes, extracción de tarea/fecha/recurrencia, edición contextual y generación de mensajes breves.
  - Modelo configurable por variable de entorno `GEMINI_MODEL`; el código usa por defecto `gemini-2.0-flash-exp` si no se especifica, aunque el despliegue puede optar por variantes más recientes (p. ej., `gemini-2.5-flash`).
- MySQL 8.0 para persistencia con pooling de conexiones.
- pytz para manejo explícito de zonas horarias.
- python-dotenv para gestión de credenciales y configuración.

## 4. Metodología de Desarrollo

- Arquitectura modular con separación de responsabilidades: configuración, IA, base de datos, lógica de UI (handlers), scheduler y utilidades de tiempo.
- Diseño guiado por prompts: se definieron prompts específicos para cada tarea de la IA (clasificación, parsing, edición, mensajes breves, solicitud de hora), con validación sintáctica de salidas JSON.
- Validaciones defensivas: límites anti-flood, verificación de fechas futuras, y normalización de nombres de campos para compatibilidad con el esquema de datos.
- Concurrencia segura: scheduler en thread dedicado con event loop propio para llamadas a Telegram.

## 5. Arquitectura del Sistema

Componentes principales del proyecto (carpeta `recordatorios/`):

- `bot_recordatorios.py`: Punto de entrada. Inicializa configuración, base de datos, servicio Gemini, handlers y scheduler; arranca el polling de Telegram.
- `handlers.py`: Lógica de interacción con el usuario; flujos de creación, edición, listado y eliminación con `ConversationHandler` y botones `InlineKeyboard`.
- `gemini_service.py`: Encapsula la interacción con Gemini. Define prompts y métodos para: parsing de mensajes, detección de múltiples recordatorios, edición contextual, clasificación y mensajes breves.
- `database.py`: Capa de acceso a datos (CRUD) con `mysql.connector.pooling`. Incluye validaciones anti-flood y actualización de recurrencias.
- `scheduler.py`: Verifica periódicamente recordatorios vencidos, envía notificaciones y actualiza recurrencias.
- `config.py`: Carga y valida variables de entorno; expone `db_config` y parámetros del sistema.
- `timezone_utils.py`: Conversión entre UTC y Argentina, y utilidades de tiempo.
- `db_recordatorios.sql`: Script de creación del esquema, índices, procedimientos y triggers.

Diagrama de flujo de datos (alto nivel):

```
Usuario → Telegram → Handlers → Gemini → Database
                                  ↓
                          Scheduler → Notificaciones (Telegram)
```

## 6. Implementación y Flujos Operativos

### 6.1 Creación de recordatorios

1) El usuario envía un mensaje en lenguaje natural.  
2) `classify_and_respond()` determina si es recordatorio o fuera de tema/saludo.  
3) `parse_multiple_reminders()` extrae estructura: tarea (en infinitivo), fecha, hora, y opcionalmente recurrencia.  
4) Validaciones anti-flood y de consistencia.  
5) Conversión de hora Argentina a UTC para almacenar.  
6) Persistencia vía `create_reminder()`.  
7) Confirmación al usuario con formato legible en español.

Si falta la hora, el bot solicita explícitamente el horario y reintenta el parseo de la hora.

### 6.2 Edición

- La edición se inicia desde la lista con un botón dedicado.  
- `parse_reminder_edit()` combina contexto original, texto de edición y estado actual para inferir cambios parciales (p. ej., solo fecha) o totales (tarea + fecha).  
- Se aplica control de versiones: la versión previa se marca como no actual y se inserta una nueva versión con cambios.

### 6.3 Listado y eliminación

- Listado: muestra próximos 7 días (futuros y/o próximas ejecuciones de recurrentes) con botones de acción.  
- Eliminación: individual con confirmación o masiva (soft delete).  

### 6.4 Notificaciones y recurrencia

- El `ReminderScheduler` ejecuta un bucle con intervalo configurable (por defecto 10 s).  
- Para cada recordatorio vencido:
  - Genera mensaje breve con Gemini y extrae contexto relevante para enriquecer la notificación.
  - Envía el mensaje por Telegram.  
  - Si es recurrente, se calcula la próxima fecha según el tipo/intervalo y se actualiza el mismo registro. Si se supera una `fecha_fin`, el recordatorio se finaliza (marcado como notificado).  
  - Si es único, se marca como notificado.

## 7. Modelo de Datos y Persistencia

Tabla única `recordatorios` que concentra recordatorios únicos y recurrentes, más campos de auditoría y versionado. Características:

- Soft delete (`eliminado`, `fecha_eliminacion`, `usuario_eliminacion`).
- Control de versiones: `version`, `recordatorio_original_id`, `es_version_actual`.
- Recurrencia en el mismo registro: `es_recurrente`, `tipo_recurrencia`, `intervalo_recurrencia`, `dias_semana`, `fecha_fin_recurrencia`, `ultima_ejecucion`.
- Índices para consultas del scheduler y listados.

El script `db_recordatorios.sql` incluye además procedimientos para obtener vencidos y calcular próximas ejecuciones, y triggers para auditoría.

## 8. Integración con IA (Gemini)

- Salidas JSON validadas: los prompts fuerzan nombres de campos consistentes con la base de datos, y se implementa `_extract_json()` para robustez.  
- Tareas soportadas:
  - Clasificación de intención (recordatorio, saludo, fuera de tema).
  - Parsing de recordatorios múltiples / recurrentes.
  - Edición contextual conservando información previa.
  - Generación de notificaciones breves y amables.
- Configuración de modelo: `GEMINI_API_KEY` y `GEMINI_MODEL` vía `.env`. Valor por defecto en el código: `gemini-2.0-flash-exp` si no se establece la variable; se recomienda mantenerlo configurable para poder utilizar modelos más recientes.
- Consideraciones de calidad: validación de fechas, normalización a infinitivo y límites de longitud/estilo en mensajes generados.

## 9. Gestión de Zonas Horarias

- El servidor y la BD operan en UTC; la interfaz de usuario muestra hora de Argentina.  
- Conversión explícita: `to_utc()` para almacenar y `to_argentina()` para presentar.  
- `now_for_user()` y `format_datetime_argentina()` soportan comparaciones y presentación consistentes.

## 10. Seguridad, Privacidad y Robustez

- Credenciales mediante variables de entorno (`.env`), validadas en `config.py` (terminación temprana si faltan).
- Límites anti-flood: 200 recordatorios activos por chat y 20 creaciones por minuto.
- Validación de intervalos de recurrencia para evitar spam (mínimos y máximos razonables).  
- Eliminación lógica para preservar auditoría y evitar pérdidas accidentales.  
- Manejo de errores y fallback: mensajes genéricos si falla IA; reintentos controlados en scheduler.

## 11. Casos de Borde y Tolerancia a Fallos

- Mensajes ambiguos o sin fecha: se solicita hora/fecha adicional de forma guiada.  
- Formatos de hora variados: soporte de "10am", "15:30", "9 de la mañana"; validación a `HH:MM:SS`.  
- Diferencias de huso horario: todo se normaliza a UTC al persistir.  
- Caídas temporales de IA o Telegram: fallback a mensajes sin enriquecimiento; el sistema registra errores sin detener el scheduler.  
- Concurrencia: el scheduler usa un event loop independiente por thread para enviar mensajes de forma segura.

## 12. Evaluación (Funcional)

Se ejecutaron pruebas funcionales manuales sobre los flujos principales: creación (simple y recurrente), edición con cambios parciales y totales, listado semanal y eliminación con confirmación. Se verificó la consistencia de horarios (entrada en Argentina, almacenamiento en UTC, presentación en Argentina) y las validaciones anti-flood.

Entorno de prueba esperado:
- Python ≥ 3.8, MySQL ≥ 8.0.  
- Variables de entorno válidas y tabla creada con `db_recordatorios.sql`.  
- Dependencias instaladas vía `requirements.txt`.

## 13. Limitaciones

- Dependencia de la calidad del modelo de IA para el parsing; aunque mitigada con validaciones, la ambigüedad del lenguaje puede requerir interacciones adicionales.  
- El scheduler opera con sondeo periódico; una granularidad demasiado fina puede impactar consumo, y demasiado gruesa puede demorar notificaciones.
- No se implementa autenticación avanzada más allá del `chat_id` de Telegram.
- No se incluye internacionalización completa (el foco es español de Argentina).

## 14. Trabajo Futuro

- Métricas y telemetría de precisión del parsing (golden set de frases y evaluación automática).  
- Pruebas automatizadas end-to-end con entornos simulados de Telegram y DB.  
- Soporte de múltiples zonas horarias por usuario.  
- Panel web de administración e historial de versiones.  
- Persistencia de logs estructurados y dashboard de estado del scheduler.  
- Mecanismo de rate limiting adaptativo a nivel global.

## 15. Conclusiones

El sistema demuestra que la integración de IA generativa con una arquitectura modular permite una experiencia conversacional natural y efectiva para la gestión de recordatorios. La persistencia con control de versiones, el manejo explícito de zonas horarias y el scheduler en segundo plano brindan robustez operativa. Las líneas de mejora proponen avanzar en mediciones objetivas, pruebas automatizadas e internacionalización.

## 16. Referencias

- python-telegram-bot (v20+): https://docs.python-telegram-bot.org/
- Google Generative AI for Python: https://ai.google.dev/gemini-api/docs
- mysql-connector-python: https://dev.mysql.com/doc/connector-python/en/
- MySQL 8.0 Reference Manual: https://dev.mysql.com/doc/refman/8.0/en/
- pytz: https://pythonhosted.org/pytz/

## Anexo A. Variables de Entorno (ejemplo)

```
TELEGRAM_TOKEN=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash-exp
DB_HOST=localhost
DB_PORT=3306
DB_USER=...
DB_PASS=...
DB_NAME=recordatorios_db
SCHEDULER_INTERVAL=10
TIMEZONE=America/Argentina/Buenos_Aires
```

## Anexo B. Requisitos y Ejecución

Requisitos: Python 3.8+, MySQL 8.0+, credenciales válidas, dependencias de `requirements.txt`.

Pasos generales:
1) Crear esquema con `db_recordatorios.sql` en MySQL.  
2) Configurar `.env` según Anexo A.  
3) Instalar dependencias.  
4) Ejecutar `bot_recordatorios.py` y conversar por Telegram con el bot.
