# Changelog - Versión 2.3.0

## 🎯 Cambios Principales

### Borrado Lógico
- ✅ Implementado **borrado lógico** en lugar de eliminación física
- ✅ Nueva columna `eliminado` (TINYINT) para marcar registros eliminados
- ✅ Nueva columna `fecha_eliminacion` (DATETIME) para auditoría
- ✅ Índice `idx_eliminado` para optimizar consultas

### Seguimiento de Usuarios
- ✅ Nueva columna `username` (VARCHAR) para almacenar el usuario de Telegram
- ✅ Se guarda el username al crear recordatorios
- ✅ Se registra quién elimina cada recordatorio en los logs

### Mejoras de UX
- ✅ **Menú principal simplificado**: Eliminados botones de "Editar" y "Eliminar"
- ✅ Edición y eliminación ahora solo desde "Ver Mis Recordatorios"
- ✅ **Confirmación de borrado**: Se pide confirmación antes de eliminar cada recordatorio
- ✅ Mensajes mejorados con información contextual

---

## 📝 Archivos Modificados

### 1. `update_database_soft_delete.sql` (NUEVO)
Script SQL para agregar las nuevas columnas:
```sql
ALTER TABLE recordatorios ADD COLUMN eliminado TINYINT(1) DEFAULT 0;
ALTER TABLE recordatorios ADD COLUMN username VARCHAR(255) DEFAULT NULL;
ALTER TABLE recordatorios ADD COLUMN fecha_eliminacion DATETIME DEFAULT NULL;
ALTER TABLE recordatorios ADD INDEX idx_eliminado (eliminado);
```

### 2. `database.py`
**Cambios en métodos:**

#### `create_reminder()`
- Nuevo parámetro: `username: Optional[str] = None`
- Almacena el username en la base de datos

#### `delete_reminder()`
- **Borrado lógico**: `SET eliminado = 1, fecha_eliminacion = NOW()`
- Nuevo parámetro: `username: Optional[str] = None`
- Log mejorado con username

#### `delete_all_reminders()`
- **Borrado lógico masivo**: `SET eliminado = 1`
- Nuevo parámetro: `username: Optional[str] = None`
- Log mejorado con username

#### Consultas actualizadas con filtro `eliminado = 0`:
- `get_pending_reminders()`
- `get_upcoming_reminders()`
- `get_past_reminders()`
- `get_reminder_by_id()`
- `get_due_reminders()`
- `get_recurrent_reminder()`

### 3. `handlers.py`
**Cambios en handlers:**

#### `start()` y `menu()`
- **Menú simplificado**: Solo 3 opciones
  - 📝 Crear Recordatorio
  - 📋 Ver Mis Recordatorios
  - ❓ Ayuda
- Eliminados botones de "✏️ Editar" y "🗑️ Eliminar"

#### `create_reminder()`
- Extrae `username` de `update.message.from_user.username`
- Pasa username a `db.create_reminder()`

#### `delete_reminder()`
- Nuevo parámetro: `confirmed: bool = False`
- **Flujo de confirmación**:
  1. Primera llamada: Muestra botón "✅ Sí, eliminar"
  2. Segunda llamada (confirmada): Ejecuta eliminación lógica
- Extrae `username` de `update.effective_user.username`
- Pasa username a `db.delete_reminder()`

#### `delete_all_reminders()`
- Extrae y pasa `username`

#### `handle_callback_query()`
- Nuevo callback: `delconfirm:{job_id}` para confirmación
- Callback `del:{job_id}` ahora llama con `confirmed=False`
- Callback `menu_principal` muestra menú simplificado
- Mensajes actualizados en callbacks de editar/eliminar

---

## 🔧 Migraciones de Base de Datos

### Ejecutar migración:
```bash
cd /home/mariano/Documentos/Trabajo\ Final/recordatorios
mysql -u root -pRaizCuadrada < update_database_soft_delete.sql
```

### Verificar cambios:
```sql
USE recordatorios_db;
DESCRIBE recordatorios;
```

Columnas agregadas:
- `eliminado` TINYINT(1) DEFAULT 0
- `username` VARCHAR(255) DEFAULT NULL
- `fecha_eliminacion` DATETIME DEFAULT NULL

---

## 🎨 Cambios en la Interfaz

### Antes (v2.2.0):
```
🤖 Menú Principal

📝 Crear Recordatorio
📋 Ver Mis Recordatorios
✏️ Editar  |  🗑️ Eliminar
❓ Ayuda
```

### Ahora (v2.3.0):
```
🤖 Menú Principal

📝 Crear Recordatorio
📋 Ver Mis Recordatorios
❓ Ayuda
```

### Flujo de eliminación:
**Antes**: Click en 🗑️ → Eliminado inmediatamente

**Ahora**: 
1. Click en 🗑️
2. Mensaje de confirmación:
   ```
   ⚠️ ¿Confirmar eliminación?
   
   📌 Nombre del recordatorio
   📅 06/11/2024 - 20:00 hs
   
   ✅ Sí, eliminar  |  ❌ No, cancelar
   ```
3. Click en "✅ Sí, eliminar" → Eliminación lógica

---

## 🔐 Auditoría

### Logs mejorados:

**Creación de recordatorio:**
```
INFO - Recordatorio 7 creado para chat 1506941156 por usuario @mariano
```

**Eliminación de recordatorio:**
```
INFO - Recordatorio 7 eliminado lógicamente por @mariano
```

**Eliminación masiva:**
```
INFO - Usuario @mariano eliminó lógicamente 3 recordatorios
```

### Base de datos:
Los recordatorios eliminados ahora quedan en la base con:
- `eliminado = 1`
- `fecha_eliminacion = '2024-11-05 18:30:08'`
- `username = '@mariano'`

---

## 🧪 Testing

### Casos de prueba:

1. **Crear recordatorio**:
   - ✅ Username se guarda correctamente
   - ✅ Recordatorio aparece en /listar

2. **Eliminar recordatorio**:
   - ✅ Se muestra confirmación
   - ✅ Al confirmar, se marca `eliminado = 1`
   - ✅ No aparece más en /listar
   - ✅ Registro permanece en base de datos

3. **Menú principal**:
   - ✅ No muestra botones de editar/eliminar
   - ✅ Solo 3 opciones visibles

4. **Desde "Ver Mis Recordatorios"**:
   - ✅ Botones ✏️ y 🗑️ funcionan correctamente
   - ✅ Confirmación de borrado aparece

---

## 📊 Impacto en Performance

- **Consultas optimizadas** con índice en `eliminado`
- **Sin DELETE físico**: Mejor para auditoría
- **Mismo rendimiento** para el usuario final

---

## 🔄 Compatibilidad

- ✅ Compatible con recordatorios existentes
- ✅ Recordatorios antiguos tienen `eliminado = 0` por defecto
- ✅ No requiere modificación de datos existentes

---

## 📌 Notas Importantes

1. **Borrado lógico** permite:
   - Recuperación de datos si es necesario
   - Auditoría completa de operaciones
   - Cumplimiento de normativas de datos

2. **Username** puede ser NULL:
   - Algunos usuarios de Telegram no tienen username
   - El sistema maneja correctamente valores NULL

3. **Menú simplificado**:
   - Reduce confusión para nuevos usuarios
   - Centraliza CRUD en "Ver Mis Recordatorios"

---

## 🚀 Próximos Pasos

Posibles mejoras futuras:
- [ ] Panel de administración para ver registros eliminados
- [ ] Función de "papelera" para recuperar eliminados
- [ ] Eliminación física automática después de X días
- [ ] Estadísticas de uso por usuario
