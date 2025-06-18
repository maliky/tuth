"""Role assignment module."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

from app.shared.constants.perms import UserRole

User = get_user_model()


class RoleAssignment(models.Model):
    """Period during which a user holds a specific role.

    Example:
        >>> from app.people.models import RoleAssignment
        >>> RoleAssignment.objects.create(user=user, role=UserRole.ADMIN)
    """

    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.CharField(max_length=30, choices=UserRole.choices)
    college = models.ForeignKey(
        "academics.College",
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

    def __str__(self) -> str:
        return f"{self.user} -> {self.role} ({self.start_date})"
