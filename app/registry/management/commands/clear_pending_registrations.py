"""Clear registrations that still show Pending Payment."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TypeAlias, TypedDict

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.registry.models.status_types import RegistrationStatus
from app.timetable.models.semester import Semester
from app.timetable.utils import normalize_academic_year

DEFAULT_LOG_DIR = Path("logs/registry_reconciliation")
RegistrationQueryT: TypeAlias = QuerySet[Registration]


class AuditRowT(TypedDict):
    """CSV audit row for one pending-payment registration."""

    registration_id: str
    student_id: str
    student_db_id: str
    username: str
    academic_year: str
    semester_no: str
    section_id: str
    course_code: str
    course_title: str
    credits: str
    fee: str
    previous_status: str
    new_status: str
    action: str


class Command(BaseCommand):
    """Clear pending-payment registration status rows with an audit log."""

    help = (
        "Clear Registration rows whose status is Pending Payment. Dry-run is the "
        "default; pass --apply to write status=cleared."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument(
            "--student",
            default="",
            help="Optional student username, student_id, or database id.",
        )
        parser.add_argument(
            "--semester-id",
            type=int,
            default=None,
            help="Limit to one semester database id.",
        )
        parser.add_argument(
            "--academic-year",
            default="",
            help="Limit to an academic year code such as 25-26 or 2025/2026.",
        )
        parser.add_argument(
            "--semester-number",
            type=int,
            default=None,
            help="Limit to a semester number within --academic-year.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Bulk update batch size.",
        )
        parser.add_argument(
            "--log-path",
            default="",
            help="Optional CSV audit path. Defaults under logs/registry_reconciliation.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually clear the matching pending-payment registrations.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run pending-payment registration clearance."""
        apply_changes = bool(options["apply"])
        student_token = str(options["student"]).strip()
        student_id = _resolve_student_id(student_token) if student_token else None
        semester_id = _resolve_semester_id(
            semester_id=options.get("semester_id"),
            academic_year=str(options.get("academic_year", "")).strip(),
            semester_number=options.get("semester_number"),
        )
        batch_size = _clean_batch_size(options.get("batch_size"))
        log_path = _resolve_log_path(str(options["log_path"]).strip())
        registrations = _pending_registration_qs(
            student_id=student_id,
            semester_id=semester_id,
        )
        audit_rows = _audit_rows(registrations, apply_changes=apply_changes)
        _write_audit_rows(log_path, audit_rows)
        updated = _clear_registrations(registrations, batch_size) if apply_changes else 0
        mode = "Applied" if apply_changes else "Dry-run"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} pending-registration clearance: {len(audit_rows)} matched, "
                f"{updated} cleared. Audit: {log_path}"
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


def _resolve_semester_id(
    *,
    semester_id: object,
    academic_year: str,
    semester_number: object,
) -> int | None:
    """Resolve direct or academic-year/semester-number filters."""
    if isinstance(semester_id, int):
        return semester_id
    if not academic_year and semester_number is None:
        return None
    if not academic_year or not isinstance(semester_number, int):
        raise CommandError("--academic-year and --semester-number must be used together.")
    year_code = normalize_academic_year(academic_year)
    semester = Semester.objects.filter(
        academic_year__code=year_code,
        number=semester_number,
    ).first()
    if semester is None:
        raise CommandError(f"Semester not found: {year_code} Sem{semester_number}")
    return int(semester.id)


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
    return DEFAULT_LOG_DIR / f"pending_registration_clearance_{timestamp}.csv"


def _pending_registration_qs(
    *,
    student_id: int | None = None,
    semester_id: int | None = None,
) -> RegistrationQueryT:
    """Return registrations still labeled Pending Payment."""
    registrations = Registration.objects.filter(status_id="pending").select_related(
        "student",
        "student__user",
        "section",
        "section__semester",
        "section__semester__academic_year",
        "section__curriculum_course",
        "section__curriculum_course__course",
        "section__curriculum_course__credit_hours",
    )
    if student_id is not None:
        registrations = registrations.filter(student_id=student_id)
    if semester_id is not None:
        registrations = registrations.filter(section__semester_id=semester_id)
    return registrations.order_by(
        "section__semester__academic_year__start_date",
        "section__semester__number",
        "student__student_id",
        "section__curriculum_course__course__short_code",
        "id",
    )


def _audit_rows(
    registrations: RegistrationQueryT,
    *,
    apply_changes: bool,
) -> list[AuditRowT]:
    """Build audit rows before any status mutation."""
    rows: list[AuditRowT] = []
    action = "cleared" if apply_changes else "would_clear"
    for registration in registrations.iterator(chunk_size=5000):
        section = registration.section
        semester = section.semester
        curriculum_course = section.curriculum_course
        course = curriculum_course.course
        rows.append(
            {
                "registration_id": str(registration.id),
                "student_id": registration.student.student_id,
                "student_db_id": str(registration.student_id),
                "username": registration.student.user.username,
                "academic_year": semester.academic_year.code,
                "semester_no": str(semester.number),
                "section_id": str(section.id),
                "course_code": course.short_code or course.code,
                "course_title": course.title or "",
                "credits": str(curriculum_course.credit_hours_id),
                "fee": str(section.fee_total_amount()),
                "previous_status": "pending",
                "new_status": "cleared",
                "action": action,
            }
        )
    return rows


def _write_audit_rows(path: Path, rows: list[AuditRowT]) -> None:
    """Write registration clearance audit rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(AuditRowT.__annotations__)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _clear_registrations(registrations: RegistrationQueryT, batch_size: int) -> int:
    """Bulk update pending registrations to the canonical cleared status."""
    cleared_status = RegistrationStatus.cleared()
    ids = list(registrations.values_list("id", flat=True))
    updated = 0
    with transaction.atomic():
        for index in range(0, len(ids), batch_size):
            batch = ids[index : index + batch_size]
            updated += Registration.objects.filter(
                id__in=batch,
                status_id="pending",
            ).update(status=cleared_status)
    return updated


__all__ = ["Command"]
