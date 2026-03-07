"""Tests for CurriStdEnroll admin actions."""

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import RequestFactory

from app.academics.admin.core import CurriStdEnrollAdmin
from app.academics.models import CurriStdEnroll


pytestmark = pytest.mark.django_db


def _build_action_request(superuser, data: dict[str, object]):
    """Return an admin POST request with the acting superuser."""
    request = RequestFactory().post("/admin/academics/curristdenroll/", data=data)
    request.user = superuser
    return request


def test_bulk_change_curri_moves_row_without_target_collision(
    superuser,
    student,
    curri_factory,
):
    """Selected rows should move directly when no target row exists."""
    source_curri = curri_factory("CURRI-STD-MOVE-SRC")
    target_curri = curri_factory("CURRI-STD-MOVE-TGT")
    source_row = CurriStdEnroll.objects.create(
        student=student,
        curriculum=source_curri,
        is_primary=False,
        is_active=True,
    )
    queryset = CurriStdEnroll.objects.filter(pk=source_row.pk)
    request = _build_action_request(
        superuser,
        data={
            "apply_change_curri": "1",
            "curriculum": str(target_curri.pk),
            "_selected_action": [str(source_row.pk)],
            ACTION_CHECKBOX_NAME: [str(source_row.pk)],
        },
    )
    admin_obj = CurriStdEnrollAdmin(CurriStdEnroll, admin.site)

    with patch.object(admin_obj, "message_user"):
        response = admin_obj.bulk_change_curri_on_selected_rows(request, queryset)

    assert response is None
    source_row.refresh_from_db()
    assert source_row.curriculum_id == target_curri.pk


def test_bulk_change_curri_merges_into_existing_target_row(
    superuser,
    student,
    curri_factory,
    dft_sem,
):
    """Selected source rows should merge into existing target rows for the same student."""
    source_curri = curri_factory("CURRI-STD-MERGE-SRC")
    target_curri = curri_factory("CURRI-STD-MERGE-TGT")
    target_row = CurriStdEnroll.objects.create(
        student=student,
        curriculum=target_curri,
        entry_semester=dft_sem,
        is_primary=False,
        is_active=False,
    )
    source_row = CurriStdEnroll.objects.create(
        student=student,
        curriculum=source_curri,
        entry_semester=dft_sem,
        is_primary=False,
        is_active=True,
    )
    queryset = CurriStdEnroll.objects.filter(pk=source_row.pk)
    request = _build_action_request(
        superuser,
        data={
            "apply_change_curri": "1",
            "curriculum": str(target_curri.pk),
            "_selected_action": [str(source_row.pk)],
            ACTION_CHECKBOX_NAME: [str(source_row.pk)],
        },
    )
    admin_obj = CurriStdEnrollAdmin(CurriStdEnroll, admin.site)

    with patch.object(admin_obj, "message_user"):
        response = admin_obj.bulk_change_curri_on_selected_rows(request, queryset)

    assert response is None
    assert not CurriStdEnroll.objects.filter(pk=source_row.pk).exists()
    target_row.refresh_from_db()
    assert target_row.is_active is True
