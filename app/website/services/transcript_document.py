"""Typed transcript document builders for registrar downloads."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.people.models.student import Student
from app.registry.constants import GPA_EXCLUDED_CODES
from app.registry.gpa import effective_transcript_grades
from app.registry.models.grade import Grade
from app.timetable.models.semester import Semester
from app.website.services.transcript_formatting import (
    fmt_abbrev_date,
    fmt_date,
    fmt_gpa,
    fmt_number,
)
from app.website.services.transcript_types import (
    DEFICIENCY_POLICY_NOTES,
    GRADE_LEGEND,
    GRADE_POLICY_INTRO,
    GRADE_SCALE_ROWS,
    MENTION_RULES_NOTE,
    NOTICE_CONTINUE,
    NOTICE_FINAL,
    FloatMapT,
    IntMapT,
    TranscriptCourseRowT,
    TranscriptDocumentT,
    TranscriptTermGroupT,
)


def _semester_label(semester: Semester) -> str:
    """Return the TU-style academic year and semester label."""
    labels = {
        1: "1st Semester",
        2: "2nd Semester",
        3: "Vac School",
        4: "Remedial",
    }
    sem_label = labels.get(semester.number, f"Semester {semester.number}")
    return f"{semester.academic_year.long_name}, {sem_label}"


def _semester_start(semester: Semester) -> date | None:
    """Return the best available semester start date."""
    return semester.start_date or semester.academic_year.start_date


def _semester_end(semester: Semester) -> date | None:
    """Return the best available semester end date."""
    return semester.end_date or semester.academic_year.end_date


def _term_key(semester: Semester) -> tuple[date, int, int]:
    """Return a stable chronological key for transcript groups."""
    return (_semester_start(semester) or date.min, semester.number, semester.id or 0)


def _course_code(grade: Grade) -> str:
    """Return the display course code for a grade."""
    course = grade.section.curriculum_course.course
    return course.short_code or course.code or ""


def _address_lines(student: Student) -> tuple[str, str]:
    """Return two student address lines for the transcript header."""
    lines = [
        line.strip()
        for line in (student.physical_address or "").splitlines()
        if line.strip()
    ]
    if not lines:
        return "N/A", ""
    if len(lines) == 1:
        return lines[0], ""
    return lines[0], " ".join(lines[1:])


def _logo_uri() -> str:
    """Return a file URI for the TU logo when it is available."""
    logo_path = finders.find("img/tulogo.png")
    if not logo_path:
        return ""
    path = Path(str(logo_path))
    if not path.exists():
        return ""
    return path.resolve().as_uri()


def _grade_values(grade: Grade) -> tuple[int, int, float]:
    """Return attempted credits, earned credits, and quality points."""
    value = grade.value
    grade_code = (value.code or "").lower() if value else ""
    credits = int(grade.section.curriculum_course.credit_hours.code)
    if value is None or value.number is None or grade_code in GPA_EXCLUDED_CODES:
        return 0, 0, 0.0
    earned_credits = credits if value.number >= 1 else 0
    return credits, earned_credits, float(value.number) * credits


def _course_row(grade: Grade) -> TranscriptCourseRowT:
    """Return a display row for one grade."""
    section = grade.section
    course = section.curriculum_course.course
    attempted_credit, earned_credit, quality_points = _grade_values(grade)
    final_grade = grade.value.code.upper() if grade.value and grade.value.code else "-"
    return {
        "course_code": _course_code(grade),
        "course_title": course.title or "",
        "final_grade": final_grade,
        "attempted_credit": fmt_number(attempted_credit),
        "earned_credit": fmt_number(earned_credit),
        "quality_points": fmt_number(quality_points),
    }


def _empty_term_group(semester: Semester) -> TranscriptTermGroupT:
    """Return a term group initialized with empty display totals."""
    return {
        "term_label": _semester_label(semester),
        "rows": [],
        "term_attempted_credit": fmt_number(0),
        "term_earned_credit": fmt_number(0),
        "term_quality_points": fmt_number(0),
        "term_gpa": "N/A",
        "program_attempted_credit": fmt_number(0),
        "program_earned_credit": fmt_number(0),
        "program_quality_points": fmt_number(0),
        "program_gpa": "N/A",
    }


def _grade_queryset(student: Student) -> list[Grade]:
    """Return effective transcript grades for the student."""
    grades_qs = (
        Grade.objects.filter(student=student)
        .select_related(
            "value",
            "section__semester",
            "section__semester__academic_year",
            "section__curriculum_course__credit_hours",
            "section__curriculum_course__course",
            "section__curriculum_course__course__department",
        )
        .order_by(
            "section__semester__start_date",
            "section__semester__number",
            "section__curriculum_course__course__short_code",
        )
    )
    grades = effective_transcript_grades(grades_qs)
    return sorted(
        grades,
        key=lambda grade: (_term_key(grade.section.semester), _course_code(grade)),
    )


def _term_groups(grades: list[Grade]) -> list[TranscriptTermGroupT]:
    """Group grades by semester and compute term/program totals."""
    groups: list[TranscriptTermGroupT] = []
    group_lookup: dict[int, TranscriptTermGroupT] = {}
    attempted_by_term: IntMapT = {}
    earned_by_term: IntMapT = {}
    points_by_term: FloatMapT = {}
    for grade in grades:
        semester = grade.section.semester
        semester_id = int(semester.id)
        group = group_lookup.get(semester_id)
        if group is None:
            group = _empty_term_group(semester)
            group_lookup[semester_id] = group
            groups.append(group)
            attempted_by_term[semester_id] = 0
            earned_by_term[semester_id] = 0
            points_by_term[semester_id] = 0.0
        attempted_credit, earned_credit, quality_points = _grade_values(grade)
        group["rows"].append(_course_row(grade))
        attempted_by_term[semester_id] += attempted_credit
        earned_by_term[semester_id] += earned_credit
        points_by_term[semester_id] += quality_points

    cumulative_attempted = 0
    cumulative_earned = 0
    cumulative_points = 0.0
    for group in groups:
        semester_id = next(
            key for key, term_group in group_lookup.items() if term_group is group
        )
        term_attempted = attempted_by_term[semester_id]
        term_earned = earned_by_term[semester_id]
        term_points = points_by_term[semester_id]
        cumulative_attempted += term_attempted
        cumulative_earned += term_earned
        cumulative_points += term_points
        group["term_attempted_credit"] = fmt_number(term_attempted)
        group["term_earned_credit"] = fmt_number(term_earned)
        group["term_quality_points"] = fmt_number(term_points)
        group["term_gpa"] = fmt_gpa(term_points, term_attempted)
        group["program_attempted_credit"] = fmt_number(cumulative_attempted)
        group["program_earned_credit"] = fmt_number(cumulative_earned)
        group["program_quality_points"] = fmt_number(cumulative_points)
        group["program_gpa"] = fmt_gpa(cumulative_points, cumulative_attempted)
    return groups


def build_transcript_document(student_id: int) -> TranscriptDocumentT:
    """Build a complete registrar transcript document payload."""
    student = get_object_or_404(
        Student.objects.select_related(
            "user",
            "entry_semester__academic_year",
            "last_enrolled_semester__academic_year",
        ),
        pk=student_id,
    )
    curriculum = student.primary_curriculum
    college = curriculum.college
    grades = _grade_queryset(student)
    groups = _term_groups(grades)
    total_attempted = sum(float(group["term_attempted_credit"]) for group in groups)
    total_earned = sum(float(group["term_earned_credit"]) for group in groups)
    total_quality = sum(float(group["term_quality_points"]) for group in groups)
    printed_on = timezone.localdate()
    address_one, address_two = _address_lines(student)
    entry_semester = student.entry_semester
    enrollment_date = (
        fmt_abbrev_date(_semester_start(entry_semester)) if entry_semester else "N/A"
    )
    last_enrolled_semester = student.last_enrolled_semester
    completion_date = (
        fmt_abbrev_date(_semester_end(last_enrolled_semester))
        if last_enrolled_semester
        else "N/A"
    )
    total_gpa = fmt_gpa(total_quality, int(total_attempted))
    institution_name = getattr(
        settings, "TRANSCRIPT_UNIVERSITY_NAME", "William V.S. Tubman University"
    )
    return {
        "logo_uri": _logo_uri(),
        "institution_name": institution_name,
        "address_one": getattr(
            settings, "TRANSCRIPT_ADDRESS_ONE", "Tubman Town, East Harper"
        ),
        "address_two": getattr(settings, "TRANSCRIPT_ADDRESS_TWO", "Maryland County"),
        "country": getattr(settings, "TRANSCRIPT_COUNTRY", "Republic of Liberia"),
        "website": getattr(settings, "TRANSCRIPT_WEBSITE", "www.Tubmanu.edu.lr"),
        "registrar_email": getattr(
            settings, "TRANSCRIPT_REGISTRAR_EMAIL", "registrar@tubmanu.edu.lr"
        ),
        "document_title": getattr(
            settings, "TRANSCRIPT_DOCUMENT_TITLE", "Official Student Transcript"
        ),
        "student_name": student.long_name
        or student.user.get_full_name()
        or student.student_id,
        "student_address_one": address_one,
        "student_address_two": address_two,
        "student_id": student.student_id or "Pending ID",
        "dob": fmt_date(student.birth_date) or "N/A",
        "enrollment_date": enrollment_date,
        "completion_date": completion_date,
        "graduation_date": "N/A",
        "program_code": curriculum.short_name,
        "college": college.long_name or college.code,
        "major_program": curriculum.long_name or curriculum.short_name,
        "program_total_attempted": fmt_number(total_attempted),
        "program_total_earned": fmt_number(total_earned),
        "program_total_gpa": total_gpa,
        "cumulative_total_attempted": fmt_number(total_attempted),
        "cumulative_total_earned": fmt_number(total_earned),
        "cumulative_total_quality": fmt_number(total_quality),
        "cumulative_total_gpa": total_gpa,
        "printed_date": fmt_date(printed_on),
        "printed_date_short": printed_on.strftime("%d-%b-%Y"),
        "grade_legend": GRADE_LEGEND,
        "grade_policy_intro": GRADE_POLICY_INTRO,
        "grade_scale_rows": GRADE_SCALE_ROWS,
        "deficiency_policy_notes": DEFICIENCY_POLICY_NOTES,
        "mention_rules_note": MENTION_RULES_NOTE,
        "notice_continue": NOTICE_CONTINUE,
        "notice_final": NOTICE_FINAL,
        "registrar_title": getattr(settings, "TRANSCRIPT_REGISTRAR_TITLE", "REGISTRAR"),
        "term_groups": groups,
        "verification_token": "",
        "verification_url": "",
        "qr_code_uri": "",
    }


def flatten_transcript_rows(document: TranscriptDocumentT) -> list[TranscriptCourseRowT]:
    """Return course rows without term grouping for simple portal previews."""
    return [row for group in document["term_groups"] for row in group["rows"]]


__all__ = [
    "TranscriptCourseRowT",
    "TranscriptDocumentT",
    "TranscriptTermGroupT",
    "build_transcript_document",
    "flatten_transcript_rows",
]
