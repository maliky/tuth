"""People donor module."""

# app/people/models/donor.py

from __future__ import annotations

from django.db import models
from app.people.choices import UserRole
from app.people.models.core import AbstractPerson


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
    GROUP = UserRole.DONOR.label

    # ~~~~ Read-only ~~~~
    donor_id = models.CharField(max_length=13, unique=True, editable=False, blank=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_donor_per_user"),
        ]
