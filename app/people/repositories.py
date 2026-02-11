"""Data access helpers for the people app."""

from __future__ import annotations
from typing import cast

from django.contrib.auth import get_user_model
from django.db import transaction

from app.academics.models.college import College
from app.people.models.faculty import Faculty
from app.people.utils import mk_username, split_name
from app.shared.auth.perms import TEST_PW

User = get_user_model()


class PeopleRepository:
    """Encapsulate common atomic operations."""

    @staticmethod
    @transaction.atomic
    def get_or_create_faculty(name: str, college: College) -> Faculty:
        """Return an existing or new Faculty for the given name and college."""
        name_parts = split_name(name)
        prefix = name_parts.prefix
        first = name_parts.first
        middle = name_parts.middle
        last = name_parts.last
        suffix = name_parts.suffix
        username = mk_username(first, last, middle, prefix_len=2)

        faculty, _ = Faculty.objects.get_or_create(
            username=username,
            defaults={
                "college": college,
                "first_name": first,
                "middle_name": middle,
                "last_name": last,
                "name_prefix": prefix,
                "name_suffix": suffix,
                "password": TEST_PW,
            },
        )

        return cast(Faculty, faculty)
