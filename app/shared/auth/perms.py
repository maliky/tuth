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
        "majorcurricrs",
        "minorcurricrs",
        "curricrs",
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
        "docstd",
        "docdonor",
        "docstaff",
        "docstatus",
    ],
    "finance": [
        "crsinvoice",
        "stdsemesterinvoice",
        "scholarship",
        "feestack",
        "feestackline",
        "crsfeestack",
        "invoicestatus",
        "paymentstatus",
        "paymentmethod",
        "feetype",
        "payer",
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
    FACULTY = RoleInfo("faculty", "Faculty", "people.Faculty", "CAS")
    CHAIR = RoleInfo("chair", "Chair", "people.Faculty", "CAS")
    DEAN = RoleInfo("dean", "Dean", "people.Faculty", "CAS")
    VPAA = RoleInfo("vpaa", "Vice President Academic Affairs", "people.Staff")

    ENROLLMENT = RoleInfo("enrollment", "Enrollment", "people.Staff")
    ENROLLMENT_OFFICER = RoleInfo(
        "enrollment_officer", "Enrollment Officer", "people.Staff"
    )
    FINANCE = RoleInfo("finance", "Finance", "people.Staff")
    FINANCE_OFFICER = RoleInfo("finance_officer", "Finance Officer", "people.Staff")
    REGISTRAR = RoleInfo("registrar", "Registrar", "people.Staff")
    REGISTRAR_OFFICER = RoleInfo("reg_officer", "Registrar Officer", "people.Staff")
    IT = RoleInfo("it", "It", "people.Staff")


ROLE_MATRIX = {
    "staff": {"view": ["student"]},
    "donor": {"view": ["student", "donor"]},
    "cashier": {
        "add": ["crsinvoice", "stdsemesterinvoice", "payment"],
        "view": ["crsinvoice", "stdsemesterinvoice", "payment", "paymentmethod"],
    },
    "chair": {
        "add": ["course", "curricrs", "section"],
        "change": ["course", "curricrs", "section"],
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
            "curricrs",
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
            "curricrs",
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
            "curricrs",
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
            "curricrs",
            "room",
            "section",
            "semester",
            "space",
            "term",
        ],
    },
    "enrollment_officer": {
        "view": [
            "curriculum",
            "docstd",
            "registration",
            "semester",
            "student",
            "user",
        ],
        "add": ["student", "docstd", "curriculum"],
        "change": [
            "curriculum",
            "department",
            "docstd",
            "registration",
            "student",
            "user",
        ],
        "delete": ["student", "docstd", "curriculum"],
    },
    "enrollment": {
        "view": [
            "college",
            "curriculum",
            "department",
            "docstd",
            "registration",
            "semester",
            "student",
        ],
        "add": ["student", "docstd"],
        "change": ["student", "registration", "docstd"],
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
            "curricrs",
            "schedule",
            "secsession",
            "section",
            "student",
        ],
    },
    "finance_officer": {
        "add": [
            "docdonor",
            "docstaff",
            "donor",
            "payment",
            "paymentmethod",
            "scholarship",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
        ],
        "change": [
            "docdonor",
            "payment",
            "paymentmethod",
            "docstaff",
            "donor",
            "crsinvoice",
            "stdsemesterinvoice",
            "scholarship",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
        ],
        "delete": [
            "donor",
            "crsinvoice",
            "stdsemesterinvoice",
            "scholarship",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
        ],
        "view": [
            "docdonor",
            "docstaff",
            "donor",
            "crsinvoice",
            "stdsemesterinvoice",
            "payment",
            "paymentmethod",
            "scholarship",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
            "student",
        ],
    },
    "finance": {
        "add": [
            "docdonor",
            "donor",
            "payment",
            "scholarship",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
        ],
        "change": [
            "docdonor",
            "donor",
            "crsinvoice",
            "stdsemesterinvoice",
            "payment",
            "paymentmethod",
            "scholarship",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
        ],
        "delete": [
            "donor",
            "crsinvoice",
            "stdsemesterinvoice",
            "scholarship",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
        ],
        "view": [
            "docdonor",
            "docstaff",
            "docstd",
            "donor",
            "crsinvoice",
            "stdsemesterinvoice",
            "payment",
            "paymentmethod",
            "scholarship",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
            "student",
        ],
    },
    "prospecting_student": {
        "add": ["docstd"],
        "delete": ["docstd"],
        "change": ["docstd"],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "docstd",
            "room",
            "semester",
            "space",
            "term",
            "docstd",
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
            "crsinvoice",
            "stdsemesterinvoice",
            "prerequisite",
            "curricrs",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
            "semester",
            "space",
            "staff",
            "student",
            "term",
        ],
    },
    "reg_officer": {
        "add": [
            "grade",
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
            "crsinvoice",
            "stdsemesterinvoice",
            "payment",
            "paymentmethod",
            "prerequisite",
            "curricrs",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
            "semester",
            "space",
            "staff",
            "student",
            "term",
        ],
    },
    "student": {
        "add": ["docstd", "registration"],
        "view": [
            "academicyear",
            "college",
            "course",
            "curriculum",
            "docstd",
            "grade",
            "major",
            "minor",
            "crsinvoice",
            "stdsemesterinvoice",
            "payment",
            "curricrs",
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
            "curricrs",
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
            "crsinvoice",
            "stdsemesterinvoice",
            "prerequisite",
            "curricrs",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
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
            "curricrs",
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
            "crsinvoice",
            "stdsemesterinvoice",
            "payment",
            "paymentmethod",
            "prerequisite",
            "curricrs",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
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
            "curricrs",
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
            "crsinvoice",
            "stdsemesterinvoice",
            "prerequisite",
            "curricrs",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
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
            "curricrs",
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
            "crsinvoice",
            "stdsemesterinvoice",
            "payment",
            "paymentmethod",
            "prerequisite",
            "curricrs",
            "registration",
            "room",
            "schedule",
            "scholarship",
            "secsession",
            "section",
            "crsfeestack",
            "feestack",
            "feestackline",
            "crsfeestack",
            "feestack",
            "feestackline",
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
            expanded += [m for m in APP_MODELS["registry"] if m.startswith("doc")]
        else:
            expanded += [item]

    # Keep deterministic order while avoiding duplicate permission lookups.
    return list(dict.fromkeys(expanded))
