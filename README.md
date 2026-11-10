# 🏛️ Homero (`homero.deft.work`)

> **Tu editorial digital y de audiolibros en un solo comando.**  
> Escribe tus capítulos en texto sencillo (Markdown) y **Homero** los traduce automáticamente, graba el audiolibro con voces neuronales naturales, crea el «Karaoke a la inversa» (*Read-Along* palabra por palabra) y maqueta el libro para **Web, Kindle (`.epub`) y `.pdf`**.

Creado dentro del ecosistema de la Iniciativa Ciudadana Europea **`ECI(2026)000012`** (*Denominación de Origen `.IA`*) para impulsar obras vivas y abiertas como [**La Odisea de la .IA** (`odisea.deft.work`)](https://odisea.deft.work).

---

## ⚡ Guía rápida en 3 pasos (Cómo usar la plataforma)

No necesitas conocimientos complejos: **Homero** separa por completo el **motor técnico** (`homero.deft.work`) del **libro** (por ejemplo, `odisea.deft.work`).

### Paso 1: Escribe tu capítulo en español
Dentro de la carpeta `capitulos/es/` de tu libro, crea o edita un archivo `.md` (por ejemplo, `01-mi-capitulo.md`):

```markdown
---
capitulo: 1
titulo: "Título del capítulo"
subtitulo: "Subtítulo opcional"
fecha: "2026"
tiempo_lectura: "5 min"
---

# Capítulo 1: Título del capítulo

Escribe aquí tu historia con formato Markdown normal (negritas, citas, imágenes...).
```

### Paso 2: Traduce y compila todo con 1 solo comando
Ejecuta Homero indicando dónde está la carpeta de tu libro. Homero detectará únicamente lo que haya cambiado (usando su caché inteligente) para terminar en segundos:

```bash
/home/pirate/docker/homero.deft.work/.venv/bin/python3 /home/pirate/docker/homero.deft.work/homero.py build --book-dir /home/pirate/docker/odisea.deft.work --translate
```

### Paso 3: Sube los cambios a GitHub (`git push`)
Entra en la carpeta de tu libro y publica:

```bash
cd /home/pirate/docker/odisea.deft.work
git add .
git commit -m "feat: actualizar capítulos y audiolibros"
git push
```

¡Listo! GitHub Pages actualizará tu web automáticamente.

---

## 🛠️ Tabla de comandos rápidos

| Qué quieres hacer | Comando directo (Python) | Comando equivalente (Docker) |
| :--- | :--- | :--- |
| **Todo en uno** *(Traducir + Audiolibros + EPUB + PDF + Web)* | `python3 homero.py build --book-dir /ruta/libro --translate` | `docker run --rm -v /ruta/libro:/book homero:latest build --translate` |
| **Solo compilar** *(sin volver a traducir)* | `python3 homero.py build --book-dir /ruta/libro` | `docker run --rm -v /ruta/libro:/book homero:latest build` |
| **Solo traducir** *(del español al resto de idiomas)* | `python3 homero.py translate --book-dir /ruta/libro` | `docker run --rm -v /ruta/libro:/book homero:latest translate` |
| **Regenerar todas las voces desde cero** | `python3 homero.py build --book-dir /ruta/libro --force-tts` | `docker run --rm -v /ruta/libro:/book homero:latest build --force-tts` |

---

## ✨ ¿Qué genera Homero automáticamente por ti?

1. **🌍 Traducción automática con caché inteligente (`capitulos/<idioma>/`):**
   - Traduce tus capítulos desde el idioma original (`es`) a todos los idiomas activos en `libro.yaml` (`en`, `fr`, `de`, `it`, `pt`, `el`, `hu`, `hr`, `zh`...), respetando los títulos, enlaces e ilustraciones.
   - Si no has cambiado un capítulo en español, no lo vuelve a traducir.
2. **🎧 Audiolibro neuronal + «Karaoke a la inversa» (`audio/<idioma>/`):**
   - Genera un archivo `.mp3` por capítulo con voces neuronales naturales (`edge-tts`) o respeta tu propia voz grabada si subes `audio/<idioma>/<capitulo>-autor.mp3`.
   - Crea un archivo `.sync.json` con el milisegundo exacto de cada frase y palabra para que el lector web ilumine el texto en vivo mientras suena el audio y permita saltar a cualquier frase haciendo clic.
3. **📚 Ebook `.epub` compatible con Amazon Kindle y Apple Books (`descargas/`):**
   - Empaqueta portada e ilustraciones interiores convirtiendo automáticamente imágenes `.webp` o `.png` a JPEG estándar dentro del manifiesto OPF para que se vean en todos los modelos de Kindle.
4. **📄 Libro maquetado en `.pdf` (`descargas/`):**
   - Genera el PDF completo con portada, índice, ilustraciones centradas, códigos QR ajustados y soporte tipográfico multilingüe (alfabeto latino, griego y chino).
5. **✏️ Enlaces de edición colaborativa en GitHub (`homero-bundle.js`):**
   - Conecta cada capítulo con su archivo fuente en GitHub (`repositorio_url` y `rama_edicion` en `libro.yaml`) para que cualquier lector pueda pulsar **«✏️ Editar en GitHub»** y proponer mejoras en 3 clics.

---

## ⚙️ Configuración de `libro.yaml` (Ejemplo)

En la raíz de tu libro, el archivo `libro.yaml` controla todos los detalles de forma clara:

```yaml
id: "odisea-ia"
titulo: "La Odisea de la .IA"
subtitulo: "Un informático en el laberinto de Bruselas"
autor: "Eloy López"
url: "https://odisea.deft.work"
portada: "img/portada.jpg"

# Repositorio de GitHub para los botones "✏️ Editar en GitHub" de cada capítulo
repositorio_url: "https://github.com/elswork/odisea.deft.work"
rama_edicion: "main"

idioma_defecto: "es"
idiomas:
  es:
    nombre: "Español"
    bandera: "🇪🇸"
    voz_tts: "es-ES-AlvaroNeural"
    activo: true
  en:
    nombre: "English"
    bandera: "🇬🇧"
    voz_tts: "en-US-ChristopherNeural"
    activo: true
```

---

## 📦 Instalación inicial (solo la primera vez)

### Opción A: Con Python 3.10+
```bash
cd /home/pirate/docker/homero.deft.work
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Opción B: Con Docker
```bash
cd /home/pirate/docker/homero.deft.work
docker build -t homero:latest .
```
