from django.db import models
from app.models.academics import College  # avoid circular import issues


class Profile(models.Model):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)


class RoleAssignment(models.Model):
    USER_ROLES = [
        ("Dean", "Dean"),
        ("Chair", "Chair"),
        ("Lecturer", "Lecturer"),
        ("Assistant Professor", "Assistant Professor"),
        ("Associate Professor", "Associate Professor"),
        ("Professor", "Professor"),
        ("Technician", "Technician"),
        ("Lab Technician", "Lab Technician"),
        ("Instructor", "Instructor"),
        ("VPAA", "VPAA"),
        ("Registrar", "Registrar"),
        ("FinancialOfficer", "FinancialOfficer"),
        ("EnrollmentOfficer", "EnrollmentOfficer"),
    ]
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.CharField(max_length=30, choices=USER_ROLES)
    college = models.ForeignKey(
        College,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="role_assignments",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "college", "start_date"],
                name="unique_role_per_period",
            )
        ]
        indexes = [
            models.Index(fields=["role", "college", "end_date"]),
        ]

    def __str__(self):
        return f"{self.user} -> {self.role} ({self.start_date})"
