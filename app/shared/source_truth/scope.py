"""Explicit source scopes used by the import-ready truth builder."""

from __future__ import annotations

from typing import TypeAlias

TableNamesT: TypeAlias = frozenset[str]
FileNamesT: TypeAlias = tuple[str, ...]

SMARTSCHOOL_IMPORT_TABLES: TableNamesT = frozenset(
    {
        "UM_Courses",
        "UM_CoursesLevels",
        "UM_CurriculumCourses",
        "UM_Curriculums",
        "UM_GradeSheet",
        "UM_Oldgrades",
        "UM_Programs",
        "UM_Registrations",
        "UM_Students",
        "UM_StudentsCourses",
        "payments",
    }
)

FUNDAMENTAL_IMPORT_FILES: FileNamesT = (
    "academic_course.csv",
    "academic_curriculum_course.csv",
    "academics_curriculums.csv",
    "finance_payments.csv",
    "full_grades.tsv",
    "people_full_student.tsv",
    "registry_registration.csv",
)

GRAPRO_IMPORT_FILES: FileNamesT = (
    "Accounts.csv",
    "Courses.csv",
)

TUCURRICULA_IMPORT_FILES: FileNamesT = (
    "academic_course.tsv",
    "academic_curriculum.tsv",
    "academic_curriculum_course.tsv",
    "academic_curriculum_requirement.tsv",
)
