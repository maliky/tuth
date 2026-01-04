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
    ("Faculty", FacultyResource, ("people_full_faculty.tsv",)),
    ("Staff", Staff, ("people_full_staff.tsv",)),    
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
    # "UM_students.utf8.tsv"  #  people_students.csv is a cleaned version of UM
    #  "StudentInfo.csv"
    (
        "Student",
        StudentResource,
        ("people_full_student.tsv",),
    ),
    (
        "Grade",
        GradeResource,
        (
            # "gradesheets.utf8.tsv",
            # "oldgrades.utf8.tsv",
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
    # (
    #     "LegacyGrade",
    #     LegacyGradeSheetResource,
    #     (
    #         # Strange I cannot find the file. Need to look in db archives if it was useful
    #         # "UM_TransferGrades.csv",
    #         # "gradesheets.utf8.tsv",
    #         # "oldgrades.utf8.tsv",
    #         # "registry_gradeSheets.csv",
    #     ),
    # ),
)

RESOURCE_CHOICES: Sequence[str] = tuple(
    OrderedDict.fromkeys([name for name, *_ in DIRECTORY_RESOURCE_ENTRIES]).keys()
)

RESOURCE_REGISTRY: dict[str, ModelResourceType] = {
    name: resource_cls for name, resource_cls, _ in DIRECTORY_RESOURCE_ENTRIES
}
