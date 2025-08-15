#!/bin/bash
set -euo pipefail  # e exit immediatly if error, -u unset var are error -o pipefail forward errors

printusage() {
    cat >&2 <<EOF
Usage: $(basename "$0") [-o | --ofile] 

Draw the class diagram of TUSIS in the -ofile
Options
  arg1    Destination of the graph def. "../Docs/Archi/all_models.png"
EOF
}

# unbound variable
if [[ -z "$1" ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]];
then
    printusage
    exit 1
fi

if [[ -z "$1" ]];
then
    ofile="../Docs/Archi/all_models.png";
else
    ofile="$1";
fi

python manage.py graph_models\
       --exclude-models "./models_to_exclude.txt" \
       --disable-abstract-fields\
       --rankdir LR\
       --all-applications\
       --group-models\
       --output "$1"
