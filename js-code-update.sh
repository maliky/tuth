#!/usr/bin/env bash
set -euo pipefail

# Run JS checks/build, collectstatic, and restart the web service.

COMPOSE_FILE="docker-compose-preprod.yml"

log() {
  printf "[js-update] %s\n" "$1"
}

log "Running TypeScript checks"
docker-compose -f "${COMPOSE_FILE}" exec -T js-tools npm run check:ts

log "Building TypeScript"
docker-compose -f "${COMPOSE_FILE}" exec -T js-tools npm run build:ts

log "Collecting static files"
docker-compose -f "${COMPOSE_FILE}" exec -T web python manage.py collectstatic --noinput

log "Restarting web service"
docker-compose -f "${COMPOSE_FILE}" restart web

log "Done"
