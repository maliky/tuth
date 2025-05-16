#/bin/bash

docker compose -f docker-compose-dev.yml exec web bash -c \
  "python manage.py reset_db && \
   python manage.py migrate --noinput && \
   python manage.py populate_initial_data"


 docker compose -f docker-compose-dev.yml down
