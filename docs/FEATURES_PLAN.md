# Checklist de Features - PESync

Este documento registra el progreso y el plan de mejoras del proyecto. Como Senior Developer, he filtrado las ideas originales para priorizar la **resiliencia, integridad de datos y mantenibilidad**.

---

## ☁️ 1. Proveedores de Almacenamiento
*Añadir más opciones mejora la versatilidad para diferentes tipos de usuarios.*

- [x] **Dropbox** (Implementado: `src/providers/storage_providers.py`)
- [x] **Google Drive** (Implementado: `src/providers/storage_providers.py`)
- [ ] **OneDrive** - *Alta Prioridad:* Es el estándar en Windows.
- [ ] **Soporte genérico S3 (Cloudflare R2, Backblaze)** - *Recomendación Senior:* Más flexible que proveedores individuales.

---

## 🛡️ 2. Resiliencia y Confiabilidad
*Un sistema de backup que falla silenciosamente no sirve. Estos puntos son CRÍTICOS.*

- [x] **Reintentos Automáticos (Exponential Backoff)** (Implementado en `helpers.py`)
- [x] **Verificación de Integridad (SHA256)** (Implementado: Generación de archivos `.sha256`)
- [ ] **Modo Offline** - *Baja Prioridad:* El script debería simplemente terminar con un error elegante si no hay red.

---

## 💻 3. Interfaz y Experiencia (UX)
*Facilitar el uso y monitoreo del sistema.*

- [x] **Barras de Progreso Compartidas** (Implementado con `rich`)
- [x] **Logs Detallados** (Implementado en `logs/`)
- [x] **CLI Interactiva (Typer/Click)** - *Alta Prioridad:* Reemplazar el flujo actual por comandos claros (`pesync sync`, `pesync status`).
- [ ] **Notificaciones Enriquecidas** - *Media Prioridad:* Ya existe Telegram, pero podría incluir imágenes o reportes más visuales.

---

## 📦 4. Gestión de Archivos
*Optimización de recursos y seguridad.*

- [x] **Subida Paralela** (Implementado con `ThreadPoolExecutor`)

---

## ⚙️ 5. Automatización y Configuración
*Eficiencia en la ejecución.*

- [x] **Variables de Entorno (.env)** (Implementado)
- [x] **Configuración YAML** (Implementado en `config.yaml`)
- [ ] **Intervalo de Polling Inteligente** - *Alta Prioridad:* No pollear si no hay cambios detectados (ETags/Last-Modified).
- [ ] **Perfiles de Sincronización** - *Media Prioridad:* Configurar qué categorías se respaldan y con qué frecuencia.

---

## 🛠️ 6. Calidad Técnica (Mantenibilidad)
*El "Core" de un proyecto profesional.*

- [x] **Tests Automatizados (Pytest)** (Suite de 12 tests implementada en `tests/`)
- [ ] **Type Hints Estrictos (Mypy)** - *Alta Prioridad:* Mejora la detección de bugs en tiempo de desarrollo.
- [ ] **Dockerización** - *Media Prioridad:* Facilita la ejecución en NAS o servidores 24/7.

---

## 📅 Hoja de Ruta Sugerida (Top 3 Próximos Pasos)

1. [x] **Refactor de CLI:** Migrar a Typer/Click para una mejor experiencia de usuario y comandos claros.
2. [ ] **Soporte OneDrive / S3:** Ampliar los destinos de backup para mayor versatilidad (Windows Standard).
3. [ ] **Type Hints Estrictos:** Eliminar los `# type: ignore` y asegurar una cobertura total con Mypy.
