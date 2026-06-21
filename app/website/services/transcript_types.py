"""Typed shapes and constants for registrar transcript documents."""

from __future__ import annotations

from typing import Literal, TypeAlias, TypedDict

FloatMapT: TypeAlias = dict[int, float]
IntMapT: TypeAlias = dict[int, int]
TranscriptLayoutKeyT: TypeAlias = Literal[
    "portrait",
    "landscape",
]

DEFAULT_TRANSCRIPT_LAYOUT: TranscriptLayoutKeyT = "portrait"
GRADE_LEGEND = "A = 90-100; B = 80-89; C = 70-79; D = 60-69; F = Below 60"
GRADE_POLICY_INTRO = (
    "Each course is assigned credit in semester hours. One semester hour is "
    "defined as fifty (50) contact minutes and, where applicable, three hours "
    "per week of practical or laboratory work throughout a fifteen-week semester."
)
DEFICIENCY_POLICY_NOTES = [
    (
        "Grades of D, I, F, AB, DR, or NG are considered deficiencies in a "
        "student's academic status at the university."
    ),
    (
        "A grade of D is unsatisfactory. A student must re-enroll in the course "
        "within the next two consecutive semesters and earn a grade of C or "
        "better to earn the course credits where university policy requires it."
    ),
    (
        "A grade of I indicates that a student completed a substantial part of "
        "the course with satisfactory performance but could not complete all "
        "requirements. It may be converted to a letter grade when requirements "
        "are met within the next two consecutive semesters."
    ),
    (
        "A grade of F represents failure. The student must re-enroll in the "
        "course and earn a grade of C or better to earn course credits."
    ),
    (
        "A grade of AB indicates that the student did not take the final "
        "examination and provided documented evidence for that inability."
    ),
    (
        "A grade of DR indicates that the student exceeded the three excused "
        "absences allowed and must re-enroll to earn course credits."
    ),
    (
        "A grade of NG indicates that the student registered for the course but "
        "failed to officially withdraw or attend classes."
    ),
    (
        "A grade of W indicates an official withdrawal approved through the "
        "Office of the Registrar after consultation with the instructor and "
        "department chair and/or dean."
    ),
]
MENTION_RULES_NOTE = (
    "Mention and honor thresholds are to be confirmed by the Registrar before "
    "final transcript publication."
)
NOTICE_CONTINUE = (
    "When inscribed with a signature and the seal of Tubman University on the "
    "last page of this transcript, this constitutes an Official Transcript."
)
NOTICE_FINAL = (
    "This is a true copy of the records for the above named student. When "
    "inscribed with the seal of William V.S. Tubman University Registrar's "
    "Office, this constitutes an Official Transcript."
)


class TranscriptLayoutOptionT(TypedDict):
    """Selectable transcript PDF layout option."""

    key: TranscriptLayoutKeyT
    label: str
    description: str
    orientation: str
    column_count: int
    css_class: str


class TranscriptLayoutChoiceT(TranscriptLayoutOptionT):
    """Transcript layout option annotated for form display."""

    selected: bool


TRANSCRIPT_LAYOUT_OPTIONS: tuple[TranscriptLayoutOptionT, ...] = (
    {
        "key": "portrait",
        "label": "Portrait",
        "description": "A4 portrait with two transcript detail columns.",
        "orientation": "portrait",
        "column_count": 2,
        "css_class": "layout-portrait",
    },
    {
        "key": "landscape",
        "label": "Landscape",
        "description": "A4 landscape with two transcript detail columns.",
        "orientation": "landscape",
        "column_count": 2,
        "css_class": "layout-landscape",
    },
)


class TranscriptGradeScaleRowT(TypedDict):
    """One grade-letter description for transcript back matter."""

    numerical_value: str
    letter_grade: str
    meaning: str
    index_number: str


GRADE_SCALE_ROWS: list[TranscriptGradeScaleRowT] = [
    {
        "numerical_value": "90-100",
        "letter_grade": "A",
        "meaning": "Excellent",
        "index_number": "4.0",
    },
    {
        "numerical_value": "80-89",
        "letter_grade": "B",
        "meaning": "Good",
        "index_number": "3.0",
    },
    {
        "numerical_value": "70-79",
        "letter_grade": "C",
        "meaning": "Average",
        "index_number": "2.0",
    },
    {
        "numerical_value": "60-69",
        "letter_grade": "D",
        "meaning": "Poor",
        "index_number": "1.0",
    },
    {
        "numerical_value": "Below 60",
        "letter_grade": "F",
        "meaning": "Failure",
        "index_number": "0.0",
    },
]


def normalize_transcript_layout(value: str | None) -> TranscriptLayoutKeyT:
    """Return a supported transcript layout key."""
    if value in {"portrait_one", "portrait_two", "portrait"}:
        return "portrait"
    if value in {"landscape_two", "landscape"}:
        return "landscape"
    for option in TRANSCRIPT_LAYOUT_OPTIONS:
        if option["key"] == value:
            return option["key"]
    return DEFAULT_TRANSCRIPT_LAYOUT


def transcript_layout_config(
    layout_key: TranscriptLayoutKeyT,
) -> TranscriptLayoutOptionT:
    """Return the display and rendering config for one layout."""
    for option in TRANSCRIPT_LAYOUT_OPTIONS:
        if option["key"] == layout_key:
            return option
    return TRANSCRIPT_LAYOUT_OPTIONS[0]


def transcript_layout_choices(
    selected_key: TranscriptLayoutKeyT,
) -> list[TranscriptLayoutChoiceT]:
    """Return layout options marked for the selected form value."""
    return [
        {
            "key": option["key"],
            "label": option["label"],
            "description": option["description"],
            "orientation": option["orientation"],
            "column_count": option["column_count"],
            "css_class": option["css_class"],
            "selected": option["key"] == selected_key,
        }
        for option in TRANSCRIPT_LAYOUT_OPTIONS
    ]


class TranscriptCourseRowT(TypedDict):
    """Single transcript course row ready for display."""

    course_code: str
    course_title: str
    final_grade: str
    attempted_credit: str
    earned_credit: str
    quality_points: str


class TranscriptTermGroupT(TypedDict):
    """Transcript rows and summaries for one semester."""

    term_label: str
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
    grade_policy_intro: str
    grade_scale_rows: list[TranscriptGradeScaleRowT]
    deficiency_policy_notes: list[str]
    mention_rules_note: str
    notice_continue: str
    notice_final: str
    registrar_title: str
    term_groups: list[TranscriptTermGroupT]
    verification_token: str
    verification_url: str
    qr_code_uri: str


__all__ = [
    "FloatMapT",
    "DEFAULT_TRANSCRIPT_LAYOUT",
    "DEFICIENCY_POLICY_NOTES",
    "GRADE_LEGEND",
    "GRADE_POLICY_INTRO",
    "GRADE_SCALE_ROWS",
    "IntMapT",
    "MENTION_RULES_NOTE",
    "NOTICE_CONTINUE",
    "NOTICE_FINAL",
    "TRANSCRIPT_LAYOUT_OPTIONS",
    "TranscriptCourseRowT",
    "TranscriptDocumentT",
    "TranscriptGradeScaleRowT",
    "TranscriptLayoutChoiceT",
    "TranscriptLayoutKeyT",
    "TranscriptLayoutOptionT",
    "TranscriptTermGroupT",
    "normalize_transcript_layout",
    "transcript_layout_choices",
    "transcript_layout_config",
]
