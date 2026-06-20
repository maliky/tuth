"""Audit and optionally merge duplicate student records."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser

from app.people.models.student import Student
from app.people.services.student_duplicate_merge import (
    StudentMergeConflictT,
    safe_merge_student,
)
from app.people.services.student_duplicates import (
    StudentDuplicateGroupT,
    duplicate_sources,
    student_duplicate_groups,
    student_operational_counts,
)


class Command(BaseCommand):
    """Report exact/case student-id duplicates and sensitive numeric overlaps."""

    help = "Audit duplicate student records; --apply merges only safe exact-id groups."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register duplicate-audit options."""
        parser.add_argument(
            "--student-id",
            default="",
            help="Limit the audit to one student id or numeric overlap key.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
            help="Maximum groups to print for each duplicate category.",
        )
        parser.add_argument(
            "--include-numeric-overlaps",
            action="store_true",
            help="Also print bare-number/TU-prefixed overlaps for manual review.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Merge safe exact-id duplicates. Numeric overlaps are never merged.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the duplicate audit and optional exact-id merge."""
        student_id = str(options.get("student_id") or "")
        limit = _positive_int(options.get("limit"), default=25)
        apply_merges = bool(options.get("apply"))
        include_numeric = bool(options.get("include_numeric_overlaps")) or bool(
            student_id
        )
        exact_groups = student_duplicate_groups(
            kind="exact_id",
            student_id=student_id or None,
        )
        self._write_group_header("Exact/case student-id duplicates", exact_groups)
        for group in exact_groups[:limit]:
            self._write_exact_group(group, apply_merges=apply_merges)

        if include_numeric:
            numeric_groups = student_duplicate_groups(
                kind="numeric_overlap",
                student_id=student_id or None,
            )
            self._write_group_header("Numeric overlaps for manual review", numeric_groups)
            for group in numeric_groups[:limit]:
                self._write_numeric_group(group)

        if not exact_groups and not include_numeric:
            self.stdout.write(self.style.SUCCESS("No exact/case duplicates found."))

    def _write_group_header(
        self,
        label: str,
        groups: list[StudentDuplicateGroupT],
    ) -> None:
        """Print one duplicate category heading."""
        self.stdout.write(f"{label}: {len(groups)} group(s)")

    def _write_exact_group(
        self,
        group: StudentDuplicateGroupT,
        *,
        apply_merges: bool,
    ) -> None:
        """Print and optionally apply one exact duplicate group."""
        target, sources = duplicate_sources(group.students)
        self.stdout.write(f"  key={group.key} target={_student_label(target)}")
        self._write_student_rows(group.students)
        for source in sources:
            result = safe_merge_student(target, source, apply=apply_merges)
            if result.conflicts:
                self.stdout.write(
                    self.style.WARNING(
                        f"    blocked source={_student_label(source)} "
                        f"conflicts={_conflict_text(result.conflicts)}"
                    )
                )
                continue
            verb = "merged" if result.applied else "dry-run"
            self.stdout.write(
                self.style.SUCCESS(
                    f"    {verb} source={_student_label(source)} counts={result.counts}"
                )
            )

    def _write_numeric_group(self, group: StudentDuplicateGroupT) -> None:
        """Print one sensitive numeric-overlap group without merging."""
        self.stdout.write(f"  digits={group.key} manual-review-only")
        self._write_student_rows(group.students)

    def _write_student_rows(self, students: list[Student]) -> None:
        """Print duplicate members with their operational counts."""
        for student in students:
            self.stdout.write(
                f"    {_student_label(student)} counts={student_operational_counts(student)}"
            )


def _student_label(student: Student) -> str:
    """Return a compact student label for command output."""
    name = student.long_name or student.username or "-"
    return f"pk={student.pk} id={student.student_id} name={name}"


def _positive_int(value: object, *, default: int) -> int:
    """Return a positive integer option value or its default."""
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdecimal():
        parsed = int(value)
        if parsed > 0:
            return parsed
    return default


def _conflict_text(conflicts: list[StudentMergeConflictT]) -> str:
    """Return a compact conflict summary for command output."""
    return "; ".join(f"{conflict.model_name}:{conflict.key}" for conflict in conflicts)
