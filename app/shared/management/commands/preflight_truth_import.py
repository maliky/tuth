"""Preflight import-ready truth TSV files before destructive database loads."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping, TypeAlias

from django.core.management.base import BaseCommand, CommandError, CommandParser

from app.registry.constants import GRADES_NUM
from app.shared.course_wrangling import parse_course_identity
from app.shared.source_truth.io import read_rows

RowT: TypeAlias = Mapping[str, str]
ErrorT: TypeAlias = tuple[str, int, str, RowT]

REQUIRED_FILES = (
    "academic_curriculum.tsv",
    "academic_course.tsv",
    "academic_curriculum_course.tsv",
    "academic_curriculum_requirement.tsv",
    "people_full_student.tsv",
    "registry_registration.tsv",
    "full_grades.tsv",
    "finance_payments.tsv",
)
VALID_GRADE_CODES = set(GRADES_NUM)
VALID_GRADE_CODES.add("ab")


class Command(BaseCommand):
    """Validate import-ready truth files before long imports."""

    help = "Validate import_ready TSV files before rebuilding preprod."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register preflight options."""
        parser.add_argument(
            "--truth-dir",
            default="logs/tusis_truth/SmartSchoolDB_20260609/import_ready",
            help="Directory containing import-ready TSV files.",
        )
        parser.add_argument(
            "--max-errors",
            type=int,
            default=100,
            help="Maximum errors to collect before failing.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run all file-level preflight checks."""
        truth_dir = Path(str(options["truth_dir"]))
        max_errors_value = options.get("max_errors", 100)
        max_errors = (
            max_errors_value
            if isinstance(max_errors_value, int)
            else int(str(max_errors_value))
        )
        errors: list[ErrorT] = []
        missing = [name for name in REQUIRED_FILES if not (truth_dir / name).exists()]
        for name in missing:
            errors.append((name, 0, "missing_required_file", {}))
        if missing:
            _write_errors(errors)
            raise CommandError(f"Missing required truth files: {', '.join(missing)}")

        _check_courses(truth_dir / "academic_course.tsv", errors, max_errors)
        _check_curriculum_courses(
            truth_dir / "academic_curriculum_course.tsv", errors, max_errors
        )
        _check_students(truth_dir / "people_full_student.tsv", errors, max_errors)
        _check_registrations(truth_dir / "registry_registration.tsv", errors, max_errors)
        _check_grades(truth_dir / "full_grades.tsv", errors, max_errors)
        _check_payments(truth_dir / "finance_payments.tsv", errors, max_errors)

        if errors:
            log_path = _write_errors(errors)
            raise CommandError(
                f"Truth preflight failed with {len(errors)} errors; see {log_path}."
            )
        self.stdout.write(self.style.SUCCESS("Truth preflight passed."))


def _check_courses(path: Path, errors: list[ErrorT], max_errors: int) -> None:
    """Validate course identity rows."""
    for row_number, row in _limited_rows(path, errors, max_errors):
        if parse_course_identity(row.get("course_dept"), row.get("course_no")) is None:
            _add_error(
                errors, path, row_number, "invalid_course_identity", row, max_errors
            )


def _check_curriculum_courses(path: Path, errors: list[ErrorT], max_errors: int) -> None:
    """Validate curriculum-course identity rows."""
    for row_number, row in _limited_rows(path, errors, max_errors):
        if not row.get("curriculum"):
            _add_error(errors, path, row_number, "missing_curriculum", row, max_errors)
        if parse_course_identity(row.get("course_dept"), row.get("course_no")) is None:
            _add_error(
                errors, path, row_number, "invalid_course_identity", row, max_errors
            )


def _check_students(path: Path, errors: list[ErrorT], max_errors: int) -> None:
    """Validate student import rows."""
    seen_ids: set[str] = set()
    seen_usernames: set[str] = set()
    for row_number, row in _limited_rows(path, errors, max_errors):
        student_id = row.get("student_id", "")
        if not student_id:
            _add_error(errors, path, row_number, "missing_student_id", row, max_errors)
        if student_id and student_id in seen_ids:
            _add_error(errors, path, row_number, "duplicate_student_id", row, max_errors)
        seen_ids.add(student_id)
        username = row.get("username", "")
        if username and username in seen_usernames:
            _add_error(errors, path, row_number, "duplicate_username", row, max_errors)
        seen_usernames.add(username)
        birth_date = row.get("birth_date", "")
        if birth_date and not _is_iso_date(birth_date):
            _add_error(errors, path, row_number, "invalid_birth_date", row, max_errors)


def _check_registrations(path: Path, errors: list[ErrorT], max_errors: int) -> None:
    """Validate course registration import rows."""
    for row_number, row in _limited_rows(path, errors, max_errors):
        _check_student_term_course(path, row_number, row, errors, max_errors)


def _check_grades(path: Path, errors: list[ErrorT], max_errors: int) -> None:
    """Validate grade import rows."""
    for row_number, row in _limited_rows(path, errors, max_errors):
        _check_student_term_course(path, row_number, row, errors, max_errors)
        if row.get("grade_code", "").lower() not in VALID_GRADE_CODES:
            _add_error(errors, path, row_number, "invalid_grade_code", row, max_errors)


def _check_payments(path: Path, errors: list[ErrorT], max_errors: int) -> None:
    """Validate payment import rows."""
    for row_number, row in _limited_rows(path, errors, max_errors):
        if not row.get("student_id"):
            _add_error(errors, path, row_number, "missing_student_id", row, max_errors)
        if not row.get("academic_year") or not row.get("semester_no"):
            _add_error(errors, path, row_number, "missing_term", row, max_errors)
        try:
            Decimal(row.get("amount_paid", ""))
        except InvalidOperation:
            _add_error(errors, path, row_number, "invalid_amount_paid", row, max_errors)


def _check_student_term_course(
    path: Path,
    row_number: int,
    row: RowT,
    errors: list[ErrorT],
    max_errors: int,
) -> None:
    """Validate common student/term/course columns."""
    if not row.get("student_id"):
        _add_error(errors, path, row_number, "missing_student_id", row, max_errors)
    if not row.get("academic_year") or not row.get("semester_no"):
        _add_error(errors, path, row_number, "missing_term", row, max_errors)
    if parse_course_identity(row.get("course_dept"), row.get("course_no")) is None:
        _add_error(errors, path, row_number, "invalid_course_identity", row, max_errors)


def _limited_rows(
    path: Path, errors: list[ErrorT], max_errors: int
) -> Iterable[tuple[int, RowT]]:
    """Yield rows until enough errors have been collected."""
    for row_number, row in enumerate(read_rows(path), start=1):
        if len(errors) >= max_errors:
            break
        yield row_number, row


def _is_iso_date(value: str) -> bool:
    """Return whether value parses as YYYY-MM-DD."""
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _add_error(
    errors: list[ErrorT],
    path: Path,
    row_number: int,
    reason: str,
    row: RowT,
    max_errors: int,
) -> None:
    """Append one bounded preflight error."""
    if len(errors) < max_errors:
        errors.append((path.name, row_number, reason, row))


def _write_errors(errors: list[ErrorT]) -> Path:
    """Write preflight errors to a compact CSV report."""
    log_path = Path("logs/import_errors/preflight_truth_import_errors.csv")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "file",
        "row_number",
        "reason",
        "student_id",
        "academic_year",
        "semester_no",
        "course_dept",
        "course_no",
        "grade_code",
        "amount_paid",
    ]
    with log_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for file_name, row_number, reason, row in errors:
            writer.writerow(
                {
                    "file": file_name,
                    "row_number": row_number,
                    "reason": reason,
                    "student_id": row.get("student_id", ""),
                    "academic_year": row.get("academic_year", ""),
                    "semester_no": row.get("semester_no", ""),
                    "course_dept": row.get("course_dept", ""),
                    "course_no": row.get("course_no", ""),
                    "grade_code": row.get("grade_code", ""),
                    "amount_paid": row.get("amount_paid", ""),
                }
            )
    return log_path
