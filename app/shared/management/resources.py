"""Shared resource registry for import/export commands."""

from __future__ import annotations

from collections import OrderedDict
from typing import Sequence

from import_export import resources

from app.academics.admin.resources import CourseResource, CurriculumCourseResource
from app.people.admin.resources import DonorResource, FacultyResource, StudentResource
from app.people.models.staffs import Staff
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
    ("Faculty", FacultyResource, ("people_all_faculty.tsv",)),
    ("Staff", StaffResource, ("people_all_staff.tsv",)),
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
    ("Student", StudentResource, ("people_all_student.tsv",)),
    (
        "Grade",
        GradeResource,
        (
            "full_grades.tsv",  # new file combining gradesheets and oldgrades
            # "full_grades_students.tsv"  # file with student information
            # "registry_gradeSheets.csv",
        ),
    ),
    (
        "LegacyRegistration",
        LegacyRegistrationResource,
        (
            "UM_StudentsCourses.csv",
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
