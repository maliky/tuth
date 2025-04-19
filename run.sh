#!/bin/bash

printusage() {
    prog=$(basename "$0")
    echo "lance l'application en mode dev ou prod"
    echo "Usage: $prog arg"  >&2
    echo "arg1: -d --dev  -p --prod: Option qui définie l'environement d'execution de l'application"
    echo "" >&2
    echo "Options:" >&2
    echo " -h or --help	  Print this messages" >&2
}

#### Run section

# print.cmd.helper
if [[ -z "$1" ]] || [[ "$1" == '-h' ]]  || [[ "$1" == '--help' ]];
then  # -z if for empty
    printusage
    exit 1
fi

# Check the environment variable FLASK_ENV
if [[ "$1" == "-d" ]] || [[ "$1" == "--dev" ]]; then
    echo "Running in development mode..."
    export PYTHONPATH=$(pwd)
    ln -fs .env-dev .env
elif [[ "$1" == "-p" ]] || [[ "$1" == "--prod" ]]; then
    echo "Running in production mode..."
    ln -fs .env-dev .env
fi

python manage.py migrate
python manage.py collectstatic --noinput
gunicorn app.wsgi:application --bind 0.0.0.0:8000

