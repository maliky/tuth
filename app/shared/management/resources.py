"""Shared resource registry for import/export commands."""

from __future__ import annotations

from collections import OrderedDict
from typing import Sequence

from import_export import resources

from app.academics.admin.resources import CourseResource, CurriculumCourseResource
from app.people.admin.resources import DonorResource, FacultyResource, StudentResource
from app.registry.admin.resources import GradeResource
from app.registry.admin.resources_legacy import (
    LegacyGradeSheetResource,
    LegacyRegistrationResource,
)
from app.shared.types import DirectoryResourceEntry, ModelResourceType
from app.spaces.admin.resources import RoomResource
from app.timetable.admin.resources.core import SemesterResource

# Unified directory-backed resources (legacy included)
DIRECTORY_RESOURCE_ENTRIES: Sequence[DirectoryResourceEntry] = (
    ("Faculty", FacultyResource, ("people_instructors.csv",)),
    ("Room", RoomResource, ("space_room.csv",)),
    ("Course", CourseResource, ("academic_course.csv",)),
    (
        "CurriculumCourse",
        CurriculumCourseResource,
        ("academic_curriculum_course.csv",),
    ),
    (
        "Semester",
        SemesterResource,
        ("academicyear_semester.csv",),
    ),
    ("Donor", DonorResource, ("people_donors.csv",)),
    (
        "Student",
        StudentResource,
        (
            "people_students.csv",
            "UM_students.csv",
        ),
    ),
    (
        "Grade",
        GradeResource,
        (
            "registry_gradeSheets.csv",
            "gradesheets.csv",
        ),
    ),
    (
        "LegacyRegistration",
        LegacyRegistrationResource,
        (
            "registry_registration.csv",
            "studentcourses.csv",
            "UM_StudentsCourses.csv",
        ),
    ),
    (
        "LegacyGrade",
        LegacyGradeSheetResource,
        (
            "oldgrades.csv",
            "UM_TransferGrades.csv",
            "registry_gradeSheets.csv",
            "gradesheets.csv",
        ),
    ),
)

# Mapping of label -> ResourceClass for single-file imports
RESOURCE_REGISTRY: dict[str, ModelResourceType] = {
    "Grade": GradeResource,
    "LegacyGrade": LegacyGradeSheetResource,
    "LegacyRegistration": LegacyRegistrationResource,
}

RESOURCE_CHOICES: Sequence[str] = tuple(
    OrderedDict.fromkeys([name for name, *_ in DIRECTORY_RESOURCE_ENTRIES]).keys()
)

__all__ = [
    "DIRECTORY_RESOURCE_ENTRIES",
    "RESOURCE_REGISTRY",
    "RESOURCE_CHOICES",
]
