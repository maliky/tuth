#!/usr/bin/env bash
set -euo pipefail  # e exit immediatly if error, -u unset var are error -o pipefail forward errors

printusage() {
    cat >&2 <<EOF
Usage: $(basename "$0") [-d | --dev] [-p | --prod] [-m | --migrate]

Options
  -d, --dev       Run in development mode (loads .env-dev)
  -p, --prod      Run in production mode  (loads .env-prod)
  -m, --migrate   Run 'makemigrations' and 'migrate' before starting
  -h, --help      Show this help
EOF
}

# ---- parse CLI -------------------------------------------------------------
MODE=""
RUN_MIGRATIONS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dev)   MODE=dev ;;
        -p|--prod)  MODE=prod ;;
        -m|--migrate) RUN_MIGRATIONS=true ;;
        -h|--help)  printusage; exit 0 ;;
        *)          echo "Unknown option: $1" >&2; printusage; exit 1 ;;
    esac
    shift
done

if [[ -z "$MODE" ]]; then
    echo "Error: you must specify --dev or --prod" >&2
    printusage
    exit 1
fi

# ---- load environment ------------------------------------------------------
echo "Running in $MODE mode…"
if [[ $MODE == dev ]]; then
    ln -fs .env-dev .env
else
    ln -fs .env-prod .env
fi
export $(grep -v '^#' .env | xargs)  # load variables

# ---- optional migrations ---------------------------------------------------
if $RUN_MIGRATIONS; then
    echo "▶  Running makemigrations and migrate"
    python manage.py makemigrations app
    python manage.py migrate
fi

# ---- static & server -------------------------------------------------------
python manage.py collectstatic --noinput
gunicorn app.wsgi:application --bind 0.0.0.0:8000
