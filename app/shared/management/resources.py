"""Shared resource registry for import/export commands."""

from typing import Sequence, Tuple
from collections import OrderedDict
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
from import_export import resources

FILEMAP: dict[str, Tuple[str, type[resources.ModelResource]]] = OrderedDict(
    [
        ("people_instructors.head.csv", ("Faculty", FacultyResource)),
        ("people_donors.csv", ("Donor", DonorResource)),
        ("people_students.csv", ("Student", StudentResource)),
        ("space_room.csv", ("Room", RoomResource)),
        ("academic_course.csv", ("Course", CourseResource)),
        (
            "academic_curriculum_course.csv",
            ("CurriculumCourse", CurriculumCourseResource),
        ),
        ("academicyear_semester.csv", ("Semester", SemesterResource)),
        ("grades-registry.csv", ("Grade", GradeResource)),
        ("registry_gradeSheets.csv", ("LegacyGrade", LegacyGradeSheetResource)),
        (
            "registry_gradeSheets.head.csv",
            ("LegacyGrade", LegacyGradeSheetResource),
        ),
        ("gradesheets.head.csv", ("LegacyGrade", LegacyGradeSheetResource)),
        ("oldgrades.head.csv", ("LegacyGrade", LegacyGradeSheetResource)),
        ("UM_GradeSheet.head.csv", ("LegacyGrade", LegacyGradeSheetResource)),
        ("UM_TransferGrades.head.csv", ("LegacyGrade", LegacyGradeSheetResource)),
        (
            "registry_registration.head.csv",
            ("LegacyRegistration", LegacyRegistrationResource),
        ),
        (
            "studentcourses.head.csv",
            ("LegacyRegistration", LegacyRegistrationResource),
        ),
        (
            "UM_StudentsCourses.head.csv",
            ("LegacyRegistration", LegacyRegistrationResource),
        ),
    ]
)

RESOURCE_REGISTRY: dict[str, ModelResourceType] = {
    "Grade": GradeResource,
    "LegacyGrade": LegacyGradeSheetResource,
    "LegacyRegistration": LegacyRegistrationResource,
}
DIRECTORY_RESOURCES: Sequence[DirectoryResourceEntry] = (
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
            # StudentInfo.csv  # may  have usefull info
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
)
LEGACY_DIRECTORY_RESOURCES: Sequence[DirectoryResourceEntry] = (
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
        ),
    ),
)
RESOURCE_CHOICES = tuple(
    OrderedDict.fromkeys(
        list(RESOURCE_REGISTRY.keys())
        + [key for key, *_ in DIRECTORY_RESOURCES]
        + [key for key, *_ in LEGACY_DIRECTORY_RESOURCES]
    ).keys()
)
