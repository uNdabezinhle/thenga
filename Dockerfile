FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/
COPY frontend/ /frontend/
COPY scripts/docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && useradd -m app \
    && mkdir -p /app/media /var/www/static /var/lib/celery \
    && chown -R app:app /app /frontend /var/www/static /var/lib/celery

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "reka.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
