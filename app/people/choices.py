"""Module for choices constants used for people."""

from django.db import models


class UserRole(models.TextChoices):
    CASHIER = "cashier", "Cashier"
    VPA = "vpa", "Vice President Administration"
    STUDENT = "student", "Student"
    PROSPECTIVE_STUDENT = "prospective_student", "Prospective Student"
    TECHNICIAN = "technician", "Technician"
    LAB_TECHNICIAN = "lab_technician", "Lab Technician"
    REGISTRAR = "registrar", "Registrar"
    ENROLLMENT_OFFICER = "enrollment_officer", "Enrollment Officer"
    DEAN = "dean", "Dean"
    CHAIR = "chair", "Chair"
    LECTURER = "lecturer", "Lecturer"
    ASSISTANT_PROFESSOR = "assistant_professor", "Assistant Professor"
    ASSOCIATE_PROFESSOR = "associate_professor", "Associate Professor"
    PROFESSOR = "professor", "Professor"
    FACULTY = "faculty", "Faculty"
    VPAA = "vpaa", "Vpaa"
    FINANCIALOFFICER = "financial_officer", "Financial Officer"
