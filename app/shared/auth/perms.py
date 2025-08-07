"""Authentication constants used during data population."""

from dataclasses import dataclass
from enum import Enum

from typing import Type
from django.apps import apps
from django.db.models import Model

TEST_PW = "test"


DEFAULT_ROLE_TO_COLLEGE = {
    "dean": "COAS",  # map role → default college code
    "chair": "COAS",
    "lecturer": "COAS",
    "assistant_professor": "COAS",
    "associate_professor": "COAS",
    "professor": "COAS",
    "technician": "COAS",
    "lab_technician": "COAS",
    "faculty": "COAS",
}

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

    label: str
    code: str
    model_path: str
    default_college: str | None = None

    @property
    def model(self) -> Type[Model]:
        """Get the model avoiding circular imports."""
        app_label, model_name = self.model_path.split(".")
        return apps.get_model(app_label, model_name)


class UserRole(Enum):
    """Self-describing user roles used throughout the app."""

    DONOR = RoleInfo("Donor", "donor", "people.Donor")
    STUDENT = RoleInfo("Student", "student", "people.Student")
    PROSPECTING_STUDENT = RoleInfo(
        "Prospecting Student", "prospecting_student", "people.Student"
    )

    STAFF = RoleInfo("Staff", "staff", "people.Staff")
    FACULTY = RoleInfo("Faculty", "faculty", "people.Faculty", "COAS")
    CHAIR = RoleInfo("Chair", "chair", "people.Faculty", "COAS")
    DEAN = RoleInfo("Dean", "dean", "people.Faculty", "COAS")
    VPAA = RoleInfo("Vice President Academic Affairs", "vpaa", "people.Staff")

    ENROLLMENT = RoleInfo("Enrollment", "enrollment", "people.Staff")
    ENROLLMENT_OFFICER = RoleInfo(
        "Enrollment Officer", "enrollment_officer", "people.Staff"
    )
    FINANCE = RoleInfo("Finance", "finance", "people.Staff")
    FINANCE_OFFICER = RoleInfo("Finance Officer", "finance_officer", "people.Staff")
    REGISTRAR = RoleInfo("Registrar", "registrar", "people.Staff")
    REGISTRAR_OFFICER = RoleInfo("Registrar Officer", "registrar_officer", "people.Staff")
    IT = RoleInfo("It", "it", "people.Staff")


ROLE_MATRIX = {
    "Donor":{"view": ["student", "donor"]},
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
        "view": ["document", "registration"],
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
