"""Current catalog usage counters for safe reconciliation decisions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeAlias, no_type_check

from django.db.models import Count

from app.academics.models import Course, CurriCrs, Curriculum
from app.academics.reconciliation_io import RowT, as_cell, course_key
from app.finance.models import CrsInvoice
from app.people.models.student_curriculum_enrollment import StdCurriEnroll
from app.registry.models import Grade, Registration
from app.timetable.models.section import Section

CountMapT: TypeAlias = dict[int, int]


@dataclass(frozen=True)
class CurrentUsageT:
    """Usage counts that decide whether current catalog rows are safe to remap."""

    course_sections: CountMapT
    course_registrations: CountMapT
    course_grades: CountMapT
    course_invoices: CountMapT
    curriculum_student_enrollments: CountMapT
    curriculum_sections: CountMapT
    curriculum_registrations: CountMapT
    curriculum_grades: CountMapT
    curriculum_invoices: CountMapT
    curriculum_course_sections: CountMapT
    curriculum_course_registrations: CountMapT
    curriculum_course_grades: CountMapT
    curriculum_course_invoices: CountMapT


def _count_pairs(rows: Iterable[tuple[object, object]]) -> CountMapT:
    """Convert aggregate ``values_list`` output into an int keyed count map."""
    counts: CountMapT = {}
    for raw_key, raw_count in rows:
        key = _coerce_int(raw_key)
        if key is None:
            continue
        counts[key] = _coerce_int(raw_count) or 0
    return counts


def _coerce_int(value: object) -> int | None:
    """Return an int for simple DB scalar values."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        return int(text) if text else None
    return int(str(value))


def _sum_counts(*maps: CountMapT, key: int) -> int:
    """Return the total usage count for a single object id."""
    return sum(counts.get(key, 0) for counts in maps)


@no_type_check
def _count_by(manager, field_name: str) -> CountMapT:
    """Return aggregate counts for a Django relation path.

    The Django mypy plugin crashes on some nested aggregate paths here; keep the
    ORM expression centralized and runtime-checked by the reconciliation tests.
    """
    rows = (
        manager.values(field_name)
        .annotate(total=Count("id"))
        .values_list(field_name, "total")
    )
    return _count_pairs(rows)


def load_current_usage() -> CurrentUsageT:
    """Return current references to course, curriculum, and curriculum-course rows."""
    return CurrentUsageT(
        course_sections=_count_by(
            Section.objects,
            "curriculum_course__course_id",
        ),
        course_registrations=_count_by(
            Registration.objects,
            "section__curriculum_course__course_id",
        ),
        course_grades=_count_by(
            Grade.objects,
            "section__curriculum_course__course_id",
        ),
        course_invoices=_count_by(
            CrsInvoice.objects,
            "curriculum_course__course_id",
        ),
        curriculum_student_enrollments=_count_by(
            StdCurriEnroll.objects,
            "curriculum_id",
        ),
        curriculum_sections=_count_by(
            Section.objects,
            "curriculum_course__curriculum_id",
        ),
        curriculum_registrations=_count_by(
            Registration.objects,
            "section__curriculum_course__curriculum_id",
        ),
        curriculum_grades=_count_by(
            Grade.objects,
            "section__curriculum_course__curriculum_id",
        ),
        curriculum_invoices=_count_by(
            CrsInvoice.objects,
            "curriculum_course__curriculum_id",
        ),
        curriculum_course_sections=_count_by(
            Section.objects,
            "curriculum_course_id",
        ),
        curriculum_course_registrations=_count_by(
            Registration.objects,
            "section__curriculum_course_id",
        ),
        curriculum_course_grades=_count_by(
            Grade.objects,
            "section__curriculum_course_id",
        ),
        curriculum_course_invoices=_count_by(
            CrsInvoice.objects,
            "curriculum_course_id",
        ),
    )


def iter_current_course_rows(usage: CurrentUsageT) -> Iterable[RowT]:
    """Yield current Course rows with historical dependency counts."""
    courses = Course.objects.select_related("department__college").order_by(
        "department__code", "number", "id"
    )
    for course in courses.iterator():
        course_id = int(course.id)
        yield {
            "course_id": as_cell(course_id),
            "college_code": as_cell(course.department.college.code),
            "course_dept": as_cell(course.department.code),
            "course_no": as_cell(course.number),
            "course_key": course_key(course.department.code, course.number),
            "course_code": as_cell(course.code),
            "short_code": as_cell(course.short_code),
            "course_title": as_cell(course.title),
            "description": as_cell(course.description),
            "section_count": as_cell(usage.course_sections.get(course_id, 0)),
            "registration_count": as_cell(usage.course_registrations.get(course_id, 0)),
            "grade_count": as_cell(usage.course_grades.get(course_id, 0)),
            "course_invoice_count": as_cell(usage.course_invoices.get(course_id, 0)),
            "usage_total": as_cell(
                _sum_counts(
                    usage.course_sections,
                    usage.course_registrations,
                    usage.course_grades,
                    usage.course_invoices,
                    key=course_id,
                )
            ),
        }


def iter_current_curriculum_rows(usage: CurrentUsageT) -> Iterable[RowT]:
    """Yield current Curriculum rows with student and activity references."""
    curricula = Curriculum.objects.select_related("college").order_by(
        "college__code", "short_name", "id"
    )
    for curriculum in curricula.iterator():
        curriculum_id = int(curriculum.id)
        yield {
            "curriculum_id": as_cell(curriculum_id),
            "college_code": as_cell(curriculum.college.code),
            "curriculum": as_cell(curriculum.short_name),
            "curriculum_key": as_cell(curriculum.short_name).upper(),
            "long_name": as_cell(curriculum.long_name),
            "status": as_cell(curriculum.status_id),
            "is_active": as_cell(curriculum.is_active),
            "student_enrollment_count": as_cell(
                usage.curriculum_student_enrollments.get(curriculum_id, 0)
            ),
            "section_count": as_cell(usage.curriculum_sections.get(curriculum_id, 0)),
            "registration_count": as_cell(
                usage.curriculum_registrations.get(curriculum_id, 0)
            ),
            "grade_count": as_cell(usage.curriculum_grades.get(curriculum_id, 0)),
            "course_invoice_count": as_cell(
                usage.curriculum_invoices.get(curriculum_id, 0)
            ),
            "usage_total": as_cell(
                _sum_counts(
                    usage.curriculum_student_enrollments,
                    usage.curriculum_sections,
                    usage.curriculum_registrations,
                    usage.curriculum_grades,
                    usage.curriculum_invoices,
                    key=curriculum_id,
                )
            ),
        }


def iter_current_curriculum_course_rows(usage: CurrentUsageT) -> Iterable[RowT]:
    """Yield current CurriCrs rows with dependency counts."""
    curriculum_courses = CurriCrs.objects.select_related(
        "curriculum__college",
        "course__department__college",
        "credit_hours",
    ).order_by("curriculum__short_name", "course__department__code", "course__number")
    for curriculum_course in curriculum_courses.iterator():
        curri_crs_id = int(curriculum_course.id)
        course = curriculum_course.course
        curriculum = curriculum_course.curriculum
        yield {
            "curriculum_course_id": as_cell(curri_crs_id),
            "curriculum_id": as_cell(curriculum.id),
            "course_id": as_cell(course.id),
            "curriculum": as_cell(curriculum.short_name),
            "curriculum_key": as_cell(curriculum.short_name).upper(),
            "course_key": course_key(course.department.code, course.number),
            "college_code": as_cell(curriculum.college.code),
            "course_college_code": as_cell(course.department.college.code),
            "course_dept": as_cell(course.department.code),
            "course_no": as_cell(course.number),
            "course_title": as_cell(course.title),
            "credit_hours": as_cell(curriculum_course.credit_hours_id),
            "year_number": as_cell(curriculum_course.year_number),
            "semester_number": as_cell(curriculum_course.semester_number),
            "level_number": as_cell(curriculum_course.level_number),
            "is_required": as_cell(curriculum_course.is_required),
            "is_elective": as_cell(curriculum_course.is_elective),
            "section_count": as_cell(
                usage.curriculum_course_sections.get(curri_crs_id, 0)
            ),
            "registration_count": as_cell(
                usage.curriculum_course_registrations.get(curri_crs_id, 0)
            ),
            "grade_count": as_cell(usage.curriculum_course_grades.get(curri_crs_id, 0)),
            "course_invoice_count": as_cell(
                usage.curriculum_course_invoices.get(curri_crs_id, 0)
            ),
            "usage_total": as_cell(
                _sum_counts(
                    usage.curriculum_course_sections,
                    usage.curriculum_course_registrations,
                    usage.curriculum_course_grades,
                    usage.curriculum_course_invoices,
                    key=curri_crs_id,
                )
            ),
        }
