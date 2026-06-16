"""Tests for TUCurricula course-description backfill."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from app.academics.course_description_backfill import backfill_course_descriptions
from app.academics.models import Course, Department
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
ALIAS_HEADERS = (
    "source_course_dept",
    "source_course_no",
    "target_course_dept",
    "target_course_no",
    "reason",
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


def _write_import_dir(import_dir: Path, rows: list[dict[str, str]]) -> None:
    """Write an academic_course.tsv fixture."""
    _write_tsv(import_dir / "academic_course.tsv", COURSE_HEADERS, rows)


def _write_aliases(path: Path, rows: list[dict[str, str]] | None = None) -> None:
    """Write an approved-alias TSV fixture."""
    _write_tsv(path, ALIAS_HEADERS, rows or [])


def _course(dept_code: str, number: str, title: str, description: str = "") -> Course:
    """Create one current TUSIS course."""
    return Course.objects.create(
        department=Department.get_dft(dept_code),
        number=number,
        title=title,
        description=description,
    )


def _source_row(
    dept_code: str,
    number: str,
    title: str,
    description: str,
) -> dict[str, str]:
    """Return one TUCurricula course TSV row."""
    return {
        "college_code": "CAS",
        "course_college_code": "CAS",
        "course_dept": dept_code,
        "course_no": number,
        "course_title": title,
        "credit_hours": "3",
        "description": description,
        "source_course_key": f"{dept_code}{number}",
        "source_files": "test.org",
    }


def test_backfill_dry_run_reports_without_mutating(tmp_path: Path) -> None:
    """Dry-run should report exact matches but leave Course unchanged."""
    import_dir = tmp_path / "import"
    aliases = tmp_path / "aliases.tsv"
    report_path = tmp_path / "report.tsv"
    _write_import_dir(
        import_dir,
        [_source_row("BIOL", "101", "Biology I", "Living systems.")],
    )
    _write_aliases(aliases)
    course = _course("BIOL", "101", "Biology I")

    summary = backfill_course_descriptions(
        import_dir=import_dir,
        approved_aliases_path=aliases,
        report_path=report_path,
    )

    course.refresh_from_db()
    rows = read_rows(report_path)
    assert summary.would_update == 1
    assert summary.updated == 0
    assert course.description == ""
    assert rows[0]["action"] == "would_update"
    assert rows[0]["match_method"] == "exact_course_key"


def test_backfill_apply_updates_blank_exact_description(tmp_path: Path) -> None:
    """Apply mode should fill a blank description from an exact source key."""
    import_dir = tmp_path / "import"
    aliases = tmp_path / "aliases.tsv"
    _write_import_dir(
        import_dir,
        [_source_row("MATH", "101", "College Algebra", "Algebra foundations.")],
    )
    _write_aliases(aliases)
    course = _course("MATH", "101", "College Algebra")

    summary = backfill_course_descriptions(
        import_dir=import_dir,
        approved_aliases_path=aliases,
        apply=True,
    )

    course.refresh_from_db()
    assert summary.updated == 1
    assert course.description == "Algebra foundations."


def test_backfill_uses_safe_close_department_title_match(tmp_path: Path) -> None:
    """Legacy PSY101 can inherit a PSYC101 description when title and number match."""
    import_dir = tmp_path / "import"
    aliases = tmp_path / "aliases.tsv"
    report_path = tmp_path / "report.tsv"
    _write_import_dir(
        import_dir,
        [
            _source_row(
                "PSYC",
                "101",
                "Introduction to Psychology",
                "History, theories, and methods in psychology.",
            )
        ],
    )
    _write_aliases(aliases)
    course = _course("PSY", "101", "Introduction to Psychology")

    summary = backfill_course_descriptions(
        import_dir=import_dir,
        approved_aliases_path=aliases,
        report_path=report_path,
        apply=True,
    )

    course.refresh_from_db()
    rows = read_rows(report_path)
    assert summary.updated == 1
    assert course.description.startswith("History, theories")
    assert rows[0]["source_course_key"] == "PSYC101"
    assert rows[0]["match_method"] == "same_number_close_dept_title"


def test_backfill_skips_existing_description_by_default(tmp_path: Path) -> None:
    """Existing descriptions should not be overwritten unless explicitly requested."""
    import_dir = tmp_path / "import"
    aliases = tmp_path / "aliases.tsv"
    _write_import_dir(
        import_dir,
        [_source_row("CHEM", "101", "Chemistry I", "New description.")],
    )
    _write_aliases(aliases)
    course = _course("CHEM", "101", "Chemistry I", "Existing description.")

    summary = backfill_course_descriptions(
        import_dir=import_dir,
        approved_aliases_path=aliases,
        apply=True,
    )

    course.refresh_from_db()
    assert summary.skipped_existing == 1
    assert course.description == "Existing description."


def test_backfill_skips_ambiguous_close_department_matches(tmp_path: Path) -> None:
    """Same-score fuzzy candidates should be audited instead of applied."""
    import_dir = tmp_path / "import"
    aliases = tmp_path / "aliases.tsv"
    report_path = tmp_path / "report.tsv"
    _write_import_dir(
        import_dir,
        [
            _source_row("ABCD", "101", "Shared Course", "First description."),
            _source_row("ABCE", "101", "Shared Course", "Second description."),
        ],
    )
    _write_aliases(aliases)
    course = _course("ABC", "101", "Shared Course")

    summary = backfill_course_descriptions(
        import_dir=import_dir,
        approved_aliases_path=aliases,
        report_path=report_path,
        apply=True,
    )

    course.refresh_from_db()
    rows = read_rows(report_path)
    assert summary.skipped_ambiguous == 1
    assert course.description == ""
    assert rows[0]["action"] == "skipped_ambiguous"


def test_backfill_command_defaults_to_dry_run(tmp_path: Path) -> None:
    """Management command should run in dry-run mode unless --apply is passed."""
    import_dir = tmp_path / "import"
    aliases = tmp_path / "aliases.tsv"
    report_path = tmp_path / "command-report.tsv"
    _write_import_dir(
        import_dir,
        [_source_row("HIST", "201", "Liberian History", "Liberian history.")],
    )
    _write_aliases(aliases)
    course = _course("HIST", "201", "Liberian History")
    output = StringIO()

    call_command(
        "backfill_tucurricula_course_descriptions",
        import_dir=str(import_dir),
        approved_aliases=str(aliases),
        report_path=str(report_path),
        stdout=output,
    )

    course.refresh_from_db()
    assert course.description == ""
    assert "dry-run" in output.getvalue()
    assert read_rows(report_path)[0]["action"] == "would_update"
