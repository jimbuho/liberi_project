# ------------------------------
# Liberi MVP - Dockerfile (Fly.io ready)
# ------------------------------
FROM python:3.12-slim

# Evita archivos pyc y mantiene stdout limpio
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instala dependencias del sistema necesarias para psycopg y Pillow
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia dependencias antes para aprovechar cache de Docker
COPY requirements.txt /app/

# Instala dependencias de Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copia el resto del código
COPY . /app

# Recopila archivos estáticos (usa whitenoise)
RUN python manage.py collectstatic --noinput

# Expone puerto 8080 (Fly.io usa este por defecto)
EXPOSE 8080

# Ejecuta con Gunicorn
CMD ["gunicorn", "liberi_project.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "3"]
