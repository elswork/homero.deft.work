# ==============================================================================
# Dockerfile para HOMERO — Motor de Publicación Editorial, Audiolibros y Karaoke
# ==============================================================================
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Homero"
LABEL org.opencontainers.image.description="Motor de libros interactivos, audiolibros neuronales Edge-TTS, Karaoke inverso, EPUB y PDF"
LABEL org.opencontainers.image.source="https://github.com/elswork/homero.deft.work"
LABEL org.opencontainers.image.authors="Eloy López Sánchez <elswork@gmail.com>"

# Fuentes TrueType para PDF y utilidades básicas
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    fonts-noto-core \
    fonts-noto-cjk \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente de Homero
COPY homero.py .

# Directorio de trabajo para montar el repositorio del libro
WORKDIR /book

ENTRYPOINT ["python3", "/app/homero.py"]
CMD ["build", "--book-dir", "/book", "--translate"]

