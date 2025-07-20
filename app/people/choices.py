"""Module for choices constants used for people."""

from django.db import models


class UserRole(models.TextChoices):
    CASHIER = "cashier", "Cashier"
    CHAIR = "chair", "Chair"
    DEAN = "dean", "Dean"
    DONOR = "donor", "Donor"
    ENROLLMENT_CLERC = "enrollment_clerc", "Enrollment Clerc"
    ENROLLMENT_OFFICER = "enrollment_officer", "Enrollment Officer"
    FACULTY = "faculty", "Faculty"
    FINANCEOFFICER = "finance_officer", "Finance Officer"
    REGISTRAR_CLERC = "registrar_clerc", "Registrar Clerc"
    REGISTRAR_OFFICER = "registrar", "Registrar"
    STUDENT = "student", "Student"
    STUDENT_PROSPECTING = "student_prospecting", "Student Prospecting"
    VPAA = "vpaa", "Vice President Academic Affairs"
    ADMINISTRATOR = "administrator", "Administrator"
    STAFF = "staff", "Staff"
    IT_OFFICER = (
        "it_officer",
        "It Officer",
    )
