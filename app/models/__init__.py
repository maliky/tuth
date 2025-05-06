from .academics import College, Curriculum, Course, Prerequisite
from .admin import Document, FinancialRecord, PaymentHistory, Registration, ClassRoster
from .people import Profile, RoleAssignment
from .spaces import Building, Room
from .timed import AcademicYear, Term, Section

__all__ = [
    "College",
    "Curriculum",
    "Course",
    "Prerequisite",
    "Section",
    "Document",
    "FinancialRecord",
    "PaymentHistory",
    "Registration",
    "ClassRoster",
    "Profile",
    "RoleAssignment",
    "Building",
    "Room",
    "AcademicYear",
    "Term",
]
