# Project-E Sync (PESync)

PESync es una herramienta de automatización en Python diseñada para gestionar la sincronización y el respaldo de componentes de emulación. El script automatiza el flujo de búsqueda, descarga y almacenamiento en la nube (Dropbox, Google Drive) de los siguientes recursos:

- **Emu**: El binario principal del entorno en formato `AppImage` para sistemas compatibles.
- **Licencias del sistema**: Archivos de configuración necesarios para la ejecución del emulador.
- **Actualizaciones del sistema**: Componentes base requeridos para la compatibilidad del emulador.

Esta herramienta está pensada para la gestión personal de respaldos y la automatización de la configuración del entorno de trabajo.

```mermaid
graph TD
    A[Usuario] -- "iniciar_pesync.bat" --> B[main.py]
    B -- "Módulos src/" --> C{Cloud Storage}
    C --> D[Google Drive]
    C --> E[Dropbox]
    F[GitHub Actions] -- "sync.yml" --> B
    G[Configuración] -- "tools/pesync_setup.bat" --> H[.env]
```

## 🚀 Características

- **Estado basado en la Nube**: El script consulta directamente el almacenamiento remoto al iniciar para determinar qué recursos ya están respaldados.
- **Rotación Automática y Auto-Limpieza**: El script identifica y elimina automáticamente versiones obsoletas en la nube para mantener solo lo más reciente según la configuración.
- **Almacenamiento Seguro**: Integración con múltiples servicios en la nube (Dropbox, Google Drive).
- **Verificación de Integridad (SHA256)**: Cada archivo descargado se valida mediante su firma digital.
- **Feedback Visual (Progreso)**: Muestra barras de progreso detalladas (0-100%) en consola tanto para la descarga de archivos como para la subida a los servicios de nube (Dropbox/Google Drive).
- **Notificaciones Telegram**: Envía mensajes automáticos cuando se completan sincronizaciones exitosas o cuando ocurren errores críticos.

## 📋 Requisitos Previos

- **Python 3.7+**
- Cuenta de almacenamiento en la nube (Dropbox o Google Drive) con acceso a API configurado.

### Instalación

Instala los módulos necesarios:

```bash
pip install -r requirements.txt
```

## ⚙️ Configuración

Para habilitar la sincronización remota, primero selecciona el proveedor de almacenamiento que deseas usar (Dropbox o Google Drive) y luego configura las variables de entorno necesarias.

### Seleccionar Proveedor de Almacenamiento

PESync soporta múltiples proveedores de almacenamiento. Para seleccionar cuál usar, configura la variable `STORAGE_PROVIDER`:

| Valor | Proveedor |
| :--- | :--- |
| `dropbox` | Dropbox (por defecto) |
| `googledrive` | Google Drive |

### Configuración de Credenciales (Local)

Para la ejecución en entorno local, dependiendo del proveedor seleccionado, configura las siguientes variables en tu archivo `.env`:

**Para Dropbox (`STORAGE_PROVIDER=dropbox`):**

- `DROPBOX_APP_KEY`: Llave de acceso de la API.
- `DROPBOX_APP_SECRET`: Secreto de la API.
- `DROPBOX_REFRESH_TOKEN`: Token de actualización de sesión.

**Para Google Drive (`STORAGE_PROVIDER=googledrive`):**

- `GOOGLE_DRIVE_CLIENT_ID`: ID del cliente OAuth.
- `GOOGLE_DRIVE_CLIENT_SECRET`: Secreto del cliente OAuth.
- `GOOGLE_DRIVE_REFRESH_TOKEN`: Token de actualización de sesión.
- `GOOGLE_DRIVE_FOLDER`: *(Opcional)* Nombre de la carpeta de respaldo. Por defecto es `PESync_Backup`.
- `GOOGLE_DRIVE_FOLDER_ID`: *(Opcional)* ID directo de la carpeta en Google Drive. Si se proporciona, tiene prioridad sobre el nombre.
- `BACKUP_COUNT`: *(Opcional)* Cantidad de versiones a mantener de cada componente. Por defecto es `2`.

> [!CAUTION]
> **ENTORNO LOCAL**: El archivo `.env` es **exclusivo para ejecución local**. Nunca lo subas a un repositorio público (ya está mitigado por `.gitignore`). Para entornos automatizados (como GitHub Actions), utiliza los *Secrets* del repositorio.

### Paso 1: Obtener Credenciales

Para obtener estas credenciales, ejecuta el asistente interactivo:

```bash
# Opción 1: Ejecutar archivo .bat (Windows)
.\tools\pesync_setup.bat
.\tools\pesync_test.bat
.\tools\pesync_status.bat
```

### Configuración de Versiones

PESync permite definir cuántas versiones de cada componente mantener en la nube. Puedes configurar esto de dos maneras:

1. **Durante el Setup:** Al ejecutar `python scripts/setup_storage.py`, el asistente te preguntará cuántas versiones deseas mantener (por defecto 2).
2. **Variable de Entorno:** Configura `BACKUP_COUNT` en tu archivo `.env` o como Repository Secret en GitHub.

Si `BACKUP_COUNT` no está definido, el sistema usará el valor predeterminado de **2**.

> [!NOTE]
> El script utiliza un sistema de **rotación basada en la fuente**. Si una versión ya no está entre las `N` más recientes de la fuente oficial, será eliminada automáticamente de la nube para dejar espacio a las nuevas.

### Notificaciones Telegram (opcional)

PESync puede enviarte notificaciones por Telegram para mantenerte informado del estado de las sincronizaciones.

**Notificaciones enviadas:**

- ✅ **Éxito**: Cuando se suben nuevas versiones a la nube (resumen con lista de archivos)
- ❌ **Error**: Cuando ocurre un error crítico (tipo, mensaje y stack trace completo)

**Configuración:**

1. **Obtener el token del bot:**
   - Habla con [@BotFather](https://t.me/botfather) en Telegram
   - Envía `/newbot` y sigue las instrucciones
1. **Obtener el token del bot:**
   - Habla con [@BotFather](https://t.me/botfather) en Telegram
   - Envía `/newbot` y sigue las instrucciones
   - Copia el token (ejemplo: `123456:ABC-DEF...`)

1. **Obtener tu Chat ID:**
   - Habla con [@userinfobot](https://t.me/userinfobot)
   - Te mostrará tu `id` (ejemplo: `987654321`)

1. **Configurar en `.env` (Datos Sensibles)**:

   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=987654321
   ```

1. **Habilitar en `config.yaml`**:

   ```yaml
   notifications:
     telegram_enabled: true
   ```

**Notas:**
- Si `notifications.telegram_enabled: false` o las variables están vacías, no se enviarán notificaciones
- La notificación de éxito solo se envía cuando hay nuevas versiones subidas (no en cada ejecución)
- La notificación de error se envía automáticamente cuando ocurre un error crítico
- Los errores de Telegram se loguean pero no bloquean la ejecución

## 🤖 Automatización (GitHub Actions)

PESync está diseñado para ejecutarse de forma totalmente desatendida mediante GitHub Actions. El flujo de trabajo incluido (`.github/workflows/sync.yml`) se encarga de:

1. **Ejecución Programada**: Por defecto, se ejecuta dos veces al día (00:00 y 12:00 UTC).
2. **Gestión de Secretos**: Utiliza los **GitHub Secrets** para inyectar de forma segura las credenciales de Dropbox o Google Drive.
3. **Eficiencia**: El entorno de ejecución se limpia automáticamente tras cada sesión.

### Cómo configurar la automatización

1. **Workflow Pre-configurado**: El archivo `.github/workflows/sync.yml` ya está incluido en el repositorio. **No necesitas editarlo**.
2. **Configuración de Secrets**: Solo debes añadir las variables de entorno como **Repository Secrets** en GitHub:
    - Ve a tu repositorio > **Settings** > **Secrets and variables** > **Actions**.
    - Haz clic en **New repository secret** por cada variable necesaria.

### Eficiencia y Monitoreo

El sistema divide automáticamente las subidas grandes en bloques fijos de **8MB**. Este valor está optimizado para garantizar alta velocidad con la máxima fluidez en las barras de progreso, además de mantener un consumo de RAM casi nulo.

### Resumen de Uso

1. **Obtener Credenciales:** Ejecuta `.\tools\pesync_setup.bat`.
2. **Validar Conexión:** Ejecuta `.\tools\pesync_test.bat`.
3. **Ejecutar Sincronización:** Ejecuta `iniciar_pesync.bat` (en la raíz) o `python main.py`.

> [!TIP]
> Para una guía detallada de todos los comandos y opciones, consulta nuestra [Guía de Uso CLI](docs/GUI_USO_CLI.md).

## 🛠 Estructura (Arquitectura Organizada)

El proyecto sigue principios de Clean Code, dividiendo responsabilidades de forma clara:

- **Raíz / `main.py`**: Punto de entrada principal y ejecutor diario (`iniciar_pesync.bat`).
- **`src/`**: Motor principal del sistema (CLI, Core, Proveedores, Network, Utils).
- **`docs/`**: Documentación detallada, planes de mejora y [guías de uso](docs/GUI_USO_CLI.md).
- **`tools/`**: Scripts de utilidad para configuración, diagnóstico y consulta de estado.
- **`.agents/`**: Contexto compartido para asistentes de IA (`MEMORIA.md`).
- **`tests/`**: Suite completa de pruebas automatizadas.
- **`scripts/`**: Lógica de configuración heredada.
