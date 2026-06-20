"""Student duplicate detection and conservative merge helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import StdCurriEnroll
from app.registry.models.document import DocStd
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.student_ids import student_id_digit_key, student_id_exact_key

StudentDuplicateKindT: TypeAlias = Literal["exact_id", "numeric_overlap"]
CountMapT: TypeAlias = dict[str, int]


@dataclass(frozen=True)
class StudentDuplicateGroupT:
    """Students grouped by a duplicate-detection key."""

    key: str
    kind: StudentDuplicateKindT
    students: list[Student]


def student_operational_counts(student: Student) -> CountMapT:
    """Return row counts that matter before a duplicate student merge."""
    return {
        "registrations": Registration.objects.filter(student=student).count(),
        "grades": Grade.objects.filter(student=student).count(),
        "semester_invoices": StdSemesterInvoice.objects.filter(student=student).count(),
        "course_invoices": CrsInvoice.objects.filter(student=student).count(),
        "curricula": StdCurriEnroll.objects.filter(student=student).count(),
        "documents": DocStd.objects.filter(person=student).count(),
    }


def student_duplicate_groups(
    *,
    kind: StudentDuplicateKindT = "exact_id",
    student_id: str | None = None,
) -> list[StudentDuplicateGroupT]:
    """Return duplicate student groups for exact ids or numeric overlaps."""
    students = list(Student.objects.select_related("user").order_by("student_id", "pk"))
    selected_key = _student_group_key(student_id or "", kind) if student_id else ""
    grouped: dict[str, list[Student]] = {}
    for student in students:
        key = _student_group_key(student.student_id, kind)
        if not key:
            continue
        if selected_key and key != selected_key:
            continue
        grouped.setdefault(key, []).append(student)

    groups: list[StudentDuplicateGroupT] = []
    for key, group_students in grouped.items():
        if len(group_students) < 2:
            continue
        if kind == "numeric_overlap":
            exact_keys = {
                student_id_exact_key(student.student_id) for student in group_students
            }
            if len(exact_keys) < 2:
                continue
        groups.append(StudentDuplicateGroupT(key=key, kind=kind, students=group_students))
    return sorted(
        groups, key=lambda group: (len(group.students), group.key), reverse=True
    )


def choose_canonical_student(students: list[Student]) -> Student:
    """Choose the safest target row among duplicate student records."""
    return max(students, key=_student_score)


def duplicate_sources(students: list[Student]) -> tuple[Student, list[Student]]:
    """Return target and non-target sources from a duplicate student group."""
    target = choose_canonical_student(students)
    sources = [student for student in students if student.pk != target.pk]
    return target, sources


def _student_group_key(value: str, kind: StudentDuplicateKindT) -> str:
    """Return the grouping key for one student id."""
    if kind == "numeric_overlap":
        return student_id_digit_key(value)
    return student_id_exact_key(value)


def _is_placeholder_student(student: Student) -> bool:
    """Return whether a student row looks like an import placeholder."""
    student_id = (student.student_id or "").strip().casefold()
    long_name = (student.long_name or "").strip().casefold()
    username = (student.username or "").strip().casefold()
    return (
        not long_name
        or long_name in {student_id, f"student {student_id}"}
        or username.startswith("student.tu")
    )


def _student_score(student: Student) -> tuple[int, int, int, int]:
    """Rank duplicate targets by identity quality and operational evidence."""
    counts = student_operational_counts(student)
    completeness = sum(
        bool(getattr(student, field))
        for field in (
            "long_name",
            "birth_date",
            "physical_address",
            "phone_number",
            "nationality",
            "last_school_attended",
        )
    )
    operational_total = sum(counts.values())
    return (
        0 if _is_placeholder_student(student) else 1,
        completeness,
        operational_total,
        student.pk,
    )


__all__ = [
    "StudentDuplicateGroupT",
    "choose_canonical_student",
    "duplicate_sources",
    "student_duplicate_groups",
    "student_operational_counts",
]
