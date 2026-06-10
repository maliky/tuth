"""Validate that preprod reflects an import-ready truth bundle."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from django.core.management.base import BaseCommand, CommandError, CommandParser

from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.requirement_group import CurriCrsReqMember
from app.finance.models.payment import Payment
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.source_truth.io import RowT, read_rows

CountsT: TypeAlias = dict[str, int]


class Command(BaseCommand):
    """Check loaded database counts and key revised-curriculum invariants."""

    help = "Validate preprod DB against import-ready truth files."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register validation options."""
        parser.add_argument(
            "--truth-dir",
            default="logs/tusis_truth/SmartSchoolDB_20260609/import_ready",
            help="Directory containing import-ready TSV files.",
        )
        parser.add_argument(
            "--min-ratio",
            type=float,
            default=0.95,
            help="Minimum accepted loaded/source ratio for registrations and grades.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run all validation checks."""
        truth_dir = Path(str(options["truth_dir"]))
        min_ratio_value = options.get("min_ratio", 0.95)
        min_ratio = (
            min_ratio_value
            if isinstance(min_ratio_value, float)
            else float(str(min_ratio_value))
        )
        expected = _expected_counts(truth_dir)
        actual = _actual_counts()
        failures: list[str] = []

        _at_least("courses", actual, expected, failures)
        _at_least("curricula", actual, expected, failures)
        _at_least("curriculum_courses", actual, expected, failures)
        _at_least("requirement_members", actual, expected, failures)
        _at_least("students", actual, expected, failures)
        _ratio("registrations", actual, expected, min_ratio, failures)
        _ratio("grades", actual, expected, min_ratio, failures)
        _at_least("payments", actual, expected, failures)
        _check_revised_curricula(truth_dir, failures)

        for name in sorted(expected):
            self.stdout.write(
                f"{name}: expected {expected[name]}, loaded {actual.get(name, 0)}"
            )
        if failures:
            raise CommandError("; ".join(failures))
        self.stdout.write(self.style.SUCCESS("Preprod truth validation passed."))


def _expected_counts(truth_dir: Path) -> CountsT:
    """Return expected counts from import-ready files."""
    return {
        "courses": _row_count(truth_dir / "academic_course.tsv"),
        "curricula": _row_count(truth_dir / "academic_curriculum.tsv"),
        "curriculum_courses": _row_count(truth_dir / "academic_curriculum_course.tsv"),
        "requirement_members": _requirement_member_count(
            truth_dir / "academic_curriculum_requirement.tsv"
        ),
        "students": len(_student_ids(truth_dir / "people_full_student.tsv")),
        "registrations": _row_count(truth_dir / "registry_registration.tsv"),
        "grades": _row_count(truth_dir / "full_grades.tsv"),
        "payments": _row_count(truth_dir / "finance_payments.tsv"),
    }


def _actual_counts() -> CountsT:
    """Return current database counts for import domains."""
    return {
        "courses": Course.objects.count(),
        "curricula": Curriculum.objects.count(),
        "curriculum_courses": CurriCrs.objects.count(),
        "requirement_members": CurriCrsReqMember.objects.count(),
        "students": Student.objects.count(),
        "registrations": Registration.objects.count(),
        "grades": Grade.objects.count(),
        "payments": Payment.objects.count(),
    }


def _student_ids(path: Path) -> set[str]:
    """Return distinct student ids from an import file."""
    return {row.get("student_id", "") for row in read_rows(path) if row.get("student_id")}


def _requirement_member_count(path: Path) -> int:
    """Count requirement members using the import resource identity."""
    return len({_requirement_member_key(row) for row in read_rows(path)})


def _requirement_member_key(row: RowT) -> tuple[str, ...]:
    """Return the deduplicating key used by CurriCrsRequirementResource."""
    return (
        row.get("curriculum_college_code") or row.get("college_code", ""),
        row.get("curriculum", ""),
        row.get("course_college_code") or row.get("college_code", ""),
        row.get("course_dept", ""),
        row.get("course_no", ""),
        row.get("requirement_kind", ""),
        row.get("requirement_label", "")[:80],
        row.get("required_course_college_code") or row.get("college_code", ""),
        row.get("required_course_dept", ""),
        row.get("required_course_no", ""),
    )


def _row_count(path: Path) -> int:
    """Count data rows in a TSV file."""
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _at_least(name: str, actual: CountsT, expected: CountsT, failures: list[str]) -> None:
    """Require DB count to cover the import-ready source count."""
    if actual.get(name, 0) < expected.get(name, 0):
        failures.append(f"{name} loaded below expected")


def _ratio(
    name: str,
    actual: CountsT,
    expected: CountsT,
    min_ratio: float,
    failures: list[str],
) -> None:
    """Require DB count to meet a source coverage ratio."""
    expected_count = expected.get(name, 0)
    if not expected_count:
        return
    if actual.get(name, 0) / expected_count < min_ratio:
        failures.append(f"{name} loaded below {min_ratio:.0%} of source")


def _check_revised_curricula(truth_dir: Path, failures: list[str]) -> None:
    """Require revised TUCurricula rows to be active and approved."""
    revised_codes = {
        row.get("curriculum", "")
        for row in read_rows(truth_dir / "academic_curriculum.tsv")
        if _is_revised(row)
    }
    if not revised_codes:
        failures.append("no revised curricula found in truth bundle")
        return
    loaded = set(
        Curriculum.objects.filter(
            short_name__in=revised_codes,
            is_active=True,
            status_id="approved",
        ).values_list("short_name", flat=True)
    )
    missing = revised_codes - loaded
    if missing:
        failures.append(f"missing active approved revised curricula: {len(missing)}")


def _is_revised(row: RowT) -> bool:
    """Return whether a curriculum row represents the revised catalog."""
    return row.get("status") == "approved" and row.get("is_active") == "true"
