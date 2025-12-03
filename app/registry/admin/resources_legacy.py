"""Admin resources for importing historical registry data."""

from __future__ import annotations

import csv
from functools import cached_property
from pathlib import Path

from django.conf import settings
from import_export import fields, widgets

from app.people.admin.widgets import GradeStudentWidget
from app.registry.admin.resources import GradeResource, RegistrationResource
from app.registry.models.registration import RegistrationStatus
from app.shared.data import legacy_registration_rows
from app.shared.utils import expand_course_code, get_in_row, normalize_academic_year
from app.timetable.admin.widgets.section import SectionWidget

SEM_MAP = {
    "1": "1",
    "FIRST": "1",
    "2": "2",
    "SECOND": "2",
    "SUMMER": "3",
    "VAC": "3",
    "3": "3",
}

CURRICULUM_MAX_LEN = 40


def normalize_semester(raw: str | None) -> str:
    """Collapse textual semester labels to numeric slots."""
    token = (raw or "").strip().upper()
    return SEM_MAP.get(token, "1")


def _rename_headers(row: dict[str, str], mapping: dict[str, str]) -> None:
    """Copy legacy SmartSchool headers into the new schema."""
    for legacy, modern in mapping.items():
        if modern in row:
            continue
        value = row.get(legacy)
        if value is not None:
            row[modern] = value


def _extract_course_codes(row: dict[str, str]) -> tuple[str, str]:
    """Return the parsed college and department codes for the row."""
    course_code = row.pop("course_code", "") or row.get("course_dept", "")
    course_no = get_in_row("course_no", row)
    merged = f"{course_code}{course_no}".strip()
    if not merged:
        return (
            get_in_row("college_code", row) or "",
            get_in_row("course_dept", row) or "",
        )

    try:
        college_code, dept_code, _ = expand_course_code(merged, row=row)
    except AssertionError:
        return (
            get_in_row("college_code", row) or "",
            get_in_row("course_dept", row) or "",
        )
    return college_code, dept_code


def _first_value(row: dict[str, str], keys: tuple[str, ...]) -> str:
    """Return the first non-empty value for any key in *keys*."""
    for key in keys:
        value = get_in_row(key, row)
        if value:
            return value
    return ""


def _truncate_curriculum_label(label: str) -> str:
    """Clamp curriculum labels to the DB max_length (40 chars)."""
    text = (label or "").strip()
    if len(text) > CURRICULUM_MAX_LEN:
        return text[:CURRICULUM_MAX_LEN]
    return text


class LegacyGradeSheetResource(GradeResource):
    """Import SmartSchool grade sheets while reusing the standard widgets."""
    invalid_log_path = (
        Path(settings.BASE_DIR) / "Seed_data" / "Tmp" / "legacy_grade_invalid.csv"
    )
    dataset_headers = {
        "StudentID": "student_id",
        "Grade": "grade_code",
        "CourseNo": "course_no",
        "CourseCode": "course_code",
        "Section": "section_no",
        "CrHrs": "credit_hours",
        "AcademicYear": "academic_year",
        "Semester": "semester_no",
        "Major": "curriculum",
        "College": "college_code",
        "Instructor": "faculty",
        "Points": "legacy_points",
        "Date": "legacy_graded_on",
    }
    fallback_curriculum = "Legacy"

    def __init__(self, *args, **kwargs):
        """Track invalid rows skipped during import."""
        super().__init__(*args, **kwargs)
        self._skipped_count = 0

    def should_skip_row(self, row, row_number, *, command=None) -> bool:
        """Skip empty/invalid rows lacking course or grade data."""
        student = _first_value(row, ("student_id", "StudentID"))
        course_code = _first_value(row, ("course_code", "CourseCode"))
        course_no = _first_value(row, ("course_no", "CourseNo"))
        grade = _first_value(row, ("grade_code", "Grade"))
        reason = ""
        if not grade.strip():
            reason = "missing grade"
        elif not course_code.strip() and not course_no.strip():
            reason = "missing course code/number"

        if reason:
            self._skipped_count += 1
            self._log_invalid_row(row_number, row, reason)
            return True
        return False

    def post_import_report(self, command) -> None:
        """Emit summary for skipped invalid rows."""
        if self._skipped_count:
            command.stdout.write(
                command.style.WARNING(
                    f"LegacyGrade skipped {self._skipped_count} invalid rows; "
                    f"details logged to {self.invalid_log_path}"
                )
            )

    @cached_property
    def registration_lookup(self) -> dict[tuple[str, str, str], tuple[str, str]]:
        """Map (student, academic_year, semester) to (major, college)."""
        lookup: dict[tuple[str, str, str], tuple[str, str]] = {}
        for row in legacy_registration_rows():
            student_id = get_in_row("student_id", row) or get_in_row("StudentID", row)
            if not student_id:
                continue
            year = normalize_academic_year(
                get_in_row("academic_year", row) or get_in_row("AcademicYear", row)
            )
            sem = normalize_semester(
                get_in_row("semester_no", row) or get_in_row("Semester", row)
            )
            if not year:
                continue
            lookup[(student_id, year, sem)] = (
                get_in_row("major", row) or get_in_row("Major", row),
                get_in_row("college", row) or get_in_row("College", row),
            )
        return lookup

    def before_import_row(self, row, **kwargs):
        """Normalize SmartSchool grade sheets before delegating to GradeResource."""
        _rename_headers(row, self.dataset_headers)

        row["student_id"] = get_in_row("student_id", row)
        row["academic_year"] = normalize_academic_year(row.get("academic_year"))
        row["semester_no"] = normalize_semester(row.get("semester_no"))
        row["section_no"] = get_in_row("section_no", row)
        row["course_no"] = get_in_row("course_no", row)
        row["credit_hours"] = get_in_row("credit_hours", row) or "0"
        college_code, dept_code = _extract_course_codes(row)
        row.setdefault("college_code", college_code)
        row.setdefault("course_dept", dept_code)

        key = (
            row.get("student_id", ""),
            row.get("academic_year", ""),
            row.get("semester_no", ""),
        )
        major, college = self.registration_lookup.get(
            key, ("", row.get("college_code", ""))
        )
        current_curriculum = get_in_row("curriculum", row)
        if not current_curriculum:
            current_curriculum = major or self.fallback_curriculum
        row["curriculum_long_name"] = current_curriculum
        row["curriculum"] = _truncate_curriculum_label(current_curriculum)
        if college:
            row["college_code"] = college

        graded_on = get_in_row("graded_on", row) or row.get("legacy_graded_on")
        if graded_on:
            row["graded_on"] = graded_on
        points = get_in_row("legacy_points", row)
        if points:
            row["legacy_points"] = points

        return super().before_import_row(row, **kwargs)

    def _log_invalid_row(self, row_number: int, row: dict[str, str], reason: str) -> None:
        """Append invalid row context to a CSV log for follow-up."""
        path = self.invalid_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "row_number",
            "student_id",
            "academic_year",
            "semester_no",
            "course_code",
            "course_no",
            "grade_code",
            "reason",
        ]
        write_header = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            if write_header:
                writer.writeheader()
            writer.writerow(
                {
                    "row_number": row_number,
                    "student_id": _first_value(row, ("student_id", "StudentID")),
                    "academic_year": _first_value(row, ("academic_year", "AcademicYear")),
                    "semester_no": _first_value(row, ("semester_no", "Semester")),
                    "course_code": _first_value(row, ("course_code", "CourseCode")),
                    "course_no": _first_value(row, ("course_no", "CourseNo")),
                    "grade_code": _first_value(row, ("grade_code", "Grade")),
                    "reason": reason,
                }
            )


class LegacyRegistrationResource(RegistrationResource):
    """Load SmartSchool registrations while ensuring statuses and widgets."""

    dataset_headers = {
        "StudentID": "student_id",
        "AcademicYear": "academic_year",
        "Semester": "semester_no",
        "CourseCode": "course_code",
        "CourseNo": "course_no",
        "Section": "section_no",
        "CrHrs": "credit_hours",
        "Major": "curriculum",
        "Curriculum": "curriculum",
        "College": "college_code",
    }

    student = fields.Field(
        attribute="student",
        column_name="student_id",
        widget=GradeStudentWidget(),
    )
    section = fields.Field(
        attribute="section",
        column_name="section_no",
        widget=SectionWidget(),
    )
    status = fields.Field(
        attribute="status",
        column_name="status",
        widget=widgets.ForeignKeyWidget(RegistrationStatus, field="code"),
    )

    def before_import_row(self, row, **kwargs):
        """Normalize headers and ensure the widgets receive the expected columns."""
        _rename_headers(row, self.dataset_headers)

        row["student_id"] = get_in_row("student_id", row)
        row["academic_year"] = normalize_academic_year(row.get("academic_year"))
        row["semester_no"] = normalize_semester(row.get("semester_no"))
        row["section_no"] = get_in_row("section_no", row)
        row["course_no"] = get_in_row("course_no", row)
        row["credit_hours"] = get_in_row("credit_hours", row) or "0"
        college_code, dept_code = _extract_course_codes(row)
        row.setdefault("college_code", college_code)
        row.setdefault("course_dept", dept_code)
        current_curriculum = get_in_row("curriculum", row)
        if not current_curriculum:
            current_curriculum = self.fallback_curriculum
        row["curriculum_long_name"] = current_curriculum
        row["curriculum"] = _truncate_curriculum_label(current_curriculum)
        row.setdefault(
            "status",
            get_in_row("status", row) or RegistrationStatus.get_default().code,
        )

        return super().before_import_row(row, **kwargs)

    @property
    def fallback_curriculum(self) -> str:
        """Return a default curriculum label for registrations."""
        return LegacyGradeSheetResource.fallback_curriculum

    # ---------------- duplicate handling / logging ----------------

    duplicate_log_path = (
        Path(settings.BASE_DIR) / "Seed_data" / "Tmp" / "legacy_registration_duplicates.csv"
    )
    _duplicate_count: int

    def __init__(self, *args, **kwargs):
        """Initialize internal counters for duplicate tracking."""
        super().__init__(*args, **kwargs)
        self._duplicate_count = 0

    def handle_integrity_error(self, exc, row, row_number, *, command=None) -> bool:
        """Allow the import command to skip duplicate registration rows gracefully."""
        message = str(exc)
        if "uniq_registration_student_section" not in message:
            return False
        self._duplicate_count += 1
        self._log_duplicate_row(row_number, row, message)
        return True

    def post_import_report(self, command) -> None:
        """Emit a summary when duplicates were encountered."""
        if not self._duplicate_count:
            return
        command.stdout.write(
            command.style.WARNING(
                f"LegacyRegistration skipped {self._duplicate_count} duplicates; "
                f"details logged to {self.duplicate_log_path}"
            )
        )

    def _log_duplicate_row(self, row_number: int, row: dict[str, str], error: str) -> None:
        """Append duplicate registration context to the log file."""
        path = self.duplicate_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "row_number",
            "student_id",
            "academic_year",
            "semester_no",
            "course_code",
            "course_no",
            "section_no",
            "status",
            "error",
        ]
        write_header = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            if write_header:
                writer.writeheader()
            writer.writerow(
                {
                    "row_number": row_number,
                    "student_id": row.get("student_id", ""),
                    "academic_year": row.get("academic_year", ""),
                    "semester_no": row.get("semester_no", ""),
                    "course_code": row.get("course_code") or row.get("course_dept", ""),
                    "course_no": row.get("course_no", ""),
                    "section_no": row.get("section_no", ""),
                    "status": row.get("status", ""),
                    "error": error,
                }
            )
