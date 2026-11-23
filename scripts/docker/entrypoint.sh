#!/bin/sh
set -eu

if [ "$(id -u)" = "0" ]; then
  mkdir -p /var/www/static /app/media /var/lib/celery
  chown -R app:app /var/www/static /app/media /var/lib/celery
  exec runuser -u app -- "$0" "$@"
fi

if [ -n "${POSTGRES_HOST:-}" ]; then
  echo "Waiting for Postgres at ${POSTGRES_HOST}..."
  until python - <<'PY'
import os, sys
import psycopg
try:
    psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ.get("POSTGRES_DB", "reka"),
        user=os.environ.get("POSTGRES_USER", "reka"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        connect_timeout=3,
    ).close()
except Exception:
    sys.exit(1)
PY
  do
    sleep 1
  done
fi

if [ "${RUN_MIGRATIONS:-}" = "true" ]; then
  python manage.py migrate --noinput
fi

if [ "${SEED_ON_START:-}" = "true" ]; then
  python manage.py seed_northbound
fi

exec "$@"
