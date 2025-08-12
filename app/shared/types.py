"""Personal Types."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from django.db.models import QuerySet

if TYPE_CHECKING:
    from app.academics.models.course import Course
    from app.people.models.faculty import Faculty
    from app.people.models.student import Student
    from app.registry.models import Registration
    from app.timetable.models import Section

SectionQuery: TypeAlias = QuerySet["Section"]
CourseQuery: TypeAlias = QuerySet["Course"]
FacultyQuery: TypeAlias = QuerySet["Faculty"]
StudentQuery: TypeAlias = QuerySet["Student"]
RegistrationQuery: TypeAlias = QuerySet["Registration"]

FieldT: TypeAlias = (
    list[str | list[str] | tuple[str, ...] | tuple[()]]
    | tuple[str | list[str] | tuple[str, ...] | tuple[()], ...]
    | tuple[()]
)
# PersonT = TypeVar("PersonT")  # ? what is this.
# PersonT = TypeAlias = Donor|Staff| Student| Faculty
