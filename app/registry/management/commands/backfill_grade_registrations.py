"""Backfill historical registrations inferred from imported grade rows."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TypedDict

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q
from django.utils import timezone

from app.people.models.student import Student
from app.registry.grade_registration_reconciliation import (
    GradeRegistrationPairT,
    ensure_grade_registration_pairs,
    student_credit_gaps,
)
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration

DEFAULT_LOG_DIR = Path("logs/registry_reconciliation")


class AuditRowT(TypedDict):
    """CSV audit row for one reconstructed registration."""

    student_id: str
    student_db_id: str
    section_id: str
    academic_year: str
    semester_no: str
    course_code: str
    course_title: str
    grade_code: str
    action: str


class Command(BaseCommand):
    """Create missing registrations for sections proven by grade rows."""

    help = (
        "Backfill missing historical Registration rows from imported Grade rows. "
        "Dry-run is the default; pass --apply to mutate data."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument(
            "--student",
            default="",
            help="Optional student username, student_id, or database id.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Bulk create batch size.",
        )
        parser.add_argument(
            "--log-path",
            default="",
            help="Optional CSV audit path. Defaults under logs/registry_reconciliation.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report missing registrations without writing them.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually create missing cleared registration rows.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run grade-backed registration repair."""
        apply_changes = bool(options["apply"])
        if apply_changes and bool(options["dry_run"]):
            raise CommandError("Choose either --dry-run or --apply, not both.")
        student_token = str(options["student"]).strip()
        student_id = _resolve_student_id(student_token) if student_token else None
        batch_size = _clean_batch_size(options.get("batch_size"))
        log_path = _resolve_log_path(str(options["log_path"]).strip())

        audit_rows = _missing_registration_audit_rows(student_id=student_id)
        pairs = [
            (int(row["student_db_id"]), int(row["section_id"])) for row in audit_rows
        ]
        summary = ensure_grade_registration_pairs(
            pairs,
            batch_size=batch_size,
            dry_run=not apply_changes,
        )
        action = "created" if apply_changes else "would_create"
        for row in audit_rows:
            row["action"] = action
        _write_audit_rows(log_path, audit_rows)
        gaps = student_credit_gaps(student_id=student_id, limit=10)
        mode = "Applied" if apply_changes else "Dry-run"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} grade-registration backfill: {summary.created} created, "
                f"{summary.would_create} would-create, {summary.existing} existing, "
                f"{len(gaps)} remaining credit-gap sample(s). Audit: {log_path}"
            )
        )


def _resolve_student_id(token: str) -> int:
    """Resolve a student selector to a database id."""
    query = Q(user__username=token) | Q(username=token) | Q(student_id=token)
    if token.isdigit():
        query |= Q(id=int(token))
    student = Student.objects.filter(query).order_by("id").first()
    if student is None:
        raise CommandError(f"Student not found: {token}")
    return int(student.id)


def _clean_batch_size(value: object) -> int:
    """Return a positive batch size from a command option value."""
    try:
        batch_size = int(str(value or "5000"))
    except ValueError:
        return 5000
    return max(batch_size, 1)


def _resolve_log_path(raw_path: str) -> Path:
    """Return the audit CSV path for this run."""
    if raw_path:
        return Path(raw_path)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_LOG_DIR / f"grade_registration_backfill_{timestamp}.csv"


def _missing_registration_audit_rows(
    *,
    student_id: int | None = None,
) -> list[AuditRowT]:
    """Return audit rows for grade-backed registrations that are absent."""
    registered_credits = _existing_registration_course_credits(student_id=student_id)
    selected: dict[tuple[int, int], tuple[int, AuditRowT]] = {}
    grades = Grade.objects.select_related(
        "student",
        "section__semester__academic_year",
        "section__curriculum_course__course",
        "value",
    ).order_by("student_id", "section_id", "id")
    if student_id is not None:
        grades = grades.filter(student_id=student_id)
    for grade in grades.iterator(chunk_size=5000):
        course_key = (
            int(grade.student_id),
            int(grade.section.curriculum_course.course_id),
        )
        grade_credits = int(grade.section.curriculum_course.credit_hours_id or 0)
        if registered_credits.get(course_key, 0) >= grade_credits:
            continue
        current = selected.get(course_key)
        if current is None or grade_credits > current[0]:
            selected[course_key] = (grade_credits, _audit_row(grade))
    return [row for _credits, row in selected.values()]


def _existing_registration_course_credits(
    *,
    student_id: int | None = None,
) -> dict[tuple[int, int], int]:
    """Return registered credits keyed by student and course."""
    registrations = Registration.objects.all()
    if student_id is not None:
        registrations = registrations.filter(student_id=student_id)
    totals: dict[tuple[int, int], int] = {}
    rows = registrations.values_list(
        "student_id",
        "section__curriculum_course__course_id",
        "section__curriculum_course__credit_hours_id",
    )
    for student_id_value, course_id, credit_hours in rows:
        key = (int(student_id_value), int(course_id))
        totals[key] = totals.get(key, 0) + int(credit_hours or 0)
    return totals


def _audit_row(grade: Grade) -> AuditRowT:
    """Build a CSV audit row from one grade row."""
    section = grade.section
    course = section.curriculum_course.course
    semester = section.semester
    return {
        "student_id": grade.student.student_id,
        "student_db_id": str(grade.student_id),
        "section_id": str(grade.section_id),
        "academic_year": semester.academic_year.code,
        "semester_no": str(semester.number),
        "course_code": course.short_code or course.code,
        "course_title": course.title or "",
        "grade_code": grade.value.code if grade.value else "",
        "action": "",
    }


def _write_audit_rows(path: Path, rows: list[AuditRowT]) -> None:
    """Write grade-registration reconciliation audit rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(AuditRowT.__annotations__)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


__all__ = ["Command"]
