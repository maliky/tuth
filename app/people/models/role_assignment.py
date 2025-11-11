"""Role assignment module."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models
from simple_history.models import HistoricalRecords


User = get_user_model()


class RoleAssignment(models.Model):
    """Period during which a user holds a specific role.

    Example:
        >>> RoleAssignment.objects.create(
        ...     user=user,
        ...     group=UserRole.REGISTRAR.value.group,
        ...     start_date=date.today(),
        ... )

    The optional ``department`` field further scopes a role within a
    specific academic department, similar to ``college``.
    """
    # ~~~~~~~~ Mandatory ~~~~~~~~
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="role_assignments"
    )
    # may not be necessary. could override set, get attr("group") pointing
    # to user groups.
    group = models.ForeignKey(
        "auth.Group", on_delete=models.CASCADE, related_name="roles"
    )
    start_date = models.DateField()
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    # ~~~~~~~~ Optional ~~~~~~~~
    college = models.ForeignKey(
        "academics.College",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="roles",
    )
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="roles",
    )
    end_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user} -> {self.group} ({self.start_date})"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "group", "college", "department", "start_date"],
                name="unique_role_per_period",
            )
        ]
        indexes = [
            models.Index(fields=["group", "college", "department", "end_date"]),
        ]
