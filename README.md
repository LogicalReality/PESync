# Project-E Sync (PESync)

PESync es una herramienta de automatización en Python diseñada para gestionar la sincronización y el respaldo de componentes de entorno. El script automatiza el flujo de búsqueda, descarga y almacenamiento en la nube (Dropbox) de los siguientes recursos:

- **E-Core Environment**: El binario principal del entorno en formato `AppImage` para sistemas compatibles.
- **Licencias del sistema**: Archivos de configuración necesarios para la ejecución del emulador.
- **Actualizaciones del sistema**: Componentes base requeridos para la compatibilidad del emulador.

Esta herramienta está pensada para la gestión personal de respaldos y la automatización de la configuración del entorno de trabajo.

## 🚀 Características

- **Estado basado en Dropbox**: El script consulta directamente el almacenamiento remoto al iniciar para determinar qué recursos ya están respaldados, sin depender de archivos locales.
- **Backup de 2 versiones**: Se mantienen siempre las 2 versiones más recientes de cada categoría (emu, licencias y actualizaciones del sistema).
- **Procesamiento de Datos Dinámicos**: Utiliza `BeautifulSoup` para la identificación y validación de recursos remotos de forma automatizada.
- **Almacenamiento Seguro**: Integración con Dropbox para mantener redundancia de los componentes críticos, soportando subida de archivos de gran tamaño mediante fragmentación.

## 📋 Requisitos Previos

- **Python 3.7+**
- Cuenta de Dropbox con acceso API.

### Instalación

Instala los módulos necesarios:

```bash
pip install -r requirements.txt
```

## ⚙️ Configuración

Para habilitar la sincronización remota, configura las siguientes variables de entorno (por ejemplo, como GitHub Actions Secrets):

| Variable | Propósito |
| :--- | :--- |
| `DROPBOX_APP_KEY` | Llave de acceso de la API de Dropbox. |
| `DROPBOX_APP_SECRET` | Secreto de la API de Dropbox. |
| `DROPBOX_REFRESH_TOKEN` | Token de actualización de sesión. |

Para obtener estas credenciales, ejecuta el asistente de configuración:

```bash
python setup_storage.py
```

## 🏃 Ejecución

Para iniciar el proceso de sincronización:

```bash
python main.py
```

## 🛠 Estructura

- `main.py`: Lógica central del sistema de sincronización.
- `setup_storage.py`: Utilidad de configuración inicial para el almacenamiento en la nube.
- `requirements.txt`: Definición de dependencias.
