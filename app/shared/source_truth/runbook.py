"""Runbook writer for manual source-truth imports."""

from __future__ import annotations

from pathlib import Path


def write_import_runbook(output_dir: Path, *, smartschool_dir: Path) -> int:
    """Write a compact manual import runbook and return command count."""
    import_dir = output_dir / "import_ready"
    command_blocks = _command_blocks(output_dir, import_dir, smartschool_dir)
    body = [
        "* TUSIS SmartSchool 20260609 Import Runbook",
        "",
        "This runbook intentionally prepares and lists imports only.",
        "Run these commands manually; the source-truth build itself does not mutate TUSIS.",
        "",
        "** Why registry_semester_enrollment.tsv is audit-only",
        "",
        "=UM_Registrations= records one row per student semester enrollment/clearance.",
        "It does not identify the individual course, course number, section, or credit row ",
        "required by the existing =LegacyRegistration= importer. Course registrations come ",
        "from =UM_StudentsCourses= instead. Importing =UM_Registrations= as registrations ",
        "would create fake course registrations or duplicate semester state, so it is kept ",
        "as =registry_semester_enrollment.tsv= for audit/reconciliation only.",
        "",
        "** Resume without reloading completed tables",
        "",
        "Use =scripts/rebuild_preprod_from_truth.sh= for operational reloads. If a later ",
        "stage fails after earlier tables loaded correctly, keep the database volume and ",
        "resume with =RUN_PREFLIGHT=0 START_AT=<stage>= instead of rerunning reset/imports.",
        "Useful stages are =catalog=, =students=, =registrations=, =grades=, =finance=, ",
        "=web=, =check=, and =validate=. For a student import failure after fixing the ",
        "source file, add =STUDENT_START_ROW=<row>= with =START_AT=students=.",
        "",
        "** Commands",
        "",
    ]
    for index, command in enumerate(command_blocks, start=1):
        body.extend((f"*** {index}", "", "#+begin_src bash", command, "#+end_src", ""))
    path = output_dir / "IMPORT_RUNBOOK.org"
    path.write_text("\n".join(body), encoding="utf-8")
    return len(command_blocks)


def _command_blocks(
    output_dir: Path, import_dir: Path, smartschool_dir: Path
) -> tuple[str, ...]:
    """Return the five command groups used for the manual import."""
    compose = (
        "COMPOSE_PROJECT_NAME=tusis_preprod docker-compose -f docker-compose-preprod.yml"
    )
    build_truth = (
        "python scripts/extract_tucurricula_imports.py "
        "--source-root ~/tucurricula --output-dir data/tucurricula_import && "
        "docker-compose -f docker-compose-preprod.yml run --rm web "
        "python manage.py build_tusis_truth "
        f"--smartschool-dir {smartschool_dir} --output-dir {output_dir}"
    )
    preflight = (
        f"TRUTH_DIR={import_dir} COMPOSE_PROJECT_NAME=tusis_preprod "
        "./scripts/preflight_preprod_truth.sh"
    )
    reset_standard = (
        f"{compose} down -v && {compose} up -d db && "
        f"until {compose} exec -T db bash -lc "
        '\'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"\'; '
        f"do sleep 2; done && {compose} run --rm web bash -lc "
        "'python manage.py migrate --noinput && python manage.py create_states && "
        "python manage.py load_roles && python manage.py create_test_users'"
    )
    import_catalog_students = (
        f"{compose} run --rm web python manage.py import_resources -f {import_dir} "
        "-r Curriculum -r Course -r CurriCrs -r CurriCrsRequirement && "
        f"{compose} run --rm web python manage.py import_student "
        f"-f {import_dir / 'people_full_student.tsv'} --batch-size 500"
    )
    import_registry_grades_finance = (
        f"{compose} run --rm web bash -lc "
        f"'python manage.py import_resources -f {import_dir} -r LegacyRegistration && "
        f"python manage.py import_grades -f {import_dir / 'full_grades.tsv'} "
        f"--batch-size 5000 && python manage.py import_finance_payments "
        f"-f {import_dir / 'finance_payments.tsv'} && "
        "python manage.py backfill_registration_invoices --academic-year 25-26 "
        "--semester-number 3 --include-existing --write-lab-report "
        "logs/course_fee_policy/25-26_sem3_lab_candidates.tsv' && "
        f"{compose} up -d web && "
        f"{compose} exec -T web python manage.py check && "
        f"{compose} exec -T web python manage.py validate_preprod_truth "
        f"--truth-dir {import_dir}"
    )
    return (
        build_truth,
        preflight,
        reset_standard,
        import_catalog_students,
        import_registry_grades_finance,
    )


__all__ = ["write_import_runbook"]
