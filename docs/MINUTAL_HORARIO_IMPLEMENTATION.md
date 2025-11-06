# Implementación de Recurrencia por Minutos y Horas

## Resumen de Cambios

Se ha implementado soporte completo para recurrencias en intervalos de minutos y horas, permitiendo comandos como:
- "recuerdame tomar agua cada 1 minuto desde las 22:19 hasta las 22:21"
- "recuerdame revisar el horno cada 15 minutos desde las 14:00 hasta las 16:00"

## Archivos Modificados

### 1. `gemini_service.py`
- **Método `parse_multiple_reminders`**: 
  - Prompt optimizado de ~70 líneas a ~35 líneas
  - Agregados tipos `minutal` y `horario` con ejemplos explícitos
  - Soporte para rangos temporales con `fecha_fin`

### 2. `database.py`
- **Método `validate_recurrence_interval`**:
  - Agregada validación para `minutal`: 1-1440 minutos (1 día máximo)
  - Agregada validación para `horario`: 1-168 horas (7 días máximo)
  
- **Método `update_recurrent_reminder_next_date`**:
  - Agregado cálculo para tipo `minutal`: `timedelta(minutes=intervalo)`
  - Agregado cálculo para tipo `horario`: `timedelta(hours=intervalo)`

### 3. `migrations/add_minutal_horario_tipos.sql` (NUEVO)
- Script de migración para actualizar el ENUM de la columna `tipo_recurrencia`

## Instrucciones de Despliegue

### Paso 1: Aplicar Migración de Base de Datos

```bash
cd /home/mariano/Documentos/Trabajo\ Final/recordatorios
mysql -u root -p < migrations/add_minutal_horario_tipos.sql
```

**Importante**: Este paso es CRÍTICO. Si no se ejecuta, el bot fallará al intentar crear recordatorios con tipos `minutal` u `horario` porque el ENUM no aceptará esos valores.

### Paso 2: Verificar la Migración

```bash
mysql -u root -p -e "USE recordatorios_bot; SHOW COLUMNS FROM recordatorios WHERE Field='tipo_recurrencia';"
```

Deberías ver: `ENUM('minutal','horario','diario','semanal','mensual','anual')`

### Paso 3: Reiniciar el Bot

```bash
# Si el bot está corriendo, detenerlo primero
pkill -f bot_recordatorios.py

# Iniciar el bot
source venv/bin/activate
python bot_recordatorios.py
```

## Ejemplos de Uso

### Ejemplo 1: Intervalo Corto con Límite de Tiempo
**Comando**: "recuerdame tomar agua cada 1 minuto desde las 22:19 hasta las 22:21"

**Resultado esperado**:
- Gemini detecta: tipo_recurrencia="minutal", intervalo=1, fecha_fin="2025-01-05 22:21:00"
- Se crea 1 solo registro en la DB
- El scheduler envía el primer recordatorio a las 22:19
- Actualiza el registro para 22:20
- Actualiza el registro para 22:21
- Después de 22:21, marca el recordatorio como finalizado

### Ejemplo 2: Recordatorio Cada 15 Minutos
**Comando**: "recuerdame revisar el horno cada 15 minutos desde las 14:00"

**Resultado esperado**:
- Gemini detecta: tipo_recurrencia="minutal", intervalo=15, fecha_fin=null
- Recordatorios infinitos cada 15 minutos: 14:00, 14:15, 14:30, 14:45...

### Ejemplo 3: Recordatorio Cada 2 Horas por 1 Día
**Comando**: "recuerdame tomar medicamento cada 2 horas desde las 08:00 hasta las 20:00"

**Resultado esperado**:
- Gemini detecta: tipo_recurrencia="horario", intervalo=2, fecha_fin="2025-01-05 20:00:00"
- Recordatorios: 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00

## Protecciones Anti-Flood Implementadas

### Límites Activos
1. **Máximo 200 recordatorios activos por chat**
2. **Máximo 20 creaciones por minuto por chat**
3. **Validación de intervalos**:
   - Minutal: 1-1440 minutos (1 día)
   - Horario: 1-168 horas (7 días)
   - Diario: 1-365 días
   - Semanal: 1-52 semanas
   - Mensual: 1-24 meses
   - Anual: 1-10 años

### Filtrado en Listado
- Solo se muestran recordatorios de los próximos 7 días
- Evita abrumar al usuario con listas interminables

## Testing Recomendado

### Test 1: Minutal con Fecha Fin
```
/nuevo
> recuerdame test cada 1 minuto desde las 22:19 hasta las 22:21
```
- Esperar 3 minutos
- Verificar que se reciban exactamente 3 notificaciones
- Confirmar que el recordatorio se marque como finalizado

### Test 2: Horario sin Fecha Fin
```
/nuevo
> recuerdame revisar cada 2 horas desde las 10:00
```
- Verificar que se cree el recordatorio
- Confirmar que el scheduler lo actualice correctamente cada 2 horas

### Test 3: Anti-Flood
```
# Intentar crear más de 20 recordatorios en menos de 1 minuto
/nuevo
> recuerdame test1 cada 1 minuto
> recuerdame test2 cada 1 minuto
... (repetir 20+ veces)
```
- Verificar que se rechace después del límite
- Confirmar mensaje de error apropiado

## Monitoreo

### Logs Clave
El scheduler ahora imprimirá:
```
INFO - Recordatorio recurrente {id} actualizado a su próxima fecha
INFO - Recordatorio recurrente {id} finalizó (alcanzó fecha límite)
```

### Consulta SQL para Verificar Recordatorios Minutales/Horarios Activos
```sql
SELECT id, chat_id, tarea, fecha_hora, tipo_recurrencia, intervalo_recurrencia, fecha_fin_recurrencia
FROM recordatorios
WHERE tipo_recurrencia IN ('minutal', 'horario')
  AND notificado = 0
  AND eliminado = 0
ORDER BY fecha_hora;
```

## Rollback (si es necesario)

Si algo falla, puedes revertir el ENUM a su estado anterior:

```sql
USE recordatorios_bot;
ALTER TABLE recordatorios 
MODIFY COLUMN tipo_recurrencia ENUM('diario', 'semanal', 'mensual', 'anual') 
DEFAULT NULL 
COMMENT 'Tipo de repetición';
```

**ADVERTENCIA**: Esto eliminará todos los recordatorios con tipo `minutal` u `horario`.

## Notas Técnicas

- El scheduler verifica recordatorios cada 10 segundos por defecto (configurable)
- Para recordatorios minutales, se recomienda mantener el intervalo del scheduler bajo (< 60 segundos)
- Los cálculos de `timedelta` son automáticos y manejan correctamente cambios de día/mes
- La columna `ultima_ejecucion` se actualiza en cada iteración para auditoría

---
**Fecha de implementación**: 2025-01-05  
**Autor**: GitHub Copilot
