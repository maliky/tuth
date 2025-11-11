"""Helpers for django-impersonate integration."""

from __future__ import annotations

from typing import Iterable

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

UserModel = get_user_model()


def get_role_representatives(request):  # pragma: no cover - thin wrapper
    """Limit impersonation targets to a single active user per group.

    Groups are treated as the role definition inside Tusis. To keep the
    impersonation feature manageable we only show the first active member of
    each group, skipping duplicates across groups.
    """

    representative_ids = []
    groups: Iterable[Group] = (
        Group.objects.prefetch_related("user_set").order_by("name").all()
    )

    for group in groups:
        candidate = (
            group.user_set.filter(is_active=True)
            .exclude(pk__in=representative_ids)
            .order_by("id")
            .first()
        )
        if candidate:
            representative_ids.append(candidate.pk)

    if not representative_ids:
        return UserModel.objects.none()

    return UserModel.objects.filter(pk__in=representative_ids).order_by("pk")
