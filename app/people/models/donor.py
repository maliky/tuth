"""People donor module."""

# app/people/models/donor.py

from __future__ import annotations

from typing import cast

from django.contrib.auth.models import User
from django.db import models
from simple_history.models import HistoricalRecords

from app.people.models.core import AbstractPerson
from app.people.utils import mk_password


class Donor(AbstractPerson):
    """Contact information for donors supporting students.

    Example:
        >>> user = User.objects.create_user(username="donor")
        >>> Donor.objects.create(username=username, donor_id="DN001")

    Side Effects:
        save() from :class:AbstractPerson populates donor_id.
    """

    ID_FIELD = "donor_id"
    ID_PREFIX = "TU-DNR"
    GROUP = "Donor"
    STAFF_STATUS = False

    # ~~~~ Read-only ~~~~
    donor_id = models.CharField(max_length=13, unique=True, editable=False, blank=False)
    # ~~~~ Autofilled ~~~~
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="uniq_donor_per_user"),
        ]

    @classmethod
    def mk_username(
        cls,
        first,
        last,
        middle=None,
        unique=True,
        exclude=None,
        prefix_len=None,
        sep=None,
    ):
        """Generate donor usernames with a short first-name prefix."""
        return super().mk_username(
            first,
            last,
            middle=middle,
            unique=unique,
            exclude=exclude,
            prefix_len=prefix_len,
            sep=sep,
        )

    @classmethod
    def get_default(cls) -> "Donor":
        """Return a placeholder Donor for legacy imports."""
        user, created = User.objects.get_or_create(
            username="legacy_donor",
            defaults={"first_name": "Legacy", "last_name": "Donor"},
        )
        if created:
            user.set_password(mk_password("Legacy", "Donor"))
            user.save(update_fields=["password"])

        donor, _ = cls.objects.get_or_create(
            user=user,
            defaults={"username": user.username},
        )
        return cast("Donor", donor)
