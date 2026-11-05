# Homero (`homero`)

> **Motor open-source de publicación editorial, audiolibro neuronal con «Karaoke a la inversa» (Read-Along) y exportación multiformato (Web, EPUB, PDF, MP3) sin salir de GitHub.**

Creado dentro del ecosistema de la Iniciativa Ciudadana Europea **`ECI(2026)000012`** (*Denominación de Origen `.ia`*), **Homero** separa por completo la **herramienta tecnológica** del **contenido literario** (como [*La Odisea del .ia*](https://odisea.deft.work)).

---

## Características principales

1. **Audiolibro automático sin salir de GitHub:**
   - En cada `git push`, Homero convierte los capítulos escritos en Markdown (`.md`) en archivos de audio `.mp3` con voces neuronales naturales en múltiples idiomas (`es`, `en`, `fr`, `it`, `pt`, `el`, `ro`, `hu`).
   - **Modo híbrido (Voz del autor):** Si el autor sube su propia grabación de voz (`audio/<idioma>/<capitulo>-autor.mp3`), Homero respeta la grabación humana y alinea el texto automáticamente.
2. **«Karaoke a la inversa» (Sincronización Read-Along al milisegundo):**
   - Mientras se reproduce el audiolibro, Homero ilumina suavemente la **frase activa** y resalta en tiempo real la **palabra exacta** que se está pronunciando.
   - **Navegación interactiva por clic:** Hacer clic en cualquier frase del capítulo lleva el reproductor de audio instantáneamente a ese segundo exacto.
3. **Exportación abierta a múltiples formatos:**
   - Genera automáticamente el libro electrónico **`.epub`** (compatible con Kindle, Apple Books, Kobo) y el documento maquetado **`.pdf`**, además del audiolibro descargable **`.mp3`**.
4. **Difusión en RRSS y Patrocinio Económico:**
   - Botones integrados para compartir capítulos y citas en **X (Twitter), LinkedIn, WhatsApp, Telegram** o mediante el menú nativo del dispositivo.
   - Bloque de mecenazgo/patrocinio económico configurable (`PayPal / Tarjeta`) y conversión directa hacia causas o iniciativas ciudadanas.

---

## Estructura de un libro compatible con Homero

Cualquier repositorio de libro (por ejemplo, `odisea.deft.work`) solo necesita mantener esta estructura limpia:

```text
mi-libro/
├── libro.yaml                  # Metadatos del libro, idiomas, voces y enlace de patrocinio (PayPal)
├── capitulos/
│   ├── es/
│   │   └── 01-capitulo.md      # Texto del capítulo en Markdown limpio
│   └── en/
│       └── 01-chapter.md
├── audio/                      # Generado por Homero (MP3 + JSON de sincronización karaoke)
├── descargas/                  # Generado por Homero (EPUB + PDF por idioma)
└── .github/workflows/
    └── homero.yml              # GitHub Action que ejecuta Homero automáticamente al hacer push
```

---

## Uso y Ejecución Local

Habiendo descartado la ejecución pesada en runners de GitHub Actions, Homero está diseñado para ejecutarse cómodamente en local antes de hacer `git push`. Puedes usar **Python nativo** o **Docker**.

### 1. Opción A: Con Python (Recomendada si tienes Python 3.10+)

```bash
# 1. Situarse en la carpeta de Homero e instalar dependencias (solo la primera vez)
cd /home/pirate/docker/homero.deft.work
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Solo traducir los capítulos desde el español a los demás idiomas configurados
python3 homero.py translate --book-dir /home/pirate/docker/odisea.deft.work

# 3. Compilar el libro (genera audiolibros MP3, sincronización Karaoke, EPUB, PDF y bundle web)
python3 homero.py build --book-dir /home/pirate/docker/odisea.deft.work

# 4. Traducir y compilar todo en un único comando
python3 homero.py build --book-dir /home/pirate/docker/odisea.deft.work --translate

# 5. Forzar regeneración completa de audios (incluso si no ha cambiado el texto)
python3 homero.py build --book-dir /home/pirate/docker/odisea.deft.work --force-tts
```

---

### 2. Opción B: Con Docker (Sin instalar dependencias en tu máquina)

Si prefieres no gestionar entornos de Python o fuentes del sistema (CJK, árabe, devanagari):

```bash
# 1. Construir la imagen Docker de Homero (solo la primera vez o si modificas homero.py)
cd /home/pirate/docker/homero.deft.work
docker build -t homero:latest .

# 2. Solo traducir los capítulos
docker run --rm -v /home/pirate/docker/odisea.deft.work:/book homero:latest translate

# 3. Compilar el libro (audiolibros, karaoke, epub, pdf y web)
docker run --rm -v /home/pirate/docker/odisea.deft.work:/book homero:latest build

# 4. Traducir y compilar todo de una vez
docker run --rm -v /home/pirate/docker/odisea.deft.work:/book homero:latest build --translate
```

---

## ¿Cómo funciona el flujo de trabajo?

1. **Escribes tu capítulo en español:** Creas o editas `capitulos/es/02-nombre-capitulo.md`.
2. **Generas la traducción:** Ejecutas `python3 homero.py translate` (o con `--translate` al hacer build). Homero detecta los capítulos nuevos o modificados, traduce el texto respetando los formatos Markdown y crea los archivos correspondientes en los idiomas activados en `libro.yaml` (ej. `capitulos/en/...`).
3. **Generas el audiolibro y karaoke:** Homero invoca el motor neuronal de Edge-TTS con la voz configurada para cada idioma en `libro.yaml`, calcula la marca de tiempo exacta de cada palabra, genera el audio `.mp3` y el archivo `.sync.json` para el karaoke interactivo.
4. **Exportas formatos:** Se generan automáticamente las versiones `.epub` y `.pdf` en la carpeta `descargas/` y se actualiza `homero-bundle.js`.
5. **Publicas:** Solo haces `git commit` y `git push` en el repositorio del libro. GitHub Pages actualizará la web instantáneamente en unos segundos.

