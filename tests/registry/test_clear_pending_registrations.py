"""Tests for pending-payment registration clearance command."""

from __future__ import annotations

import csv
from io import StringIO

import pytest
from django.core.management import call_command

from app.registry.models.registration import Registration

pytestmark = pytest.mark.django_db


def test_clear_pending_registrations_dry_run_writes_audit_without_mutation(
    regio_factory,
    tmp_path,
) -> None:
    """Dry-run should report pending registrations without clearing them."""
    registration = regio_factory("clear_pending_dry", "CURRI_CLEAR_DRY", "601", 1)
    audit_path = tmp_path / "pending_dry.csv"
    output = StringIO()

    call_command(
        "clear_pending_registrations",
        "--log-path",
        str(audit_path),
        stdout=output,
    )

    registration.refresh_from_db()
    assert registration.status_id == "pending"
    assert (
        "Dry-run pending-registration clearance: 1 matched, 0 cleared"
        in output.getvalue()
    )
    audit_text = audit_path.read_text(encoding="utf-8")
    assert "would_clear" in audit_text
    assert str(registration.id) in audit_text


def test_clear_pending_registrations_apply_clears_only_pending_matches(
    regio_factory,
    tmp_path,
) -> None:
    """Apply mode should clear matching pending rows and leave cleared rows alone."""
    pending_registration = regio_factory(
        "clear_pending_apply",
        "CURRI_CLEAR_APPLY",
        "602",
        1,
    )
    cleared_registration = regio_factory(
        "clear_pending_already",
        "CURRI_CLEAR_DONE",
        "603",
        1,
    )
    cleared_registration.status_id = "cleared"
    cleared_registration.save(update_fields=["status"])
    audit_path = tmp_path / "pending_apply.csv"

    call_command(
        "clear_pending_registrations",
        "--apply",
        "--log-path",
        str(audit_path),
        stdout=StringIO(),
    )

    pending_registration.refresh_from_db()
    cleared_registration.refresh_from_db()
    assert pending_registration.status_id == "cleared"
    assert cleared_registration.status_id == "cleared"
    assert Registration.objects.filter(status_id="pending").count() == 0
    with audit_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["registration_id"] for row in rows] == [str(pending_registration.id)]
    assert rows[0]["action"] == "cleared"
    assert rows[0]["new_status"] == "cleared"
