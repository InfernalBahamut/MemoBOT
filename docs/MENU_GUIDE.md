# 📱 Guía del Menú Interactivo

## Estructura del Menú Principal

Cuando el usuario ejecuta `/start` o `/menu`, ve el siguiente menú:

```
👋 ¡Hola [Nombre]!

🤖 Soy tu Bot de Recordatorios Inteligente

💡 Puedo entender lenguaje natural y ayudarte a recordar
cualquier cosa que necesites.

¿Qué querés hacer?

┌────────────────────────────────┐
│  📝 Crear Recordatorio         │
├────────────────────────────────┤
│  📋 Ver Mis Recordatorios      │
├────────────┬───────────────────┤
│  ✏️ Editar │  🗑️ Eliminar      │
├────────────┴───────────────────┤
│  ❓ Ayuda                       │
└────────────────────────────────┘
```

## Flujo de Navegación

### 1️⃣ Crear Recordatorio

```
[Menu Principal] → [📝 Crear Recordatorio]
                     ↓
            Muestra instrucciones:
            ────────────────────────
            📝 Crear un Recordatorio
            
            Es muy fácil! Simplemente escribime
            qué querés recordar y cuándo.
            
            🌟 Ejemplos:
            • Recordame pagar la luz mañana a las 10
            • Llamar al dentista el viernes a las 15:30
            • Comprar pan en 20 minutos
            
            💬 Escribí tu recordatorio ahora:
            
            [« Volver al Menú]
```

### 2️⃣ Ver Mis Recordatorios

```
[Menu Principal] → [📋 Ver Mis Recordatorios]
                     ↓
            Si hay recordatorios:
            ────────────────────────
            📋 Tus recordatorios pendientes (3):
            
            🆔 42
            📌 Pagar la luz
            📅 Miércoles 06 de noviembre - 10:00 hs
            ┌────────────┬──────────┐
            │ ✏️ Editar  │ 🗑️ Borrar │
            └────────────┴──────────┘
            
            [más recordatorios...]
            
            [« Volver al Menú]
            ────────────────────────
            
            Si NO hay recordatorios:
            ────────────────────────
            📭 No tenés ningún recordatorio pendiente.
            
            ¡Creá uno escribiendo qué querés recordar!
            
            [« Volver al Menú]
```

### 3️⃣ Editar

```
[Menu Principal] → [✏️ Editar]
                     ↓
            ✏️ Editar un Recordatorio
            
            Para editar un recordatorio:
            
            1️⃣ Usa el comando: /editar ID
               Ejemplo: /editar 42
            
            2️⃣ O desde 'Ver Mis Recordatorios',
               presiona el botón ✏️ Editar
            
            💡 Consejo: Usa /listar para ver
            los IDs de tus recordatorios
            
            [« Volver al Menú]
```

### 4️⃣ Eliminar

```
[Menu Principal] → [🗑️ Eliminar]
                     ↓
            🗑️ Eliminar Recordatorios
            
            ¿Qué querés hacer?
            
            ┌────────────────────────────────┐
            │  🗑️ Eliminar uno específico    │
            ├────────────────────────────────┤
            │  ⚠️ Eliminar TODOS             │
            ├────────────────────────────────┤
            │  « Volver al Menú              │
            └────────────────────────────────┘
                     ↓
            ┌─────────────────┬─────────────────┐
            │  Uno específico │  TODOS          │
            ├─────────────────┼─────────────────┤
            │  Instrucciones  │  Confirmación   │
            │  de cómo borrar │  ¿Estás seguro? │
            │  un recordatorio│  [Sí] [No]      │
            └─────────────────┴─────────────────┘
```

### 5️⃣ Ayuda

```
[Menu Principal] → [❓ Ayuda]
                     ↓
            ❓ Ayuda - Bot de Recordatorios
            
            📋 Comandos Disponibles:
            • /start - Mostrar menú principal
            • /menu - Volver al menú
            • /listar - Ver tus recordatorios
            • /editar ID - Editar un recordatorio
            • /borrar ID - Eliminar un recordatorio
            • /eliminar - Eliminar todos
            • /cancelar - Cancelar operación
            
            💡 Cómo Funciona:
            Solo escribí en lenguaje natural qué
            querés recordar y cuándo.
            
            🌟 Ejemplos:
            • Pagar el alquiler el 5 a las 10
            • Comprar regalo para mamá mañana
            • Llamar al médico el viernes a las 3 pm
            
            ¡Es así de simple! 😊
            
            [« Volver al Menú]
```

## Callbacks Implementados

| Callback | Acción |
|----------|--------|
| `menu_principal` | Muestra el menú principal |
| `menu_crear` | Instrucciones para crear recordatorio |
| `listar` | Lista todos los recordatorios |
| `menu_editar` | Instrucciones para editar |
| `menu_eliminar` | Opciones de eliminación |
| `help_borrar` | Instrucciones para borrar uno |
| `confirm_eliminar` | Confirmar eliminar todos |
| `new_help` | Ayuda completa |
| `edit:ID` | Inicia edición del recordatorio ID |
| `del:ID` | Elimina el recordatorio ID |
| `delall_confirm` | Confirma eliminación de todos |
| `delall_cancel` | Cancela eliminación de todos |

## Comandos vs Menú

| Funcionalidad | Comando | Botón en Menú |
|---------------|---------|---------------|
| Ver menú | `/start` o `/menu` | Botón "« Volver al Menú" |
| Crear recordatorio | Escribir texto libre | "📝 Crear Recordatorio" |
| Ver lista | `/listar` | "📋 Ver Mis Recordatorios" |
| Editar | `/editar ID` | "✏️ Editar" → Instrucciones |
| Borrar | `/borrar ID` | "🗑️ Eliminar" → Opciones |
| Ayuda | `/start` → Ayuda | "❓ Ayuda" |

## Características del Menú

### ✨ Ventajas

1. **Intuitivo**: Los usuarios ven todas las opciones disponibles
2. **Navegable**: Botones "Volver" en cada pantalla
3. **Visual**: Emojis hacen el menú más atractivo
4. **Guiado**: Instrucciones claras en cada sección
5. **Flexible**: Combina comandos de texto y botones

### 🎯 Experiencia de Usuario

- **Primera vez**: El menú guía al usuario sobre qué puede hacer
- **Usuario regular**: Puede usar comandos rápidos (`/listar`, `/editar ID`)
- **Usuario perdido**: Siempre puede volver al menú con `/menu`

### 🔄 Flujo Circular

```
      ┌─────────────┐
      │    MENÚ     │
      │  PRINCIPAL  │
      └──────┬──────┘
         ┌───┼───┐
    ┌────┴───┴───┴────┐
    │                 │
    ▼                 ▼
┌───────┐         ┌───────┐
│ Crear │         │ Listar│
└───┬───┘         └───┬───┘
    │                 │
    └────┬───┬────────┘
         │   │
         ▼   ▼
    ┌─────────────┐
    │   Volver    │
    │   al Menú   │
    └─────────────┘
```

## Personalización

El menú puede personalizarse fácilmente modificando:

1. **Texto de bienvenida**: En `handlers.start()`
2. **Botones del menú**: En `keyboard` de cada método
3. **Mensajes de ayuda**: En los diferentes callbacks
4. **Emojis**: Cambiar los iconos según preferencia

## Próximas Mejoras Sugeridas

- [ ] Menú de configuración (zona horaria, idioma)
- [ ] Estadísticas (total de recordatorios creados, completados)
- [ ] Categorías/Etiquetas en el menú
- [ ] Recordatorios recurrentes desde el menú
- [ ] Plantillas de recordatorios frecuentes
