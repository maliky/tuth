"""People donor module."""

# app/people/models/donor.py

from __future__ import annotations

from django.contrib.auth.models import Group
from django.db import models

from app.people.models.core import AbstractPerson
from app.people.choices import UserRole


class Donor(AbstractPerson):
    """Contact information for donors supporting students.

    Example:
        >>> user = User.objects.create_user(username="donor")
        >>> Donor.objects.create(user=user, donor_id="DN001")

    Side Effects:
        save() from :class:AbstractPerson populates donor_id.
    """

    ID_FIELD = "donor_id"
    ID_PREFIX = "TU-DNR"

    # ~~~~ Read-only ~~~~
    donor_id = models.CharField(max_length=13, unique=True, editable=False, blank=False)

    def save(self, *args, **kwargs):
        """Ensure donor group and staff flag."""
        super().save(*args, **kwargs)
        if self.user_id:
            group, _ = Group.objects.get_or_create(name=UserRole.DONOR.label)
            self.user.groups.add(group)
            self.user.is_staff = False
            self.user.save(update_fields=["is_staff"])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_donor_per_user"),
        ]
