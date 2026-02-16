"""Shared fast lookup helpers for people imports."""

from __future__ import annotations

from typing import TypeAlias

from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.shared.types import StrIntMapT
from app.shared.utils import parse_str

StdIdT: TypeAlias = str

STUDENT_ID_CACHE: StrIntMapT = {}


def _prime_std_id_cache() -> None:
    """Load student ids into the local cache if empty."""
    if STUDENT_ID_CACHE:
        return
    for student_id, pk in Student.objects.values_list("student_id", "id"):
        STUDENT_ID_CACHE[student_id] = pk


# def ensure_student(student_id_raw: StdIdT) -> int:
#     """Return a student id, creating the record if missing."""
#     # > we need to search student on student id direclty as
#     # > it is also a primary key for the model
#     sid = (student_id_raw or "").strip()
#     if not sid:
#         return int(Student.get_default().pk)

#     _prime_std_id_cache()
#     existing = STUDENT_ID_CACHE.get(sid)
#     if existing:
#         return existing

#     User = get_user_model()
#     # > Use the the model mk_username function
#     # the pb it is not from the sid.

#     # base_username = f"student_{sid}".lower()
#     # username = base_username
#     # this use creation is no
#     counter = 1
#     while User.objects.filter(student_id=sid).exists():
#         counter += 1
#         username = f"{base_username}{counter}"
#     user = User.objects.create_user(
#         username=username,
#         first_name="Student",
#         last_name=sid,
#     )
#     student = Student(
#         user=user,
#         student_id=sid,
#         curriculum=Curriculum.get_default(),
#     )
#     student.save()
#     STUDENT_ID_CACHE[sid] = int(student.pk)
#     return int(student.pk)


def ensure_student_sid(student_id_raw: StdIdT) -> int:
    """Return a student id, creating the record if missing."""
    # > we need to search student on student id direclty as
    # > it is also a primary key for the model
    sid = parse_str(student_id_raw)
    if not sid:
        return int(Student.get_default().pk)

    _prime_std_id_cache()
    existing = STUDENT_ID_CACHE.get(sid)
    if existing:
        return existing

    if Student.objects.filter(student_id=sid).exists():
        student = Student.objects.get(student_id=sid)
        STUDENT_ID_CACHE[sid] = int(student.pk)
        return int(student.pk)

    # our personalized manager will take care of missing students
    # and create them on the fly.
    student, _ = Student.objects.get_or_create(
        student_id=sid,
        defaults={
            "first_name": "Student",
            "last_name": sid,
            "curriculum": Curriculum.get_default(),
        },
    )

    # student.save()  # is it necessary after a save ?

    STUDENT_ID_CACHE[sid] = int(student.pk)
    return int(student.pk)
