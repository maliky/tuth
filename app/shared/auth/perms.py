"""Authentication constants used during data population."""

from dataclasses import dataclass
from enum import Enum

from typing import Type
from django.apps import apps
from django.db.models import Model

TEST_PW = "test"

APP_MODELS = {
    "academics": [
        "college",
        "department",
        "course",
        "curriculum",
        "major",
        "minor",
        "majorprogram",
        "minorprogram",
        "program",
        "prerequisite",
    ],
    "people": ["student", "faculty", "staff", "donor", "roleassignment"],
    "spaces": ["space", "room"],
    "timetable": [
        "academicyear",
        "semester",
        "term",
        "schedule",
        "secsession",
        "section",
    ],
    "registry": ["document", "registration", "grade", "gradevalue"],
    "finance": [
        "financialrecord",
        "payment",
        "paymenthistory",
        "scholarship",
        "sectionfee",
    ],
}


@dataclass(frozen=True)
class RoleInfo:
    """Metadata attached to each user role."""

    code: str
    label: str
    model_path: str
    default_college: str | None = None

    @property
    def model(self) -> Type[Model]:
        """Get the model avoiding circular imports."""
        app_label, model_name = self.model_path.split(".")
        return apps.get_model(app_label, model_name)

    @property
    def group(self) -> str:
        """Standardize the group name."""
        return self.code.capitalize()

    @property
    def rights(self) -> dict[str, list[str]]:
        """Returns the rights for a user_role"""
        return ROLE_MATRIX.get(self.code, {})


class UserRole(Enum):
    """Self-describing user roles used throughout the app."""

    DONOR = RoleInfo("donor", "Donor", "people.Donor")
    STUDENT = RoleInfo("student", "Student", "people.Student")
    PROSPECTING_STUDENT = RoleInfo(
        "prospecting_student", "Prospecting Student", "people.Student"
    )

    STAFF = RoleInfo("staff", "Staff", "people.Staff")
    FACULTY = RoleInfo("faculty", "Faculty", "people.Faculty", "COAS")
    CHAIR = RoleInfo("chair", "Chair", "people.Faculty", "COAS")
    DEAN = RoleInfo("dean", "Dean", "people.Faculty", "COAS")
    VPAA = RoleInfo("vpaa", "Vice President Academic Affairs", "people.Staff")

    ENROLLMENT = RoleInfo("enrollment", "Enrollment", "people.Staff")
    ENROLLMENT_OFFICER = RoleInfo(
        "enrollment_officer", "Enrollment Officer", "people.Staff"
    )
    FINANCE = RoleInfo("finance", "Finance", "people.Staff")
    FINANCE_OFFICER = RoleInfo("finance_officer", "Finance Officer", "people.Staff")
    REGISTRAR = RoleInfo("registrar", "Registrar", "people.Staff")
    REGISTRAR_OFFICER = RoleInfo("registrar_officer", "Registrar Officer", "people.Staff")
    IT = RoleInfo("it", "It", "people.Staff")


ROLE_MATRIX = {
    "donor": {"view": ["student", "donor"]},
    "cashier": {
        "add": ["payment", "paymenthistory"],
        "view": ["payment", "paymenthistory"],
    },
    "chair": {
        "add": ["course", "program", "section"],
        "change": ["course", "program", "section"],
        "view": [
            "college",
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "faculty",
            "space",
            "room",
            "academicyear",
            "semester",
            "term",
            "section",
        ],
    },
    "dean": {
        "add": [
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "section",
        ],
        "change": [
            "college",
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "section",
        ],
        "delete": ["minor"],
        "view": [
            "college",
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "faculty",
            "space",
            "room",
            "academicyear",
            "semester",
            "term",
            "section",
        ],
    },
    "enrollment_officer": {
        "add": ["student", "document", "registration"],
        "change": ["student", "registration"],
        "view": ["student", "document", "registration"],
        "delete": ["student", "document", "registration"],
    },
    "enrollment": {
        "add": ["student", "document", "registration"],
        "change": ["student", "registration"],
        "view": ["student", "document", "registration"],
    },
    "faculty": {
        "add": ["grade"],
        "view": [
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "student",
            "faculty",
            "schedule",
            "secsession",
            "section",
            "grade",
        ],
    },
    "finance_officer": {
        "add": ["donor", "financialrecord", "scholarship", "sectionfee"],
        "change": [
            "donor",
            "financialrecord",
            "payment",
            "paymenthistory",
            "scholarship",
            "sectionfee",
        ],
        "delete": ["donor", "payment", "scholarship", "sectionfee"],
        "view": [
            "student",
            "donor",
            "document",
            "financialrecord",
            "payment",
            "paymenthistory",
            "scholarship",
            "sectionfee",
        ],
    },
    "prospecting_student": {
        "add": ["document"],
        "view": [
            "college",
            "course",
            "curriculum",
            "space",
            "room",
            "academicyear",
            "semester",
            "term",
            "document",
        ],
    },
    "registrar": {
        "add": [
            "prerequisite",
            "space",
            "room",
            "semester",
            "term",
            "schedule",
            "secsession",
            "section",
            "document",
            "registration",
        ],
        "change": [
            "prerequisite",
            "student",
            "space",
            "room",
            "semester",
            "term",
            "schedule",
            "secsession",
            "section",
            "document",
            "registration",
            "grade",
        ],
        "delete": [
            "student",
            "room",
            "schedule",
            "secsession",
            "section",
            "document",
            "registration",
            "grade",
        ],
        "view": [
            "college",
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "student",
            "faculty",
            "staff",
            "space",
            "room",
            "academicyear",
            "semester",
            "term",
            "schedule",
            "secsession",
            "section",
            "document",
            "registration",
            "grade",
            "financialrecord",
            "payment",
            "paymenthistory",
            "scholarship",
            "sectionfee",
        ],
    },
    "student": {
        "add": ["document", "registration"],
        "view": [
            "college",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "student",
            "space",
            "room",
            "academicyear",
            "semester",
            "term",
            "schedule",
            "secsession",
            "section",
            "document",
            "registration",
            "grade",
            "financialrecord",
            "payment",
            "paymenthistory",
            "scholarship",
        ],
    },
    "vpaa": {
        "add": [
            "college",
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "faculty",
            "staff",
            "space",
            "academicyear",
            "semester",
            "term",
        ],
        "change": [
            "college",
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "faculty",
            "staff",
            "academicyear",
            "semester",
            "term",
            "schedule",
            "secsession",
            "section",
            "payment",
            "scholarship",
            "sectionfee",
        ],
        "delete": [
            "college",
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "faculty",
            "staff",
            "space",
            "academicyear",
            "semester",
            "term",
        ],
        "view": [
            "college",
            "department",
            "course",
            "curriculum",
            "major",
            "minor",
            "program",
            "prerequisite",
            "student",
            "faculty",
            "staff",
            "donor",
            "space",
            "room",
            "academicyear",
            "semester",
            "term",
            "schedule",
            "secsession",
            "section",
            "document",
            "registration",
            "grade",
            "financialrecord",
            "payment",
            "paymenthistory",
            "scholarship",
            "sectionfee",
        ],
    },
}
