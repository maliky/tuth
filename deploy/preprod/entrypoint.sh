#!/usr/bin/env bash
set -euo pipefail

log() {
  printf "[preprod] %s\n" "$1"
}

log "Waiting for the database and applying migrations"
until python manage.py migrate --noinput; do
  log "Database not ready, retrying in 3s…"
  sleep 3
done

log "Collecting static assets"
python manage.py collectstatic --noinput

log "Starting Gunicorn"
mkdir -p /run
exec gunicorn app.wsgi:application \
    --bind unix:/run/gunicorn.sock \
    --workers "${GUNICORN_WORKERS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
