#!/usr/bin/env bash
set -e

sudo find . -path "*migrations*" -type f -delete
rm testdb

#docker compose -f docker-compose-dev.yml exec web python manage.py reset_db
docker compose -f docker-compose-dev.yml exec web python manage.py makemigrations 
docker compose -f docker-compose-dev.yml exec web python manage.py migrate
# Uncomment the following if you do not have acess to the Seed_data
# docker compose -f docker-compose-dev.yml exec web python manage.py populate_initial_data
docker compose -f docker-compose-dev.yml exec web python manage.py import_resources Seed_data/cleaned_tscc.csv

