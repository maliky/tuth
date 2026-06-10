"""Write current TUSIS data snapshots before curriculum reconciliation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.academics.current_records_snapshot import (
    iter_course_invoice_rows,
    iter_grade_rows,
    iter_payment_rows,
    iter_registration_rows,
    iter_section_rows,
    iter_semester_invoice_rows,
    iter_student_curriculum_enrollment_rows,
)
from app.academics.current_usage import (
    CurrentUsageT,
    iter_current_course_rows,
    iter_current_curriculum_course_rows,
    iter_current_curriculum_rows,
    load_current_usage,
)
from app.academics.reconciliation_io import RowT, write_tsv

SnapshotSpecT = tuple[str, tuple[str, ...], Iterable[RowT]]


@dataclass(frozen=True)
class SnapshotSummaryT:
    """Summary of current-data snapshot files."""

    output_dir: Path
    counts: dict[str, int]


def _snapshot_specs(usage: CurrentUsageT) -> tuple[SnapshotSpecT, ...]:
    """Return filename, headers, and row iterators for current-data exports."""
    return (
        (
            "current_courses.tsv",
            (
                "course_id",
                "college_code",
                "course_dept",
                "course_no",
                "course_key",
                "course_code",
                "short_code",
                "course_title",
                "description",
                "section_count",
                "registration_count",
                "grade_count",
                "course_invoice_count",
                "usage_total",
            ),
            iter_current_course_rows(usage),
        ),
        (
            "current_curricula.tsv",
            (
                "curriculum_id",
                "college_code",
                "curriculum",
                "curriculum_key",
                "long_name",
                "status",
                "is_active",
                "student_enrollment_count",
                "section_count",
                "registration_count",
                "grade_count",
                "course_invoice_count",
                "usage_total",
            ),
            iter_current_curriculum_rows(usage),
        ),
        (
            "current_curriculum_courses.tsv",
            (
                "curriculum_course_id",
                "curriculum_id",
                "course_id",
                "curriculum",
                "curriculum_key",
                "course_key",
                "college_code",
                "course_college_code",
                "course_dept",
                "course_no",
                "course_title",
                "credit_hours",
                "year_number",
                "semester_number",
                "level_number",
                "is_required",
                "is_elective",
                "section_count",
                "registration_count",
                "grade_count",
                "course_invoice_count",
                "usage_total",
            ),
            iter_current_curriculum_course_rows(usage),
        ),
        (
            "current_student_curriculum_enrollments.tsv",
            (
                "student_curriculum_enrollment_id",
                "student_object_id",
                "student_id",
                "username",
                "curriculum_id",
                "curriculum",
                "entry_semester_id",
                "exit_semester_id",
                "is_primary",
                "is_active",
            ),
            iter_student_curriculum_enrollment_rows(),
        ),
        (
            "current_sections.tsv",
            (
                "section_id",
                "semester_id",
                "curriculum_course_id",
                "curriculum",
                "course_key",
                "course_title",
                "section_number",
                "faculty_id",
                "current_registrations",
            ),
            iter_section_rows(),
        ),
        (
            "current_registrations.tsv",
            (
                "registration_id",
                "student_object_id",
                "student_id",
                "username",
                "section_id",
                "semester_id",
                "curriculum_course_id",
                "curriculum",
                "course_key",
                "course_title",
                "section_number",
                "status",
                "date_registered",
            ),
            iter_registration_rows(),
        ),
        (
            "current_grades.tsv",
            (
                "grade_id",
                "student_object_id",
                "student_id",
                "username",
                "section_id",
                "semester_id",
                "curriculum_course_id",
                "curriculum",
                "course_key",
                "course_title",
                "section_number",
                "grade_value",
                "grade_number",
                "is_effective",
                "graded_on",
            ),
            iter_grade_rows(),
        ),
        (
            "current_course_invoices.tsv",
            (
                "course_invoice_id",
                "student_semester_invoice_id",
                "student_object_id",
                "student_id",
                "username",
                "semester_id",
                "curriculum_course_id",
                "curriculum",
                "course_key",
                "initial_amount_due",
                "balance",
                "status",
            ),
            iter_course_invoice_rows(),
        ),
        (
            "current_semester_invoices.tsv",
            (
                "student_semester_invoice_id",
                "student_object_id",
                "student_id",
                "username",
                "semester_id",
                "initial_amount_due",
                "required_deposit_amount",
                "balance",
                "status",
            ),
            iter_semester_invoice_rows(),
        ),
        (
            "current_payments.tsv",
            (
                "payment_id",
                "student_semester_invoice_id",
                "student_object_id",
                "student_id",
                "username",
                "semester_id",
                "amount_paid",
                "payer",
                "payment_method",
                "status",
            ),
            iter_payment_rows(),
        ),
    )


def write_current_data_snapshot(
    output_dir: Path, usage: CurrentUsageT | None = None
) -> SnapshotSummaryT:
    """Write current operational data snapshots into ``output_dir``."""
    usage = usage or load_current_usage()
    counts: dict[str, int] = {}
    for filename, headers, rows in _snapshot_specs(usage):
        counts[filename] = write_tsv(output_dir / filename, headers, rows)
    return SnapshotSummaryT(output_dir=output_dir, counts=counts)
