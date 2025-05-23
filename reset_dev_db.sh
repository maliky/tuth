#!/usr/bin/env bash
set -e

sudo find . -path "*migrations*" -type f -delete

docker compose -f docker-compose-dev.yml exec web python manage.py reset_db
docker compose -f docker-compose-dev.yml exec web python manage.py makemigrations academics finance people registry shared spaces timetable
docker compose -f docker-compose-dev.yml exec web python manage.py migrate
docker compose -f docker-compose-dev.yml exec web python manage.py populate_initial_data
