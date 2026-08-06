"""Sync administrative directory rows to Staff and role assignments."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser

from app.people.services.administrative_directory_roles import (
    SyncOptions,
    sync_administrative_directory_roles,
)


class Command(BaseCommand):
    """Create/update administrative staff profiles and operational roles."""

    help = (
        "Synchronize registrar, finance, enrollment, and cashier roles from the "
        "TU directory. Dry-run by default; pass --apply to write database changes."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command options."""
        parser.add_argument("--xlsx", required=True, help="TU directory XLSX path.")
        parser.add_argument(
            "--google-csv",
            required=True,
            help="Google admin users export CSV path.",
        )
        parser.add_argument(
            "--audit-path",
            default="/tmp/tusis_role_sync/admin_directory_role_sync.csv",
            help="CSV audit output path.",
        )
        parser.add_argument(
            "--password",
            default="PassW0rd!",
            help="Password assigned only to newly created users.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply database writes. Omit for dry-run.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Run the administrative directory role synchronization."""
        sync_options = SyncOptions(
            xlsx_path=Path(str(options["xlsx"])),
            google_csv_path=Path(str(options["google_csv"])),
            audit_path=Path(str(options["audit_path"])),
            apply=bool(options["apply"]),
            password=str(options["password"]),
            today=date.today(),
        )
        counters = sync_administrative_directory_roles(sync_options)
        mode = "applied" if sync_options.apply else "dry-run"
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counters.items()))
        self.stdout.write(
            self.style.SUCCESS(
                f"Administrative directory role sync {mode}: {summary}. "
                f"Audit: {sync_options.audit_path}"
            )
        )
