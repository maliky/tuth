"""Admin resources for importing historical registry data."""

from __future__ import annotations

from functools import cached_property

from import_export import fields, widgets

from app.people.admin.widgets import GradeStudentWidget
from app.registry.admin.resources import GradeResource, RegistrationResource
from app.registry.models.registration import RegistrationStatus
from app.shared.data import legacy_registration_rows
from app.shared.utils import expand_course_code, get_in_row
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


def normalize_year(raw: str | None) -> str:
    """Return a YY-YY academic year code from common SmartSchool formats."""
    text = (raw or "").strip().replace(" ", "").replace("/", "-")
    if not text:
        return ""

    if len(text) == 9 and text[4] == "-":  # 2019-2020
        return f"{text[2:4]}-{text[7:9]}"

    if len(text) == 4 and text.isdigit():  # 2019
        yy = text[2:4]
        return f"{yy}-{int(yy) + 1:02d}"

    if len(text) == 7 and text[2] == "-":  # 19-20
        return text

    return text.upper()


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


class LegacyGradeSheetResource(GradeResource):
    """
    Import SmartSchool grade sheets while reusing the standard GradeResource widgets.
    """

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

    @cached_property
    def registration_lookup(self) -> dict[tuple[str, str, str], tuple[str, str]]:
        """Map (student, academic_year, semester) to (major, college)."""
        lookup: dict[tuple[str, str, str], tuple[str, str]] = {}
        for row in legacy_registration_rows():
            student_id = get_in_row("student_id", row) or get_in_row("StudentID", row)
            if not student_id:
                continue
            year = normalize_year(
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
        row["academic_year"] = normalize_year(row.get("academic_year"))
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
        if not get_in_row("curriculum", row):
            row["curriculum"] = major or self.fallback_curriculum
        if college:
            row["college_code"] = college

        graded_on = get_in_row("graded_on", row) or row.get("legacy_graded_on")
        if graded_on:
            row["graded_on"] = graded_on
        points = get_in_row("legacy_points", row)
        if points:
            row["legacy_points"] = points

        return super().before_import_row(row, **kwargs)


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
        row["academic_year"] = normalize_year(row.get("academic_year"))
        row["semester_no"] = normalize_semester(row.get("semester_no"))
        row["section_no"] = get_in_row("section_no", row)
        row["course_no"] = get_in_row("course_no", row)
        row["credit_hours"] = get_in_row("credit_hours", row) or "0"
        college_code, dept_code = _extract_course_codes(row)
        row.setdefault("college_code", college_code)
        row.setdefault("course_dept", dept_code)
        if not get_in_row("curriculum", row):
            row["curriculum"] = self.fallback_curriculum
        row.setdefault(
            "status",
            get_in_row("status", row) or RegistrationStatus.get_default().code,
        )

        return super().before_import_row(row, **kwargs)

    @property
    def fallback_curriculum(self) -> str:
        """Return a default curriculum label for registrations."""
        return LegacyGradeSheetResource.fallback_curriculum
