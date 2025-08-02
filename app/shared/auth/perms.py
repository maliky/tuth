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
        return apps.get_model(f"app.{app_label}", model_name)


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


PERMISSION_MATRIX = {
    "college": {
        "view": ["dean", "chair", "vpaa", "registrar", "student", "prospecting_student"],
        "add": ["vpaa"],
        "change": ["vpaa", "dean"],
        "delete": ["vpaa"],
    },
    "department": {
        "view": ["dean", "chair", "vpaa", "registrar", "faculty"],
        "add": ["dean", "vpaa"],
        "change": ["dean", "vpaa"],
        "delete": ["vpaa"],
    },
    "course": {
        "view": [
            "dean",
            "chair",
            "faculty",
            "registrar",
            "vpaa",
            "student",
            "prospecting_student",
        ],
        "add": ["chair", "dean", "vpaa"],
        "change": ["chair", "dean", "vpaa"],
        "delete": ["vpaa"],
    },
    "curriculum": {
        "view": [
            "dean",
            "chair",
            "faculty",
            "registrar",
            "vpaa",
            "student",
            "prospecting_student",
        ],
        "add": ["dean", "vpaa"],
        "change": ["dean", "vpaa"],
        "delete": ["vpaa"],
    },
    "major": {
        "view": ["dean", "chair", "vpaa", "registrar", "faculty", "student"],
        "add": ["dean", "vpaa"],
        "change": ["dean", "vpaa"],
        "delete": ["vpaa"],
    },
    "minor": {
        "view": ["dean", "chair", "vpaa", "registrar", "faculty", "student"],
        "add": ["dean", "vpaa"],
        "change": ["dean", "vpaa"],
        "delete": ["dean", "vpaa"],
    },
    "program": {
        "view": ["dean", "chair", "vpaa", "registrar", "faculty", "student"],
        "add": ["chair", "dean", "vpaa"],
        "change": ["chair", "dean", "vpaa"],
        "delete": ["vpaa"],
    },
    "prerequisite": {
        "view": ["dean", "chair", "registrar", "vpaa"],
        "add": ["dean", "registrar", "vpaa"],
        "change": ["dean", "registrar", "vpaa"],
        "delete": ["vpaa"],
    },
    "student": {
        "view": ["registrar", "faculty", "finance_officer", "vpaa", "student"],
        "add": ["enrollment_officer"],
        "change": ["enrollment_officer", "registrar"],
        "delete": ["registrar"],
    },
    "faculty": {
        "view": ["dean", "chair", "vpaa", "registrar", "faculty"],
        "add": ["vpaa"],
        "change": ["vpaa"],
        "delete": ["vpaa"],
    },
    "staff": {
        "view": ["vpaa", "registrar"],
        "add": ["vpaa"],
        "change": ["vpaa"],
        "delete": ["vpaa"],
    },
    "donor": {
        "view": ["finance_officer", "vpaa"],
        "add": ["finance_officer"],
        "change": ["finance_officer"],
        "delete": ["finance_officer"],
    },
    "space": {
        "view": ["registrar", "vpaa", "dean", "chair", "student", "prospecting_student"],
        "add": ["registrar", "vpaa"],
        "change": ["registrar"],
        "delete": ["vpaa"],
    },
    "room": {
        "view": ["registrar", "vpaa", "dean", "chair", "student", "prospecting_student"],
        "add": ["registrar"],
        "change": ["registrar"],
        "delete": ["registrar"],
    },
    "academicyear": {
        "view": ["vpaa", "registrar", "dean", "chair", "student", "prospecting_student"],
        "add": ["vpaa"],
        "change": ["vpaa"],
        "delete": ["vpaa"],
    },
    "semester": {
        "view": ["vpaa", "registrar", "dean", "chair", "student", "prospecting_student"],
        "add": ["registrar", "vpaa"],
        "change": ["vpaa", "registrar"],
        "delete": ["vpaa"],
    },
    "term": {
        "view": ["vpaa", "registrar", "dean", "chair", "student", "prospecting_student"],
        "add": ["registrar", "vpaa"],
        "change": ["vpaa", "registrar"],
        "delete": ["vpaa"],
    },
    "schedule": {
        "view": ["registrar", "faculty", "vpaa", "student"],
        "add": ["registrar"],
        "change": ["registrar", "vpaa"],
        "delete": ["registrar"],
    },
    "session": {
        "view": ["registrar", "faculty", "vpaa", "student"],
        "add": ["registrar"],
        "change": ["registrar", "vpaa"],
        "delete": ["registrar"],
    },
    "section": {
        "view": ["dean", "chair", "faculty", "registrar", "vpaa", "student"],
        "add": ["registrar", "chair", "dean"],
        "change": ["registrar", "chair", "dean", "vpaa"],
        "delete": ["registrar"],
    },
    "document": {
        "view": [
            "registrar",
            "finance_officer",
            "enrollment_officer",
            "vpaa",
            "student",
            "prospecting_student",
        ],
        "add": ["registrar", "enrollment_officer", "student", "prospecting_student"],
        "change": ["registrar"],
        "delete": ["registrar"],
    },
    "registration": {
        "view": ["registrar", "enrollment_officer", "vpaa", "student"],
        "add": ["registrar", "enrollment_officer", "student"],
        "change": ["registrar", "enrollment_officer"],
        "delete": ["registrar"],
    },
    "classroster": {
        "view": ["registrar", "vpaa", "dean", "chair", "faculty"],
        "add": ["registrar"],
        "change": ["registrar"],
        "delete": ["registrar"],
    },
    "grade": {
        "view": ["registrar", "faculty", "vpaa", "student"],
        "add": ["faculty"],
        "change": ["registrar"],
        "delete": ["registrar"],
    },
    "financialrecord": {
        "view": ["finance_officer", "registrar", "vpaa", "student"],
        "add": ["finance_officer"],
        "change": ["finance_officer"],
        "delete": [],
    },
    "payment": {
        "view": ["cashier", "finance_officer", "registrar", "vpaa", "student"],
        "add": ["cashier"],
        "change": ["finance_officer", "vpaa"],
        "delete": ["finance_officer"],
    },
    "paymenthistory": {
        "view": ["cashier", "finance_officer", "registrar", "vpaa", "student"],
        "add": ["cashier"],
        "change": ["finance_officer"],
        "delete": [],
    },
    "scholarship": {
        "view": ["finance_officer", "registrar", "vpaa", "student"],
        "add": ["finance_officer"],
        "change": ["finance_officer", "vpaa"],
        "delete": ["finance_officer"],
    },
    "sectionfee": {
        "view": ["finance_officer", "registrar", "vpaa"],
        "add": ["finance_officer"],
        "change": ["finance_officer", "vpaa"],
        "delete": ["finance_officer"],
    },
}
