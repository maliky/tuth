#!/usr/bin/env bash
set -e

sudo find . -path "*migrations*" -type f -delete
rm db_test

docker compose -f docker-compose-dev.yml exec web python manage.py dbreset makemigrations

# Uncomment to populate db

# docker compose -f docker-compose-dev.yml exec web python manage.py populate_initial_data
# docker compose -f docker-compose-dev.yml exec web python manage.py import_resources Seed_data/cleaned_tscc.csv

