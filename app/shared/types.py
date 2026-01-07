"""Personal Types."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Sequence,
    TypeAlias,
    TypeVar,
    Union,
    Optional,
)

from django.db.models import QuerySet
from import_export import resources

if TYPE_CHECKING:
    from pathlib import Path

    from app.academics.models.course import Course
    from app.people.models.faculty import Faculty
    from app.people.models.student import Student
    from app.registry.models import Registration
    from app.timetable.models import Section

AbstractPersonT = TypeVar("_T")
Entity = TypeVar("Entity")
PersonT = TypeVar("PersonT", bound=Model)
AbstractPersonT = TypeVar("PersonT", bound="AbstractPerson")



Row = dict[str, Any]
Transform = Callable[[Row], Row]

SectionQuery: TypeAlias = QuerySet["Section"]
CourseQuery: TypeAlias = QuerySet["Course"]
FacultyQuery: TypeAlias = QuerySet["Faculty"]
StudentQuery: TypeAlias = QuerySet["Student"]
RegistrationQuery: TypeAlias = QuerySet["Registration"]
SemesterCodeT: TypeAlias = Tuple[str, int]

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

# Generic mapping aliases used across importers
StrIntMapT: TypeAlias = dict[str, int]
IntIntMapT: TypeAlias = dict[int, int]
TwoStrIntMapT: TypeAlias = dict[tuple[str, int], int]
TwoIntIntMapT: TypeAlias = dict[tuple[int, int], int]
ThreeIntOptIntMapT: TypeAlias = dict[tuple[int, int, int, Optional[int]], int]

# More explicit map aliases for common keys
DeptCollegeMapT: TypeAlias = dict[tuple[str, int], int]  # (dept_code, college_id) -> id
DeptCourseMapT: TypeAlias = dict[tuple[int, str], int]  # (dept_id, course_no) -> id
CurriculumCourseMapT: TypeAlias = dict[tuple[int, int], int]
SectionKeyMapT: TypeAlias = dict[tuple[int, int, int, Optional[int]], int]
