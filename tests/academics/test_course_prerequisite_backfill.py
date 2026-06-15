"""Tests for global TUCurricula prerequisite backfill."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from app.academics.course_prerequisite_backfill import backfill_global_prerequisites
from app.academics.models import Course, Department, Prerequisite
from app.shared.source_truth.io import read_rows

pytestmark = pytest.mark.django_db

COURSE_HEADERS = (
    "college_code",
    "course_college_code",
    "course_dept",
    "course_no",
    "course_title",
    "credit_hours",
    "description",
    "source_course_key",
    "source_files",
)
REQ_HEADERS = (
    "college_code",
    "curriculum_college_code",
    "course_college_code",
    "curriculum",
    "course_dept",
    "course_no",
    "required_course_college_code",
    "required_course_dept",
    "required_course_no",
    "requirement_kind",
    "requirement_label",
    "requirement_order",
    "member_order",
    "source_file",
    "source_course_key",
    "raw_requisite",
)


def _write_tsv(
    path: Path,
    headers: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    """Write a small TSV fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _write_import_dir(
    import_dir: Path,
    *,
    courses: list[dict[str, str]],
    requirements: list[dict[str, str]],
) -> None:
    """Write minimal TUCurricula import files."""
    _write_tsv(import_dir / "academic_course.tsv", COURSE_HEADERS, courses)
    _write_tsv(
        import_dir / "academic_curriculum_requirement.tsv",
        REQ_HEADERS,
        requirements,
    )


def _course(dept_code: str, number: str, title: str = "") -> Course:
    """Create one current TUSIS course."""
    return Course.objects.create(
        department=Department.get_dft(dept_code),
        number=number,
        title=title,
    )


def _source_course(dept_code: str, number: str, title: str) -> dict[str, str]:
    """Return one source course row."""
    return {
        "college_code": "COAS",
        "course_college_code": "COAS",
        "course_dept": dept_code,
        "course_no": number,
        "course_title": title,
        "credit_hours": "3",
        "description": "",
        "source_course_key": f"{dept_code}{number}",
        "source_files": "test.org",
    }


def _requirement(
    target_dept: str,
    target_no: str,
    required_dept: str,
    required_no: str,
    *,
    kind: str = "prereq_all",
) -> dict[str, str]:
    """Return one source requirement row."""
    return {
        "college_code": "COAS",
        "curriculum_college_code": "COAS",
        "course_college_code": "COAS",
        "curriculum": "CAS-TEST",
        "course_dept": target_dept,
        "course_no": target_no,
        "required_course_college_code": "COAS",
        "required_course_dept": required_dept,
        "required_course_no": required_no,
        "requirement_kind": kind,
        "requirement_label": f"source {kind} {target_dept}{target_no}",
        "requirement_order": "1",
        "member_order": "1",
        "source_file": "test.org",
        "source_course_key": f"{target_dept}{target_no}",
        "raw_requisite": f"{required_dept.lower()}{required_no}",
    }


def test_global_prerequisite_backfill_dry_run_reports_without_mutating(
    tmp_path: Path,
) -> None:
    """Dry-run should report global edges without creating Prerequisite rows."""
    import_dir = tmp_path / "import"
    report_path = tmp_path / "report.tsv"
    target = _course("ENGL", "102", "Academic Reading and Writing")
    required = _course("ENGL", "101", "Composition I")
    _write_import_dir(
        import_dir,
        courses=[
            _source_course("ENGL", "102", "Academic Reading and Writing"),
            _source_course("ENGL", "101", "Composition I"),
        ],
        requirements=[_requirement("ENGL", "102", "ENGL", "101")],
    )

    summary = backfill_global_prerequisites(
        import_dir=import_dir,
        report_path=report_path,
    )

    assert summary.would_create == 1
    assert not Prerequisite.objects.filter(
        curriculum__isnull=True,
        course=target,
        prerequisite_course=required,
    ).exists()
    assert read_rows(report_path)[0]["action"] == "would_create"


def test_global_prerequisite_backfill_apply_creates_global_edge(
    tmp_path: Path,
) -> None:
    """Apply mode should create idempotent curriculum-independent prereq edges."""
    import_dir = tmp_path / "import"
    target = _course("MATH", "102", "Geometry and Trigonometry")
    required = _course("MATH", "101", "College Algebra")
    _write_import_dir(
        import_dir,
        courses=[
            _source_course("MATH", "102", "Geometry and Trigonometry"),
            _source_course("MATH", "101", "College Algebra"),
        ],
        requirements=[_requirement("MATH", "102", "MATH", "101")],
    )

    summary = backfill_global_prerequisites(import_dir=import_dir, apply=True)
    second_summary = backfill_global_prerequisites(import_dir=import_dir, apply=True)

    assert summary.created == 1
    assert second_summary.skipped_existing == 1
    assert Prerequisite.objects.filter(
        curriculum__isnull=True,
        course=target,
        prerequisite_course=required,
    ).exists()


def test_global_prerequisite_backfill_matches_close_department_titles(
    tmp_path: Path,
) -> None:
    """Close department variants like PSY/PSYC should inherit prereq_all facts."""
    import_dir = tmp_path / "import"
    target = _course("PSY", "201", "Developmental Psychology")
    required = _course("PSY", "101", "Introduction to Psychology")
    _write_import_dir(
        import_dir,
        courses=[
            _source_course("PSYC", "201", "Developmental Psychology"),
            _source_course("PSYC", "101", "Introduction to Psychology"),
        ],
        requirements=[_requirement("PSYC", "201", "PSYC", "101")],
    )

    summary = backfill_global_prerequisites(import_dir=import_dir, apply=True)

    assert summary.created == 1
    assert Prerequisite.objects.filter(
        curriculum__isnull=True,
        course=target,
        prerequisite_course=required,
    ).exists()


def test_global_prerequisite_backfill_ignores_prereq_any_for_global_edges(
    tmp_path: Path,
) -> None:
    """Global hard edges should not misrepresent prereq_any groups."""
    import_dir = tmp_path / "import"
    _course("BIOL", "301", "Advanced Biology")
    _course("BIOL", "201", "Biology II")
    _write_import_dir(
        import_dir,
        courses=[
            _source_course("BIOL", "301", "Advanced Biology"),
            _source_course("BIOL", "201", "Biology II"),
        ],
        requirements=[_requirement("BIOL", "301", "BIOL", "201", kind="prereq_any")],
    )

    summary = backfill_global_prerequisites(import_dir=import_dir, apply=True)

    assert summary.source_pairs == 0
    assert Prerequisite.objects.count() == 0


def test_global_prerequisite_backfill_command_defaults_to_dry_run(
    tmp_path: Path,
) -> None:
    """Management command should not mutate unless --apply is supplied."""
    import_dir = tmp_path / "import"
    report_path = tmp_path / "command-report.tsv"
    _course("HIST", "202", "World History II")
    _course("HIST", "201", "World History I")
    _write_import_dir(
        import_dir,
        courses=[
            _source_course("HIST", "202", "World History II"),
            _source_course("HIST", "201", "World History I"),
        ],
        requirements=[_requirement("HIST", "202", "HIST", "201")],
    )
    output = StringIO()

    call_command(
        "backfill_tucurricula_global_prerequisites",
        import_dir=str(import_dir),
        report_path=str(report_path),
        stdout=output,
    )

    assert "dry-run" in output.getvalue()
    assert read_rows(report_path)[0]["action"] == "would_create"
    assert Prerequisite.objects.count() == 0
