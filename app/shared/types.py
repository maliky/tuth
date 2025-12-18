"""Personal Types."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, TypeAlias, Union

from django.db.models import QuerySet
from import_export import resources

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

FieldT: TypeAlias = Union[
    list[str | list[str] | tuple[str, ...] | tuple[()]],
    tuple[str | list[str] | tuple[str, ...] | tuple[()], ...],
    tuple[()],
]

ModelResourceType: TypeAlias = type[resources.ModelResource]
DirectoryResourceEntry: TypeAlias = tuple[
    str,
    ModelResourceType,
    tuple[str, ...],
]

LookUpType: TypeAlias = Sequence[tuple[str, str]]
# PersonT = TypeVar("PersonT")  # ? what is this.
# PersonT = TypeAlias = Donor|Staff| Student| Faculty
