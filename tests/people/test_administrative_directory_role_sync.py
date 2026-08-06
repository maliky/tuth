"""Tests for syncing administrative directory staff roles."""

from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from openpyxl import Workbook

from app.people.models import RoleAssignment, Staff
from app.shared.auth.perms import UserRole

pytestmark = pytest.mark.django_db


def _write_xlsx(path: Path) -> None:
    """Write a minimal administrative TU directory workbook."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Tu directory"
    ws.append(["Name", "Position", "CellNo", "Email", "Offices/Divisions"])
    ws.append(
        [
            "Sylvester K. Nah",
            "Registrar",
            "886479962",
            "snah@tubmanu.edu.lr, registrar@tubmanu.edu.lr",
            "OFFICE OF THE REGISTRAR",
        ]
    )
    ws.append(
        [
            "Morris Wreh",
            "Assistant Registrar for Scheduling",
            "",
            "mwreh@tubmanu.edu.lr",
            "OFFICE OF THE REGISTRAR",
        ]
    )
    ws.append(
        [
            "Frank W. Smith",
            "Administrative Assistant",
            "",
            "fsmith@tubmanu.edu.lr",
            "OFFICE OF THE REGISTRAR",
        ]
    )
    ws.append(
        [
            "Emmanuel Y. Harmon",
            "Associate Vice President for Finance and Budget",
            "",
            "eharmon@tubmanu.edu.lr",
            "BUDGET AND FINANCE DEPARTMENT",
        ]
    )
    ws.append(
        [
            "Joe G. Elloitt",
            "Chief Accountant / Payroll Manager",
            "",
            "jelloitt@tubmanu.edu.lr",
            "BUDGET AND FINANCE DEPARTMENT",
        ]
    )
    ws.append(
        [
            "Sarafina P. Blay",
            "Cashier",
            "",
            "sblay@tubmanu.edu.lr",
            "BUDGET AND FINANCE DEPARTMENT",
        ]
    )
    ws.append(
        [
            "Gbou T. Freeman",
            "Budget Assistant",
            "",
            "gfreeman@tubman.edu.lr",
            "BUDGET AND FINANCE DEPARTMENT",
        ]
    )
    ws.append(
        [
            "David H. Erskine",
            "Acting Associate Vice President",
            "",
            "derskin@tubmanu.edu.lr",
            "DIVISION OF ENROLLMENT MANAGEMENT AND STUDENT SERVICES",
        ]
    )
    ws.append(
        [
            "Roland D. Collins",
            "Acting Assistant Vice President",
            "",
            "rcollins@tubmanu.edu.lr",
            "DIVISION OF ENROLLMENT MANAGEMENT AND STUDENT SERVICES",
        ]
    )
    ws.append(
        [
            "Otis C. Blay",
            "Admission Officer",
            "",
            "oblay@tubmanu.edu.lr",
            "OFFICE OF ENROLLMENT MANAGEMENT",
        ]
    )
    ws.append(
        [
            "Google Fallback",
            "Admission Officer",
            "",
            "",
            "OFFICE OF ENROLLMENT MANAGEMENT",
        ]
    )
    ws.append(
        ["Vacant", "Admission Assistant", "", "", "OFFICE OF ENROLLMENT MANAGEMENT"]
    )
    wb.save(path)


def _write_google_csv(path: Path) -> None:
    """Write a minimal Google users export."""
    fieldnames = [
        "First Name [Required]",
        "Last Name [Required]",
        "Email Address [Required]",
        "Password [Required]",
        "Org Unit Path [Required]",
    ]
    rows = [
        ("Google", "Fallback", "gfallback@tubmanu.edu.lr", "/Staff"),
        ("David Hne", "Erskine", "derskine@tubmanu.edu.lr", "/Staff"),
        ("Joe", "Elliott", "jelliott@tubmanu.edu.lr", "/Staff"),
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for first, last, email, org_path in rows:
            writer.writerow(
                {
                    "First Name [Required]": first,
                    "Last Name [Required]": last,
                    "Email Address [Required]": email,
                    "Password [Required]": "****",
                    "Org Unit Path [Required]": org_path,
                }
            )


def _fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create source files for administrative role sync tests."""
    xlsx = tmp_path / "directory.xlsx"
    google_csv = tmp_path / "google.csv"
    audit = tmp_path / "audit.csv"
    _write_xlsx(xlsx)
    _write_google_csv(google_csv)
    return xlsx, google_csv, audit


def _call_sync(
    xlsx: Path,
    google_csv: Path,
    audit: Path,
    *,
    apply: bool = False,
) -> str:
    """Run the management command and return stdout text."""
    stdout = StringIO()
    call_command(
        "sync_administrative_directory_roles",
        xlsx=str(xlsx),
        google_csv=str(google_csv),
        audit_path=str(audit),
        apply=apply,
        stdout=stdout,
    )
    return stdout.getvalue()


def _audit_rows(path: Path) -> list[dict[str, str]]:
    """Return audit CSV rows."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _has_role(username: str, user_role: UserRole) -> bool:
    """Return whether a user has one active global role assignment."""
    return RoleAssignment.objects.filter(
        user__username=username,
        group=user_role.value.group,
        college__isnull=True,
        department__isnull=True,
        end_date__isnull=True,
    ).exists()


def test_administrative_directory_role_sync_dry_run_does_not_write(
    tmp_path: Path,
) -> None:
    """Dry-run should only write an audit file."""
    xlsx, google_csv, audit = _fixtures(tmp_path)
    stdout = _call_sync(xlsx, google_csv, audit)

    assert not User.objects.filter(username="snah").exists()
    assert not Staff.objects.filter(user__username="snah").exists()
    assert not RoleAssignment.objects.filter(user__username="snah").exists()
    assert "dry-run" in stdout
    assert audit.exists()
    assert any(row["action"] == "manual_review" for row in _audit_rows(audit))


def test_administrative_directory_role_sync_applies_staff_and_roles(
    tmp_path: Path,
) -> None:
    """Apply mode should create deterministic staff users and operational roles."""
    xlsx, google_csv, audit = _fixtures(tmp_path)
    existing_user = User.objects.create_user(
        "eharmon",
        email="old@tubmanu.edu.lr",
        password="OldPass123!",
    )

    _call_sync(xlsx, google_csv, audit, apply=True)

    existing_user.refresh_from_db()
    assert existing_user.check_password("OldPass123!")
    assert existing_user.email == "eharmon@tubmanu.edu.lr"
    assert _has_role("snah", UserRole.REGISTRAR)
    assert _has_role("mwreh", UserRole.REGISTRAR_OFFICER)
    assert _has_role("eharmon", UserRole.FINANCE)
    assert _has_role("jelliott", UserRole.FINANCE)
    assert _has_role("sblay", UserRole.CASHIER)
    assert _has_role("derskine", UserRole.ENROLLMENT)
    assert _has_role("rcollins", UserRole.ENROLLMENT)
    assert _has_role("oblay", UserRole.ENROLLMENT_OFFICER)
    assert _has_role("gfallback", UserRole.ENROLLMENT_OFFICER)
    assert Staff.objects.filter(user__username="snah").exists()
    assert User.objects.get(username="snah").email == "snah@tubmanu.edu.lr"
    assert User.objects.get(username="jelliott").last_name == "ELLIOTT"
    assert not User.objects.filter(username="gfreeman").exists()
    assert not User.objects.filter(username="fsmith").exists()


def test_administrative_directory_role_sync_is_idempotent(tmp_path: Path) -> None:
    """Re-running apply must not duplicate active role assignments."""
    xlsx, google_csv, audit = _fixtures(tmp_path)

    _call_sync(xlsx, google_csv, audit, apply=True)
    _call_sync(xlsx, google_csv, audit, apply=True)

    assert (
        RoleAssignment.objects.filter(
            user__username="snah",
            group=UserRole.REGISTRAR.value.group,
            end_date__isnull=True,
        ).count()
        == 1
    )
    assert (
        RoleAssignment.objects.filter(
            user__username="oblay",
            group=UserRole.ENROLLMENT_OFFICER.value.group,
            end_date__isnull=True,
        ).count()
        == 1
    )


def test_administrative_directory_role_sync_audits_manual_review_rows(
    tmp_path: Path,
) -> None:
    """Ambiguous or non-officer rows should be audited without role assignment."""
    xlsx, google_csv, audit = _fixtures(tmp_path)

    _call_sync(xlsx, google_csv, audit, apply=True)
    rows = _audit_rows(audit)

    assert any(
        row["name"] == "Gbou T. Freeman"
        and row["action"] == "manual_review"
        and "conflicting" in row["message"]
        for row in rows
    )
    assert any(
        row["name"] == "Frank W. Smith"
        and row["action"] == "manual_review"
        and "not an officer role" in row["message"]
        for row in rows
    )
    assert any(
        row["name"] == "Vacant"
        and row["action"] == "manual_review"
        and row["message"] == "vacant"
        for row in rows
    )
