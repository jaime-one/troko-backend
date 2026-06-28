# Imagen del backend de Troko para Cloud Run.
FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Instalar dependencias primero para aprovechar la caché de capas de Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código (la llave SA y otros secretos quedan fuera por .dockerignore;
# en Cloud Run se usa la cuenta de servicio adjunta vía ADC, sin archivo de llave).
COPY . .

# Cloud Run inyecta el puerto en $PORT (8080 por defecto). Forma shell para expandirlo.
ENV PORT=8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
