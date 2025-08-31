#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") [OUTPUT_PNG]
Draw the TUSIS class diagram to OUTPUT_PNG (default: ../Docs/Archi/all_models.png)
EOF
}

first="${1-}"  # safe with set -u

if [[ "${first:-}" == "-h" || "${first:-}" == "--help" ]]; then
  usage; exit 0
fi

ofile="${first:-../Docs/Archi/all_models.png}"
mkdir -p "$(dirname "$ofile")"

python manage.py graph_models\
       --exclude-models "./models_to_exclude.txt" \
       --disable-abstract-fields\
       --rankdir LR\
       --all-applications\
       --group-models\
       --output "$ofile"
