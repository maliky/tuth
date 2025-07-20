"""Authentication constants used during data population."""

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

from dataclasses import dataclass
from enum import Enum

from app.people.models import Faculty, Staff, Student, Donor


@dataclass(frozen=True)
class RoleInfo:
    """Metadata attached to each user role."""

    label: str
    model: type | None
    default_college: str | None = None


class Role(Enum):
    """Self-describing user roles used throughout the app."""

    CASHIER = RoleInfo("Cashier", Staff)
    CHAIR = RoleInfo("Chair", Faculty, "COAS")
    DEAN = RoleInfo("Dean", Faculty, "COAS")
    DONOR = RoleInfo("Donor", Donor)
    ENROLLMENT_CLERC = RoleInfo("Enrollment Clerc", Staff)
    ENROLLMENT_OFFICER = RoleInfo("Enrollment Officer", Staff)
    FACULTY = RoleInfo("Faculty", Faculty, "COAS")
    FINANCEOFFICER = RoleInfo("Finance Officer", Staff)
    REGISTRAR_CLERC = RoleInfo("Registrar Clerc", Staff)
    REGISTRAR_OFFICER = RoleInfo("Registrar", Staff)
    STUDENT = RoleInfo("Student", Student)
    STUDENT_PROSPECTING = RoleInfo("Student Prospecting", Student)
    VPAA = RoleInfo("Vice President Academic Affairs", Staff)
    ADMINISTRATOR = RoleInfo("Administrator", Staff)
    STAFF = RoleInfo("Staff", Staff)
    IT_OFFICER = RoleInfo("It Officer", Staff)


PERMISSION_MATRIX = {
    'college': {
        'view': ['dean', 'chair', 'vpaa', 'registrar', 'student', 'student_prospecting'],
        'add': ['vpaa'],
        'change': ['vpaa', 'dean'],
        'delete': ['vpaa'],
    },
    'department': {
        'view': ['dean', 'chair', 'vpaa', 'registrar', 'faculty'],
        'add': ['dean', 'vpaa'],
        'change': ['dean', 'vpaa'],
        'delete': ['vpaa'],
    },
    'course': {
        'view': ['dean', 'chair', 'faculty', 'registrar', 'vpaa', 'student', 'student_prospecting'],
        'add': ['chair', 'dean', 'vpaa'],
        'change': ['chair', 'dean', 'vpaa'],
        'delete': ['vpaa'],
    },
    'curriculum': {
        'view': ['dean', 'chair', 'faculty', 'registrar', 'vpaa', 'student', 'student_prospecting'],
        'add': ['dean', 'vpaa'],
        'change': ['dean', 'vpaa'],
        'delete': ['vpaa'],
    },
    'major': {
        'view': ['dean', 'chair', 'vpaa', 'registrar', 'faculty', 'student'],
        'add': ['dean', 'vpaa'],
        'change': ['dean', 'vpaa'],
        'delete': ['vpaa'],
    },
    'minor': {
        'view': ['dean', 'chair', 'vpaa', 'registrar', 'faculty', 'student'],
        'add': ['dean', 'vpaa'],
        'change': ['dean', 'vpaa'],
        'delete': ['dean', 'vpaa'],
    },
    'program': {
        'view': ['dean', 'chair', 'vpaa', 'registrar', 'faculty', 'student'],
        'add': ['chair', 'dean', 'vpaa'],
        'change': ['chair', 'dean', 'vpaa'],
        'delete': ['vpaa'],
    },
    'prerequisite': {
        'view': ['dean', 'chair', 'registrar', 'vpaa'],
        'add': ['dean', 'registrar', 'vpaa'],
        'change': ['dean', 'registrar', 'vpaa'],
        'delete': ['vpaa'],
    },
    'student': {
        'view': ['registrar', 'faculty', 'finance_officer', 'vpaa', 'student'],
        'add': ['enrollment_officer'],
        'change': ['enrollment_officer', 'registrar'],
        'delete': ['registrar'],
    },
    'faculty': {
        'view': ['dean', 'chair', 'vpaa', 'registrar', 'faculty'],
        'add': ['vpaa'],
        'change': ['vpaa'],
        'delete': ['vpaa'],
    },
    'staff': {
        'view': ['vpaa', 'registrar'],
        'add': ['vpaa'],
        'change': ['vpaa'],
        'delete': ['vpaa'],
    },
    'donor': {
        'view': ['finance_officer', 'vpaa'],
        'add': ['finance_officer'],
        'change': ['finance_officer'],
        'delete': ['finance_officer'],
    },
    'space': {
        'view': ['registrar', 'vpaa', 'dean', 'chair', 'student', 'student_prospecting'],
        'add': ['registrar', 'vpaa'],
        'change': ['registrar'],
        'delete': ['vpaa'],
    },
    'room': {
        'view': ['registrar', 'vpaa', 'dean', 'chair', 'student', 'student_prospecting'],
        'add': ['registrar'],
        'change': ['registrar'],
        'delete': ['registrar'],
    },
    'academicyear': {
        'view': ['vpaa', 'registrar', 'dean', 'chair', 'student', 'student_prospecting'],
        'add': ['vpaa'],
        'change': ['vpaa'],
        'delete': ['vpaa'],
    },
    'semester': {
        'view': ['vpaa', 'registrar', 'dean', 'chair', 'student', 'student_prospecting'],
        'add': ['registrar', 'vpaa'],
        'change': ['vpaa', 'registrar'],
        'delete': ['vpaa'],
    },
    'term': {
        'view': ['vpaa', 'registrar', 'dean', 'chair', 'student', 'student_prospecting'],
        'add': ['registrar', 'vpaa'],
        'change': ['vpaa', 'registrar'],
        'delete': ['vpaa'],
    },
    'schedule': {
        'view': ['registrar', 'faculty', 'vpaa', 'student'],
        'add': ['registrar'],
        'change': ['registrar', 'vpaa'],
        'delete': ['registrar'],
    },
    'session': {
        'view': ['registrar', 'faculty', 'vpaa', 'student'],
        'add': ['registrar'],
        'change': ['registrar', 'vpaa'],
        'delete': ['registrar'],
    },
    'section': {
        'view': ['dean', 'chair', 'faculty', 'registrar', 'vpaa', 'student'],
        'add': ['registrar', 'chair', 'dean'],
        'change': ['registrar', 'chair', 'dean', 'vpaa'],
        'delete': ['registrar'],
    },
    'document': {
        'view': ['registrar', 'finance_officer', 'enrollment_officer', 'vpaa', 'student', 'student_prospecting'],
        'add': ['registrar', 'enrollment_officer', 'student', 'student_prospecting'],
        'change': ['registrar'],
        'delete': ['registrar'],
    },
    'registration': {
        'view': ['registrar', 'enrollment_officer', 'vpaa', 'student'],
        'add': ['registrar', 'enrollment_officer', 'student'],
        'change': ['registrar', 'enrollment_officer'],
        'delete': ['registrar'],
    },
    'classroster': {
        'view': ['registrar', 'vpaa', 'dean', 'chair', 'faculty'],
        'add': ['registrar'],
        'change': ['registrar'],
        'delete': ['registrar'],
    },
    'grade': {
        'view': ['registrar', 'faculty', 'vpaa', 'student'],
        'add': ['faculty'],
        'change': ['registrar'],
        'delete': ['registrar'],
    },
    'financialrecord': {
        'view': ['finance_officer', 'registrar', 'vpaa', 'student'],
        'add': ['finance_officer'],
        'change': ['finance_officer'],
        'delete': [],
    },
    'payment': {
        'view': ['cashier', 'finance_officer', 'registrar', 'vpaa', 'student'],
        'add': ['cashier'],
        'change': ['finance_officer', 'vpaa'],
        'delete': ['finance_officer'],
    },
    'paymenthistory': {
        'view': ['cashier', 'finance_officer', 'registrar', 'vpaa', 'student'],
        'add': ['cashier'],
        'change': ['finance_officer'],
        'delete': [],
    },
    'scholarship': {
        'view': ['finance_officer', 'registrar', 'vpaa', 'student'],
        'add': ['finance_officer'],
        'change': ['finance_officer', 'vpaa'],
        'delete': ['finance_officer'],
    },
    'sectionfee': {
        'view': ['finance_officer', 'registrar', 'vpaa'],
        'add': ['finance_officer'],
        'change': ['finance_officer', 'vpaa'],
        'delete': ['finance_officer'],
    },
}

