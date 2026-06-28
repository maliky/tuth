"""Program enrollment chart data for academic leader dashboards."""

from __future__ import annotations

from collections import defaultdict
from typing import TypedDict

from django.db.models import QuerySet

from app.academics.choices import AcademicCareer, LEVEL_NUMBER
from app.academics.models.curriculum import Curriculum
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.source_truth.curriculum_match import (
    REVISED_CURRICULUM_CODE_BY_LEGACY,
    curriculum_match_key,
    standardize_legacy_curriculum_label,
)
from app.timetable.models.semester import Semester

LEVEL_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (LEVEL_NUMBER.ONE.label, "Freshman", "Fr", "#2f6f4f"),
    (LEVEL_NUMBER.TWO.label, "Sophomore", "So", "#2f5d8c"),
    (LEVEL_NUMBER.THREE.label, "Junior", "Jr", "#a06b00"),
    (LEVEL_NUMBER.FOUR.label, "Senior", "Sr", "#7f3f46"),
)
GRADUATE_LEVEL_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("graduate_1", "Graduate 1", "G1", "#2f6f4f"),
    ("graduate_2", "Graduate 2", "G2", "#7f3f46"),
)


LevelCountT = TypedDict(
    "LevelCountT",
    {"count": int, "female": int, "male": int, "unknown": int},
)
ProgramCountT = TypedDict(
    "ProgramCountT",
    {
        "program": str,
        "title": str,
        "academic_career": str,
        "total": int,
        "levels": dict[str, LevelCountT],
    },
)


def _pct(value: int, total: int) -> str:
    """Return one-decimal percentage text."""
    return f"{(100 * value / total):.1f}%" if total else "0.0%"


def _level_from_credits(credits: int) -> str:
    """Return the same student-level label used by Student.class_level."""
    for max_credits, level in (
        (36, LEVEL_NUMBER.ONE.label),
        (72, LEVEL_NUMBER.TWO.label),
        (108, LEVEL_NUMBER.THREE.label),
    ):
        if credits <= max_credits:
            return level
    return LEVEL_NUMBER.FOUR.label


def _graduate_level_from_credits(credits: int) -> str:
    """Return a graduate level bucket from completed credits."""
    if credits <= 30:
        return "graduate_1"
    return "graduate_2"


def _level_specs_for_career(career: str) -> tuple[tuple[str, str, str, str], ...]:
    """Return dashboard level buckets for one academic career."""
    if career == AcademicCareer.GRADUATE:
        return GRADUATE_LEVEL_SPECS
    return LEVEL_SPECS


def _level_from_credits_for_career(credits: int, career: str) -> str:
    """Return the student-progress bucket for one program career."""
    if career == AcademicCareer.GRADUATE:
        return _graduate_level_from_credits(credits)
    return _level_from_credits(credits)


def _completion_credits_by_student(student_ids: list[int]) -> dict[int, int]:
    """Return completed effective credits keyed by student id."""
    grades = (
        Grade.objects.filter(
            student_id__in=student_ids,
            is_effective=True,
            value__number__gte=1,
        )
        .select_related("section__curriculum_course__credit_hours")
        .only("student_id", "section__curriculum_course__credit_hours__code")
    )
    credits_by_student: dict[int, int] = defaultdict(int)
    for grade in grades:
        credits_by_student[grade.student_id] += int(
            grade.section.curriculum_course.credit_hours.code
        )
    return credits_by_student


def _empty_program_count(curriculum: Curriculum) -> ProgramCountT:
    """Return initialized counters for one active program."""
    return {
        "program": curriculum.short_name,
        "title": curriculum.long_name or curriculum.short_name,
        "academic_career": curriculum.academic_career,
        "total": 0,
        "levels": {
            key: {"count": 0, "female": 0, "male": 0, "unknown": 0}
            for key, _label, _short, _color in _level_specs_for_career(
                curriculum.academic_career
            )
        },
    }


def _program_counts(
    curricula: QuerySet[Curriculum],
    semester: Semester,
) -> list[ProgramCountT]:
    """Return active program counts, preserving zero-registration programs."""
    curriculum_list = list(
        curricula.select_related("college").order_by("short_name", "id")
    )
    program_counts = {
        curriculum.id: _empty_program_count(curriculum) for curriculum in curriculum_list
    }
    visible_careers = {
        curriculum.academic_career for curriculum in curriculum_list if curriculum.id
    }
    active_by_key = {
        curriculum_match_key(curriculum.short_name): curriculum.id
        for curriculum in curriculum_list
    }
    registrations = (
        Registration.objects.filter(
            section__semester=semester,
            section__curriculum_course__curriculum__college_id__in={
                curriculum.college_id for curriculum in curriculum_list
            },
        )
        .select_related("student", "section__curriculum_course__curriculum")
        .only(
            "student_id",
            "student__gender",
            "section__curriculum_course__curriculum_id",
            "section__curriculum_course__curriculum__short_name",
            "section__curriculum_course__curriculum__long_name",
        )
    )
    if visible_careers:
        registrations = registrations.filter(
            section__curriculum_course__curriculum__academic_career__in=visible_careers
        )
    program_students: list[tuple[int, int, str]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for registration in registrations:
        source = registration.section.curriculum_course.curriculum
        target_id = _target_program_id(source, active_by_key)
        if target_id is None:
            continue
        pair = (target_id, registration.student_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        program_students.append(
            (target_id, registration.student_id, registration.student.gender)
        )

    credits_by_student = _completion_credits_by_student(
        [student_id for _target_id, student_id, _gender in program_students]
    )
    for target_id, student_id, gender in program_students:
        data = program_counts.get(target_id)
        if data is None:
            continue
        level = _level_from_credits_for_career(
            credits_by_student.get(student_id, 0),
            data["academic_career"],
        )
        gender_key = {"f": "female", "m": "male"}.get(gender or "", "unknown")
        data["total"] += 1
        level_bucket = data["levels"][level]
        level_bucket["count"] += 1
        if gender_key == "female":
            level_bucket["female"] += 1
        elif gender_key == "male":
            level_bucket["male"] += 1
        else:
            level_bucket["unknown"] += 1
    return list(program_counts.values())


def _target_program_id(
    source: Curriculum,
    active_by_key: dict[str, int],
) -> int | None:
    """Map a section curriculum to a visible active program id."""
    direct = active_by_key.get(curriculum_match_key(source.short_name))
    if direct is not None:
        return direct
    for label in (source.short_name, source.long_name or ""):
        standardized = standardize_legacy_curriculum_label(label)
        mapped_code = REVISED_CURRICULUM_CODE_BY_LEGACY.get(standardized, "")
        target = active_by_key.get(curriculum_match_key(mapped_code))
        if target is not None:
            return target
    return None


def _chart_rows(counts: list[ProgramCountT]) -> list[dict[str, object]]:
    """Return horizontal bar rows for all active programs."""
    max_total = max((row["total"] for row in counts), default=0)
    rows: list[dict[str, object]] = []
    for data in counts:
        segments: list[dict[str, object]] = []
        for level, label, short, color in _level_specs_for_career(
            data["academic_career"]
        ):
            bucket = data["levels"][level]
            count = bucket["count"]
            if not count:
                continue
            segments.append(
                {
                    "color": color,
                    "width_pct": f"{count / data['total'] * 100:.2f}%",
                    "label": f"{short} {count}",
                    "tooltip": _segment_tooltip(data, label, bucket),
                }
            )
        rows.append(_chart_row(data, max_total, segments))
    return rows


def _segment_tooltip(
    data: ProgramCountT,
    label: str,
    bucket: LevelCountT,
) -> str:
    """Return hover text for one level segment."""
    count = bucket["count"]
    lines = [
        data["program"],
        data["title"],
        "",
        label,
        f"Total: {count} students ({_pct(count, data['total'])} of program)",
        f"Male: {bucket['male']} ({_pct(bucket['male'], count)})",
        f"Female: {bucket['female']} ({_pct(bucket['female'], count)})",
    ]
    if bucket["unknown"]:
        lines.append(f"Unknown: {bucket['unknown']} ({_pct(bucket['unknown'], count)})")
    return "\n".join(lines)


def _chart_row(
    data: ProgramCountT,
    max_total: int,
    segments: list[dict[str, object]],
) -> dict[str, object]:
    """Return text and summary data for one horizontal program row."""
    male = sum(bucket["male"] for bucket in data["levels"].values())
    female = sum(bucket["female"] for bucket in data["levels"].values())
    unknown = sum(bucket["unknown"] for bucket in data["levels"].values())
    total = data["total"] or male + female + unknown
    scale_pct = (data["total"] / max_total * 100) if max_total else 0
    return {
        "program": data["program"],
        "display_program": data["program"]
        if len(data["program"]) <= 14
        else f"{data['program'][:13]}...",
        "title": data["title"],
        "total": data["total"],
        "scale_pct": f"{scale_pct:.2f}%",
        "gender_text": f"M {_pct(male, total)} · F {_pct(female, total)}",
        "segments": segments,
    }


def program_stack_chart(
    curricula: QuerySet[Curriculum],
    semester: Semester,
) -> dict[str, object]:
    """Return horizontal stacked bars for all active programs."""
    counts = _program_counts(curricula, semester)
    has_data = any(row["total"] for row in counts)
    return {
        "rows": _chart_rows(counts),
        "legend": _legend_items(counts) if has_data else [],
        "has_data": has_data,
    }


def _legend_items(counts: list[ProgramCountT]) -> list[dict[str, object]]:
    """Return legend items for student levels."""
    careers = {row["academic_career"] for row in counts if row["total"]}
    mixed_careers = len(careers) > 1
    items: list[dict[str, object]] = []
    if AcademicCareer.UNDERGRADUATE in careers:
        for _level, label, _short, color in LEVEL_SPECS:
            # Mixed charts need career-specific labels for same-color buckets.
            item_label = f"UG {label}" if mixed_careers else label
            items.append({"color": color, "label": item_label})
    if AcademicCareer.GRADUATE in careers:
        items.extend(
            {"color": color, "label": label}
            for _level, label, _short, color in GRADUATE_LEVEL_SPECS
        )
    return items


__all__ = ["program_stack_chart"]
