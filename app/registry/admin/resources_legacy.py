"""Admin resources for importing historical registry data."""

from __future__ import annotations

from functools import cached_property

from import_export import fields, widgets

from app.people.admin.widgets import StudentGradeWidget
from app.registry.admin.resources import GradeResource, RegistrationResource
from app.registry.models.registration import RegistrationStatus
from app.shared.data import legacy_registration_rows
from app.shared.importing import (
    CsvRowLogger,
    coerce_field,
    first_value,
    normalize_field,
    pipeline,
    rename_headers,
    set_course_codes,
    setdefault_field,
)
from app.shared.utils import get_in_row
from app.timetable.admin.section_widgets import SectionWidget
from app.timetable.utils import normalize_academic_year

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


def normalize_year(raw: str | None) -> str:
    """Public alias used in tests; delegate to normalize_academic_year."""
    return normalize_academic_year(raw)


def _truncate_curriculum_label(label: str) -> str:
    """Clamp curriculum labels to the DB max_length (40 chars)."""
    text = (label or "").strip()
    if len(text) > CURRICULUM_MAX_LEN:
        return text[:CURRICULUM_MAX_LEN]
    return text


class LegacyGradeSheetResource(GradeResource):
    """Import SmartSchool grade sheets while reusing the standard widgets."""

    dataset_headers = {
        "academicyear": "academic_year",
        "college": "college_code",
        "coursecode": "course_code",
        "courseno": "course_no",
        "crhrs": "credit_hours",
        "date": "legacy_graded_on",
        "grade": "grade_code",
        "instructor": "faculty",
        "major": "curriculum",
        "points": "legacy_points",
        "section": "section_no",
        "semester": "semester_no",
        "studentid": "student_id",
    }
    fallback_curriculum = "Legacy"

    def __init__(self, *args, **kwargs):
        """Track invalid rows skipped during import."""
        super().__init__(*args, **kwargs)
        self.invalid_logger = CsvRowLogger(
            "legacy_grade_invalid.csv",
            (
                "row_number",
                "student_id",
                "academic_year",
                "semester_no",
                "course_code",
                "course_no",
                "grade_code",
                "reason",
            ),
            "LegacyGrade skipped {count} invalid rows; details logged to {path}",
        )

    def should_skip_row(self, row, row_number, *, command=None) -> bool:
        """Skip empty/invalid rows lacking course or grade data."""
        course_code = first_value(row, ("course_code", "coursecode"))
        course_no = first_value(row, ("course_no", "courseno"))
        grade = first_value(row, ("grade_code", "grade"))
        reason = ""
        if not grade:
            reason = "missing grade"
        elif not course_code and not course_no:
            reason = "missing course code/number"

        if reason:
            self._log_invalid_row(row_number, row, reason)
            return True
        return False

    def post_import_report(self, command) -> None:
        """Emit summary for skipped invalid rows."""
        self.invalid_logger.report(command)

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
        pipeline(
            row,
            rename_headers(self.dataset_headers),
            normalize_field("academic_year", normalize_academic_year),
            normalize_field("semester_no", normalize_semester),
            coerce_field("credit_hours", default="0"),
        )
        set_course_codes(row)
        row["student_id"] = get_in_row("student_id", row)
        row["section_no"] = get_in_row("section_no", row)
        row["course_no"] = get_in_row("course_no", row)

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
        self.invalid_logger.log(
            {
                "row_number": str(row_number),
                "student_id": first_value(row, ("student_id", "studentid")),
                "academic_year": first_value(row, ("academic_year", "AcademicYear")),
                "semester_no": first_value(row, ("semester_no", "semester")),
                "course_code": first_value(row, ("course_code", "coursecode")),
                "course_no": first_value(row, ("course_no", "courseno")),
                "grade_code": first_value(row, ("grade_code", "grade")),
                "reason": str(reason),
            }
        )


class LegacyRegistrationResource(RegistrationResource):
    """Load SmartSchool registrations while ensuring statuses and widgets."""

    dataset_headers = {
        "studentid": "student_id",
        "academicyear": "academic_year",
        "semester": "semester_no",
        "coursecode": "course_code",
        "courseno": "course_no",
        "section": "section_no",
        "crhrs": "credit_hours",
        "major": "curriculum",
        "curriculum": "curriculum",
        "college": "college_code",
    }

    student = fields.Field(
        attribute="student",
        column_name="student_id",
        widget=StudentGradeWidget(),
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
        pipeline(
            row,
            rename_headers(self.dataset_headers),
            normalize_field("academic_year", normalize_academic_year),
            normalize_field("semester_no", normalize_semester),
            coerce_field("credit_hours", default="0"),
        )
        set_course_codes(row)
        row["student_id"] = get_in_row("student_id", row)
        row["section_no"] = get_in_row("section_no", row)
        row["course_no"] = get_in_row("course_no", row)
        current_curriculum = get_in_row("curriculum", row) or self.fallback_curriculum
        row["curriculum_long_name"] = current_curriculum
        row["curriculum"] = _truncate_curriculum_label(current_curriculum)
        pipeline(
            row,
            setdefault_field(
                "status",
                lambda _: RegistrationStatus.get_default().code,
            ),
        )

        return super().before_import_row(row, **kwargs)

    @property
    def fallback_curriculum(self) -> str:
        """Return a default curriculum label for registrations."""
        return LegacyGradeSheetResource.fallback_curriculum

    # ---------------- duplicate handling / logging ----------------

    def __init__(self, *args, **kwargs):
        """Initialize internal counters for duplicate tracking."""
        super().__init__(*args, **kwargs)
        self.duplicate_logger = CsvRowLogger(
            "legacy_registration_duplicates.csv",
            (
                "row_number",
                "student_id",
                "academic_year",
                "semester_no",
                "course_code",
                "course_no",
                "section_no",
                "status",
                "error",
            ),
            "LegacyRegistration skipped {count} duplicates; details logged to {path}",
        )

    def handle_integrity_error(self, exc, row, row_number, *, command=None) -> bool:
        """Allow the import command to skip duplicate registration rows gracefully."""
        message = str(exc)
        if "uniq_registration_student_section" not in message:
            return False
        self._log_duplicate_row(row_number, row, message)
        return True

    def post_import_report(self, command) -> None:
        """Emit a summary when duplicates were encountered."""
        self.duplicate_logger.report(command)

    def _log_duplicate_row(
        self, row_number: int, row: dict[str, str], error: str
    ) -> None:
        """Append duplicate registration context to the log file."""
        self.duplicate_logger.log(
            {
                "row_number": str(row_number),
                "student_id": get_in_row("student_id", row),
                "academic_year": get_in_row("academic_year", row),
                "semester_no": get_in_row("semester_no", row),
                "course_code": get_in_row("course_code", row)
                or get_in_row("course_dept", row),
                "course_no": get_in_row("course_no", row),
                "section_no": get_in_row("section_no", row),
                "status": get_in_row("status", row),
                "error": error,
            }
        )
