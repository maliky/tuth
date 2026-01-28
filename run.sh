#!/usr/bin/env bash
set -euo pipefail  # e exit immediatly if error, -u unset var are error -o pipefail forward errors

printusage() {
    cat >&2 <<EOF
Usage: $(basename "$0") [-d | --dev] [-p | --preprod]

Options
  -d, --dev       Run in development mode (loads .env-dev)
  -p, --preprod   Run in pre-production mode  (loads .env-preprod)
  -h, --help      Show this help
EOF
}

# ---- parse CLI -------------------------------------------------------------
MODE=""
RUN_MIGRATIONS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dev)   MODE=dev ;;
        -p|--preprod)  MODE=preprod ;;
        -h|--help)  printusage; exit 0 ;;
        *)          echo "Unknown option: $1" >&2; printusage; exit 1 ;;
    esac
    shift
done

if [[ -z "${MODE}" ]]; then
  echo "Error: choose --dev or --preprod" >&2
  printusage
  exit 1
fi
# ---- load environment ------------------------------------------------------
echo ">> Running in ${MODE} mode…<<"

ENV_FILE=".env-${MODE}"
[[ -f "${ENV_FILE}" ]] || { echo "Missing ${ENV_FILE}" >&2; exit 1; }

ln -fs "${ENV_FILE}" .env

set -a
# shellcheck disable=SC1091
source .env
set +a

# ---- static & server -------------------------------------------------------
python manage.py collectstatic --noinput

if [[ $MODE == dev ]]; then
    echo ">> Running server <<"
    python manage.py runserver
elif [[ $MODE == preprod ]]; then
    echo ">> Running restarting the docker <<"    
    docker-compose -f docker-compose-preprod.yml restart web
fi

