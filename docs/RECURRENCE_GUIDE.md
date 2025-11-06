# 🔄 Recordatorios Recurrentes - Guía de Uso

## 📋 ¿Qué son los Recordatorios Recurrentes?

Los recordatorios recurrentes te permiten agendar tareas que se repiten automáticamente en intervalos regulares (diario, semanal, mensual o anual), sin necesidad de crearlos manualmente cada vez.

## 🎯 Tipos de Recurrencia Soportados

### 1. **Diaria** 📅
Repite el recordatorio cada día o cada ciertos días.

**Ejemplos:**
- "Recordame tomar vitaminas todos los días a las 9"
- "Cada día a las 8 recordame hacer ejercicio"
- "Todos los días a las 22 recordame apagar las luces"

### 2. **Semanal** 📆
Repite el recordatorio cada semana o en días específicos de la semana.

**Ejemplos:**
- "Todos los lunes a las 10 recordame la reunión de equipo"
- "Cada viernes a las 18 recordame revisar el email"
- "Los martes y jueves a las 7 recordame ir al gimnasio"
- "Cada 2 semanas el miércoles a las 15"

### 3. **Mensual** 🗓️
Repite el recordatorio cada mes.

**Ejemplos:**
- "El día 1 de cada mes a las 10 recordame pagar el alquiler"
- "Cada mes el 15 a las 12 recordame la cita médica"

### 4. **Anual** 🎂
Repite el recordatorio cada año.

**Ejemplos:**
- "El 25 de diciembre a las 9 recordame feliz navidad"
- "Cada año el 14 de febrero recordame comprar regalo"

## 💡 Ejemplos de Uso

### Recordatorios Simples con Límite de Tiempo
```
"Todos los viernes de noviembre a las 14 recordame tomar agua"
→ Se repetirá cada viernes solo durante noviembre
```

### Recordatorios con Intervalos Personalizados
```
"Cada 2 semanas el martes a las 10 recordame reunión"
→ Se repetirá cada 2 semanas
```

### Recordatorios Diarios
```
"Todos los días a las 8 recordame tomar medicamento"
→ Se repetirá todos los días a las 8 AM
```

## 🔧 Características Técnicas

### ✅ Funcionamiento Automático
- Una vez creado el recordatorio recurrente, el sistema **genera automáticamente** la próxima instancia después de enviarte la notificación.
- No necesitás hacer nada: el recordatorio se repetirá solo según la frecuencia configurada.

### 📊 Información Almacenada
Para cada recordatorio recurrente, el sistema guarda:
- **Tipo de recurrencia**: diario, semanal, mensual o anual
- **Intervalo**: cada cuántos días/semanas/meses
- **Días de la semana**: para recordatorios semanales específicos
- **Fecha límite** (opcional): hasta cuándo se debe repetir

### 🔄 Proceso de Regeneración
1. El scheduler detecta que es hora de enviar el recordatorio
2. Te envía la notificación
3. Marca el recordatorio como notificado
4. **Automáticamente crea la próxima instancia** con la nueva fecha calculada
5. El proceso se repite indefinidamente (o hasta la fecha límite)

## 📝 Visualización en el Bot

Cuando crees un recordatorio recurrente, verás un mensaje como:

```
✅ ¡Recordatorio recurrente agendado!

📌 tomar agua

🔄 Frecuencia: todas las semanas
📅 Primera vez: viernes 08 de noviembre a las 14:00 hs

💡 Se repetirá automáticamente
```

## ⚠️ Notas Importantes

1. **Persistencia**: Los recordatorios recurrentes se guardan en la base de datos y sobreviven reinicios del bot.

2. **Edición**: Cuando edites un recordatorio, podés convertirlo en recurrente o viceversa.

3. **Eliminación**: Al eliminar un recordatorio recurrente, solo se elimina esa instancia específica. Las futuras instancias se seguirán generando.

4. **Límites de tiempo**: Si especificás un período limitado (ej: "todos los viernes de noviembre"), el sistema dejará de generar nuevas instancias automáticamente cuando se alcance la fecha límite.

5. **Visualización**: En /listar solo verás la **próxima instancia pendiente** de cada recordatorio recurrente, no todas las futuras.

## 🎨 Ejemplos Avanzados

### Combinaciones Complejas
```
"Cada 3 días a las 20 recordame regar las plantas"
"Los lunes, miércoles y viernes a las 6 recordame correr"
"El primer día de cada mes a las 9 recordame revisar finanzas"
"Cada año el 1 de enero a las 12 recordame propósitos"
```

---

**Desarrollado para el Bot de Recordatorios v2.2.0**  
*Sistema de Recurrencia implementado el 5 de noviembre de 2025*
