"""Module for choices constants used for people."""

from django.db import models


class UserRole(models.TextChoices):
    CASHIER = "cashier", "Cashier"
    CHAIR = "chair", "Chair"
    DEAN = "dean", "Dean"
    ENROLLMENT_CLERC = "enrollment_clerc", "Enrollment Clerc"
    ENROLLMENT_OFFICER = "enrollment_officer", "Enrollment Officer"
    FACULTY = "faculty", "Faculty"
    FINANCEOFFICER = "finance_officer", "Finance Officer"
    REGISTRAR_CLERC = "registrar_clerc", "Registrar Clerc"
    REGISTRAR_OFFICER = "registrar", "Registrar"
    STUDENT = "student", "Student"
    STUDENT_PROSPECTING = "student_prospecting", "Student Prospecting"
    VPAA = "vice_president_acadmic_affaires", "Vice President Academic Affairs"
    ADMINISTRATOR = "administrator", "Administrator"
    IT_OFFICER = (
        "it_officer",
        "It Officer",
    )  # capitalize for coherence. do not chante to IT
    # ASSISTANT_PROFESSOR = "assistant_professor", "Assistant Professor"
    # ASSOCIATE_PROFESSOR = "associate_professor", "Associate Professor"
    # LAB_TECHNICIAN = "lab_technician", "Lab Technician"
    # LECTURER = "lecturer", "Lecturer"
    # PROFESSOR = "professor", "Professor"
    # TECHNICIAN = "technician", "Technician"
