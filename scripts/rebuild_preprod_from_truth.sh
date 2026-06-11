#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose-preprod.yml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-tusis_preprod}"
TRUTH_DIR="${TRUTH_DIR:-logs/tusis_truth/latest-check/import_ready}"
BATCH_SIZE_STUDENTS="${BATCH_SIZE_STUDENTS:-500}"
BATCH_SIZE_GRADES="${BATCH_SIZE_GRADES:-5000}"
IMPORT_REGISTRATIONS="${IMPORT_REGISTRATIONS:-1}"
IMPORT_FINANCE_PAYMENTS="${IMPORT_FINANCE_PAYMENTS:-1}"
BACKFILL_REGISTRATION_INVOICES="${BACKFILL_REGISTRATION_INVOICES:-1}"
FEE_BACKFILL_ACADEMIC_YEAR="${FEE_BACKFILL_ACADEMIC_YEAR:-25-26}"
FEE_BACKFILL_SEMESTER_NUMBER="${FEE_BACKFILL_SEMESTER_NUMBER:-3}"
FEE_LAB_REPORT="${FEE_LAB_REPORT:-logs/course_fee_policy/25-26_sem3_lab_candidates.tsv}"
RUN_PREFLIGHT="${RUN_PREFLIGHT:-1}"
START_AT="${START_AT:-preflight}"
STUDENT_START_ROW="${STUDENT_START_ROW:-1}"

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

stage_index() {
  case "$1" in
    preflight) echo 10 ;;
    reset) echo 20 ;;
    build) echo 30 ;;
    db) echo 40 ;;
    migrate) echo 50 ;;
    defaults) echo 60 ;;
    catalog) echo 70 ;;
    students) echo 80 ;;
    registrations) echo 90 ;;
    grades) echo 100 ;;
    finance) echo 110 ;;
    web) echo 120 ;;
    check) echo 130 ;;
    validate) echo 140 ;;
    *)
      printf '[truth-rebuild] Unknown START_AT stage: %s\n' "$1" >&2
      exit 2
      ;;
  esac
}

START_INDEX="$(stage_index "$START_AT")"

should_run() {
  [[ "$(stage_index "$1")" -ge "$START_INDEX" ]]
}

require_file "$TRUTH_DIR/academic_course.tsv"
require_file "$TRUTH_DIR/academic_curriculum.tsv"
require_file "$TRUTH_DIR/academic_curriculum_course.tsv"
require_file "$TRUTH_DIR/academic_curriculum_requirement.tsv"
require_file "$TRUTH_DIR/people_full_student.tsv"
require_file "$TRUTH_DIR/registry_registration.tsv"
require_file "$TRUTH_DIR/full_grades.tsv"
require_file "$TRUTH_DIR/finance_payments.tsv"

if [[ "$RUN_PREFLIGHT" == "1" ]] && should_run preflight; then
  log "Running static truth preflight"
  run_web python manage.py preflight_truth_import --truth-dir "$TRUTH_DIR"
fi

if should_run reset; then
  log "Dropping preprod containers and named volumes"
  compose down -v
fi

if should_run build; then
  log "Building web image"
  compose build web
fi

if should_run db; then
  log "Starting database"
  compose up -d db

  log "Waiting for database"
  until exec_db bash -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; do
    sleep 2
  done
fi

if should_run migrate; then
  log "Applying committed migrations"
  run_web python manage.py migrate --noinput
fi

if should_run defaults; then
  log "Creating default states, roles, and test users"
  run_web python manage.py create_states
  run_web python manage.py load_roles
  run_web python manage.py create_test_users
fi

if should_run catalog; then
  log "Importing truth catalog"
  run_web python manage.py import_resources \
    -f "$TRUTH_DIR" \
    -r Curriculum \
    -r Course \
    -r CurriCrs \
    -r CurriCrsRequirement
fi

if should_run students; then
  log "Importing truth students"
  run_web python manage.py import_student \
    -f "$TRUTH_DIR/people_full_student.tsv" \
    --batch-size "$BATCH_SIZE_STUDENTS" \
    --start-row "$STUDENT_START_ROW"
fi

if should_run registrations; then
  if [[ "$IMPORT_REGISTRATIONS" == "1" ]]; then
    log "Importing truth course registrations"
    run_web python manage.py import_resources \
      -f "$TRUTH_DIR" \
      -r LegacyRegistration
  else
    log "Skipping truth course registrations; set IMPORT_REGISTRATIONS=1 after preflight"
  fi
fi

if should_run grades; then
  log "Importing truth grades"
  run_web python manage.py import_grades \
    -f "$TRUTH_DIR/full_grades.tsv" \
    --batch-size "$BATCH_SIZE_GRADES"
fi

if should_run finance; then
  if [[ "$IMPORT_FINANCE_PAYMENTS" == "1" ]]; then
    log "Importing truth finance payments"
    run_web python manage.py import_finance_payments \
      -f "$TRUTH_DIR/finance_payments.tsv"
  else
    log "Skipping truth finance payments; set IMPORT_FINANCE_PAYMENTS=1 after preflight"
  fi

  if [[ "$BACKFILL_REGISTRATION_INVOICES" == "1" ]]; then
    log "Backfilling registration invoices for $FEE_BACKFILL_ACADEMIC_YEAR Sem$FEE_BACKFILL_SEMESTER_NUMBER"
    run_web python manage.py backfill_registration_invoices \
      --academic-year "$FEE_BACKFILL_ACADEMIC_YEAR" \
      --semester-number "$FEE_BACKFILL_SEMESTER_NUMBER" \
      --include-existing \
      --write-lab-report "$FEE_LAB_REPORT"
  else
    log "Skipping registration invoice backfill"
  fi
fi

if should_run web; then
  log "Starting web"
  compose up -d web
fi

if should_run check; then
  log "Running Django system check"
  compose exec -T web python manage.py check
fi

if should_run validate; then
  log "Validating loaded truth counts"
  compose exec -T web python manage.py validate_preprod_truth --truth-dir "$TRUTH_DIR"
fi

log "Rebuild complete"
