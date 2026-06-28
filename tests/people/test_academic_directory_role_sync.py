"""Tests for syncing academic directory staff roles."""

from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from openpyxl import Workbook

from app.academics.models import College, Department
from app.people.models import Faculty, RoleAssignment, Staff
from app.shared.auth.perms import UserRole

pytestmark = pytest.mark.django_db


def _college(code: str) -> College:
    """Create a test college with a stable code."""
    return College.objects.create(code=code)


def _department(college: College, code: str) -> Department:
    """Create one test department under a college."""
    return Department.objects.create(college=college, code=code)


def _write_xlsx(path: Path) -> None:
    """Write a minimal TU directory workbook."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Tu directory"
    ws.append(["Name", "Position", "CellNo", "Email", "Offices/Divisions"])
    ws.append(
        [
            "Neonora Ade Payne-Barclay",
            "Instructor",
            "0770000000",
            "npayne-barclay@tubmanu.edu.lr",
            "COLLEGE OF HEALTH SCIENCES",
        ]
    )
    ws.append(
        [
            "Faikai Dorley",
            "Instructor/ Chair, Econ/BFIN",
            "",
            "fdorley@tubmanu.edu.lr",
            "COLLEGE OF BUSINESS & ADMINISTRATION",
        ]
    )
    ws.append(
        [
            "Osarue O. Edosa",
            "Assistant Professor/ Chair, Mechanical Engineering",
            "",
            "oedosa@tubmanu.edu.lr",
            "COLLEGE OF ENGINEERING AND TECHNOLOGY",
        ]
    )
    ws.append(
        [
            "Micheal Oche,Ph.D.",
            "Assistant Professor, Computer Science",
            "",
            "",
            "COLLEGE OF ENGINEERING AND TECHNOLOGY",
        ]
    )
    ws.append(["Vacant", "Dean", "", "", "COLLEGE OF ARTS AND SCIENCES"])
    wb.save(path)


def _write_google_csv(path: Path) -> None:
    """Write a minimal Google users export."""
    fieldnames = [
        "First Name [Required]",
        "Last Name [Required]",
        "Email Address [Required]",
        "Password [Required]",
        "Org Unit Path [Required]",
        "Employee Title",
        "Department",
        "Mobile Phone",
        "Work Phone",
    ]
    rows = [
        ("Dr. Michael", "Oche", "moche@tubmanu.edu.lr", "/Staff"),
        ("Babatunde Fatai", "Ogunbayo", "bogunbayo@tubmanu.edu.lr", "/Staff"),
        ("Ma Fe", "Gueta", "mgueta@tubmanu.edu.lr", "/Staff"),
        ("Tukundane", "Benson", "tbenson@tubmanu.edu.lr", "/Staff"),
        ("Larry Hwang", "Hwang", "lhwang@tubmanu.edu.lr", "/Staff"),
        ("Dr. Jerry Castor", "BU-AO", "jbuao@tubmanu.edu.lr", "/Staff"),
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
    """Create source files and required academic org rows."""
    cba = _college("CBA")
    cet = _college("CET")
    chs = _college("CHS")
    _college("CAS")
    _college("CAFS")
    _college("EDRCE")
    _department(cba, "ECON")
    _department(cba, "BFIN")
    _department(cet, "CSEN")
    _department(chs, "NURS")
    xlsx = tmp_path / "directory.xlsx"
    google_csv = tmp_path / "google.csv"
    audit = tmp_path / "audit.csv"
    _write_xlsx(xlsx)
    _write_google_csv(google_csv)
    return xlsx, google_csv, audit


def test_academic_directory_role_sync_dry_run_does_not_write(tmp_path: Path) -> None:
    """Dry-run should only write the audit file."""
    xlsx, google_csv, audit = _fixtures(tmp_path)
    stdout = StringIO()

    call_command(
        "sync_academic_directory_roles",
        xlsx=str(xlsx),
        google_csv=str(google_csv),
        audit_path=str(audit),
        stdout=stdout,
    )

    assert not User.objects.filter(username="fdorley").exists()
    assert not Staff.objects.filter(user__username="fdorley").exists()
    assert not RoleAssignment.objects.filter(user__username="fdorley").exists()
    assert audit.exists()
    assert "dry-run" in stdout.getvalue()


def test_academic_directory_role_sync_applies_staff_faculty_and_roles(
    tmp_path: Path,
) -> None:
    """Apply mode should create people and current role assignments."""
    xlsx, google_csv, audit = _fixtures(tmp_path)
    old_dean = User.objects.create_user("test_dean", password="old")
    old_dean.groups.add(UserRole.DEAN.value.group)
    RoleAssignment.objects.create(
        user=old_dean,
        group=UserRole.DEAN.value.group,
        college=College.objects.get(code="CAS"),
        start_date=date(2025, 1, 1),
    )

    call_command(
        "sync_academic_directory_roles",
        xlsx=str(xlsx),
        google_csv=str(google_csv),
        audit_path=str(audit),
        apply=True,
    )

    faikai = User.objects.get(username="fdorley")
    assert faikai.groups.filter(name=UserRole.CHAIR.value.label).exists()
    chair_depts = set(
        RoleAssignment.objects.filter(user=faikai, group=UserRole.CHAIR.value.group)
        .exclude(department__isnull=True)
        .values_list("department__code", flat=True)
    )
    assert chair_depts == {"BFIN", "ECON"}
    assert Staff.objects.filter(user__username="moche").exists()
    assert Faculty.objects.filter(staff_profile__user__username="moche").exists()
    assert RoleAssignment.objects.filter(
        user__username="bogunbayo",
        group=UserRole.DEAN.value.group,
        college__code="CET",
        end_date__isnull=True,
    ).exists()
    assert RoleAssignment.objects.filter(
        user__username="npayne-barclay",
        group=UserRole.DEAN.value.group,
        college__code="CHS",
        end_date__isnull=True,
    ).exists()
    assert RoleAssignment.objects.filter(
        user__username="mgueta",
        group=UserRole.VPAA.value.group,
        end_date__isnull=True,
    ).exists()
    assert not RoleAssignment.objects.filter(
        user__username="oedosa",
        group=UserRole.CHAIR.value.group,
        end_date__isnull=True,
    ).exists()
    old_role = RoleAssignment.objects.get(user=old_dean)
    assert old_role.end_date is not None
