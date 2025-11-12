# 🚀 MemoBOT — Bot de recordatorios

Un bot ligero para gestionar recordatorios vía Telegram, con apoyo de IA (Gemini) para mejorar textos y resúmenes.

## ✨ Resumen
- 🔑 Se conecta a Telegram usando `TELEGRAM_TOKEN`.
- 🤖 Integra Gemini (`GEMINI_API_KEY`) para generación y asistencia de texto.
- 🗄️ Persiste recordatorios en MySQL (configurado por variables de entorno).


## ⚙️ Configuración mínima

### Requisitos
- Python 3.10+ (recomendado)
- `requirements.txt` presente en el repositorio

### 1) Variables de entorno
- Copia `.env.example` a `.env` y completa las variables obligatorias.
- ⚠️ No subir `.env` al repositorio.

### 2) Entorno virtual e instalación

```bash
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

### 3) Inicializar la base de datos (opcional)
- La estructura inicial está en `db_recordatorios.sql`.

```bash
# importar usando el cliente mysql local
mysql -u <usuario> -p < nombre_basedatos < db_recordatorios.sql
```

### 4) Ejecutar el bot

```bash
source venv/bin/activate
python bot_recordatorios.py
```

## 📝 Variables principales (resumen)
- `TELEGRAM_TOKEN` — token del bot de Telegram (obligatorio)
- `GEMINI_API_KEY` — API key para Gemini (obligatorio si se usa IA)
- `GEMINI_MODEL` — modelo a usar (opcional)
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME` — configuración MySQL
- `SCHEDULER_INTERVAL` — intervalo (segundos) para verificar recordatorios

## 🐞 Debug / logs
- Por defecto el bot escribe en stdout; para más detalle, agrega `LOG_LEVEL=DEBUG` en tu `.env` si el código lo respeta.
- Errores comunes: variables de entorno faltantes, credenciales de BD incorrectas, token de Telegram inválido.

## 🔒 Notas rápidas de seguridad
- Añade `.env` a `.gitignore` para evitar subir secretos.
- En producción usa Docker secrets o un gestor de secretos (Vault, AWS Secrets Manager, etc.).

## 💡 Contribuciones
- Issues y PRs son bienvenidos. Proyecto orientado a uso académico/personal.

