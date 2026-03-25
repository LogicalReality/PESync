# 🚀 Guía de Uso: PESync CLI

Esta guía te ayudará a dominar tanto los accesos directos de Windows como la interfaz de línea de comandos (CLI) avanzada.

---

## 🖱️ Panel de Control (Windows)

He organizado las herramientas en la carpeta `tools/` para mantener tu espacio de trabajo limpio. El ejecutor principal permanece en la raíz para un acceso rápido.

| Comando | Ubicación | Cuándo usarlo |
| :--- | :--- | :--- |
| **`iniciar_pesync.bat`** | **Raíz** | **Uso diario.** Sincroniza todo según tu configuración. |
| `tools/pesync_setup.bat` | `tools/` | **Primer uso** o cuando necesites cambiar de cuenta/proveedor. |
| `tools/pesync_test.bat` | `tools/` | Si notas errores de red o credenciales (Diagnóstico). |
| `tools/pesync_status.bat` | `tools/` | Para ver qué tienes en la nube sin descargar nada. |

---

## 💻 Interfaz de Línea de Comandos (Avanzado)

Si prefieres la terminal, PESync ofrece una interfaz basada en `main.py`.

### 1. Comandos Principales

- **Sincronización:** `python main.py sync` o simplemente `python main.py`
- **Estado Remoto:** `python main.py status`
- **Diagnóstico:** `python main.py test`
- **Configuración:** `python main.py setup`

### 2. Ayuda e Inspección

PESync es autodocumentado. Puedes pedir ayuda en cualquier nivel:

```bash
python main.py --help          # Ayuda general
python main.py sync --help     # Opciones específicas de sincronización
```

---

## 🔄 Flujo de Trabajo Recomendado

Para una experiencia óptima, sigue este orden la primera vez:

1. **Configura:** Ejecuta `tools/pesync_setup.bat` y sigue el enlace de autorización.
2. **Verifica:** Ejecuta `tools/pesync_test.bat` para confirmar que la nube responde.
3. **Ejecuta:** Usa `iniciar_pesync.bat` para tu primer respaldo total.
4. **Monitorea:** Si activaste Telegram, recibirás un resumen al finalizar.

---

## 💡 Tips de "Simplicidad Elegante"

- **Logs Detallados:** Si algo falla, consulta la carpeta `logs/`. Los archivos están organizados por fecha.
- **Entorno Virtual:** Los archivos `.bat` activan automáticamente tu `.venv`. Si usas la terminal manualmente, recuerda activarlo (`.venv\Scripts\activate`).
- **Limpieza de Raíz:** Mantén archivos temporales o descargados fuera de la raíz para evitar el desorden.

---
