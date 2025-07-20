"""Module for choices constants used for people."""

from app.people.models.staffs import Faculty, Staff
from app.people.models.student import Student
from django.db import models


class UserRole(models.TextChoices):
    # ~~~~~~~~ Academics ~~~~~~~~
    TEACHING_ASSISTANT = "ta", "Teaching Assistant"
    FACULTY = "faculty", "Faculty"
    CHAIR = "chair", "Chair"
    DEAN = "dean", "Dean"
    VPAA = "vpaa", "Vice President Academic Affairs"
    # ~~~~ Students ~~~~
    PROSPECTING_STUDENT = "prospecting_student", "Prospecting Student"
    STUDENT = "student", "Student"
    # ~~~~~~~~ Administration ~~~~~~~~
    STAFF = "staff", "Staff"
    # ~~~~ Regular User ~~~~
    ENROLLMENT = "enrollment", "Enrollment Staff"
    ENROLLMENT_OFFICER = "enrollment_officer", "Enrollment Officer"
    FINANCE = "finance", "Finance Staff"
    FINANCE_OFFICER = "finance_officer", "Finance Officer"
    REGISTRAR = "registrar", "Registrar Staff"
    REGISTRAR_OFFICER = "registrar_officer", "Registrar Officer"
    # ~~~~ Occasional users ~~~~
    IT_OFFICER = "it_officer", "IT Officer"
    VPA = "vpa", "Vice President for Administration"
    # ~~~~~~~~ Others ~~~~~~~~
    DONOR = "donor", "Donor"


USER_CLASS = {
    # ~~~~~~~~ Academics ~~~~~~~~
    "ta": Faculty,
    "faculty": Faculty,
    "chair": Faculty,
    "dean": Faculty,
    "vpaa": Faculty,
    # ~~~~ Students ~~~~
    "prospecting_student": Student,
    "student": Student,
    # ~~~~~~~~ Administration ~~~~~~~~
    # ~~~~ Regular User ~~~~
    "enrollment": Staff,
    "enrollment_officer": Staff,
    "finance": Staff,
    "finance_officer": Staff,
    "registrar": Staff,
    "registrar_officer": Staff,
    # ~~~~ Occasional users ~~~~
    "it_officer": Staff,
    "staff": Staff,
    "vpa": Staff,
    # ~~~~~~~~ Others ~~~~~~~~
    "donor": Donor,
}
