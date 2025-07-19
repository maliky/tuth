"""Role assignment module."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models
from simple_history.models import HistoricalRecords

from app.people.choices import UserRole

User = get_user_model()


class RoleAssignment(models.Model):
    """Period during which a user holds a specific role.

    Example:
        >>> RoleAssignment.objects.create(
        ...     user=user,
        ...     role=UserRole.REGISTRAR,
        ...     start_date=date.today(),
        ... )

    The optional ``department`` field further scopes a role within a
    specific academic department, similar to ``college``.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.CharField(max_length=40, choices=UserRole.choices)
    start_date = models.DateField()
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    # ~~~~~~~~ Optional ~~~~~~~~
    college = models.ForeignKey(
        "academics.College",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="role_assignments",
    )
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="role_assignments",
    )
    end_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user} -> {self.role} ({self.start_date})"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "college", "department", "start_date"],
                name="unique_role_per_period",
            )
        ]
        indexes = [
            models.Index(fields=["role", "college", "department", "end_date"]),
        ]
