"""Focused tests for curriculum admin changelist behavior."""

from __future__ import annotations

import pytest
from django.urls import reverse

from app.academics.admin.core import CurriAdmin
from app.academics.admin.filters import CurriCollegeFltAC
from app.academics.models import College, CurriStatus, Curriculum

pytestmark = pytest.mark.django_db


def _curriculum(
    college: College,
    short_name: str,
    *,
    active: bool,
    status_id: str,
) -> Curriculum:
    """Create one curriculum row for changelist filtering."""
    return Curriculum.objects.create(
        college=college,
        short_name=short_name,
        is_active=active,
        status_id=status_id,
    )


def _admin_result_ids(client, superuser, params: dict[str, str]) -> set[int]:
    """Return curriculum ids from the filtered admin changelist."""
    client.force_login(superuser)
    response = client.get(reverse("admin:academics_curriculum_changelist"), params)
    assert response.status_code == 200
    return {row.id for row in response.context["cl"].result_list}


def test_curriculum_admin_changelist_configuration() -> None:
    """Curriculum admin should expose requested filters without inline college edit."""
    assert CurriCollegeFltAC in CurriAdmin.list_filter
    assert "is_active" in CurriAdmin.list_filter
    assert "status" in CurriAdmin.list_filter
    assert "college" not in CurriAdmin.list_editable


def test_curriculum_admin_filters_by_college_active_and_status(client, superuser) -> None:
    """Curriculum changelist should narrow by college, active state, and status."""
    CurriStatus._populate_attributes_and_db()
    cba = College.objects.create(code="TCBA", long_name="Test Business")
    cas = College.objects.create(code="TCAS", long_name="Test Arts")
    active_approved = _curriculum(
        cba,
        "TCBA-ACCT",
        active=True,
        status_id="approved",
    )
    inactive_pending = _curriculum(
        cba,
        "TCBA-OLD",
        active=False,
        status_id="pending",
    )
    cas_approved = _curriculum(
        cas,
        "TCAS-BIOL",
        active=True,
        status_id="approved",
    )

    assert _admin_result_ids(client, superuser, {"college": str(cba.id)}) == {
        active_approved.id,
        inactive_pending.id,
    }
    assert _admin_result_ids(client, superuser, {"is_active__exact": "1"}) == {
        active_approved.id,
        cas_approved.id,
    }
    assert _admin_result_ids(client, superuser, {"status__code__exact": "pending"}) == {
        inactive_pending.id,
    }
