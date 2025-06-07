#!/usr/bin/env bash
set -euo pipefail  # e exit immediatly if error, -u unset var are error -o pipefail forward errors

printusage() {
    cat >&2 <<EOF
Usage: $(basename "$0") [-d | --dev] [-p | --prod] [-m | --migrate]

Options
  -d, --dev       Run in development mode (loads .env-dev)
  -p, --prod      Run in production mode  (loads .env-prod)
  -t, --test      Run in test mode (loads .env-test)
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
        -t|--test)  MODE=test ;;        
        -m|--migrate) RUN_MIGRATIONS=true ;;
        -h|--help)  printusage; exit 0 ;;
        *)          echo "Unknown option: $1" >&2; printusage; exit 1 ;;
    esac
    shift
done

if [[ -z "$MODE" ]]; then
    MODE="test"
fi

# ---- load environment ------------------------------------------------------
echo ">> Running in $MODE mode…<<"
if [[ $MODE == dev ]]; then
    ln -fs .env-dev .env
elif [[ $MODE == prod ]]; then
    ln -fs .env-prod .env
elif [[ $MODE == test ]]; then
    ln -fs env-test .env
fi
export $(grep -v '^#' .env | xargs)  # load variables

# ---- optional migrations ---------------------------------------------------
if $RUN_MIGRATIONS; then
    # we start from fresh db
    if [[ $MODE == dev ]]; then
        python manage reset_db
    elif [[ $MODE == test ]]; then
        sudo find . -path "*migrations*" -type f -delete
        sudo find . -type d -name "__pycache__" -exec rm -rf {} +        
        rm -f $DJANGO_DB_NAME
    fi
    echo ">> Running makemigrations and migrate <<"
    # should makemigraton for all discovered apps
    python manage.py makemigrations
    python manage.py makemigrations registry spaces academics timetable people finance shared
    python manage.py migrate 
fi

# ---- static & server -------------------------------------------------------
python manage.py collectstatic --noinput

if [[ $MODE == dev ||  $MODE == prod ]]; then
    echo ">> Running gunicorn server <<"
    gunicorn app.wsgi:application --bind 0.0.0.0:8000
elif [[ $MODE == test ]]; then
    echo ">> Running local server <<"    
    python manage.py runserver
fi

