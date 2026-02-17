"""Personal Types."""

from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Mapping,
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
    from app.timetable.models.section import Section
    from app.timetable.models.semester import Semester


_T = TypeVar("_T")
ModelT = TypeVar("ModelT", bound=Model)
PersonT = TypeVar("PersonT", "Staff", "Donor", "Student")  # No Faculty?
AbstractPersonT = TypeVar(
    "AbstractPersonT", bound="AbstractPerson"
)  # Faculty included here
Score = float

Row = dict[str, Any]
Transform = Callable[[Row], Row]
RowStrOptT: TypeAlias = Mapping[str, Optional[str]]

SectionQuery: TypeAlias = QuerySet["Section"]
CrsQuery: TypeAlias = QuerySet["Course"]
FacultyQuery: TypeAlias = QuerySet["Faculty"]
StdQuery: TypeAlias = QuerySet["Student"]
RegistrationQuery: TypeAlias = QuerySet["Registration"]
SemesterCodeT: TypeAlias = Tuple[str, int]

FieldT: TypeAlias = Union[
    list[str | list[str] | tuple[str, ...] | tuple[()]],
    tuple[str | list[str] | tuple[str, ...] | tuple[()], ...],
    tuple[()],
]

OpenRegistrationSemesterResultT: TypeAlias = Tuple[Optional["Semester"], Optional[str]]
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
DeptCrsMapT: TypeAlias = dict[tuple[int, str], int]  # (dept_id, course_no) -> id
CurriCrsMapT: TypeAlias = dict[tuple[int, int], int]
SectionKeyMapT: TypeAlias = dict[tuple[int, int, int, Optional[int]], int]

ScheduleKeyT: TypeAlias = tuple[int, time, time | None]
RoomKeyT: TypeAlias = tuple[str, str]
SectionKeyT: TypeAlias = tuple[int, int, int]
SessionKeyT: TypeAlias = tuple[int, int]
ScheduleCacheT: TypeAlias = dict[ScheduleKeyT, int]
RoomCacheT: TypeAlias = dict[RoomKeyT, int]
SectionCacheT: TypeAlias = dict[SectionKeyT, tuple[int, Optional[int]]]
SessionCacheT: TypeAlias = dict[SessionKeyT, tuple[int, int]]
