"""Authentication constants used during data population."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Type

from django.apps import apps
from django.contrib.auth.models import Group
from django.db.models import Model

from app.academics.choices import COLLEGE_CODE

logger = logging.getLogger(__name__)

TEST_PW = "test2Façil007!"

APP_MODELS = {
    "academics": [
        "college",
        "department",
        "course",
        "curriculum",
        "major",
        "minor",
        "majorcurriculumcourse",
        "minorcurriculumcourse",
        "curriculumcourse",
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
    "registry": [
        "registration",
        "grade",
        "gradevalue",
        "documentstudent",
        "documentdonor",
        "documentstaff",
        "documentstatus",
    ],
    "finance": [
        "invoice",
        "scholarship",
        "sectionfee",
        "clearancestatus",
        "paymentmethod",
        "feetype",
        "payment",
    ],
    "auth": ["user", "group"],
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
    def group(self) -> Group:
        """Return a or the Group(s)."""
        gp, _ = Group.objects.get_or_create(name=self.label)
        return gp

    @property
    def rights(self) -> dict[str, list[str]]:
        """Return the expanded list of rights for the user_role."""
        return {
            actions: expand_rights(models)
            for actions, models in ROLE_MATRIX.get(self.code, {}).items()
        }

    @property
    def college(self) -> str:
        """Return the default college."""
        return self.default_college or COLLEGE_CODE["deft"]


class UserRole(Enum):
    """Self-describing user roles used throughout the app."""

    DONOR = RoleInfo("donor", "Donor", "people.Donor")
    CASHIER = RoleInfo("cashier", "Cashier", "people.Staff")
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
    "staff": {"view": ["student"]},
    "donor": {"view": ["student", "donor"]},
    "cashier": {
        "add": ["invoice", "payment"],
        "view": ["invoice", "payment", "paymentmethod"],
    },
    "chair": {
        "add": ["course", "curriculumcourse", "section"],
        "change": ["course", "curriculumcourse", "section"],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "faculty",
            "major",
            "minor",
            "prerequisite",
            "curriculumcourse",
            "room",
            "section",
            "semester",
            "space",
            "term",
        ],
    },
    "dean": {
        "add": [
            "course",
            "curriculum",
            "department",
            "major",
            "minor",
            "prerequisite",
            "curriculumcourse",
            "section",
        ],
        "change": [
            "college",
            "course",
            "curriculum",
            "department",
            "major",
            "minor",
            "prerequisite",
            "curriculumcourse",
            "section",
        ],
        "delete": ["minor"],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "faculty",
            "major",
            "minor",
            "prerequisite",
            "curriculumcourse",
            "room",
            "section",
            "semester",
            "space",
            "term",
        ],
    },
    "enrollment_officer": {
        "view": [
            "Academics",
            "documentstudent",
            "registration",
            "semester",
            "student",
            "user",
        ],
        "add": ["student", "documentstudent", "curriculum"],
        "change": [
            "curriculum",
            "department",
            "documentstudent",
            "registration",
            "student",
            "user",
        ],
        "delete": ["student", "documentstudent", "curriculum"],
    },
    "enrollment": {
        "view": [
            "college",
            "curriculum",
            "department",
            "documentstudent",
            "registration",
            "semester",
            "student",
        ],
        "add": ["student", "documentstudent"],
        "change": ["student", "registration", "documentstudent"],
    },
    "faculty": {
        "add": ["grade"],
        "view": [
            "course",
            "curriculum",
            "department",
            "faculty",
            "grade",
            "major",
            "minor",
            "curriculumcourse",
            "schedule",
            "secsession",
            "section",
            "student",
        ],
    },
    "finance_officer": {
        "add": [
            "documentdonor",
            "documentstaff",
            "donor",
            "payment",
            "paymentmethod",
            "scholarship",
            "sectionfee",
        ],
        "change": [
            "documentdonor",
            "payment",
            "paymentmethod",
            "documentstaff",
            "donor",
            "invoice",
            "scholarship",
            "sectionfee",
        ],
        "delete": ["donor", "invoice", "scholarship", "sectionfee"],
        "view": [
            "documentdonor",
            "documentstaff",
            "donor",
            "invoice",
            "payment",
            "paymentmethod",
            "scholarship",
            "sectionfee",
            "student",
        ],
    },
    "finance": {
        "add": [
            "documentdonor",
            "donor",
            "payment",
            "scholarship",
            "sectionfee",
        ],
        "change": [
            "documentdonor",
            "donor",
            "invoice",
            "payment",
            "paymentmethod",
            "scholarship",
            "sectionfee",
        ],
        "delete": ["donor", "invoice", "scholarship", "sectionfee"],
        "view": [
            "documentdonor",
            "documentstaff",
            "documentstudent",
            "donor",
            "invoice",
            "payment",
            "paymentmethod",
            "scholarship",
            "sectionfee",
            "student",
        ],
    },
    "prospecting_student": {
        "add": ["documentstudent"],
        "delete": ["documentstudent"],
        "change": ["documentstudent"],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "documentstudent",
            "room",
            "semester",
            "space",
            "term",
            "documentstudent",
        ],
    },
    "registrar": {
        "add": ["schedule", "secsession", "section", "registration", "grade"],
        "change": [
            "grade",
            "registration",
            "schedule",
            "secsession",
            "section",
            "student",
        ],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "documents",
            "faculty",
            "payment",
            "paymentmethod",
            "grade",
            "major",
            "minor",
            "invoice",
            "prerequisite",
            "curriculumcourse",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "sectionfee",
            "semester",
            "space",
            "staff",
            "student",
            "term",
        ],
    },
    "registrar_officer": {
        "add": [
            "documents",
            "prerequisite",
            "registration",
            "room",
            "schedule",
            "secsession",
            "section",
            "semester",
            "space",
            "term",
        ],
        "change": [
            "documents",
            "grade",
            "prerequisite",
            "registration",
            "room",
            "schedule",
            "secsession",
            "section",
            "semester",
            "space",
            "student",
            "term",
        ],
        "delete": [
            "documents",
            "grade",
            "registration",
            "room",
            "schedule",
            "secsession",
            "section",
            "student",
        ],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "documents",
            "faculty",
            "grade",
            "major",
            "minor",
            "invoice",
            "payment",
            "paymentmethod",
            "prerequisite",
            "curriculumcourse",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "sectionfee",
            "semester",
            "space",
            "staff",
            "student",
            "term",
        ],
    },
    "student": {
        "add": ["documentstudent", "registration"],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "documentstudent",
            "grade",
            "major",
            "minor",
            "invoice",
            "payment",
            "curriculumcourse",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "semester",
            "space",
            "student",
            "term",
        ],
    },
    "vpaa": {
        "add": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "faculty",
            "major",
            "minor",
            "prerequisite",
            "curriculumcourse",
            "semester",
            "space",
            "staff",
            "term",
        ],
        "change": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "faculty",
            "major",
            "minor",
            "invoice",
            "prerequisite",
            "curriculumcourse",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "sectionfee",
            "semester",
            "staff",
            "term",
        ],
        "delete": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "faculty",
            "major",
            "minor",
            "prerequisite",
            "curriculumcourse",
            "semester",
            "space",
            "staff",
            "term",
        ],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "documents",
            "donor",
            "faculty",
            "grade",
            "major",
            "minor",
            "invoice",
            "payment",
            "paymentmethod",
            "prerequisite",
            "curriculumcourse",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "sectionfee",
            "semester",
            "space",
            "staff",
            "student",
            "term",
        ],
    },
    "it": {
        "add": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "faculty",
            "major",
            "minor",
            "prerequisite",
            "curriculumcourse",
            "semester",
            "space",
            "staff",
            "term",
        ],
        "change": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "faculty",
            "major",
            "minor",
            "invoice",
            "prerequisite",
            "curriculumcourse",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "sectionfee",
            "semester",
            "staff",
            "term",
        ],
        "delete": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "faculty",
            "major",
            "minor",
            "prerequisite",
            "curriculumcourse",
            "semester",
            "space",
            "staff",
            "term",
        ],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "department",
            "documents",
            "donor",
            "faculty",
            "grade",
            "major",
            "minor",
            "invoice",
            "payment",
            "paymentmethod",
            "prerequisite",
            "curriculumcourse",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "sectionfee",
            "semester",
            "space",
            "staff",
            "student",
            "term",
        ],
    },
}


def validate_role_matrix() -> set[str]:
    """Ensure Userrole codes match role_matrix keys."""
    ur = {ur.value.code for ur in UserRole}
    rm = set(ROLE_MATRIX.keys())
    only_in_ur = ur - rm
    only_in_rm = rm - ur
    msg = f"{only_in_rm} only in ROLLE MATRIX. " if only_in_rm else ""
    msg += f"{only_in_ur} only in UserRole. " if only_in_ur else ""
    if msg:
        logger.error(msg)
        raise ValueError(msg)
    return only_in_rm | only_in_ur


def expand_rights(models: list[str]) -> list[str]:
    """Expand shorthand model tokens to explicit model names.

    A capitalized application name, e.g. ``Academics``, expands to all models
    defined for that app in :data:`APP_MODELS`.

    An Application named suffixed by ``-model`` means exclusions,
    e.g. ``Academics-college``, expands to all models for ``academics`` except
    ``college``.
    """

    expanded: list[str] = []
    for item in models:
        if not item:
            continue

        if item[0].isupper():
            parts = item.split("-")
            app_label = parts[0].lower()
            exclusions = set(parts[1:])
            expanded += [m for m in APP_MODELS.get(app_label, []) if m not in exclusions]
        elif item == "documents":
            expanded += [m for m in APP_MODELS["registry"] if m.startswith("document")]
        else:
            expanded += [item]

    return expanded
