#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose-preprod.yml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-tusis_preprod}"
TRUTH_DIR="${TRUTH_DIR:-logs/tusis_truth/SmartSchoolDB_20260609/import_ready}"
BATCH_SIZE_STUDENTS="${BATCH_SIZE_STUDENTS:-500}"
BATCH_SIZE_GRADES="${BATCH_SIZE_GRADES:-5000}"
RUN_DB_DRY_RUNS="${RUN_DB_DRY_RUNS:-0}"

log() {
  printf '[truth-preflight] %s\n' "$1"
}

compose() {
  docker-compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
}

run_web() {
  compose run --rm web "$@"
}

log "Running static truth preflight"
run_web python manage.py preflight_truth_import --truth-dir "$TRUTH_DIR"

if [[ "$RUN_DB_DRY_RUNS" != "1" ]]; then
  log "Skipping DB dry-runs; set RUN_DB_DRY_RUNS=1 to validate importer widgets"
  exit 0
fi

log "Running catalog dry-run"
run_web python manage.py import_resources \
  -f "$TRUTH_DIR" \
  --dry-run \
  -r Curriculum \
  -r Course \
  -r CurriCrs \
  -r CurriCrsRequirement

log "Running student dry-run"
run_web python manage.py import_student \
  -f "$TRUTH_DIR/people_full_student.tsv" \
  --dry-run \
  --batch-size "$BATCH_SIZE_STUDENTS"

log "Running course registration dry-run"
run_web python manage.py import_resources \
  -f "$TRUTH_DIR" \
  --dry-run \
  -r LegacyRegistration

log "Running grade dry-run"
run_web python manage.py import_grades \
  -f "$TRUTH_DIR/full_grades.tsv" \
  --dry-run \
  --batch-size "$BATCH_SIZE_GRADES"

log "Running finance payment dry-run"
run_web python manage.py import_finance_payments \
  -f "$TRUTH_DIR/finance_payments.tsv" \
  --dry-run

log "Preflight complete"
