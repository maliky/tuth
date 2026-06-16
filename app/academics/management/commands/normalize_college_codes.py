"""Normalize stored college codes to the canonical TU acronym set."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from app.academics.college_normalization import normalize_college_records


class Command(BaseCommand):
    """CLI helper for applying canonical college acronym data fixes."""

    help = "Normalize college rows to CAS/CBA/EDRCE/CET/CHS and supported defaults."

    def handle(self, *args: object, **options: object) -> None:
        """Run the college normalization inside one database transaction."""
        result = normalize_college_records()
        self.stdout.write(
            self.style.SUCCESS(
                "College codes normalized "
                f"(created={result.created}, renamed={result.renamed}, "
                f"merged={result.merged}, related_updates={result.related_updates}, "
                f"curriculum_updates={result.curriculum_updates}, "
                f"derived_code_updates={result.derived_code_updates})"
            )
        )
