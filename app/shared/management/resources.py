"""Shared resource registry for import/export commands."""

from __future__ import annotations

from collections import OrderedDict
from typing import Sequence


from app.academics.admin.resources import CourseResource, CurriCourseResource
from app.people.admin.resources import (
    DonorResource,
    FacultyResource,
    StaffResource,
    StdResource,
)
from app.people.models.staffs import Staff
from app.registry.admin.resources_legacy import (
    LegacyRegioResource,
)
from app.shared.types import DirectoryResourceEntry, ModelResourceType
from app.spaces.admin.resources import RoomResource
from app.timetable.admin.core_resources import SemResource
from app.timetable.admin.session_resources import SecSessionResource

# Unified directory-backed resources (legacy included)
DIRECTORY_RESOURCE_ENTRIES: Sequence[DirectoryResourceEntry] = (
    ("Room", RoomResource, ("space_room.csv",)),
    ("Semester", SemResource, ("academicyear_semester.csv",)),
    ("Staff", StaffResource, ("people_full_staff.tsv",)),
    ("Donor", DonorResource, ("people_donors.csv",)),
    ("Faculty", FacultyResource, ("people_full_faculty.tsv",)),
    ("Student", StdResource, ("people_full_student.tsv",)),
    ("Course", CourseResource, ("academic_course.csv",)),
    ("SecSession", SecSessionResource, ("timetable_sessions_25-26s2.tsv",)),
    ("CurriCourse", CurriCourseResource, ("academic_curriculum_course.csv",)),
    (
        "LegacyRegistration",
        LegacyRegioResource,
        (
            "UM_StudentsCrs.csv",
            "registry_registration.csv",
            "studentcourses.csv",
        ),
    ),
)

RESOURCE_CHOICES: Sequence[str] = tuple(
    OrderedDict.fromkeys([name for name, *_ in DIRECTORY_RESOURCE_ENTRIES]).keys()
)

RESOURCE_REGISTRY: dict[str, ModelResourceType] = {
    name: resource_cls for name, resource_cls, _ in DIRECTORY_RESOURCE_ENTRIES
}
