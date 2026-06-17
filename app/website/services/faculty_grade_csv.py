"""CSV import/export helpers for faculty grade rosters."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Sequence, TypeAlias, TypedDict

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from app.registry.models.grade import Grade
from app.timetable.models.section import Section
from app.website.services.faculty_grade_portal import (
    FacultyGradeError,
    _grade_value_for_code,
    _set_grade_code,
    build_faculty_grade_rows,
    course_code,
    ensure_grade_roster,
    grade_entry_open,
)

GRADE_CSV_HEADERS: tuple[str, ...] = (
    "student_id",
    "student_name",
    "section_id",
    "section_code",
    "academic_year",
    "semester_no",
    "course_code",
    "grade_code",
)

CsvRowT: TypeAlias = dict[str, str | None]
GradeUploadT: TypeAlias = list[tuple[Grade, str]]


class CsvIssueT(TypedDict):
    """One blocking CSV validation issue shown to faculty."""

    row: int | None
    field: str
    message: str


class FacultyGradeCsvError(FacultyGradeError):
    """Raised when a CSV roster has row-level validation errors."""

    def __init__(self, summary: str, issues: list[CsvIssueT]) -> None:
        super().__init__(summary)
        self.summary = summary
        self.issues = issues


def grade_roster_csv(section: Section) -> str:
    """Return an importable CSV roster for one section."""
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=GRADE_CSV_HEADERS)
    writer.writeheader()
    for row in build_faculty_grade_rows(section):
        writer.writerow(
            {
                "student_id": row["student_id"],
                "student_name": row["student_label"],
                "section_id": section.id,
                "section_code": section.short_code,
                "academic_year": section.semester.academic_year.code,
                "semester_no": section.semester.number,
                "course_code": course_code(section),
                "grade_code": row["current_code"].upper(),
            }
        )
    return buffer.getvalue()


def _uploaded_csv_text(uploaded_file: UploadedFile) -> str:
    """Decode an uploaded CSV file as UTF-8 text."""
    data = b"".join(uploaded_file.chunks())
    return data.decode("utf-8-sig")


def _row_value(row: CsvRowT, key: str) -> str:
    """Return a stripped CSV row value."""
    return (row.get(key) or "").strip()


def _normalize_csv_token(value: str) -> str:
    """Normalize CSV identity fields for strict template matching."""
    return " ".join(value.casefold().split())


def _issue(row: int | None, field: str, message: str) -> CsvIssueT:
    """Build one typed CSV validation issue."""
    return {"row": row, "field": field, "message": message}


def _validate_headers(fieldnames: Sequence[str] | None) -> None:
    """Validate the CSV headers before row processing."""
    missing_headers = set(GRADE_CSV_HEADERS).difference(fieldnames or [])
    if missing_headers:
        missing = ", ".join(sorted(missing_headers))
        raise FacultyGradeCsvError(
            "CSV import stopped before reading rows.",
            [_issue(None, "headers", f"Missing CSV column(s): {missing}.")],
        )


def _validate_upload_rows(section: Section, rows: list[CsvRowT]) -> GradeUploadT:
    """Validate CSV rows and return grade updates without mutating data."""
    roster_grades = ensure_grade_roster(section)
    roster = {grade.student.student_id: grade for grade in roster_grades}
    roster_names = {
        grade.student.student_id: _normalize_csv_token(
            grade.student.long_name
            or grade.student.user.get_full_name()
            or grade.student.user.username
        )
        for grade in roster_grades
    }
    section_code = section.short_code
    current_course_code = course_code(section)
    issues: list[CsvIssueT] = []
    updates: GradeUploadT = []
    seen_students: dict[str, tuple[int, str]] = {}
    for index, row in enumerate(rows, start=2):
        row_section_id = _row_value(row, "section_id")
        row_section_code = _row_value(row, "section_code")
        row_course_code = _row_value(row, "course_code")
        student_id = _row_value(row, "student_id")
        student_name = _row_value(row, "student_name")
        grade_code = _row_value(row, "grade_code")

        if not row_section_id:
            issues.append(_issue(index, "section_id", "Missing section id."))
        elif row_section_id != str(section.id):
            issues.append(
                _issue(index, "section_id", "Section id does not match this roster.")
            )
        if not row_section_code:
            issues.append(_issue(index, "section_code", "Missing section code."))
        elif row_section_code != section_code:
            issues.append(
                _issue(
                    index,
                    "section_code",
                    f"Expected section code {section_code}, got {row_section_code}.",
                )
            )
        if not row_course_code:
            issues.append(_issue(index, "course_code", "Missing course code."))
        elif row_course_code != current_course_code:
            issues.append(
                _issue(
                    index,
                    "course_code",
                    f"Expected course code {current_course_code}, got {row_course_code}.",
                )
            )
        if not student_id:
            issues.append(_issue(index, "student_id", "Missing student id."))
        if not student_name:
            issues.append(_issue(index, "student_name", "Missing student name."))

        grade = roster.get(student_id)
        if student_id and grade is None:
            issues.append(
                _issue(index, "student_id", "Student id is not in this section.")
            )
        expected_name = roster_names.get(student_id)
        if student_name and expected_name:
            normalized_name = _normalize_csv_token(student_name)
            if normalized_name != expected_name:
                issues.append(
                    _issue(
                        index,
                        "student_name",
                        "Student name does not match the student id in this roster.",
                    )
                )
        if student_id:
            previous = seen_students.get(student_id)
            if previous is not None:
                previous_row, previous_grade_code = previous
                if _normalize_csv_token(previous_grade_code) != _normalize_csv_token(
                    grade_code
                ):
                    issues.append(
                        _issue(
                            index,
                            "student_id",
                            (
                                f"Duplicate student id also appears on row "
                                f"{previous_row} with a different grade."
                            ),
                        )
                    )
                else:
                    issues.append(
                        _issue(
                            index,
                            "student_id",
                            f"Duplicate student id also appears on row {previous_row}.",
                        )
                    )
            else:
                seen_students[student_id] = (index, grade_code)

        if grade_code:
            try:
                _grade_value_for_code(grade_code)
            except FacultyGradeError as exc:
                issues.append(_issue(index, "grade_code", str(exc)))
        if grade is not None and grade_code:
            updates.append((grade, grade_code))
    if issues:
        raise FacultyGradeCsvError(
            "CSV import stopped. No grade changes were saved.",
            issues,
        )
    return updates


def import_grade_roster_csv(section: Section, uploaded_file: UploadedFile) -> int:
    """Import grades from a section-scoped CSV roster."""
    if not grade_entry_open(section):
        raise FacultyGradeError("Grade entry is closed for this section.")
    with transaction.atomic():
        reader = csv.DictReader(StringIO(_uploaded_csv_text(uploaded_file)))
        _validate_headers(reader.fieldnames)
        updates = _validate_upload_rows(section, list(reader))
        changed = 0
        for grade, grade_code in updates:
            if _set_grade_code(grade, grade_code):
                changed += 1
    return changed


__all__ = [
    "CsvIssueT",
    "FacultyGradeCsvError",
    "GRADE_CSV_HEADERS",
    "grade_roster_csv",
    "import_grade_roster_csv",
]
