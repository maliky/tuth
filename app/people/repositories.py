"""Data access helpers for the people app."""

from __future__ import annotations
from typing import cast, Any

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
        n = split_name(name)
        username = mk_username(n.first, n.last, n.middle, prefix_len=2)

        faculty_dft: dict[str, Any] = n.to_dict()
        faculty_dft.update({"college": college, "password": TEST_PW})
        faculty, _ = Faculty.objects.get_or_create(
            username=username, defaults=faculty_dft
        )

        return cast(Faculty, faculty)
