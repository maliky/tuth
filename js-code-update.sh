#!/usr/bin/env bash
set -euo pipefail

# Run JS checks/build, collectstatic, and restart the web service.

COMPOSE_FILE="docker-compose-preprod.yml"
MODE="docker"

usage() {
  cat <<EOF
Usage: $(basename "$0") [-d | --dev] [-h | --help]

Options
  -d, --dev   Run natively (no Docker) for local development
  -h, --help  Show this help

Default
  Runs in Docker mode (preprod compose services).
EOF
}

log() {
  printf "[js-update] %s\n" "$1"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dev)
      MODE="dev"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if [[ "${MODE}" == "dev" ]]; then
  log "Running TypeScript checks (native)"
  npm run check:ts

  log "Building TypeScript (native)"
  npm run build:ts

  log "Collecting static files (native)"
  python manage.py collectstatic --noinput

  log "Done (native mode, no Docker restart)"
else
  log "Running TypeScript checks (docker)"
  docker-compose -f "${COMPOSE_FILE}" exec -T js-tools npm run check:ts

  log "Building TypeScript (docker)"
  docker-compose -f "${COMPOSE_FILE}" exec -T js-tools npm run build:ts

  log "Collecting static files (docker)"
  docker-compose -f "${COMPOSE_FILE}" exec -T web python manage.py collectstatic --noinput

  log "Restarting web service (docker)"
  docker-compose -f "${COMPOSE_FILE}" restart web

  log "Done"
fi
