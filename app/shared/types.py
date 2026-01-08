"""Personal Types."""

from __future__ import annotations

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Sequence,
    Tuple,
    TypeAlias,
    TypeVar,
    Union,
)

from django.db.models import Model, QuerySet
from import_export import resources

if TYPE_CHECKING:
    from app.academics.models.course import Course
    from app.people.models.core import AbstractPerson
    from app.people.models.donor import Donor
    from app.people.models.faculty import Faculty
    from app.people.models.staffs import Staff
    from app.people.models.student import Student
    from app.registry.models import Registration
    from app.timetable.models import Section


_T = TypeVar("_T")
ModelT = TypeVar("ModelT", bound=Model)
PersonT = TypeVar("PersonT", "Staff", "Donor", "Student")
AbstractPersonT = TypeVar("AbstractPersonT", bound="AbstractPerson")
Score = float

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
