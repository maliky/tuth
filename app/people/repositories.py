"""Data access helpers for the people app."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from app.academics.models.college import College
from app.people.models.staffs import Faculty, Staff
from app.people.utils import mk_username, split_name
from app.shared.auth.perms import TEST_PW

User = get_user_model()


class PeopleRepository:
    """Encapsulate common atomic operations."""

    @staticmethod
    @transaction.atomic
    def get_or_create_faculty(name: str, college: College) -> Faculty:
        """Return an existing or new Faculty for the given name and college."""

        _, first, _, last, _ = split_name(name)
        username = mk_username(first, last, exclude=False, prefix_len=2)

        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first, "last_name": last},
        )

        if user_created:
            user.set_password(TEST_PW)
            user.save()
            staff, _ = Staff.objects.get_or_create(user=user)
            faculty = Faculty.objects.create(staff_profile=staff, college=college)
            return faculty

        staff, _ = Staff.objects.get_or_create(user=user)

        faculty, _ = Faculty.objects.get_or_create(
            staff_profile=staff,
            defaults={"college": college},
        )

        if faculty.college != college:
            faculty.college = college
            faculty.save()

        return faculty
