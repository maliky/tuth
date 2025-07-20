#!/bin/bash
# ? Will this load the one in the virtual env
       # --exclude-models Historical*\
       # --exclude-models User\

python manage.py graph_models\
       --exclude-models "./models_to_exclude.txt" \
       --disable-abstract-fields\
       --rankdir LR\
       --all-applications\
       --group-models\
       --output "../Docs/Archi/2507120_all_models.png"
