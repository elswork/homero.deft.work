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

## Uso rápido

```bash
# Instalar dependencias ligeras
pip install -r requirements.txt

# Compilar un libro (genera web, audiolibros, sincronización karaoke, EPUB y PDF)
python3 homero.py build --book-dir /ruta/a/odisea.deft.work
```

