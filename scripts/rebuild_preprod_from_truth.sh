#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose-preprod.yml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-tusis_preprod}"
TRUTH_DIR="${TRUTH_DIR:-logs/tusis_truth/latest-check/import_ready}"
BATCH_SIZE_STUDENTS="${BATCH_SIZE_STUDENTS:-500}"
BATCH_SIZE_GRADES="${BATCH_SIZE_GRADES:-5000}"
IMPORT_REGISTRATIONS="${IMPORT_REGISTRATIONS:-0}"

log() {
  printf '[truth-rebuild] %s\n' "$1"
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    printf '[truth-rebuild] Missing required truth file: %s\n' "$path" >&2
    exit 1
  fi
}

run_web() {
  compose run --rm web "$@"
}

exec_db() {
  compose exec -T db "$@"
}

compose() {
  docker-compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
}

require_file "$TRUTH_DIR/academic_course.tsv"
require_file "$TRUTH_DIR/academic_curriculum.tsv"
require_file "$TRUTH_DIR/academic_curriculum_course.tsv"
require_file "$TRUTH_DIR/people_full_student.tsv"
require_file "$TRUTH_DIR/registry_registration.tsv"
require_file "$TRUTH_DIR/full_grades.tsv"

log "Dropping preprod containers and named volumes"
compose down -v

log "Building web image"
compose build web

log "Starting database"
compose up -d db

log "Waiting for database"
until exec_db bash -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; do
  sleep 2
done

log "Applying committed migrations"
run_web python manage.py migrate --noinput

log "Creating default states, roles, and test users"
run_web python manage.py create_states
run_web python manage.py load_roles
run_web python manage.py create_test_users

log "Importing truth catalog"
run_web python manage.py import_resources \
  -f "$TRUTH_DIR" \
  -r Curriculum \
  -r Course \
  -r CurriCrs

log "Importing truth students"
run_web python manage.py import_student \
  -f "$TRUTH_DIR/people_full_student.tsv" \
  --batch-size "$BATCH_SIZE_STUDENTS"

if [[ "$IMPORT_REGISTRATIONS" == "1" ]]; then
  log "Importing truth registrations"
  run_web python manage.py import_resources \
    -f "$TRUTH_DIR" \
    -r LegacyRegistration
else
  log "Skipping truth registrations; current export is semester-enrollment shaped"
fi

log "Importing truth grades"
run_web python manage.py import_grades \
  -f "$TRUTH_DIR/full_grades.tsv" \
  --batch-size "$BATCH_SIZE_GRADES"

log "Starting web"
compose up -d --build web

log "Running Django system check"
compose exec -T web python manage.py check

log "Rebuild complete"
log "Finance payments were exported but not imported; no finance truth adapter exists yet."
