"""Typed shapes and constants for registrar transcript documents."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

FloatMapT: TypeAlias = dict[int, float]
IntMapT: TypeAlias = dict[int, int]

GRADE_LEGEND = "A = 90-100; B = 80-89; C = 70-79; D = 60-69; F = 0-59"
NOTICE_CONTINUE = (
    "When inscribed with a signature and the seal of Tubman University on the "
    "last page of this transcript, this constitutes an Official Transcript."
)
NOTICE_FINAL = (
    "This is a true copy of the records for the above named student. When "
    "inscribed with the seal of William V.S. Tubman University Registrar's "
    "Office, this constitutes an Official Transcript."
)


class TranscriptCourseRowT(TypedDict):
    """Single transcript course row ready for display."""

    course_code: str
    course_title: str
    clinical: str
    start_date: str
    end_date: str
    final_grade: str
    attempted_credit: str
    earned_credit: str
    quality_points: str


class TranscriptTermGroupT(TypedDict):
    """Transcript rows and summaries for one semester."""

    term_label: str
    term_start_date: str
    term_end_date: str
    rows: list[TranscriptCourseRowT]
    term_attempted_credit: str
    term_earned_credit: str
    term_quality_points: str
    term_gpa: str
    program_attempted_credit: str
    program_earned_credit: str
    program_quality_points: str
    program_gpa: str


class TranscriptDocumentT(TypedDict):
    """Complete document payload consumed by transcript templates."""

    logo_uri: str
    institution_name: str
    address_one: str
    address_two: str
    country: str
    website: str
    registrar_email: str
    document_title: str
    student_name: str
    student_address_one: str
    student_address_two: str
    student_id: str
    dob: str
    enrollment_date: str
    completion_date: str
    graduation_date: str
    program_code: str
    college: str
    major_program: str
    program_total_attempted: str
    program_total_earned: str
    program_total_gpa: str
    cumulative_total_attempted: str
    cumulative_total_earned: str
    cumulative_total_quality: str
    cumulative_total_gpa: str
    printed_date: str
    printed_date_short: str
    grade_legend: str
    notice_continue: str
    notice_final: str
    registrar_title: str
    term_groups: list[TranscriptTermGroupT]


__all__ = [
    "FloatMapT",
    "GRADE_LEGEND",
    "IntMapT",
    "NOTICE_CONTINUE",
    "NOTICE_FINAL",
    "TranscriptCourseRowT",
    "TranscriptDocumentT",
    "TranscriptTermGroupT",
]
